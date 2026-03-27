"""Configuration for marimo-jupyter-extension."""

import os
import socket
from dataclasses import dataclass
from pathlib import Path

from traitlets import Bool, Int, Unicode, default
from traitlets.config import Configurable

DEFAULT_TIMEOUT = 60


def _detect_localhost_host() -> str | None:
    """Return '::1' if localhost resolves to IPv6 first, else None.

    When None, the --host flag is omitted and marimo uses its own default
    (127.0.0.1). When '::1', marimo binds to the IPv6 loopback to match
    how jupyter-server-proxy resolves localhost on IPv6-first systems.
    """
    try:
        results = socket.getaddrinfo("localhost", None)
        if results and results[0][0] == socket.AF_INET6:
            return "::1"
    except socket.gaierror:
        pass
    return None


class MarimoProxyConfig(Configurable):
    """Configuration for marimo-jupyter-extension.

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

    no_sandbox = Bool(
        default_value=False,
        allow_none=True,
        help="Start marimo without sandboxing",
    ).tag(config=True)

    host = Unicode(
        allow_none=True,
        help=(
            "Host for marimo to bind to. Auto-detected from localhost "
            "resolution if not set; override to force a specific address."
        ),
    ).tag(config=True)

    @default("host")
    def _default_host(self):
        return _detect_localhost_host()

    @default("marimo_path")
    def _default_marimo_path(self):
        return None

    @default("uvx_path")
    def _default_uvx_path(self):
        # Derive uvx from $UV if set (standard uv environment variable)
        if uv_path := os.environ.get("UV"):
            return str(Path(uv_path).parent / "uvx")
        return None

    @default("timeout")
    def _default_timeout(self):
        return DEFAULT_TIMEOUT


@dataclass(frozen=True)
class Config:
    """Resolved configuration (immutable snapshot)."""

    marimo_path: str | None  # Explicit marimo path
    uvx_path: str | None  # If set, use uvx mode
    timeout: int
    base_url: str
    no_sandbox: bool = False  # Keep sandbox as default
    host: str | None = (
        None  # None = omit --host flag, let marimo use its default
    )


def get_config(traitlets_config: MarimoProxyConfig | None = None) -> Config:
    """Load configuration from Traitlets or defaults."""
    if traitlets_config is not None:
        cfg = traitlets_config
    else:
        # Try to get config from the running ServerApp so that settings
        # from jupyter_notebook_config / jupyterhub_config are respected.
        try:
            from jupyter_server.serverapp import ServerApp

            app = ServerApp.instance()
            cfg = MarimoProxyConfig(config=app.config)
        except Exception:
            cfg = MarimoProxyConfig()

    return Config(
        marimo_path=cfg.marimo_path,
        uvx_path=cfg.uvx_path,
        timeout=cfg.timeout,
        base_url=_get_base_url(),
        no_sandbox=bool(cfg.no_sandbox),
        host=cfg.host,
    )


def _get_base_url() -> str:
    """Get base URL, gracefully handling non-JupyterHub environments."""
    prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
    return f"{prefix}marimo"
