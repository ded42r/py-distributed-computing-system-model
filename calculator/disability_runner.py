# coding: utf8
from __future__ import print_function

import logging
import random
import threading
import time
from threading import Thread

from .calculator_interface import ICalculator

try:
    from typing import Optional, Callable, Tuple
except ImportError:
    pass


logger = logging.getLogger(__name__)


class DisabilityRunner(object):
    def __init__(self, calculator_fabric, **config):
        # type: (Callable[[], ICalculator], **float) -> None
        self.calculator_fabric = calculator_fabric  # type: Callable
        self.calculator = None  # type: Optional[ICalculator]
        self.calculator_thread = None  # type: Optional[Thread]

        self.disability_probability = config["probability"]  # type: float
        self.disability_duration = config["duration"]  # type: Tuple[float, float]
        self.poll_interval = config.get("poll_interval", 1.0)  # type: float

    def serve_forever(self):
        # type: () -> None
        while True:
            if self.calculator is None:
                self.start_calc()
            time.sleep(self.poll_interval)
            if self.is_disability_chance():
                logger.debug(
                    "Переход в режим неработоспособности. Вычислитель экстренно завершается"
                )
                self.stop_calculator()
                self.go_disability_mode()

    def start_calc(self):
        # type: () -> None
        self.calculator = self.calculator_fabric()  # type: ICalculator
        self.calculator_thread = threading.Thread(target=self.calculator.start)
        self.calculator_thread.start()

    def stop_calculator(self):
        # type: () -> None
        self.calculator.shutdown(True)
        self.calculator_thread.join(None)
        if self.calculator_thread.is_alive():
            logger.warning("Поток вычислителя все еще жив")
        self.calculator = None

    def go_disability_mode(self):
        # type: () -> None
        delay = random.uniform(*self.disability_duration)
        logger.debug("Режим неработоспособности активирован на {} сек".format(delay))
        time.sleep(delay)
        logger.debug("Период неработоспособности закончен")

    def is_disability_chance(self):
        # type: () -> bool
        return self.disability_probability >= random.random()
