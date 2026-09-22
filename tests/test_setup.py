"""Tests for the setup_marimoserver() function."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestSetupMarimoserver:
    """Test suite for setup_marimoserver() return value structure."""

    def test_returns_required_keys(self, clean_env, mock_marimo_in_path):
        """setup_marimoserver returns keys for jupyter-server-proxy."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        required_keys = {"command", "timeout", "launcher_entry"}
        assert required_keys.issubset(result.keys()), (
            f"Missing keys: {required_keys - result.keys()}"
        )

    def test_command_is_list(self, clean_env, mock_marimo_in_path):
        """Command should be a list of strings."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert isinstance(result["command"], list)
        assert all(isinstance(arg, str) for arg in result["command"])

    def test_command_includes_edit_subcommand(
        self, clean_env, mock_marimo_in_path
    ):
        """Command should include 'edit' subcommand."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert "edit" in result["command"]

    def test_command_includes_port_placeholder(
        self, clean_env, mock_marimo_in_path
    ):
        """Command should include {port} placeholder for server-proxy."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert "{port}" in result["command"]

    def test_command_includes_headless_flag(
        self, clean_env, mock_marimo_in_path
    ):
        """Command should include --headless flag."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert "--headless" in result["command"]

    def test_timeout_is_positive_integer(self, clean_env, mock_marimo_in_path):
        """Timeout should be a positive integer."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert isinstance(result["timeout"], int)
        assert result["timeout"] > 0

    def test_launcher_entry_disabled(self, clean_env, mock_marimo_in_path):
        """Launcher entry should be disabled (labextension provides it)."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert "enabled" in result["launcher_entry"]
        assert result["launcher_entry"]["enabled"] is False

    def test_command_includes_sandbox_by_default(
        self, clean_env, mock_marimo_in_path
    ):
        """Command should include --sandbox when no_sandbox is False."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert "--sandbox" in result["command"]

    def test_command_excludes_sandbox_when_sandbox_is_none(
        self, clean_env, mock_marimo_in_path
    ):
        """Command should omit every --sandbox spelling when sandbox is None."""
        from marimo_jupyter_extension.config import Config

        mock_config = Config(
            marimo_path=mock_marimo_in_path,
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
            sandbox=None,
        )

        with patch(
            "marimo_jupyter_extension.get_config",
            return_value=mock_config,
        ):
            from marimo_jupyter_extension import setup_marimoserver

            result = setup_marimoserver()

        assert not [a for a in result["command"] if a.startswith("--sandbox")]

    def test_uv_backend_emits_bare_sandbox_flag(
        self, clean_env, mock_marimo_in_path
    ):
        """sandbox='uv' must stay a bare --sandbox for marimo<=0.23 compat."""
        from marimo_jupyter_extension.config import Config

        mock_config = Config(
            marimo_path=mock_marimo_in_path,
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
            sandbox="uv",
        )

        with patch(
            "marimo_jupyter_extension.get_config",
            return_value=mock_config,
        ):
            from marimo_jupyter_extension import setup_marimoserver

            result = setup_marimoserver()

        cmd = result["command"]
        assert "--sandbox" in cmd
        assert "--sandbox=uv" not in cmd
        assert "uv" not in cmd

    def test_command_excludes_log_level_by_default(
        self, clean_env, mock_marimo_in_path
    ):
        """Command should omit --log-level when debug is False."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert "--log-level" not in result["command"]

    def test_command_includes_debug_log_level_when_debug_enabled(
        self, clean_env, mock_marimo_in_path
    ):
        """Command should include --log-level DEBUG when debug is True."""
        from marimo_jupyter_extension.config import Config

        mock_config = Config(
            marimo_path=mock_marimo_in_path,
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
            debug=True,
        )

        with patch(
            "marimo_jupyter_extension.get_config",
            return_value=mock_config,
        ):
            from marimo_jupyter_extension import setup_marimoserver

            result = setup_marimoserver()

        cmd = result["command"]
        assert "--log-level" in cmd
        assert cmd[cmd.index("--log-level") + 1] == "DEBUG"
        assert cmd.index("--log-level") < cmd.index("edit")


class TestPixiSandbox:
    """Tests for sandbox='pixi': flag spelling, PATH injection, discovery."""

    @staticmethod
    def _pixi_config(marimo_path, **overrides):
        from marimo_jupyter_extension.config import Config

        return Config(
            marimo_path=marimo_path,
            uvx_path=None,
            timeout=300,
            base_url="/marimo",
            sandbox="pixi",
            **overrides,
        )

    def _setup(self, config):
        with patch("marimo_jupyter_extension.get_config", return_value=config):
            from marimo_jupyter_extension import setup_marimoserver

            return setup_marimoserver()

    def test_pixi_backend_uses_equals_form(
        self, clean_env, temp_bin_dir, temp_pixi_path
    ):
        """pixi must be spelled --sandbox=pixi, not a positional value."""
        marimo = str(Path(temp_bin_dir) / "marimo")
        config = self._pixi_config(marimo, pixi_path=temp_pixi_path)

        with patch("shutil.which", return_value=None):
            result = self._setup(config)

        cmd = result["command"]
        assert "--sandbox=pixi" in cmd
        assert "--sandbox" not in cmd
        assert "pixi" not in cmd
        assert cmd.index("--sandbox=pixi") > cmd.index("edit")

    def test_pixi_path_outside_path_is_prepended_to_path(
        self, clean_env, temp_bin_dir, temp_pixi_path
    ):
        """marimo finds pixi via which(), so its directory must lead PATH."""
        marimo = str(Path(temp_bin_dir) / "marimo")
        config = self._pixi_config(marimo, pixi_path=temp_pixi_path)

        with (
            patch("shutil.which", return_value=None),
            patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}),
        ):
            result = self._setup(config)

        env = result["environment"]
        assert env["MARIMO_SERVER_TRANSPORT"] == "websocket"
        assert env["PATH"].split(os.pathsep) == [
            str(Path(temp_pixi_path).parent),
            "/usr/bin",
            "/bin",
        ]

    def test_pixi_path_overrides_different_pixi_on_path(
        self, clean_env, temp_bin_dir, temp_pixi_path
    ):
        """An explicit pixi_path must shadow another pixi already on PATH."""
        marimo = str(Path(temp_bin_dir) / "marimo")
        config = self._pixi_config(marimo, pixi_path=temp_pixi_path)

        with patch("shutil.which", return_value="/usr/bin/pixi"):
            result = self._setup(config)

        assert result["environment"]["PATH"].startswith(
            str(Path(temp_pixi_path).parent) + os.pathsep
        )

    def test_pixi_on_path_leaves_path_untouched(self, clean_env, temp_bin_dir):
        """When which() already finds the chosen pixi, PATH is not overridden."""
        marimo = str(Path(temp_bin_dir) / "marimo")
        config = self._pixi_config(marimo)

        with patch("shutil.which", return_value="/usr/local/bin/pixi"):
            result = self._setup(config)

        assert "PATH" not in result["environment"]
        assert "--sandbox=pixi" in result["command"]

    def test_pixi_missing_raises_actionable_error(
        self, clean_env, temp_bin_dir, mock_pixi_not_found
    ):
        """sandbox='pixi' without pixi must fail fast with install hints."""
        marimo = str(Path(temp_bin_dir) / "marimo")
        config = self._pixi_config(marimo)

        with pytest.raises(FileNotFoundError) as exc_info:
            self._setup(config)

        message = str(exc_info.value)
        assert "pixi executable not found" in message
        assert "https://pixi.sh" in message
        assert "MarimoProxyConfig.pixi_path" in message

    def test_uv_backend_never_probes_pixi(self, clean_env, temp_bin_dir):
        """The default backend must not require pixi to be installed."""
        from marimo_jupyter_extension.config import Config

        marimo = str(Path(temp_bin_dir) / "marimo")
        config = Config(
            marimo_path=marimo,
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
            sandbox="uv",
        )

        with patch(
            "marimo_jupyter_extension.get_pixi_path",
            side_effect=AssertionError("pixi lookup must not run"),
        ):
            result = self._setup(config)

        assert "PATH" not in result["environment"]


class TestTransportEnvironment:
    """Test suite for the MARIMO_SERVER_TRANSPORT environment variable."""

    def test_environment_defaults_to_websocket(
        self, clean_env, mock_marimo_in_path
    ):
        """environment should set MARIMO_SERVER_TRANSPORT=websocket by default."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert result["environment"]["MARIMO_SERVER_TRANSPORT"] == "websocket"

    def test_environment_uses_configured_transport(
        self, clean_env, mock_marimo_in_path
    ):
        """environment should reflect the configured transport (sse)."""
        from marimo_jupyter_extension.config import Config

        mock_config = Config(
            marimo_path=mock_marimo_in_path,
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
            transport="sse",
        )

        with patch(
            "marimo_jupyter_extension.get_config",
            return_value=mock_config,
        ):
            from marimo_jupyter_extension import setup_marimoserver

            result = setup_marimoserver()

        assert result["environment"]["MARIMO_SERVER_TRANSPORT"] == "sse"


class TestTokenAuthentication:
    """Test suite for token-based authentication."""

    def test_generates_auth_header(self, clean_env, mock_marimo_in_path):
        """Should generate request_headers_override with Authorization."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert "request_headers_override" in result
        assert "Authorization" in result["request_headers_override"]

    def test_auth_header_is_basic_auth(self, clean_env, mock_marimo_in_path):
        """Authorization header should be Basic auth format."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()
        auth_header = result["request_headers_override"]["Authorization"]

        assert auth_header.startswith("Basic ")

    def test_token_is_in_command(self, clean_env, mock_marimo_in_path):
        """Token should be passed to marimo command."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert "--token" in result["command"]
        assert "--token-password" in result["command"]

    def test_token_is_unique_per_call(self, clean_env, mock_marimo_in_path):
        """Each call should generate a unique token."""
        from marimo_jupyter_extension import setup_marimoserver

        result1 = setup_marimoserver()
        result2 = setup_marimoserver()

        # Extract tokens from auth headers
        auth1 = result1["request_headers_override"]["Authorization"]
        auth2 = result2["request_headers_override"]["Authorization"]

        assert auth1 != auth2, "Tokens should be unique per call"


class TestAbsoluteUrl:
    """Test suite for absolute URL configuration."""

    def test_absolute_url_is_true(self, clean_env, mock_marimo_in_path):
        """absolute_url should be True for proper proxy routing."""
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()

        assert result.get("absolute_url") is True

    def test_base_url_with_prefix(self, clean_env, mock_marimo_in_path):
        """Base URL should use JUPYTERHUB_SERVICE_PREFIX when set."""
        os.environ["JUPYTERHUB_SERVICE_PREFIX"] = "/user/testuser/"

        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()
        command = " ".join(result["command"])

        assert "/user/testuser/marimo" in command

    def test_base_url_without_prefix(self, clean_env, mock_marimo_in_path):
        """Base URL should default to /marimo when no prefix set."""
        # clean_env already removes JUPYTERHUB_SERVICE_PREFIX
        from marimo_jupyter_extension import setup_marimoserver

        result = setup_marimoserver()
        command = " ".join(result["command"])

        assert "/marimo" in command


class TestHostFlag:
    """Tests for --host flag behavior in setup_marimoserver()."""

    def test_host_flag_included_when_ipv6(
        self, clean_env, mock_marimo_in_path
    ):
        """--host ::1 should appear in command when IPv6 is detected."""
        from marimo_jupyter_extension.config import Config

        mock_config = Config(
            marimo_path=mock_marimo_in_path,
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
            host="::1",
        )

        with patch(
            "marimo_jupyter_extension.get_config",
            return_value=mock_config,
        ):
            from marimo_jupyter_extension import setup_marimoserver

            result = setup_marimoserver()

        cmd = result["command"]
        assert "--host" in cmd
        assert cmd[cmd.index("--host") + 1] == "::1"

    def test_host_flag_omitted_when_none(self, clean_env, mock_marimo_in_path):
        """--host should not appear in command when host is None."""
        from marimo_jupyter_extension.config import Config

        mock_config = Config(
            marimo_path=mock_marimo_in_path,
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
            host=None,
        )

        with patch(
            "marimo_jupyter_extension.get_config",
            return_value=mock_config,
        ):
            from marimo_jupyter_extension import setup_marimoserver

            result = setup_marimoserver()

        assert "--host" not in result["command"]
