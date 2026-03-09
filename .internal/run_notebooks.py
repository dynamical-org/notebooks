"""
Execute notebooks, skipping cells that contain %pip install lines.

Clears all outputs first, then runs and saves with updated outputs.

Usage:
    uv run python .internal/run_notebooks.py [notebook1.ipynb notebook2.ipynb ...]

If no notebooks are specified, runs all non-icechunk notebooks in the root directory.

Always updates the icechunk versions of notebooks after running the main notebooks.
"""

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

from create_icechunk_versions import main as create_icechunk_versions

SKIP_MARKER = "%pip install"

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
    print(f"  Saved {notebook_path.name}")


def main():
    root_dir = Path(__file__).parent.parent

    if len(sys.argv) > 1:
        notebooks = [Path(arg) for arg in sys.argv[1:]]
    else:
        notebooks = sorted(
            p
            for p in root_dir.glob("*.ipynb")
            if not p.name.endswith("-icechunk.ipynb") and p.name not in SKIP_NOTEBOOKS
        )

    for nb_path in notebooks:
        run_notebook(nb_path)

    # Regenerate icechunk versions of notebooks
    print("\nRegenerating icechunk notebook versions...")
    create_icechunk_versions()


if __name__ == "__main__":
    main()
