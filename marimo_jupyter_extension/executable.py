"""Executable discovery for marimo."""

import shutil
from pathlib import Path

from .config import Config

COMMON_LOCATIONS = [
    "~/.local/bin/marimo",
    "/opt/bin/marimo",
    "/usr/local/bin/marimo",
]


def get_marimo_command(config: Config) -> list[str]:
    """Get marimo command based on configuration.

    Args:
        config: Config dataclass with marimo_path and uvx_path

    Logic:
    - If uvx_path is set → use uvx mode: [uvx_path, 'marimo']
    - If marimo_path is set → use it directly: [marimo_path]
    - Otherwise → search PATH and common locations
    - If not found → raise FileNotFoundError

    Returns:
        Command as list, e.g. ['/usr/bin/marimo'] or ['/usr/bin/uvx', 'marimo']
    """
    # uvx mode (opt-in via explicit uvx_path)
    if config.uvx_path:
        return [config.uvx_path, "marimo[sandbox]>=0.19.11"]

    # Explicit marimo path
    if config.marimo_path:
        return [config.marimo_path]

    # Search for marimo
    if found := _find_marimo():
        return [found]

    raise FileNotFoundError(
        "marimo executable not found.\n"
        "Solutions:\n"
        "  - Install marimo: pip install marimo\n"
        "  - Configure MarimoProxyConfig.marimo_path in jupyterhub_config.py\n"
        "  - Configure MarimoProxyConfig.uvx_path to use uvx marimo"
    )


def _find_marimo() -> str | None:
    """Search for marimo in PATH and common locations."""
    # Check system PATH
    if which := shutil.which("marimo"):
        return which

    # Check common locations
    for location in COMMON_LOCATIONS:
        candidate = Path(location).expanduser()
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    return None
