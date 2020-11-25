import inspect
import socket
import time
import traceback
from collections import namedtuple
from itertools import chain
from multiprocessing import SimpleQueue
from typing import Any

import psutil

from pidtree_bcc.probes import BPFProbe
from pidtree_bcc.utils import crawl_process_tree
from pidtree_bcc.utils import int_to_ip
from pidtree_bcc.utils import ip_to_int
from pidtree_bcc.utils import never_crash


NetListenWrapper = namedtuple('NetListenWrapper', ('pid', 'laddr', 'port', 'protocol'))


class NetListenProbe(BPFProbe):

    PROTO_MAP = {
        value: name.split('_')[1].lower()
        for name, value in inspect.getmembers(socket)
        if name.startswith('IPPROTO_')
    }
    CONFIG_DEFAULTS = {
        'ip_to_int': ip_to_int,
        'protocols': ['tcp'],
        'excludeaddress': [],
        'excludeports': [],
        'includeports': [],
        'snapshot_periodicity': False,
    }
    SUPPORTED_PROTOCOLS = ('udp', 'tcp')

    def __init__(self, output_queue: SimpleQueue, config: dict = {}):
        super().__init__(output_queue, config)

        def port_range_mapper(port_range: str):
            from_p, to_p = map(int, port_range.split('-'))
            return max(0, from_p), min(65535, to_p + 1)

        config = {**self.CONFIG_DEFAULTS, **config}
        self.log_tcp = 'tcp' in config['protocols']
        self.log_udp = 'udp' in config['protocols']
        self.excludeaddrs = set(config['excludeaddress'])
        if config['includeports']:
            includeports = set(map(int, config['includeports']))
            self.port_filter = lambda port: port in includeports
        else:
            excludeports = set(
                chain.from_iterable(
                    range(*port_range_mapper(p)) if '-' in p else [int(p)]
                    for p in map(str, config['excludeports'])
                ),
            )
            self.port_filter = lambda port: port not in excludeports
        if config['snapshot_periodicity']:
            self.SIDECARS.append((
                self._snapshot_worker,
                (config['snapshot_periodicity'],),
            ))

    def validate_config(self, config: dict):
        """ Checks if config values are valid """
        for proto in config.get('protocols', []):
            if proto not in self.SUPPORTED_PROTOCOLS:
                raise RuntimeError(
                    '{} is not among supported protocols {}'
                    .format(proto, self.SUPPORTED_PROTOCOLS),
                )

    def enrich_event(self, event: Any) -> dict:
        """ Parses network "listen event" and adds process tree data

        :param Any event: BPF event
        :return: event dictionary with process tree
        """
        error = ''
        try:
            proctree = crawl_process_tree(event.pid)
        except Exception:
            error = traceback.format_exc()
            proctree = []
        return {
            'pid': event.pid,
            'port': event.port,
            'proctree': proctree,
            'laddr': int_to_ip(event.laddr),
            'protocol': self.PROTO_MAP.get(event.protocol, 'unknown'),
            'error': error,
        }

    @never_crash
    def _snapshot_worker(self, periodicity: int):
        """ Handler function for snapshot thread.

        :param int periodicity: how many seconds to wait between snapshots
        """
        time.sleep(300)  # sleep 5 minutes to avoid "noisy" restarts
        while True:
            socket_stats = psutil.net_connections('inet4')
            for conn in socket_stats:
                if not conn.pid:
                    # filter out entries without associated PID
                    continue
                if self.log_tcp and conn.status == 'LISTEN':
                    protocol = socket.IPPROTO_TCP
                elif self.log_udp and conn.status == 'NONE' and conn.type == socket.SOCK_DGRAM:
                    protocol = socket.IPPROTO_UDP
                else:
                    protocol = None
                if (
                    protocol
                    and conn.laddr.ip not in self.excludeaddrs
                    and self.port_filter(conn.laddr.port)
                ):
                    event = NetListenWrapper(
                        conn.pid,
                        ip_to_int(conn.laddr.ip),
                        conn.laddr.port,
                        protocol,
                    )
                    self._process_events(None, event, None, False)
            time.sleep(periodicity)
