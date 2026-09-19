"""Public CLI boundaries: selection, planning, delegation and stale adoption rejection."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
SPEC = importlib.util.spec_from_file_location('pcb_cli', Path(__file__).resolve().parents[1] / 'cli.py')
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)

class PublicCliTests(unittest.TestCase):

    def test_advanced_help_delegates_without_an_extra_protocol(self):
        args = cli.parser().parse_args(['tool', 'export-gerber', '--help'])
        with mock.patch.object(cli, 'invoke', return_value=({}, 0)) as invoke:
            cli.dispatch(args)
        self.assertEqual(invoke.call_args.args[0][-1], '--help')
        self.assertTrue(invoke.call_args.args[0][1].endswith('export_fabricator_gerbers.py'))

    def test_build_dry_run_never_runs_a_mutating_goal(self):
        args = cli.parser().parse_args(['build', '--dry-run', '--design', 'Example'])
        with mock.patch.object(cli, 'invoke', return_value=({}, 0)) as invoke:
            cli.dispatch(args)
        command = invoke.call_args.args[0]
        self.assertIn('plan', command)
        self.assertIn('--for-goal', command)
        self.assertIn('manufacturing-refresh', command)

    def test_finish_planning_is_read_only_and_orders_clear_before_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            d = root / 'Designs/X'
            d.mkdir(parents=True)
            (d / 'X.kicad_pcb').write_text('board')
            args = cli.parser().parse_args(['--root', str(root), 'finish', '--design', 'X', '--dry-run'])
            with mock.patch.object(cli.subprocess, 'run') as run:
                (receipt, code) = cli.dispatch(args)
            run.assert_not_called()
            self.assertEqual(code, 0)
            self.assertLess(receipt['phases'].index('clean-route-and-review'), receipt['phases'].index('build-u4-mask-gerber'))

    def test_design_name_cannot_escape_repository(self):
        with self.assertRaises(ValueError):
            cli.design_board(Path('/tmp'), '../elsewhere')

    def test_explicit_missing_runtime_does_not_fallback(self):
        with self.assertRaises(ValueError):
            cli.find_runtime('/missing/runtime', 'PCB_TEST', ['/bin/sh'])

    def test_metrics_receipt_has_status_and_human_display_accepts_nested_candidate(self):
        with mock.patch.object(cli.subprocess, 'run', return_value=argparse.Namespace(returncode=0, stdout='{"candidate":{"segments":2}}', stderr='')):
            (receipt, code) = cli.invoke(['metrics'], Path.cwd())
        self.assertEqual(receipt['status'], 'pass')
        with mock.patch('builtins.print'):
            cli.display(receipt, False)

    def test_finish_stops_before_routing_when_design_check_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            design = root / 'Designs/X'
            design.mkdir(parents=True)
            (design / 'X.kicad_pcb').touch()
            args = cli.parser().parse_args(['--root', str(root), 'finish', '--design', 'X'])
            with mock.patch.object(cli, 'dispatch', return_value=({'status': 'fail'}, 2)) as dispatch:
                result, code = cli.finish_design(args, root)
            self.assertEqual(dispatch.call_count, 1)
            self.assertEqual(dispatch.call_args.args[0].command, 'check')
            self.assertEqual(result['failed_phase'], 'design-check')
            self.assertEqual(code, 2)

    def test_every_catalog_engine_exists(self):
        for name in cli.ENGINES:
            self.assertTrue(cli.engine(name).is_file(), name)

    def test_adoption_rejects_stale_source_before_running_kicad(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            d = root / 'Designs/X'
            d.mkdir(parents=True)
            (d / 'X.kicad_pcb').write_text('changed')
            receipt = root / 'receipt.json'
            receipt.write_text(json.dumps({'candidate': str(root / 'candidate.kicad_pcb'), 'inputs': {'X.kicad_pcb': 'old-hash'}}))
            with self.assertRaisesRegex(ValueError, 'source changed'):
                cli.adopt_candidate(root, 'X', receipt)
if __name__ == '__main__':
    unittest.main()
