# coding: utf8
from __future__ import print_function

import json
import logging
import socket
import threading
import time
from collections import OrderedDict

from .client_interface import INetClient
from .net_proto import NetCommand, PacketType, ResponseConfirmation, TransmissionStatus

try:
    from typing import Optional, Callable, Tuple, Any, Dict
except ImportError:
    pass

logger = logging.getLogger(__name__)

MSG_FIELD_PACKET_TYPE = "packet_type"
MSG_FIELD_TRANSMISSION_ID = "transmission_id"


class NetClient(INetClient):
    def __init__(self, address, **kwargs):
        # type: (Tuple[str, int], **Any) -> None
        self.addr = address  # type: Tuple[str, int]
        self.timeout = kwargs.get("timeout", 0.05)  # type: float
        self.max_attempts = kwargs.get("max_attempts", 3)  # type: int

        self.socket = None  # type: Optional[socket.socket]
        self.is_alive = True  # type: bool
        self.handle_request_callback = self.__default_handler_request
        self.lock = threading.Lock()
        self.cmd_dict = OrderedDict()  # type: Dict[Tuple[str, int, int],NetCommand]
        self.__create_socket()

    def serve_forever(self):
        # type: () -> None
        self.is_alive = True
        self.socket.settimeout(self.timeout)
        while self.is_alive:
            self.__send_commands_from_queue()
            try:
                data, addr = self.socket.recvfrom(1024)
            except socket.timeout:
                continue
            except socket.error:
                continue

            message = self.__unpack_data(data)
            if message is None:
                continue
            if not self.__check_message(message, verbose=True):
                continue

            # если это подтверждение прошлой команды
            if message[MSG_FIELD_PACKET_TYPE] >= PacketType.response:
                self.process_answer_confirmation(addr, message)
                continue

            # поступила новая команда
            # noinspection PyBroadException
            try:
                cb_result = self.handle_request_callback(addr, message)
                if cb_result:  # отправить подтверждение команды
                    if cb_result.data:
                        message["result"] = cb_result.data
                    self.confirm_message(addr, message)
            except:
                logger.exception(
                    "Ошибка при вызове callback-обработчика новой команды от {}. Данные: {}".format(
                        addr, message
                    )
                )

    def process_answer_confirmation(self, addr, message):
        # type: (Tuple[str, int], dict) -> None
        """ обработать ответ-подтверждение """
        transmission_id = message[MSG_FIELD_TRANSMISSION_ID]
        ckey = self.__generate_confirm_key(*addr, transmission_id=transmission_id)
        cmd = self.cmd_dict.get(ckey)
        if cmd:
            # noinspection PyBroadException
            try:
                cmd.callback(addr, transmission_id, TransmissionStatus.success)
            except:
                logger.exception(
                    "Ошибка при вызове callback. Адрес: {}, данные: {}".format(
                        addr, message
                    )
                )
            else:
                with self.lock:
                    self.__remove_cmd(ckey)
        else:
            logger.warning(
                "Поступило неизвестно подтверждение от {}. Данные: {}".format(
                    addr, message
                )
            )

    def send_command(self, address, data, callback):
        # type: (Tuple[str, int], dict, Callable) -> None
        transmission_id = self.__generation_transmission_id()
        ckey = self.__generate_confirm_key(*address, transmission_id=transmission_id)
        cmd = NetCommand(
            address=address,
            packet_type=PacketType.request,
            transmission_id=transmission_id,
            data=data,
            callback=callback,
        )
        with self.lock:
            self.cmd_dict[ckey] = cmd

    def send_command_without_confirmation(self, addr, data):
        # type: (Tuple[str, int], dict) -> None
        try:
            data[MSG_FIELD_PACKET_TYPE] = PacketType.no_answer
            self.__send_command_udp(addr, data)
        except socket.gaierror:
            logger.exception("Не могу найти диспетчера")
        except socket.error:
            logger.exception(
                "Ошибка при работе с сокетом при отправке данных без подтверждения"
            )

    def add_handler_request(self, callback):
        # type: (Callable) -> None
        if callback is None:
            raise ValueError("Callback не может быть пустым")
        self.handle_request_callback = callback

    def __remove_cmd(self, ckey):
        del self.cmd_dict[ckey]

    def __generate_confirm_key(self, host, port, transmission_id):
        # type: (str, int, int) -> Tuple[str, int, int]
        try:
            _host = socket.gethostbyname(host)
        except socket.error:
            _host = host
        return (
            _host,
            port,
            transmission_id,
        )

    def __unpack_data(self, data):
        # type: (str) -> dict
        try:
            return json.loads(data, encoding="utf-8")
        except ValueError:
            logger.exception("Ошибка при декодировании сообщения")

    def __pack_data(self, data):
        # type: (dict) -> bytes
        return json.dumps(data).encode("utf-8")

    def __check_message(self, message, verbose=False):
        # type: (dict, bool) -> bool
        packet_type = message.get(MSG_FIELD_PACKET_TYPE)
        if (packet_type is None) or (packet_type not in PacketType.get_states()):
            if verbose:
                logger.error(
                    "packet_type принимает неизвестное значение. Данные: {}".format(
                        message
                    )
                )
            return False

        transmission_id = message.get(MSG_FIELD_TRANSMISSION_ID)
        if (packet_type != PacketType.no_answer) and (transmission_id is None):
            if verbose:
                logger.error(
                    "Должен быть задан transmission_id. Данные: {}".format(message)
                )
            return False
        return True

    def __send_commands_from_queue(self):
        # type: () -> None
        cmd_delete = []
        with self.lock:
            for ckey, cmd in self.cmd_dict.iteritems():
                if cmd.attempts > self.max_attempts:
                    cmd_delete.append((ckey, cmd))
                    continue
                else:
                    message = cmd.data.copy()
                    if cmd.packet_type:
                        message[MSG_FIELD_PACKET_TYPE] = cmd.packet_type
                    if cmd.transmission_id:
                        message[MSG_FIELD_TRANSMISSION_ID] = cmd.transmission_id
                    try:
                        self.__send_command_udp(cmd.address, message)
                    except socket.error:
                        logger.exception(
                            "Ошибка при работе с сокетом при отправке данных на адрес {}. Данные: {}".format(
                                cmd.address, message
                            )
                        )

                    cmd.attempts += 1
                    break
            # удаление команд по которым истекли попытки
            for ckey, cmd in cmd_delete:
                self.__remove_cmd(ckey)

        # вызов callback для команд по которым истекли попытки
        for ckey, cmd in cmd_delete:
            # noinspection PyBroadException
            try:
                cmd.callback(
                    cmd.address, cmd.transmission_id, TransmissionStatus.failure
                )
            except:
                logger.exception("Ошибка при вызове callback о неудачной доставке")

    def shutdown(self, immediate=False):
        # type: (bool) -> None
        self.is_alive = False
        if self.socket:
            self.socket.close()

    def __send_command_udp(self, addr, message):
        # type: (Tuple[str, int], dict) -> None
        self.socket.sendto(self.__pack_data(message), addr)
        logger.debug("отправлен пакет на адрес {}, данные {}".format(addr, message))

    def __create_socket(self):
        # type: () -> None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # todo: тут может произойти ошибка <class 'socket.error'>, error(98, 'Address already in use')
        self.socket.bind(self.addr)
        port = self.socket.getsockname()[1]
        logger.debug("Приложение слушает по порту {}".format(port))

    def __default_handler_request(self, address, message):
        # type: (Tuple[str, int], dict) -> ResponseConfirmation
        logger.warning("Обработчик запросов не зарегистрирован")

    @staticmethod
    def __generation_transmission_id():
        # type: () -> int
        return int(time.time() * 1000)

    def confirm_message(self, addr, message):
        # type: (Tuple[str, int], dict) -> None
        transmission_id = message.get(MSG_FIELD_TRANSMISSION_ID)
        if transmission_id:
            reply_message = message.copy()
            reply_message[MSG_FIELD_PACKET_TYPE] = PacketType.response
            self.__send_command_udp(addr, reply_message)
