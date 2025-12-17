# Configuration

## Executable Search Path

When marimo is installed in a different location than Jupyter, you need to configure the search path so the proxy can find it.

### Option 1: Environment Variable

Set `JUPYTERMARIMOPROXY_PATH` to include the path to marimo:

```bash
export JUPYTERMARIMOPROXY_PATH="~/.local/bin:~/bin:$PATH"
```

!!! note "JupyterHub Configuration"
    When using JupyterHub, add `JUPYTERMARIMOPROXY_PATH` to the spawner's preserved environment variables:

    ```python
    c.Spawner.env_keep.append('JUPYTERMARIMOPROXY_PATH')
    ```

### Option 2: Configuration File

Create `~/.jupytermarimoproxyrc`:

```ini
[DEFAULT]
path = ~/.local/bin:~/bin:$PATH
```

Or with a section name:

```ini
[jupyter-marimo-proxy]
path = /opt/conda/bin:/usr/local/bin:$PATH
```

### Path Expansion

Both methods support:

- Home directory expansion: `~` → `/home/username`
- Environment variable expansion: `$PATH`, `$HOME`
- Path deduplication (duplicate entries removed)
- Validation (non-existent paths removed)

### Precedence

1. `JUPYTERMARIMOPROXY_PATH` environment variable (highest)
2. `~/.jupytermarimoproxyrc` config file
3. System PATH (default)

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

Instead of PATH configuration, copy or symlink marimo to a location already in the spawner's PATH:

```bash
# As root
ln -s /opt/jupyterhub/.venv/bin/marimo /opt/bin/marimo
```

This works if `/opt/bin` is already in the spawner's PATH.
