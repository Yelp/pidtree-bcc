import pytest
from pidtree_bcc.plugin import Plugins
from pidtree_bcc.plugins.identityplugin import Identityplugin

def test_plugins_loads_identity_plugin():
    plugins = Plugins({"identityplugin": {}}) 
    assert isinstance(plugins.plugins()[0], type(Identityplugin({})))

def test_plugins_exception_on_no_file():
    with pytest.raises(RuntimeError) as e:
        Plugins({"please_dont_make_a_plugin_called_this": {}})
    assert "No module named " in str(e)
