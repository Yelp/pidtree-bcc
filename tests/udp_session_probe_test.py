from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from pidtree_bcc.probes.udp_session import SessionEventWrapper
from pidtree_bcc.probes.udp_session import UDPSessionProbe


@patch('pidtree_bcc.probes.udp_session.crawl_process_tree')
@patch('pidtree_bcc.probes.udp_session.time')
def test_udp_session_enrich_event(mock_time, mock_crawl):
    probe = UDPSessionProbe(None)
    mock_time.monotonic.side_effect = range(3)
    mock_crawl.return_value = [
        {'pid': 123, 'cmdline': 'some_program', 'username': 'foo'},
        {'pid': 50, 'cmdline': 'bash', 'username': 'foo'},
        {'pid': 1, 'cmdline': 'init', 'username': 'root'},
    ]
    assert probe.enrich_event(
        MagicMock(type=1, pid=123, sock_pointer=1, daddr=168430090, dport=1337),
    ) is None
    assert probe.enrich_event(
        MagicMock(type=2, pid=123, sock_pointer=1, daddr=16777343, dport=1337),
    ) is None
    assert probe.enrich_event(
        MagicMock(type=3, pid=123, sock_pointer=1),
    ) == {
        'pid': 123,
        'proctree': [
            {'pid': 123, 'cmdline': 'some_program', 'username': 'foo'},
            {'pid': 50, 'cmdline': 'bash', 'username': 'foo'},
            {'pid': 1, 'cmdline': 'init', 'username': 'root'},
        ],
        'destinations': [
            {
                'daddr': '10.10.10.10',
                'port': 1337,
                'duration': 2,
                'msg_count': 1,
            },
            {
                'daddr': '127.0.0.1',
                'port': 1337,
                'duration': 1,
                'msg_count': 1,
            },
        ],
        'error': '',
    }
    mock_crawl.assert_called_once_with(123)


@patch('pidtree_bcc.probes.udp_session.time')
def test_udp_session_expiration_worker(mock_time):
    mock_time.sleep.side_effect = [None, Exception('foobar')]  # to stop inf loop
    mock_time.monotonic.return_value = 200
    probe = UDPSessionProbe(None)
    probe.session_tracking = {
        (1, 1): {'last_update': 180},
        (2, 2): {'last_update': 0},
        (3, 3): {'last_update': 190},
    }
    with patch.object(probe, '_process_events') as mock_process:
        # never_crash uses functools.wraps so we can extract the wrapped method
        undecorated_method = probe._session_expiration_worker.__wrapped__
        # assert we catch the inf loop stopping exception
        with pytest.raises(Exception, match='foobar'):
            # the undecorated method is not bound to the object,
            # so we need to pass `probe` as `self`
            undecorated_method(probe, 120)
        mock_process.assert_called_once_with(
            None, SessionEventWrapper(3, 2, 2), None, False,
        )
