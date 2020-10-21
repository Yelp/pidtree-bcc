from unittest.mock import MagicMock
from unittest.mock import patch

from pidtree_bcc.probes.tcp_connect import TCPConnectProbe
from pidtree_bcc.utils import ip_to_int


@patch('pidtree_bcc.probes.tcp_connect.datetime')
@patch('pidtree_bcc.probes.tcp_connect.crawl_process_tree')
@patch('pidtree_bcc.probes.tcp_connect.psutil')
def test_tcp_connect_enrich_event(mock_psutil, mock_crawl, mock_datetime):
    probe = TCPConnectProbe(None)
    mock_event = MagicMock(
        pid=123,
        dport=80,
        daddr=ip_to_int('1.1.1.1'),
        saddr=ip_to_int('127.0.0.1'),
    )
    mock_crawl.return_value = [
        MagicMock(
            pid=123,
            cmdline=lambda: ['curl', '1.1.1.1'],
            username=lambda: 'foo',
        ),
        MagicMock(
            pid=50,
            cmdline=lambda: ['bash'],
            username=lambda: 'foo',
        ),
        MagicMock(
            pid=1,
            cmdline=lambda: ['init'],
            username=lambda: 'root',
        ),
    ]
    mock_datetime.utcnow.return_value.isoformat.return_value = 'x'
    assert probe.enrich_event(mock_event) == {
        'timestamp': 'xZ',
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
    mock_psutil.Process.assert_called_once_with(123)
    mock_crawl.assert_called_once_with(mock_psutil.Process.return_value)
