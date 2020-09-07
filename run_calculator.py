# coding: utf8
from __future__ import print_function

import logging
from functools import partial

from calculator import Calculator, DisabilityRunner
from net_protocol import NetClient
from utils import argparse_worker, read_config

if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    args, _ = argparse_worker()
    config = read_config(args.settings)

    dispatcher_addr = (config["dispatcher"]["host"], config["dispatcher"]["port"])
    calc_fabric = partial(Calculator, NetClient, dispatcher_addr, **config)
    DisabilityRunner(calc_fabric, **config["disability"]).serve_forever()
