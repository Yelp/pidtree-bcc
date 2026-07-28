from multiprocessing import SimpleQueue
from unittest.mock import patch

import pytest

from pidtree_bcc.config import reset_config_state
from pidtree_bcc.probes.tcp_connect import TCPConnectProbe


@pytest.fixture(autouse=True)
def clean_staticconf():
    yield
    reset_config_state()


@patch('pidtree_bcc.probes.socket.gethostbyname_ex')
def test_resolve_domains(mock_gethostbyname_ex):
    def side_effect(domain):
        if domain == 'a.example.com':
            return ('a.example.com', [], ['1.2.3.4', '5.6.7.8'])
        if domain == 'b.example.com':
            return ('b.example.com', [], ['9.9.9.9'])
        raise OSError('DNS failed')

    mock_gethostbyname_ex.side_effect = side_effect
    probe = TCPConnectProbe(SimpleQueue(), {'filters': [], 'dns_filters': []})
    result = probe.resolve_domains(['a.example.com', 'b.example.com', 'bad.example.com'])

    networks = {r['network'] for r in result}
    assert networks == {'1.2.3.4', '5.6.7.8', '9.9.9.9'}
    assert all(r['network_mask'] == '255.255.255.255' for r in result)
