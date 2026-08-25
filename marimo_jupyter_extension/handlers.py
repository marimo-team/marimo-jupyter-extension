"""Jupyter server extension handlers for marimo tools."""

import asyncio
import json
import re
from pathlib import Path, PurePath, PureWindowsPath

from jupyter_core.utils import ensure_async
from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.utils import url_path_join
from tornado import web
from tornado.ioloop import IOLoop

from . import version_info
from .convert import convert_notebook_to_marimo
from .executable import MARIMO_VERSION

_WATCHER_POLL_INTERVAL = 1.0

# How long to wait for marimo to honor SIGTERM (proc.terminate()) before
# falling back to SIGKILL on restart. SIGTERM lets marimo's own signal
# handler forward the signal to the --sandbox child's process group
# (os.killpg) so the whole subtree shuts down; SIGKILL is uncatchable and
# would orphan that child (see RestartHandler.post).
_SIGTERM_GRACE_SECONDS = 5.0

# Key under which the cached default-file body is stored on
# web_app.settings. Read once at extension load (see
# _load_jupyter_server_extension) and consumed by CreateStubHandler.
_DEFAULT_FILE_SETTING = "marimo_default_stub_content"


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

        Finds the jupyter-server-proxy handler's state, terminates the
        current process, and clears the state so the next request spawns a
        new process.
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
                    # Use SIGTERM (terminate), not SIGKILL (kill): under
                    # --sandbox marimo spawns its inner uv process in a new
                    # session and forwards SIGINT/SIGTERM/SIGHUP to that
                    # group via os.killpg. SIGKILL is uncatchable, so it
                    # only reaps the outer CLI and orphans the inner child,
                    # which keeps holding the cached port and makes the next
                    # spawn collide ([Errno 98]). SIGTERM lets marimo tear
                    # down the whole subtree. Fall back to SIGKILL only if
                    # the outer process ignores SIGTERM, so restart always
                    # returns.
                    try:
                        await asyncio.wait_for(
                            proc.terminate(),
                            timeout=_SIGTERM_GRACE_SECONDS,
                        )
                    except asyncio.TimeoutError:
                        try:
                            await proc.kill()
                        except Exception:
                            pass  # Already dead
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
    """Process liveness probe used by the sidebar; never spawns marimo.

    Only reports whether jupyter-server-proxy's SupervisedProcess is
    running. Server-reachability is checked client-side from the sidebar
    so the probe path matches the iframe's path (see #95 — a server-side
    HTTP probe via self.request.host gets bounced by oauth2 redirects
    on reverse-proxy setups even when marimo is fully reachable).
    """

    @web.authenticated
    async def get(self):
        proxy_state = _find_marimo_proxy_state(self.application)
        proc = proxy_state.get("proc") if proxy_state else None
        self.finish({"process_alive": _is_process_alive(proc)})


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
        if not isinstance(path, str) or not path.endswith(".py"):
            self.set_status(400)
            self.finish(
                {
                    "success": False,
                    "error": "Notebook filename must end in .py",
                }
            )
            return

        # Build stub content
        lines = []

        # Add PEP 723 header if venv is specified
        if venv:
            venv_path = _venv_directory(venv)
            quoted_venv_path = json.dumps(str(venv_path), ensure_ascii=False)
            lines.extend(
                [
                    "# /// script",
                    "# [tool.marimo.venv]",
                    f"# path = {quoted_venv_path}",
                    "# ///",
                    "",
                ]
            )

        cached_default = self.application.settings.get(_DEFAULT_FILE_SETTING)
        if cached_default is not None:
            # Operator provided a template via
            # c.MarimoProxyConfig.default_file — emit its contents
            # verbatim after the optional PEP 723 header. The template
            # is responsible for being a parseable marimo notebook
            # (import marimo, app = marimo.App(...), the __main__
            # block); we don't substitute __generated_with so the
            # template's pin (if any) wins.
            lines.append(cached_default.rstrip("\n"))
        else:
            # Default boilerplate. Prefer the running marimo's
            # version so the stub matches what will read it; fall
            # back to the floor MARIMO_VERSION when marimo can't be
            # queried (e.g. uvx mode with no marimo in the Jupyter
            # env).
            marimo_version = (
                version_info.get_marimo_version() or MARIMO_VERSION
            )
            lines.extend(
                [
                    "import marimo",
                    "",
                    f'__generated_with = "{marimo_version}"',
                    'app = marimo.App(width="medium")',
                    "",
                    "",
                    'if __name__ == "__main__":',
                    "    app.run()",
                ]
            )
        lines.append("")
        content = "\n".join(lines)

        try:
            file_path = Path(path)
            file_path.write_text(content)
            self.finish({"success": True, "path": path})
        except Exception as e:
            self.set_status(500)
            self.finish({"success": False, "error": str(e)})


def _venv_directory(python_executable: str) -> PurePath:
    """Return the environment directory for a kernelspec interpreter."""
    executable: PurePath
    if "\\" in python_executable and "/" not in python_executable:
        executable = PureWindowsPath(python_executable)
    else:
        executable = Path(python_executable)
    if executable.parent.name.casefold() in {"bin", "scripts"}:
        return executable.parent.parent
    return executable


def _line_without_ending(line: str) -> str:
    return line.rstrip("\r\n")


def _pep723_content(line: str) -> str | None:
    """Return the TOML content from one PEP 723 comment line."""
    line = _line_without_ending(line)
    if line == "#":
        return ""
    if line.startswith("# "):
        return line[2:]
    return None


def _set_notebook_venv(content: str, venv: str | None) -> str:
    """Set or clear ``tool.marimo.venv.path`` in notebook metadata.

    This intentionally edits the existing text instead of parsing and
    serializing all TOML, so dependency pins, comments, and formatting remain
    untouched.
    """
    lines = content.splitlines(keepends=True)
    starts = [
        index
        for index, line in enumerate(lines)
        if _line_without_ending(line) == "# /// script"
    ]
    if len(starts) > 1:
        raise ValueError("Multiple PEP 723 script metadata blocks found")

    newline = "\r\n" if "\r\n" in content else "\n"
    path_line = None
    if venv:
        quoted_path = json.dumps(
            str(_venv_directory(venv)), ensure_ascii=False
        )
        path_line = f"# path = {quoted_path}{newline}"

    if not starts:
        if path_line is None:
            return content
        insert_at = 0
        if lines and _line_without_ending(lines[0]).startswith("#!"):
            insert_at = 1
        encoding_pattern = re.compile(r"^\s*#.*?coding[:=]\s*[-_.a-zA-Z0-9]+")
        if insert_at < len(lines) and encoding_pattern.match(
            _line_without_ending(lines[insert_at])
        ):
            insert_at += 1
        if insert_at and not lines[insert_at - 1].endswith(("\n", "\r")):
            lines[insert_at - 1] += newline
        lines[insert_at:insert_at] = [
            f"# /// script{newline}",
            f"# [tool.marimo.venv]{newline}",
            path_line,
            f"# ///{newline}",
            newline,
        ]
        return "".join(lines)

    start = starts[0]
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if _line_without_ending(lines[index]) == "# ///"
        ),
        None,
    )
    if end is None:
        raise ValueError("Unterminated PEP 723 script metadata block")

    section_pattern = re.compile(r"^\s*\[([^]]+)]\s*(?:#.*)?$")
    path_pattern = re.compile(r"^\s*path\s*=")
    section_start = None
    section_end = end
    for index in range(start + 1, end):
        metadata_line = _pep723_content(lines[index])
        if metadata_line is None:
            continue
        match = section_pattern.match(metadata_line)
        if not match:
            continue
        if section_start is not None:
            section_end = index
            break
        if match.group(1).strip() == "tool.marimo.venv":
            section_start = index

    if section_start is None:
        if path_line is None:
            return content
        lines[end:end] = [
            f"# [tool.marimo.venv]{newline}",
            path_line,
        ]
        return "".join(lines)

    path_indexes = []
    for index in range(section_start + 1, section_end):
        metadata_line = _pep723_content(lines[index])
        if metadata_line is not None and path_pattern.match(metadata_line):
            path_indexes.append(index)

    if path_line is not None:
        if path_indexes:
            lines[path_indexes[0]] = path_line
            for index in reversed(path_indexes[1:]):
                del lines[index]
        else:
            lines.insert(section_start + 1, path_line)
        return "".join(lines)

    for index in reversed(path_indexes):
        del lines[index]
        section_end -= 1

    remaining = [
        _pep723_content(line)
        for line in lines[section_start + 1 : section_end]
    ]
    if not any(line is not None and line.strip() for line in remaining):
        del lines[section_start:section_end]
    return "".join(lines)


def _get_notebook_venv(content: str) -> str | None:
    """Read ``tool.marimo.venv.path`` without importing marimo or TOML."""
    lines = content.splitlines(keepends=True)
    starts = [
        index
        for index, line in enumerate(lines)
        if _line_without_ending(line) == "# /// script"
    ]
    if len(starts) > 1:
        raise ValueError("Multiple PEP 723 script metadata blocks found")
    if not starts:
        return None

    start = starts[0]
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if _line_without_ending(lines[index]) == "# ///"
        ),
        None,
    )
    if end is None:
        raise ValueError("Unterminated PEP 723 script metadata block")

    in_venv_section = False
    section_pattern = re.compile(r"^\s*\[([^]]+)]\s*(?:#.*)?$")
    path_pattern = re.compile(r"^\s*path\s*=\s*(.+?)\s*$")
    for line in lines[start + 1 : end]:
        metadata_line = _pep723_content(line)
        if metadata_line is None:
            continue
        section = section_pattern.match(metadata_line)
        if section:
            in_venv_section = section.group(1).strip() == "tool.marimo.venv"
            continue
        if not in_venv_section:
            continue
        path = path_pattern.match(metadata_line)
        if not path:
            continue
        value = path.group(1)
        try:
            parsed, _end = json.JSONDecoder().raw_decode(value)
            return parsed if isinstance(parsed, str) else None
        except json.JSONDecodeError:
            if len(value) >= 2 and value[0] == value[-1] == "'":
                return value[1:-1]
            return None
    return None


def _has_marimo_app_markers(content: str) -> bool:
    """Match marimo's directory-scanner check for Python notebooks."""
    # marimo is not a dependency of this extension when it runs through uvx,
    # so its internal directory-scanner helper cannot be imported here.
    return (
        re.search(r"^import marimo(?:\s|$)", content, re.MULTILINE) is not None
        and "marimo.App" in content
    )


class SetVenvHandler(JupyterHandler):
    """Handler for changing a saved marimo notebook's environment."""

    async def _read_notebook(self, path: str) -> str:
        model = await ensure_async(
            self.contents_manager.get(
                path=path,
                type="file",
                format="text",
                content=True,
            )
        )
        content = model.get("content")
        if not isinstance(content, str):
            raise web.HTTPError(400, "Notebook is not a text file")
        return content

    async def _save_notebook(self, path: str, content: str) -> None:
        await ensure_async(
            self.contents_manager.save(
                {"type": "file", "format": "text", "content": content},
                path,
            )
        )

    def _finish_contents_error(self, error: web.HTTPError) -> None:
        status = error.status_code
        message = (
            "Notebook not found"
            if status == 404
            else error.get_message() or error.reason or str(error)
        )
        self.set_status(status)
        self.finish({"success": False, "error": message})

    @web.authenticated
    async def get(self):
        """Return the currently configured environment for a notebook."""
        path = self.get_argument("path", None)
        if not path:
            self.set_status(400)
            self.finish({"success": False, "error": "Missing path"})
            return

        try:
            content = await self._read_notebook(path)
            is_marimo = _has_marimo_app_markers(content)
            self.finish(
                {
                    "success": True,
                    "isMarimo": is_marimo,
                    "venv": _get_notebook_venv(content) if is_marimo else None,
                }
            )
        except web.HTTPError as e:
            self._finish_contents_error(e)
        except ValueError as e:
            self.set_status(400)
            self.finish({"success": False, "error": str(e)})
        except Exception as e:
            self.set_status(500)
            self.finish({"success": False, "error": str(e)})

    @web.authenticated
    async def post(self):
        """Update the notebook's ``tool.marimo.venv.path`` metadata.

        POST /marimo-tools/set-venv
        Body: {"path": "notebook.py", "venv": "/path/to/python" | null}
        """
        try:
            data = json.loads(self.request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.set_status(400)
            self.finish({"success": False, "error": "Invalid JSON body"})
            return
        if not isinstance(data, dict):
            self.set_status(400)
            self.finish(
                {"success": False, "error": "JSON body must be an object"}
            )
            return
        path = data.get("path")
        venv = data.get("venv")

        if not isinstance(path, str) or not path:
            self.set_status(400)
            self.finish({"success": False, "error": "Missing path"})
            return
        if not path.endswith(".py"):
            self.set_status(400)
            self.finish(
                {
                    "success": False,
                    "error": (
                        "Environment selection is only supported for "
                        "Python notebooks"
                    ),
                }
            )
            return
        if venv is not None and not isinstance(venv, str):
            self.set_status(400)
            self.finish({"success": False, "error": "Invalid venv"})
            return

        try:
            content = await self._read_notebook(path)
            if not _has_marimo_app_markers(content):
                self.set_status(400)
                self.finish(
                    {
                        "success": False,
                        "error": "File is not a marimo notebook",
                    }
                )
                return
            updated = _set_notebook_venv(content, venv)
            await self._save_notebook(path, updated)
            self.finish(
                {
                    "success": True,
                    "path": path,
                    "venv": str(_venv_directory(venv)) if venv else None,
                }
            )
        except web.HTTPError as e:
            self._finish_contents_error(e)
        except ValueError as e:
            self.set_status(400)
            self.finish({"success": False, "error": str(e)})
        except Exception as e:
            self.set_status(500)
            self.finish({"success": False, "error": str(e)})


def _jupyter_server_extension_points():
    """Return the server extension points for this package."""
    return [{"module": "marimo_jupyter_extension.handlers"}]


def _strip_leading_pep723(text: str) -> str:
    """Drop a leading PEP 723 ``# /// script ... # ///`` block.

    CreateStubHandler prepends its own ``[tool.marimo.venv]`` PEP 723 block
    per-request (when the body carries ``venv``). If the operator's
    default_file template *also* starts with a PEP 723 block (natural if they
    copy-pasted a real notebook), the stub ends up with two blocks and uv
    rejects it ("multiple PEP 723 metadata blocks"). Stripping the template's
    leading block at load time lets the request-time venv win.

    Only a block at the very top (after any leading blank/whitespace-only
    lines) is removed; any ``requires-python``/``dependencies`` pins it
    contained are dropped along with it.
    """
    lines = text.splitlines(keepends=True)
    start = 0
    while start < len(lines) and lines[start].strip() == "":
        start += 1
    if start >= len(lines) or lines[start].strip() != "# /// script":
        return text
    # Find the closing fence.
    for end in range(start + 1, len(lines)):
        if lines[end].strip() == "# ///":
            # Drop the block (and a single trailing blank line, if present)
            # so we don't leave an awkward gap at the top of the stub.
            rest = lines[end + 1 :]
            if rest and rest[0].strip() == "":
                rest = rest[1:]
            return "".join(lines[:start] + rest)
    # Unterminated block: leave the content untouched rather than eat the
    # whole template.
    return text


def _load_default_file(server_app) -> str | None:
    """Read the default_file template once at extension load.

    Returns the file contents (a str) when default_file is configured,
    or None when it isn't. Raises FileNotFoundError eagerly if the
    operator configured a path that doesn't exist; jupyter-server's
    extension manager logs the traceback and skips loading our
    extension (the server itself keeps running, but
    /marimo-tools/create-stub will 404 until the path is fixed and
    the server is restarted). The alternative — deferring the read
    to /marimo-tools/create-stub request handling — would surface
    the misconfiguration as a 500 on every "New Notebook" click and
    leave the boot log silent.

    Reading once at startup (rather than per-request) also means
    operators must restart Jupyter Server to pick up template
    changes. This trades the convenience of hot-swap for a clearer
    audit boundary: whatever was on disk when the server booted is
    what users get.
    """
    from .config import get_config

    cfg = get_config()
    if not cfg.default_file:
        return None

    template_path = Path(cfg.default_file).expanduser()
    try:
        content = template_path.read_text(encoding="utf-8")
    except (
        FileNotFoundError,
        IsADirectoryError,
        PermissionError,
        UnicodeDecodeError,
        OSError,
    ) as e:
        # Every one of these (missing file, a directory, unreadable perms,
        # non-utf-8 bytes, broken symlink, ...) lands in the same place:
        # the extension fails to load and /marimo-tools/* all 404. Surface
        # the actionable trait pointer instead of a bare traceback.
        server_app.log.error(
            "c.MarimoProxyConfig.default_file points at %s but the "
            "file could not be read (%s); the marimo-jupyter-extension "
            "will fail to load and /marimo-tools/create-stub will 404 "
            "until this is fixed and the server is restarted.",
            template_path,
            e.__class__.__name__,
        )
        raise
    # Strip a leading PEP 723 block so it doesn't collide with the venv block
    # CreateStubHandler prepends per-request (see _strip_leading_pep723).
    content = _strip_leading_pep723(content)
    server_app.log.info(
        "marimo-jupyter-extension loaded default notebook template "
        "from %s (%d bytes); restart to pick up changes.",
        template_path,
        len(content),
    )
    return content


def _load_jupyter_server_extension(server_app):
    """Load the jupyter server extension."""
    from . import __version__

    # Read default_file first so a misconfigured path aborts the load
    # cleanly. If we registered handlers first and *then* raised, the
    # tornado routes would survive — CreateStubHandler would still be
    # reachable but would silently fall back to the default boilerplate
    # (cached content never landed on web_app.settings), masking the
    # operator's misconfiguration. Failing before any side effects
    # keeps "extension loaded successfully" and "template wired up" as
    # a single atomic outcome.
    default_file_content = _load_default_file(server_app)

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
            (
                url_path_join(base_url, "marimo-tools/set-venv"),
                SetVenvHandler,
            ),
            (url_path_join(base_url, "marimo-tools/config"), ConfigHandler),
        ],
    )
    IOLoop.current().spawn_callback(_proc_watcher_loop, server_app)

    if default_file_content is not None:
        server_app.web_app.settings[_DEFAULT_FILE_SETTING] = (
            default_file_content
        )

    page_config = server_app.web_app.settings.setdefault(
        "page_config_data", {}
    )
    page_config["marimoExtensionVersion"] = __version__
    page_config["marimoVersion"] = version_info.get_marimo_version() or ""

    server_app.log.info("marimo-jupyter-extension tools extension loaded")
