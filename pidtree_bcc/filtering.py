from collections import namedtuple
from typing import List
from typing import Union

from pidtree_bcc.utils import ip_to_int


IpPortFilter = namedtuple('IpPortFilter', ('subnet', 'netmask', 'except_ports', 'include_ports'))


class NetFilter:

    def __init__(self, filters: List[dict]):
        """ Constructor

        :param List[dict] filters: list of IP-ports filters. Format:
                                   {
                                       'network': '127.0.0.1',
                                       'network_mask': '255.0.0.0',
                                       'except_ports': [123, 456], # optional
                                       'include_ports': [789],     # optional
                                   }
        """
        self.filters = [
            IpPortFilter(
                ip_to_int(f['network']) & ip_to_int(f['network_mask']),
                ip_to_int(f['network_mask']),
                set(map(int, f.get('except_ports', []))),
                set(map(int, f.get('include_ports', []))),
            ) for f in filters
        ]

    def is_filtered(self, ip_address: Union[int, str], port: int) -> bool:
        """ Check if IP-port combination is filtered

        :param Union[int, str] ip_address: IP address in integer or string form
        :param int port: port in host byte order representation (i.e. pre htons / after ntohs)
        :return: True if filtered
        """
        if isinstance(ip_address, str):
            ip_address = ip_to_int(ip_address)
        for f in self.filters:
            if (
                f.netmask & ip_address == f.subnet
                and port not in f.except_ports
                and (not f.include_ports or port in f.include_ports)
            ):
                return True
        return False
