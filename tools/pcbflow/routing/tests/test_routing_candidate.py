import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from freerouting_candidate import constrain_dsn, strip_routing, geometry_signature
from routing_finish import finish
from routing_metrics import metrics

def segment(start, end, net='GND', width=0.25):
    return f'(segment (start {start[0]} {start[1]}) (end {end[0]} {end[1]}) (width {width}) (layer "F.Cu") (net "{net}") (uuid "x"))'

class RoutingContractTests(unittest.TestCase):

    def test_settings_follow_layers_and_raise_only_smd_exception(self):
        dsn = '(pcb x (resolution um 10) (structure (layer F.Cu (type signal)) (layer B.Cu (type signal)) (rule (clearance 50 (type smd_smd)))))'
        result = constrain_dsn(dsn, 0.2)
        self.assertLess(result.index('(layer B.Cu'), result.index('(autoroute_settings'))
        self.assertIn('(clearance 200 (type smd_smd))', result)
        self.assertIn('(vias off)', result)
        self.assertIn('(layer_rule B.Cu (active off)', result)

    def test_reject_unsupported_units(self):
        with self.assertRaises(ValueError):
            constrain_dsn('(structure (layer F.Cu) (layer B.Cu))', 0.2)

    def test_strip_routing_retains_footprints_and_outline(self):
        source = '(kicad_pcb (footprint "x" (at 1 2)) (gr_line (start 0 0) (end 1 1)) ' + segment((0, 0), (1, 0)) + ')'
        result = strip_routing(source)
        self.assertEqual(geometry_signature(source), geometry_signature(result))
        self.assertNotIn('(segment', result)

    def measure(self, text):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'x.kicad_pcb'
            p.write_text(text)
            return metrics(p)

    def test_bevel_right_angle_and_enforce_width(self):
        source = '(kicad_pcb ' + segment((0, 0), (1, 0), width=0.18) + segment((1, 0), (1, 1)) + ')'
        (result, changes) = finish(source)
        self.assertEqual(changes, {'widened_segments': 1, 'beveled_degree_two_corners': 1})
        measured = self.measure(result)
        self.assertEqual(measured['degree_two_right_angles'], 0)
        self.assertEqual(measured['non_45_segments'], 0)
        self.assertEqual(measured['segments'], 3)
        self.assertEqual(measured['nets']['GND']['widths_mm'], [0.25])

    def test_preserve_t_junction_and_different_nets(self):
        source = '(kicad_pcb ' + ''.join((segment((0, 0), p) for p in [(1, 0), (0, 1), (-1, 0)])) + ')'
        (_, changes) = finish(source)
        self.assertEqual(changes['beveled_degree_two_corners'], 0)
        source = '(kicad_pcb ' + segment((0, 0), (1, 0)) + segment((1, 0), (1, 1), 'VCC') + ')'
        (_, changes) = finish(source)
        self.assertEqual(changes['beveled_degree_two_corners'], 0)

    def test_existing_45_degree_bend_is_unchanged(self):
        source = '(kicad_pcb ' + segment((0, 0), (1, 0)) + segment((1, 0), (2, 1)) + ')'
        (_, changes) = finish(source)
        self.assertEqual(changes['beveled_degree_two_corners'], 0)
if __name__ == '__main__':
    unittest.main()
