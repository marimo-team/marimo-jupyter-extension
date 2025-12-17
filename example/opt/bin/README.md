# Shared Executables Directory

This directory contains executables that should be accessible to spawned notebook processes.

## Use Case

When marimo is installed in JupyterHub's virtualenv but needs to be accessible to spawned notebook servers running as a different user, you can symlink it here.

```bash
# As root
ln -s /opt/jupyterhub/.venv/bin/marimo /opt/bin/marimo
```

## Configuration

Ensure `/opt/bin` is in the spawner's PATH:

```python
c.SystemdSpawner.environment = {
    "PATH": "/opt/bin:/opt/jupyterhub/.venv/bin:/usr/local/bin:/usr/bin:/bin",
    # ...
}
```

## Alternative Approaches

1. **PATH configuration**: Add the venv bin directly to PATH (simpler)
2. **Environment variable**: Set `JUPYTERMARIMOPROXY_PATH`
3. **Config file**: Use `~/.jupytermarimoproxyrc`

See [Configuration](../../../docs/configuration.md) for details.
