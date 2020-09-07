# coding: utf8
from __future__ import print_function

import logging

from dispatcher import Dispatcher
from net_protocol import NetClient
from utils import argparse_worker, read_config

if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    args, _ = argparse_worker()
    config = read_config(args.settings)

    client_address = config.pop("client_address")
    local_address = (
        client_address.get("host", ""),
        client_address["port"],
    )
    Dispatcher(NetClient, local_address, **config).start()
