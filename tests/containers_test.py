import subprocess
from unittest.mock import call
from unittest.mock import MagicMock
from unittest.mock import patch

from pidtree_bcc.containers import ContainerEventType
from pidtree_bcc.containers import list_container_mnt_namespaces
from pidtree_bcc.containers import MountNSInfo


@patch('pidtree_bcc.containers.os')
@patch('pidtree_bcc.containers.subprocess')
def test_list_container_mnt_namespaces(mock_subprocess, mock_os):
    mock_subprocess.check_output.side_effect = [
        'aaaabbbbcccc\nddddeeeeffff\naaaacccceeee\nbbbbddddffff',
        r'[{"State":{"Pid":123},"Name":"abc","Config":{"Labels":{"a":"b"}}}]',
        subprocess.CalledProcessError(returncode=1, cmd='whatever'),
        r'[{"State":{"Pid":456},"Name":"def","Config":{"Labels":{"a":"b"}}}]',
        r'[{"State":{"Pid":789},"Name":"ghi","Config":{"Labels":{"a":"b"}}}]',
    ]
    mock_os.path.exists.return_value = False  # force container client detection to "docker"
    mock_os.stat.side_effect = [
        MagicMock(st_ino=111),
        MagicMock(st_ino=222),
        IOError,
    ]
    assert list_container_mnt_namespaces(['a=b']) == {
        MountNSInfo('aaaabbbbcccc', 'abc', 111, ContainerEventType.start),
        MountNSInfo('aaaacccceeee', 'def', 222, ContainerEventType.start),
    }
    mock_subprocess.check_output.assert_has_calls([
        call(('docker', 'ps', '--no-trunc', '--quiet'), encoding='utf8'),
        call(('docker', 'inspect', 'aaaabbbbcccc'), encoding='utf8'),
        call(('docker', 'inspect', 'ddddeeeeffff'), encoding='utf8'),
        call(('docker', 'inspect', 'aaaacccceeee'), encoding='utf8'),
    ])
    mock_os.stat.assert_has_calls([
        call('/proc/123/ns/mnt'),
        call('/proc/456/ns/mnt'),
        call('/proc/789/ns/mnt'),
    ])
