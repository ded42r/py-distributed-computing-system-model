# coding: utf8
from __future__ import print_function

try:
    from typing import Optional, Callable, Tuple
except ImportError:
    pass


class CalculatorStatus(object):
    ready, busy, not_available = range(3)


class TaskStatus(object):
    # создана клиентом
    created = 0
    # отправлена диспетчеру клиентом
    sent_to_dispatcher = 1
    # получена от клиента диспетчером
    accepted_from_client = 2
    # отправлена вычислителю диспетчером
    sent_to_calculator = 3
    # принята на выполнение вычислителем, диспетчер получил подтверждение
    accepted_for_execution_calculator = 4
    # ошибка размещения задачи диспетчером
    error_accepted_calculator = 5
    # ошибка размещения задачи диспетчером (истек таймаут)
    error_placement_timeout = 6
    # решена вычислителем, получена диспетчером
    solved = 7
    # отправлена клиенту диспетчером
    sent_to_client = 8
    # решена, клиент получил от диспетчера выполненную задачу
    resolved = 9
