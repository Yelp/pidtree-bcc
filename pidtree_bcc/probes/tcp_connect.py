import socket
import struct
import traceback
from datetime import datetime
from multiprocessing import SimpleQueue
from typing import Any

import psutil

from pidtree_bcc.probes import BPFProbe
from pidtree_bcc.utils import crawl_process_tree
from pidtree_bcc.utils import ip_to_int


class TCPConnectProbe(BPFProbe):

    def __init__(self, output_queue: SimpleQueue, probe_config: dict = {}):
        probe_config['ip_to_int'] = ip_to_int
        probe_config.setdefault('filters', [])
        probe_config.setdefault('includeports', [])
        super().__init__(output_queue, probe_config)

    def enrich_event(self, event: Any) -> dict:
        """ Parses TCP connect event and adds process tree data

        :param Any event: BPF event
        :return: event dictionary with process tree
        """
        proctree_enriched = []
        error = ''
        try:
            proc = psutil.Process(event.pid)
            proctree = crawl_process_tree(proc)
            proctree_enriched = [
                {
                    'pid': p.pid,
                    'cmdline': ' '.join(p.cmdline()),
                    'username': p.username(),
                } for p in proctree
            ]
        except Exception:
            error = traceback.format_exc()
        return {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'pid': event.pid,
            'proctree': proctree_enriched,
            # We're turning a little-endian insigned long ('<L')
            # representation of the destination address sent from the
            # kernel to a python `int` and then turning that into a string
            # representation of an IP address:
            'daddr': socket.inet_ntoa(struct.pack('<L', event.daddr)),
            'saddr': socket.inet_ntoa(struct.pack('<L', event.saddr)),
            'port': event.dport,
            'error': error,
        }
