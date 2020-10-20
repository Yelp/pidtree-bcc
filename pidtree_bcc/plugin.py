import importlib
import sys
from typing import List


class BasePlugin:

    def __init__(self, args: dict):
        """ Constructor

        :param dict args: plugin parameters
        """
        self.validate_args(args)

    def process(self, event: dict) -> dict:
        """ Process the `event` dict, add in additional metadata and return a dict

        :param dict event: event dictionary
        :return: processed event dictionary
        """
        raise NotImplementedError(
            'Required method `process` has not been implemented by {}'.format(self.__name__),
        )

    def validate_args(self, args: dict):
        """ Not required, override in inheriting class if you want to use this

        :param dict args: plugin parameters
        """
        pass


def load_plugins(plugin_dict: dict, plugin_dir: str = 'pidtree_bcc.plugins') -> List[BasePlugin]:
    """ Load and configure plugins

    :param dict plugin_dict: where the keys are plugin names and the value
                             for each key is another dict of kwargs. Each key
                             must match a `.py` file in the plugin directory
    :param str plugin_dir: (optional) module path for plugins
    :return: list of loaded plugins
    """
    plugins = []
    for plugin_name, plugin_args in plugin_dict.items():
        error = None
        unload_on_init_exception = plugin_args.get(
            'unload_on_init_exception', False,
        )
        if not plugin_args.get('enabled', True):
            continue
        plugin_classname = plugin_name.capitalize()
        import_line = '.'.join([plugin_dir, plugin_name])
        try:
            module = importlib.import_module(import_line)
            plugin = getattr(module, plugin_classname)(plugin_args)
            plugins.append(plugin)
        except ImportError as e:
            error = RuntimeError(
                'Could not import {import_line}: {e}'.format(
                    import_line=import_line,
                    e=e,
                ),
            )
        except AttributeError as e:
            error = RuntimeError(
                'Could not find class {plugin_classname} in module {import_line}: {e}'.format(
                    plugin_classname=plugin_classname,
                    import_line=import_line,
                    e=e,
                ),
            )
        except Exception as e:
            error = e
        finally:
            if error:
                if unload_on_init_exception:
                    sys.stderr.write(str(error) + '\n')
                else:
                    raise error
    return plugins
