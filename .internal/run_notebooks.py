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
Notebooks are grouped by install requirements within each invocation. Each group
gets a fresh environment; uv reuses its download/install cache between groups.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from collections import defaultdict
from pathlib import Path

from notebook_deps import RUNNER_PACKAGES, install_line_packages

SKIP_MARKER = "pip install"

# Notebooks to skip by default (e.g. one-off or WIP notebooks)
SKIP_NOTEBOOKS = {"noaa-stations+gefs.ipynb"}


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
        kernel_name = "notebook-isolated-" + uuid.uuid4().hex
        python = env_dir / "bin" / "python"

        env = dict(os.environ)
        for name in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
            env.pop(name, None)
        env["PYTHONNOUSERSITE"] = "1"
        env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
        started = time.monotonic()
        subprocess.run(
            ["uv", "venv", "-q", "--python", sys.executable, str(env_dir)],
            env=env, check=True,
        )
        subprocess.run(
            ["uv", "pip", "install", "-q", "--python", str(python),
             *packages, *RUNNER_PACKAGES],
            env=env, check=True,
        )
        subprocess.run(
            [str(python), "-m", "ipykernel", "install",
             "--prefix", str(kernels), "--name", kernel_name],
            env=env, check=True,
        )

        subprocess.run(
            ["uv", "pip", "freeze", "--python", str(python)], env=env, check=True,
        )
        env["JUPYTER_PATH"] = str(kernels / "share" / "jupyter")
        print(f"  Environment ready in {time.monotonic() - started:.1f}s: {python}", flush=True)
        result = subprocess.run(
            [str(python), "-u", str(Path(__file__).resolve()),
             "--kernel", kernel_name, *(str(n.resolve()) for n in notebooks)],
            env=env, check=False,
        )
    return result.returncode == 0


def run_isolated(notebooks: list[Path]) -> int:
    """Run each notebook against only its own install line. Returns an exit code."""
    groups: dict[tuple[str, ...], list[Path]] = defaultdict(list)
    for notebook_path in notebooks:
        try:
            packages = install_line_packages(notebook_path)
        except (ValueError, OSError) as error:
            print(f"ERROR: {notebook_path.name}: {error}")
            return 1
        groups[packages].append(notebook_path)

    failures: list[str] = []
    for packages, group in sorted(groups.items()):
        print(f"\n=== {' '.join(packages)} ({len(group)} notebook(s)) ===", flush=True)
        try:
            passed = run_group(packages, group)
        except subprocess.CalledProcessError:
            traceback.print_exc()
            passed = False
        if not passed:
            failures.append(" ".join(packages))

    if failures:
        print("\nDependency groups with failures (see errors above):")
        for name in failures:
            print(f"  {name}")
        return 1
    print("\nEvery notebook ran against only what its install line names.")
    return 0


def run_notebook(notebook_path: Path, kernel_name: str = "python3") -> None:
    print(f"Running {notebook_path.name}...", flush=True)

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
    print(f"  Saved {notebook_path.name} ({size_mb:.1f} MB)", flush=True)
    if size_mb > 10:
        print(f"  ⚠ WARNING: {notebook_path.name} is too large ({size_mb:.1f} MB). Reduce notebook size.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--kernel", default="python3", help=argparse.SUPPRESS)
    parser.add_argument("notebooks", nargs="*", type=Path)
    args = parser.parse_args()
    root_dir = Path(__file__).parent.parent
    notebooks = args.notebooks or sorted(
        p for p in root_dir.glob("*.ipynb") if p.name not in SKIP_NOTEBOOKS
    )
    if not notebooks:
        parser.error("no notebooks found")
    if args.isolated:
        return run_isolated(notebooks)
    failed = False
    for notebook in notebooks:
        try:
            run_notebook(notebook, args.kernel)
        except Exception:
            print(f"FAILED: {notebook.name}", flush=True)
            traceback.print_exc()
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
