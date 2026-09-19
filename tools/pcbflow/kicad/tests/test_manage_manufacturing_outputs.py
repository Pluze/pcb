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
sys.path.insert(0, str(SCRIPT.parent))
from manufacturing_discovery import stage_package_board, drc_failure_detail

manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)


class ManufacturingManagerTests(unittest.TestCase):
    def test_drc_error_survives_temporary_report_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'drc.json'
            report.write_text('{"violations":[{"type":"starved_thermal","description":"one spoke","items":[{"description":"U1 pad 1"}]}],"unconnected_items":[]}')
            detail = drc_failure_detail(['kicad-cli', 'pcb', 'drc', '--output', str(report)])
        self.assertIn('starved_thermal', detail)
        self.assertIn('U1 pad 1', detail)


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
        self.assertEqual(run.call_count, len(manager.EXPORTERS) + 1)
        for call in run.call_args_list:
            command = call.args[0]
            self.assertEqual(Path(command[3]).name, "Beta")
        self.assertEqual(
            Path(run.call_args_list[0].args[0][1]).name,
            manager.VARIANT_GENERATOR,
        )

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


    def test_third_format_failure_keeps_every_published_format(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.make_design(root,'Example');design=root/'Example'
            for kind in ['u4','lightburn','gerber']:
                folder=design/'fabrication'/kind;folder.mkdir(parents=True);(folder/'old').write_text(kind)
            def child(command):
                if Path(command[1]).name == 'export_fabricator_gerbers.py':
                    return subprocess.CompletedProcess(command,7)
                return subprocess.CompletedProcess(command,0)
            with mock.patch.object(manager.subprocess,'run',side_effect=child), mock.patch.object(sys,'argv',[str(SCRIPT),'export','--root',str(root),'--force']):
                self.assertEqual(manager.main(),7)
            for kind in ['u4','lightburn','gerber']:
                self.assertEqual((design/'fabrication'/kind/'old').read_text(),kind)

    def test_success_installs_all_three_formats_together(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.make_design(root,'Example');design=root/'Example'
            def child(command):
                kind={'export_circuitpro_u4_packages.py':'u4','export_kapton_lightburn_templates.py':'lightburn','export_fabricator_gerbers.py':'gerber'}.get(Path(command[1]).name)
                if kind:
                    folder=Path(command[3])/'fabrication'/kind;folder.mkdir(parents=True);(folder/'ready').write_text(kind)
                return subprocess.CompletedProcess(command,0)
            with mock.patch.object(manager.subprocess,'run',side_effect=child), mock.patch.object(sys,'argv',[str(SCRIPT),'export','--root',str(root),'--force']):
                self.assertEqual(manager.main(),0)
            for kind in ['u4','lightburn','gerber']:
                self.assertEqual((design/'fabrication'/kind/'ready').read_text(),kind)

    def test_export_snapshot_retains_project_and_custom_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board = root / "variant.kicad_pcb"
            project = root / "parent.kicad_pro"
            rules = root / "parent.kicad_dru"
            for path in (board, project, rules):
                path.write_text(path.name)
            destination = root / "export.kicad_pcb"
            stage_package_board({"board": board, "project": project}, destination)
            self.assertEqual(destination.read_text(), board.read_text())
            self.assertEqual(destination.with_suffix(".kicad_pro").read_text(), project.read_text())
            self.assertEqual(destination.with_suffix(".kicad_dru").read_text(), rules.read_text())

    def test_export_refuses_missing_project_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board = root / "variant.kicad_pcb"
            board.write_text("board")
            destination = root / "export.kicad_pcb"
            with self.assertRaisesRegex(ValueError, "missing manufacturing project"):
                stage_package_board({"board": board, "project": root / "missing.kicad_pro"}, destination)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
