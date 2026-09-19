"""Acceptance tests for net equivalence and saved-design audit coverage."""
import copy
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_design import compare, pcb_components, schematic_components, check, find_kicad_cli
from manufacturing_discovery import extract_blocks


def part(pads):
    return {'value': '1k', 'footprint': 'R:0805', 'pads': pads}


class DesignCheckTests(unittest.TestCase):
    def test_equivalent_nets_with_different_names_pass(self):
        a = {'R1': part({'1': 'VBAT', '2': 'GND'}), 'R2': part({'1': 'VBAT', '2': 'GND'})}
        b = {'R1': part({'1': 'auto1', '2': 'auto2'}), 'R2': part({'1': 'auto1', '2': 'auto2'})}
        self.assertEqual(compare(a, b), [])

    def test_rewired_pin_is_rejected(self):
        a = {'R1': part({'1': 'A', '2': 'B'}), 'R2': part({'1': 'A', '2': 'B'})}
        b = copy.deepcopy(a)
        b['R2']['pads']['1'] = 'B'
        self.assertIn('connectivity_mismatch', {f['type'] for f in compare(a, b)})

    def test_stale_value_missing_footprint_and_extra_connected_pad(self):
        a = {'R1': part({'1': 'A'})}
        b = {'R1': part({'1': 'A', '3': 'A'})}
        b['R1']['value'] = '2k'
        self.assertEqual({f['type'] for f in compare(a, b)}, {'value_mismatch', 'connectivity_mismatch', 'extra_connected_pad'})
        self.assertEqual(compare(a, {})[0]['type'], 'component_mismatch')

    def test_unnamed_pads_are_independent(self):
        a = {'R1': part({'1': 'unconnected-R1', '2': 'unconnected-R2'})}
        b = {'R1': part({'1': '', '2': ''})}
        self.assertEqual(compare(a, b), [])

    def test_repeated_native_pad_number_must_have_same_net(self):
        block = '(footprint "R:0805" (property "Reference" "R1") (pad "1" smd (net "A")) (pad "1" smd (net "B")))'
        with self.assertRaisesRegex(ValueError, 'conflicting nets'):
            pcb_components(block)

    def test_excluded_board_symbols_are_omitted_and_dnp_retains_connectivity(self):
        root = ET.fromstring('<export><components><comp ref="R1"><property name="dnp"/></comp><comp ref="X1"><property name="exclude_from_board"/></comp></components></export>')
        components = schematic_components(root)
        self.assertEqual(set(components), {'R1'})
        self.assertTrue(components['R1']['dnp'])

    @unittest.skipUnless(os.environ.get('PCB_REVIEW_REAL') == '1', 'real KiCad opt-in')
    def test_real_schematic_value_change_is_caught_despite_clean_erc(self):
        repo = Path(__file__).resolve().parents[4]
        source = repo / 'Designs/LM555_LED_Flasher'
        with tempfile.TemporaryDirectory(prefix='pcb-parity-test-') as directory:
            root = Path(directory)
            design = root / source.name
            design.mkdir()
            for suffix in ('.kicad_pcb', '.kicad_sch', '.kicad_pro'):
                shutil.copy2(source / (source.name + suffix), design)
            schematic = design / (source.name + '.kicad_sch')
            text = schematic.read_text()
            target = next(b for b in extract_blocks(text, 'symbol') if '(property "Reference" "R1"' in b)
            schematic.write_text(text.replace(target, target.replace('(property "Value" "1k"', '(property "Value" "2k"'), 1))
            output = root / 'results'
            output.mkdir()
            result = check(design, output, find_kicad_cli(None))
            self.assertEqual(result['erc']['errors'], 0)
            self.assertEqual(result['status'], 'fail')
            self.assertGreater(result['parity']['findings'], 0)
            self.assertTrue(result['source_unchanged'])


if __name__ == '__main__':
    unittest.main()
