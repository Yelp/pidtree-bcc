from pidtree_bcc.probes import BPFProbe


class MockProbe(BPFProbe):
    BPF_TEXT = r'''some text
{{ some_variable }}
some other text'''


def test_pbf_templating():
    mock_probe = MockProbe(None, {'some_variable': 'some_value'})
    assert mock_probe.expanded_bpf_text == '''some text
some_value
some other text'''
    MockProbe.TEMPLATE_VARS = ['some_variable']
    mock_probe = MockProbe(None, {'some_variable': 'some_value', 'rand_config': 1})
    assert mock_probe.expanded_bpf_text == '''some text
some_value
some other text'''
