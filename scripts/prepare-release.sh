#!/usr/bin/env bash
set -euo pipefail
uv version --package marimo-jupyter-extension --frozen "$1"
python3 scripts/release-metadata.py --sync
