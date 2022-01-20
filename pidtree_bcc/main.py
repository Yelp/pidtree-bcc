import argparse
import logging
import os
import select
import signal
import sys
import time
from functools import partial
from multiprocessing import Process
from multiprocessing import SimpleQueue
from threading import Thread
from typing import Any
from typing import Callable
from typing import List
from typing import TextIO

from staticconf.config import ConfigurationWatcher

from pidtree_bcc import __version__
from pidtree_bcc.config import setup_config
from pidtree_bcc.probes import load_probes
from pidtree_bcc.utils import smart_open


EXIT_CODE = 0
HEALTH_CHECK_PERIOD_DEFAULT = 60  # seconds
HANDLED_SIGNALS = (signal.SIGINT, signal.SIGTERM)


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
        '-w', '--watch-config', action='store_true', default=False,
        help='Enable configuration file watch and hot-swapping for probe network filters',
    )
    parser.add_argument(
        '--health-check-period', type=int, default=HEALTH_CHECK_PERIOD_DEFAULT,
        help='Controls how often the watchdog thread performs health and configuration checks (in seconds)',
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


def termination_handler(probe_workers: List[Process], signum: int, frame: Any):
    """ Generic termination signal handler

    :param List[Process] probe_workers: list of probe processes
    :param int signum: signal integer code
    :param Any frame: signal stack frame
    """
    logging.warning('Caught termination signal, shutting off probes and exiting')
    for worker in probe_workers:
        worker.terminate()
    sys.exit(EXIT_CODE)


def deregister_signals(func: Callable):
    """ De-register signal handlers before invoking function

    :param Callable func: function to wrap
    :return: wrapped function
    """
    def helper(*args, **kwargs):
        for s in HANDLED_SIGNALS:
            signal.signal(s, signal.SIG_DFL)
        return func(*args, **kwargs)
    return helper


def health_and_config_watchdog(
    probe_workers: List[Process],
    output_fh: TextIO,
    config_watcher: ConfigurationWatcher = None,
    check_period: int = HEALTH_CHECK_PERIOD_DEFAULT,
):
    """ Check that probe processes are alive, output file is writable and monitor configuration changes

    :param List[Process] probe_workers: list of probe processes
    :param TextIO output_fh: Output file handle
    :param ConfigurationWatcher config_watcher: Watcher for monitoring configuration changes
    ;param int check_period: how often the checks are run (in seconds)
    """
    global EXIT_CODE
    fs_poller = select.poll()
    fs_poller.register(output_fh, select.POLLERR)
    while True:
        time.sleep(check_period)
        bad_fds = fs_poller.poll(0)
        if not all(worker.is_alive() for worker in probe_workers) or bad_fds:
            EXIT_CODE = 1
            msg = 'Broken output file' if bad_fds else 'Probe terminated unexpectedly'
            logging.error('{}, exiting'.format(msg))
            os.kill(os.getpid(), signal.SIGTERM)
            break
        if config_watcher:
            config_watcher.reload_if_changed()


def main(args: argparse.Namespace):
    global EXIT_CODE
    probe_workers = []
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )
    curried_handler = partial(termination_handler, probe_workers)
    for s in HANDLED_SIGNALS:
        signal.signal(s, curried_handler)
    config_watcher = setup_config(
        args.config,
        watch_config=args.watch_config,
        min_watch_interval=args.health_check_period,
    )
    out = smart_open(args.output_file, mode='w')
    output_queue = SimpleQueue()
    probes = load_probes(
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
        probe_workers.append(Process(target=deregister_signals(probe.start_polling)))
        probe_workers[-1].start()
    watchdog_thread = Thread(
        target=health_and_config_watchdog,
        args=(probe_workers, out, config_watcher, args.health_check_period),
        daemon=True,
    )
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
