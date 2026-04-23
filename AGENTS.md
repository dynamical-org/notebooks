# dynamical.org notebooks

This repo contains example Jupyter notebooks for the [dynamical.org](https://dynamical.org/catalog/) weather and climate dataset catalog. Each notebook demonstrates how to access and work with a specific dataset using the [`dynamical-catalog`](https://pypi.org/project/dynamical-catalog/) Python library, which loads datasets from S3-backed Icechunk stores as xarray datasets.

## Organization

- **Root directory**: All notebooks live at the top level, following the pattern `<provider>-<dataset>-<variant>.ipynb`.
- **`.internal/`**: Internal tooling scripts (see below).
- **`pyproject.toml`**: Python dependencies managed with `uv`. Python 3.12+.
- **`environment.yml`**: Conda environment for SageMaker Studio Lab.
- **`connection_diagnostics.py`**: Troubleshooting utility for connectivity to dynamical.org.

## .internal/ tools

### `run_notebooks.py`

Executes notebooks to produce fresh outputs. Skips `pip install` cells during execution (restores them afterward).

**When to use**: After making logical code changes to a notebook. Only run the specific notebooks you changed — the underlying datasets update continuously, so re-running unchanged notebooks creates unnecessary output diffs.

**How to use**:
```
# Run specific notebooks (preferred):
uv run .internal/run_notebooks.py <notebook1.ipynb> [notebook2.ipynb ...]

# Run all notebooks (rarely needed):
uv run .internal/run_notebooks.py
```

## Before committing

Always run `uv run .internal/run_notebooks.py` on any notebooks you changed before committing. Keep notebooks < 10MB.
