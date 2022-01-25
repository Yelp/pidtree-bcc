import logging
from functools import partial
from multiprocessing import SimpleQueue
from typing import Generator
from typing import Iterable
from typing import Optional
from typing import Tuple

import staticconf.config
import yaml
from staticconf.config import ConfigNamespace
from staticconf.config import ConfigurationWatcher
from staticconf.config import DEFAULT as DEFAULT_NAMESPACE
from staticconf.config import get_namespace
from staticconf.config import get_namespaces_from_names
from staticconf.loader import DictConfiguration

from pidtree_bcc.utils import never_crash
from pidtree_bcc.utils import self_restart


HOTSWAP_CALLBACK_NAMESPACE = get_namespace('__change_callbacks')
HOT_SWAPPABLE_SETTINGS = ('filters', 'excludeports', 'includeports')


@never_crash
def _forward_config_change(queue: SimpleQueue, config_data: dict):
    queue.put(config_data)


def _non_hotswap_settings(config_data: dict) -> dict:
    return {
        k: v for k, v in config_data.items()
        if k not in HOT_SWAPPABLE_SETTINGS
    }


def _get_probe_namespaces() -> Generator[ConfigNamespace, None, None]:
    """ Enumerate probe configuration namespaces """
    for namespace in get_namespaces_from_names(None, all_names=True):
        if namespace.name not in (DEFAULT_NAMESPACE, HOTSWAP_CALLBACK_NAMESPACE.name):
            yield namespace


def _clear_and_restart():
    """ Clear staticconf namespaces and restart """
    reset_config_state()
    self_restart()


def _drop_namespaces(names: Iterable[str]):
    """ Deletes configuration namespaces from staticconf

    :param Iterable[str] names: namespaces to drop
    """
    for name in names:
        staticconf.config.configuration_namespaces.pop(name, None)


def parse_config(config_file: str, watch_config: bool = False):
    """ Parses yaml config file (if indicated)

    :param str config_file: config file path
    :param bool watch_config: perform necessary setup to enable configuration hot swaps
    """
    with open(config_file) as f:
        config_data = yaml.safe_load(f)
    config_probe_names = {key for key in config_data if not key.startswith('_')}
    current_probe_names = {ns.name for ns in _get_probe_namespaces()}
    if watch_config and current_probe_names and config_probe_names != current_probe_names:
        # probes added or removed, triggering restart
        _drop_namespaces(current_probe_names - config_probe_names)
        return _clear_and_restart()
    for key in config_probe_names:
        probe_config = config_data[key]
        config_namespace = get_namespace(key)
        current_values = config_namespace.get_config_values().copy()
        if key not in HOTSWAP_CALLBACK_NAMESPACE:
            # First time loading
            callback_method = partial(_forward_config_change, SimpleQueue()) if watch_config else None
            DictConfiguration({key: callback_method}, namespace=HOTSWAP_CALLBACK_NAMESPACE.name)
        elif watch_config:
            is_different = probe_config != current_values
            if is_different and _non_hotswap_settings(probe_config) != _non_hotswap_settings(current_values):
                # Non hot-swappable setting changed -> restart
                return _clear_and_restart()
            elif is_different:
                # Only hot-swappable settings changed, trigger proble filters reload
                HOTSWAP_CALLBACK_NAMESPACE[key](probe_config)
        # staticconf does clear namespaces before reloads, so we do it ourselves
        config_namespace.clear()
        DictConfiguration(probe_config, namespace=key, flatten=False)


def setup_config(
    config_file: str,
    watch_config: bool = False,
    min_watch_interval: int = 60,
) -> Optional[ConfigurationWatcher]:
    """ Load and setup configuration file

    :param str config_file: config file path
    :param bool watch_config: perform necessary setup to enable configuration hot swaps
    :param int min_watch_interval:
    :return: if `watch_config` is set, the configuration watcher object, None otherwise.
    """
    logging.getLogger('staticconf.config').setLevel(logging.WARN)
    config_loader = partial(parse_config, config_file, watch_config)
    watcher = ConfigurationWatcher(
        config_loader=config_loader,
        filenames=[config_file],
        min_interval=min_watch_interval,
    ) if watch_config else None
    config_loader()
    return watcher


def enumerate_probe_configs() -> Generator[Tuple[str, dict, Optional[SimpleQueue]], None, None]:
    """ List loaded probe configurations

    :return: tuple of probe name, configuration data, and optionally the queue for change notifications
    """
    for namespace in _get_probe_namespaces():
        curr_values = namespace.get_config_values().copy()
        change_callback = HOTSWAP_CALLBACK_NAMESPACE.get(namespace.name, default=None)
        change_queue = change_callback.args[0] if change_callback else None
        yield namespace.name, curr_values, change_queue


def reset_config_state():
    """ Reset all configuration namespaces """
    for namespace in get_namespaces_from_names(None, all_names=True):
        namespace.clear()
