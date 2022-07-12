import yaml

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
