"""Tests for marimo version discovery and caching."""

import subprocess
from dataclasses import replace
from unittest.mock import patch

import pytest

from marimo_jupyter_extension import (
    executable,
    setup_marimoserver,
    version_info,
)
from marimo_jupyter_extension.config import Config


@pytest.fixture(autouse=True)
def clear_version_cache():
    version_info._get_command_version.cache_clear()
    yield
    version_info._get_command_version.cache_clear()


@pytest.fixture
def config(temp_pixi_path):
    return Config(
        marimo_path="/opt/bin/marimo",
        uvx_path=None,
        timeout=300,
        base_url="/marimo",
        sandbox="pixi",
        pixi_path=temp_pixi_path,
    )


@pytest.mark.parametrize("version_first", [True, False])
def test_setup_and_display_share_version_probe(config, version_first):
    with (
        patch("marimo_jupyter_extension.get_config", return_value=config),
        patch.object(version_info, "get_config", return_value=config),
        patch.object(
            version_info.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "marimo 0.25.0\n"),
        ) as run,
    ):
        if version_first:
            assert version_info.get_marimo_version() == "0.25.0"
        result = setup_marimoserver()
        assert version_info.get_marimo_version() == "0.25.0"

    assert "--sandbox=pixi" in result["command"]
    run.assert_called_once_with(
        ["/opt/bin/marimo", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )


def _assert_reprobed(first, second):
    """Two configs that spawn different commands each get their own probe."""
    with (
        patch.object(
            version_info,
            "get_config",
            side_effect=[first, second],
        ),
        patch.object(
            version_info.subprocess,
            "run",
            side_effect=[
                subprocess.CompletedProcess([], 0, "marimo 0.24.2\n"),
                subprocess.CompletedProcess([], 0, "marimo 0.25.0\n"),
            ],
        ),
    ):
        assert version_info.get_marimo_version() == "0.24.2"
        assert version_info.get_marimo_version() == "0.25.0"


def test_version_cache_distinguishes_marimo_paths(config):
    _assert_reprobed(config, replace(config, marimo_path="/other/marimo"))


def test_version_cache_distinguishes_sandbox_backends(config):
    # uvx requests `marimo[sandbox]>=<floor>`, and the floor depends on the
    # backend. Pin the uv floor below pixi's so the two commands differ even
    # when the constants are currently equal.
    uv = replace(config, uvx_path="/opt/bin/uvx", sandbox="uv")
    pixi = replace(uv, sandbox="pixi")
    with patch.object(executable, "MARIMO_VERSION", "0.23.14"):
        _assert_reprobed(uv, pixi)


@pytest.mark.parametrize("output", ["", "invalid"])
def test_setup_rejects_unknown_version(config, output):
    with (
        patch("marimo_jupyter_extension.get_config", return_value=config),
        patch.object(
            version_info.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, output),
        ),
        pytest.raises(
            RuntimeError, match="Pixi sandboxing requires marimo>=0.25.0"
        ),
    ):
        setup_marimoserver()


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("missing marimo"),
        subprocess.CalledProcessError(1, ["marimo", "--version"]),
        subprocess.TimeoutExpired(["marimo", "--version"], 10),
    ],
)
def test_failed_probe_is_optional_for_display_but_blocks_pixi(config, error):
    with (
        patch("marimo_jupyter_extension.get_config", return_value=config),
        patch.object(version_info, "get_config", return_value=config),
        patch.object(version_info.subprocess, "run", side_effect=error) as run,
    ):
        assert version_info.get_marimo_version() is None
        with pytest.raises(RuntimeError, match="an unknown version"):
            setup_marimoserver()

    run.assert_called_once()
