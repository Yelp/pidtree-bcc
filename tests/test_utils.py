from pidtree_bcc import utils as u
import pytest
import os
import psutil
import sys

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
    tree = u.crawl_process_tree(this_proc)
    assert type(tree) is list
    assert len(tree) >= 1
    assert tree[0].pid == this_pid
    assert tree[-1].pid == 1 #should be init

def test_smart_open(this_file):
    with u.smart_open() as out:
        assert out == sys.stdout
    with u.smart_open('-') as out:
        assert out == sys.stdout
    with u.smart_open(this_file) as out:
        assert out.name == this_file
