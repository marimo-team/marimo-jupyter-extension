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

### Error: "No such option: --base-url"

**Cause**: marimo version is too old.

**Solution**: Upgrade to marimo 0.19.4 or newer:

```bash
pip install 'marimo>=0.19.4'
```

### JupyterHub Issues

| Issue | Solution |
|-------|----------|
| Service won't start | Check logs: `journalctl -u jupyterhub -e` |
| OAuth errors | Verify callback URL matches between GitHub and config |
| Permission denied | Ensure `/opt/jupyterhub` is owned by `jupyterhub` user |
| Proxy 502 errors | Check `journalctl -u jupyterhub` for marimo startup errors |

### Debug Mode

To see detailed proxy logs, check the JupyterHub logs:

```bash
journalctl -u jupyterhub -f
```

Or for local JupyterLab:

```bash
jupyter lab --debug
```
