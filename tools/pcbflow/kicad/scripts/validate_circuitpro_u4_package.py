#!/usr/bin/env python3
"""Validate a CircuitPro RP 1.x / ProtoLaser U4 import directory."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ALL_MACHINE_FILES = {
    "TopLayer.gtl", "BottomLayer.gbl", "BoardOutline.gm1", "CutInside.gm2",
    "DrillPlated.drl", "DrillUnplated.drl",
}
GERBER_SUFFIXES = {".gtl", ".gbl", ".gm1", ".gm2"}
DRILL_COORDINATE = re.compile(r"^X[-+]?\d+(?:\.\d+)?Y[-+]?\d+(?:\.\d+)?(?:G85.*)?$")
GERBER_DRAW = re.compile(
    r"^(?:G0[123])?(?:X(?P<x>-?\d+))?(?:Y(?P<y>-?\d+))?"
    r"(?:I-?\d+)?(?:J-?\d+)?D0?(?P<op>[12])\*$"
)
GERBER_FORMAT = re.compile(r"^%FS.*\*%$", re.MULTILINE)
GERBER_UNITS = re.compile(r"^%MO(?:MM|IN)\*%$", re.MULTILINE)
GERBER_APERTURE = re.compile(r"^%ADD\d+", re.MULTILINE)
DRILL_UNITS = re.compile(r"^(?:METRIC|INCH)(?:,.*)?$", re.MULTILINE)
DRILL_TOOL = re.compile(r"^T\d+C", re.MULTILINE)


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="machine-input directory to validate")
    parser.add_argument("--required-file", action="append", default=[])
    parser.add_argument("--expected-cut-contours", type=nonnegative_int, default=0)
    parser.add_argument("--expected-plated-drills", type=nonnegative_int, default=0)
    parser.add_argument("--expected-unplated-drills", type=nonnegative_int, default=0)
    return parser.parse_args()


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def read_text(path: Path, errors: list[str]) -> str:
    if not path.is_file():
        fail(errors, f"missing required file: {path.name}")
        return ""
    if path.stat().st_size == 0:
        fail(errors, f"empty machine input: {path.name}")
        return ""
    try:
        return path.read_text(encoding="ascii")
    except UnicodeDecodeError:
        fail(errors, f"machine input is not ASCII text: {path.name}")
        return ""


def contour_components(content: str) -> tuple[int, int]:
    """Count connected contour components and components with open endpoints."""
    current_x = 0
    current_y = 0
    edges: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for raw_line in content.splitlines():
        match = GERBER_DRAW.match(raw_line.strip())
        if not match:
            continue
        next_x = int(match.group("x")) if match.group("x") is not None else current_x
        next_y = int(match.group("y")) if match.group("y") is not None else current_y
        next_point = (next_x, next_y)
        if match.group("op") == "1" and next_point != (current_x, current_y):
            edges.append(((current_x, current_y), next_point))
        current_x, current_y = next_point

    adjacency: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for start, end in edges:
        adjacency.setdefault(start, []).append(end)
        adjacency.setdefault(end, []).append(start)
    components = 0
    open_components = 0
    unseen = set(adjacency)
    while unseen:
        components += 1
        stack = [unseen.pop()]
        nodes = []
        while stack:
            node = stack.pop()
            nodes.append(node)
            for neighbor in adjacency[node]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        if any(len(adjacency[node]) % 2 for node in nodes):
            open_components += 1
    return components, open_components


def validate_gerber_structure(name: str, content: str, errors: list[str]) -> None:
    if not GERBER_FORMAT.search(content):
        fail(errors, f"Gerber coordinate format is missing in {name}")
    if not GERBER_UNITS.search(content):
        fail(errors, f"Gerber units are missing in {name}")
    if not GERBER_APERTURE.search(content):
        fail(errors, f"Gerber aperture table is missing in {name}")
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines or lines[-1] != "M02*":
        fail(errors, f"Gerber end-of-file marker is missing in {name}")


def validate_drill_structure(name: str, content: str, errors: list[str]) -> None:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines or lines[0] != "M48":
        fail(errors, f"Excellon header is missing in {name}")
    if not DRILL_UNITS.search(content):
        fail(errors, f"Excellon units are missing in {name}")
    if "%" not in lines:
        fail(errors, f"Excellon header terminator is missing in {name}")
    if any(DRILL_COORDINATE.match(line) for line in lines) and not DRILL_TOOL.search(content):
        fail(errors, f"Excellon tool table is missing in {name}")
    if not lines or lines[-1] != "M30":
        fail(errors, f"Excellon end-of-file marker is missing in {name}")


def main() -> int:
    args = parse_args()
    directory = args.directory.resolve()
    errors: list[str] = []

    if not directory.is_dir():
        print(f"ERROR: not a directory: {directory}", file=sys.stderr)
        return 2

    required = set(args.required_file)
    if not required or required - ALL_MACHINE_FILES:
        fail(errors, "required-file set is empty or contains an unsupported filename")
    files = {path.name for path in directory.iterdir() if path.is_file()}
    for missing in sorted(required - files):
        fail(errors, f"missing required file: {missing}")
    for unexpected in sorted(files - required):
        fail(errors, f"unexpected file in machine-input directory: {unexpected}")

    contents: dict[str, str] = {}
    for name in sorted(files & ALL_MACHINE_FILES):
        contents[name] = read_text(directory / name, errors)

    for name, content in contents.items():
        suffix = Path(name).suffix.lower()
        if suffix in GERBER_SUFFIXES:
            validate_gerber_structure(name, content, errors)
            if re.search(r"\bTO[.,]", content):
                fail(errors, f"X2 object/net attribute found in {name}")
        elif suffix == ".drl":
            validate_drill_structure(name, content, errors)

    board_outline = contents.get("BoardOutline.gm1", "")
    outline_count, outline_open = contour_components(board_outline)
    if board_outline and outline_count != 1:
        fail(errors, f"BoardOutline.gm1 must contain exactly one contour; found {outline_count}")
    if outline_open:
        fail(errors, f"BoardOutline.gm1 contains {outline_open} open contour component(s)")

    cut_inside = contents.get("CutInside.gm2")
    cut_count, cut_open = contour_components(cut_inside or "")
    if cut_inside is not None and cut_count < 1:
        fail(errors, "CutInside.gm2 is present but contains no contour")
    if cut_open:
        fail(errors, f"CutInside.gm2 contains {cut_open} open contour component(s)")
    if cut_count != args.expected_cut_contours:
        fail(errors, f"CutInside contour count is {cut_count}; expected {args.expected_cut_contours}")

    plated = contents.get("DrillPlated.drl", "")
    plated_hits = sum(bool(DRILL_COORDINATE.match(line.strip())) for line in plated.splitlines())
    if plated_hits != args.expected_plated_drills:
        fail(errors, f"plated drill hit count is {plated_hits}; expected {args.expected_plated_drills}")
    unplated = contents.get("DrillUnplated.drl", "")
    unplated_hits = sum(bool(DRILL_COORDINATE.match(line.strip())) for line in unplated.splitlines())
    if unplated_hits != args.expected_unplated_drills:
        fail(errors, f"unplated drill hit count is {unplated_hits}; expected {args.expected_unplated_drills}")

    if errors:
        for message in errors:
            print(f"ERROR: {message}", file=sys.stderr)
        return 1

    print(f"PASS: {directory}")
    print(f"files={len(files)} board_outline_contours={outline_count} cut_inside_contours={cut_count} plated_drill_hits={plated_hits} unplated_drill_hits={unplated_hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
