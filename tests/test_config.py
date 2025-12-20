"""Tests for configuration (config.py)."""

import os
import warnings

import pytest


class TestMarimoProxyConfig:
    """Test suite for MarimoProxyConfig traitlets class."""

    def test_default_marimo_path_is_none(self, clean_env):
        """Default marimo_path should be None when env var not set."""
        from jupyter_marimo_proxy.config import MarimoProxyConfig

        config = MarimoProxyConfig()

        assert config.marimo_path is None

    def test_marimo_path_from_env_var(self, clean_env):
        """marimo_path should default to env var value."""
        os.environ["JUPYTERMARIMOPROXY_MARIMO_PATH"] = "/custom/marimo"

        from jupyter_marimo_proxy.config import MarimoProxyConfig

        config = MarimoProxyConfig()

        assert config.marimo_path == "/custom/marimo"

    def test_default_uvx_path_is_none(self, clean_env):
        """Default uvx_path should be None when env var not set."""
        from jupyter_marimo_proxy.config import MarimoProxyConfig

        config = MarimoProxyConfig()

        assert config.uvx_path is None

    def test_uvx_path_from_env_var(self, clean_env):
        """uvx_path should default to env var value."""
        os.environ["JUPYTERMARIMOPROXY_UVX_PATH"] = "/custom/uvx"

        from jupyter_marimo_proxy.config import MarimoProxyConfig

        config = MarimoProxyConfig()

        assert config.uvx_path == "/custom/uvx"

    def test_default_timeout(self, clean_env):
        """Default timeout should be 60 seconds."""
        from jupyter_marimo_proxy.config import (
            DEFAULT_TIMEOUT,
            MarimoProxyConfig,
        )

        config = MarimoProxyConfig()

        assert config.timeout == DEFAULT_TIMEOUT

    def test_timeout_from_env_var(self, clean_env):
        """Timeout should default to env var value."""
        os.environ["JUPYTERMARIMOPROXY_TIMEOUT"] = "120"

        from jupyter_marimo_proxy.config import MarimoProxyConfig

        config = MarimoProxyConfig()

        assert config.timeout == 120

    def test_invalid_timeout_env_var_uses_default(self, clean_env):
        """Invalid timeout env var should fall back to default."""
        os.environ["JUPYTERMARIMOPROXY_TIMEOUT"] = "not_a_number"

        from jupyter_marimo_proxy.config import (
            DEFAULT_TIMEOUT,
            MarimoProxyConfig,
        )

        config = MarimoProxyConfig()

        assert config.timeout == DEFAULT_TIMEOUT


class TestGetConfig:
    """Test suite for get_config() function."""

    def test_returns_config_dataclass(self, clean_env, mock_marimo_in_path):
        """get_config() should return a Config dataclass."""
        from jupyter_marimo_proxy.config import Config, get_config

        result = get_config()

        assert isinstance(result, Config)

    def test_config_has_all_fields(self, clean_env, mock_marimo_in_path):
        """Config should have all expected fields."""
        from jupyter_marimo_proxy.config import get_config

        result = get_config()

        assert hasattr(result, "marimo_path")
        assert hasattr(result, "uvx_path")
        assert hasattr(result, "timeout")
        assert hasattr(result, "base_url")

    def test_base_url_with_prefix(self, clean_env, mock_marimo_in_path):
        """base_url should use JUPYTERHUB_SERVICE_PREFIX."""
        os.environ["JUPYTERHUB_SERVICE_PREFIX"] = "/user/testuser/"

        from jupyter_marimo_proxy.config import get_config

        result = get_config()

        assert result.base_url == "/user/testuser/marimo"

    def test_base_url_without_prefix(self, clean_env, mock_marimo_in_path):
        """base_url should default to /marimo when no prefix."""
        from jupyter_marimo_proxy.config import get_config

        result = get_config()

        assert result.base_url == "/marimo"

    def test_deprecated_rc_file_warning(
        self, clean_env, mock_marimo_in_path, temp_rc_file
    ):
        """Should warn when deprecated .jupytermarimoproxyrc exists."""
        from jupyter_marimo_proxy.config import get_config

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            get_config()

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert ".jupytermarimoproxyrc" in str(w[0].message)

    def test_traitlets_override_env_vars(self, clean_env, mock_marimo_in_path):
        """Traitlets config should override environment variables."""
        os.environ["JUPYTERMARIMOPROXY_MARIMO_PATH"] = "/env/marimo"
        os.environ["JUPYTERMARIMOPROXY_TIMEOUT"] = "30"

        from jupyter_marimo_proxy.config import MarimoProxyConfig, get_config

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
        from jupyter_marimo_proxy.config import Config

        config = Config(
            marimo_path="/path/to/marimo",
            uvx_path=None,
            timeout=60,
            base_url="/marimo",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            config.timeout = 120
