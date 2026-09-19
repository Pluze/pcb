from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_circuitpro_u4_package.py"
SPEC = importlib.util.spec_from_file_location("validate_circuitpro_u4_package", SCRIPT)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class CircuitProStructureTests(unittest.TestCase):
    def test_complete_minimal_gerber_passes_structure(self) -> None:
        content = "%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,1.0*%\nD10*\nX0Y0D03*\nM02*\n"
        errors: list[str] = []
        validator.validate_gerber_structure("TopLayer.gtl", content, errors)
        self.assertEqual(errors, [])

    def test_truncated_gerber_is_rejected(self) -> None:
        content = "%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,1.0*%\nD10*\nX0Y0D03*\n"
        errors: list[str] = []
        validator.validate_gerber_structure("TopLayer.gtl", content, errors)
        self.assertIn("Gerber end-of-file marker is missing in TopLayer.gtl", errors)

    def test_complete_minimal_excellon_passes_structure(self) -> None:
        content = "M48\nMETRIC\nT1C1.0\n%\nT1\nX1.0Y2.0\nM30\n"
        errors: list[str] = []
        validator.validate_drill_structure("DrillPlated.drl", content, errors)
        self.assertEqual(errors, [])

    def test_truncated_excellon_is_rejected(self) -> None:
        content = "M48\nMETRIC\nT1C1.0\n%\nT1\nX1.0Y2.0\n"
        errors: list[str] = []
        validator.validate_drill_structure("DrillPlated.drl", content, errors)
        self.assertIn("Excellon end-of-file marker is missing in DrillPlated.drl", errors)


if __name__ == "__main__":
    unittest.main()
