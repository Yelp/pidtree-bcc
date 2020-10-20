from unittest.mock import mock_open
from unittest.mock import patch

from pidtree_bcc.plugins.loginuidmap import Loginuidmap


def test_loginuidmap_get_loginuid():
    with patch('builtins.open', mock_open(read_data='123')) as _mock_open, \
            patch('pidtree_bcc.plugins.loginuidmap.pwd') as mock_pwd:
        mock_pwd.getpwuid.return_value.pw_name = 'foo'
        loginuid_info = Loginuidmap._get_loginuid(321)
        mock_pwd.getpwuid.assert_called_once_with(123)
        _mock_open.assert_called_once_with('/proc/321/loginuid')
        assert loginuid_info == (123, 'foo')


def test_loginuidmap_process():
    with patch.object(Loginuidmap, '_get_loginuid') as mock_get_loginuid:
        mock_get_loginuid.side_effect = [(1, 'foo'), (None, None), (2, 'bar')]
        plugin = Loginuidmap(None)
        event = plugin.process({'proctree': [{'pid': 100 + i} for i in range(3)]})
        assert event == {
            'proctree': [
                {'pid': 100, 'loginuid': 1, 'loginname': 'foo'},
                {'pid': 101},
                {'pid': 102, 'loginuid': 2, 'loginname': 'bar'},
            ],
        }
