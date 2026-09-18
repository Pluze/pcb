#!/usr/bin/env python3
"""Discover PCB designs and audit or export all inferred manufacturing outputs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


EXPORTERS = (
    "export_circuitpro_u4_packages.py",
    "export_kapton_lightburn_templates.py",
)
VARIANT_GENERATOR = "generate_copper_pour_variants.py"


def cleanup_variant_personal_state(design: Path) -> None:
    """Remove KiCad per-user state created while validating generated variants."""
    for path in (design / "variants").glob("*.kicad_prl"):
        path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "export"))
    parser.add_argument("--root", type=Path, default=Path("Designs"))
    parser.add_argument("--design", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    script_dir = Path(__file__).resolve().parent
    designs = [
        path for path in sorted(root.iterdir())
        if path.is_dir() and (path / f"{path.name}.kicad_pcb").is_file()
    ]
    if args.design:
        wanted = set(args.design)
        designs = [path for path in designs if path.name in wanted]
        missing = wanted - {path.name for path in designs}
        if missing:
            print(f"ERROR: unknown design(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 1
    if not designs:
        print(f"ERROR: no PCB designs found under {root}", file=sys.stderr)
        return 1

    for design in designs:
        try:
            variant_command = [
                sys.executable, str(script_dir / VARIANT_GENERATOR), args.mode, str(design),
            ]
            if args.mode == "export" and args.force:
                variant_command.append("--force")
            result = subprocess.run(variant_command)
            if result.returncode:
                return result.returncode
            for exporter in EXPORTERS:
                command = [sys.executable, str(script_dir / exporter), args.mode, str(design)]
                if args.mode == "export" and args.force:
                    command.append("--force")
                result = subprocess.run(command)
                if result.returncode:
                    return result.returncode
        finally:
            cleanup_variant_personal_state(design)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
