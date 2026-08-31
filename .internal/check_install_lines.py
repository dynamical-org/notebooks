"""
Check every notebook's Colab install line against pyproject's dependencies.

CI runs notebooks against the repo's environment, so an install line can name a
package the repo does not have, or omit one the notebook imports, and stay green
while every Colab reader hits an ImportError.

This catches the first half statically. `run_notebooks.py --isolated` catches the
second by running each notebook against only what its install line asks for.

Usage:
    uv run .internal/check_install_lines.py
"""

import sys

from notebook_deps import ROOT, install_line_packages, normalize, project_dependencies


def main() -> int:
    declared = project_dependencies()
    problems: list[str] = []

    for notebook_path in sorted(ROOT.glob("*.ipynb")):
        packages = install_line_packages(notebook_path)
        if packages is None:
            continue
        undeclared = sorted(
            {normalize(p) for p in packages} - declared - {"uv"}
        )
        if undeclared:
            problems.append(f"{notebook_path.name}: {', '.join(undeclared)}")

    if problems:
        print("Install line packages missing from pyproject dependencies:\n")
        for problem in problems:
            print(f"  {problem}")
        print(
            "\nAdd them to [project.dependencies] so the environment CI runs "
            "matches what a Colab reader installs, or drop them from the "
            "install line if the notebook does not need them."
        )
        return 1

    print(f"All install lines are covered by pyproject dependencies.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
