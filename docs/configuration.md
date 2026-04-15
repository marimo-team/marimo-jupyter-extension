# Configuration

## Executable Discovery

By default, the extension searches for `marimo` in:

1. System PATH (via `shutil.which`)
2. Common locations: `~/.local/bin/marimo`, `/opt/bin/marimo`, `/usr/local/bin/marimo`

## Standalone JupyterLab

If you launched JupyterLab directly from a venv (not via JupyterHub), you configure the extension either via a CLI argument or a config file — there is no `jupyterhub_config.py`.

**One-time (CLI argument)**

Pass any `MarimoProxyConfig` option as a flag when starting JupyterLab:

```bash
jupyter lab --MarimoProxyConfig.no_sandbox=True
```

**Permanent (jupyter_server_config.py)**

Find your Jupyter config directory:

```bash
jupyter --config-dir
```

Create or edit `jupyter_server_config.py` in that directory using the same traitlets syntax as below. For example:

```python
c.MarimoProxyConfig.no_sandbox = True
```

## Traitlets Configuration (JupyterHub)

For JupyterHub deployments, configure the extension in `jupyterhub_config.py`:

```python
from marimo_jupyter_extension.config import MarimoProxyConfig

# Explicit marimo path
c.MarimoProxyConfig.marimo_path = "/opt/bin/marimo"

# Or use uvx mode (runs `uvx marimo` instead)
c.MarimoProxyConfig.uvx_path = "/usr/local/bin/uvx"

# Do not use marimo sandboxing
# When True, disables --sandbox and skips venv picker (venv selection requires sandbox)
# WARNING: Consider setting up a virtual environment instead of using this flag.
# Sandbox mode enables per-notebook dependency management and venv selection.
c.MarimoProxyConfig.no_sandbox = False

# Startup timeout in seconds (default: 60)
c.MarimoProxyConfig.timeout = 120

# Enable marimo debug logging for spawn troubleshooting.
# This adds the global marimo CLI flag `--log-level DEBUG`.
c.MarimoProxyConfig.debug = True

# Watch notebook files for external changes and reload automatically.
# Useful when editing .py notebooks with Claude Code, Cursor, vim, or other
# external editors while the notebook is open in the browser (default: False).
c.MarimoProxyConfig.watch = True

# Allowed origins for CORS (default: [] — same-origin only).
# Set to ["*"] to allow all origins, or list specific origins.
c.MarimoProxyConfig.allow_origins = ["https://example.com"]

# Suppress the marimo version-check network call on startup (default: False).
c.MarimoProxyConfig.skip_update_check = True

# Minutes of no browser connection before marimo shuts itself down.
# None (the default) keeps the server running indefinitely.
c.MarimoProxyConfig.idle_timeout = 30.0

# Seconds to keep a session alive after a websocket disconnect.
# None (the default) keeps sessions open indefinitely.
c.MarimoProxyConfig.session_ttl = 300
```

## Spawner Environment

For JupyterHub deployments using SystemdSpawner, configure the spawned notebook environment:

```python
c.SystemdSpawner.environment = {
    "PATH": "/opt/jupyterhub/.venv/bin:/usr/local/bin:/usr/bin:/bin",
    "XDG_RUNTIME_DIR": "/run/user/jupyter",
    "XDG_DATA_HOME": "/opt/notebooks/.local/share",
    "XDG_CONFIG_HOME": "/opt/notebooks/.config",
    "XDG_CACHE_HOME": "/opt/notebooks/.cache",
    "HOME": "/opt/notebooks",
}
```

## Alternative: Symlink marimo

Instead of explicit path configuration, copy or symlink marimo to a location already in the spawner's PATH:

```bash
# As root
ln -s /opt/jupyterhub/.venv/bin/marimo /opt/bin/marimo
```

This works if `/opt/bin` is already in the spawner's PATH.
