# coding: utf8
from abc import ABCMeta, abstractmethod


class ICalculator:
    __metaclass__ = ABCMeta

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def shutdown(self, immediate=False):
        # type: (bool) -> None
        """ остановка вычислителя.
            Если immediate = True, то все задания прерываются """
        pass
