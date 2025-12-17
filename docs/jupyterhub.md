# JupyterHub Deployment

This guide covers deploying JupyterHub with marimo support on Ubuntu/Debian using uv and systemd.

For comprehensive JupyterHub documentation, see the [official tutorial](https://jupyterhub.readthedocs.io/en/stable/tutorial/quickstart.html).

## Prerequisites

- Fresh Ubuntu/Debian server with root access
- A domain name pointing to your server

!!! tip "Quick DNS"
    [sslip.io](https://sslip.io) provides free DNS that maps `<IP>.sslip.io` to your IP, useful for SSL certificates without a domain.

## Part 1: System Setup

### Install Dependencies

```bash
sudo su
apt update
apt install -y nodejs npm nginx certbot python3-certbot-nginx
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Create System Users

```bash
# jupyterhub: Runs the hub process (control plane)
useradd -r -m -s /bin/bash jupyterhub

# jupyter: Runs spawned notebook servers (user workloads)
useradd -r -s /usr/sbin/nologin jupyter
```

### Create Directories

```bash
mkdir -p /opt/jupyterhub /opt/notebooks /opt/bin
chown jupyterhub:jupyterhub /opt/jupyterhub
chown jupyter:jupyter /opt/notebooks
```

## Part 2: JupyterHub Installation

As the jupyterhub user:

```bash
su - jupyterhub
cd /opt/jupyterhub
uv init
```

Edit `pyproject.toml`:

```toml
[project]
name = "jupyterhub-deployment"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "jupyterhub>=5.4.3",
    "jupyterlab>=4.5.1",
    "notebook>=7.5.0",
    "oauthenticator>=17.3.0",
    "jupyterhub-systemdspawner>=1.0.2",
    "marimo>=0.18.4",
    "jupyter-marimo-proxy>=0.0.4",
]
```

```bash
uv sync
npm init -y && npm install configurable-http-proxy
```

### GitHub OAuth Setup

1. Go to GitHub → Settings → Developer settings → OAuth Apps → New OAuth App
2. Set callback URL to `https://your-domain.com/hub/oauth_callback`
3. Note your Client ID and Client Secret

### JupyterHub Configuration

Create `jupyterhub_config.py`:

```python
import os
from oauthenticator.github import GitHubOAuthenticator

# Authentication
c.JupyterHub.authenticator_class = GitHubOAuthenticator
c.GitHubOAuthenticator.client_id = os.environ.get("GITHUB_CLIENT_ID")
c.GitHubOAuthenticator.client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
c.GitHubOAuthenticator.oauth_callback_url = os.environ.get("OAUTH_CALLBACK_URL")
c.GitHubOAuthenticator.allowed_users = {"your-github-username"}
c.GitHubOAuthenticator.scope = ["read:org"]

# Spawner
c.JupyterHub.spawner_class = "systemdspawner.SystemdSpawner"
c.SystemdSpawner.user = "jupyter"
c.SystemdSpawner.username_template = "jupyter"
c.SystemdSpawner.user_workingdir = "/opt/notebooks/{USERNAME}"

# HTTP Proxy
c.ConfigurableHTTPProxy.command = "/opt/jupyterhub/node_modules/configurable-http-proxy/bin/configurable-http-proxy"

# Spawned notebook environment
c.SystemdSpawner.environment = {
    "PATH": "/opt/jupyterhub/.venv/bin:/opt/bin:/usr/local/bin:/usr/bin:/bin",
    "XDG_RUNTIME_DIR": "/run/user/jupyter",
    "XDG_DATA_HOME": "/opt/notebooks/.local/share",
    "XDG_CONFIG_HOME": "/opt/notebooks/.config",
    "XDG_CACHE_HOME": "/opt/notebooks/.cache",
    "HOME": "/opt/notebooks",
}
```

## Part 3: SSL & Reverse Proxy

### nginx Configuration

Create `/opt/jupyterhub/nginx.conf`:

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
    }
}
```

As root:

```bash
ln -sf /opt/jupyterhub/nginx.conf /etc/nginx/sites-enabled/jupyterhub
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
certbot --nginx -d your-domain.com --non-interactive --agree-tos -m your@email.com
echo "0 0 * * * root certbot renew --quiet" > /etc/cron.d/certbot-renew
```

## Part 4: systemd Service

Create `/etc/systemd/system/jupyterhub.service`:

```ini
[Unit]
Description=JupyterHub
After=syslog.target network.target

[Service]
User=jupyterhub
WorkingDirectory=/opt/jupyterhub

Environment="GITHUB_CLIENT_ID=your-client-id"
Environment="GITHUB_CLIENT_SECRET=your-client-secret"
Environment="OAUTH_CALLBACK_URL=https://your-domain.com/hub/oauth_callback"

ExecStart=/opt/jupyterhub/.venv/bin/jupyterhub -f /opt/jupyterhub/jupyterhub_config.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable jupyterhub
systemctl start jupyterhub
```

## Verification

```bash
systemctl status jupyterhub
journalctl -u jupyterhub -f
```

Visit `https://your-domain.com` and authenticate with GitHub.

## Using marimo

1. Log into JupyterHub
2. Start your server
3. Click the marimo icon in the JupyterLab launcher, or navigate to `/user/<username>/marimo/`

marimo notebooks are stored in the user's working directory (`/opt/notebooks/<username>/`).
