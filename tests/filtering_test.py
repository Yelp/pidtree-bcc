import pytest

from pidtree_bcc.filtering import NetFilter
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
