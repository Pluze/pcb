from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_copper_pour_variants.py"
SPEC = importlib.util.spec_from_file_location("generate_copper_pour_variants", SCRIPT)
assert SPEC and SPEC.loader
variants = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(variants)


BOARD = """(kicad_pcb
  (footprint "Example"
    (layer "F.Cu")
    (pad "1" smd rect (at 2 2) (size 1 1) (layers "F.Cu") (net "GND"))
  )
  (gr_rect (start 0 0) (end 10 10) (layer "Edge.Cuts"))
)
"""


def defaults(clearance: float = 1.0) -> dict:
    return {
        "default_profile": "u4",
        "profiles": {
            "u4": {
                "copper_pour": {
                    "clearance_mm": clearance,
                    "edge_inset_mm": 1.0,
                    "layer": "F.Cu",
                    "minimum_fill_thickness_mm": 0.25,
                    "net": "GND",
                    "thermal_gap_mm": 0.5,
                    "thermal_spoke_width_mm": 0.5,
                },
                "manufacturing": {
                    "copper_pour_variants": {
                        "default": "no_pour",
                        "enabled_for_production_unless_opted_out": True,
                        "with_pour_suffix": "With_Pour",
                    }
                },
            }
        },
    }


class CopperPourVariantTests(unittest.TestCase):
    def make_design(self, root: Path) -> tuple[Path, Path]:
        design = root / "Example"
        design.mkdir(parents=True)
        (design / "Example.kicad_pcb").write_text(BOARD, encoding="utf-8")
        defaults_path = root / "repository-defaults.json"
        defaults_path.write_text(json.dumps(defaults()), encoding="utf-8")
        return design, defaults_path

    def test_generates_only_with_pour_variant_from_routing_primary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            design, defaults_path = self.make_design(Path(directory))
            policy = variants.load_policy(design, defaults_path)
            expected = variants.expected_variants(design, policy)
            self.assertIsNone(variants.export(expected, force=True))
            with_pour = design / "variants" / "Example_With_Pour.kicad_pcb"
            self.assertEqual(set(expected), {with_pour})
            text = with_pour.read_text(encoding="utf-8")
            self.assertIn("(clearance 1)", text)
            self.assertIn("(xy 1 1)", text)
            self.assertNotIn("(zone", (design / "Example.kicad_pcb").read_text(encoding="utf-8"))
            self.assertEqual(variants.audit(design, expected), [])

    def test_rejects_zone_in_primary_routing_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            design, defaults_path = self.make_design(Path(directory))
            policy = variants.load_policy(design, defaults_path)
            source = design / "Example.kicad_pcb"
            source.write_text(variants.add_zone(BOARD, design.name, policy), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "explicit routing only"):
                variants.expected_variants(design, policy)

    def test_explicit_project_opt_out_skips_variant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            design, defaults_path = self.make_design(Path(directory))
            (design / ".konnect").mkdir()
            (design / ".konnect" / "project.json").write_text(
                json.dumps({"manufacturing": {"copper_pour_variants": {"enabled": False}}}),
                encoding="utf-8",
            )
            self.assertIsNone(variants.load_policy(design, defaults_path))


if __name__ == "__main__":
    unittest.main()
