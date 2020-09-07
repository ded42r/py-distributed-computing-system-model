# coding: utf8
from __future__ import print_function

import logging as logging
import random
import sys
import threading
import time
from collections import OrderedDict
from functools import partial
from signal import SIGABRT, SIGINT, SIGTERM, signal

from entities import TaskStatus
from net_protocol import INetClient, ResponseConfirmation, TransmissionStatus

try:
    from typing import Tuple, Any, Optional, Dict
except ImportError:
    pass

logger = logging.getLogger(__name__)


class ClientTaskInfo(object):
    def __init__(self, task_id, status=None):
        # type: (int, Optional[int]) -> None
        self.task_id = task_id  # type: int
        self.status = status  # type: Optional[int]
        self.created_tm = time.time()
        self.done_tm = None  # type: Optional[float]

    def done(self):
        # type: () -> None
        self.status = TaskStatus.resolved
        self.done_tm = time.time()


class Client(object):
    def __init__(self, net_client_class, dispatcher_address, task_duration, **kwargs):
        # type: (INetClient, Tuple[str, int], Tuple[float, float], **Any) -> None
        self.net_client = net_client_class(("", kwargs.get("client_port", 0)))
        self.net_client.add_handler_request(self.handle_request)

        self.dispatcher_address = dispatcher_address
        self.task_duration = task_duration

        self.is_alive = True
        self.task_id = 0
        self.tasks = OrderedDict()  # type: Dict[int, ClientTaskInfo]
        self.thread_generator_task = threading.Thread(target=self.__generate_task)

    def start(self):
        # type: () -> None
        self.register_signal_handler()
        self.thread_generator_task.start()
        self.net_client.serve_forever()

    def print_stat(self):
        task_ids = list(self.tasks.keys())
        execution_times = []
        for task_id in task_ids:
            task = self.tasks[task_id]
            if task.done_tm:
                execution_times.append(task.done_tm - task.created_tm)
        count_solved = len(execution_times)
        count_created = len(task_ids)
        print("Задач создано:", count_created)
        print("Задач решено:", count_solved)
        print("Задач не решено:", count_created - count_solved)
        if count_solved > 0:
            print(
                "min/avg/max решения: {:.2f}/{:.2f}/{:.2f} сек".format(
                    min(execution_times),
                    sum(execution_times) / count_solved,
                    max(execution_times),
                )
            )
        else:
            print("min/avg/max недоступно потому что не решено ни одной задачи")

    def handle_request(self, address, message):
        # type: (Tuple[str, int], dict) -> ResponseConfirmation
        if message["method"] == "notify_task":
            return self.notify_task_handler(message)

        logger.warning(
            "Получен неизвестный запрос c адреса {}, сообщение: {}".format(
                address, message
            )
        )

    def notify_task_handler(self, message):
        # type: (dict) -> ResponseConfirmation
        done_task_id = message["params"]["task_id"]
        try:
            self.tasks[done_task_id].done()
            logger.debug("Задача {}. решена".format(done_task_id))
            return ResponseConfirmation(data=None)
        except KeyError:
            logger.error(
                "Получен запрос о выполнении неизвестной задачи {}. Запрос: {}".format(
                    done_task_id, message
                )
            )

    def __generate_task(self):
        # type: () -> None
        while self.is_alive:
            delay = random.uniform(*self.task_duration)
            time.sleep(delay)
            if not self.is_alive:
                break
            try:
                self.tasks[self.task_id] = ClientTaskInfo(
                    self.task_id, TaskStatus.sent_to_dispatcher
                )
                self.net_client.send_command(
                    self.dispatcher_address,
                    self.__generate_command("add_task", {"task_id": self.task_id}),
                    partial(self.__add_task_callback, task_id=self.task_id),
                )
                self.task_id += 1
                logger.debug("Новая задача {}".format(self.task_id))
            except:
                logger.exception("Ошибка при генерации задания")

    def __add_task_callback(self, address, transmission_id, status, task_id):
        # type: (Tuple[str, int], int, int, int) -> None
        if status == TransmissionStatus.success:
            logger.debug("Задача {} принята диспетчером".format(task_id))
        elif status == TransmissionStatus.failure:
            logger.debug(
                "Не удалось передать задачу {} диспетчеру. transmission_id: {}".format(
                    task_id, transmission_id
                )
            )

    def __generate_command(self, method, params):
        # type: (str, dict) -> dict
        return {"method": method, "params": params}

    def register_signal_handler(self):
        # type: () -> None
        if sys.platform != "win32":
            for sig in (SIGINT, SIGTERM, SIGABRT):
                signal(sig, self.signal_handler)

    def signal_handler(self, signum, frame):
        logger.warning("Получен сигнал {}, остановка...".format(signum))
        self.is_alive = False
        self.thread_generator_task.join()
        self.net_client.shutdown()
