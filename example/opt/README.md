# Example Deployment Structure

This directory mirrors a typical JupyterHub deployment on `/opt/`.

```
/opt/
├── jupyterhub/       # JupyterHub installation
│   ├── .venv/        # Python virtual environment (uv)
│   ├── jupyterhub_config.py
│   ├── nginx.conf
│   └── jupyterhub.service
├── notebooks/        # User notebook storage
│   └── {USERNAME}/   # Per-user directories
└── bin/              # Shared executables
    └── marimo        # Symlink to .venv/bin/marimo
```

## Directory Purposes

| Directory | Owner | Purpose |
|-----------|-------|---------|
| `/opt/jupyterhub` | `jupyterhub` | Hub installation, configs, venv |
| `/opt/notebooks` | `jupyter` | User data, spawned notebook working dirs |
| `/opt/bin` | `root` | Shared executables accessible to spawned processes |

## Users

| User | Purpose |
|------|---------|
| `jupyterhub` | Runs the hub process (control plane) |
| `jupyter` | Runs spawned notebook servers (all users share this) |

For user isolation, consider per-user system accounts or container-based spawners.
