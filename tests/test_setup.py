"""Tests for the setup_marimoserver() function."""

import os


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
