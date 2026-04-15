# Troubleshooting

## Common Issues

### Marimo icon does not appear in the launcher

**Cause**: `marimo-jupyter-extension` is not installed in the same Python environment as Jupyter.

**Solution**: Install the proxy in Jupyter's environment:

```bash
# Find where Jupyter is installed
which jupyter

# Install proxy in that environment
/path/to/jupyter/bin/pip install marimo-jupyter-extension
```

### Marimo icon appears but fails to launch

**Cause**: marimo executable is not in the search path.

**Solution**: Ensure marimo is accessible via one of these methods:

1. Add to PATH in spawner environment:
   ```python
   c.SystemdSpawner.environment = {
       "PATH": "/path/to/marimo/bin:$PATH",
   }
   ```

2. Configure explicit path in `jupyterhub_config.py`:
   ```python
   c.MarimoProxyConfig.marimo_path = "/path/to/marimo"
   ```

### Marimo cannot find installed modules

**Cause**: marimo is installed in a different Python environment than the modules.

**Solution**: Install marimo in the same environment as your packages:

```bash
# If modules are in conda environment
/opt/conda/bin/pip install marimo

# If modules are in a virtualenv
/path/to/venv/bin/pip install marimo
```

### Packages work outside marimo but fail inside (sandbox incompatibility)

**Cause**: marimo runs in sandbox mode by default, which creates an isolated temporary venv per notebook. Native libraries, ADBC drivers, and packages already installed in your project venv are not visible inside the sandbox.

**Solution**: Disable sandbox mode.

For standalone JupyterLab (no JupyterHub), pass a CLI flag when launching:

```bash
jupyter lab --MarimoProxyConfig.no_sandbox=True
```

Or add it permanently to `jupyter_server_config.py` (run `jupyter --config-dir` to locate it):

```python
c.MarimoProxyConfig.no_sandbox = True
```

For JupyterHub, add the same line to `jupyterhub_config.py`.

> **Note**: Disabling sandbox mode removes per-notebook dependency management and the venv picker. Consider setting up a shared virtual environment instead if you need dependency isolation.

### Cannot find jupyterhub_config.py

**Cause**: `jupyterhub_config.py` only exists in JupyterHub deployments. If you launched JupyterLab directly from a venv, this file does not exist on your system.

**Solution**: Use the [Standalone JupyterLab](configuration.md#standalone-jupyterlab) configuration approach instead — either a CLI flag or `jupyter_server_config.py`.

### Error: "No such option: --base-url"

**Cause**: marimo version is too old.

**Solution**: Upgrade to marimo 0.23.1 or newer:

```bash
pip install 'marimo>=0.23.1'
```

### JupyterHub Issues

| Issue | Solution |
|-------|----------|
| Service won't start | Check logs: `journalctl -u jupyterhub -e` |
| OAuth errors | Verify callback URL matches between GitHub and config |
| Permission denied | Ensure `/opt/jupyterhub` is owned by `jupyterhub` user |
| Proxy 502 errors | Check `journalctl -u jupyterhub` for marimo startup errors |

### Debug Mode

To diagnose marimo launch failures, enable debug logging so spawned marimo processes run with `--log-level DEBUG`.

For standalone JupyterLab, pass it as a CLI flag:

```bash
jupyter lab --MarimoProxyConfig.debug=True
```

Or add it to `jupyter_server_config.py` (run `jupyter --config-dir` to locate it):

```python
c.MarimoProxyConfig.debug = True
```

For JupyterHub, add the same line to `jupyterhub_config.py`.

This is the recommended way to troubleshoot both initial launch failures and
restart-triggered respawn failures. The restart endpoint only clears the old
process; any actual failure happens on the next marimo spawn attempt and will
show up in the logs.

For JupyterHub, check the service logs while reproducing the issue:

```bash
journalctl -u jupyterhub -f
```

For local JupyterLab, start Jupyter with debug logging enabled:

```bash
jupyter lab --debug
```
