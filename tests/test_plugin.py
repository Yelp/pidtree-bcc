import pytest
from pidtree_bcc.plugin import load_plugins
from pidtree_bcc.plugins.identityplugin import Identityplugin
from pidtree_bcc.plugins.sourceipmap import Sourceipmap

def test_plugins_loads_no_plugins():
    plugins = load_plugins({})
    assert plugins == []

def test_plugins_loads_multiple_plugins():
    plugins = load_plugins({
        "identityplugin": {},
        "sourceipmap": {
            "hostfiles": ["/etc/hosts"]
        }
    })
    assert len(plugins) == 2

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

def test_plugins_exception_with_unload(capsys):
    plugins = load_plugins({
        "please_dont_make_a_plugin_called_this": {"unload_on_init_exception": True},
        "identityplugin": {},
    })
    captured = capsys.readouterr()
    assert len(plugins) == 1
    assert isinstance(plugins[0], Identityplugin)
    assert "Could not import pidtree_bcc.plugins.please_dont_make_a_plugin_called_this" in captured.err
