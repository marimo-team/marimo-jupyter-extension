"""Configuration for marimo-jupyter-extension."""

import os
import socket
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from jupyter_server.utils import url_path_join
from traitlets import (
    Bool,
    Enum,
    Float,
    Int,
    List,
    TraitError,
    Unicode,
    default,
    validate,
)
from traitlets.config import Configurable

DEFAULT_TIMEOUT = 60
# pixi cold starts (`pixi exec` fetching uv, conda solve, uv overlay build)
# routinely exceed the uv default before the HTTP port opens.
DEFAULT_PIXI_TIMEOUT = 300

SandboxBackend = Literal["uv", "pixi"]


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
        c.MarimoProxyConfig.sandbox = "pixi"  # or "uv" (default), or None
        c.MarimoProxyConfig.timeout = 120
        c.MarimoProxyConfig.debug = True
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

    pixi_path = Unicode(
        allow_none=True,
        help=(
            "Explicit path to the pixi executable used by `sandbox = 'pixi'`. "
            "If not set, searches PATH, `$PIXI_HOME/bin`, and common "
            "locations (`~/.pixi/bin`, `/opt/pixi/bin`, `/usr/local/bin`)."
        ),
    ).tag(config=True)

    timeout = Int(
        DEFAULT_TIMEOUT,
        help=(
            "Timeout in seconds for marimo to start. Defaults to "
            f"{DEFAULT_TIMEOUT} s, or {DEFAULT_PIXI_TIMEOUT} s when "
            "`sandbox = 'pixi'` (cold conda solves are slow)."
        ),
    ).tag(config=True)

    debug = Bool(
        default_value=False,
        help=(
            "Enable marimo debug logging by passing "
            "'--log-level DEBUG' to the spawned process."
        ),
    ).tag(config=True)

    sandbox = Enum(
        ["uv", "pixi"],
        default_value="uv",
        allow_none=True,
        help=(
            "Sandbox backend for per-notebook environments from PEP 723 "
            "metadata. 'uv' is the default. 'pixi' creates conda script "
            "environments and requires pixi>=0.80 and marimo>=0.25.0. "
            "None disables sandboxing."
        ),
    ).tag(config=True)

    no_sandbox = Bool(
        default_value=False,
        allow_none=True,
        help=(
            "Deprecated alias for `sandbox = None`. "
            "Start marimo without sandboxing."
        ),
    ).tag(config=True)

    host = Unicode(
        allow_none=True,
        help=(
            "Host for marimo to bind to. Auto-detected from localhost "
            "resolution if not set; override to force a specific address."
        ),
    ).tag(config=True)

    watch = Bool(
        default_value=False,
        help=(
            "Watch notebook files for external changes and reload "
            "automatically. Useful when editing .py notebooks with an "
            "external editor."
        ),
    ).tag(config=True)

    allow_origins = List(
        Unicode(),
        help=(
            "Allowed origins for CORS. Can be set to ['*'] for all origins. "
            "Example: "
            "c.MarimoProxyConfig.allow_origins = ['https://marimo.io']"
        ),
    ).tag(config=True)

    skip_update_check = Bool(
        default_value=False,
        help=(
            "Don't check if a new version of marimo is available for download."
        ),
    ).tag(config=True)

    idle_timeout = Float(
        default_value=None,
        allow_none=True,
        help=(
            "Minutes of no connection before shutting down the marimo server. "
            "None (the default) means the server runs indefinitely."
        ),
    ).tag(config=True)

    session_ttl = Int(
        default_value=None,
        allow_none=True,
        help=(
            "Seconds to wait before closing a session on websocket "
            "disconnect. None (the default) keeps sessions open indefinitely."
        ),
    ).tag(config=True)

    transport = Unicode(
        "websocket",
        help=(
            "Kernel connection transport for marimo, sets the "
            "MARIMO_SERVER_TRANSPORT environment variable. Either 'websocket' "
            "(the default) or 'sse'. Use 'sse' for deployments behind a proxy "
            "that doesn't handle WebSockets, e.g. AWS SageMaker."
        ),
    ).tag(config=True)

    default_file = Unicode(
        allow_none=True,
        help=(
            "Path to a template file whose contents are used as the body of "
            "newly created notebooks (via POST /marimo-tools/create-stub). "
            "When set, the file is read once at extension load and cached "
            "for the lifetime of the Jupyter Server; restart the server to "
            "pick up changes. The contents are written verbatim; the "
            "extension does not parse or substitute __generated_with."
        ),
    ).tag(config=True)

    @validate("transport")
    def _validate_transport(self, proposal):
        value = proposal["value"]
        if value not in ("websocket", "sse"):
            raise TraitError(
                f"transport must be 'websocket' or 'sse', got {value!r}"
            )
        return value

    @default("host")
    def _default_host(self):
        return _detect_localhost_host()

    @default("marimo_path")
    def _default_marimo_path(self):
        return None

    @default("default_file")
    def _default_default_file(self):
        return None

    @default("uvx_path")
    def _default_uvx_path(self):
        # Derive uvx from $UV if set (standard uv environment variable)
        if uv_path := os.environ.get("UV"):
            return str(Path(uv_path).parent / "uvx")
        return None

    @default("pixi_path")
    def _default_pixi_path(self):
        return None

    @default("timeout")
    def _default_timeout(self):
        return DEFAULT_TIMEOUT

    def resolve_sandbox(self) -> SandboxBackend | None:
        """Effective sandbox backend after applying the `no_sandbox` alias.

        `no_sandbox = True` wins and yields None. A conflicting explicit
        `sandbox` value is reported with a warning rather than an error so
        existing `no_sandbox` deployments keep starting.
        """
        # Check before reading `sandbox`: traitlets materializes defaults
        # lazily, so an unread trait has a value only when it was set.
        sandbox_explicit = self.trait_has_value("sandbox")
        if not self.no_sandbox:
            return self.sandbox
        if sandbox_explicit and self.sandbox is not None:
            warnings.warn(
                "MarimoProxyConfig.no_sandbox=True overrides "
                f"MarimoProxyConfig.sandbox={self.sandbox!r}; marimo starts "
                "without a sandbox. no_sandbox is deprecated: set "
                "sandbox = None instead and drop no_sandbox.",
                stacklevel=2,
            )
        return None

    def resolve_timeout(self, sandbox: SandboxBackend | None) -> int:
        """Startup timeout, widened for pixi unless set explicitly."""
        if self.trait_has_value("timeout"):
            return self.timeout
        return DEFAULT_PIXI_TIMEOUT if sandbox == "pixi" else self.timeout


@dataclass(frozen=True)
class Config:
    """Resolved configuration (immutable snapshot)."""

    marimo_path: str | None  # Explicit marimo path
    uvx_path: str | None  # If set, use uvx mode
    timeout: int
    base_url: str
    debug: bool = False
    sandbox: SandboxBackend | None = "uv"  # None disables sandboxing
    pixi_path: str | None = None  # Explicit pixi path (sandbox="pixi")
    host: str | None = (
        None  # None = omit --host flag, let marimo use its default
    )
    watch: bool = False
    allow_origins: tuple[str, ...] = ()
    skip_update_check: bool = False
    idle_timeout: float | None = None
    session_ttl: int | None = None
    transport: str = "websocket"
    default_file: str | None = None

    @property
    def no_sandbox(self) -> bool:
        """True when marimo runs without any sandbox backend."""
        return self.sandbox is None


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

    sandbox = cfg.resolve_sandbox()
    return Config(
        marimo_path=cfg.marimo_path,
        uvx_path=cfg.uvx_path,
        timeout=cfg.resolve_timeout(sandbox),
        base_url=_get_base_url(),
        debug=bool(cfg.debug),
        sandbox=sandbox,
        pixi_path=cfg.pixi_path,
        host=cfg.host,
        watch=bool(cfg.watch),
        allow_origins=tuple(cfg.allow_origins),
        skip_update_check=bool(cfg.skip_update_check),
        idle_timeout=cfg.idle_timeout,
        session_ttl=cfg.session_ttl,
        transport=cfg.transport,
        default_file=cfg.default_file,
    )


def _get_base_url() -> str:
    """Get base URL, gracefully handling non-JupyterHub environments."""
    prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
    return url_path_join(prefix, "marimo")
