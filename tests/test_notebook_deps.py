"""Install declarations must be explicit and compared by distribution name."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".internal"))
from notebook_deps import install_line_packages, requirement_name


class InstallDeclarations(unittest.TestCase):
    def notebook(self, directory, sources):
        path = Path(directory) / "example.ipynb"
        path.write_text(json.dumps({"cells": [{"cell_type": "code", "source": s} for s in sources]}))
        return path

    def test_requirement_names_include_extras_and_versions(self):
        self.assertEqual(requirement_name("Foo_Bar[array]>=1.2"), "foo-bar")

    def test_grouping_ignores_order_and_duplicate_requirements(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.notebook(directory, ["!uv pip install numpy 'foo[array]>=1.2' numpy"])
            self.assertEqual(install_line_packages(path), ("foo[array]>=1.2", "numpy"))

    def test_missing_or_multiple_lines_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            for sources in (["# uv pip install numpy"], ["!uv pip install numpy", "!uv pip install pandas"]):
                with self.subTest(sources=sources), self.assertRaises(ValueError):
                    install_line_packages(self.notebook(directory, sources))

    def test_unsupported_options_fail_instead_of_becoming_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                install_line_packages(self.notebook(directory, ["!uv pip install --index-url https://example.org numpy"]))
