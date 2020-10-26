import os
import sys

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
