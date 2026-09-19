"""Desktop launch and command mapping without requiring a display server."""
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pcbflow import cli, gui
from pcbflow.presentation import summarize, artifact_label


class GuiTests(unittest.TestCase):
    def test_empty_cli_shows_help_without_opening_desktop(self):
        with mock.patch.object(cli, 'dispatch') as dispatch, mock.patch('sys.stdout'):
            with self.assertRaises(SystemExit) as stopped:
                cli.main([])
        self.assertEqual(stopped.exception.code, 0)
        dispatch.assert_not_called()

    def test_direct_file_launch_enters_runtime_selecting_cli(self):
        with mock.patch.object(sys, 'argv', [gui.__file__]), mock.patch('os.execv', side_effect=RuntimeError('exec intercepted')) as execute:
            with self.assertRaisesRegex(RuntimeError, 'exec intercepted'):
                runpy.run_path(gui.__file__, run_name='__main__')
        command = execute.call_args.args[1]
        self.assertEqual(Path(command[1]), cli.REPOSITORY / 'pcb')
        self.assertEqual(command[2:], ['gui'])

    def test_candidate_pause_only_changes_finish(self):
        self.assertEqual(gui.command_for('Finish design', 'Example', True), ['finish', '--design', 'Example', '--candidate-only'])
        self.assertEqual(gui.command_for('Review board', 'Example', True), ['review', '--design', 'Example'])

    def test_artifact_collection_is_nested_deduplicated_and_existing(self):
        with tempfile.TemporaryDirectory() as temporary:
            board = Path(temporary) / 'board.kicad_pcb'
            board.touch()
            self.assertEqual(gui.collect_paths({'reviews': [{'candidate': str(board)}, {'candidate': str(board)}], 'png': '/missing.png'}), [board])

    def test_review_warns_without_exposing_raw_receipt(self):
        review = {'board': 'board.kicad_pcb', 'drc': {'unconnected': 0, 'severities': {'warning': 8}, 'types': {'lib_footprint_mismatch': 8}}}
        title, summary = summarize(['review'], {'status': 'pass', 'reviews': {'board': review}})
        self.assertEqual(title, 'Completed with warnings')
        self.assertIn('0 errors · 0 unconnected · 8 warnings', summary)
        self.assertIn('Footprints differ from installed library: 8', summary)
        self.assertNotIn('lib_footprint_mismatch', summary)
        self.assertIn('Next step', summary)

    def test_failed_exit_never_shows_completed_even_with_pass_receipt(self):
        title, summary = summarize(['build'], {'status': 'pass', 'failed_phase': 'manufacturing-export'}, code=2)
        self.assertEqual(title, 'Needs attention')
        self.assertIn('Stopped at: Generate production files', summary)
        self.assertNotIn('0 errors', summary)

    def test_candidate_pause_suggests_review_not_finished_production(self):
        title, summary = summarize(['finish', '--candidate-only'], {'status': 'pass'})
        self.assertIn('Inspect the candidate preview', summary)
        self.assertNotIn('final preview', summary)

    def test_cached_checks_and_artifact_names_are_human_readable(self):
        _, summary = summarize(['verify'], {'status': 'pass', 'phases': {'manufacturing-audit': 'cached'}})
        self.assertIn('Check production files: Verified — unchanged', summary)
        self.assertEqual(artifact_label(Path('/tmp/review.png')), 'Board preview — review.png')


if __name__ == '__main__':
    unittest.main()
