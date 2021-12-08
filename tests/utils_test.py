import os
import sys
from unittest.mock import call
from unittest.mock import patch

import pytest

from pidtree_bcc import utils


def test_crawl_process_tree():
    this_pid = os.getpid()
    tree = utils.crawl_process_tree(this_pid)
    assert len(tree) >= 1
    assert tree[0]['pid'] == this_pid
    assert tree[-1]['pid'] == 1  # should be init


def test_smart_open():
    this_file = os.path.abspath(__file__)
    assert utils.smart_open() == sys.stdout
    assert utils.smart_open('-') == sys.stdout
    assert utils.smart_open(this_file).name == this_file


def test_ip_to_int():
    assert utils.ip_to_int('127.0.0.1') == 16777343
    assert utils.ip_to_int('10.10.10.10') == 168430090


def test_int_to_ip():
    assert utils.int_to_ip(16777343) == '127.0.0.1'
    assert utils.int_to_ip(168430090) == '10.10.10.10'


@patch('pidtree_bcc.utils.os')
def test_get_network_namespace(mock_os):
    mock_os.readlink.return_value = 'net:[456]'
    assert utils.get_network_namespace() == 456
    assert utils.get_network_namespace(123) == 456
    mock_os.readlink.assert_has_calls([
        call('/proc/self/ns/net'),
        call('/proc/123/ns/net'),
    ])
    mock_os.readlink.side_effect = Exception
    assert utils.get_network_namespace() is None


def test_netmask_to_prefixlen():
    assert utils.netmask_to_prefixlen('0.0.0.0') == 0
    assert utils.netmask_to_prefixlen('255.255.255.255') == 32
    assert utils.netmask_to_prefixlen('255.0.0.0') == 8
    with pytest.raises(ValueError):
        utils.netmask_to_prefixlen('1.1.1.1')
