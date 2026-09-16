"""Check every notebook install requirement is declared in project.dependencies.

The isolated runner separately checks that this dependency closure can execute
its notebook. Static checking includes notebooks excluded from execution.
"""

import sys

from notebook_deps import ROOT, install_line_packages, project_dependencies, requirement_name


def main() -> int:
    declared = project_dependencies()
    problems: list[str] = []
    notebooks = sorted(ROOT.glob("*.ipynb"))
    if not notebooks:
        print("ERROR: No notebooks found")
        return 1
    for notebook in notebooks:
        try:
            packages = install_line_packages(notebook)
        except ValueError as error:
            problems.append(f"{notebook.name}: {error}")
            continue
        undeclared = sorted({requirement_name(p) for p in packages} - declared)
        if undeclared:
            problems.append(f"{notebook.name}: undeclared {', '.join(undeclared)}")
    if problems:
        print("Invalid notebook install declarations:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"All {len(notebooks)} install lines are covered by project dependencies.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
