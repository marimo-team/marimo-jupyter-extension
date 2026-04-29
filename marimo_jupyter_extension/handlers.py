"""Jupyter server extension handlers for marimo tools."""

import asyncio
import json
from pathlib import Path

from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.utils import url_path_join
from tornado import web
from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop

from .convert import convert_notebook_to_marimo

_WATCHER_POLL_INTERVAL = 1.0


def _find_marimo_proxy_state(web_app):
    """Return the jupyter-server-proxy state dict for the marimo route."""
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
    """Liveness probe used by the sidebar; never spawns marimo."""

    @web.authenticated
    async def get(self):
        # GET handlers are conventionally exempt from XSRF, but this
        # endpoint forwards the caller's Cookie + Authorization onward
        # to /marimo/health, so explicitly validate the inbound token
        # to keep cross-origin pages from triggering a credentialed
        # proxy probe. JupyterHandler.prepare() only auto-checks XSRF
        # for non-GET methods, so the call is needed here.
        self.check_xsrf_cookie()

        proxy_state = _find_marimo_proxy_state(self.application)
        proc = proxy_state.get("proc") if proxy_state else None

        if not _is_process_alive(proc):
            self.finish({"process_alive": False, "marimo_healthy": False})
            return

        try:
            base_url = self.application.settings.get("base_url", "/")
            health_url = url_path_join(
                f"{self.request.protocol}://{self.request.host}",
                base_url,
                "marimo/health",
            )

            forward_headers = {}
            for h in ("Cookie", "Authorization", "X-Xsrftoken"):
                v = self.request.headers.get(h, "")
                if v:
                    forward_headers[h] = v

            # follow_redirects=False prevents forwarded Cookie/Authorization
            # leaking to a third party if the proxy target returns a 3xx.
            response = await AsyncHTTPClient().fetch(
                health_url,
                request_timeout=10,
                headers=forward_headers,
                follow_redirects=False,
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
    if proc is None or isinstance(proc, str):
        return False
    if hasattr(proc, "running"):
        return proc.running
    return True


async def _proc_watcher_loop(server_app):
    """Evict stale proc from jupyter-server-proxy state when marimo dies.

    Without this, a self-exited marimo leaves a cached SupervisedProcess
    behind; the next request's ensure_process() cleanup awaits kill() on
    a reaped child and raises ProcessLookupError as a 500.
    """
    while True:
        try:
            proxy_state = _find_marimo_proxy_state(server_app.web_app)
            proc = proxy_state.get("proc") if proxy_state else None
            if (
                proc is None
                or isinstance(proc, str)
                or not hasattr(proc, "proc")
            ):
                await asyncio.sleep(_WATCHER_POLL_INTERVAL)
                continue

            # Suppress simpervisor's auto-restart: on non-zero exit it
            # would re-spawn into the proxy's still-cached port and
            # collide with our fresh spawn loop. Real respawns must come
            # from ensure_process() on a real request.
            #
            # Private attribute because simpervisor has no public API
            # to disable auto-restart yet — tracked in
            # https://github.com/jupyterhub/simpervisor/pull/73. Switch
            # to the public API once it lands and we bump the floor.
            restart_future = getattr(proc, "_restart_process_future", None)
            if restart_future is not None and not restart_future.done():
                restart_future.cancel()

            try:
                await proc.proc.wait()
            except Exception:
                pass

            async with proxy_state["proc_lock"]:
                if proxy_state.get("proc") is proc:
                    rc = getattr(proc.proc, "returncode", "?")
                    server_app.log.info(
                        "marimo proc exited (rc=%s); evicting from "
                        "jupyter-server-proxy state",
                        rc,
                    )
                    del proxy_state["proc"]
        except Exception as e:
            server_app.log.warning(
                "marimo proc watcher iteration failed: %s", e
            )
            await asyncio.sleep(_WATCHER_POLL_INTERVAL)


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
                '__generated_with = "0.23.4"',
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
    IOLoop.current().spawn_callback(_proc_watcher_loop, server_app)
    server_app.log.info("marimo-jupyter-extension tools extension loaded")
