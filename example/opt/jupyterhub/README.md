# JupyterHub Installation Directory

This directory contains the JupyterHub installation and configuration.

## Contents

| File | Purpose |
|------|---------|
| `jupyterhub_config.py` | JupyterHub configuration (OAuth, spawner, environment) |
| `nginx.conf` | Reverse proxy with WebSocket and SSL support |
| `jupyterhub.service` | systemd service unit file |
| `pyproject.toml` | Python dependencies for uv |
| `package.json` | Node.js dependencies (configurable-http-proxy) |

## Setup

```bash
# As jupyterhub user
cd /opt/jupyterhub
uv init
uv sync
npm install
```

## Directory Structure (after setup)

```
/opt/jupyterhub/
├── .venv/                    # Python virtual environment
├── node_modules/             # Node.js dependencies
├── jupyterhub_config.py
├── nginx.conf
├── jupyterhub.service
├── pyproject.toml
├── package.json
└── uv.lock                   # Generated lock file
```

## Ownership

```bash
chown -R jupyterhub:jupyterhub /opt/jupyterhub
```
