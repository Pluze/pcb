from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
