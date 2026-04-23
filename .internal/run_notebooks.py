"""
Execute notebooks, skipping cells that contain %pip install lines.

Clears all outputs first, then runs and saves with updated outputs.

Usage:
    uv run python .internal/run_notebooks.py [notebook1.ipynb notebook2.ipynb ...]

If no notebooks are specified, runs all notebooks in the root directory.
"""

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

SKIP_MARKER = "pip install"

# Notebooks to skip by default (e.g. one-off or WIP notebooks)
SKIP_NOTEBOOKS = {"noaa-stations+gefs.ipynb"}


def run_notebook(notebook_path: Path) -> None:
    print(f"Running {notebook_path.name}...")

    nb = nbformat.read(notebook_path, as_version=4)

    # Clear all outputs
    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None

    # Tag cells to skip so we can restore them after execution
    skip_sources: dict[int, str] = {}
    for i, cell in enumerate(nb.cells):
        if cell.cell_type == "code" and SKIP_MARKER in cell.source:
            skip_sources[i] = cell.source
            # Replace with a no-op so nbclient still "executes" it
            # but nothing happens
            cell.source = "# skipped: pip install cell"

    client = NotebookClient(
        nb,
        timeout=600,
        kernel_name="python3",
        resources={"metadata": {"path": str(notebook_path.parent)}},
    )

    try:
        client.execute()
    finally:
        # Restore original source for skipped cells
        for i, source in skip_sources.items():
            nb.cells[i].source = source
            # Clear the output from the no-op
            nb.cells[i].outputs = []
            nb.cells[i].execution_count = None

    nbformat.write(nb, notebook_path)

    size_mb = notebook_path.stat().st_size / (1024 * 1024)
    print(f"  Saved {notebook_path.name} ({size_mb:.1f} MB)")
    if size_mb > 10:
        print(f"  ⚠ WARNING: {notebook_path.name} is too large ({size_mb:.1f} MB). Reduce notebook size.")


def main():
    root_dir = Path(__file__).parent.parent

    if len(sys.argv) > 1:
        notebooks = [Path(arg) for arg in sys.argv[1:]]
    else:
        notebooks = sorted(
            p for p in root_dir.glob("*.ipynb") if p.name not in SKIP_NOTEBOOKS
        )

    for nb_path in notebooks:
        run_notebook(nb_path)


if __name__ == "__main__":
    main()
