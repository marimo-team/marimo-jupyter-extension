"""Parity check between marimo edit CLI options and proxy config.

Ensures that every option exposed by `marimo edit --help` is deliberately
accounted for — either hardcoded into the proxy command, mapped to a
MarimoProxyConfig traitlet, or explicitly excluded. Unknown options
(newly added by marimo) will fail the test.

Run as an integration test:
    uv run pytest tests/test_parity.py -m integration -v

Run as a standalone report:
    uv run python tests/test_parity.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Option categories
# ---------------------------------------------------------------------------

# Passed to marimo by the proxy itself — not user-configurable.
HARDCODED_OPTIONS: set[str] = {
    "--port",  # injected by jupyter-server-proxy as {port}
    "--headless",  # always set; proxy handles browser launching
    "--token",  # always enabled; token auth is required
    "--token-password",  # auto-generated via secrets.token_urlsafe(16)
    "--no-skew-protection",  # required for proxy compat (version mismatch ok)
    "--base-url",  # auto-configured from JUPYTERHUB_SERVICE_PREFIX
}

# Mapped to MarimoProxyConfig traitlets in config.py — user-configurable.
EXPOSED_OPTIONS: set[str] = {
    "--sandbox",
    "--no-sandbox",  # config: no_sandbox (default: sandbox on)
    "--host",  # config: host (auto-detected localhost)
    "--watch",  # config: watch
    "--allow-origins",  # config: allow_origins
    "--skip-update-check",  # config: skip_update_check
    "--timeout",  # config: idle_timeout
    "--session-ttl",  # config: session_ttl
}

# Deliberately not exposed — not applicable in a proxy deployment.
EXCLUDED_OPTIONS: set[str] = {
    "--proxy",  # upstream reverse proxy address, not this proxy
    "--no-token",  # token auth is always required by the proxy
    "--token-password-file",  # token is auto-generated; file mode not needed
    "--trusted",  # requires Docker; not applicable here
    "--untrusted",  # requires Docker; not applicable here
    "--skew-protection",  # hardcoded to --no-skew-protection
    "--help",  # meta-option, not a marimo server flag
}

ALL_KNOWN: set[str] = HARDCODED_OPTIONS | EXPOSED_OPTIONS | EXCLUDED_OPTIONS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_uv() -> str | None:
    return shutil.which("uv")


def get_marimo_edit_options(uv_exe: str | None = None) -> set[str]:
    """Run ``uv run marimo edit --help`` and return all ``--flag`` names."""
    exe = uv_exe or _find_uv()
    if exe is None:
        raise FileNotFoundError("uv executable not found.")
    result = subprocess.run(
        [
            exe,
            "run",
            "--no-project",
            "--with",
            "marimo",
            "marimo",
            "edit",
            "--help",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout + result.stderr
    return set(re.findall(r"--[\w-]+", output))


def check_parity(
    uv_exe: str | None = None,
) -> tuple[set[str], set[str], set[str], set[str]]:
    """Categorize all marimo edit options.

    Returns:
        (hardcoded, exposed, excluded, unknown)
        ``unknown`` is non-empty when marimo adds options we haven't seen.
    """
    options = get_marimo_edit_options(uv_exe)
    hardcoded = options & HARDCODED_OPTIONS
    exposed = options & EXPOSED_OPTIONS
    excluded = options & EXCLUDED_OPTIONS
    unknown = options - ALL_KNOWN
    return hardcoded, exposed, excluded, unknown


def print_report(
    hardcoded: set[str],
    exposed: set[str],
    excluded: set[str],
    unknown: set[str],
) -> None:
    """Print a human-readable parity report."""
    print("\n=== marimo edit ↔ proxy parity report ===\n")

    print("  ✓ hardcoded  (proxy-managed, not user-configurable)")
    for opt in sorted(hardcoded):
        print(f"      {opt}")

    print("\n  ✓ exposed    (MarimoProxyConfig traitlets)")
    for opt in sorted(exposed):
        print(f"      {opt}")

    print("\n  – excluded   (deliberately omitted)")
    for opt in sorted(excluded):
        print(f"      {opt}")

    if unknown:
        print("\n  ✗ UNKNOWN    (unaccounted — add to a category above!)")
        for opt in sorted(unknown):
            print(f"      {opt}")
        print()
    else:
        print("\n  All options accounted for.\n")


# ---------------------------------------------------------------------------
# Pytest integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_no_unaccounted_edit_options():
    """Fail when marimo edit gains flags we haven't categorized.

    This test catches when a new marimo release adds CLI options that the
    proxy hasn't considered. Add new options to one of the category sets
    at the top of this file to resolve the failure.
    """
    uv_exe = _find_uv()
    if uv_exe is None:
        pytest.skip("uv executable not found")

    *_, unknown = check_parity(uv_exe)

    assert not unknown, (
        f"marimo edit has unaccounted options: {sorted(unknown)}\n"
        "Add each option to HARDCODED_OPTIONS, EXPOSED_OPTIONS, or "
        "EXCLUDED_OPTIONS in tests/test_parity.py."
    )


@pytest.mark.integration
def test_exposed_options_still_exist():
    """Fail when marimo removes an option we currently expose as a traitlet.

    If marimo drops a flag that MarimoProxyConfig exposes, the proxy will
    pass an unrecognized argument and fail to start.
    """
    uv_exe = _find_uv()
    if uv_exe is None:
        pytest.skip("uv executable not found")

    options = get_marimo_edit_options(uv_exe)
    missing = EXPOSED_OPTIONS - options
    assert not missing, (
        f"Options exposed by MarimoProxyConfig are no longer in marimo edit: "
        f"{sorted(missing)}\n"
        "Update config.py and __init__.py to remove or replace them."
    )


@pytest.mark.integration
def test_hardcoded_options_still_exist():
    """Fail when marimo removes an option the proxy always passes."""
    uv_exe = _find_uv()
    if uv_exe is None:
        pytest.skip("uv executable not found")

    options = get_marimo_edit_options(uv_exe)
    missing = HARDCODED_OPTIONS - options
    assert not missing, (
        f"Options hardcoded in setup_marimoserver() are no longer in marimo "
        f"edit: {sorted(missing)}\n"
        "Update __init__.py to remove or replace them."
    )


# ---------------------------------------------------------------------------
# Standalone entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        hardcoded, exposed, excluded, unknown = check_parity()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    print_report(hardcoded, exposed, excluded, unknown)
    sys.exit(1 if unknown else 0)
