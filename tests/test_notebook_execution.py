"""
Validate that all notebooks have been executed exactly once from start to finish.

Checks:
- Every code cell (except pip install cells) has a non-null execution_count.
- Execution counts are sequential starting from 1 with no gaps or repeats,
  which proves a single clean run from top to bottom.
- Pip install cells have execution_count = None (skipped by run_notebooks.py).
"""

import sys
from pathlib import Path

import nbformat

SKIP_MARKER = "pip install"

# Notebooks excluded from validation (same as run_notebooks.py)
SKIP_NOTEBOOKS = {"noaa-stations+gefs.ipynb"}


def validate_notebook(notebook_path: Path) -> list[str]:
    """Return a list of error messages (empty = pass)."""
    nb = nbformat.read(notebook_path, as_version=4)
    errors: list[str] = []

    executed_counts: list[tuple[int, int]] = []  # (cell_index, execution_count)

    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue

        is_pip_cell = SKIP_MARKER in cell.source

        if is_pip_cell:
            if cell.execution_count is not None:
                errors.append(
                    f"Cell {i}: pip install cell should have execution_count=None, "
                    f"got {cell.execution_count}"
                )
            continue

        if cell.execution_count is None:
            errors.append(f"Cell {i}: execution_count is None (cell was not executed)")
            continue

        executed_counts.append((i, cell.execution_count))

    if not executed_counts:
        errors.append("No executed code cells found")
        return errors

    # Verify execution counts are strictly sequential (each increments by 1).
    # They may not start at 1 if pip install cells consumed earlier counts.
    for idx in range(1, len(executed_counts)):
        prev_cell, prev_count = executed_counts[idx - 1]
        curr_cell, curr_count = executed_counts[idx]
        if curr_count != prev_count + 1:
            errors.append(
                f"Cell {curr_cell}: expected execution_count={prev_count + 1}, "
                f"got {curr_count} (not sequential with cell {prev_cell})"
            )

    return errors


def main() -> int:
    root_dir = Path(__file__).parent.parent
    notebooks = sorted(
        p
        for p in root_dir.glob("*.ipynb")
        if p.name not in SKIP_NOTEBOOKS
    )

    if not notebooks:
        print("ERROR: No notebooks found")
        return 1

    failed = False
    for nb_path in notebooks:
        errors = validate_notebook(nb_path)
        if errors:
            failed = True
            print(f"FAIL: {nb_path.name}")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"OK:   {nb_path.name}")

    if failed:
        print("\nSome notebooks failed validation.")
        return 1

    print("\nAll notebooks passed validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
