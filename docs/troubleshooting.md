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

### Large cell outputs hang or never render

Two caps in series: marimo's `runtime.output_max_bytes` (default 8 MB) and tornado's websocket frame cap (default 10 MiB). Big plotly figures or DataFrames blow past 10 MiB and get dropped silently — the cell just hangs.

Raise marimo's side via PEP 723 script header, `~/.config/marimo/marimo.toml`, or `MARIMO_OUTPUT_MAX_BYTES` (on JupyterHub set it in `c.Spawner.environment`). Raise tornado's side via:

```python
c.ServerApp.tornado_settings = {
    "websocket_max_message_size": 256 * 1024 * 1024
}
```

Run `marimo config show` in a JupyterHub terminal to verify marimo's effective config.

### Marimo fails to connect behind a proxy (e.g. AWS SageMaker)

**Cause**: Some proxies (notably AWS SageMaker) don't forward WebSocket
connections, which marimo uses for its kernel by default. The notebook loads but
never connects, often failing silently.

**Solution**: Switch marimo to the Server-Sent Events (SSE) transport, which
works over plain HTTP. This sets `MARIMO_SERVER_TRANSPORT=sse` on the marimo
process:

```python
c.MarimoProxyConfig.transport = "sse"
```

Add it to `jupyterhub_config.py` (JupyterHub) or `jupyter_server_config.py`
(standalone JupyterLab); or pass `--MarimoProxyConfig.transport=sse` as a CLI
flag. The default is `websocket`, which is preferred wherever WebSockets work.

> **Note**: SSE transport requires `marimo>=0.23.14`.

### Error: "No such option: --base-url"

**Cause**: marimo version is too old.

**Solution**: Upgrade to marimo 0.23.14 or newer:

```bash
pip install 'marimo>=0.23.14'
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
