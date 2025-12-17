# Installation

## Requirements

- Python 3.8+
- marimo >= 0.6.21
- jupyter-server-proxy (installed automatically)

## Basic Installation

`jupyter-marimo-proxy` requires marimo but does not declare it as a dependency, allowing flexible installation scenarios.

```bash
pip install 'marimo>=0.6.21' jupyter-marimo-proxy
```

Or with uv:

```bash
uv add marimo jupyter-marimo-proxy
```

## Single Python Environment

The simplest setup has both packages in the same environment:

```dockerfile
FROM quay.io/jupyterhub/jupyterhub:latest
RUN cd /srv/jupyterhub && jupyterhub --generate-config && \
    echo "c.JupyterHub.authenticator_class = 'dummy'" >> jupyterhub_config.py && \
    echo "c.DummyAuthenticator.password = 'demo'" >> jupyterhub_config.py && \
    pip install --no-cache-dir notebook 'marimo>=0.6.21' jupyter-marimo-proxy
RUN useradd -ms /bin/bash demo
```

## Multiple Python Environments

With more complex setups (conda, virtualenvs), install packages in the correct environments:

| Package | Install Location | Why |
|---------|------------------|-----|
| `marimo` | User's environment | Access user's packages |
| `jupyter-marimo-proxy` | Jupyter's environment | Jupyter must import it |

Example with Miniforge:

```dockerfile
FROM quay.io/jupyterhub/jupyterhub:latest

RUN cd /srv/jupyterhub && jupyterhub --generate-config && \
    echo "c.JupyterHub.authenticator_class = 'dummy'" >> jupyterhub_config.py && \
    echo "c.DummyAuthenticator.password = 'demo'" >> jupyterhub_config.py && \
    pip install --no-cache-dir notebook

ENV PATH=/opt/conda/bin:$PATH
RUN curl -fsSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -o /root/miniforge.sh && \
    bash /root/miniforge.sh -b -p /opt/conda && rm /root/miniforge.sh

# marimo in conda environment (user packages available)
RUN /opt/conda/bin/pip install --no-cache-dir 'marimo>=0.6.21'

# jupyter-marimo-proxy in Jupyter's environment
RUN /usr/bin/pip install --no-cache-dir jupyter-marimo-proxy

RUN useradd -ms /bin/bash demo
```

## DockerSpawner

For JupyterHub with DockerSpawner, install both packages in the single-user container images. They are not needed in the hub container.

## Verifying Installation

After installation, start JupyterLab:

```bash
jupyter lab
```

You should see a marimo icon in the launcher. If not, see [Troubleshooting](troubleshooting.md).
