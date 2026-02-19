# Configuration

## Executable Discovery

By default, the extension searches for `marimo` in:

1. System PATH (via `shutil.which`)
2. Common locations: `~/.local/bin/marimo`, `/opt/bin/marimo`, `/usr/local/bin/marimo`

## Traitlets Configuration

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
