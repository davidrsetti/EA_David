"""Root conftest.py — adds project root to sys.path so 'nexus.*' imports work."""
import os
import sys

# Project root is the directory containing this file (EA_David/EA_David/)
# The package is imported as nexus.* so we add its parent directory.
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
