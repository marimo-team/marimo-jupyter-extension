"""Executable discovery for marimo and pixi."""

import os
import shutil
from pathlib import Path

from .config import Config

# Minimum marimo version for uv or disabled sandboxing.
MARIMO_VERSION = "0.23.14"
PIXI_MARIMO_MIN_VERSION = "0.25.0"

COMMON_LOCATIONS = [
    "~/.local/bin/marimo",
    "/opt/bin/marimo",
    "/usr/local/bin/marimo",
]

# Where the pixi installer (https://pixi.sh/install.sh) and image layers
# usually put the binary. `$PIXI_HOME/bin` is checked first when set.
PIXI_COMMON_LOCATIONS = [
    "~/.pixi/bin/pixi",
    "/opt/pixi/bin/pixi",
    "/usr/local/bin/pixi",
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
        version = (
            PIXI_MARIMO_MIN_VERSION
            if config.sandbox == "pixi"
            else MARIMO_VERSION
        )
        return [config.uvx_path, f"marimo[sandbox]>={version}"]

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


def get_pixi_path(config: Config) -> str:
    """Path to the pixi executable required by `sandbox = "pixi"`.

    Raises:
        FileNotFoundError: pixi is not configured and not discoverable.
    """
    if found := find_pixi(config):
        return found

    raise FileNotFoundError(
        "pixi executable not found, but MarimoProxyConfig.sandbox is "
        "'pixi'.\n"
        "Solutions:\n"
        "  - Install pixi>=0.80: curl -fsSL https://pixi.sh/install.sh | sh\n"
        "  - Add pixi's bin directory (e.g. ~/.pixi/bin) to the spawner PATH\n"
        "  - Configure MarimoProxyConfig.pixi_path in jupyterhub_config.py\n"
        "  - Or select the uv backend: MarimoProxyConfig.sandbox = 'uv'"
    )


def find_pixi(config: Config) -> str | None:
    """Locate pixi: explicit `pixi_path`, then PATH, then common locations."""
    if config.pixi_path:
        candidate = Path(config.pixi_path).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        return None

    if which := shutil.which("pixi"):
        return which

    candidates = list(PIXI_COMMON_LOCATIONS)
    if pixi_home := os.environ.get("PIXI_HOME"):
        candidates.insert(0, str(Path(pixi_home) / "bin" / "pixi"))
    for location in candidates:
        candidate = Path(location).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    return None
