# coding: utf8
from abc import ABCMeta, abstractmethod

from .net_proto import ResponseConfirmation

try:
    from typing import Callable, Tuple, Any
except ImportError:
    pass


class INetClient(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, address, **kwargs):
        # type: (Tuple[str, int], **Any) -> None
        pass

    @abstractmethod
    def serve_forever(self):
        # type: () -> None
        pass

    @abstractmethod
    def shutdown(self, immediate):
        # type: (bool) -> None
        pass

    @abstractmethod
    def send_command(self, address, data, callback):
        # type: (Tuple[str, int], dict, Callable[[Tuple[str, int], int, int], None]) -> None
        """ отправить команду с подтверждением """
        pass

    @abstractmethod
    def send_command_without_confirmation(self, address, data):
        # type: (Tuple[str, int], dict) -> None
        """ отправить команду без подтверждения """
        pass

    @abstractmethod
    def add_handler_request(self, callback):
        # type: (Callable[[Tuple[str, int], dict], ResponseConfirmation]) -> None
        """ добавить обработчик входящих команд """
        pass
