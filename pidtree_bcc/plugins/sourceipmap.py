import os
from functools import partial

import staticconf

from pidtree_bcc.plugin import BasePlugin


def hosts_loader(filename: str) -> dict:
    """ Loads host mapping file

    :param str filename: path to file
    :return: mapping as dictionary
    """
    return_dict = {}
    with open(filename) as mapfile:
        lines = [
            line.strip() for line in mapfile
            if not line.startswith('#') and line.strip() != ''
        ]
    for line in lines:
        splitline = line.split()
        return_dict[splitline[0]] = ' '.join(splitline[1:])
    return return_dict


def build_configuration(filename: str, namespace: str) -> staticconf.config.ConfigurationWatcher:
    """ Create configuration watcher for host mapping files

    :param str filename: path to file
    :param str namespace: configuration namespace
    :return: configuration watcher
    """
    config_loader = partial(
        staticconf.loader.build_loader(hosts_loader),
        filename,
        namespace=namespace,
        flatten=True,
    )
    reloader = staticconf.config.ReloadCallbackChain(namespace)
    return staticconf.config.ConfigurationWatcher(
        config_loader,
        filename,
        min_interval=2,
        reloader=reloader,
    )


class Sourceipmap(BasePlugin):
    """ Plugin for mapping source ip to a name """

    def __init__(self, args: dict):
        self.validate_args(args)
        self.hosts_dict = {}
        self.config_watchers = []
        self.attribute_key = args.get('attribute_key', 'source_host')
        for hostfile in args['hostfiles']:
            self.config_watchers.append(
                build_configuration(hostfile, __name__),
            )
        for config_watcher in self.config_watchers:
            config_watcher.config_loader()
        self.config = staticconf.NamespaceReaders(__name__)

    def process(self, event: dict) -> dict:
        saddr = event.get('saddr', None)
        for config_watcher in self.config_watchers:
            config_watcher.reload_if_changed()
        if saddr is not None:
            event[self.attribute_key] = self.config.read_string(saddr, '')
        return event

    def validate_args(self, args: dict):
        hostfiles = args.get('hostfiles', None)
        if hostfiles is None:
            raise RuntimeError(
                "'hostfiles' option not supplied to sourceipmap plugin",
            )
        elif not isinstance(hostfiles, list):
            raise RuntimeError(
                "'hostfiles' option should be a list of fully qualified file paths",
            )

        for hostfile in hostfiles:
            if not os.path.isfile(hostfile):
                raise RuntimeError(
                    "File `{hostfile}` passed as a 'hostfiles' entry to the sourceipmap plugin does not exist".format(
                        hostfile=hostfile,
                    ),
                )
