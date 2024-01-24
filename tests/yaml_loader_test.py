import os
from unittest.mock import patch

import yaml

from pidtree_bcc.utils import StopFlagWrapper
from pidtree_bcc.yaml_loader import fetch_remote_configurations
from pidtree_bcc.yaml_loader import FileIncludeLoader


def test_file_include_loader():
    loader, included_files = FileIncludeLoader.get_loader_instance()
    with open('tests/fixtures/parent_config.yaml') as f:
        data = yaml.load(f, Loader=loader)
    assert data == {
        'foo': [1, {'a': 2, 'b': 3}, 4],
        'bar': {'fizz': 'buzz'},
    }
    assert included_files == ['tests/fixtures/child_config.yaml']


@patch('pidtree_bcc.yaml_loader.tempfile')
@patch('pidtree_bcc.yaml_loader.request')
def test_file_include_remote(mock_request, mock_tempfile, tmp_path):
    stop_flag = StopFlagWrapper()
    # test could technically work with a real network request, but we mock anyway for better isolation
    mock_request.urlopen.return_value = open('tests/fixtures/child_config.yaml', 'rb')
    mock_tempfile.mkdtemp.return_value = tmp_path.absolute().as_posix()
    tmpout = (tmp_path / 'tmp.yaml').absolute().as_posix()
    mock_tempfile.mkstemp.return_value = (
        os.open(tmpout, os.O_WRONLY | os.O_CREAT | os.O_EXCL),
        tmpout,
    )
    # this self-referring patch ensures mocks are propagated to the fetcher thread
    with patch('pidtree_bcc.yaml_loader.fetch_remote_configurations', fetch_remote_configurations):
        loader, included_files = FileIncludeLoader.get_loader_instance(stop_flag)
        with open('tests/fixtures/remote_config.yaml') as f:
            data = yaml.load(f, Loader=loader)
    stop_flag.stop()
    assert data == {
        'foo': [1, {'a': 2, 'b': 3}, 4],
        'bar': {'fizz': 'buzz'},
    }
    assert included_files == [
        (tmp_path / '72e7a811f0c6baf6b49f9ddd2300d252a3eba7eb370f502cb834faa018ab26b9.yaml').absolute().as_posix(),
    ]
    mock_request.urlopen.assert_called_once_with(
        'https://raw.githubusercontent.com/Yelp/pidtree-bcc/master/tests/fixtures/child_config.yaml',
    )
