# coding: utf8
from __future__ import print_function

import logging

from client import Client
from net_protocol import NetClient
from utils import argparse_worker, read_config

if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    args, _ = argparse_worker()
    config = read_config(args.settings)

    dispatcher_addr = (
        config["dispatcher"]["host"],
        config["dispatcher"]["port"],
    )
    c = Client(NetClient, dispatcher_addr, **config)
    c.start()
    c.print_stat()
