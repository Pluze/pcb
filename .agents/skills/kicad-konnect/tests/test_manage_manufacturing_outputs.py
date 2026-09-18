from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "manage_manufacturing_outputs.py"
SPEC = importlib.util.spec_from_file_location("manage_manufacturing_outputs", SCRIPT)
assert SPEC and SPEC.loader
manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)


class ManufacturingManagerTests(unittest.TestCase):
    def make_design(self, root: Path, name: str) -> None:
        design = root / name
        design.mkdir(parents=True)
        (design / f"{name}.kicad_pcb").write_text("fixture\n", encoding="utf-8")

    @mock.patch.object(manager.subprocess, "run")
    def test_selected_design_limits_all_exporters(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_design(root, "Alpha")
            self.make_design(root, "Beta")
            argv = [str(SCRIPT), "audit", "--root", str(root), "--design", "Beta"]
            with mock.patch.object(sys, "argv", argv):
                self.assertEqual(manager.main(), 0)
        self.assertEqual(run.call_count, len(manager.EXPORTERS))
        for call in run.call_args_list:
            self.assertEqual(Path(call.args[0][-1]).name, "Beta")

    @mock.patch.object(manager.subprocess, "run")
    def test_unknown_selected_design_fails_before_export(self, run: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_design(root, "Alpha")
            argv = [str(SCRIPT), "audit", "--root", str(root), "--design", "Missing"]
            with mock.patch.object(sys, "argv", argv):
                self.assertEqual(manager.main(), 1)
        run.assert_not_called()

    @mock.patch.object(manager.subprocess, "run")
    def test_failure_stops_before_later_exporters_and_designs(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=7)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_design(root, "Alpha")
            self.make_design(root, "Beta")
            argv = [str(SCRIPT), "audit", "--root", str(root)]
            with mock.patch.object(sys, "argv", argv):
                self.assertEqual(manager.main(), 7)
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
