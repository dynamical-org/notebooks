# dynamical.org notebooks

This repo contains example Jupyter notebooks for the [dynamical.org](https://dynamical.org/catalog/) weather and climate dataset catalog. Each notebook demonstrates how to access and work with a specific dataset using xarray/zarr. Most notebooks have two versions: a standard Zarr version and an Icechunk variant that reads from S3-backed Icechunk stores.

## Organization

- **Root directory**: All notebooks live at the top level. Standard notebooks follow the pattern `<provider>-<dataset>-<variant>.ipynb`. Icechunk variants are auto-generated with an `-icechunk.ipynb` suffix — never edit icechunk notebooks directly, as they are overwritten by the tooling. Always edit the non-icechunk version.
- **`.internal/`**: Internal tooling scripts (see below).
- **`pyproject.toml`**: Python dependencies managed with `uv`. Python 3.12+.
- **`environment.yml`**: Conda environment for SageMaker Studio Lab.
- **`connection_diagnostics.py`**: Troubleshooting utility for connectivity to dynamical.org.

## .internal/ tools

### `run_notebooks.py`

Executes notebooks to produce fresh outputs. Skips `pip install` cells during execution (restores them afterward). Always regenerates icechunk variants afterward by calling `create_icechunk_versions.py`.

**When to use**: After making logical code changes to a notebook. Only run the specific notebooks you changed — the underlying datasets update continuously, so re-running unchanged notebooks creates unnecessary output diffs.

**How to use**:
```
# Run specific notebooks (preferred):
uv run .internal/run_notebooks.py <notebook1.ipynb> [notebook2.ipynb ...]

# Run all non-icechunk notebooks (rarely needed):
uv run .internal/run_notebooks.py
```

### `create_icechunk_versions.py`

Generates `-icechunk.ipynb` variants from standard notebooks by rewriting three cells: the title, the pip install cell, and the dataset-opening cell.

**When to use**: Generally don't run this directly, use run_notebooks.py on new or changed notebooks and it will create icechunk versions automatically.

**How to use**:
```
uv run .internal/create_icechunk_versions.py
```

When adding a new notebook, first register it in the `NOTEBOOKS` constant at the top of this script with its icechunk S3 URI. The user will have to provide this URI to you.

## Before committing

Always run `uv run .internal/run_notebooks.py` on any notebooks you changed before committing.
