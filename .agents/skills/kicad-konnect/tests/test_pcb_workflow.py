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
            workflow.write_cache(cache_path, {phase.name: first})
            self.assertEqual(workflow.read_cache(cache_path)[phase.name], first)
            (design / "README.md").write_text("changed\n", encoding="utf-8")
            self.assertNotEqual(first, workflow.fingerprint(root, [design], phase))

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


if __name__ == "__main__":
    unittest.main()
