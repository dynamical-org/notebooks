"""
Execute notebooks, skipping cells that contain %pip install lines.

Clears all outputs first, then runs and saves with updated outputs.

Usage:
    uv run python .internal/run_notebooks.py [notebook1.ipynb notebook2.ipynb ...]
    uv run python .internal/run_notebooks.py --isolated

If no notebooks are specified, runs all notebooks in the root directory.

`--isolated` runs each notebook against only the packages its own Colab install
line names, rather than the repo environment, so an install line that omits
something the notebook imports fails here instead of on a reader's first run.
Notebooks are grouped by install line, so the 21 notebooks need a handful of
environments rather than one each, and uv caches them between runs.
"""

import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from notebook_deps import RUNNER_PACKAGES, install_line_packages

SKIP_MARKER = "pip install"

# Notebooks to skip by default (e.g. one-off or WIP notebooks)
SKIP_NOTEBOOKS = {"noaa-stations+gefs.ipynb"}

KERNEL_NAME = "isolated"


def run_group(packages: tuple[str, ...], notebooks: list[Path]) -> bool:
    """Run `notebooks` against only `packages`. Returns True if they all passed.

    Builds an explicit throwaway environment rather than layering onto the
    project one. `uv run --with` discovers the repo's .venv and would let the
    notebook import packages its install line never named, so the check would
    pass no matter what the install line said.

    The kernel must come from that environment too: nbclient resolves the stock
    "python3" kernel to whichever jupyter finds first, so install a kernelspec
    into the throwaway environment and point JUPYTER_PATH at it.
    """
    with tempfile.TemporaryDirectory() as tmp:
        env_dir = Path(tmp) / "env"
        kernels = Path(tmp) / "kernels"
        python = env_dir / "bin" / "python"

        subprocess.run(["uv", "venv", "-q", str(env_dir)], check=True)
        subprocess.run(
            ["uv", "pip", "install", "-q", "--python", str(python),
             *packages, *RUNNER_PACKAGES],
            check=True,
        )
        subprocess.run(
            [str(python), "-m", "ipykernel", "install",
             "--prefix", str(kernels), "--name", KERNEL_NAME],
            check=True, capture_output=True,
        )

        env = dict(os.environ, JUPYTER_PATH=str(kernels / "share" / "jupyter"))
        env.pop("VIRTUAL_ENV", None)
        result = subprocess.run(
            [str(python), str(Path(__file__).resolve()),
             "--kernel", KERNEL_NAME, *(str(n.resolve()) for n in notebooks)],
            env=env, check=False,
        )
    return result.returncode == 0


def run_isolated(notebooks: list[Path]) -> int:
    """Run each notebook against only its own install line. Returns an exit code."""
    groups: dict[tuple[str, ...], list[Path]] = defaultdict(list)
    for notebook_path in notebooks:
        packages = install_line_packages(notebook_path)
        if packages is None:
            print(f"Skipping {notebook_path.name}: no install line to isolate against")
            continue
        groups[packages].append(notebook_path)

    failures: list[str] = []
    for packages, group in sorted(groups.items()):
        print(f"\n=== {' '.join(packages)} ({len(group)} notebook(s)) ===", flush=True)
        if not run_group(packages, group):
            failures.extend(n.name for n in group)

    if failures:
        print("\nFailed against their own install line:")
        for name in failures:
            print(f"  {name}")
        return 1
    print("\nEvery notebook ran against only what its install line names.")
    return 0


def run_notebook(notebook_path: Path, kernel_name: str = "python3") -> None:
    print(f"Running {notebook_path.name}...")

    # Imported here, not at module scope: --isolated orchestrates throwaway
    # environments using only the standard library, and installs these into each.
    import nbformat
    from nbclient import NotebookClient

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
        kernel_name=kernel_name,
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


def main() -> int:
    root_dir = Path(__file__).parent.parent
    args = sys.argv[1:]

    isolated = "--isolated" in args
    args = [a for a in args if a != "--isolated"]

    kernel_name = "python3"
    if "--kernel" in args:
        index = args.index("--kernel")
        kernel_name = args[index + 1]
        del args[index : index + 2]

    if args:
        notebooks = [Path(arg) for arg in args]
    else:
        notebooks = sorted(
            p for p in root_dir.glob("*.ipynb") if p.name not in SKIP_NOTEBOOKS
        )

    if isolated:
        return run_isolated(notebooks)

    for nb_path in notebooks:
        run_notebook(nb_path, kernel_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
