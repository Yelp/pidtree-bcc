import os
from pidtree_bcc.plugins import sourceipmap

def test_hosts_loader():
    hostfile = os.path.dirname(os.path.realpath(__file__)) + '/fixtures/hostfile'
    assert sourceipmap.hosts_loader(hostfile) == {'169.254.0.1': 'derp'}
