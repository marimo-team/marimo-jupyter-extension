"""Jupyter server extension handlers for marimo tools."""

import json
import subprocess

from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.utils import url_path_join
from tornado import web

from .config import get_config
from .executable import get_marimo_command


def _find_marimo_proxy_state(web_app):
    """Find the marimo proxy handler's state dict.

    Searches through the web_app's registered handlers to find the
    jupyter-server-proxy handler for marimo and returns its state dict.
    """
    for host_pattern, handlers in web_app.handlers:
        for spec in handlers:
            if hasattr(spec, 'kwargs') and 'state' in spec.kwargs:
                if 'marimo' in str(spec.regex.pattern):
                    return spec.kwargs['state']
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
            self.finish({"success": False, "error": "Missing input or output path"})
            return

        config = get_config()
        marimo_cmd = get_marimo_command(config)

        result = subprocess.run(
            [*marimo_cmd, "convert", input_path, "-o", output_path],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            self.finish({"success": True, "output": output_path})
        else:
            self.set_status(500)
            self.finish({"success": False, "error": result.stderr or result.stdout})


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
            self.finish({"success": False, "error": "Proxy not initialized yet"})
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


def _jupyter_server_extension_points():
    """Return the server extension points for this package."""
    return [{"module": "jupyter_marimo_proxy.handlers"}]


def _load_jupyter_server_extension(server_app):
    """Load the jupyter server extension."""
    base_url = server_app.web_app.settings["base_url"]
    server_app.web_app.add_handlers(
        ".*",
        [
            (url_path_join(base_url, "marimo-tools/convert"), ConvertHandler),
            (url_path_join(base_url, "marimo-tools/restart"), RestartHandler),
        ],
    )
    server_app.log.info("jupyter-marimo-proxy tools extension loaded")
