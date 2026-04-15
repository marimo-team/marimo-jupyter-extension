<p align="center">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg" width="400px">
</p>

<p align="center">
  <em>Seamlessly integrate marimo notebooks into JupyterLab and JupyterHub</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/marimo-jupyter-extension/"><img src="https://img.shields.io/pypi/v/marimo-jupyter-extension?color=%2334D058&label=pypi" alt="PyPI"/></a>
  <a href="https://github.com/marimo-team/marimo-jupyter-extension/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/marimo-jupyter-extension" alt="License"/></a>
  <a href="https://marimo.io/discord?ref=readme"><img src="https://shields.io/discord/1059888774789730424" alt="Discord"/></a>
</p>

---

**marimo-jupyter-extension** brings the power of [marimo](https://marimo.io/) reactive notebooks to your existing Jupyter infrastructure. Launch marimo directly from JupyterLab's launcher, manage running sessions, and convert Jupyter notebooks to marimo format.

**Highlights**

- 🚀 **Launcher Integration** - marimo appears in the JupyterLab launcher with its own icon
- 🍃 **First-Class Marimo Notebook Support** - Double-click `_mo.py` files to open directly in marimo
- 📊 **Sidebar Panel** - Monitor server status, view running sessions, and quick actions
- 🐍 **Venv Selection** - Choose Python environment when creating new notebooks (with PEP 723 metadata)
- 📁 **Context Menus** - Right-click `.py` files to edit with marimo, `.ipynb` files to convert
- 🏢 **JupyterHub Compatible** - Works with existing authenticators and spawners
- 🔒 **Secure** - Token-based authentication between proxy and marimo
- 📦 **Sandbox Mode** - Run marimo in isolated environments with uvx

## Quick Start

```bash
uv pip install 'marimo[sandbox]>=0.23.1' marimo-jupyter-extension
```

Launch JupyterLab and click the marimo icon in the launcher, or use the sidebar panel.

## Features

### Launcher & Sidebar

Create new marimo notebooks from the launcher. The sidebar shows server status, running sessions with kill buttons, and quick actions.

<p align="center">
  <img src="screenshot.png" width="800px" alt="marimo extension sidebar and editor">
  <br>
  <em>Joy Division-style plot from pulsar CP 1919 (PSR B1919+21) made with <a href="https://github.com/koaning/wigglystuff">wigglystuff</a></em>
</p>

### Environment Selection

When creating a new notebook, select from available Python environments. The extension discovers Jupyter kernel specs and embeds the venv path using PEP 723 script metadata.

### File Type Handling

| File Type | Double-click Behavior | "Open With" Menu |
|-----------|----------------------|------------------|
| `_mo.py`  | Opens in marimo      | marimo available |
| `.py`     | Opens in standard editor | marimo available |

### Context Menu Actions

- **Edit with marimo**: Right-click any `.py` or `_mo.py` file to open it in the marimo editor
- **Convert to marimo**: Right-click any `.ipynb` file to convert it to marimo format

## Installation

See [Installation Guide](https://marimo-team.github.io/marimo-jupyter-extension/installation/) for detailed setup instructions.

### Single Environment

```bash
uv pip install 'marimo[sandbox]>=0.23.1' marimo-jupyter-extension
```

### Multiple Environments (JupyterHub)

| Package | Install Location | Why |
|---------|------------------|-----|
| `marimo` | User's environment | Access user's packages |
| `marimo-jupyter-extension` | Jupyter's environment | Jupyter must import it |

## Configuration

Configure in `jupyterhub_config.py`:

```python
# Explicit marimo path
c.MarimoProxyConfig.marimo_path = "/opt/bin/marimo"

# Or use uvx mode (sandbox)
c.MarimoProxyConfig.uvx_path = "/usr/local/bin/uvx"

# Startup timeout (default: 60s)
c.MarimoProxyConfig.timeout = 120

# Enable marimo debug logging for spawn troubleshooting
c.MarimoProxyConfig.debug = True

# Watch files for external edits (Claude Code, Cursor, vim, etc.)
c.MarimoProxyConfig.watch = True

# Allowed CORS origins (default: same-origin only)
c.MarimoProxyConfig.allow_origins = ["*"]

# Suppress version-check network call on startup
c.MarimoProxyConfig.skip_update_check = True

# Shut down after N minutes of no browser connection
c.MarimoProxyConfig.idle_timeout = 30.0

# Keep sessions alive N seconds after websocket disconnect
c.MarimoProxyConfig.session_ttl = 300
```

See [Configuration Guide](https://marimo-team.github.io/marimo-jupyter-extension/configuration/), [Troubleshooting Guide](https://marimo-team.github.io/marimo-jupyter-extension/troubleshooting/), and [JupyterHub Deployment](https://marimo-team.github.io/marimo-jupyter-extension/jupyterhub/) for more details.

## Migrating from jupyter-marimo-proxy

```bash
pip uninstall jupyter-marimo-proxy
pip install marimo-jupyter-extension
```

Configuration via `c.MarimoProxyConfig` in `jupyterhub_config.py` remains the same. This package is a drop-in replacement with additional features.

## Attribution

This project is based on [jupyter-marimo-proxy](https://github.com/jyio/jupyter-marimo-proxy) by **Jiang Yio**, which provided the original server proxy implementation.

Additional inspiration from [b-data/jupyter-marimo-proxy](https://github.com/b-data/jupyter-marimo-proxy).

This fork adds:
- Full JupyterLab extension with sidebar UI
- Venv/kernel selection with PEP 723 metadata
- Context menu integration for file operations
- Notebook conversion support
- Server restart capabilities

## Troubleshooting

See [Troubleshooting Guide](https://marimo-team.github.io/marimo-jupyter-extension/troubleshooting/) for common issues.

| Issue | Solution |
|-------|----------|
| marimo icon missing | Install `marimo-jupyter-extension` in Jupyter's environment |
| marimo fails to launch | Ensure marimo is in PATH or configure `MarimoProxyConfig.marimo_path` |
| Modules not found | Install marimo in the same environment as your packages |
| Sandbox features not working | Upgrade to `marimo[sandbox]>=0.23.1` |

## Community

- [marimo Discord](https://marimo.io/discord?ref=readme) - Chat with the community
- [GitHub Issues](https://github.com/marimo-team/marimo-jupyter-extension/issues) - Report bugs or request features
- [marimo Documentation](https://docs.marimo.io) - Learn about marimo notebooks
- [Contributing Guidelines](https://github.com/marimo-team/marimo/blob/main/CONTRIBUTING.md) - Help improve marimo

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE) for details.
