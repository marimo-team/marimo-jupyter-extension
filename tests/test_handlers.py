"""Tests for the handlers module."""

import asyncio
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_handler(handler_cls, *, application=None):
    """Build a handler instance bypassing Tornado's initializer."""
    handler = handler_cls.__new__(handler_cls)
    handler.application = application
    handler.current_user = "u"
    handler.set_status = MagicMock()
    handler.finish = MagicMock()
    # Bypass XSRF: real validation needs a fully-initialized Tornado
    # request, which these unit tests deliberately skip. Per-test
    # overrides can swap this for a side-effect to exercise rejection.
    handler.check_xsrf_cookie = MagicMock()
    return handler


def _run(handler, method_name):
    """Invoke an @web.authenticated async method, bypassing the guard."""
    method = getattr(type(handler), method_name).__wrapped__
    asyncio.run(method(handler))


class TestHandlers:
    """Test the handlers module."""

    def test_module_importable(self):
        """Test that the handlers module is importable."""
        from marimo_jupyter_extension import handlers

        assert handlers is not None

    def test_extension_points_function_exists(self):
        """Test that _jupyter_server_extension_points exists."""
        from marimo_jupyter_extension.handlers import (
            _jupyter_server_extension_points,
        )

        result = _jupyter_server_extension_points()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["module"] == "marimo_jupyter_extension.handlers"

    def test_load_extension_function_exists(self):
        """Test that _load_jupyter_server_extension exists."""
        from marimo_jupyter_extension.handlers import (
            _load_jupyter_server_extension,
        )

        assert callable(_load_jupyter_server_extension)

    def test_convert_handler_exists(self):
        """Test that ConvertHandler class exists."""
        from marimo_jupyter_extension.handlers import ConvertHandler

        assert ConvertHandler is not None


class TestConvertHandler:
    """Test suite for ConvertHandler."""

    def test_convert_handler_imports_convert_function(self):
        """Test that ConvertHandler imports convert_notebook_to_marimo."""
        from marimo_jupyter_extension import handlers

        # Verify the import exists in the handlers module
        assert hasattr(handlers, "convert_notebook_to_marimo")

    def test_handler_logic_with_missing_input(self):
        """Test validation logic for missing input path."""
        # Simulate the validation that happens in the handler
        data = json.loads(json.dumps({"output": "test.py"}))
        input_path = data.get("input")
        output_path = data.get("output")

        # Handler should validate these
        assert input_path is None
        assert output_path == "test.py"
        # Would return 400
        assert not (input_path and output_path)

    def test_handler_logic_with_valid_inputs(self):
        """Test validation logic for valid inputs."""
        # Simulate the validation that happens in the handler
        data = json.loads(
            json.dumps({"input": "test.ipynb", "output": "test.py"})
        )
        input_path = data.get("input")
        output_path = data.get("output")

        # Handler should validate these
        assert input_path == "test.ipynb"
        assert output_path == "test.py"
        # Would succeed
        assert input_path and output_path


class TestFindMarimoProxyState:
    """`_find_marimo_proxy_state` must work against both modern and
    legacy tornado router shapes."""

    def _modern_rule(self, pattern, kwargs):
        return SimpleNamespace(
            target_kwargs=kwargs,
            matcher=SimpleNamespace(regex=re.compile(pattern)),
        )

    def _modern_web_app(self, inner_rules):
        target = SimpleNamespace(rules=inner_rules)
        host_rule = SimpleNamespace(target=target)
        return SimpleNamespace(
            default_router=SimpleNamespace(rules=[host_rule])
        )

    def _legacy_spec(self, pattern, kwargs):
        spec = SimpleNamespace()
        spec.regex = re.compile(pattern)
        spec.kwargs = kwargs
        return spec

    def test_modern_router_returns_marimo_state(self):
        from marimo_jupyter_extension.handlers import (
            _find_marimo_proxy_state,
        )

        marimo_state = {"proc": "fake", "proc_lock": object()}
        web_app = self._modern_web_app(
            [
                self._modern_rule(r"^/other", {"state": {"x": 1}}),
                self._modern_rule(r"^/marimo/", {"state": marimo_state}),
            ]
        )
        assert _find_marimo_proxy_state(web_app) is marimo_state

    def test_modern_router_skips_specs_without_state(self):
        from marimo_jupyter_extension.handlers import (
            _find_marimo_proxy_state,
        )

        web_app = self._modern_web_app([self._modern_rule(r"^/marimo/", {})])
        assert _find_marimo_proxy_state(web_app) is None

    def test_legacy_handlers_returns_marimo_state(self):
        from marimo_jupyter_extension.handlers import (
            _find_marimo_proxy_state,
        )

        marimo_state = {"proc": "fake", "proc_lock": object()}
        # Legacy shape: no `default_router`, only `.handlers`
        web_app = SimpleNamespace(
            handlers=[
                (".*", [self._legacy_spec(r"^/other", {"state": {"x": 1}})]),
                (
                    ".*",
                    [self._legacy_spec(r"^/marimo/", {"state": marimo_state})],
                ),
            ]
        )
        assert _find_marimo_proxy_state(web_app) is marimo_state

    def test_returns_none_when_no_marimo_route(self):
        from marimo_jupyter_extension.handlers import (
            _find_marimo_proxy_state,
        )

        web_app = self._modern_web_app(
            [self._modern_rule(r"^/other", {"state": {"x": 1}})]
        )
        assert _find_marimo_proxy_state(web_app) is None


class TestHealthHandler:
    """`HealthHandler.get` reports liveness without spawning marimo."""

    def test_returns_false_when_no_proxy_state(self):
        from marimo_jupyter_extension import handlers
        from marimo_jupyter_extension.handlers import HealthHandler

        original = handlers._find_marimo_proxy_state
        handlers._find_marimo_proxy_state = lambda _app: None
        try:
            handler = _make_handler(
                HealthHandler, application=SimpleNamespace()
            )
            _run(handler, "get")
        finally:
            handlers._find_marimo_proxy_state = original

        handler.finish.assert_called_once_with({"process_alive": False})

    def test_returns_false_when_proc_missing(self):
        from marimo_jupyter_extension import handlers
        from marimo_jupyter_extension.handlers import HealthHandler

        original = handlers._find_marimo_proxy_state
        handlers._find_marimo_proxy_state = lambda _app: {}
        try:
            handler = _make_handler(
                HealthHandler, application=SimpleNamespace()
            )
            _run(handler, "get")
        finally:
            handlers._find_marimo_proxy_state = original

        handler.finish.assert_called_once_with({"process_alive": False})

    def test_returns_false_when_proc_not_running(self):
        from marimo_jupyter_extension import handlers
        from marimo_jupyter_extension.handlers import HealthHandler

        proc = SimpleNamespace(running=False)
        original = handlers._find_marimo_proxy_state
        handlers._find_marimo_proxy_state = lambda _app: {"proc": proc}
        try:
            handler = _make_handler(
                HealthHandler, application=SimpleNamespace()
            )
            _run(handler, "get")
        finally:
            handlers._find_marimo_proxy_state = original

        handler.finish.assert_called_once_with({"process_alive": False})

    def test_returns_false_when_proc_is_unmanaged_string(self):
        """jupyter-server-proxy uses the string 'process not managed'
        when it cannot supervise the process."""
        from marimo_jupyter_extension import handlers
        from marimo_jupyter_extension.handlers import HealthHandler

        original = handlers._find_marimo_proxy_state
        handlers._find_marimo_proxy_state = lambda _app: {
            "proc": "process not managed"
        }
        try:
            handler = _make_handler(
                HealthHandler, application=SimpleNamespace()
            )
            _run(handler, "get")
        finally:
            handlers._find_marimo_proxy_state = original

        handler.finish.assert_called_once_with({"process_alive": False})


class TestRestartHandler:
    """`RestartHandler.post` must SIGTERM (terminate) the marimo proc, not
    SIGKILL (kill) it.

    Under --sandbox marimo forwards SIGTERM to its inner uv process group;
    SIGKILL is uncatchable and orphans that child, which keeps the cached
    port and makes the next spawn collide. SIGKILL is only a last-resort
    fallback if SIGTERM is ignored past the grace period.
    """

    def _run_restart(self, proxy_state):
        from marimo_jupyter_extension import handlers
        from marimo_jupyter_extension.handlers import RestartHandler

        original = handlers._find_marimo_proxy_state
        handlers._find_marimo_proxy_state = lambda _app: proxy_state
        try:
            handler = _make_handler(
                RestartHandler, application=SimpleNamespace()
            )
            _run(handler, "post")
        finally:
            handlers._find_marimo_proxy_state = original
        return handler

    def test_uses_terminate_not_kill(self):
        calls = []

        class FakeProc:
            async def terminate(self):
                calls.append("terminate")

            async def kill(self):
                calls.append("kill")

        class NoopLock:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        proxy_state = {"proc": FakeProc(), "proc_lock": NoopLock()}
        handler = self._run_restart(proxy_state)

        assert calls == ["terminate"]  # SIGTERM, never SIGKILL
        assert "proc" not in proxy_state  # state cleared for respawn
        handler.finish.assert_called_once_with(
            {"success": True, "message": "Server restarting"}
        )

    def test_falls_back_to_kill_when_terminate_times_out(self):
        calls = []

        class FakeProc:
            async def terminate(self):
                calls.append("terminate")
                await asyncio.sleep(10)  # never returns within the grace

            async def kill(self):
                calls.append("kill")

        class NoopLock:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        proxy_state = {"proc": FakeProc(), "proc_lock": NoopLock()}
        with patch(
            "marimo_jupyter_extension.handlers._SIGTERM_GRACE_SECONDS",
            0.01,
        ):
            handler = self._run_restart(proxy_state)

        assert calls == ["terminate", "kill"]
        assert "proc" not in proxy_state
        handler.finish.assert_called_once_with(
            {"success": True, "message": "Server restarting"}
        )

    def test_returns_503_when_proxy_not_initialized(self):
        handler = self._run_restart(None)

        handler.set_status.assert_called_once_with(503)
        handler.finish.assert_called_once_with(
            {"success": False, "error": "Proxy not initialized yet"}
        )


class TestStripLeadingPep723:
    """`_strip_leading_pep723` drops a leading PEP 723 block so it can't
    collide with the venv block CreateStubHandler prepends."""

    def test_strips_leading_block(self):
        from marimo_jupyter_extension.handlers import _strip_leading_pep723

        text = (
            "# /// script\n"
            "# [tool.marimo.venv]\n"
            '# path = "/orig/venv"\n'
            "# ///\n"
            "\n"
            "import marimo\napp = marimo.App()\n"
        )
        assert (
            _strip_leading_pep723(text)
            == "import marimo\napp = marimo.App()\n"
        )

    def test_no_block_unchanged(self):
        from marimo_jupyter_extension.handlers import _strip_leading_pep723

        text = "import marimo\napp = marimo.App()\n"
        assert _strip_leading_pep723(text) == text

    def test_unterminated_block_left_intact(self):
        from marimo_jupyter_extension.handlers import _strip_leading_pep723

        # No closing fence: don't eat the whole template.
        text = "# /// script\n# path = x\nimport marimo\n"
        assert _strip_leading_pep723(text) == text


class TestSetNotebookVenv:
    def test_adds_metadata_to_notebook_without_block(self):
        from marimo_jupyter_extension.handlers import _set_notebook_venv

        content = "import marimo\napp = marimo.App()\n"
        updated = _set_notebook_venv(content, "/srv/envs/project")

        assert updated.startswith(
            "# /// script\n"
            "# [tool.marimo.venv]\n"
            '# path = "/srv/envs/project"\n'
            "# ///\n\n"
        )
        assert updated.endswith(content)

    def test_adds_metadata_after_shebang_and_encoding_cookie(self):
        from marimo_jupyter_extension.handlers import _set_notebook_venv

        content = (
            "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\nimport marimo\n"
        )

        updated = _set_notebook_venv(content, "/env")

        assert updated.startswith(
            "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n# /// script\n"
        )

    def test_preserves_crlf_line_endings(self):
        from marimo_jupyter_extension.handlers import _set_notebook_venv

        content = (
            "# /// script\r\n"
            "# [tool.marimo.venv]\r\n"
            '# path = "/old"\r\n'
            "# ///\r\n"
            "import marimo\r\n"
        )

        updated = _set_notebook_venv(content, "/new")

        assert '# path = "/new"\r\n' in updated
        assert updated.count("\n") == updated.count("\r\n")

    def test_updates_path_without_reformatting_other_metadata(self):
        from marimo_jupyter_extension.handlers import _set_notebook_venv

        content = (
            "# /// script\n"
            '# dependencies = ["polars"]\n'
            "# [tool.marimo.venv]\n"
            '# path = "/old/environment"\n'
            "# writable = true\n"
            "# [tool.marimo.runtime]\n"
            "# output_max_bytes = 10_000 # Keep this comment.\n"
            "# ///\n"
            "import marimo\n"
        )

        updated = _set_notebook_venv(content, "/new/environment")

        assert '# path = "/new/environment"\n' in updated
        assert '# path = "/old/environment"\n' not in updated
        assert '# dependencies = ["polars"]\n' in updated
        assert "# writable = true\n" in updated
        assert "# output_max_bytes = 10_000 # Keep this comment.\n" in updated

    def test_adds_venv_section_to_existing_metadata(self):
        from marimo_jupyter_extension.handlers import _set_notebook_venv

        content = (
            '# /// script\n# dependencies = ["polars"]\n# ///\nimport marimo\n'
        )

        updated = _set_notebook_venv(content, "/env")

        assert '# dependencies = ["polars"]\n' in updated
        assert "# [tool.marimo.venv]\n" in updated
        assert '# path = "/env"\n' in updated
        assert updated.endswith("# ///\nimport marimo\n")

    def test_clear_path_preserves_other_venv_settings(self):
        from marimo_jupyter_extension.handlers import _set_notebook_venv

        content = (
            "# /// script\n"
            "# [tool.marimo.venv]\n"
            '# path = "/env"\n'
            "# writable = true\n"
            "# ///\n"
            "import marimo\n"
        )

        updated = _set_notebook_venv(content, None)

        assert "# [tool.marimo.venv]\n" in updated
        assert "# writable = true\n" in updated
        assert "# path =" not in updated

    def test_clear_path_leaves_other_tables_untouched(self):
        from marimo_jupyter_extension.handlers import _set_notebook_venv

        content = (
            "# /// script\n"
            '# dependencies = ["polars"]\n'
            "# [tool.marimo.venv]\n"
            '# path = "/env"\n'
            "# [tool.marimo.runtime]\n"
            '# on_cell_change = "autorun"\n'
            "# ///\n"
            "import marimo\n"
        )

        updated = _set_notebook_venv(content, None)

        assert "# path =" not in updated
        assert "# [tool.marimo.runtime]\n" in updated
        assert '# dependencies = ["polars"]\n' in updated

    def test_writes_windows_environment_path(self):
        from marimo_jupyter_extension.handlers import _set_notebook_venv

        updated = _set_notebook_venv("import marimo\n", r"C:\Users\me\venv")

        assert '# path = "C:\\\\Users\\\\me\\\\venv"\n' in updated

    def test_rejects_multiple_metadata_blocks(self):
        from marimo_jupyter_extension.handlers import _set_notebook_venv

        content = "# /// script\n# ///\n# /// script\n# ///\nimport marimo\n"

        with pytest.raises(ValueError, match="Multiple PEP 723"):
            _set_notebook_venv(content, "/env")

    def test_reads_configured_path(self):
        from marimo_jupyter_extension.handlers import _get_notebook_venv

        content = (
            "# /// script\n"
            "# [tool.marimo.venv]\n"
            "# path = '/srv/envs/project'\n"
            "# writable = true\n"
            "# ///\n"
            "import marimo\n"
        )

        assert _get_notebook_venv(content) == "/srv/envs/project"

    @pytest.mark.parametrize(
        "venv_config",
        [
            'venv.path = "/srv/envs/project"',
            'venv = { path = "/srv/envs/project" }',
        ],
    )
    def test_reads_equivalent_toml_spellings(self, venv_config):
        from marimo_jupyter_extension.handlers import _get_notebook_venv

        content = f"# /// script\n# [tool.marimo]\n# {venv_config}\n# ///\n"

        assert _get_notebook_venv(content) == "/srv/envs/project"

    @pytest.mark.parametrize(
        "venv_config",
        [
            'venv.path = "/old"',
            'venv = { path = "/old", writable = true }',
        ],
    )
    def test_updates_equivalent_toml_spellings(self, venv_config):
        from marimo_jupyter_extension.handlers import (
            _get_notebook_venv,
            _set_notebook_venv,
        )

        content = f"# /// script\n# [tool.marimo]\n# {venv_config}\n# ///\n"

        updated = _set_notebook_venv(content, "/new")

        assert _get_notebook_venv(updated) == "/new"
        if "writable" in content:
            assert "writable = true" in updated

    def test_array_table_path_is_not_treated_as_venv_path(self):
        from marimo_jupyter_extension.handlers import (
            _get_notebook_venv,
            _set_notebook_venv,
        )

        content = (
            "# /// script\n"
            "# [tool.marimo.venv]\n"
            '# path = "/old"\n'
            "# [[tool.uv.sources]]\n"
            '# path = "/vendor/wheel"\n'
            "# editable = true\n"
            "# ///\n"
        )

        updated = _set_notebook_venv(content, "/new")

        assert _get_notebook_venv(updated) == "/new"
        assert '# path = "/vendor/wheel"\n' in updated
        assert "# editable = true\n" in updated

    def test_rejects_malformed_toml(self):
        from marimo_jupyter_extension.handlers import _set_notebook_venv

        content = "# /// script\n# dependencies = [\n# ///\n"

        with pytest.raises(ValueError, match="Invalid PEP 723 TOML"):
            _set_notebook_venv(content, "/new")

    def test_rejects_non_table_venv_config(self):
        from marimo_jupyter_extension.handlers import _set_notebook_venv

        content = (
            '# /// script\n# [tool.marimo]\n# venv = "not-a-table"\n# ///\n'
        )

        with pytest.raises(ValueError, match="must be a table"):
            _set_notebook_venv(content, "/new")

    def test_reads_json_quoted_path_with_comment(self):
        from marimo_jupyter_extension.handlers import _get_notebook_venv

        content = (
            "# /// script\n"
            "# [tool.marimo.venv]\n"
            '# path = "/srv/envs/project" # selected in JupyterLab\n'
            "# ///\n"
        )

        assert _get_notebook_venv(content) == "/srv/envs/project"


class TestResolveKernelEnvironment:
    def test_reads_sys_prefix_from_selected_interpreter(self):
        from marimo_jupyter_extension.handlers import (
            _resolve_kernel_environment,
        )

        manager = MagicMock()
        manager.get_kernel_spec.return_value = SimpleNamespace(
            language="python",
            argv=[sys.executable, "-m", "ipykernel_launcher"],
            env={},
        )

        prefix = asyncio.run(_resolve_kernel_environment(manager, "python"))

        assert prefix == sys.prefix
        manager.get_kernel_spec.assert_called_once_with("python")

    def test_rejects_non_python_kernel(self):
        from marimo_jupyter_extension.handlers import (
            _resolve_kernel_environment,
        )

        manager = MagicMock()
        manager.get_kernel_spec.return_value = SimpleNamespace(
            language="julia", argv=["julia"], env={}
        )

        with pytest.raises(ValueError, match="not a Python environment"):
            asyncio.run(_resolve_kernel_environment(manager, "julia"))

    @pytest.mark.skipif(os.name != "posix", reason="uses a POSIX shell")
    def test_timeout_kills_wrapper_process_group(self):
        from marimo_jupyter_extension.handlers import (
            _resolve_kernel_environment,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            process_group_file = Path(tmpdir) / "process-group"
            wrapper = Path(tmpdir) / "python-wrapper"
            wrapper.write_text(
                f"#!/bin/sh\necho $$ > {process_group_file}\nsleep 30\n"
            )
            wrapper.chmod(0o755)
            manager = MagicMock()
            manager.get_kernel_spec.return_value = SimpleNamespace(
                language="python", argv=[str(wrapper)], env={}
            )

            started = time.monotonic()
            with pytest.raises(ValueError, match="inspection timed out"):
                asyncio.run(
                    _resolve_kernel_environment(manager, "wrapped-python")
                )
            elapsed = time.monotonic() - started

            assert elapsed < 8
            process_group = int(process_group_file.read_text())
            for _attempt in range(100):
                try:
                    os.killpg(process_group, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.01)
            else:
                pytest.fail("wrapper process group survived timeout")


class TestResolveKernelEnvironmentHandler:
    def _build(self, body):
        from marimo_jupyter_extension.handlers import (
            ResolveKernelEnvironmentHandler,
        )

        application = SimpleNamespace(
            settings={"kernel_spec_manager": MagicMock()}
        )
        handler = _make_handler(
            ResolveKernelEnvironmentHandler, application=application
        )
        handler.request = SimpleNamespace(body=json.dumps(body).encode())
        return handler

    def test_resolves_configured_kernel(self):
        handler = self._build({"kernel": "project"})

        with patch(
            "marimo_jupyter_extension.handlers._resolve_kernel_environment",
            new=AsyncMock(return_value="/srv/envs/project"),
        ) as resolve:
            _run(handler, "post")

        resolve.assert_awaited_once_with(
            handler.kernel_spec_manager, "project"
        )
        handler.finish.assert_called_once_with(
            {"success": True, "venv": "/srv/envs/project"}
        )

    def test_rejects_missing_kernel(self):
        handler = self._build({})

        _run(handler, "post")

        handler.set_status.assert_called_once_with(400)
        handler.finish.assert_called_once_with(
            {"success": False, "error": "Missing kernel"}
        )


class TestHasMarimoAppMarkers:
    def test_uses_marimo_app_markers(self):
        from marimo_jupyter_extension.handlers import _has_marimo_app_markers

        assert _has_marimo_app_markers(
            "import marimo\napp = marimo.App(width='medium')\n"
        )

    def test_requires_marimo_import_marker(self):
        from marimo_jupyter_extension.handlers import _has_marimo_app_markers

        assert not _has_marimo_app_markers("app = marimo.App()\n")

    def test_import_marker_must_not_be_indented(self):
        from marimo_jupyter_extension.handlers import _has_marimo_app_markers

        assert not _has_marimo_app_markers(
            "if True:\n    import marimo\n    marimo.App()\n"
        )

    def test_import_marker_requires_exact_module_name(self):
        from marimo_jupyter_extension.handlers import _has_marimo_app_markers

        assert not _has_marimo_app_markers(
            "import marimo_tools\nmarimo.App()\n"
        )

    def test_requires_marimo_app_marker(self):
        from marimo_jupyter_extension.handlers import _has_marimo_app_markers

        assert not _has_marimo_app_markers("import marimo\nprint('hello')\n")


class TestSetVenvHandler:
    def _build(
        self,
        body,
        *,
        content="import marimo\napp = marimo.App()\n",
    ):
        from marimo_jupyter_extension.handlers import SetVenvHandler

        contents_manager = MagicMock()
        contents_manager.get.return_value = {
            "type": "file",
            "format": "text",
            "content": content,
        }
        application = SimpleNamespace(
            settings={"contents_manager": contents_manager}
        )
        handler = _make_handler(SetVenvHandler, application=application)
        request_body = (
            body if isinstance(body, bytes) else json.dumps(body).encode()
        )
        handler.request = SimpleNamespace(body=request_body)
        return handler, contents_manager

    def test_updates_notebook(self):
        handler, contents_manager = self._build(
            {
                "path": "notebook.py",
                "venv": "/srv/envs/project",
            }
        )

        _run(handler, "post")

        handler.finish.assert_called_once_with(
            {
                "success": True,
                "path": "notebook.py",
                "venv": "/srv/envs/project",
            }
        )
        saved_model, saved_path = contents_manager.save.call_args.args
        assert saved_path == "notebook.py"
        assert saved_model["type"] == "file"
        assert saved_model["format"] == "text"
        assert '# path = "/srv/envs/project"\n' in saved_model["content"]

    def test_missing_notebook_returns_404(self):
        from tornado import web

        handler, contents_manager = self._build(
            {"path": "missing.py", "venv": None}
        )
        contents_manager.get.side_effect = web.HTTPError(404)

        _run(handler, "post")

        handler.set_status.assert_called_once_with(404)
        handler.finish.assert_called_once_with(
            {"success": False, "error": "Notebook not found"}
        )

    def test_contents_manager_rejects_path_outside_root(self):
        from tornado import web

        handler, contents_manager = self._build(
            {"path": "../outside.py", "venv": None}
        )
        contents_manager.get.side_effect = web.HTTPError(
            403, "Path is outside the contents root"
        )

        _run(handler, "post")

        handler.set_status.assert_called_once_with(403)
        handler.finish.assert_called_once_with(
            {
                "success": False,
                "error": "Path is outside the contents root",
            }
        )
        contents_manager.save.assert_not_called()

    def test_malformed_json_returns_400(self):
        handler, _contents_manager = self._build(b"{not-json")

        _run(handler, "post")

        handler.set_status.assert_called_once_with(400)
        handler.finish.assert_called_once_with(
            {"success": False, "error": "Invalid JSON body"}
        )

    def test_json_body_must_be_an_object(self):
        handler, _contents_manager = self._build([])

        _run(handler, "post")

        handler.set_status.assert_called_once_with(400)
        handler.finish.assert_called_once_with(
            {"success": False, "error": "JSON body must be an object"}
        )

    def test_rejects_non_python_files(self):
        handler, _contents_manager = self._build(
            {"path": "notebook.md", "venv": None}
        )

        _run(handler, "post")

        handler.set_status.assert_called_once_with(400)
        handler.finish.assert_called_once_with(
            {
                "success": False,
                "error": "Environment selection is only supported for Python notebooks",
            }
        )

    def test_rejects_python_file_that_is_not_a_marimo_notebook(self):
        handler, contents_manager = self._build(
            {"path": "script.py", "venv": "/srv/env/bin/python"},
            content="print('ordinary Python')\n",
        )

        _run(handler, "post")

        handler.set_status.assert_called_once_with(400)
        handler.finish.assert_called_once_with(
            {"success": False, "error": "File is not a marimo notebook"}
        )
        contents_manager.save.assert_not_called()

    def test_invalid_toml_returns_400_without_saving(self):
        handler, contents_manager = self._build(
            {"path": "notebook.py", "venv": "/srv/envs/project"},
            content=(
                "# /// script\n"
                "# dependencies = [\n"
                "# ///\n"
                "import marimo\n"
                "app = marimo.App()\n"
            ),
        )

        _run(handler, "post")

        handler.set_status.assert_called_once_with(400)
        assert (
            "Invalid PEP 723 TOML" in handler.finish.call_args.args[0]["error"]
        )
        contents_manager.save.assert_not_called()

    def test_get_identifies_non_marimo_python_file(self):
        handler, _contents_manager = self._build(
            {}, content="print('ordinary Python')\n"
        )
        handler.get_argument = MagicMock(return_value="script.py")

        _run(handler, "get")

        handler.finish.assert_called_once_with(
            {"success": True, "isMarimo": False, "venv": None}
        )

    def test_get_returns_current_environment(self):
        handler, contents_manager = self._build(
            {},
            content=(
                "# /// script\n"
                "# [tool.marimo.venv]\n"
                '# path = "/srv/envs/project"\n'
                "# ///\n"
                "import marimo\n"
                "app = marimo.App()\n"
            ),
        )
        handler.get_argument = MagicMock(return_value="notebook.py")

        _run(handler, "get")

        handler.finish.assert_called_once_with(
            {
                "success": True,
                "isMarimo": True,
                "venv": "/srv/envs/project",
            }
        )
        contents_manager.get.assert_called_once_with(
            path="notebook.py", type="file", format="text", content=True
        )


class TestCreateStubHandler:
    """`CreateStubHandler.post` writes a marimo notebook stub to disk.

    When `c.MarimoProxyConfig.default_file` is configured, the cached
    template content (stored on web_app.settings by
    _load_jupyter_server_extension) is written verbatim; otherwise the
    handler emits the built-in boilerplate.
    """

    def _build(self, body, settings=None):
        from marimo_jupyter_extension.handlers import CreateStubHandler

        app = SimpleNamespace(settings=settings or {})
        handler = _make_handler(CreateStubHandler, application=app)
        handler.request = SimpleNamespace(body=json.dumps(body).encode())
        return handler

    def test_writes_default_boilerplate_when_no_template(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stub_path = str(Path(tmpdir) / "out.py")
            handler = self._build({"path": stub_path})

            _run(handler, "post")

            handler.finish.assert_called_once_with(
                {"success": True, "path": stub_path}
            )
            content = Path(stub_path).read_text()
            assert "import marimo" in content
            assert "__generated_with" in content
            assert 'app = marimo.App(width="medium")' in content
            assert 'if __name__ == "__main__":' in content

    def test_uses_cached_template_verbatim(self):
        from marimo_jupyter_extension.handlers import _DEFAULT_FILE_SETTING

        template = (
            "import marimo\n\n"
            '__generated_with = "0.99.0"\n'
            'app = marimo.App(width="medium")\n\n'
            "with app.setup(hide_code=True):\n"
            "    from my_pkg import helper  # noqa: F401\n\n"
            'if __name__ == "__main__":\n'
            "    app.run()\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            stub_path = str(Path(tmpdir) / "out.py")
            handler = self._build(
                {"path": stub_path},
                settings={_DEFAULT_FILE_SETTING: template},
            )

            _run(handler, "post")

            handler.finish.assert_called_once_with(
                {"success": True, "path": stub_path}
            )
            assert Path(stub_path).read_text() == template

    def test_cached_template_does_not_substitute_version(self):
        """The cached template is emitted verbatim; the running marimo
        version is *not* spliced into __generated_with."""
        from marimo_jupyter_extension.handlers import _DEFAULT_FILE_SETTING

        template = (
            "import marimo\n"
            '__generated_with = "0.0.0-template"\n'
            'app = marimo.App(width="medium")\n'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            stub_path = str(Path(tmpdir) / "out.py")
            handler = self._build(
                {"path": stub_path},
                settings={_DEFAULT_FILE_SETTING: template},
            )
            with patch(
                "marimo_jupyter_extension.version_info.get_marimo_version",
                return_value="9.9.9",
            ):
                _run(handler, "post")

            content = Path(stub_path).read_text()
            assert '"0.0.0-template"' in content
            assert "9.9.9" not in content

    def test_pep723_header_prepended_to_cached_template(self):
        from marimo_jupyter_extension.handlers import _DEFAULT_FILE_SETTING

        template = "import marimo\napp = marimo.App()\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            stub_path = str(Path(tmpdir) / "out.py")
            handler = self._build(
                {
                    "path": stub_path,
                    "venv": "/srv/envs/proj",
                },
                settings={_DEFAULT_FILE_SETTING: template},
            )

            _run(handler, "post")

            content = Path(stub_path).read_text()
            assert content.startswith("# /// script\n")
            assert '# path = "/srv/envs/proj"\n' in content
            assert content.endswith(template)

    def test_windows_venv_path_is_toml_escaped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stub_path = str(Path(tmpdir) / "out.py")
            handler = self._build(
                {
                    "path": stub_path,
                    "venv": r"C:\Users\me\venv",
                }
            )

            _run(handler, "post")

            content = Path(stub_path).read_text()
            assert '# path = "C:\\\\Users\\\\me\\\\venv"\n' in content

    def test_no_duplicate_pep723_when_template_has_block(self, clean_env):
        """A template carrying its own PEP 723 block + a venv request
        must not yield two blocks (uv rejects multiple metadata blocks).

        Exercises the full path: _load_default_file strips the template's
        leading block, then CreateStubHandler prepends the request venv.
        """
        from marimo_jupyter_extension import config as config_mod
        from marimo_jupyter_extension.handlers import (
            _DEFAULT_FILE_SETTING,
            _load_default_file,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            template = Path(tmpdir) / "tmpl.py"
            template.write_text(
                "# /// script\n"
                "# [tool.marimo.venv]\n"
                '# path = "/orig/venv"\n'
                "# ///\n"
                "\n"
                "import marimo\napp = marimo.App()\n"
            )
            traitlets_config = config_mod.MarimoProxyConfig()
            traitlets_config.default_file = str(template)
            server_app = MagicMock()
            with patch(
                "marimo_jupyter_extension.config.get_config",
                return_value=config_mod.get_config(traitlets_config),
            ):
                cached = _load_default_file(server_app)

            stub_path = str(Path(tmpdir) / "out.py")
            handler = self._build(
                {"path": stub_path, "venv": "/srv/envs/proj"},
                settings={_DEFAULT_FILE_SETTING: cached},
            )

            _run(handler, "post")

            content = Path(stub_path).read_text()
            assert content.count("# /// script") == 1
            # The request-time venv wins; the template's stale path is gone.
            assert '# path = "/srv/envs/proj"' in content
            assert '# path = "/orig/venv"' not in content

    def test_missing_path_returns_400(self):
        handler = self._build({})

        _run(handler, "post")

        handler.set_status.assert_called_once_with(400)
        handler.finish.assert_called_once_with(
            {"success": False, "error": "Missing path"}
        )

    def test_rejects_markdown_filename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stub_path = Path(tmpdir) / "out.md"
            handler = self._build({"path": str(stub_path)})

            _run(handler, "post")

            handler.set_status.assert_called_once_with(400)
            handler.finish.assert_called_once_with(
                {
                    "success": False,
                    "error": "Notebook filename must end in .py",
                }
            )
            assert not stub_path.exists()


class TestLoadDefaultFile:
    """`_load_default_file` reads the configured template once."""

    def test_returns_none_when_unconfigured(self, clean_env):
        from marimo_jupyter_extension.handlers import _load_default_file

        server_app = MagicMock()
        assert _load_default_file(server_app) is None

    def test_reads_file_contents(self, clean_env):
        from marimo_jupyter_extension import config as config_mod
        from marimo_jupyter_extension.handlers import _load_default_file

        with tempfile.TemporaryDirectory() as tmpdir:
            template = Path(tmpdir) / "tmpl.py"
            template.write_text("import marimo\napp = marimo.App()\n")

            traitlets_config = config_mod.MarimoProxyConfig()
            traitlets_config.default_file = str(template)

            server_app = MagicMock()
            with patch(
                "marimo_jupyter_extension.config.get_config",
                return_value=config_mod.get_config(traitlets_config),
            ):
                content = _load_default_file(server_app)

            assert content == "import marimo\napp = marimo.App()\n"

    def test_strips_leading_pep723_block(self, clean_env):
        """A leading PEP 723 block is removed at load time so it can't
        duplicate the venv block CreateStubHandler prepends."""
        from marimo_jupyter_extension import config as config_mod
        from marimo_jupyter_extension.handlers import _load_default_file

        with tempfile.TemporaryDirectory() as tmpdir:
            template = Path(tmpdir) / "tmpl.py"
            template.write_text(
                "# /// script\n"
                '# path = "/orig/venv"\n'
                "# ///\n"
                "\n"
                "import marimo\napp = marimo.App()\n"
            )
            traitlets_config = config_mod.MarimoProxyConfig()
            traitlets_config.default_file = str(template)
            server_app = MagicMock()
            with patch(
                "marimo_jupyter_extension.config.get_config",
                return_value=config_mod.get_config(traitlets_config),
            ):
                content = _load_default_file(server_app)

            assert "# /// script" not in content
            assert content == "import marimo\napp = marimo.App()\n"

    def test_raises_on_missing_file(self, clean_env):
        from marimo_jupyter_extension.config import MarimoProxyConfig
        from marimo_jupyter_extension.handlers import _load_default_file

        traitlets_config = MarimoProxyConfig()
        traitlets_config.default_file = "/nonexistent/template.py"

        from marimo_jupyter_extension import config as config_mod

        server_app = MagicMock()
        with patch(
            "marimo_jupyter_extension.config.get_config",
            return_value=config_mod.get_config(traitlets_config),
        ):
            import pytest

            with pytest.raises(FileNotFoundError):
                _load_default_file(server_app)

    def test_directory_path_raises_with_actionable_log(self, clean_env):
        """A directory (and other non-FileNotFound read errors) must
        still surface the actionable c.MarimoProxyConfig.default_file
        pointer, not a bare traceback."""
        import pytest

        from marimo_jupyter_extension import config as config_mod
        from marimo_jupyter_extension.handlers import _load_default_file

        with tempfile.TemporaryDirectory() as tmpdir:
            traitlets_config = config_mod.MarimoProxyConfig()
            traitlets_config.default_file = tmpdir  # a directory, not a file
            server_app = MagicMock()
            with patch(
                "marimo_jupyter_extension.config.get_config",
                return_value=config_mod.get_config(traitlets_config),
            ):
                with pytest.raises(IsADirectoryError):
                    _load_default_file(server_app)

            assert server_app.log.error.called
            log_fmt = server_app.log.error.call_args[0][0]
            assert "c.MarimoProxyConfig.default_file" in log_fmt


class TestLoadServerExtension:
    """Test suite for _load_jupyter_server_extension."""

    def _make_server_app(self):
        server_app = MagicMock()
        server_app.web_app.settings = {"base_url": "/"}
        return server_app

    def test_populates_version_keys_when_marimo_installed(self):
        from marimo_jupyter_extension.handlers import (
            _load_jupyter_server_extension,
        )

        server_app = self._make_server_app()
        with patch(
            "marimo_jupyter_extension.version_info.get_marimo_version",
            return_value="0.23.1",
        ):
            _load_jupyter_server_extension(server_app)

        page_config = server_app.web_app.settings["page_config_data"]
        assert page_config["marimoVersion"] == "0.23.1"
        assert page_config["marimoExtensionVersion"]
        server_app.web_app.add_handlers.assert_called_once()
        routes = server_app.web_app.add_handlers.call_args.args[1]
        assert any(
            path == "/marimo-tools/resolve-kernel"
            and handler.__name__ == "ResolveKernelEnvironmentHandler"
            for path, handler in routes
        )
        server_app.log.info.assert_called_once()

    def test_marimo_version_falls_back_to_empty_string(self):
        from marimo_jupyter_extension.handlers import (
            _load_jupyter_server_extension,
        )

        server_app = self._make_server_app()
        with patch(
            "marimo_jupyter_extension.version_info.get_marimo_version",
            return_value=None,
        ):
            _load_jupyter_server_extension(server_app)

        page_config = server_app.web_app.settings["page_config_data"]
        assert page_config["marimoVersion"] == ""
        assert page_config["marimoExtensionVersion"]

    def test_preserves_existing_page_config_data(self):
        from marimo_jupyter_extension.handlers import (
            _load_jupyter_server_extension,
        )

        server_app = self._make_server_app()
        server_app.web_app.settings["page_config_data"] = {"existing": "value"}
        with patch(
            "marimo_jupyter_extension.version_info.get_marimo_version",
            return_value="0.23.1",
        ):
            _load_jupyter_server_extension(server_app)

        page_config = server_app.web_app.settings["page_config_data"]
        assert page_config["existing"] == "value"
        assert page_config["marimoVersion"] == "0.23.1"

    def test_aborts_handler_registration_when_default_file_missing(
        self, clean_env
    ):
        """The template read must run *before* add_handlers. If the
        operator points default_file at a missing path, the extension
        load aborts with FileNotFoundError and no routes get
        registered — preventing CreateStubHandler from silently falling
        back to default boilerplate."""
        import pytest

        from marimo_jupyter_extension import config as config_mod
        from marimo_jupyter_extension.config import MarimoProxyConfig
        from marimo_jupyter_extension.handlers import (
            _load_jupyter_server_extension,
        )

        traitlets_config = MarimoProxyConfig()
        traitlets_config.default_file = "/nonexistent/template.py"

        server_app = self._make_server_app()
        with patch(
            "marimo_jupyter_extension.config.get_config",
            return_value=config_mod.get_config(traitlets_config),
        ):
            with pytest.raises(FileNotFoundError):
                _load_jupyter_server_extension(server_app)

        server_app.web_app.add_handlers.assert_not_called()
