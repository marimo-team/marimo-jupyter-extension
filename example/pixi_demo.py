# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["marimo>=0.25.0"]
# [tool.pixi.workspace]
# channels = ["conda-forge"]
# [tool.pixi.dependencies]
# numpy = ">=2,<3"
# ///

import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import sys
    from pathlib import Path

    import marimo as mo
    import numpy as np

    return Path, mo, np, sys


@app.cell
def _(mo):
    mo.md("""
    # Pixi sandbox

    Use **Default (no venv)** to install NumPy from conda-forge with Pixi.

    Change the notebook environment to **venv (numpy)** to compare the package paths.
    """)
    return


@app.cell
def _(Path, mo, np, sys):
    conda_prefix = next(
        (
            str(path)
            for path in Path(np.__file__).parents
            if (path / "conda-meta").is_dir()
        ),
        "None (NumPy is outside a conda environment)",
    )
    mo.ui.table(
        [
            {"Setting": "Python", "Value": sys.executable},
            {"Setting": "NumPy version", "Value": np.__version__},
            {"Setting": "NumPy path", "Value": np.__file__},
            {"Setting": "Conda prefix", "Value": conda_prefix},
        ],
        selection=None,
    )
    return


@app.cell
def _(mo):
    count = mo.ui.slider(1, 20, value=5, label="Number of squares")
    count
    return (count,)


@app.cell
def _(count, np):
    np.arange(1, count.value + 1) ** 2
    return


if __name__ == "__main__":
    app.run()
