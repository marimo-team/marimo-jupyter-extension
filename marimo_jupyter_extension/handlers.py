"""Jupyter server extension handlers for marimo tools."""

import asyncio
import json
from pathlib import Path

from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.utils import url_path_join
from tornado import web
from tornado.httpclient import AsyncHTTPClient

from .convert import convert_notebook_to_marimo


def _find_marimo_proxy_state(web_app):
    """Find the marimo proxy handler's state dict.

    Searches through the web_app's registered handlers to find the
    jupyter-server-proxy handler for marimo and returns its state dict.
    Supports both legacy tornado (<6) .handlers and modern (.default_router).
    """
    # Modern tornado (6.x+): handlers are in default_router.rules.
    # Each Rule stores its handler kwargs as `target_kwargs`.
    if hasattr(web_app, "default_router"):
        for host_rule in web_app.default_router.rules:
            target = getattr(host_rule, "target", None)
            if not hasattr(target, "rules"):
                continue
            for rule in target.rules:
                kwargs = getattr(rule, "target_kwargs", None) or {}
                if "state" not in kwargs:
                    continue
                matcher = getattr(rule, "matcher", None)
                regex = getattr(matcher, "regex", None)
                if regex and "marimo" in regex.pattern:
                    return kwargs["state"]

    # Legacy tornado: handlers stored as (host_pattern, [URLSpec, ...])
    if hasattr(web_app, "handlers"):
        for _host_pattern, handlers in web_app.handlers:
            for spec in handlers:
                if hasattr(spec, "kwargs") and "state" in spec.kwargs:
                    if "marimo" in str(spec.regex.pattern):
                        return spec.kwargs["state"]

    return None


class ConvertHandler(JupyterHandler):
    """Handler for converting Jupyter notebooks to marimo format."""

    @web.authenticated
    async def post(self):
        """Convert a Jupyter notebook to marimo format.

        POST /marimo-tools/convert
        Body: {"input": "notebook.ipynb", "output": "notebook.py"}
        """
        data = json.loads(self.request.body)
        input_path = data.get("input")
        output_path = data.get("output")

        if not input_path or not output_path:
            self.set_status(400)
            self.finish(
                {"success": False, "error": "Missing input or output path"}
            )
            return

        try:
            convert_notebook_to_marimo(input_path, output_path)
            self.finish({"success": True, "output": output_path})
        except RuntimeError as e:
            self.set_status(500)
            self.finish({"success": False, "error": str(e)})


class RestartHandler(JupyterHandler):
    """Handler for restarting the marimo server."""

    @web.authenticated
    async def post(self):
        """Restart the marimo server.

        POST /marimo-tools/restart

        Finds the jupyter-server-proxy handler's state, kills the current
        process, and clears the state so the next request spawns a new process.
        """
        proxy_state = _find_marimo_proxy_state(self.application)

        if not proxy_state:
            self.set_status(503)
            self.finish(
                {"success": False, "error": "Proxy not initialized yet"}
            )
            return

        try:
            async with proxy_state["proc_lock"]:
                proc = proxy_state.get("proc")
                if proc and proc != "process not managed":
                    try:
                        await proc.kill()
                    except Exception:
                        pass  # Already dead
                # Clear the process reference so next request spawns new one
                if "proc" in proxy_state:
                    del proxy_state["proc"]

            self.finish({"success": True, "message": "Server restarting"})
        except Exception as e:
            self.set_status(500)
            self.finish({"success": False, "error": str(e)})


class HealthHandler(JupyterHandler):
    """Health check that avoids the jupyter-server-proxy deadlock.

    When marimo has exited, polling /marimo/health through the proxy triggers
    ensure_process() which hangs on the dead process. This handler checks
    process liveness first (instant), cleans up stale state if dead, and only
    proxies the health check to marimo when the process is alive.
    """

    @web.authenticated
    async def get(self):
        """Check marimo server health.

        GET /marimo-tools/health
        Response: {"process_alive": bool, "marimo_healthy": bool}

        This endpoint NEVER triggers ensure_process() — it only checks
        existing state. Starting marimo is left to explicit user actions
        (Start Server button, opening a notebook) which go through the
        proxy directly.
        """
        proxy_state = _find_marimo_proxy_state(self.application)

        if not proxy_state:
            self.finish({"process_alive": False, "marimo_healthy": False})
            return

        proc = proxy_state.get("proc")

        # No process in state — either never started or previously cleaned up
        if proc is None:
            self.finish({"process_alive": False, "marimo_healthy": False})
            return

        # Process exists but has exited — clean up stale state so the next
        # real request (notebook open, Start Server) spawns fresh instead
        # of deadlocking in ensure_process()
        if not _is_process_alive(proc):
            returncode = getattr(proc, "returncode", "unknown")
            self.log.info(
                "marimo process has exited (returncode: %s), "
                "cleaning up proxy state",
                returncode,
            )
            await _cleanup_proxy_state(proxy_state)
            self.finish({"process_alive": False, "marimo_healthy": False})
            return

        # Process is alive — proxy the health check to marimo.
        # ensure_process() is a no-op when proc is already in state.
        try:
            base_url = self.application.settings.get("base_url", "/")
            health_url = url_path_join(
                f"{self.request.protocol}://{self.request.host}",
                base_url,
                "marimo/health",
            )

            # Forward jupyter auth (cookies + Authorization) so the internal
            # request authenticates the same way the original did.
            forward_headers = {}
            cookie = self.request.headers.get("Cookie", "")
            if cookie:
                forward_headers["Cookie"] = cookie
            auth = self.request.headers.get("Authorization", "")
            if auth:
                forward_headers["Authorization"] = auth

            http_client = AsyncHTTPClient()
            response = await http_client.fetch(
                health_url,
                request_timeout=10,
                headers=forward_headers,
                validate_cert=False,
            )

            data = json.loads(response.body)
            marimo_healthy = data.get("status") == "healthy"

            if not marimo_healthy:
                self.log.warning(
                    "marimo process is running but health check returned: %s",
                    response.body.decode(),
                )

            self.finish(
                {"process_alive": True, "marimo_healthy": marimo_healthy}
            )
        except Exception as e:
            self.log.warning("marimo health check failed: %s", e)
            self.finish({"process_alive": True, "marimo_healthy": False})


def _is_process_alive(proc):
    """Check if a jupyter-server-proxy managed process is still running."""
    if proc is None:
        return False
    if isinstance(proc, str):
        # "process not managed by jupyter-server-proxy"
        return False
    if hasattr(proc, "running"):
        return proc.running
    return True


async def _cleanup_proxy_state(proxy_state):
    """Remove stale proc from proxy state so next request spawns fresh.

    Uses a timeout to avoid blocking if proc_lock is already held by a
    hung ensure_process() call.
    """

    async def _do_cleanup():
        async with proxy_state["proc_lock"]:
            if "proc" in proxy_state:
                del proxy_state["proc"]

    try:
        await asyncio.wait_for(_do_cleanup(), timeout=5)
    except (asyncio.TimeoutError, Exception):
        pass


class ConfigHandler(JupyterHandler):
    """Handler for exposing extension configuration to the frontend."""

    @web.authenticated
    async def get(self):
        """Return extension configuration.

        GET /marimo-tools/config
        Response: {"no_sandbox": bool}
        """
        from .config import get_config

        config = get_config()
        self.finish({"no_sandbox": config.no_sandbox})


class CreateStubHandler(JupyterHandler):
    """Handler for creating marimo notebook stub files."""

    @web.authenticated
    async def post(self):
        """Create a marimo notebook stub with PEP 723 metadata.

        POST /marimo-tools/create-stub
        Body: {"path": "notebook.py", "venv": "/path/to/python"}
        """
        data = json.loads(self.request.body)
        path = data.get("path")
        venv = data.get("venv")

        if not path:
            self.set_status(400)
            self.finish({"success": False, "error": "Missing path"})
            return

        # Build stub content
        lines = []

        # Add PEP 723 header if venv is specified
        if venv:
            # Extract venv directory from python executable path
            # e.g., /path/to/venv/bin/python3.12 -> /path/to/venv
            venv_path = Path(venv)
            if venv_path.parent.name == "bin":
                venv_path = venv_path.parent.parent
            lines.extend(
                [
                    "# /// script",
                    "# [tool.marimo.venv]",
                    f'# path = "{venv_path}"',
                    "# ///",
                    "",
                ]
            )

        # Add marimo app boilerplate
        lines.extend(
            [
                "import marimo",
                "",
                '__generated_with = "0.23.1"',
                'app = marimo.App(width="medium")',
                "",
                "",
                'if __name__ == "__main__":',
                "    app.run()",
                "",
            ]
        )

        content = "\n".join(lines)

        try:
            file_path = Path(path)
            file_path.write_text(content)
            self.finish({"success": True, "path": path})
        except Exception as e:
            self.set_status(500)
            self.finish({"success": False, "error": str(e)})


def _jupyter_server_extension_points():
    """Return the server extension points for this package."""
    return [{"module": "marimo_jupyter_extension.handlers"}]


def _load_jupyter_server_extension(server_app):
    """Load the jupyter server extension."""
    base_url = server_app.web_app.settings["base_url"]
    server_app.web_app.add_handlers(
        ".*",
        [
            (url_path_join(base_url, "marimo-tools/convert"), ConvertHandler),
            (url_path_join(base_url, "marimo-tools/restart"), RestartHandler),
            (url_path_join(base_url, "marimo-tools/health"), HealthHandler),
            (
                url_path_join(base_url, "marimo-tools/create-stub"),
                CreateStubHandler,
            ),
            (url_path_join(base_url, "marimo-tools/config"), ConfigHandler),
        ],
    )
    server_app.log.info("marimo-jupyter-extension tools extension loaded")
