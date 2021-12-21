from unittest.mock import call
from unittest.mock import MagicMock

import pytest

from pidtree_bcc.filtering import CFilterKey
from pidtree_bcc.filtering import CFilterValue
from pidtree_bcc.filtering import CPortRange
from pidtree_bcc.filtering import load_filters_into_map
from pidtree_bcc.filtering import load_port_filters_into_map
from pidtree_bcc.filtering import NetFilter
from pidtree_bcc.filtering import port_range_mapper
from pidtree_bcc.filtering import PortFilterMode
from pidtree_bcc.utils import ip_to_int


@pytest.fixture
def net_filtering():
    return NetFilter(
        [
            {
                'network': '127.0.0.1',
                'network_mask': '255.0.0.0',
            },
            {
                'network': '10.0.0.0',
                'network_mask': '255.0.0.0',
                'except_ports': [123],
            },
            {
                'network': '192.168.0.0',
                'network_mask': '255.255.0.0',
                'include_ports': [123],
            },
        ],
    )


def test_filter_ip_int(net_filtering):
    assert net_filtering.is_filtered(ip_to_int('127.1.33.7'), 80)
    assert not net_filtering.is_filtered(ip_to_int('1.2.3.4'), 80)


def test_filter_ip_str(net_filtering):
    assert net_filtering.is_filtered('127.1.33.7', 80)
    assert not net_filtering.is_filtered('1.2.3.4', 80)


def test_filter_ip_except_port(net_filtering):
    assert net_filtering.is_filtered('10.1.2.3', 80)
    assert not net_filtering.is_filtered('10.1.2.3', 123)


def test_filter_ip_include_port(net_filtering):
    assert net_filtering.is_filtered('192.168.0.1', 123)
    assert not net_filtering.is_filtered('192.168.0.1', 80)


def test_load_filters_into_map():
    mock_filters = [
        {
            'network': '127.0.0.1',
            'network_mask': '255.0.0.0',
        },
        {
            'network': '10.0.0.1',
            'network_mask': '255.0.0.0',
            'except_ports': [123, 456],
        },
        {
            'network': '192.168.0.1',
            'network_mask': '255.255.0.0',
            'include_ports': ['100-200'],
        },
    ]
    res_map = MagicMock()
    load_filters_into_map(mock_filters, res_map)
    res_map.__setitem__.assert_has_calls([
        call(
            CFilterKey(prefixlen=8, data=16777343),
            CFilterValue(mode=0, range_size=0),
        ),
        call(
            CFilterKey(prefixlen=8, data=16777226),
            CFilterValue(
                mode=1,
                range_size=2,
                ranges=CFilterValue.range_array_t(CPortRange(123, 123), CPortRange(456, 456)),
            ),
        ),
        call(
            CFilterKey(prefixlen=16, data=16820416),
            CFilterValue(mode=2, range_size=1, ranges=CFilterValue.range_array_t(CPortRange(100, 200))),
        ),
    ])


@pytest.mark.parametrize(
    'filter_input,mode,expected',
    [
        ((22, 80, 443), PortFilterMode.include, {0: 2, 22: 1, 80: 1, 443: 1}),
        (('10-20',), PortFilterMode.exclude, {0: 1, **{i: 1 for i in range(10, 21)}}),
        ((1, '2-9', 10), PortFilterMode.exclude, {i: 1 for i in range(11)}),
    ],
)
def test_load_port_filters_into_map(filter_input, mode, expected):
    res_map = MagicMock()
    load_port_filters_into_map(filter_input, mode, res_map)
    assert expected == {
        call_args[0][0].value: call_args[0][1].value
        for call_args in res_map.__setitem__.call_args_list
    }


def test_port_range_mapper():
    assert list(port_range_mapper('22-80')) == list(range(22, 81))
    assert list(port_range_mapper('0-10')) == list(range(1, 11))
    assert list(port_range_mapper('100-100000000')) == list(range(100, 65535))
