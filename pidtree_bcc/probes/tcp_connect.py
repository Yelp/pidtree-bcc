import traceback
from typing import Any

from pidtree_bcc.probes import BPFProbe
from pidtree_bcc.utils import crawl_process_tree
from pidtree_bcc.utils import int_to_ip
from pidtree_bcc.utils import ip_to_int


class TCPConnectProbe(BPFProbe):

    CONFIG_DEFAULTS = {
        'ip_to_int': ip_to_int,
        'filters': [],
        'includeports': [],
        'excludeports': [],
    }

    def enrich_event(self, event: Any) -> dict:
        """ Parses TCP connect event and adds process tree data

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
            'proctree': proctree,
            # We're turning a little-endian insigned long ('<L')
            # representation of the destination address sent from the
            # kernel to a python `int` and then turning that into a string
            # representation of an IP address:
            'daddr': int_to_ip(event.daddr),
            'saddr': int_to_ip(event.saddr),
            'port': event.dport,
            'error': error,
        }
