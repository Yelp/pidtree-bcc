from unittest.mock import MagicMock
from unittest.mock import patch

from pidtree_bcc.probes.tcp_connect import TCPConnectProbe
from pidtree_bcc.utils import ip_to_int


@patch('pidtree_bcc.probes.tcp_connect.crawl_process_tree')
def test_tcp_connect_enrich_event(mock_crawl):
    probe = TCPConnectProbe(None)
    mock_event = MagicMock(
        pid=123,
        dport=80,
        daddr=ip_to_int('1.1.1.1'),
        saddr=ip_to_int('127.0.0.1'),
    )
    mock_crawl.return_value = [
        {'pid': 123, 'cmdline': 'curl 1.1.1.1', 'username': 'foo'},
        {'pid': 50, 'cmdline': 'bash', 'username': 'foo'},
        {'pid': 1, 'cmdline': 'init', 'username': 'root'},
    ]
    assert probe.enrich_event(mock_event) == {
        'pid': 123,
        'proctree': [
            {'pid': 123, 'cmdline': 'curl 1.1.1.1', 'username': 'foo'},
            {'pid': 50, 'cmdline': 'bash', 'username': 'foo'},
            {'pid': 1, 'cmdline': 'init', 'username': 'root'},
        ],
        'daddr': '1.1.1.1',
        'saddr': '127.0.0.1',
        'port': 80,
        'error': '',
    }
    mock_crawl.assert_called_once_with(123)
