"""Resolve the marimo version using the same flow that spawns the proxy."""

import subprocess

from .config import get_config
from .executable import get_marimo_command

_cached: str | None = None
_resolved = False


def get_marimo_version() -> str | None:
    """Run `<get_marimo_command()> --version` once and cache the result.

    Returns the version string (e.g. "0.23.1") or None if marimo can't be
    resolved or the subprocess fails.
    """
    global _cached, _resolved
    if _resolved:
        return _cached
    _resolved = True
    try:
        cmd = [*get_marimo_command(get_config()), "--version"]
        result = subprocess.run(
            cmd, capture_output=True, timeout=10, check=True
        )
        token = result.stdout.decode().strip().split()[-1]
        _cached = token or None
    except Exception:
        _cached = None
    return _cached
