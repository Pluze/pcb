from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pcb_workflow.py"
SPEC = importlib.util.spec_from_file_location("pcb_workflow", SCRIPT)
assert SPEC and SPEC.loader
workflow = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = workflow
SPEC.loader.exec_module(workflow)


class WorkflowTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        design = root / "Designs" / "Example"
        design.mkdir(parents=True)
        for name in (
            "Example.kicad_pro",
            "Example.kicad_sch",
            "Example.kicad_pcb",
            "README.md",
            "VALIDATION.md",
        ):
            (design / name).write_text(f"fixture {name}\n", encoding="utf-8")
        scripts = root / ".agents" / "skills" / "kicad-konnect" / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "manage_manufacturing_outputs.py").write_text("# fixture\n")
        governance = (
            root / ".agents" / "skills" / "pcb-repository-governance"
            / "scripts"
        )
        governance.mkdir(parents=True)
        (governance / "check_repository_growth.py").write_text("# fixture\n")
        return design

    def test_discovers_design_and_builds_release_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            designs = workflow.discover_designs(root)
            phases = workflow.phase_plan(root, "release-ready", apply=False, designs=designs)
            self.assertEqual([path.name for path in designs], ["Example"])
            self.assertEqual(
                [phase.name for phase in phases],
                ["design-contract", "manufacturing-audit", "diff-check", "repository-growth"],
            )
            self.assertIn("--design", phases[1].command)
            self.assertIn("Example", phases[1].command)

    def test_schematic_goal_builds_route_and_validation_phases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            design = self.make_repo(root)
            (design / "schematic_topology.json").write_text("{}\n", encoding="utf-8")
            phases = workflow.phase_plan(root, "schematic-validate", False, [design])
            self.assertEqual(
                [phase.name for phase in phases],
                [
                    "design-contract",
                    "schematic-route-plan-Example",
                    "schematic-validation-Example",
                ],
            )

    def test_explicit_schematic_goal_rejects_design_without_topology(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            design = self.make_repo(root)
            with self.assertRaisesRegex(ValueError, "requires schematic_topology.json"):
                workflow.topology_designs([design], explicitly_selected=True)

    def test_refresh_requires_explicit_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            design = self.make_repo(root)
            with self.assertRaisesRegex(ValueError, "pass --apply"):
                workflow.execute(root, "manufacturing-refresh", [design], False, False)

    def test_cache_skips_unchanged_success_and_invalidates_on_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            design = self.make_repo(root)
            phase = workflow.Phase("design-contract", cacheable=True)
            first = workflow.fingerprint(root, [design], phase)
            cache_path = root / ".work" / "pcb-workflow" / "cache.json"
            key = workflow.cache_key(phase, [design])
            workflow.write_cache(cache_path, {key: first})
            self.assertEqual(workflow.read_cache(cache_path)[key], first)
            (design / "README.md").write_text("changed\n", encoding="utf-8")
            self.assertNotEqual(first, workflow.fingerprint(root, [design], phase))

    def test_cache_keys_are_isolated_by_design_scope(self) -> None:
        phase = workflow.Phase("manufacturing-audit", cacheable=True)
        alpha = Path("Designs/Alpha")
        beta = Path("Designs/Beta")
        self.assertNotEqual(
            workflow.cache_key(phase, [alpha]),
            workflow.cache_key(phase, [alpha, beta]),
        )

    def test_manufacturing_fingerprint_ignores_unrelated_docs_but_tracks_board(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            design = self.make_repo(root)
            phase = workflow.Phase("manufacturing-audit", cacheable=True)
            first = workflow.fingerprint(root, [design], phase)
            (root / "README.md").write_text("unrelated\n", encoding="utf-8")
            self.assertEqual(first, workflow.fingerprint(root, [design], phase))
            (design / "Example.kicad_pcb").write_text("changed\n", encoding="utf-8")
            self.assertNotEqual(first, workflow.fingerprint(root, [design], phase))

    @mock.patch.object(workflow.subprocess, "run")
    def test_phase_keeps_verbose_output_in_log_and_returns_small_failure(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=["fake"], returncode=1, stdout="x" * 5000, stderr="failure\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / ".work" / "phase.log"
            outcome = workflow.run_phase(workflow.Phase("fake", ("fake",)), root, log)
            self.assertEqual(outcome["status"], "fail")
            self.assertLessEqual(len(outcome["error"]), workflow.MAX_ERROR_CHARS)
            self.assertGreater(len(log.read_text(encoding="utf-8")), 5000)

    @mock.patch.object(workflow.subprocess, "run")
    def test_failure_summary_redacts_repository_and_home_paths(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=["fake"], returncode=1, stdout="", stderr=str(Path.home() / "secret") + "\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outcome = workflow.run_phase(
                workflow.Phase("fake", ("fake",)), root, root / ".work" / "phase.log"
            )
            self.assertNotIn(str(Path.home()), outcome["error"])
            self.assertIn("~/secret", outcome["error"])

    def test_cli_plan_emits_one_compact_json_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "plan", "--root", str(root)],
                capture_output=True,
                text=True,
                check=True,
            )
            lines = result.stdout.splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["status"], "planned")
            self.assertLess(len(result.stdout), 1000)

    def test_cli_can_plan_schematic_goal_without_running_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            design = self.make_repo(root)
            (design / "schematic_topology.json").write_text("{}\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "plan", "--for-goal",
                    "schematic-validate", "--root", str(root),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["goal"], "schematic-validate")
            self.assertIn("schematic-validation-Example", payload["phases"])

    @mock.patch.object(workflow, "run_phase")
    def test_success_result_is_compact_while_details_stay_in_work_dir(self, run: mock.Mock) -> None:
        def successful_phase(phase: object, root: Path, log_path: Path) -> dict[str, object]:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            return {"name": phase.name, "status": "pass", "duration_ms": 5}

        run.side_effect = successful_phase
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            design = self.make_repo(root)
            result = workflow.execute(root, "validate", [design], False, True)
            self.assertEqual(
                result["phases"],
                {"design-contract": "pass", "manufacturing-audit": "pass"},
            )
            self.assertNotIn("log_dir", result)
            summaries = list((root / ".work" / "pcb-workflow" / "runs").glob("*/summary.json"))
            self.assertEqual(len(summaries), 1)


if __name__ == "__main__":
    unittest.main()
