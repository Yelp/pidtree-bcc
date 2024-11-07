import subprocess
from unittest.mock import call
from unittest.mock import MagicMock
from unittest.mock import patch

from pidtree_bcc.containers import list_container_mnt_namespaces


@patch('pidtree_bcc.containers.os')
@patch('pidtree_bcc.containers.subprocess')
def test_list_container_mnt_namespaces(mock_subprocess, mock_os):
    mock_subprocess.check_output.side_effect = [
        'aaaabbbbcccc\nddddeeeeffff\naaaacccceeee\nbbbbddddffff',
        '123',
        subprocess.CalledProcessError,
        '456',
        '789',
    ]
    mock_os.path.exists.return_value = False
    mock_os.stat.side_effect = [
        MagicMock(st_ino=111),
        MagicMock(st_ino=222),
        IOError,
    ]
    assert list_container_mnt_namespaces(['a=b']) == {111, 222}
    mock_subprocess.check_output.assert_has_calls([
        call(('docker', 'ps', '--no-trunc', '--quiet', '--filter', 'label=a=b'), encoding='utf8'),
        call(('docker', 'inspect', '-f', r'{{.State.Pid}}', 'aaaabbbbcccc'), encoding='utf8'),
        call(('docker', 'inspect', '-f', r'{{.State.Pid}}', 'ddddeeeeffff'), encoding='utf8'),
        call(('docker', 'inspect', '-f', r'{{.State.Pid}}', 'aaaacccceeee'), encoding='utf8'),
    ])
    mock_os.stat.assert_has_calls([
        call('/proc/123/ns/mnt'),
        call('/proc/456/ns/mnt'),
        call('/proc/789/ns/mnt'),
    ])
