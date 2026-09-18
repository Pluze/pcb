from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_circular_contact_board.py"
SPEC = importlib.util.spec_from_file_location("generate_circular_contact_board", SCRIPT)
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generator
SPEC.loader.exec_module(generator)


class CircularContactBoardTests(unittest.TestCase):
    @mock.patch.object(generator.subprocess, "run")
    def test_drc_validates_staged_candidate_before_final_write(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result" / "NewBoard.kicad_pcb"
            contents = generator.render_board(generator.BoardSpec(8, 10, 18.75), "NewBoard", 1.5, 0.8)
            generator.validate_with_kicad(Path("/fake/kicad-cli"), [(output, contents)])
            self.assertFalse(output.exists())
        command = run.call_args.args[0]
        self.assertIn("drc", command)
        self.assertTrue(command[-1].endswith("NewBoard.kicad_pcb"))

    @mock.patch.object(generator.subprocess, "run")
    def test_drc_failure_prevents_output(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="clearance violation",
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "NewBoard.kicad_pcb"
            contents = generator.render_board(generator.BoardSpec(8, 10, 18.75), "NewBoard", 1.5, 0.8)
            with self.assertRaisesRegex(ValueError, "clearance violation"):
                generator.validate_with_kicad(Path("/fake/kicad-cli"), [(output, contents)])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
