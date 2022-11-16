import sys
from unittest.mock import MagicMock


# Globally mock bcc module
bcc = MagicMock()
bcc.__version__ = '0.18.0'
sys.modules.setdefault('bcc', bcc)
