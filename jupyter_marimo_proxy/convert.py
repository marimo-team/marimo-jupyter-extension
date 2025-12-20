"""Shared notebook conversion logic."""

import subprocess

from .config import get_config
from .executable import get_marimo_command


def convert_notebook_to_marimo(input_path: str, output_path: str) -> None:
    """Convert a Jupyter notebook to marimo format.

    Args:
        input_path: Path to input .ipynb file
        output_path: Path to output .py file

    Raises:
        RuntimeError: If conversion fails
    """
    config = get_config()
    marimo_cmd = get_marimo_command(config)

    result = subprocess.run(
        [*marimo_cmd, "convert", input_path, "-o", output_path],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"marimo convert failed: {result.stderr or result.stdout}"
        )
