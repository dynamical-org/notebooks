"""Read the dependency declarations in notebook Colab install cells."""

import json
import re
import shlex
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
# Kernel/execution tooling is the only addition to the install-line dependency closure.
RUNNER_PACKAGES = ("nbclient", "nbformat", "ipykernel")
INSTALL_LINE = re.compile(r"^\s*!?uv\s+pip\s+install\s+(.+)$")


def normalize(name: str) -> str:
    """Normalize distribution names as specified by PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str:
    """Extract a name from a package requirement, including extras/version bounds."""
    match = re.fullmatch(
        r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[A-Za-z0-9,._-]+\])?(?:\s*[<>=!~].+)?",
        requirement,
    )
    if match is None:
        raise ValueError(f"unsupported install requirement: {requirement!r}")
    return normalize(match.group(1))


def install_line_packages(notebook_path: Path) -> tuple[str, ...]:
    """Return one canonical install group; missing/ambiguous declarations fail."""
    notebook = json.loads(notebook_path.read_text())
    lines = [
        match.group(1)
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
        for line in "".join(cell["source"]).splitlines()
        if (match := INSTALL_LINE.fullmatch(line))
    ]
    if len(lines) != 1:
        raise ValueError("expected exactly one '!uv pip install ...' line")
    packages = shlex.split(lines[0], comments=True)
    if not packages:
        raise ValueError("install line has no packages")
    for package in packages:
        requirement_name(package)
    return tuple(sorted(set(packages)))


def project_dependencies() -> set[str]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return {requirement_name(dep) for dep in pyproject["project"]["dependencies"]}
