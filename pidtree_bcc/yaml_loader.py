import hashlib
import logging
import os
import re
import shutil
import sys
import tempfile
from functools import partial
from threading import Condition
from threading import Thread
from typing import Any
from typing import AnyStr
from typing import Dict
from typing import IO
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union
from urllib import request

import yaml

from pidtree_bcc.utils import never_crash
from pidtree_bcc.utils import StopFlagWrapper


class FileIncludeLoader(yaml.SafeLoader):
    """ Custom YAML loader which allows including data from separate files, e.g.:

    ```
    foo: !include some/other/file
    ```
    """

    REMOTE_FETCH_INTERVAL_SECONDS = 60 * 60
    REMOTE_FETCH_MAX_WAIT_SECONDS = 20

    remote_fetcher: Optional[Thread] = None
    remote_fetcher_outdir: Optional[str] = None
    remote_fetcher_fence: Optional[Condition] = None
    remote_fetch_workload: Dict[str, Tuple[str, Condition]] = {}

    def __init__(
        self,
        stream: Union[AnyStr, IO],
        included_files: List[str],
        stop_flag: Optional[StopFlagWrapper] = None,
    ):
        """ Constructor

        :param Union[AnyStr, IO] stream: input data
        :param List[str] included_files: list reference to be filled with external files being loaded
        """
        super().__init__(stream)
        self.add_constructor('!include', self.include_file)
        self.included_files = included_files
        self.stop_flag = stop_flag

    def include_file(self, loader: yaml.Loader, node: yaml.Node) -> Any:
        """ Constructs a yaml node from a separate file.

        :param yaml.Loader loader: YAML loader object
        :param yaml.Node node: parsed node
        :return: loaded node contents
        """
        name = loader.construct_scalar(node)
        filepath = (
            self.include_remote(name)
            if re.match(r'^https?://', name)
            else (
                os.path.join(os.path.dirname(loader.name), name)
                if not os.path.isabs(name)
                else name
            )
        )
        try:
            with open(filepath) as f:
                self.included_files.append(filepath)
                next_loader = partial(FileIncludeLoader, included_files=self.included_files)
                return yaml.load(f, Loader=next_loader)
        except OSError:
            _, value, traceback = sys.exc_info()
            raise yaml.YAMLError(value).with_traceback(traceback)

    def include_remote(self, url: str) -> str:
        """ Load remote configuration data

        :param str url: resource url
        :return: local filepath where data is stored
        """
        if self.remote_fetcher is None or not self.remote_fetcher.is_alive():
            self.remote_fetcher_fence = Condition()
            self.remote_fetcher_outdir = tempfile.mkdtemp(prefix='pidtree-bcc-conf')
            self.remote_fetcher = Thread(
                target=fetch_remote_configurations,
                args=(
                    self.REMOTE_FETCH_INTERVAL_SECONDS, self.remote_fetcher_fence,
                    self.remote_fetch_workload, self.stop_flag,
                ),
                daemon=True,
            )
            self.remote_fetcher.start()
        logging.info(f'Loading remote configuration from {url}')
        ready = Condition()
        url_sha = hashlib.sha256(url.encode()).hexdigest()
        output_path = os.path.join(self.remote_fetcher_outdir, f'{url_sha}.yaml')
        self.remote_fetch_workload[url] = (output_path, ready)
        with self.remote_fetcher_fence:
            self.remote_fetcher_fence.notify()
        with ready:
            if not ready.wait(timeout=self.REMOTE_FETCH_MAX_WAIT_SECONDS):
                raise ValueError(f'Failed to load configuration at {url}')
        return output_path

    @classmethod
    def get_loader_instance(cls, stop_flag: Optional[StopFlagWrapper] = None) -> Tuple[partial, List[str]]:
        """ Get loader and callback list of included files

        :param StopFlagWrapper stop_flag: signal for background threads to stop
        :return: loader and callback list of included files
        """
        included_files = []
        return partial(cls, included_files=included_files, stop_flag=stop_flag), included_files


@never_crash
def fetch_remote_configurations(
    interval: int,
    fence: Condition,
    workload: Dict[str, Tuple[str, Condition]],
    stop_flag: Optional[StopFlagWrapper] = None,
):
    """ Periodically sync to disc remote configurations

    :param int interval: seconds to wait between each check
    :param Condition fence: condition object to cause
    :param Dict[str, Tuple[str, Condition]] workload: set of resources to fetch (format: url -> (output_file, ready))
    :param StopFlagWrapper stop_flag: signal thead to stop
    """
    while not (stop_flag and stop_flag.do_stop):
        # list() prevents dict from changing during the loop
        for url, path_ready in list(workload.items()):
            output_path, ready = path_ready
            with ready:
                _fetch_remote_configuration_impl(url, output_path)
                ready.notify()
        with fence:
            fence.wait(timeout=interval)


def _fetch_remote_configuration_impl(url: str, output_path: str):
    """ Downloads remote configuration to file, if changed
    compared to current output path.

    :param str url: remote config url
    :param str output_path: output file path
    """
    checksum = _md5sum(output_path) if os.path.exists(output_path) else ''
    if checksum and '.s3.amazonaws.' in url:
        # special case for AWS S3, which can give us a checksum in the header
        req = request.Request(url=url, method='HEAD')
        with request.urlopen(req) as response:
            response_etag = response.headers.get('ETag').strip('"').lower()
        if response_etag == checksum:
            return
    # store data to different path and rename, so eventual replacement is atomic
    tmpfd, tmppath = tempfile.mkstemp()
    tmp = os.fdopen(tmpfd, 'wb')
    with request.urlopen(url) as response:
        shutil.copyfileobj(response, tmp)
    tmp.close()
    if _md5sum(tmppath) != checksum:
        os.rename(tmppath, output_path)


def _md5sum(filepath: str) -> str:
    """ Compute MD5 checksum for file

    :param str filepath: path to read data from
    :return: hex encoded checksum string
    """
    hash_md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()
