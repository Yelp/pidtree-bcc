import argparse
import os
import signal
import sys
from functools import partial
from multiprocessing import Process
from multiprocessing import SimpleQueue
from typing import Any
from typing import List
from typing import TextIO

import yaml

from pidtree_bcc import __version__
from pidtree_bcc.probes import BPFProbe
from pidtree_bcc.utils import find_subclass
from pidtree_bcc.utils import smart_open


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


def sigint_handler(
    probe_workers: List[Process],
    output_file: TextIO,
    signum: int,
    frame: Any,
):
    """ SIGINT handler

    :param List[Process] probe_workers: list of sub-processes to terminate
    :param TextIO output_file: event output file (to be closed)
    :param int signum: signal integer code
    :param Any frame: signal stack frame
    """
    sys.stderr.write('Caught SIGINT, exiting\n')
    for worker in probe_workers:
        worker.terminate()
    output_file.close()
    sys.exit(0)


def main(args: argparse.Namespace):
    probe_workers = []
    out = smart_open(args.output_file, mode='w')
    signal.signal(signal.SIGINT, partial(sigint_handler, probe_workers, out))
    config = parse_config(args.config)
    output_queue = SimpleQueue()
    probes = {
        probe_name: find_subclass(
            'pidtree_bcc.probes.{}'.format(probe_name),
            BPFProbe,
        )(output_queue, probe_config)
        for probe_name, probe_config in config.items()
        if not probe_name.startswith('_')
    }
    if args.print_and_quit:
        for probe_name, probe in probes.items():
            print('----- {} -----'.format(probe_name))
            print(probe.expanded_bpf_text)
            print('\n')
        sys.exit(0)
    for probe in probes.values():
        probe_workers.append(Process(target=probe.start_polling))
        probe_workers[-1].start()
    while True:
        print(output_queue.get(), file=out)
        out.flush()
    out.close()
    sys.exit(0)


if __name__ == '__main__':
    main(parse_args())
