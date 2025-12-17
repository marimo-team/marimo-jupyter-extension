# User Notebooks Directory

This directory stores user data and serves as the working directory for spawned notebook servers.

## Structure

```
/opt/notebooks/
├── {USERNAME}/           # Per-user directory
│   ├── *.py              # marimo notebooks
│   └── *.ipynb           # Jupyter notebooks
├── .local/share/         # Shared XDG data
├── .config/              # Shared XDG config
└── .cache/               # Shared XDG cache
```

## Configuration

Set in `jupyterhub_config.py`:

```python
c.SystemdSpawner.user_workingdir = "/opt/notebooks/{USERNAME}"
c.SystemdSpawner.environment = {
    "HOME": "/opt/notebooks",
    "XDG_DATA_HOME": "/opt/notebooks/.local/share",
    "XDG_CONFIG_HOME": "/opt/notebooks/.config",
    "XDG_CACHE_HOME": "/opt/notebooks/.cache",
}
```

## Ownership

```bash
chown -R jupyter:jupyter /opt/notebooks
```

## Note on Isolation

This single-user setup provides no isolation between users. All spawned processes run as the `jupyter` user with shared storage.

For multi-tenant deployments, consider:
- Per-user system accounts with SystemdSpawner
- Container-based spawners (DockerSpawner, KubeSpawner)
