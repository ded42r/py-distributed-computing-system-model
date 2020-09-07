# coding: utf8
from __future__ import print_function

import logging
import socket
import time
from functools import partial
from threading import Event

from entities import CalculatorStatus, TaskStatus
from net_protocol import INetClient, ResponseConfirmation, TransmissionStatus
from utils import call_repeatedly

try:
    from typing import Optional, Dict, Tuple, Any
except ImportError:
    pass

logger = logging.getLogger()


class CalculatorInfo(object):
    def __init__(self, state=None):
        # type: (int) -> None
        self.state = state
        self.last_update_tm = None
        self.update_tm()

    def update_tm(self):
        # type: () -> None
        self.last_update_tm = time.time()


class TaskInfo(object):
    def __init__(self):
        # type: () -> None
        self.client_address = None  # type: Optional[Tuple[str, int]]
        self.calculator_address = None  # type: Optional[Tuple[str, int]]
        self.status = None  # type: Optional[int]
        self.task_params = None  # type: Optional[dict]
        self.created_tm = time.time()


class Dispatcher(object):
    def __init__(self, net_client_class, address, **kwargs):
        # type: (INetClient, Tuple[str, int], **Any) -> None
        addr = (
            socket.gethostbyname(address[0]),
            address[1],
        )
        self.net_client = net_client_class(addr)
        self.net_client.add_handler_request(self.handle_message)

        self.calculators = {}  # type: Dict[Tuple[str, int], CalculatorInfo]
        self.tasks = {}  # type: Dict[str, TaskInfo]

        self.timeout_task_placement = kwargs.get(
            "timeout_task_placement", 120
        )  # type: float
        self.repeater_unsuccessful_tasks_event = None  # type: Event
        self.repeater_unsuccessful_tasks_interval = 1  # type: float

        self.activity_poll_event = None  # type: Event
        self.activity_poll_sec = kwargs.get("activity_poll_sec", 10.0)  # type: float
        self.inactivity_timeout = kwargs.get("inactivity_timeout", 10.0)  # type: float

    def start(self):
        # type: () -> None
        try:
            self.activity_poll_event = call_repeatedly(
                self.activity_poll_sec, self.activity_poll
            )
            self.repeater_unsuccessful_tasks_event = call_repeatedly(
                self.repeater_unsuccessful_tasks_interval,
                self.repeat_unsuccessful_tasks,
            )
            self.net_client.serve_forever()
        except KeyboardInterrupt:
            logger.info("Ctrl+C Pressed. Shutting down.")

    def handle_message(self, address, message):
        # type: (Tuple[str, int], dict) -> ResponseConfirmation
        logger.debug("адрес: {} data: {}".format(address, message))

        if message["method"] == "add_task":
            return self.add_task_handler(address, message)

        if message["method"] == "heartbeat":
            return self.heartbeat_handler(address, message)

        if message["method"] == "completed_task":
            return self.completed_task_handler(address, message)

    def heartbeat_handler(self, address, message):
        # type: (Tuple[str, int], dict) -> ResponseConfirmation
        calculator_info = self.calculators.get(address, CalculatorInfo())
        calculator_info.state = int(message["params"]["status"])
        calculator_info.update_tm()
        self.calculators[address] = calculator_info
        return ResponseConfirmation(data=None)

    def completed_task_handler(self, address, message):
        # type: (Tuple[str, int], dict) -> ResponseConfirmation
        task_uuid = message["params"]["task_uuid"]
        try:
            task_info = self.tasks[task_uuid]
        except KeyError:
            logger.error(
                "Не найдено задачи {}. Уведомление от {}, данные: {}".format(
                    task_uuid, address, message
                )
            )
            return ResponseConfirmation(data=None)

        # 0. Обновляем задачу в реестре задач
        task_info.status = TaskStatus.solved
        task_info.calculator_address = None

        # 0. Меняет статус вычислителя:
        calculator_info = self.calculators.get(address, CalculatorInfo())
        calculator_info.state = CalculatorStatus.ready
        calculator_info.update_tm()
        self.calculators[address] = calculator_info

        # 0. Отправить клиенту команду notify_task
        params = {"status": "success"}
        params.update(task_info.task_params)
        data = self.__generate_command("notify_task", params)
        self.net_client.send_command(
            task_info.client_address, data, self.echo_callback_calculator
        )
        task_info.status = TaskStatus.sent_to_client

        # 0. отправляется подтверждение вычислителю
        return ResponseConfirmation(data=None)

    def add_task_handler(self, address, message):
        # type: (Tuple[str, int], dict) -> ResponseConfirmation
        client_task_id = message["params"]["task_id"]
        task_uuid = self.__generate_task_uuid(address, client_task_id)
        task_info = self.tasks.get(task_uuid)
        if task_info:
            logger.warning(
                "Запрос на выполнение задачи от {} c id {} уже поступала".format(
                    address, client_task_id
                )
            )
            return ResponseConfirmation(data=None)

        task_info = TaskInfo()
        task_info.client_address = address
        task_info.task_params = message["params"]
        task_info.status = TaskStatus.accepted_from_client
        self.tasks[task_uuid] = task_info
        self.find_calculator_for_task(task_uuid)
        return ResponseConfirmation(data=None)

    def find_calculator_for_task(self, task_uuid):
        # type: (str) -> None
        task_info = self.tasks[task_uuid]
        for calc_addr in list(self.calculators.keys()):
            calc_info = self.calculators[calc_addr]
            if calc_info.state == CalculatorStatus.ready:
                calc_info.state = CalculatorStatus.busy
                task_info.calculator_address = calc_addr
                data = self.__generate_command("perform_task", {"task_uuid": task_uuid})
                self.net_client.send_command(
                    calc_addr,
                    data,
                    partial(self.update_task_status_callback, task_uuid=task_uuid),
                )
                task_info.status = TaskStatus.sent_to_calculator
                break
        if task_info.calculator_address is None:
            task_info.status = TaskStatus.error_accepted_calculator
            logger.warning(
                "Не найден свободный вычислитель для задачи {}".format(task_uuid)
            )

    def __generate_task_uuid(self, client_address, task_id):
        # type: (Tuple[str, int], int) -> str
        return "{}:{}:{}".format(client_address[0], client_address[1], task_id)

    def update_task_status_callback(self, address, transmission_id, status, task_uuid):
        # type: (Tuple[str, int], int, int, str) -> None
        task_info = self.tasks[task_uuid]
        if status == TransmissionStatus.success:
            calculator_info = self.calculators[address]
            calculator_info.update_tm()
            task_info.status = TaskStatus.accepted_for_execution_calculator
        elif status == TransmissionStatus.failure:
            calculator_info = self.calculators[address]
            calculator_info.state = CalculatorStatus.not_available
            calculator_info.update_tm()
            task_info.status = TaskStatus.error_accepted_calculator

    def echo_callback_calculator(self, address, transmission_id, status):
        # type: (Tuple[str, int], int, int) -> None
        logger.debug(
            "Адрес: {}, transmission_id: {}, статус: {}".format(
                address, transmission_id, TransmissionStatus.code2status_name(status)
            )
        )

    def repeat_unsuccessful_tasks(self):
        # type: () -> None
        """ отправляем неразмещенные задачи повторно """
        for task_uuid in list(self.tasks.keys()):
            task_info = self.tasks[task_uuid]
            if time.time() - task_info.created_tm >= self.timeout_task_placement:
                logger.error(
                    "Не удалось разместить задачу {} принятую от {}. Информация о задаче: {}".format(
                        task_uuid, task_info.client_address, task_info.task_params
                    )
                )
                task_info.status = TaskStatus.error_placement_timeout
                continue
            if task_info.status in (
                TaskStatus.accepted_from_client,
                TaskStatus.error_accepted_calculator,
            ):
                self.find_calculator_for_task(task_uuid)

    def activity_poll(self):
        # type: () -> None
        current_tm = time.time()
        for calc_addr in list(self.calculators.keys()):
            calc_info = self.calculators[calc_addr]
            if calc_info.last_update_tm is None:
                calc_info.update_tm()
            if current_tm - calc_info.last_update_tm >= self.inactivity_timeout:
                data = self.__generate_command("status", {})
                self.net_client.send_command(
                    calc_addr, data, self.activity_poll_callback
                )

    def activity_poll_callback(self, address, transmission_id, status):
        # type: (Tuple[str, int], int, int) -> None
        if status == TransmissionStatus.success:
            self.calculators[address].update_tm()
        elif status == TransmissionStatus.failure:
            calculator_info = self.calculators[address]
            calculator_info.state = CalculatorStatus.not_available
            calculator_info.update_tm()
            logger.debug("Вычислитель {} не отвечает".format(address))

    def __generate_command(self, method, params):
        # type: (str, dict) -> dict
        return {"method": method, "params": params}
