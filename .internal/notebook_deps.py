"""
Read the packages each notebook asks a Colab reader to install.

Every notebook carries a cell like:

    !uv pip install dynamical-catalog rioxarray

That line is the only dependency declaration a Colab reader ever sees, and CI
installs the repo's own dependencies instead, so nothing checks it.
"""

import json
import re
from pathlib import Path

INSTALL_MARKER = "uv pip install"

ROOT = Path(__file__).parent.parent

# Runner requirements, added to every isolated environment. A notebook does not
# import these; nbclient needs them to start a kernel and read the file.
RUNNER_PACKAGES = ("nbclient", "nbformat", "ipykernel")


def normalize(name: str) -> str:
    """PyPI treats runs of -_. as equal and is case insensitive (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def install_line_packages(notebook_path: Path) -> tuple[str, ...] | None:
    """Packages from the notebook's `uv pip install` cell, or None if it has no such cell."""
    notebook = json.loads(notebook_path.read_text())
    for cell in notebook["cells"]:
        source = "".join(cell["source"])
        if INSTALL_MARKER not in source:
            continue
        line = next(l for l in source.splitlines() if INSTALL_MARKER in l)
        args = line.split(INSTALL_MARKER, 1)[1].split()
        return tuple(a for a in args if not a.startswith("-"))
    return None


def project_dependencies() -> set[str]:
    """Normalized names from pyproject's [project.dependencies]."""
    import tomllib

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return {
        normalize(re.split(r"[<>=!~\[ ]", dep)[0])
        for dep in pyproject["project"]["dependencies"]
    }
