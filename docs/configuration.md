# Configuration

## Executable Discovery

By default, the extension searches for `marimo` in:

1. System PATH (via `shutil.which`)
2. Common locations: `~/.local/bin/marimo`, `/opt/bin/marimo`, `/usr/local/bin/marimo`

## Standalone JupyterLab

If you launched JupyterLab directly from a venv (not via JupyterHub), you configure the extension either via a CLI argument or a config file — there is no `jupyterhub_config.py`.

**One-time (CLI argument)**

Pass any `MarimoProxyConfig` option as a flag when starting JupyterLab:

```bash
jupyter lab --MarimoProxyConfig.sandbox=pixi
```

**Permanent (jupyter_server_config.py)**

Find your Jupyter config directory:

```bash
jupyter --config-dir
```

Create or edit `jupyter_server_config.py` in that directory using the same traitlets syntax as below. For example:

```python
c.MarimoProxyConfig.sandbox = "pixi"
```

## Traitlets Configuration (JupyterHub)

For JupyterHub deployments, configure the extension in `jupyterhub_config.py`:

```python
from marimo_jupyter_extension.config import MarimoProxyConfig

# Explicit marimo path
c.MarimoProxyConfig.marimo_path = "/opt/bin/marimo"

# Or use uvx mode (runs `uvx marimo` instead)
c.MarimoProxyConfig.uvx_path = "/usr/local/bin/uvx"

# Sandbox backend: "uv" (default), "pixi", or None.
# marimo provisions one environment per notebook from its PEP 723 metadata:
# a uv venv, or a conda script environment from `[tool.pixi]` tables. Both
# backends keep the venv picker. None disables sandboxing (and the picker).
# See "Sandbox backends" below for pixi requirements.
c.MarimoProxyConfig.sandbox = "uv"

# Deprecated alias for `sandbox = None`. When both are set, no_sandbox wins
# and a warning is logged.
# c.MarimoProxyConfig.no_sandbox = True

# Explicit pixi executable for sandbox = "pixi". If not set, the extension
# searches PATH, $PIXI_HOME/bin, ~/.pixi/bin, /opt/pixi/bin, /usr/local/bin.
c.MarimoProxyConfig.pixi_path = "/opt/pixi/bin/pixi"

# Startup timeout in seconds (default: 60; 300 when sandbox = "pixi").
c.MarimoProxyConfig.timeout = 120

# Enable marimo debug logging for spawn troubleshooting.
# This adds the global marimo CLI flag `--log-level DEBUG`.
c.MarimoProxyConfig.debug = True

# Watch notebook files for external changes and reload automatically.
# Useful when editing .py notebooks with Claude Code, Cursor, vim, or other
# external editors while the notebook is open in the browser (default: False).
c.MarimoProxyConfig.watch = True

# Allowed origins for CORS (default: [] — same-origin only).
# Set to ["*"] to allow all origins, or list specific origins.
c.MarimoProxyConfig.allow_origins = ["https://example.com"]

# Suppress the marimo version-check network call on startup (default: False).
c.MarimoProxyConfig.skip_update_check = True

# Minutes of no browser connection before marimo shuts itself down.
# None (the default) keeps the server running indefinitely.
c.MarimoProxyConfig.idle_timeout = 30.0

# Seconds to keep a session alive after a websocket disconnect.
# None (the default) keeps sessions open indefinitely.
c.MarimoProxyConfig.session_ttl = 300

# Path to a template file whose contents are used as the body of every
# new notebook (POST /marimo-tools/create-stub). Read once at extension
# load and cached for the server's lifetime; restart to pick up changes.
# If the path doesn't exist at boot, this extension fails to load and
# the "New Marimo Notebook" launcher entry will 404 until the path is
# fixed and the server is restarted. The file is emitted verbatim —
# pin __generated_with in the template if you care which version
# reads it.
c.MarimoProxyConfig.default_file = "/opt/marimo/notebook_template.py"
```

A typical template (e.g. with a shared `app.setup` block so every new
notebook starts with imports in scope):

```python
import marimo

__generated_with = "0.23.8"
app = marimo.App(width="medium")

with app.setup(hide_code=True):
    import os  # noqa: F401
    from pathlib import Path  # noqa: F401

if __name__ == "__main__":
    app.run()
```

> **PEP 723 / sandbox metadata:** a leading `# /// script ... # ///` block at
> the top of the template is stripped when the template is loaded. The venv
> for a new notebook is supplied per-request (the launcher passes it), so
> keeping the template's own block would produce a duplicate PEP 723 block and
> `uv` would reject the file. Note this means any `requires-python` or
> `dependencies` pins placed in that leading block are dropped — manage those
> outside the leading PEP 723 block if you need them.

## Sandbox backends

`sandbox` selects how marimo builds the per-notebook environment described by a
notebook's PEP 723 header. The proxy passes it to `marimo edit`:

| `sandbox` | Flag passed to marimo | Environment per notebook |
|-----------|-----------------------|--------------------------|
| `"uv"` (default) | `--sandbox` | uv virtualenv from `dependencies` |
| `"pixi"` | `--sandbox=pixi` | conda script environment from `[tool.pixi]` tables, with PyPI packages layered by uv |
| `None` | *(none)* | the interpreter marimo itself runs in |

The uv spelling stays a bare `--sandbox` so `marimo>=0.23.14` releases keep
working; newer marimo normalizes it to `--sandbox=uv`.

### Using pixi

Pick pixi when notebooks need conda-only packages (GDAL, CUDA toolkits, R
bindings). See marimo's
[Pixi sandboxes](https://docs.marimo.io/guides/package_management/inlining_dependencies/)
guide for the notebook side.

**Requirements**

> **Warning:** Upgrade to `marimo>=0.25.0` before selecting `sandbox = "pixi"`.
> Older releases reject `--sandbox=pixi`.

- `marimo>=0.25.0` for Pixi, or `marimo>=0.23.14` for uv.
- `pixi>=0.80`, which adds `pixi install --script`. marimo probes for it at
  startup and fails otherwise.
- Network access to conda-forge (or a mirror configured in pixi's global
  config) from the spawned server.

With `uvx_path`, the extension requests `marimo[sandbox]>=0.25.0` for Pixi so
uvx cannot reuse an older installed version. With `marimo_path` or PATH
discovery, upgrade marimo in that environment:

```bash
uv pip install --upgrade "marimo[sandbox]>=0.25.0"
```

**Install pixi where the spawned server can see it**

- In the image or on the host, as root: `curl -fsSL https://pixi.sh/install.sh | sh`
  (set `PIXI_HOME=/opt/pixi` first to install system-wide), or
- From conda-forge into an existing conda base: `conda install -c conda-forge pixi`, or
- Per user, with the same installer, which lands in `~/.pixi/bin`.

marimo locates pixi with `shutil.which("pixi")`, so either put its `bin`
directory on the spawner `PATH` or set `pixi_path`. When `pixi_path` (or a
common install location) points outside `PATH`, the extension prepends that
directory to `PATH` for the spawned marimo process. If pixi cannot be found the
extension fails at load time with a `FileNotFoundError` naming both fixes.

```python
c.MarimoProxyConfig.sandbox = "pixi"
c.MarimoProxyConfig.pixi_path = "/opt/pixi/bin/pixi"  # or add its dir to PATH
```

**Persist the package cache**

pixi keeps solved environments and downloaded packages in its cache
(`$PIXI_CACHE_DIR`, else `$XDG_CACHE_HOME/rattler`, else `~/.cache/rattler` on
Linux). A cold cache means a full conda solve and download on first launch, so
point it at a persistent volume in the spawner environment:

```python
c.SystemdSpawner.environment["PIXI_CACHE_DIR"] = "/opt/notebooks/.cache/pixi"
```

**Startup timeout**

The first pixi launch runs `pixi exec` (fetching uv), solves and installs the
conda environment, then builds marimo's uv overlay before the HTTP port opens.
When `sandbox = "pixi"` and `timeout` is not set, the startup timeout defaults
to 300 s instead of 60 s. Raise it further on slow links; a timeout kills the
process mid-solve and the next launch starts the solve again.

**Limitations inherited from marimo**

- Conda activation scripts are not applied; packages that rely on them for
  environment variables need those set in the spawner environment.
- Most `marimo export` targets (including `html-wasm`) support only the uv
  backend.
- Extra ingress: one conda prefix per notebook under the cache; ephemeral home
  directories lose it on restart.

## Spawner Environment

For JupyterHub deployments using SystemdSpawner, configure the spawned notebook environment:

```python
c.SystemdSpawner.environment = {
    "PATH": "/opt/jupyterhub/.venv/bin:/usr/local/bin:/usr/bin:/bin",
    "XDG_RUNTIME_DIR": "/run/user/jupyter",
    "XDG_DATA_HOME": "/opt/notebooks/.local/share",
    "XDG_CONFIG_HOME": "/opt/notebooks/.config",
    "XDG_CACHE_HOME": "/opt/notebooks/.cache",
    "HOME": "/opt/notebooks",
}
```

With `sandbox = "pixi"`, also add pixi's `bin` directory to `PATH` (or set
`pixi_path`) and set `PIXI_CACHE_DIR` to a persistent location, as described
above.

## Alternative: Symlink marimo

Instead of explicit path configuration, copy or symlink marimo to a location already in the spawner's PATH:

```bash
# As root
ln -s /opt/jupyterhub/.venv/bin/marimo /opt/bin/marimo
```

This works if `/opt/bin` is already in the spawner's PATH.
