"""Tests for notebook conversion module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestConvertNotebookToMarimo:
    """Test suite for convert_notebook_to_marimo() function."""

    def test_successful_conversion(self, clean_env, mock_marimo_in_path):
        """Test successful conversion calls marimo convert with correct
        arguments."""
        from jupyter_marimo_proxy.convert import convert_notebook_to_marimo

        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "test.ipynb"
            output_file = Path(tmpdir) / "test.py"

            # Create a minimal notebook file
            notebook = {
                "cells": [],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 2,
            }
            input_file.write_text(json.dumps(notebook))

            # Mock subprocess.run to simulate successful conversion
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                # Simulate marimo creating the output file
                output_file.write_text("# marimo notebook\n")

                convert_notebook_to_marimo(str(input_file), str(output_file))

                # Verify subprocess.run was called with correct arguments
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert "convert" in call_args
                assert str(input_file) in call_args
                assert "-o" in call_args
                assert str(output_file) in call_args

    def test_conversion_failure_raises_error(
        self, clean_env, mock_marimo_in_path
    ):
        """Test that conversion failure raises RuntimeError."""
        from jupyter_marimo_proxy.convert import convert_notebook_to_marimo

        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "test.ipynb"
            output_file = Path(tmpdir) / "test.py"

            # Mock subprocess.run to simulate failed conversion
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 1
                mock_run.return_value.stderr = "Conversion error"
                mock_run.return_value.stdout = ""

                with pytest.raises(RuntimeError) as exc_info:
                    convert_notebook_to_marimo(
                        str(input_file), str(output_file)
                    )

                assert "marimo convert failed" in str(exc_info.value)
                assert "Conversion error" in str(exc_info.value)

    def test_conversion_failure_uses_stdout_fallback(
        self, clean_env, mock_marimo_in_path
    ):
        """Test that conversion error uses stdout when stderr is empty."""
        from jupyter_marimo_proxy.convert import convert_notebook_to_marimo

        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "test.ipynb"
            output_file = Path(tmpdir) / "test.py"

            # Mock subprocess.run with empty stderr
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 1
                mock_run.return_value.stderr = ""
                mock_run.return_value.stdout = "stdout error message"

                with pytest.raises(RuntimeError) as exc_info:
                    convert_notebook_to_marimo(
                        str(input_file), str(output_file)
                    )

                assert "stdout error message" in str(exc_info.value)

    def test_uses_config_and_marimo_command(
        self, clean_env, mock_marimo_in_path
    ):
        """Test that function uses get_config and get_marimo_command."""
        from jupyter_marimo_proxy.convert import convert_notebook_to_marimo

        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "test.ipynb"
            output_file = Path(tmpdir) / "test.py"

            with patch(
                "jupyter_marimo_proxy.convert.get_config"
            ) as mock_config:
                with patch(
                    "jupyter_marimo_proxy.convert.get_marimo_command"
                ) as mock_cmd:
                    mock_cmd.return_value = [mock_marimo_in_path, "marimo"]

                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value.returncode = 0

                        convert_notebook_to_marimo(
                            str(input_file), str(output_file)
                        )

                        mock_config.assert_called_once()
                        mock_cmd.assert_called_once()
