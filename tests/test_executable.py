"""Tests for executable discovery (executable.py)."""

from pathlib import Path
from unittest.mock import patch

import pytest


class TestGetMarimoCommand:
    """Test suite for get_marimo_command() function."""

    def test_uvx_mode_with_uvx_path(self, clean_env):
        """When uvx_path set, return [uvx_path, 'marimo[sandbox]...']."""
        from marimo_jupyter_extension.config import Config
        from marimo_jupyter_extension.executable import get_marimo_command

        config = Config(
            marimo_path=None,
            uvx_path="/usr/local/bin/uvx",
            timeout=60,
            base_url="/marimo",
        )
        result = get_marimo_command(config)

        assert len(result) == 2
        assert result[0] == "/usr/local/bin/uvx"
        assert result[1].startswith("marimo[sandbox]")

    def test_explicit_marimo_path(self, clean_env):
        """When marimo_path is set, should return [marimo_path]."""
        from marimo_jupyter_extension.config import Config
        from marimo_jupyter_extension.executable import get_marimo_command

        config = Config(
            marimo_path="/opt/bin/marimo",
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
        )
        result = get_marimo_command(config)

        assert result == ["/opt/bin/marimo"]

    def test_uvx_takes_precedence_over_marimo_path(self, clean_env):
        """When both uvx_path and marimo_path set, uvx_path wins."""
        from marimo_jupyter_extension.config import Config
        from marimo_jupyter_extension.executable import get_marimo_command

        config = Config(
            marimo_path="/opt/bin/marimo",
            uvx_path="/usr/local/bin/uvx",
            timeout=60,
            base_url="/marimo",
        )
        result = get_marimo_command(config)

        assert len(result) == 2
        assert result[0] == "/usr/local/bin/uvx"
        assert result[1].startswith("marimo[sandbox]")

    def test_finds_marimo_in_path(self, clean_env, mock_marimo_in_path):
        """When no explicit path, should find marimo in PATH."""
        from marimo_jupyter_extension.config import Config
        from marimo_jupyter_extension.executable import get_marimo_command

        config = Config(
            marimo_path=None,
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
        )
        result = get_marimo_command(config)

        assert result == [mock_marimo_in_path]

    def test_marimo_not_found_raises_error(
        self, clean_env, mock_marimo_not_in_path
    ):
        """When marimo not found anywhere, should raise FileNotFoundError."""
        from marimo_jupyter_extension.config import Config
        from marimo_jupyter_extension.executable import get_marimo_command

        config = Config(
            marimo_path=None,
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
        )

        with pytest.raises(FileNotFoundError) as exc_info:
            get_marimo_command(config)

        assert "marimo executable not found" in str(exc_info.value)
        assert "MarimoProxyConfig.marimo_path" in str(exc_info.value)


class TestFindMarimo:
    """Test suite for _find_marimo() helper function."""

    def test_finds_in_system_path(self, clean_env, mock_marimo_in_path):
        """Should find marimo via shutil.which."""
        from marimo_jupyter_extension.executable import _find_marimo

        result = _find_marimo()

        assert result == mock_marimo_in_path

    def test_finds_in_common_locations(self, clean_env, temp_bin_dir):
        """Should check common locations when not in PATH."""
        from marimo_jupyter_extension.executable import _find_marimo

        # Create marimo in common location
        marimo_path = Path(temp_bin_dir) / "marimo"

        with patch("shutil.which", return_value=None):
            with patch(
                "marimo_jupyter_extension.executable.COMMON_LOCATIONS",
                [str(marimo_path)],
            ):
                result = _find_marimo()

        assert result == str(marimo_path)

    def test_returns_none_when_not_found(
        self, clean_env, mock_marimo_not_in_path
    ):
        """Should return None when marimo not found anywhere."""
        from marimo_jupyter_extension.executable import _find_marimo

        with patch(
            "marimo_jupyter_extension.executable.COMMON_LOCATIONS",
            ["/nonexistent/path/marimo"],
        ):
            result = _find_marimo()

        assert result is None
