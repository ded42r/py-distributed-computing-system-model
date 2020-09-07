# coding: utf8
from __future__ import print_function

import logging
import time
from threading import Thread

try:
    from typing import Callable
except ImportError:
    pass

logger = logging.getLogger(__name__)


class CalculatorTask(object):
    def __init__(self, duration, callback):

        # type: (float, Callable) -> None
        self.duration = duration
        self.callback = callback
        self.__thread = Thread(target=self.do_job)
        self.__thread.daemon = True

    def start(self):
        # type: () -> None
        self.__thread.start()

    def do_job(self):
        # type: () -> None
        logger.debug("Задача будет выполнена через %.2f секунд", self.duration)
        time.sleep(self.duration)
        logger.debug("Задача выполнена")
        self.callback()
