"""Jupyter extension to proxy Marimo.

This module provides the setup function for jupyter-server-proxy to launch
marimo.
"""

import base64
import os
import secrets

from .config import get_config
from .executable import get_marimo_command

__version__ = "0.1.0"
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
            "edit",
            "--sandbox",
            "--port",
            "{port}",
            "--base-url",
            config.base_url,
            "--token",
            "--token-password",
            token,
            "--headless",
            "--no-skew-protection",
        ],
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
