import inspect
import socket
import traceback
from typing import Any

from pidtree_bcc.probes import BPFProbe
from pidtree_bcc.utils import crawl_process_tree
from pidtree_bcc.utils import int_to_ip
from pidtree_bcc.utils import ip_to_int


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
    }

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
