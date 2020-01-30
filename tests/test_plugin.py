import pytest
from pidtree_bcc.plugin import load_plugins
from pidtree_bcc.plugins.identityplugin import Identityplugin

def test_plugins_loads_no_plugins():
    plugins = load_plugins({})
    assert plugins == []

def test_plugins_loads_identity_plugin():
    plugins = load_plugins({"identityplugin": {}})
    assert isinstance(plugins[0], Identityplugin)

def test_plugins_doesnt_load_disabled_identity_plugin():
    plugins = load_plugins({"identityplugin": {"enabled": False}})
    assert plugins == []

def test_plugins_exception_on_no_file():
    with pytest.raises(RuntimeError) as e:
        load_plugins({"please_dont_make_a_plugin_called_this": {}})
    assert "No module named " in str(e)
