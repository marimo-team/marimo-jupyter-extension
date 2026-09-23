"""Jupyter extension to proxy Marimo.

This module provides the setup function for jupyter-server-proxy to launch
marimo.
"""

import base64
import os
import secrets
import shutil

from .config import Config, SandboxBackend, get_config
from .executable import get_marimo_command, get_pixi_path

__version__ = "0.4.0"
__all__ = ["setup_marimoserver"]


def setup_marimoserver():
    """Setup function for jupyter-server-proxy.

    Returns a configuration dictionary that jupyter-server-proxy uses to
    launch and proxy marimo.
    """
    token = secrets.token_urlsafe(16)
    config = get_config()

    # Get marimo command based on config
    marimo_cmd = get_marimo_command(config)

    return {
        "command": [
            *marimo_cmd,
            *(["--log-level", "DEBUG"] if config.debug else []),
            "edit",
            *_sandbox_args(config.sandbox),
            "--port",
            "{port}",
            *(["--host", config.host] if config.host is not None else []),
            "--base-url",
            config.base_url,
            "--token",
            "--token-password",
            token,
            "--headless",
            "--no-skew-protection",
            *(["--watch"] if config.watch else []),
            *[
                arg
                for o in config.allow_origins
                for arg in ("--allow-origins", o)
            ],
            *(["--skip-update-check"] if config.skip_update_check else []),
            *(
                ["--timeout", str(config.idle_timeout)]
                if config.idle_timeout is not None
                else []
            ),
            *(
                ["--session-ttl", str(config.session_ttl)]
                if config.session_ttl is not None
                else []
            ),
        ],
        "environment": _environment(config),
        "timeout": config.timeout,
        "absolute_url": True,
        "request_headers_override": {
            "Authorization": "Basic "
            + base64.b64encode(b" :" + token.encode()).decode()
        },
        "launcher_entry": {
            "icon_path": os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "icon.svg"
            ),
            # Disabled - our labextension provides the launcher
            "enabled": False,
        },
    }


def _sandbox_args(sandbox: SandboxBackend | None) -> list[str]:
    """CLI arguments selecting marimo's sandbox backend.

    The uv backend is spelled as a bare `--sandbox`, which marimo releases
    without a backend choice (<= 0.23.x) accept and newer releases normalize
    to `--sandbox=uv`. pixi uses the `=` form: `--sandbox pixi` would be
    ambiguous with the positional notebook NAME argument.
    """
    if sandbox is None:
        return []
    if sandbox == "uv":
        return ["--sandbox"]
    return [f"--sandbox={sandbox}"]


def _environment(config: Config) -> dict[str, str]:
    """Extra environment for the spawned marimo process.

    jupyter-server-proxy merges this into a copy of the server's environment.
    """
    environment = {"MARIMO_SERVER_TRANSPORT": config.transport}
    if config.sandbox != "pixi":
        return environment

    # marimo locates pixi with shutil.which("pixi"), so a binary found via
    # pixi_path or a common install location must be made visible on PATH.
    pixi = get_pixi_path(config)
    if shutil.which("pixi") != pixi:
        environment["PATH"] = os.pathsep.join(
            p for p in (os.path.dirname(pixi), os.environ.get("PATH", "")) if p
        )
    return environment
