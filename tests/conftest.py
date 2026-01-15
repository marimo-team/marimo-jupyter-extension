"""pytest fixtures for marimo-jupyter-extension tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def clean_env():
    """Remove proxy-related environment variables for clean test state."""
    env_vars = [
        "JUPYTERHUB_SERVICE_PREFIX",
        "UV",  # Used as fallback for uvx_path
    ]
    old_values = {}
    for var in env_vars:
        old_values[var] = os.environ.pop(var, None)

    yield

    # Restore original values
    for var, value in old_values.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]


@pytest.fixture
def temp_bin_dir():
    """Create a temporary directory with a mock marimo executable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        marimo_path = Path(tmpdir) / "marimo"
        marimo_path.write_text("#!/bin/bash\necho 'mock marimo'")
        marimo_path.chmod(0o755)
        yield tmpdir


@pytest.fixture
def mock_marimo_in_path(temp_bin_dir):
    """Mock shutil.which to return a marimo path."""
    marimo_path = str(Path(temp_bin_dir) / "marimo")
    with patch("shutil.which", return_value=marimo_path):
        yield marimo_path


@pytest.fixture
def mock_marimo_not_in_path():
    """Mock shutil.which to return None (marimo not found)."""
    with patch(
        "marimo_jupyter_extension.executable.shutil.which", return_value=None
    ):
        with patch(
            "marimo_jupyter_extension.executable.COMMON_LOCATIONS",
            ["/nonexistent/path/marimo"],
        ):
            yield
