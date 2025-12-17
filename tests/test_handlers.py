"""Tests for the handlers module."""

import pytest


class TestHandlers:
    """Test the handlers module."""

    def test_module_importable(self):
        """Test that the handlers module is importable."""
        from jupyter_marimo_proxy import handlers

        assert handlers is not None

    def test_extension_points_function_exists(self):
        """Test that _jupyter_server_extension_points exists."""
        from jupyter_marimo_proxy.handlers import _jupyter_server_extension_points

        result = _jupyter_server_extension_points()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["module"] == "jupyter_marimo_proxy.handlers"

    def test_load_extension_function_exists(self):
        """Test that _load_jupyter_server_extension exists."""
        from jupyter_marimo_proxy.handlers import _load_jupyter_server_extension

        assert callable(_load_jupyter_server_extension)

    def test_convert_handler_exists(self):
        """Test that ConvertHandler class exists."""
        from jupyter_marimo_proxy.handlers import ConvertHandler

        assert ConvertHandler is not None
