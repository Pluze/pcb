from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "headless_pcb_review.py"
SPEC = importlib.util.spec_from_file_location("headless_pcb_review", SCRIPT)
assert SPEC and SPEC.loader
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


class HeadlessReviewTests(unittest.TestCase):
    def test_drc_summary_preserves_severity_and_type_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "drc.json"
            report.write_text(json.dumps({
                "violations": [
                    {"severity": "warning", "type": "lib_footprint_mismatch"},
                    {"severity": "error", "type": "clearance"},
                    {"severity": "error", "type": "clearance"},
                ],
                "unconnected_items": [{"type": "unconnected_items"}],
            }), encoding="utf-8")
            self.assertEqual(review.drc_summary(report), {
                "violations": 3,
                "unconnected": 1,
                "severities": {"warning": 1, "error": 2},
                "types": {"lib_footprint_mismatch": 1, "clearance": 2},
            })


    def test_rejects_incomplete_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "drc.json"
            report.write_text("{}")
            with self.assertRaisesRegex(ValueError, "invalid DRC report"):
                review.drc_summary(report)

    def test_explicit_cli_is_not_silently_substituted(self):
        with self.assertRaisesRegex(ValueError, "requested kicad-cli"):
            review.find_kicad_cli(Path("/nonexistent/explicit/kicad-cli"))

    def test_project_rules_are_preserved_and_source_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board = root / "sample.kicad_pcb"
            project = board.with_suffix(".kicad_pro")
            rules = board.with_suffix(".kicad_dru")
            for path in (board, project, rules):
                path.write_text(path.suffix)
            before = {p: p.read_bytes() for p in (board, project, rules)}
            staged_paths = []
            def command(args, log):
                staged = Path(args[-1])
                if "drc" in args:
                    staged_paths.append(staged)
                    self.assertEqual(staged.with_suffix(".kicad_pro").read_bytes(), before[project])
                    self.assertEqual(staged.with_suffix(".kicad_dru").read_bytes(), before[rules])
                    staged.write_text("refilled")
                    Path(args[args.index("--output") + 1]).write_text(
                        '{"violations":[],"unconnected_items":[]}'
                    )
                else:
                    Path(args[args.index("--output") + 1]).write_text("render")
            with mock.patch.object(review, "run", side_effect=command):
                first = review.review(board, root / "output", Path("cli"))
                second = review.review(board, root / "output", Path("cli"))
            self.assertEqual(first["status"], "pass")
            self.assertTrue(second["source_unchanged"])
            self.assertNotEqual(staged_paths[0], staged_paths[1])
            self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_rejects_missing_project_and_source_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board = root / "sample.kicad_pcb"
            board.write_text("board")
            with self.assertRaisesRegex(ValueError, "sibling"):
                review.review(board, root / "out", Path("cli"))
            board.with_suffix(".kicad_pro").write_text("{}")
            with self.assertRaisesRegex(ValueError, "isolated"):
                review.review(board, root, Path("cli"))


    @unittest.skipUnless(os.environ.get("PCB_REVIEW_REAL") == "1", "opt-in real KiCad regression")
    def test_real_project_rules_catch_defects_that_bare_board_misses(self):
        repository = SCRIPT.parents[4]
        source = repository / "Designs/Ionto_Current_Source_Core/Ionto_Current_Source_Core.kicad_pcb"
        cli = review.find_kicad_cli(None)
        with tempfile.TemporaryDirectory(prefix="pcb-review-regression-") as directory:
            root = Path(directory)
            board = root / source.name
            shutil.copy2(source, board)
            bare_report = root / "bare.json"
            subprocess.run([str(cli), "pcb", "drc", "--format", "json", "--output", str(bare_report), str(board)], check=True, capture_output=True)
            self.assertEqual(review.drc_summary(bare_report)["types"].get("track_width", 0), 0)
            project = json.loads(source.with_suffix(".kicad_pro").read_text())
            project["board"]["design_settings"]["rules"]["min_track_width"] = 2.0
            board.with_suffix(".kicad_pro").write_text(json.dumps(project))
            result = review.review(board, root / "output", cli)
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["drc"]["types"].get("track_width"), 53)
            self.assertTrue(result["source_unchanged"])


if __name__ == "__main__":
    unittest.main()
