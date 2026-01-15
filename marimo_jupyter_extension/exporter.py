"""nbconvert exporter for marimo format."""

import json
import tempfile
from pathlib import Path

from nbconvert.exporters import Exporter
from traitlets import default

from .convert import convert_notebook_to_marimo


class MarimoExporter(Exporter):
    """Export Jupyter notebooks to marimo .py format.

    This exporter integrates with JupyterLab's "File > Save and Export
    Notebook As" menu.
    """

    export_from_notebook = "marimo"
    output_mimetype = "text/x-python"

    @default("file_extension")
    def _file_extension_default(self):
        return ".py"

    def from_notebook_node(self, nb, resources=None, **kwargs):
        """Convert notebook to marimo format.

        Args:
            nb: NotebookNode object
            resources: Additional resources (paths, metadata, etc.)
            **kwargs: Additional keyword arguments

        Returns:
            Tuple of (output, resources) where output is the converted string
        """
        if resources is None:
            resources = {}

        # Write notebook to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ipynb", delete=False
        ) as tmp_in:
            json.dump(nb, tmp_in)
            tmp_in_path = tmp_in.name

        # Create temporary output file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp_out:
            tmp_out_path = tmp_out.name

        try:
            # Convert notebook using shared conversion logic
            convert_notebook_to_marimo(tmp_in_path, tmp_out_path)

            # Read converted output
            with open(tmp_out_path) as f:
                output = f.read()

            # Set output extension for nbconvert handler
            resources["output_extension"] = ".py"

            return (output, resources)

        finally:
            # Clean up temporary files
            Path(tmp_in_path).unlink(missing_ok=True)
            Path(tmp_out_path).unlink(missing_ok=True)
