import mock
import pytest
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import bpf_text


def test_valid_bpf_text():
    print "BPF text" + bpf_text[0:10]
    assert False
