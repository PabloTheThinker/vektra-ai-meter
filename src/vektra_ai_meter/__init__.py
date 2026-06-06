"""Vektra AI Meter — local usage glance panel for Linux."""

from .snapshot import build_snapshot, write_snapshot
from ._version import resolve_version

__all__ = ["build_snapshot", "write_snapshot", "__version__"]
__version__ = resolve_version()