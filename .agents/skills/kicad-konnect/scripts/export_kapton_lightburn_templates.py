#!/usr/bin/env python3
"""Audit or export inferred KiCad solder-mask openings as LightBurn-ready DXF."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from manufacturing_discovery import discover_packages
from manufacturing_transaction import replace_directories


SIDE_CONFIG = {
    "front": ("F.Mask", "FrontMask_TopView.dxf"),
    "back": ("B.Mask", "BackMask_BoardCoordinates.dxf"),
}


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
        detail = (result.stderr or result.stdout).strip() or "no diagnostic output"
        raise RuntimeError(f"command failed: {' '.join(command)}\n{detail}")


def dxf_groups(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    if len(lines) % 2:
        raise RuntimeError("DXF contains an incomplete group-code pair")
    groups = []
    for index in range(0, len(lines), 2):
        try:
            code = int(lines[index].strip())
        except ValueError as exc:
            raise RuntimeError(f"invalid DXF group code: {lines[index]!r}") from exc
        groups.append((code, lines[index + 1].strip()))
    return groups


def entity_bounds(text: str) -> tuple[float, float, float, float]:
    groups = dxf_groups(text)
    in_entities = False
    pending_x: dict[int, float] = {}
    points: list[tuple[float, float]] = []
    for code, value in groups:
        if code == 0 and value == "SECTION":
            in_entities = False
            pending_x.clear()
            continue
        if code == 2 and value == "ENTITIES":
            in_entities = True
            continue
        if in_entities and code == 0 and value == "ENDSEC":
            break
        if not in_entities:
            continue
        if 10 <= code <= 18:
            pending_x[code] = float(value)
        elif 20 <= code <= 28:
            x_code = code - 10
            if x_code in pending_x:
                points.append((pending_x.pop(x_code), float(value)))
    if not points:
        raise RuntimeError("DXF ENTITIES section contains no 2D coordinates")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def add_autocad_view(path: Path) -> None:
    """Add extents and a fitted model-space viewport omitted by KiCad's DXF writer."""
    text = path.read_text(encoding="ascii")
    min_x, min_y, max_x, max_y = entity_bounds(text)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        raise RuntimeError(f"{path.name}: invalid entity bounds")
    padding = max(width, height) * 0.05
    view_width = width + 2 * padding
    view_height = max(height + 2 * padding, view_width / 1.6)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    header_end = re.search(
        r"(?m)^\s*0\s*\nENDSEC\s*\n\s*0\s*\nSECTION\s*\n\s*2\s*\nTABLES\s*$",
        text,
    )
    if not header_end:
        raise RuntimeError(f"{path.name}: HEADER/TABLES boundary not found")
    extents = (
        f"  9\n$EXTMIN\n 10\n{min_x - padding:.9f}\n"
        f" 20\n{min_y - padding:.9f}\n 30\n0.0\n"
        f"  9\n$EXTMAX\n 10\n{max_x + padding:.9f}\n"
        f" 20\n{max_y + padding:.9f}\n 30\n0.0\n"
        f"  9\n$LIMMIN\n 10\n{min_x - padding:.9f}\n"
        f" 20\n{min_y - padding:.9f}\n"
        f"  9\n$LIMMAX\n 10\n{max_x + padding:.9f}\n"
        f" 20\n{max_y + padding:.9f}\n"
    )
    text = text[: header_end.start()] + extents + text[header_end.start() :]

    tables_start = re.search(
        r"(?m)^\s*0\s*\nSECTION\s*\n\s*2\s*\nTABLES\s*$", text
    )
    if not tables_start:
        raise RuntimeError(f"{path.name}: TABLES section not found")
    used_handles = {
        value.upper() for code, value in dxf_groups(text) if code in (5, 105)
    }
    empty_vport = re.search(
        r"(?ms)^\s*0\s*\nTABLE\s*\n\s*2\s*\nVPORT\s*\n(?P<body>.*?)"
        r"^\s*0\s*\nENDTAB\s*$",
        text,
    )
    if empty_vport and re.search(r"(?m)^\s*0\s*\nVPORT\s*$", empty_vport.group("body")):
        raise RuntimeError(f"{path.name}: VPORT table is not empty")
    table_handle_match = (
        re.search(r"(?m)^\s*5\s*\n([0-9A-Fa-f]+)\s*$", empty_vport.group("body"))
        if empty_vport else None
    )
    table_handle = int(table_handle_match.group(1), 16) if table_handle_match else 0xF0000000
    while not empty_vport and f"{table_handle:X}" in used_handles:
        table_handle += 1
    record_handle = 0xF0000000
    while f"{record_handle:X}" in used_handles:
        record_handle += 1
    viewport = (
        "  0\nTABLE\n  2\nVPORT\n"
        f"  5\n{table_handle:X}\n330\n0\n100\nAcDbSymbolTable\n 70\n1\n"
        "  0\nVPORT\n"
        f"  5\n{record_handle:X}\n330\n{table_handle:X}\n"
        "100\nAcDbSymbolTableRecord\n100\nAcDbViewportTableRecord\n"
        "  2\n*Active\n 70\n0\n"
        " 10\n0.0\n 20\n0.0\n 11\n1.0\n 21\n1.0\n"
        f" 12\n{center_x:.9f}\n 22\n{center_y:.9f}\n"
        " 13\n0.0\n 23\n0.0\n 14\n0.5\n 24\n0.5\n"
        " 15\n0.5\n 25\n0.5\n 16\n0.0\n 26\n0.0\n 36\n1.0\n"
        " 17\n0.0\n 27\n0.0\n 37\n0.0\n"
        f" 40\n{view_height:.9f}\n 41\n1.6\n"
        " 42\n50.0\n 43\n0.0\n 44\n0.0\n 50\n0.0\n 51\n0.0\n"
        " 71\n0\n 72\n1000\n 73\n1\n 74\n3\n 75\n0\n 76\n0\n"
        " 77\n0\n 78\n0\n281\n0\n 65\n0\n146\n0.0\n  0\nENDTAB"
    )
    if empty_vport:
        text = text[: empty_vport.start()] + viewport + text[empty_vport.end() :]
    else:
        insertion = tables_start.end()
        text = text[:insertion] + "\n" + viewport + text[insertion:]
    path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="ascii")


def validate_dxf(path: Path, mask_layer: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"missing or empty DXF: {path}")
    text = path.read_text(encoding="ascii")
    if not re.search(r"\$INSUNITS\s+70\s+4(?:\s|$)", text):
        raise RuntimeError(f"{path.name}: DXF units are not millimetres")
    for layer in (mask_layer, "Edge.Cuts"):
        if layer not in text:
            raise RuntimeError(f"{path.name}: missing layer {layer}")
    if not any(entity in text for entity in ("LWPOLYLINE", "CIRCLE", "ARC", "LINE", "SPLINE")):
        raise RuntimeError(f"{path.name}: no vector entities found")
    for marker in ("$EXTMIN", "$EXTMAX", "$LIMMIN", "$LIMMAX", "*Active"):
        if marker not in text:
            raise RuntimeError(f"{path.name}: missing AutoCAD view metadata {marker}")


def build(cli: Path, package: dict, root: Path) -> Path:
    staging = root / package["name"]
    staging.mkdir()
    for side in package["sides"]:
        mask_layer, filename = SIDE_CONFIG[side]
        output = staging / filename
        command = [
            str(cli), "pcb", "export", "dxf", "--output", str(output),
            "--layers", f"{mask_layer},Edge.Cuts", "--mode-single",
            "--output-units", "mm", "--use-contours", "--drill-shape-opt", "0",
            "--check-zones",
        ]
        # KiCad 10's DXF exporter has no mirror switch. Keep back geometry in
        # board coordinates; fixture/tape transfer orientation determines
        # whether the operator must flip it horizontally in LightBurn.
        command.append(str(package["board"]))
        run(command)
        add_autocad_view(output)
        validate_dxf(output, mask_layer)
    return staging


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
        if (existing / name).read_bytes() != (generated / name).read_bytes()
    ]


def stale_directories(packages: list[dict]) -> list[Path]:
    expected = {item["output"].resolve() for item in packages}
    roots = {item["output"].parent.resolve() for item in packages}
    return sorted(
        child for root in roots if root.is_dir() for child in root.iterdir()
        if child.is_dir() and child.resolve() not in expected
    )


def replace(packages: list[dict], generated: dict[str, Path], force: bool, clean_stale: bool) -> Path | None:
    stale = stale_directories(packages) if clean_stale else []
    return replace_directories(
        packages, generated, force=force, stale=stale, kind="kapton-lightburn",
    )


def main() -> int:
    args = parse_args()
    try:
        packages = discover_packages(args.design, "lightburn", args.selected)
        cli = find_cli(args.kicad_cli)
        with tempfile.TemporaryDirectory(prefix="kapton-lightburn-export-") as temp:
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
