import pathlib
from unittest.mock import ANY
from unittest.mock import patch

from pidtree_bcc import config


MOCK_CONFIG = '''---
udp_session:
  filters: [foo]
tcp_connect:
  filters: [bar]
  other: true
'''


@patch('pidtree_bcc.config.self_restart')
def test_configuration_loading_lifecycle(mock_restart, tmp_path: pathlib.Path):
    test_conf = tmp_path / 'test.yml'
    with test_conf.open('w') as f:
        f.write(MOCK_CONFIG)

    watcher = config.setup_config(test_conf.as_posix(), watch_config=True, min_watch_interval=0)

    loaded_configs = {k: (v, q) for k, v, q in config.enumerate_probe_configs()}
    assert loaded_configs == {
        'udp_session': ({'filters': ['foo']}, ANY),
        'tcp_connect': ({'filters': ['bar'], 'other': True}, ANY),
    }

    # test hot-swappable
    with test_conf.open('w') as f:
        f.write(MOCK_CONFIG.replace('foo', 'stuff'))

    watcher.reload_if_changed()
    assert loaded_configs['tcp_connect'][1].empty()
    assert not loaded_configs['udp_session'][1].empty()
    assert loaded_configs['udp_session'][1].get() == {'filters': ['stuff']}

    # test non-hot-swappable
    with test_conf.open('w') as f:
        f.write(MOCK_CONFIG.replace('true', 'false'))

    watcher.reload()  # forcing reload to avoid caring about mtime
    mock_restart.assert_called_once_with()
