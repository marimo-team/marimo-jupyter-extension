"""Tests for configuration (config.py)."""

import os

import pytest


class TestMarimoProxyConfig:
    """Test suite for MarimoProxyConfig traitlets class."""

    def test_default_marimo_path_is_none(self, clean_env):
        """Default marimo_path should be None."""
        from marimo_jupyter_extension.config import MarimoProxyConfig

        config = MarimoProxyConfig()

        assert config.marimo_path is None

    def test_default_uvx_path_is_none(self, clean_env):
        """Default uvx_path should be None."""
        from marimo_jupyter_extension.config import MarimoProxyConfig

        config = MarimoProxyConfig()

        assert config.uvx_path is None

    def test_default_timeout(self, clean_env):
        """Default timeout should be 60 seconds."""
        from marimo_jupyter_extension.config import MarimoProxyConfig, DEFAULT_TIMEOUT

        config = MarimoProxyConfig()

        assert config.timeout == DEFAULT_TIMEOUT

    def test_uvx_path_from_uv_env(self, clean_env):
        """uvx_path should derive from UV env var."""
        os.environ["UV"] = "/custom/path/uv"

        from marimo_jupyter_extension.config import MarimoProxyConfig

        config = MarimoProxyConfig()

        assert config.uvx_path == "/custom/path/uvx"


class TestGetConfig:
    """Test suite for get_config() function."""

    def test_returns_config_dataclass(self, clean_env, mock_marimo_in_path):
        """get_config() should return a Config dataclass."""
        from marimo_jupyter_extension.config import get_config, Config

        result = get_config()

        assert isinstance(result, Config)

    def test_config_has_all_fields(self, clean_env, mock_marimo_in_path):
        """Config should have all expected fields."""
        from marimo_jupyter_extension.config import get_config

        result = get_config()

        assert hasattr(result, "marimo_path")
        assert hasattr(result, "uvx_path")
        assert hasattr(result, "timeout")
        assert hasattr(result, "base_url")

    def test_base_url_with_prefix(self, clean_env, mock_marimo_in_path):
        """base_url should use JUPYTERHUB_SERVICE_PREFIX."""
        os.environ["JUPYTERHUB_SERVICE_PREFIX"] = "/user/testuser/"

        from marimo_jupyter_extension.config import get_config

        result = get_config()

        assert result.base_url == "/user/testuser/marimo"

    def test_base_url_without_prefix(self, clean_env, mock_marimo_in_path):
        """base_url should default to /marimo when no prefix."""
        from marimo_jupyter_extension.config import get_config

        result = get_config()

        assert result.base_url == "/marimo"

    def test_traitlets_config_applied(self, clean_env, mock_marimo_in_path):
        """Traitlets config should be applied to get_config result."""
        from marimo_jupyter_extension.config import get_config, MarimoProxyConfig

        traitlets_config = MarimoProxyConfig()
        traitlets_config.marimo_path = "/traitlets/marimo"
        traitlets_config.timeout = 90

        result = get_config(traitlets_config)

        assert result.marimo_path == "/traitlets/marimo"
        assert result.timeout == 90


class TestConfigDataclass:
    """Test suite for the Config dataclass."""

    def test_config_is_frozen(self, clean_env):
        """Config dataclass should be immutable (frozen)."""
        from marimo_jupyter_extension.config import Config

        config = Config(
            marimo_path="/path/to/marimo",
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            config.timeout = 120
