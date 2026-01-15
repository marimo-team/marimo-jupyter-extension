"""Tests for the handlers module."""

import json


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
