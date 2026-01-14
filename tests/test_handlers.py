"""Tests for the handlers module."""

import pytest


class TestHandlers:
    """Test the handlers module."""

    def test_module_importable(self):
        """Test that the handlers module is importable."""
        from marimo_jupyter_extension import handlers

        assert handlers is not None

    def test_extension_points_function_exists(self):
        """Test that _jupyter_server_extension_points exists."""
        from marimo_jupyter_extension.handlers import _jupyter_server_extension_points

        result = _jupyter_server_extension_points()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["module"] == "marimo_jupyter_extension.handlers"

    def test_load_extension_function_exists(self):
        """Test that _load_jupyter_server_extension exists."""
        from marimo_jupyter_extension.handlers import _load_jupyter_server_extension

        assert callable(_load_jupyter_server_extension)

    def test_convert_handler_exists(self):
        """Test that ConvertHandler class exists."""
        from marimo_jupyter_extension.handlers import ConvertHandler

        assert ConvertHandler is not None
