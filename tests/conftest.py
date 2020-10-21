import sys
from unittest.mock import MagicMock


# Globally mock bcc module
bcc = MagicMock()
sys.modules.setdefault('bcc', bcc)
