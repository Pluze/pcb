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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "export"))
    parser.add_argument("--root", type=Path, default=Path("Designs"))
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
    if not designs:
        print(f"ERROR: no PCB designs found under {root}", file=sys.stderr)
        return 1

    failed = False
    for design in designs:
        for exporter in EXPORTERS:
            command = [sys.executable, str(script_dir / exporter), args.mode, str(design)]
            if args.mode == "export" and args.force:
                command.append("--force")
            result = subprocess.run(command)
            failed = failed or result.returncode != 0
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
