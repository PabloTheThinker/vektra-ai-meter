"""Vektra AI Meter — local usage glance panel for Linux."""

from .snapshot import build_snapshot, write_snapshot

__all__ = ["build_snapshot", "write_snapshot"]
__version__ = "0.3.6"