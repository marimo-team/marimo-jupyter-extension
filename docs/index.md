# marimo-jupyter-extension

Jupyter extension that enables launching [marimo](https://marimo.io/) from JupyterLab and JupyterHub.

## What is this?

`marimo-jupyter-extension` integrates marimo into your Jupyter environment using [jupyter-server-proxy](https://jupyter-server-proxy.readthedocs.io/). It adds a marimo launcher to the JupyterLab interface, allowing users to start marimo notebooks without leaving their Jupyter environment.

On JupyterHub deployments, this leverages existing authentication and spawning infrastructure—no separate marimo deployment needed.

## Quick Start

```bash
pip install 'marimo>=0.19.8' marimo-jupyter-extension
```

Launch JupyterLab and click the marimo icon in the launcher.

## Features

- **JupyterLab Integration**: marimo appears in the launcher with its own icon
- **First-Class Marimo Notebook Support**: `_mo.py` files are recognized as Marimo notebooks and open in marimo by default on double-click
- **Sidebar Panel**: Server status, running sessions, and quick actions
- **Venv Selection**: Choose Python environment when creating new notebooks
- **Context Menus**: Right-click to edit .py files or convert .ipynb files
- **JupyterHub Support**: Works with existing authenticators and spawners
- **Secure**: Token-based authentication between proxy and marimo
- **Sandbox Mode**: Run marimo in isolated environments with uvx
- **Flexible PATH**: Configure executable search paths via environment variables or config files

## File Type Handling

| File Type | Double-click Behavior | "Open With" Menu |
|-----------|----------------------|------------------|
| `_mo.py`  | Opens in marimo      | marimo available |
| `.py`     | Opens in standard editor | marimo available |

## Next Steps

- [Installation](installation.md) - Detailed setup instructions
- [Configuration](configuration.md) - PATH and environment configuration
- [JupyterHub Deployment](jupyterhub.md) - Multi-user deployment guide
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
