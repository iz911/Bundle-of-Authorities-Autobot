import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MEMO_PATH = (
    ROOT
    / "Example docs for BOA"
    / "Example memo with a certain order for list of authorities that can be used for BOAs (but no BOA).docx"
)

# The example memo is a private document (gitignored), so tests that read it are skipped without it.
requires_memo = pytest.mark.skipif(not MEMO_PATH.exists(), reason="the private example memo isn't present")
