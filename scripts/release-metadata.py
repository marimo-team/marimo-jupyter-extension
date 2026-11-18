"""Read coordinated release metadata; --sync updates version mirrors."""

import json
import re
import subprocess
import sys
from pathlib import Path

version = subprocess.check_output(
    [
        "uv",
        "version",
        "--package",
        "marimo-jupyter-extension",
        "--frozen",
        "--short",
    ],
    text=True,
).strip()
path = Path("marimo_jupyter_extension/__init__.py")
pattern = '^__version__ = "[^"\\n]+"$'
text = path.read_text(encoding="utf-8")
if len(re.findall(pattern, text, flags=re.MULTILINE)) != 1:
    raise ValueError(f"Expected one __version__ assignment in {path}")
if "--sync" in sys.argv:
    path.write_text(
        re.sub(
            pattern, f'__version__ = "{version}"', text, flags=re.MULTILINE
        ),
        encoding="utf-8",
    )
elif f'__version__ = "{version}"' not in text.splitlines():
    raise ValueError(f"Version mismatch in {path}")
print(json.dumps({"version": version}))
