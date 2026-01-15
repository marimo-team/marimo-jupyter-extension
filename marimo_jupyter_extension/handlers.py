"""Jupyter server extension handlers for marimo tools."""

import json
import subprocess
from pathlib import Path

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
            self.finish(
                {"success": False, "error": result.stderr or result.stdout}
            )


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
                '__generated_with = "0.19.2"',
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
            (
                url_path_join(base_url, "marimo-tools/create-stub"),
                CreateStubHandler,
            ),
        ],
    )
    server_app.log.info("marimo-jupyter-extension tools extension loaded")
