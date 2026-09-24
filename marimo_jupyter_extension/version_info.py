"""Resolve the marimo version using the same flow that spawns the proxy."""

import subprocess
from functools import cache

from packaging.version import InvalidVersion, Version

from .config import get_config
from .executable import PIXI_MARIMO_MIN_VERSION, get_marimo_command


def get_marimo_version() -> str | None:
    """Return the configured marimo version, or None if it is unavailable."""
    try:
        return _get_command_version(tuple(get_marimo_command(get_config())))
    except Exception:
        return None


@cache
def _get_command_version(command: tuple[str, ...]) -> str | None:
    """Read and cache the version for each marimo command."""
    try:
        result = subprocess.run(
            [*command, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        tokens = result.stdout.strip().split()
        return tokens[-1] if tokens else None
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None


def check_pixi_marimo_version(command: list[str]) -> None:
    """Reject marimo versions that do not support Pixi sandboxing."""
    version = _get_command_version(tuple(command))
    try:
        if version is not None and Version(version) >= Version(
            PIXI_MARIMO_MIN_VERSION
        ):
            return
    except InvalidVersion:
        pass

    raise RuntimeError(
        f"Pixi sandboxing requires marimo>={PIXI_MARIMO_MIN_VERSION}.\n"
        f"Detected {version or 'an unknown version'} at {command[0]!r}.\n"
        "Upgrade marimo in the Python environment that provides this "
        "executable:\n"
        '  uv pip install --upgrade "marimo[sandbox]>='
        f'{PIXI_MARIMO_MIN_VERSION}"\n'
        "Or configure MarimoProxyConfig.uvx_path to use the uvx executable."
    )
