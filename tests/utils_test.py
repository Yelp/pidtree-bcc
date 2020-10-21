import os
import sys

import psutil
import pytest

from pidtree_bcc import utils


@pytest.fixture
def this_proc():
    return psutil.Process(os.getpid())


@pytest.fixture
def this_pid():
    return os.getpid()


@pytest.fixture
def this_file():
    return os.path.abspath(__file__)


def test_crawl_process_tree(this_proc, this_pid):
    tree = utils.crawl_process_tree(this_proc)
    assert type(tree) is list
    assert len(tree) >= 1
    assert tree[0].pid == this_pid
    assert tree[-1].pid == 1  # should be init


def test_smart_open(this_file):
    assert utils.smart_open() == sys.stdout
    assert utils.smart_open('-') == sys.stdout
    assert utils.smart_open(this_file).name == this_file


def test_ip_to_int():
    assert utils.ip_to_int('127.0.0.1') == 16777343
    assert utils.ip_to_int('10.10.10.10') == 168430090
