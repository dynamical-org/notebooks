"""
Validate that all notebooks have been executed exactly once from a fresh kernel,
top to bottom, with pip install cells skipped.

Checks:
- Pip install cells have execution_count=None and no outputs (not run).
- Every other code cell has a non-null execution_count (was run).
- The first executed cell's count is consistent with a fresh kernel
  (1 if pip cells weren't executed, or pip_count + 1 if they were).
- Execution counts are strictly sequential with no gaps or repeats,
  proving a single clean run from top to bottom.
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

    pip_cell_count = 0
    executed_counts: list[tuple[int, int]] = []  # (cell_index, execution_count)

    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue

        is_pip_cell = SKIP_MARKER in cell.source

        if is_pip_cell:
            pip_cell_count += 1
            if cell.execution_count is not None:
                errors.append(
                    f"Cell {i}: pip install cell should have execution_count=None, "
                    f"got {cell.execution_count}"
                )
            if cell.outputs:
                errors.append(
                    f"Cell {i}: pip install cell should have no outputs"
                )
            continue

        if cell.execution_count is None:
            errors.append(f"Cell {i}: execution_count is None (cell was not executed)")
            continue

        executed_counts.append((i, cell.execution_count))

    if not executed_counts:
        errors.append("No executed code cells found")
        return errors

    # Verify the notebook was run from a fresh kernel restart, top to bottom.
    # A fresh kernel starts execution counts at 1. Pip install cells may or may
    # not have consumed kernel counts (run_notebooks.py executes a no-op
    # placeholder that consumes a count, but older runs may not have). The first
    # executed cell's count must be consistent with a fresh kernel either way.
    first_cell, first_count = executed_counts[0]
    valid_first_counts = {1, pip_cell_count + 1}
    if first_count not in valid_first_counts:
        errors.append(
            f"Cell {first_cell}: expected execution_count in {valid_first_counts} "
            f"(fresh kernel with {pip_cell_count} pip cell(s)), "
            f"got {first_count} — notebook may not have been run from a fresh kernel"
        )

    # Execution counts must be strictly sequential (each increments by 1).
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
