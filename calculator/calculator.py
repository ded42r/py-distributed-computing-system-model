# coding: utf8
from __future__ import print_function

import logging
import random
import socket
from collections import namedtuple
from threading import Event

from entities import CalculatorStatus
from net_protocol import INetClient, ResponseConfirmation, TransmissionStatus
from utils import call_repeatedly

from .calculator_interface import ICalculator
from .calculator_task import CalculatorTask

try:
    from typing import Optional, Tuple, Any
except ImportError:
    pass

logger = logging.getLogger(__name__)

TaskContainer = namedtuple("TaskContainer", ["runner", "params"])


class Calculator(ICalculator):
    def __init__(self, net_client_class, dispatcher_address, **kwargs):
        # type: (INetClient, Tuple[str, int], **Any) -> None
        self.dispatcher_address = (
            socket.gethostbyname(dispatcher_address[0]),
            dispatcher_address[1],
        )
        self.listen_port = kwargs.get("listen_port", 0)  # type: int
        self.net_client = net_client_class(("", self.listen_port))
        self.net_client.add_handler_request(self.handle_message_dispatcher)

        self.status = CalculatorStatus.ready
        self.task_duration = kwargs["task_duration"]  # type: Tuple[float, float]
        self.__task = None  # type: Optional[TaskContainer]
        self.heartbeat_sec = kwargs.get("heartbeat", 5)  # type: float
        self.heartbeat_event = None  # type: Optional[Event]

    def start(self):
        # type: () -> None
        try:
            # регистрация вычислителя в диспетчере
            self.heartbeat()
            self.heartbeat_event = call_repeatedly(self.heartbeat_sec, self.heartbeat)
            self.net_client.serve_forever()
        except KeyboardInterrupt:
            logger.info("Ctrl+C Pressed. Shutting down.")

    def shutdown(self, immediate=False):
        # type: (bool) -> None
        """ остановка вычислителя.
            Если immediate = True, то все задания прерываются """
        if self.heartbeat_event:
            self.heartbeat_event.set()
        self.net_client.shutdown(immediate=immediate)

    def handle_message_dispatcher(self, address, message):
        # type: (Tuple[str, int], dict) -> ResponseConfirmation
        logger.debug(
            "Получено сообщение с адреса: {}, данные: {}".format(address, message)
        )

        if message["method"] == "perform_task":
            return self.perform_task_handler(message)

        if message["method"] == "status":
            return ResponseConfirmation(data={"status": self.status})

    def perform_task_handler(self, message):
        # type: (dict) -> ResponseConfirmation
        if self.status == CalculatorStatus.ready:
            self.perform_task(message["params"])
            return ResponseConfirmation(data=None)
        else:
            field_task_id = "task_uuid"
            if self.__task and message["params"][
                field_task_id
            ] == self.__task.params.get(field_task_id):
                logger.warning(
                    "Повторно получено задача которая уже находится в обработке {}".format(
                        self.status
                    )
                )
                return ResponseConfirmation(data=None)
            else:
                logger.warning(
                    "Вычислитель получил задачу, но при этом находится в недоступном статусе {}".format(
                        self.status
                    )
                )

    def perform_task(self, task_params):
        # type: (dict) -> None
        self.status = CalculatorStatus.busy
        task_runner = CalculatorTask(
            random.uniform(*self.task_duration), self.__task_completed_callback,
        )
        self.__task = TaskContainer(runner=task_runner, params=task_params)
        task_runner.start()

    def heartbeat(self):
        # type: () -> None
        data = self.__generate_command("heartbeat", {"status": self.status})
        self.net_client.send_command_without_confirmation(self.dispatcher_address, data)

    def __task_completed_callback(self):
        # type: () -> None
        logger.debug("Задача выполнена. {}".format(self.__task.params))

        self.status = CalculatorStatus.ready
        data = self.__generate_command("completed_task", self.__task.params)
        self.__task = None
        self.net_client.send_command(
            self.dispatcher_address, data, self.__confirmation_echo
        )

    def __confirmation_echo(self, address, transmission_id, status):
        # type: (Tuple[str, int], int, int) -> None
        if status == TransmissionStatus.success:
            logger.debug("Результат задачи успешно отправлен диспетчеру")
        elif status == TransmissionStatus.failure:
            logger.error(
                "Ошибка при отправке результат задачи. Адрес: {}, команда: {}, статус: {}".format(
                    address,
                    transmission_id,
                    TransmissionStatus.code2status_name(status),
                )
            )

    def __generate_command(self, method, params):
        # type: (str, dict) -> dict
        return {"method": method, "params": params}
