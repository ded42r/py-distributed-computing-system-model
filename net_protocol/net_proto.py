# coding: utf8
from collections import Callable, namedtuple

try:
    from typing import Tuple, Iterable
except ImportError:
    pass


class PacketType(object):
    no_answer, request, response = range(3)

    @classmethod
    def get_states(cls):
        # type: () -> Iterable[int]
        return (
            cls.no_answer,
            cls.request,
            cls.response,
        )


class TransmissionStatus:
    pending, success, failure = range(3)

    @classmethod
    def code2status_name(cls, code):
        # type: (int) -> str
        for name, status_code in cls.__dict__.iteritems():
            if code == status_code:
                return name


class NetCommand(object):
    def __init__(
        self,
        address,  # type: Tuple[str, int]
        data,  # type: dict
        packet_type,  # type: int
        transmission_id,  # type: int
        callback,  # type: Callable
        attempts=0,  # type: int
    ):
        self.__address = None
        self.__packet_type = None
        self.__callback = None
        self.__transmission_id = None

        self.address = address
        self.data = data
        self.transmission_id = transmission_id
        self.packet_type = packet_type
        self.callback = callback
        self.attempts = attempts

    @property
    def address(self):
        return self.__address

    @address.setter
    def address(self, value):
        if not (isinstance(value[0], (str, unicode)) and (0 <= value[1] <= 65535)):
            raise ValueError(
                "address должен быть в формате (str, (0 <= port <= 65535))"
            )
        self.__address = value

    @property
    def packet_type(self):
        return self.__packet_type

    @packet_type.setter
    def packet_type(self, value):
        allowed_values = PacketType.get_states()
        if value not in allowed_values:
            raise ValueError("packet_type должно принимать значения из списка ")
        self.__packet_type = value

    @property
    def callback(self):
        return self.__callback

    @callback.setter
    def callback(self, value):
        if self.packet_type == PacketType.request:
            if value is None:
                raise ValueError(
                    "Для типа пакета с гарантированной доставкой callback не может быть пустым"
                )
            elif not isinstance(value, Callable):
                raise ValueError("Callback не функция")
        self.__callback = value

    @property
    def transmission_id(self):
        return self.__transmission_id

    @transmission_id.setter
    def transmission_id(self, value):
        if value is None:
            raise ValueError("transmission_id не может быть пустым")
        self.__transmission_id = value


ResponseConfirmation = namedtuple("ResponseConfirmation", ["data"])
