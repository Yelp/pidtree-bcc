import socket
from unittest.mock import call
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from pidtree_bcc.probes.net_listen import NetListenProbe
from pidtree_bcc.probes.net_listen import NetListenWrapper


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


@patch('pidtree_bcc.probes.net_listen.time')
@patch('pidtree_bcc.probes.net_listen.psutil')
def test_net_listen_snapshot_worker(mock_psutil, mock_time):
    mock_time.sleep.side_effect = [None, Exception('foobar')]  # to stop inf loop
    mock_psutil.net_connections.return_value = [
        MagicMock(
            pid=111,
            status='LISTEN',
            laddr=MagicMock(ip='127.0.0.1', port=1337),
        ),
        MagicMock(
            pid=112,
            status='LISTEN',
            laddr=MagicMock(ip='127.0.0.1', port=80),
        ),
        MagicMock(
            pid=113,
            status='NONE',
            laddr=MagicMock(ip='127.0.0.1', port=7331),
            type=socket.SOCK_DGRAM,
        ),
        MagicMock(
            pid=None,
        ),
    ]
    probe = NetListenProbe(None, {'excludeports': ['0-100'], 'protocols': ['udp', 'tcp']})
    with patch.object(probe, '_process_events') as mock_process:
        # never_crash uses functools.wraps so we can extract the wrapped method
        undecorated_method = probe._snapshot_worker.__wrapped__
        # assert we catch the inf loop stopping exception
        with pytest.raises(Exception, match='foobar'):
            # the undecorated method is not bound to the object,
            # so we need to pass `probe` as `self`
            undecorated_method(probe, 123)
        mock_process.assert_has_calls([
            call(None, NetListenWrapper(111, 16777343, 1337, 6), None, False),
            call(None, NetListenWrapper(113, 16777343, 7331, 17), None, False),
        ])
    mock_psutil.net_connections.assert_called_once_with('inet4')
    mock_time.sleep.assert_has_calls([call(300), call(123)])
