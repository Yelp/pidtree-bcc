import ctypes
import enum
from collections import namedtuple
from itertools import chain
from typing import Any
from typing import Iterable
from typing import List
from typing import Set
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

    @classmethod
    def from_network_definition(cls, netmask: str, ip: str):
        """ Normalize data according to prefix length to avoid equivalent keys
        with different representations.

        :param str netmask: network mask
        :param str ip: network ip
        """
        data = ip_to_int(ip)
        bitmask = ip_to_int(netmask)
        prefixlen = netmask_to_prefixlen(netmask)
        return cls(prefixlen=prefixlen, data=data & bitmask)


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


def load_filters_into_map(filters: List[dict], ebpf_map: Any, do_diff: bool = False):
    """ Loads network filters into a eBPF map. The map is expected to be a trie
    with prefix as they key and net_filter_val_t as elements, according to the
    type definitions in the `net_filter_trie_init` macro in `utils.j2`.

    NOTE: modifying values in the map is not atomic, hence it may cause a brief moment
    of inconsistency between probe output and configuration.

    :param List[dict] filters: list of IP-ports filters. Format:
                                {
                                    'network': '127.0.0.1',
                                    'network_mask': '255.0.0.0',
                                    'except_ports': [123, 456], # optional
                                    'include_ports': [789],     # optional
                                }
    :param Any ebpf_map: reference to eBPF table where filters should be loaded.
    :param bool do_diff: diff input with existing values, removing excess entries
    """
    leftovers = set(
        # The map returns keys using an auto-generated type.
        # Casting works, but we don't want to keep map references anyway to avoid
        # side effect, so we might as well unpack them explicitly
        (CFilterKey(prefixlen=k.prefixlen, data=k.data) for k in ebpf_map)
        if do_diff else [],
    )
    for entry in filters:
        map_key = CFilterKey.from_network_definition(
            netmask=entry['network_mask'],
            ip=entry['network'],
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
        leftovers.discard(map_key)
    for key in leftovers:
        del ebpf_map[key]


def load_port_filters_into_map(
    filters: List[Union[int, str]],
    mode: PortFilterMode,
    ebpf_map: Any,
    do_diff: bool = False,
):
    """ Loads global port filters into eBPF array map.
    The map must be a BPF array with allocated space to fit all the possible TCP/UDP ports (2^16).

    NOTE: modifying values in the map is not atomic, hence it may cause a brief moment
    of inconsistency between probe output and configuration. For this reason, hot-swapping
    the filtering mode is supported but not recommended.

    :param List[Union[int, str]] filters: list of ports or port ranges
    :param PortFilterMode mode: include or exclude
    :param Any ebpf_map: array in which filters are loaded
    :param bool do_diff: diff input with existing values, removing excess entries
    """
    if mode not in (PortFilterMode.include, PortFilterMode.exclude):
        raise ValueError('Invalid global port filtering mode: {}'.format(mode))
    current_state = set((k.value for k, v in ebpf_map.items() if v.value > 0 and k.value > 0) if do_diff else [])
    portset = set(
        chain.from_iterable(
            port_range_mapper(port_or_range)
            if isinstance(port_or_range, str) and '-' in port_or_range
            else (int(port_or_range),)
            for port_or_range in filters
        ),
    )
    leftovers = current_state - portset
    for port in portset:
        ebpf_map[ctypes.c_int(port)] = ctypes.c_uint8(1)
    for port in leftovers:
        ebpf_map[ctypes.c_int(port)] = ctypes.c_uint8(0)
    # 0-element of the map holds the filtering mode
    ebpf_map[ctypes.c_int(0)] = ctypes.c_uint8(mode.value)


def load_intset_into_map(intset: Set[int], ebpf_map: Any, do_diff: bool = False, delete: bool = False):
    """ Loads set of int values into eBPF map

    :param Set[int] intset: input values
    :param Any ebpf_map: array in which filters are loaded
    :param bool do_diff: diff input with existing values, removing excess entries
    :param bool delete: remove values rather than adding them
    """
    if delete:
        to_delete = intset
    else:
        current_state = set((k.value for k, _ in ebpf_map.items()) if do_diff else [])
        to_delete = current_state - intset
        for val in intset:
            ebpf_map[ctypes.c_int(val)] = ctypes.c_uint8(1)
    for val in to_delete:
        del ebpf_map[ctypes.c_int(val)]
