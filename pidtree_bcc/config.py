import logging
from functools import partial
from multiprocessing import SimpleQueue
from typing import Generator
from typing import Optional
from typing import Tuple

import yaml
from staticconf.config import ConfigurationWatcher
from staticconf.config import DEFAULT as DEFAULT_NAMESPACE
from staticconf.config import get_namespace
from staticconf.config import get_namespaces_from_names
from staticconf.loader import DictConfiguration

from pidtree_bcc.utils import never_crash


HOTSWAP_CALLBACK_FIELD = '__change_callback'
HOT_SWAPPABLE_SETTINGS = ('filters', 'excludeports', 'includeports')


@never_crash
def _forward_config_change(queue: SimpleQueue, config_data: dict):
    queue.put(config_data)


def parse_config(config_file: str, watch_config: bool = False):
    """ Parses yaml config file (if indicated)

    :param str config_file: config file path
    :param bool watch_config: perform necessary setup to enable configuration hot swaps
    """
    with open(config_file) as f:
        config_data = yaml.safe_load(f)
    for key in config_data:
        if key.startswith('_'):
            continue
        probe_config = config_data[key]
        config_namespace = get_namespace(key)
        current_values = config_namespace.get_config_values().copy()
        if HOTSWAP_CALLBACK_FIELD not in current_values:
            # First time loading
            current_values[HOTSWAP_CALLBACK_FIELD] = partial(
                _forward_config_change, SimpleQueue(),
            ) if watch_config else None
        elif watch_config and any(
            current_values.get(field) != probe_config.get(field)
            for field in HOT_SWAPPABLE_SETTINGS
        ):
            # Checking if any of the changes can cause an hotswap (and then triggering it)
            current_values[HOTSWAP_CALLBACK_FIELD](probe_config)
        # staticconf does clear namespaces before reloads, so we do it ourselves
        config_namespace.clear()
        DictConfiguration(
            {**probe_config, HOTSWAP_CALLBACK_FIELD: current_values[HOTSWAP_CALLBACK_FIELD]},
            namespace=key,
            flatten=False,
        )


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
    for namespace in get_namespaces_from_names(None, all_names=True):
        if namespace.name != DEFAULT_NAMESPACE:
            curr_values = namespace.get_config_values().copy()
            change_callback = curr_values.pop(HOTSWAP_CALLBACK_FIELD, None)
            change_queue = change_callback.args[0] if change_callback else None
            yield namespace.name, curr_values, change_queue
