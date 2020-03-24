import importlib
import sys

class BasePlugin:
    def __init__(self, args):
        self.validate_args(args)

    def process(self, event):
        """ Process the `event` dict, add in additional metadata and
        return a dict """
        raise NotImplementedError("Required method `process` has not been implemented by {}" % self.__name__)

    def validate_args(self, args):
        """ Not required, override in inheriting class if you want to
        use this """
        pass


def load_plugins(plugin_dict, plugin_dir="pidtree_bcc.plugins"):
    """ `plugin_dict` is a dict where the keys are plugin names and
    the value for each key is another dict of kwargs. Each key must
    match a `.py` file in the plugin directory and the kwargs can
    be validated on initialization of the plugin """
    plugins = []
    for plugin_name, plugin_args in plugin_dict.items():
        error = None
        unload_on_init_exception = plugin_args.get("unload_on_init_exception", False)
        if not plugin_args.get("enabled", True):
            continue
        plugin_classname = plugin_name.capitalize()
        import_line = ".".join([plugin_dir, plugin_name])
        try:
            module = importlib.import_module(import_line)
            plugin = getattr(module, plugin_classname)(plugin_args)
            plugins.append(plugin)
        except ImportError as e:
            error = RuntimeError("Could not import {import_line}: {e}".format(
                import_line=import_line,
                e=e,
            ))
        except AttributeError as e:
            error = RuntimeError("Could not find class {plugin_classname} in module {import_line}: {e}".format(
                plugin_classname=plugin_classname,
                import_line=import_line,
                e=e,
            ))
        except Exception as e:
            error = e
        finally:
            if error:
                if unload_on_init_exception:
                    sys.stderr.write(str(error) + "\n")
                else:
                    raise error
    return plugins
