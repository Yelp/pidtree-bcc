import ctypes
import enum
from collections import namedtuple
from typing import Any
from typing import Iterable
from typing import List
from typing import Union

from pidtree_bcc.ctypes_helper import ComparableCtStructure
from pidtree_bcc.ctypes_helper import create_comparable_array_type
from pidtree_bcc.utils import ip_to_int
from pidtree_bcc.utils import netmask_to_prefixlen


NET_FILTER_MAX_PORT_RANGES = 8
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


class CPortRange(ComparableCtStructure):
    _fields_ = [
        ('lower', ctypes.c_uint16),
        ('upper', ctypes.c_uint16),
    ]

    @classmethod
    def from_conf_value(cls, val: Union[int, str]) -> 'CPortRange':
        lower, upper = (
            map(int, val.split('-'))
            if isinstance(val, str) and '-' in val
            else (val, val)
        )
        return cls(lower=lower, upper=upper)


class CFilterKey(ComparableCtStructure):
    _fields_ = [
        ('prefixlen', ctypes.c_uint32),
        ('data', ctypes.c_uint32),
    ]


class CFilterValue(ComparableCtStructure):
    range_array_t = create_comparable_array_type(NET_FILTER_MAX_PORT_RANGES, CPortRange)
    _fields_ = [
        ('mode', ctypes.c_int),  # this is actually an enum, which are ints in C
        ('range_size', ctypes.c_uint8),
        ('ranges', range_array_t),
    ]


class PortFilterMode(enum.IntEnum):
    """ Reflects values used for `net_filter_mode` in utils.j2 """
    all = 0
    exclude = 1
    include = 2


def port_range_mapper(port_range: str) -> Iterable[int]:
    from_p, to_p = map(int, port_range.split('-'))
    return range(max(1, from_p), min(65535, to_p + 1))


def load_filters_into_map(filters: List[dict], ebpf_map: Any):
    """ Loads network filters into a eBPF map. The map is expected to be a trie
    with prefix as they key and net_filter_val_t as elements, according to the
    type definitions in the `net_filter_trie_init` macro in `utils.j2`.

    :param List[dict] filters: list of IP-ports filters. Format:
                                {
                                    'network': '127.0.0.1',
                                    'network_mask': '255.0.0.0',
                                    'except_ports': [123, 456], # optional
                                    'include_ports': [789],     # optional
                                }
    :param Any ebpf_map: reference to eBPF table where filters should be loaded.
    """
    for entry in filters:
        map_key = CFilterKey(
            prefixlen=netmask_to_prefixlen(entry['network_mask']),
            data=ip_to_int(entry['network']),
        )
        if entry.get('except_ports'):
            mode = PortFilterMode.exclude
            port_ranges = list(map(CPortRange.from_conf_value, entry['except_ports']))
        elif entry.get('include_ports'):
            mode = PortFilterMode.include
            port_ranges = list(map(CPortRange.from_conf_value, entry['include_ports']))
        else:
            mode = PortFilterMode.all
            port_ranges = []
        ebpf_map[map_key] = CFilterValue(
            mode=mode.value,
            range_size=len(port_ranges),
            ranges=CFilterValue.range_array_t(*port_ranges),
        )


def load_port_filters_into_map(filters: List[Union[int, str]], mode: PortFilterMode, ebpf_map: Any):
    """ Loads global port filters into eBPF array map.
    The map must be a BPF array with allocated space to fit all
    the possible TCP/UDP ports (2^16).

    :param List[Union[int, str]] filters: list of ports or port ranges
    :param PortFilterMode mode: include or exclude
    :param Any ebpf_map: array in which filters are loaded
    """
    if mode not in (PortFilterMode.include, PortFilterMode.exclude):
        raise ValueError('Invalid global port filtering mode: {}'.format(mode))
    # 0-element of the map holds the filtering mode
    ebpf_map[ctypes.c_int(0)] = ctypes.c_uint8(mode.value)
    for port_or_range in filters:
        prange = (
            port_range_mapper(port_or_range)
            if isinstance(port_or_range, str) and '-' in port_or_range
            else (int(port_or_range),)
        )
        for port in prange:
            ebpf_map[ctypes.c_int(port)] = ctypes.c_uint8(1)
