import pytest
import os
from pidtree_bcc.plugins import sourceipmap

def test_hosts_loader():
    hostfile = os.path.dirname(os.path.realpath(__file__)) + '/fixtures/hostfile'
    assert sourceipmap.hosts_loader(hostfile) == {'169.254.0.1': 'derp'}

def test_multiple_hosts_loader():
    hostfile1 = os.path.dirname(os.path.realpath(__file__)) + '/fixtures/hostfile'
    hostfile2 = os.path.dirname(os.path.realpath(__file__)) + '/fixtures/hostfile2'
    plugin = sourceipmap.Sourceipmap({"hostfiles": [hostfile1, hostfile2]})
    assert plugin.process({"saddr": "169.254.0.2"})["source_host"] == 'herp'
    assert plugin.process({"saddr": "169.254.0.1"})["source_host"] == 'derp'

def test_host_file_doesnt_exist():
    hostfile = "/bananas_in_spaaaaaaaaaaace"
    with pytest.raises(RuntimeError) as e:
        plugin = sourceipmap.Sourceipmap({"hostfiles": [hostfile]})
    assert "File `/bananas_in_spaaaaaaaaaaace` passed as a 'hostfiles' entry to the sourceipmap plugin does not exist" in str(e)
