import sys, tempfile, unittest, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from export_fabricator_gerbers import comparable, layers_for, validate, plot_filename

class FabricatorTests(unittest.TestCase):

    def test_declared_empty_back_and_inner_copper_are_included(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / 'X.kicad_pcb'
            board.write_text('(kicad_pcb (layers (0 "F.Cu" signal) (2 "In1.Cu" signal) (31 "B.Cu" signal)))')
            layers = layers_for(board)
            self.assertEqual(layers[:3], ['F.Cu', 'In1.Cu', 'B.Cu'])
            self.assertIn('B.Mask', layers)

    def test_timestamp_changes_do_not_hide_real_geometry_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'x.gbr'
            p.write_text('%TF.CreationDate,old*%\nX100Y100D03*\n')
            before = comparable(p)
            p.write_text('%TF.CreationDate,new*%\nX100Y100D03*\n')
            self.assertEqual(before, comparable(p))
            p.write_text('%TF.CreationDate,new*%\nX101Y100D03*\n')
            self.assertNotEqual(before, comparable(p))

    def test_job_timestamp_only_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'x.gbrjob'
            p.write_text(json.dumps({'Header': {'CreationDate': 'a'}, 'GeneralSpecs': {'LayerNumber': 2}}))
            a = comparable(p)
            p.write_text(json.dumps({'Header': {'CreationDate': 'b'}, 'GeneralSpecs': {'LayerNumber': 2}}))
            self.assertEqual(a, comparable(p))

    def test_custom_cut_layer_uses_its_native_plot_name(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / 'Panel.kicad_pcb'
            board.write_text('(kicad_pcb (layers (0 "F.Cu" signal) (50 "User.1" user "Coupon.Cuts")))')
            self.assertEqual(plot_filename(board, 'User.1'), 'Panel-Coupon_Cuts.gbr')

    def test_missing_back_layer_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / 'X.kicad_pcb'
            board.write_text('(kicad_pcb (layers (0 "F.Cu" signal) (31 "B.Cu" signal)))')
            output = Path(directory) / 'output'
            output.mkdir()
            with self.assertRaisesRegex(ValueError, 'file set'):
                validate(output, {'board': board}, ['F.Cu', 'B.Cu'])
if __name__ == '__main__':
    unittest.main()
