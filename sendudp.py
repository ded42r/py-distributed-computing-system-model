# coding: utf8
from __future__ import print_function

import json
import logging
import socket
from argparse import ArgumentParser


def send(data, host, port):
    conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    conn.sendto(json.dumps(data).encode("utf-8"), (host, port))
    conn.close()


def main(data, host, port, count):
    logger.info("Будут отправлены данные {} на адрес {}:{}".format(data, host, port))
    for i in range(count):
        if data:
            try:
                send(data, host, port)
            except ValueError:
                logger.exception("Ошибка при преобразовании json {}".format(data))
        else:
            send(str(i), host, port)
    logger.info("данные отправлены")


if __name__ == "__main__":
    # утилита для отправки пакетов (для тестов)
    logging.basicConfig(format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    parser = ArgumentParser()
    parser.add_argument("--host", "-a", required=True)
    parser.add_argument("--port", "-p", required=True, type=int)
    parser.add_argument("--data", "-d", default=None)
    parser.add_argument("--count", "-c", type=int, default=1)
    parser.add_argument("--filename", "-f", default=None)
    args, unknown = parser.parse_known_args()
    if args.filename:
        with open(args.filename, "r") as fp:
            data = json.load(fp)
            logger.info("Загружен файл с данными: {}".format(data))
    else:
        data = args.data
    main(data, args.host, args.port, args.count)
