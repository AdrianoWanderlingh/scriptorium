"""Scriptorium: private, CPU-only knowledge bases built from digitised books."""

import os
from importlib.metadata import PackageNotFoundError, version

os.environ.setdefault("LANCEDB_LOG", "error")

try:
    __version__ = version("scriptorium")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
