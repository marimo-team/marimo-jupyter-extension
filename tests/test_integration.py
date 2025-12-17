"""Integration tests that actually invoke external commands.

These tests are marked with @pytest.mark.integration and are skipped by default.
Run with: uv run pytest -m integration
"""

import shutil
import subprocess

import pytest


class TestUvxIntegration:
    """Integration tests that actually invoke uvx."""

    @pytest.mark.integration
    def test_uvx_marimo_version(self):
        """Verify uvx can run marimo --version."""
        uvx_path = shutil.which("uvx")
        if not uvx_path:
            pytest.skip("uvx not installed")

        result = subprocess.run(
            [uvx_path, "marimo", "--version"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        assert "marimo" in result.stdout.lower() or result.stdout.strip()

    @pytest.mark.integration
    def test_uvx_marimo_help(self):
        """Verify uvx can run marimo edit --help."""
        uvx_path = shutil.which("uvx")
        if not uvx_path:
            pytest.skip("uvx not installed")

        result = subprocess.run(
            [uvx_path, "marimo", "edit", "--help"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        assert "--port" in result.stdout


class TestMarimoIntegration:
    """Integration tests for directly installed marimo."""

    @pytest.mark.integration
    def test_marimo_version(self):
        """Verify marimo --version works."""
        marimo_path = shutil.which("marimo")
        if not marimo_path:
            pytest.skip("marimo not installed")

        result = subprocess.run(
            [marimo_path, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

    @pytest.mark.integration
    def test_marimo_edit_help(self):
        """Verify marimo edit --help works."""
        marimo_path = shutil.which("marimo")
        if not marimo_path:
            pytest.skip("marimo not installed")

        result = subprocess.run(
            [marimo_path, "edit", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "--port" in result.stdout
        assert "--headless" in result.stdout


class TestSetupIntegration:
    """Integration tests for the complete setup function."""

    @pytest.mark.integration
    def test_setup_marimoserver_full_command(self):
        """Verify setup_marimoserver produces valid command structure."""
        from jupyter_marimo_proxy import setup_marimoserver

        try:
            result = setup_marimoserver()
        except FileNotFoundError:
            pytest.skip("marimo not installed")

        # Verify command structure
        command = result["command"]
        assert "edit" in command
        assert "{port}" in command
        assert "--headless" in command
        assert "--token" in command
        assert "--token-password" in command
        assert "--base-url" in command

    @pytest.mark.integration
    def test_setup_marimoserver_command_executable(self):
        """Verify the executable in command actually exists."""
        from jupyter_marimo_proxy import setup_marimoserver

        try:
            result = setup_marimoserver()
        except FileNotFoundError:
            pytest.skip("marimo not installed")

        executable = result["command"][0]
        # Either it's a direct path or it's a uvx command
        if "uvx" not in executable:
            assert (
                shutil.which(executable)
                or subprocess.run(
                    [executable, "--version"],
                    capture_output=True,
                ).returncode
                == 0
            )
