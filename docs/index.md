# marimo-jupyter-extension

Jupyter extension that enables launching [marimo](https://marimo.io/) from JupyterLab and JupyterHub.

## What is this?

`marimo-jupyter-extension` integrates marimo into your Jupyter environment using [jupyter-server-proxy](https://jupyter-server-proxy.readthedocs.io/). It adds a marimo launcher to the JupyterLab interface, allowing users to start marimo notebooks without leaving their Jupyter environment.

On JupyterHub deployments, this leverages existing authentication and spawning infrastructure—no separate marimo deployment needed.

## Quick Start

```bash
pip install 'marimo>=0.19.4' marimo-jupyter-extension
```

Launch JupyterLab and click the marimo icon in the launcher.

## Features

- **JupyterLab Integration**: marimo appears in the launcher with its own icon
- **Sidebar Panel**: Server status, running sessions, and quick actions
- **Venv Selection**: Choose Python environment when creating new notebooks
- **Context Menus**: Right-click to edit .py files or convert .ipynb files
- **JupyterHub Support**: Works with existing authenticators and spawners
- **Secure**: Token-based authentication between proxy and marimo
- **Sandbox Mode**: Run marimo in isolated environments with uvx
- **Flexible PATH**: Configure executable search paths via environment variables or config files

## Next Steps

- [Installation](installation.md) - Detailed setup instructions
- [Configuration](configuration.md) - PATH and environment configuration
- [JupyterHub Deployment](jupyterhub.md) - Multi-user deployment guide
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
