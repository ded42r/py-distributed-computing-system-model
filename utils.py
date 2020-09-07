# coding: utf8
from __future__ import print_function

import json
from argparse import ArgumentParser
from threading import Event, Thread

try:
    from typing import Any, Callable
except ImportError:
    pass


def argparse_worker():
    # type: () -> tuple
    parser = ArgumentParser()
    parser.add_argument(
        "--settings", "-s", help=u"путь до файла с настройками", required=True
    )
    args, unknown = parser.parse_known_args()
    return args, unknown


def read_config(filename):
    # type: (str) -> dict
    with open(filename) as config_file:
        return json.load(config_file)


def call_repeatedly(interval, func, *args):
    # type: (float, Callable, *Any) -> Event
    stopped = Event()

    def loop():
        while not stopped.wait(interval):
            func(*args)

    Thread(target=loop).start()
    return stopped
