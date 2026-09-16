"""Execute and validate one deterministic shard of the repository notebooks."""

import argparse
import subprocess
import sys
from pathlib import Path

from run_notebooks import SKIP_NOTEBOOKS


ROOT_DIR = Path(__file__).parent.parent
RUNNER_PATH = Path(__file__).with_name("run_notebooks.py")
VALIDATOR_PATH = ROOT_DIR / "tests" / "test_notebook_execution.py"


def discover_notebooks(root_dir: Path = ROOT_DIR) -> list[Path]:
    """Return the sorted notebooks that the runner executes by default."""
    return sorted(
        path.resolve()
        for path in root_dir.glob("*.ipynb")
        if path.name not in SKIP_NOTEBOOKS
    )


def select_shard(
    notebooks: list[Path], shard_index: int, shard_count: int
) -> list[Path]:
    """Select one non-empty strided shard, rejecting unsafe configurations."""
    if shard_count <= 0:
        raise ValueError("shard count must be greater than zero")
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard index must be at least zero and less than shard count")

    selected = notebooks[shard_index::shard_count]
    # Both downstream CLIs interpret no paths as "all notebooks".
    if not selected:
        raise ValueError("selected shard contains no notebooks")
    return selected


def execute_and_validate(notebooks: list[Path], isolated: bool = False) -> None:
    """Run both stages with exactly the same absolute notebook arguments."""
    notebook_args = [str(path.resolve()) for path in notebooks]
    runner_command = [sys.executable, "-u", str(RUNNER_PATH)]
    if isolated:
        runner_command.append("--isolated")
    subprocess.run([*runner_command, *notebook_args], check=True)
    subprocess.run(
        [sys.executable, "-u", str(VALIDATOR_PATH), *notebook_args], check=True
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute and validate a deterministic shard of notebooks."
    )
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument(
        "--isolated",
        action="store_true",
        help="run notebooks against only the packages in their install lines",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        notebooks = select_shard(
            discover_notebooks(), args.shard_index, args.shard_count
        )
    except ValueError as error:
        parser.error(str(error))

    execute_and_validate(notebooks, isolated=args.isolated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
