"""Tests for executable discovery (executable.py)."""

from pathlib import Path
from unittest.mock import patch

import pytest


class TestGetMarimoCommand:
    """Test suite for get_marimo_command() function."""

    @pytest.mark.parametrize(
        ("sandbox", "minimum"),
        [("uv", "0.23.14"), ("pixi", "0.25.0"), (None, "0.23.14")],
    )
    def test_uvx_mode_with_uvx_path(self, clean_env, sandbox, minimum):
        """Select a marimo version that supports the sandbox backend."""
        from marimo_jupyter_extension.config import Config
        from marimo_jupyter_extension.executable import get_marimo_command

        config = Config(
            marimo_path=None,
            uvx_path="/usr/local/bin/uvx",
            timeout=60,
            base_url="/marimo",
            sandbox=sandbox,
        )
        result = get_marimo_command(config)

        assert result == ["/usr/local/bin/uvx", f"marimo[sandbox]>={minimum}"]

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


class TestFindPixi:
    """Test suite for find_pixi() and get_pixi_path()."""

    @staticmethod
    def _config(pixi_path=None):
        from marimo_jupyter_extension.config import Config

        return Config(
            marimo_path="/opt/bin/marimo",
            uvx_path=None,
            timeout=300,
            base_url="/marimo",
            sandbox="pixi",
            pixi_path=pixi_path,
        )

    def test_explicit_pixi_path_wins(
        self, clean_env, mock_pixi_not_found, temp_pixi_path
    ):
        """Use the configured executable before searching for pixi."""
        from marimo_jupyter_extension.executable import find_pixi

        assert find_pixi(self._config(temp_pixi_path)) == temp_pixi_path

    @pytest.mark.parametrize("kind", ["missing", "directory", "nonexecutable"])
    def test_invalid_explicit_pixi_path_raises(
        self, clean_env, mock_pixi_not_found, tmp_path, kind
    ):
        from marimo_jupyter_extension.executable import get_pixi_path

        pixi = tmp_path / "pixi"
        if kind == "directory":
            pixi.mkdir()
        elif kind == "nonexecutable":
            pixi.write_text("#!/bin/sh\n")
            pixi.chmod(0o644)

        with pytest.raises(
            FileNotFoundError, match="pixi executable not found"
        ):
            get_pixi_path(self._config(str(pixi)))

    def test_finds_in_system_path(self, clean_env):
        """Should find pixi via shutil.which("pixi")."""
        from marimo_jupyter_extension.executable import find_pixi

        def which(name):
            return "/usr/local/bin/pixi" if name == "pixi" else None

        with patch(
            "marimo_jupyter_extension.executable.shutil.which",
            side_effect=which,
        ):
            assert find_pixi(self._config()) == "/usr/local/bin/pixi"

    def test_finds_in_pixi_home(
        self, clean_env, mock_pixi_not_found, tmp_path, monkeypatch
    ):
        """$PIXI_HOME/bin/pixi should be checked before common locations."""
        from marimo_jupyter_extension.executable import find_pixi

        pixi = tmp_path / "bin" / "pixi"
        pixi.parent.mkdir()
        pixi.write_text("")
        pixi.chmod(0o755)
        monkeypatch.setenv("PIXI_HOME", str(tmp_path))

        assert find_pixi(self._config()) == str(pixi)

    def test_finds_in_common_locations(
        self, clean_env, temp_pixi_path, tmp_path
    ):
        """Skip files that cannot execute when searching common locations."""
        from marimo_jupyter_extension.executable import find_pixi

        nonexecutable = tmp_path / "pixi"
        nonexecutable.write_text("#!/bin/sh\n")
        nonexecutable.chmod(0o644)

        with (
            patch(
                "marimo_jupyter_extension.executable.shutil.which",
                return_value=None,
            ),
            patch(
                "marimo_jupyter_extension.executable.PIXI_COMMON_LOCATIONS",
                ["/nonexistent/pixi", str(nonexecutable), temp_pixi_path],
            ),
        ):
            assert find_pixi(self._config()) == temp_pixi_path

    def test_returns_none_when_not_found(self, clean_env, mock_pixi_not_found):
        """Should return None when pixi is nowhere to be found."""
        from marimo_jupyter_extension.executable import find_pixi

        assert find_pixi(self._config()) is None

    def test_get_pixi_path_raises_with_hints(
        self, clean_env, mock_pixi_not_found
    ):
        """get_pixi_path should raise FileNotFoundError with install hints."""
        from marimo_jupyter_extension.executable import get_pixi_path

        with pytest.raises(FileNotFoundError) as exc_info:
            get_pixi_path(self._config())

        message = str(exc_info.value)
        assert "https://pixi.sh" in message
        assert "MarimoProxyConfig.pixi_path" in message
        assert "sandbox = 'uv'" in message
