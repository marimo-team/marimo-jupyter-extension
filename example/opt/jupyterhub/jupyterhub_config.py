import os

from oauthenticator.github import GitHubOAuthenticator

# Get the JupyterHub Traitlets configuration object
# This is injected by JupyterHub when loading this file
c = get_config()  # noqa: F821

# =============================================================================
# Authentication
# =============================================================================
c.JupyterHub.authenticator_class = GitHubOAuthenticator
c.GitHubOAuthenticator.client_id = os.environ.get("GITHUB_CLIENT_ID")
c.GitHubOAuthenticator.client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
c.GitHubOAuthenticator.oauth_callback_url = os.environ.get(
    "OAUTH_CALLBACK_URL"
)
c.GitHubOAuthenticator.allowed_users = {"your-github-username"}
c.GitHubOAuthenticator.scope = ["read:org"]
# c.GitHubOAuthenticator.allowed_orgs = {"your-org"}

# =============================================================================
# Spawner
# =============================================================================
c.JupyterHub.spawner_class = "systemdspawner.SystemdSpawner"

# All notebooks run as 'jupyter' user - no isolation between users.
# For isolation, use dynamic user creation or container-based spawners.
c.SystemdSpawner.user = "jupyter"
c.SystemdSpawner.username_template = "jupyter"
c.SystemdSpawner.user_workingdir = "/opt/notebooks/{USERNAME}"

# c.SystemdSpawner.mem_limit = "2G"
# c.SystemdSpawner.cpu_limit = 1.0

# =============================================================================
# HTTP Proxy
# =============================================================================
c.ConfigurableHTTPProxy.command = (
    "/opt/jupyterhub/node_modules/configurable-http-proxy"
    "/bin/configurable-http-proxy"
)

# =============================================================================
# Spawned notebook environment
# =============================================================================
c.SystemdSpawner.environment = {
    "PATH": "/opt/jupyterhub/.venv/bin:/opt/bin:/usr/local/bin:/usr/bin:/bin",
    "XDG_RUNTIME_DIR": "/run/user/jupyter",
    "XDG_DATA_HOME": "/opt/notebooks/.local/share",
    "XDG_CONFIG_HOME": "/opt/notebooks/.config",
    "XDG_CACHE_HOME": "/opt/notebooks/.cache",
    "HOME": "/opt/notebooks",
}
