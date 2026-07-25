from multiprocessing import SimpleQueue
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from pidtree_bcc.config import reset_config_state
from pidtree_bcc.probes.tcp_connect import TCPConnectProbe


def _make_getaddrinfo_response(*ips):
    return [(2, 1, 6, '', (ip, 0)) for ip in ips]


@pytest.fixture(autouse=True)
def clean_staticconf():
    yield
    reset_config_state()


class TestResolveDomainToIps:

    @patch('pidtree_bcc.probes.socket.getaddrinfo')
    def test_single_ip(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = _make_getaddrinfo_response('1.2.3.4')
        probe = TCPConnectProbe(SimpleQueue(), {'filters': [], 'dns_filters': []})
        result = probe.resolve_domain_to_ips('example.com')
        assert result == ['1.2.3.4']
        mock_getaddrinfo.assert_called_once_with('example.com', None, 2)

    @patch('pidtree_bcc.probes.socket.getaddrinfo')
    def test_multiple_ips(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = _make_getaddrinfo_response('1.2.3.4', '5.6.7.8')
        probe = TCPConnectProbe(SimpleQueue(), {'filters': [], 'dns_filters': []})
        result = probe.resolve_domain_to_ips('example.com')
        assert set(result) == {'1.2.3.4', '5.6.7.8'}

    @patch('pidtree_bcc.probes.socket.getaddrinfo')
    def test_deduplicates(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = _make_getaddrinfo_response('1.2.3.4', '1.2.3.4')
        probe = TCPConnectProbe(SimpleQueue(), {'filters': [], 'dns_filters': []})
        result = probe.resolve_domain_to_ips('example.com')
        assert result == ['1.2.3.4']

    @patch('pidtree_bcc.probes.socket.getaddrinfo')
    def test_resolution_failure(self, mock_getaddrinfo):
        mock_getaddrinfo.side_effect = OSError('DNS failed')
        probe = TCPConnectProbe(SimpleQueue(), {'filters': [], 'dns_filters': []})
        result = probe.resolve_domain_to_ips('bad.example.com')
        assert result == []


class TestResolveDomains:

    @patch('pidtree_bcc.probes.socket.getaddrinfo')
    def test_single_domain_single_ip(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = _make_getaddrinfo_response('1.2.3.4')
        probe = TCPConnectProbe(SimpleQueue(), {'filters': [], 'dns_filters': []})
        result = probe.resolve_domains(['example.com'])
        assert result == [
            {'description': 'Resolved example.com', 'network': '1.2.3.4', 'network_mask': '255.255.255.255'},
        ]

    @patch('pidtree_bcc.probes.socket.getaddrinfo')
    def test_single_domain_multiple_ips(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = _make_getaddrinfo_response('1.2.3.4', '5.6.7.8')
        probe = TCPConnectProbe(SimpleQueue(), {'filters': [], 'dns_filters': []})
        result = probe.resolve_domains(['example.com'])
        networks = {r['network'] for r in result}
        assert networks == {'1.2.3.4', '5.6.7.8'}
        assert all(r['network_mask'] == '255.255.255.255' for r in result)

    @patch('pidtree_bcc.probes.socket.getaddrinfo')
    def test_multiple_domains(self, mock_getaddrinfo):
        def side_effect(domain, *args):
            if domain == 'a.com':
                return _make_getaddrinfo_response('1.1.1.1')
            return _make_getaddrinfo_response('2.2.2.2')
        mock_getaddrinfo.side_effect = side_effect
        probe = TCPConnectProbe(SimpleQueue(), {'filters': [], 'dns_filters': []})
        result = probe.resolve_domains(['a.com', 'b.com'])
        networks = {r['network'] for r in result}
        assert networks == {'1.1.1.1', '2.2.2.2'}

    @patch('pidtree_bcc.probes.socket.getaddrinfo')
    def test_partial_failure(self, mock_getaddrinfo):
        def side_effect(domain, *args):
            if domain == 'good.com':
                return _make_getaddrinfo_response('1.2.3.4')
            raise OSError('DNS failed')
        mock_getaddrinfo.side_effect = side_effect
        probe = TCPConnectProbe(SimpleQueue(), {'filters': [], 'dns_filters': []})
        result = probe.resolve_domains(['good.com', 'bad.com'])
        assert result == [
            {'description': 'Resolved good.com', 'network': '1.2.3.4', 'network_mask': '255.255.255.255'},
        ]


class TestReloadFiltersWithDns:

    @patch('pidtree_bcc.probes.socket.getaddrinfo')
    def test_merges_static_and_dns_filters(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = _make_getaddrinfo_response('9.9.9.9')
        probe = TCPConnectProbe(
            SimpleQueue(),
            {
                'filters': [{'network': '10.0.0.0', 'network_mask': '255.0.0.0'}],
                'dns_filters': [{'domain': 'example.com'}],
            },
        )
        mock_bpf = MagicMock()
        probe.bpf = mock_bpf
        probe.reload_filters(is_init=True)
        mock_bpf.__getitem__.assert_any_call(probe.NET_FILTER_MAP_NAME)

    @patch('pidtree_bcc.probes.socket.getaddrinfo')
    def test_dns_filters_empty(self, mock_getaddrinfo):
        probe = TCPConnectProbe(
            SimpleQueue(),
            {
                'filters': [{'network': '10.0.0.0', 'network_mask': '255.0.0.0'}],
                'dns_filters': [],
            },
        )
        mock_bpf = MagicMock()
        probe.bpf = mock_bpf
        probe.reload_filters(is_init=True)
        mock_getaddrinfo.assert_not_called()
        mock_bpf.__getitem__.assert_any_call(probe.NET_FILTER_MAP_NAME)


class TestDnsFiltersConfig:

    def test_dns_filters_stored_from_config(self):
        probe = TCPConnectProbe(
            SimpleQueue(),
            {
                'filters': [],
                'dns_filters': [{'domain': 'api.airbrake.io'}, {'domain': 'collector.newrelic.com'}],
            },
        )
        assert probe.dns_filters == [{'domain': 'api.airbrake.io'}, {'domain': 'collector.newrelic.com'}]

    def test_dns_filters_defaults_to_empty(self):
        probe = TCPConnectProbe(SimpleQueue(), {'filters': []})
        assert probe.dns_filters == []
