"""
Execute notebooks, skipping cells that contain %pip install lines.

Clears all outputs first, then runs and saves with updated outputs.

Notebooks are executed in parallel across processes (each notebook is mostly
waiting on network I/O to S3, so parallelism is a big speedup). Control the
worker count with the NOTEBOOK_WORKERS environment variable; it defaults to the
number of CPUs. Set NOTEBOOK_WORKERS=1 to run sequentially (useful for
debugging).

Usage:
    uv run python .internal/run_notebooks.py [notebook1.ipynb notebook2.ipynb ...]

If no notebooks are specified, runs all notebooks in the root directory.
"""

import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import nbformat
from nbclient import NotebookClient

SKIP_MARKER = "pip install"

# Notebooks to skip by default (e.g. one-off or WIP notebooks)
SKIP_NOTEBOOKS = {"noaa-stations+gefs.ipynb"}


def run_notebook(notebook_path: Path) -> list[str]:
    """Execute a single notebook and save it. Returns log lines to print.

    Raises on execution failure (propagated to the caller so CI fails).
    """
    messages = [f"Running {notebook_path.name}..."]

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
    messages.append(f"  Saved {notebook_path.name} ({size_mb:.1f} MB)")
    if size_mb > 10:
        messages.append(
            f"  ⚠ WARNING: {notebook_path.name} is too large ({size_mb:.1f} MB). "
            "Reduce notebook size."
        )
    return messages


def main() -> int:
    root_dir = Path(__file__).parent.parent

    if len(sys.argv) > 1:
        notebooks = [Path(arg) for arg in sys.argv[1:]]
    else:
        notebooks = sorted(
            p for p in root_dir.glob("*.ipynb") if p.name not in SKIP_NOTEBOOKS
        )

    if not notebooks:
        print("No notebooks to run.")
        return 0

    default_workers = os.cpu_count() or 1
    workers = int(os.environ.get("NOTEBOOK_WORKERS", default_workers))
    workers = max(1, min(workers, len(notebooks)))

    failures: list[tuple[str, BaseException]] = []

    if workers == 1:
        for nb_path in notebooks:
            try:
                for line in run_notebook(nb_path):
                    print(line, flush=True)
            except BaseException as exc:  # noqa: BLE001 - report and continue
                failures.append((nb_path.name, exc))
                print(f"  ✗ FAILED {nb_path.name}: {exc}", flush=True)
    else:
        print(f"Running {len(notebooks)} notebooks with {workers} workers...", flush=True)
        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_nb = {
                executor.submit(run_notebook, nb_path): nb_path
                for nb_path in notebooks
            }
            for future in as_completed(future_to_nb):
                nb_path = future_to_nb[future]
                try:
                    for line in future.result():
                        print(line, flush=True)
                except BaseException as exc:  # noqa: BLE001 - report and continue
                    failures.append((nb_path.name, exc))
                    print(f"  ✗ FAILED {nb_path.name}: {exc}", flush=True)

    if failures:
        print(f"\n{len(failures)} notebook(s) failed:", flush=True)
        for name, exc in failures:
            print(f"  - {name}: {type(exc).__name__}: {exc}", flush=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
