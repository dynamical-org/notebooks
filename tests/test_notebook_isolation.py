"""Exercise real kernels so a project-environment fallback cannot pass silently."""
import importlib.util
import json
import os
import re
import shutil
import site
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ".internal" / "run_notebooks.py"


@unittest.skipUnless(shutil.which("uv"), "uv is required for real environment isolation")
class KernelIsolation(unittest.TestCase):
    def test_missing_import_fails_then_declared_import_passes_in_private_kernel(self):
        # These exist in the project environment and must not leak into the kernel.
        self.assertIsNotNone(importlib.util.find_spec("numpy"))
        self.assertIsNotNone(importlib.util.find_spec("duckdb"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrong_kernel = root / "jupyter" / "kernels" / "python3"
            wrong_kernel.mkdir(parents=True)
            (wrong_kernel / "kernel.json").write_text(json.dumps({
                "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                "display_name": "Project kernel that must not be used", "language": "python",
            }))
            env = dict(os.environ, VIRTUAL_ENV=sys.prefix,
                       PYTHONPATH=os.pathsep.join(site.getsitepackages()),
                       JUPYTER_PATH=str(root / "jupyter"))

            def notebook(name, packages, source):
                path = root / name
                nbformat.write(nbformat.v4.new_notebook(cells=[
                    nbformat.v4.new_code_cell("!uv pip install " + packages),
                    nbformat.v4.new_code_cell(source),
                ]), path)
                return path

            def run(*paths):
                return subprocess.run(
                    [sys.executable, "-u", str(RUNNER), "--isolated", *map(str, paths)],
                    env=env, capture_output=True, text=True, timeout=180,
                )

            bad = notebook("missing.ipynb", "nbformat", "import numpy")
            failed = run(bad)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("ModuleNotFoundError", failed.stdout + failed.stderr)
            self.assertIn("No module named 'numpy'", failed.stdout + failed.stderr)

            source = """import sys, importlib.util
import numpy
assert importlib.util.find_spec('duckdb') is None
assert '_seen_in_previous_notebook' not in globals()
_seen_in_previous_notebook = True
print(sys.executable)
"""
            good = notebook("declared.ipynb", "numpy", source)
            other = notebook("fresh-kernel.ipynb", "numpy", source)
            passed = run(good, other)
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            interpreters = re.findall(r"Environment ready in .*?: (.+)", passed.stdout)
            self.assertEqual(len(interpreters), 1, passed.stdout)
            self.assertNotEqual(interpreters[0], sys.executable)
            for path in (good, other):
                executed = nbformat.read(path, as_version=4)
                self.assertEqual(executed.cells[1].outputs[0].text.strip(), interpreters[0])
                self.assertIsNone(executed.cells[0].execution_count)
                self.assertEqual(executed.cells[1].execution_count, 2)
                self.assertEqual(passed.stdout.count(f"Running {path.name}..."), 1)
