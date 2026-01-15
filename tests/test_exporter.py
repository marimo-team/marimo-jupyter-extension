"""Tests for the marimo nbconvert exporter."""

from unittest.mock import MagicMock, patch

import pytest


class TestMarimoExporter:
    """Test suite for MarimoExporter class."""

    def test_exporter_importable(self):
        """Test that MarimoExporter is importable."""
        from marimo_jupyter_extension.exporter import MarimoExporter

        assert MarimoExporter is not None

    def test_exporter_attributes(self):
        """Test that exporter has correct attributes."""
        from marimo_jupyter_extension.exporter import MarimoExporter

        assert MarimoExporter.export_from_notebook == "marimo"
        assert MarimoExporter.output_mimetype == "text/x-python"

    def test_file_extension_default(self):
        """Test that default file extension is .py."""
        from marimo_jupyter_extension.exporter import MarimoExporter

        exporter = MarimoExporter()
        assert exporter.file_extension == ".py"

    def test_from_notebook_node_successful_conversion(
        self, clean_env, mock_marimo_in_path
    ):
        """Test successful notebook conversion."""
        from marimo_jupyter_extension.exporter import MarimoExporter

        exporter = MarimoExporter()

        # Create a minimal notebook node
        notebook = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["print('hello')"],
                    "metadata": {},
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        with patch(
            "marimo_jupyter_extension.exporter.convert_notebook_to_marimo"
        ) as mock_convert:
            # Mock successful conversion
            def mock_convert_side_effect(input_path, output_path):
                # Simulate writing the output file
                with open(output_path, "w") as f:
                    f.write("# marimo notebook\nimport marimo as mo\n")

            mock_convert.side_effect = mock_convert_side_effect

            output, resources = exporter.from_notebook_node(notebook)

            assert isinstance(output, str)
            assert "marimo" in output
            assert isinstance(resources, dict)
            assert resources["output_extension"] == ".py"
            mock_convert.assert_called_once()

    def test_from_notebook_node_conversion_failure(
        self, clean_env, mock_marimo_in_path
    ):
        """Test that conversion failure raises RuntimeError."""
        from marimo_jupyter_extension.exporter import MarimoExporter

        exporter = MarimoExporter()

        notebook = {
            "cells": [],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        with patch(
            "marimo_jupyter_extension.exporter.convert_notebook_to_marimo"
        ) as mock_convert:
            mock_convert.side_effect = RuntimeError(
                "marimo convert failed: test error"
            )

            with pytest.raises(RuntimeError) as exc_info:
                exporter.from_notebook_node(notebook)

            assert "marimo convert failed" in str(exc_info.value)

    def test_from_notebook_node_cleanup_on_success(
        self, clean_env, mock_marimo_in_path
    ):
        """Test that temporary files are cleaned up on success."""
        from marimo_jupyter_extension.exporter import MarimoExporter

        exporter = MarimoExporter()

        notebook = {
            "cells": [],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        with patch(
            "marimo_jupyter_extension.exporter.convert_notebook_to_marimo"
        ) as mock_convert:
            with patch("marimo_jupyter_extension.exporter.Path") as mock_path:
                mock_unlink = MagicMock()
                mock_path.return_value.unlink = mock_unlink

                def mock_convert_side_effect(input_path, output_path):
                    # Simulate successful conversion
                    pass

                mock_convert.side_effect = mock_convert_side_effect

                try:
                    exporter.from_notebook_node(notebook)
                except Exception:
                    pass

                # Verify unlink was called (cleanup happened)
                assert mock_unlink.called

    def test_from_notebook_node_cleanup_on_failure(
        self, clean_env, mock_marimo_in_path
    ):
        """Test that temporary files are cleaned up even on failure."""
        from marimo_jupyter_extension.exporter import MarimoExporter

        exporter = MarimoExporter()

        notebook = {
            "cells": [],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        with patch(
            "marimo_jupyter_extension.exporter.convert_notebook_to_marimo"
        ) as mock_convert:
            with patch("marimo_jupyter_extension.exporter.Path") as mock_path:
                mock_unlink = MagicMock()
                mock_path.return_value.unlink = mock_unlink

                mock_convert.side_effect = RuntimeError("conversion failed")

                with pytest.raises(RuntimeError):
                    exporter.from_notebook_node(notebook)

                # Verify unlink was called despite the error
                assert mock_unlink.called

    def test_from_notebook_node_with_resources(
        self, clean_env, mock_marimo_in_path
    ):
        """Test that resources dict is preserved and returned."""
        from marimo_jupyter_extension.exporter import MarimoExporter

        exporter = MarimoExporter()

        notebook = {
            "cells": [],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        resources = {"custom_key": "custom_value"}

        with patch(
            "marimo_jupyter_extension.exporter.convert_notebook_to_marimo"
        ) as mock_convert:

            def mock_convert_side_effect(input_path, output_path):
                with open(output_path, "w") as f:
                    f.write("# converted")

            mock_convert.side_effect = mock_convert_side_effect

            output, returned_resources = exporter.from_notebook_node(
                notebook, resources=resources
            )

            assert returned_resources is resources
            assert returned_resources.get("custom_key") == "custom_value"
