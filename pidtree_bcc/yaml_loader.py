import os.path
import sys
from functools import partial
from typing import Any
from typing import AnyStr
from typing import IO
from typing import List
from typing import Tuple
from typing import Union

import yaml


class FileIncludeLoader(yaml.SafeLoader):
    """ Custom YAML loader which allows including data from separate files, e.g.:

    ```
    foo: !include some/other/file
    ```
    """

    def __init__(self, stream: Union[AnyStr, IO], included_files: List[str]):
        """ Constructor

        :param Union[AnyStr, IO] stream: input data
        :param List[str] included_files: list reference to be filled with external files being loaded
        """
        super().__init__(stream)
        self.add_constructor('!include', self.include_file)
        self.included_files = included_files

    def include_file(self, loader: yaml.Loader, node: yaml.Node) -> Any:
        """ Constructs a yaml node from a separate file.

        :param yaml.Loader loader: YAML loader object
        :param yaml.Node node: parsed node
        :return: loaded node contents
        """
        name = loader.construct_scalar(node)
        filepath = (
            os.path.join(os.path.dirname(loader.name), name)
            if not os.path.isabs(name)
            else name
        )
        try:
            with open(filepath) as f:
                self.included_files.append(filepath)
                next_loader = partial(FileIncludeLoader, included_files=self.included_files)
                return yaml.load(f, Loader=next_loader)
        except OSError:
            _, value, traceback = sys.exc_info()
            raise yaml.YAMLError(value).with_traceback(traceback)

    @classmethod
    def get_loader_instance(cls) -> Tuple[partial, List[str]]:
        """ Get loader and callback list of included files """
        included_files = []
        return partial(cls, included_files=included_files), included_files
