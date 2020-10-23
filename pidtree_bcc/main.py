import argparse
import logging
import os
import signal
import sys
import time
from multiprocessing import Process
from multiprocessing import SimpleQueue
from threading import Thread
from typing import Any
from typing import List

import yaml

from pidtree_bcc import __version__
from pidtree_bcc.probes import BPFProbe
from pidtree_bcc.utils import find_subclass
from pidtree_bcc.utils import smart_open


EXIT_CODE = 0
PROBE_CHECK_PERIOD = 60  # seconds


def parse_args() -> argparse.Namespace:
    """ Parses command line arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config', type=str,
        help='yaml file containing subnet safelist information',
    )
    parser.add_argument(
        '-p', '--print-and-quit', action='store_true', default=False,
        help="don't run, just print the eBPF program to be compiled and quit",
    )
    parser.add_argument(
        '-f', '--output_file', type=str, default='-',
        help='File to output to (default is STDOUT, denoted by -)',
    )
    parser.add_argument(
        '-v', '--version', action='version',
        version='pidtree-bcc %s' % __version__,
    )
    args = parser.parse_args()
    if args.config is not None and not os.path.exists(args.config):
        sys.stderr.write('--config file does not exist\n')
    return args


def parse_config(config_file: str) -> dict:
    """ Parses yaml config file (if indicated)

    :param str config_file: config file path
    :return: configuration dictionary
    """
    if config_file is None:
        return {}
    with open(config_file) as f:
        return yaml.safe_load(f)


def termination_handler(signum: int, frame: Any):
    """ Generic termination signal handler

    :param int signum: signal integer code
    :param Any frame: signal stack frame
    """
    logging.warning('Caught termination signal, exiting')
    sys.exit(EXIT_CODE)


def probe_watchdog(probe_workers: List[Process]):
    """ Check that probe processes are alive

    :param List[Process] probe_workers: list of probe processes
    """
    global EXIT_CODE
    while True:
        time.sleep(PROBE_CHECK_PERIOD)
        if not all(worker.is_alive() for worker in probe_workers):
            EXIT_CODE = 1
            logging.error('Probe terminated unexpectedly, quitting')
            for worker in probe_workers:
                worker.terminate()
            os.kill(os.getpid(), signal.SIGINT)
            break


def main(args: argparse.Namespace):
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    signal.signal(signal.SIGINT, termination_handler)
    signal.signal(signal.SIGTERM, termination_handler)
    config = parse_config(args.config)
    out = smart_open(args.output_file, mode='w')
    output_queue = SimpleQueue()
    probes = {
        probe_name: find_subclass(
            'pidtree_bcc.probes.{}'.format(probe_name),
            BPFProbe,
        )(output_queue, probe_config)
        for probe_name, probe_config in config.items()
        if not probe_name.startswith('_')
    }
    logging.info('Loaded probes: {}'.format(', '.join(probes)))
    if args.print_and_quit:
        for probe_name, probe in probes.items():
            print('----- {} -----'.format(probe_name))
            print(probe.expanded_bpf_text)
            print('\n')
        sys.exit(0)
    probe_workers = []
    for probe in probes.values():
        probe_workers.append(Process(target=probe.start_polling))
        probe_workers[-1].start()
    watchdog_thread = Thread(target=probe_watchdog, args=(probe_workers,), daemon=True)
    watchdog_thread.start()
    try:
        while True:
            print(output_queue.get(), file=out)
            out.flush()
    except Exception as e:
        # Terminate everything if something goes wrong
        logging.error('Encountered unexpected error: {}'.format(e))
        for worker in probe_workers:
            worker.terminate()
        sys.exit(1)
    finally:
        out.close()


if __name__ == '__main__':
    main(parse_args())
