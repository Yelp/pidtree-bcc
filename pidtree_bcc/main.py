import argparse
import logging
import os
import signal
import sys
import time
from functools import partial
from multiprocessing import Process
from multiprocessing import SimpleQueue
from threading import Thread
from typing import Any
from typing import List

import yaml

from pidtree_bcc import __version__
from pidtree_bcc.probes import load_probes
from pidtree_bcc.utils import smart_open


EXIT_CODE = 0
PROBE_CHECK_PERIOD = 60  # seconds


def parse_args() -> argparse.Namespace:
    """ Parses command line arguments """
    program_name = 'pidtree-bcc'
    parser = argparse.ArgumentParser(
        program_name,
        description='eBPF tool for logging process ancestry of network events',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '-c', '--config', type=str,
        help='YAML file containing probe configurations',
    )
    parser.add_argument(
        '-p', '--print-and-quit', action='store_true', default=False,
        help='Just print the eBPF program(s) to be compiled and quit',
    )
    parser.add_argument(
        '-f', '--output_file', type=str, default='-',
        help='File to output to (default is STDOUT, denoted by -)',
    )
    parser.add_argument(
        '--lost-event-telemetry', type=int, default=-1, metavar='NEVENTS',
        help=(
            'If set and greater than 0, output telemetry every NEVENTS about the number '
            'of events dropped due to the kernel -> userland communication channel filling up'
        ),
    )
    parser.add_argument(
        '--extra-probe-path', type=str,
        help='Extra dot-notation package path where to look for probes to load',
    )
    parser.add_argument(
        '--extra-plugin-path', type=str,
        help='Extra dot-notation package path where to look for plugins to load',
    )
    parser.add_argument(
        '-v', '--version', action='version',
        version='{} {}'.format(program_name, __version__),
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


def termination_handler(probe_workers: List[Process], main_pid: int, signum: int, frame: Any):
    """ Generic termination signal handler

    :param List[Process] probe_workers: list of probe processes
    :param int main_pid: PID of the main process
    :param int signum: signal integer code
    :param Any frame: signal stack frame
    """
    logging.warning('Caught termination signal, exiting')
    if os.getpid() == main_pid:
        logging.info('Shutting off all probes')
        for worker in probe_workers:
            worker.terminate()
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
            logging.error('Probe terminated unexpectedly, exiting')
            os.kill(os.getpid(), signal.SIGTERM)
            break


def main(args: argparse.Namespace):
    global EXIT_CODE
    probe_workers = []
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    curried_handler = partial(termination_handler, probe_workers, os.getpid())
    signal.signal(signal.SIGINT, curried_handler)
    signal.signal(signal.SIGTERM, curried_handler)
    config = parse_config(args.config)
    out = smart_open(args.output_file, mode='w')
    output_queue = SimpleQueue()
    probes = load_probes(
        config,
        output_queue,
        args.extra_probe_path,
        args.extra_plugin_path,
        args.lost_event_telemetry,
    )
    logging.info('Loaded probes: {}'.format(', '.join(probes)))
    if args.print_and_quit:
        for probe_name, probe in probes.items():
            print('----- {} -----'.format(probe_name))
            print(probe.expanded_bpf_text)
            print('\n')
        sys.exit(0)
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
        EXIT_CODE = 1
        logging.error('Encountered unexpected error: {}'.format(e))
        for worker in probe_workers:
            worker.terminate()
    sys.exit(EXIT_CODE)


if __name__ == '__main__':
    main(parse_args())
