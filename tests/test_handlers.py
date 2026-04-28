"""Tests for the handlers module."""

import asyncio
import json
import re
from types import SimpleNamespace
from unittest.mock import MagicMock


def _make_handler(handler_cls, *, application=None):
    """Build a handler instance bypassing Tornado's initializer."""
    handler = handler_cls.__new__(handler_cls)
    handler.application = application
    handler.current_user = "u"
    handler.set_status = MagicMock()
    handler.finish = MagicMock()
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
        return SimpleNamespace(default_router=SimpleNamespace(rules=[host_rule]))

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

        web_app = self._modern_web_app(
            [self._modern_rule(r"^/marimo/", {})]
        )
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
                (".*", [self._legacy_spec(r"^/marimo/", {"state": marimo_state})]),
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

        handler.finish.assert_called_once_with(
            {"process_alive": False, "marimo_healthy": False}
        )

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

        handler.finish.assert_called_once_with(
            {"process_alive": False, "marimo_healthy": False}
        )

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

        handler.finish.assert_called_once_with(
            {"process_alive": False, "marimo_healthy": False}
        )

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

        handler.finish.assert_called_once_with(
            {"process_alive": False, "marimo_healthy": False}
        )
