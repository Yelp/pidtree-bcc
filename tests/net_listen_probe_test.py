from unittest.mock import MagicMock
from unittest.mock import patch

from pidtree_bcc.probes.net_listen import NetListenProbe


@patch('pidtree_bcc.probes.net_listen.crawl_process_tree')
def test_net_listen_enrich_event(mock_crawl):
    probe = NetListenProbe(None)
    mock_event = MagicMock(
        pid=123,
        port=1337,
        laddr=0,
        protocol=6,
    )
    mock_crawl.return_value = [
        {'pid': 123, 'cmdline': 'nc -lp 1337', 'username': 'foo'},
        {'pid': 50, 'cmdline': 'bash', 'username': 'foo'},
        {'pid': 1, 'cmdline': 'init', 'username': 'root'},
    ]
    assert probe.enrich_event(mock_event) == {
        'pid': 123,
        'proctree': [
            {'pid': 123, 'cmdline': 'nc -lp 1337', 'username': 'foo'},
            {'pid': 50, 'cmdline': 'bash', 'username': 'foo'},
            {'pid': 1, 'cmdline': 'init', 'username': 'root'},
        ],
        'laddr': '0.0.0.0',
        'port': 1337,
        'protocol': 'tcp',
        'error': '',
    }
    mock_crawl.assert_called_once_with(123)
