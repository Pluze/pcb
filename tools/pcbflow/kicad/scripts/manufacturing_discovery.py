#!/usr/bin/env python3
"""Discover publishable boards and infer manufacturing intent from KiCad PCB files."""

from __future__ import annotations

import re
import json
import shutil
from pathlib import Path


def extract_blocks(text: str, kind: str) -> list[str]:
    starts = [match.start() for match in re.finditer(rf"\({re.escape(kind)}(?=\s)", text)]
    blocks: list[str] = []
    for start in starts:
        depth = 0
        quoted = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    blocks.append(text[start : index + 1])
                    break
        else:
            raise ValueError(f"unterminated ({kind} ...) block")
    return blocks


def discover_boards(design: Path) -> list[Path]:
    design = design.resolve()
    if not design.is_dir():
        raise ValueError(f"not a design directory: {design}")
    primary = design / f"{design.name}.kicad_pcb"
    if not primary.is_file():
        raise ValueError(f"missing primary PCB: {primary}")
    panels = sorted((design / "panels").glob("*.kicad_pcb"))
    if panels:
        return panels
    variants = sorted((design / "variants").glob("*.kicad_pcb"))
    if variants:
        return [primary, *variants]
    return [primary]


def layer_has_geometry(text: str, layer: str) -> bool:
    escaped = re.escape(layer)
    return bool(
        re.search(rf'\(layer\s+"{escaped}"\)', text)
        or re.search(rf'\(layers\s+[^)]*"{escaped}"', text)
        or (layer in ("F.Cu", "B.Cu") and re.search(r'\(layers\s+[^)]*"\*\.Cu"', text))
        or (layer in ("F.Mask", "B.Mask") and re.search(r'\(layers\s+[^)]*"\*\.Mask"', text))
    )


def point(block: str, field: str) -> tuple[float, float]:
    match = re.search(rf"\({field}\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", block)
    if not match:
        raise ValueError(f"missing {field} coordinate in {block[:40]!r}")
    return round(float(match.group(1)), 6), round(float(match.group(2)), 6)


def coupon_contours(text: str, layer: str | None) -> int:
    if layer is None:
        return 0
    marker = f'(layer "{layer}")'
    count = sum(
        marker in block
        for kind in ("gr_rect", "gr_circle", "gr_poly")
        for block in extract_blocks(text, kind)
    )
    edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for kind in ("gr_line", "gr_arc"):
        for block in extract_blocks(text, kind):
            if marker in block:
                edges.append((point(block, "start"), point(block, "end")))
    adjacency: dict[tuple[float, float], list[tuple[float, float]]] = {}
    for start, end in edges:
        adjacency.setdefault(start, []).append(end)
        adjacency.setdefault(end, []).append(start)
    unseen = set(adjacency)
    while unseen:
        count += 1
        stack = [unseen.pop()]
        component = []
        while stack:
            node = stack.pop()
            component.append(node)
            for neighbor in adjacency[node]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        if any(len(adjacency[node]) % 2 for node in component):
            raise ValueError(f"{layer} contains an open coupon-cut contour")
    return count


def drill_counts(text: str) -> tuple[int, int]:
    plated = sum("(drill " in block for block in extract_blocks(text, "via"))
    unplated = 0
    for block in extract_blocks(text, "pad"):
        if "(drill " not in block:
            continue
        header = block.splitlines()[0]
        if re.search(r"\bnp_thru_hole\b", header):
            unplated += 1
        elif re.search(r"\bthru_hole\b", header):
            plated += 1
    return plated, unplated


def inspect_board(board: Path, output_root: Path) -> dict:
    board = board.resolve()
    text = board.read_text(encoding="utf-8")
    copper_layers = [layer for layer in ("F.Cu", "B.Cu") if layer_has_geometry(text, layer)]
    if not copper_layers:
        raise ValueError(f"{board.name}: no copper geometry found")
    coupon_match = re.search(
        r'\(\d+\s+"(User\.\d+)"\s+user\s+"Coupon\.Cuts"\)', text
    )
    coupon_layer = coupon_match.group(1) if coupon_match else None
    cut_count = coupon_contours(text, coupon_layer)
    plated, unplated = drill_counts(text)
    sides = [
        side for side, layer in (("front", "F.Mask"), ("back", "B.Mask"))
        if layer_has_geometry(text, layer)
    ]
    if not sides:
        raise ValueError(f"{board.name}: no solder-mask opening geometry found")
    layers = [*copper_layers, "Edge.Cuts"]
    if coupon_layer:
        if not cut_count:
            raise ValueError(f"{board.name}: Coupon.Cuts layer has no closed contours")
        layers.append(coupon_layer)
    expected_files = {"BoardOutline.gm1"}
    if "F.Cu" in copper_layers:
        expected_files.add("TopLayer.gtl")
    if "B.Cu" in copper_layers:
        expected_files.add("BottomLayer.gbl")
    if coupon_layer:
        expected_files.add("CutInside.gm2")
    if plated:
        expected_files.add("DrillPlated.drl")
    if unplated:
        expected_files.add("DrillUnplated.drl")
    return {
        "name": board.stem,
        "board": board,
        "output": output_root.resolve() / board.stem,
        "layers": layers,
        "coupon_layer": coupon_layer,
        "cut_count": cut_count,
        "plated_drills": plated,
        "unplated_drills": unplated,
        "sides": sides,
        "expected_files": expected_files,
    }


def discover_packages(design: Path, output_kind: str, selected: list[str] | None = None) -> list[dict]:
    design = design.resolve()
    output_root = design / "fabrication" / output_kind
    packages = [inspect_board(board, output_root) for board in discover_boards(design)]
    for package in packages:
        sibling = package["board"].with_suffix(".kicad_pro")
        package["project"] = sibling if sibling.is_file() else design / f"{design.name}.kicad_pro"
    if selected:
        wanted = set(selected)
        available = {package["name"] for package in packages}
        missing = wanted - available
        if missing:
            raise ValueError(f"unknown package(s): {', '.join(sorted(missing))}")
        packages = [package for package in packages if package["name"] in wanted]
    return packages


def stage_package_board(package: dict, destination: Path) -> None:
    """Stage the selected design rules under the export board's matching stem."""
    project = package["project"]
    if not project.is_file():
        raise ValueError(f"missing manufacturing project rules: {project.name}")
    shutil.copy2(package["board"], destination)
    shutil.copy2(project, destination.with_suffix(".kicad_pro"))
    rules = project.with_suffix(".kicad_dru")
    if rules.is_file():
        shutil.copy2(rules, destination.with_suffix(".kicad_dru"))


def drc_failure_detail(command: list[str]) -> str:
    """Preserve actionable DRC evidence before an export workspace is deleted."""
    if 'drc' not in command or '--output' not in command:
        return ''
    try:
        report = Path(command[command.index('--output') + 1])
        data = json.loads(report.read_text())
        issues = data.get('violations', []) + data.get('unconnected_items', [])
        lines = []
        for issue in issues[:10]:
            items = '; '.join(item.get('description', '') for item in issue.get('items', []))
            lines.append(f"{issue.get('type', 'unknown')}: {issue.get('description', '')}; {items}")
        return '\nDRC details: ' + ' | '.join(lines) if lines else ''
    except (OSError, ValueError, IndexError, TypeError, AttributeError):
        return '\nDRC details unavailable; inspect the child-process diagnostic'
