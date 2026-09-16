import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock


COORDINATOR_PATH = (
    Path(__file__).parent.parent / ".internal" / "test_notebooks.py"
)
SPEC = importlib.util.spec_from_file_location("test_notebooks_coordinator", COORDINATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
coordinator = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(COORDINATOR_PATH.parent))
try:
    SPEC.loader.exec_module(coordinator)
finally:
    sys.path.pop(0)


class NotebookCoordinatorTests(unittest.TestCase):
    def test_shards_are_complete_disjoint_and_exclude_skipped_notebooks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            expected = [root / "a.ipynb", root / "b.ipynb", root / "c.ipynb"]
            for path in [*expected, root / "noaa-stations+gefs.ipynb"]:
                path.touch()

            notebooks = coordinator.discover_notebooks(root)
            first = coordinator.select_shard(notebooks, 0, 2)
            second = coordinator.select_shard(notebooks, 1, 2)

            self.assertEqual(notebooks, [path.resolve() for path in expected])
            self.assertEqual(set(first) | set(second), set(notebooks))
            self.assertTrue(set(first).isdisjoint(second))

    def test_rejects_invalid_shard_configuration(self):
        notebooks = [Path("notebook.ipynb")]

        for shard_index, shard_count in [(0, 0), (-1, 1), (1, 1)]:
            with self.subTest(shard_index=shard_index, shard_count=shard_count):
                with self.assertRaises(ValueError):
                    coordinator.select_shard(notebooks, shard_index, shard_count)

    def test_rejects_empty_shard_before_starting_a_subprocess(self):
        with (
            mock.patch.object(
                coordinator, "discover_notebooks", return_value=[Path("only.ipynb")]
            ),
            mock.patch.object(coordinator.subprocess, "run") as run,
            redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as raised:
                coordinator.main(["--shard-index", "1", "--shard-count", "2"])

            self.assertEqual(raised.exception.code, 2)
            run.assert_not_called()

    def test_runner_and_validator_receive_the_same_absolute_paths(self):
        notebooks = [Path("first.ipynb"), Path("nested/second.ipynb")]

        with mock.patch.object(coordinator.subprocess, "run") as run:
            coordinator.execute_and_validate(notebooks)

        self.assertEqual(run.call_count, 2)
        runner_command = run.call_args_list[0].args[0]
        validator_command = run.call_args_list[1].args[0]
        expected = [str(path.resolve()) for path in notebooks]
        self.assertEqual(runner_command[3:], expected)
        self.assertEqual(validator_command[3:], expected)
        self.assertEqual(runner_command[:2], [coordinator.sys.executable, "-u"])
        self.assertEqual(validator_command[:2], [coordinator.sys.executable, "-u"])
        self.assertEqual(run.call_args_list[0].kwargs, {"check": True})
        self.assertEqual(run.call_args_list[1].kwargs, {"check": True})

    def test_execution_failure_prevents_validation_and_propagates(self):
        failure = subprocess.CalledProcessError(7, ["runner"])

        with mock.patch.object(
            coordinator.subprocess, "run", side_effect=failure
        ) as run:
            with self.assertRaises(subprocess.CalledProcessError) as raised:
                coordinator.execute_and_validate([Path("notebook.ipynb")])

        self.assertIs(raised.exception, failure)
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
