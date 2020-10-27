import pytest

from pidtree_bcc.plugins import load_plugins
from pidtree_bcc.plugins.identityplugin import Identityplugin


def test_plugins_loads_no_plugins():
    plugins = load_plugins({}, 'mock_probe')
    assert plugins == []


def test_plugins_loads_multiple_plugins():
    plugins = load_plugins(
        {
            'identityplugin': {},
            'sourceipmap': {
                'hostfiles': ['/etc/hosts'],
            },
        }, 'tcp_connect',
    )
    assert len(plugins) == 2


def test_plugins_loads_identity_plugin():
    plugins = load_plugins({'identityplugin': {}}, 'mock_probe')
    assert isinstance(plugins[0], Identityplugin)


def test_plugins_doesnt_load_disabled_identity_plugin():
    plugins = load_plugins({'identityplugin': {'enabled': False}}, 'mock_probe')
    assert plugins == []


def test_plugins_exception_on_no_file():
    with pytest.raises(RuntimeError) as e:
        load_plugins({'please_dont_make_a_plugin_called_this': {}}, 'mock_probe')
    assert 'No module named ' in str(e)


def test_plugins_exception_with_unload(caplog):
    plugins = load_plugins(
        {
            'please_dont_make_a_plugin_called_this': {'unload_on_init_exception': True},
            'identityplugin': {},
        }, 'mock_probe',
    )
    assert len(plugins) == 1
    assert isinstance(plugins[0], Identityplugin)
    assert 'Could not import [\'pidtree_bcc.plugins.please_dont_make_a_plugin_called_this\']' in caplog.text


def test_plugins_load_incompatible():
    with pytest.raises(RuntimeError):
        load_plugins({'sourceipmap': {}}, 'mock_probe')
