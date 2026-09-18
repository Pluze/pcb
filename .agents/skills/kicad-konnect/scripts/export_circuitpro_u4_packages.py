#!/usr/bin/env python3
"""Audit or export CircuitPro RP 1.x U4 packages inferred from KiCad PCBs."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from manufacturing_discovery import discover_packages


FIXED_LAYER_TARGETS = {
    "F.Cu": "TopLayer.gtl",
    "B.Cu": "BottomLayer.gbl",
    "Edge.Cuts": "BoardOutline.gm1",
}
DRILL_COORDINATE = re.compile(r"^X[-+]?\d+(?:\.\d+)?Y[-+]?\d+(?:\.\d+)?")
TIMESTAMP = re.compile(
    r"^(?:G04 #@! TF\.CreationDate,|G04 Created by KiCad .* date |"
    r"; DRILL file KiCad .* date |; #@! TF\.CreationDate,)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "export"))
    parser.add_argument("design", type=Path)
    parser.add_argument("--package", action="append", dest="selected")
    parser.add_argument("--kicad-cli", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def find_cli(explicit: Path | None) -> Path:
    candidates = [explicit] if explicit else []
    found = shutil.which("kicad-cli")
    if found:
        candidates.append(Path(found))
    candidates.append(Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"))
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise ValueError("kicad-cli not found; pass --kicad-cli PATH")


def run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"command failed: {' '.join(command)}\n{detail}")


def count_drills(path: Path) -> int:
    return sum(
        bool(DRILL_COORDINATE.match(line.strip()))
        for line in path.read_text(encoding="ascii").splitlines()
    )


def validate(cli_python: str, package: dict, directory: Path) -> None:
    validator = Path(__file__).with_name("validate_circuitpro_u4_package.py")
    command = [
        cli_python, str(validator), str(directory),
        "--expected-cut-contours", str(package["cut_count"]),
        "--expected-plated-drills", str(package["plated_drills"]),
        "--expected-unplated-drills", str(package["unplated_drills"]),
    ]
    for name in sorted(package["expected_files"]):
        command.extend(("--required-file", name))
    run(command)


def build(cli: Path, package: dict, root: Path) -> Path:
    staging = root / package["name"]
    staging.mkdir()
    drc_report = root / f"{package['name']}-drc.json"
    run([
        str(cli), "pcb", "drc", "--output", str(drc_report), "--format", "json",
        "--severity-error", "--exit-code-violations", str(package["board"]),
    ])
    for index, layer in enumerate(package["layers"]):
        raw = root / f"{package['name']}-layer-{index}"
        raw.mkdir()
        run([
            str(cli), "pcb", "export", "gerbers", "--output", str(raw),
            "--layers", layer, "--no-x2", "--no-netlist", "--check-zones",
            str(package["board"]),
        ])
        artwork = [
            path for path in raw.iterdir()
            if path.is_file() and path.suffix.lower() != ".gbrjob"
        ]
        if len(artwork) != 1:
            raise RuntimeError(f"{package['name']}: {layer} produced {len(artwork)} files")
        target = "CutInside.gm2" if layer == package["coupon_layer"] else FIXED_LAYER_TARGETS[layer]
        shutil.copy2(artwork[0], staging / target)

    raw_drill = root / f"{package['name']}-drill"
    raw_drill.mkdir()
    run([
        str(cli), "pcb", "export", "drill", "--output", str(raw_drill),
        "--format", "excellon", "--drill-origin", "absolute",
        "--excellon-zeros-format", "decimal", "--excellon-oval-format", "route",
        "--excellon-units", "mm", "--excellon-separate-th", str(package["board"]),
    ])
    for pattern, target in (("*-PTH.drl", "DrillPlated.drl"), ("*-NPTH.drl", "DrillUnplated.drl")):
        matches = list(raw_drill.glob(pattern))
        if len(matches) != 1:
            raise RuntimeError(f"{package['name']}: expected one {pattern} file")
        if count_drills(matches[0]):
            shutil.copy2(matches[0], staging / target)
    validate(sys.executable, package, staging)
    return staging


def normalized(path: Path) -> list[str]:
    return [
        line for line in path.read_text(encoding="ascii").splitlines()
        if not TIMESTAMP.match(line)
    ]


def compare(existing: Path, generated: Path) -> list[str]:
    if not existing.is_dir():
        return ["output directory is missing"]
    old = {path.name for path in existing.iterdir() if path.is_file()}
    new = {path.name for path in generated.iterdir() if path.is_file()}
    if old != new:
        return [f"file set differs: existing={sorted(old)} generated={sorted(new)}"]
    return [
        f"content differs from current board export: {name}"
        for name in sorted(old)
        if normalized(existing / name) != normalized(generated / name)
    ]


def stale_directories(packages: list[dict]) -> list[Path]:
    expected = {item["output"].resolve() for item in packages}
    roots = {item["output"].parent.resolve() for item in packages}
    return sorted(
        child for root in roots if root.is_dir() for child in root.iterdir()
        if child.is_dir() and child.resolve() not in expected
    )


def replace(packages: list[dict], generated: dict[str, Path], force: bool, clean_stale: bool) -> Path | None:
    existing_paths = [item["output"] for item in packages if item["output"].exists()]
    stale = stale_directories(packages) if clean_stale else []
    affected = existing_paths + stale
    if affected and not force:
        raise ValueError("output exists; rerun export with --force after reviewing the audit")
    backup = None
    if affected:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = Path(tempfile.mkdtemp(prefix=f"circuitpro-u4-backup-{stamp}-"))
        for path in affected:
            shutil.copytree(path, backup / path.name)
    for path in stale:
        shutil.rmtree(path)
    for item in packages:
        output = item["output"]
        replacement = output.parent / f".{item['name']}.u4-new"
        output.parent.mkdir(parents=True, exist_ok=True)
        if replacement.exists():
            shutil.rmtree(replacement)
        shutil.copytree(generated[item["name"]], replacement)
        if output.exists():
            shutil.rmtree(output)
        replacement.rename(output)
    return backup


def main() -> int:
    args = parse_args()
    try:
        packages = discover_packages(args.design, "u4", args.selected)
        cli = find_cli(args.kicad_cli)
        with tempfile.TemporaryDirectory(prefix="circuitpro-u4-export-") as temp:
            root = Path(temp)
            generated = {item["name"]: build(cli, item, root) for item in packages}
            if args.mode == "audit":
                failed = False
                for item in packages:
                    problems = compare(item["output"], generated[item["name"]])
                    if problems:
                        failed = True
                        for problem in problems:
                            print(f"ERROR [{item['name']}]: {problem}", file=sys.stderr)
                    else:
                        print(f"PASS [{item['name']}]: structure and source freshness")
                if not args.selected:
                    for path in stale_directories(packages):
                        failed = True
                        print(f"ERROR: stale output directory: {path}", file=sys.stderr)
                return int(failed)
            backup = replace(packages, generated, args.force, not args.selected)
            for item in packages:
                print(f"EXPORTED [{item['name']}]: {item['output']}")
            if backup:
                print(f"BACKUP: {backup}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
