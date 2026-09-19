from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_pcb_workflow.py"
SCRIPTS = SCRIPT.parent
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("benchmark_pcb_workflow", SCRIPT)
assert SPEC and SPEC.loader
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class BenchmarkTests(unittest.TestCase):
    def make_repo(self, root: Path) -> None:
        for name, topology in (("Alpha", True), ("Beta", False)):
            design = root / "Designs" / name
            design.mkdir(parents=True)
            (design / f"{name}.kicad_pcb").write_text("fixture\n")
            if topology:
                (design / "schematic_topology.json").write_text("{}\n")

    @mock.patch.object(benchmark, "find_kicad_cli", return_value=Path("/fake/kicad-cli"))
    def test_scenario_call_counts_cover_common_and_complex_work(self, _: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            scratch = root / "scratch"
            scratch.mkdir()
            expected = {
                "manufacturing-full": (6, 1),
                "manufacturing-single": (3, 1),
                "repeat-unchanged": (6, 1),
                "schematic-validate": (2, 1),
                "new-pcb": (2, 1),
                "existing-pcb-inspection": (1, 1),
                "headless-pcb-review": (3, 1),
                "release-ready": (9, 1),
            }
            for scenario, counts in expected.items():
                baseline, candidate, _ = benchmark.scenario_commands(root, scenario, None, scratch)
                self.assertEqual((len(baseline), len(candidate)), counts, scenario)

    @mock.patch.object(benchmark.subprocess, "run")
    def test_group_stops_after_first_failure(self, run: mock.Mock) -> None:
        run.return_value = mock.Mock(returncode=3, stdout="", stderr="failure\n")
        result = benchmark.run_group([("one",), ("two",)], Path.cwd())
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["logical_calls"], 1)
        self.assertEqual(run.call_count, 1)

    def test_reduction_reports_proxy_metrics(self) -> None:
        self.assertEqual(benchmark.reduction(6, 1), 83.3)
        self.assertEqual(benchmark.reduction(100, 25), 75.0)
        self.assertIsNone(benchmark.reduction(0, 0))

    def test_legacy_timestamped_reports_are_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_dir = Path(directory)
            legacy = report_dir / "20260918-102454-new-pcb-a-b.json"
            current = report_dir / "new-pcb-a-b.json"
            legacy.write_text("{}\n", encoding="utf-8")
            current.write_text("{}\n", encoding="utf-8")
            benchmark.remove_legacy_reports(report_dir)
            self.assertFalse(legacy.exists())
            self.assertTrue(current.exists())


if __name__ == "__main__":
    unittest.main()
