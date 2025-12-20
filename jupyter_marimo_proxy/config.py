"""Configuration for jupyter-marimo-proxy.

Precedence: Traitlets (admin) > Environment variables > Defaults
"""

import os
import warnings
from dataclasses import dataclass
from pathlib import Path

from traitlets import Int, Unicode, default
from traitlets.config import Configurable

# Environment variables (fallbacks when traitlets not configured)
ENV_MARIMO_PATH = "JUPYTERMARIMOPROXY_MARIMO_PATH"
ENV_UVX_PATH = "JUPYTERMARIMOPROXY_UVX_PATH"
ENV_TIMEOUT = "JUPYTERMARIMOPROXY_TIMEOUT"

DEFAULT_TIMEOUT = 60


class MarimoProxyConfig(Configurable):
    """Configuration for jupyter-marimo-proxy.

    Can be configured in jupyterhub_config.py:
        c.MarimoProxyConfig.marimo_path = "/opt/bin/marimo"
        c.MarimoProxyConfig.uvx_path = "/usr/local/bin/uvx"  # enables uvx mode
        c.MarimoProxyConfig.timeout = 120
    """

    marimo_path = Unicode(
        allow_none=True,
        help="Explicit path to marimo executable. If not set, searches PATH.",
    ).tag(config=True)

    uvx_path = Unicode(
        allow_none=True,
        help=(
            "Path to uvx executable. If set, uses 'uvx marimo' instead "
            "of marimo directly."
        ),
    ).tag(config=True)

    timeout = Int(
        DEFAULT_TIMEOUT,
        help="Timeout in seconds for marimo to start.",
    ).tag(config=True)

    @default("marimo_path")
    def _default_marimo_path(self):
        return os.environ.get(ENV_MARIMO_PATH)

    @default("uvx_path")
    def _default_uvx_path(self):
        if path := os.environ.get(ENV_UVX_PATH):
            return path
        # Derive uvx from $UV if set
        if uv_path := os.environ.get("UV"):
            return str(Path(uv_path).parent / "uvx")
        return None

    @default("timeout")
    def _default_timeout(self):
        try:
            return int(os.environ.get(ENV_TIMEOUT, DEFAULT_TIMEOUT))
        except ValueError:
            return DEFAULT_TIMEOUT


@dataclass(frozen=True)
class Config:
    """Resolved configuration (immutable snapshot)."""

    marimo_path: str | None  # Explicit marimo path
    uvx_path: str | None  # If set, use uvx mode
    timeout: int
    base_url: str


def get_config(traitlets_config: MarimoProxyConfig | None = None) -> Config:
    """Load configuration with precedence: Traitlets > Env vars > Defaults."""
    # Check for deprecated rc file
    rc_path = Path("~/.jupytermarimoproxyrc").expanduser()
    if rc_path.exists():
        warnings.warn(
            f"Deprecated: {rc_path} is no longer supported. "
            "Use environment variables or jupyterhub_config.py instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Use traitlets config if provided, otherwise create default
    cfg = traitlets_config or MarimoProxyConfig()

    return Config(
        marimo_path=cfg.marimo_path,
        uvx_path=cfg.uvx_path,
        timeout=cfg.timeout,
        base_url=_get_base_url(),
    )


def _get_base_url() -> str:
    """Get base URL, gracefully handling non-JupyterHub environments."""
    prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
    return f"{prefix}marimo"
