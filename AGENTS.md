# marimo-jupyter-extension

Jupyter/JupyterLab extension that proxies marimo (server proxy + prebuilt labextension). Published to PyPI as `marimo-jupyter-extension`; the frontend npm package is `@marimo-team/jupyter-extension`.

## Development

Dual toolchain. TypeScript lives in `labextension/` (pnpm); the Python server extension is at the repo root (uv + ruff).

```bash
# Frontend — run inside labextension/
pnpm install
pnpm run test          # vitest
pnpm run typecheck     # tsc --noEmit
pnpm run lint:check    # biome + eslint (no writes)
pnpm run lint:biome    # biome autofix   (lint:eslint for eslint --fix)
pnpm run format        # biome format --write   (format:check to verify)
pnpm run build         # dev build (build:prod for release)

# Python — run at repo root
uv sync
uv run pytest
uvx ruff format . && uvx ruff check .
```

- Do NOT run `pnpm run lint` — it invokes a nonexistent `run-s2` binary and fails; use `lint:check` / `lint:biome` / `lint:eslint` instead.
- Frontend commands must run from `labextension/`; pnpm is pinned via `packageManager` there.
