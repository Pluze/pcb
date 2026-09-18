#!/usr/bin/env python3
"""Generate and audit an on-demand pour variant from a routing-only primary PCB."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from manufacturing_discovery import extract_blocks, point


REPOSITORY_DEFAULTS = (
    Path(__file__).resolve().parents[4]
    / ".agents"
    / "skills"
    / "kicad-pcb-layout"
    / "references"
    / "repository-defaults.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "export"))
    parser.add_argument("design", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def load_policy(design: Path, defaults_path: Path = REPOSITORY_DEFAULTS) -> dict | None:
    defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
    profile_name = defaults.get("default_profile")
    profiles = defaults.get("profiles", {})
    if profile_name not in profiles:
        raise ValueError(f"unknown repository PCB defaults profile: {profile_name!r}")
    profile = profiles[profile_name]

    repository_policy = profile.get("manufacturing", {}).get("copper_pour_variants", {})
    config_path = design / ".konnect" / "project.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    local = config.get("manufacturing", {}).get("copper_pour_variants", {})
    if local.get("enabled") is False:
        return None
    if not repository_policy.get("enabled_for_production_unless_opted_out"):
        return None
    policy = {**repository_policy, **local}
    if policy.get("default") != "no_pour":
        raise ValueError("copper_pour_variants.default must be 'no_pour'")
    pour = profile.get("copper_pour", {})
    clearance = pour.get("clearance_mm")
    if not isinstance(clearance, (int, float)) or clearance <= 0:
        raise ValueError("repository copper_pour.clearance_mm must be positive")
    return {**policy, **pour, "clearance_mm": float(clearance)}


def board_bounds(text: str) -> tuple[float, float, float, float]:
    coordinates: list[tuple[float, float]] = []
    for kind in ("gr_line", "gr_rect", "gr_arc"):
        for block in extract_blocks(text, kind):
            if '(layer "Edge.Cuts")' not in block:
                continue
            coordinates.extend((point(block, "start"), point(block, "end")))
    if not coordinates:
        raise ValueError("primary PCB has no supported Edge.Cuts geometry")
    xs = [item[0] for item in coordinates]
    ys = [item[1] for item in coordinates]
    return min(xs), min(ys), max(xs), max(ys)


def add_zone(text: str, design_name: str, policy: dict) -> str:
    if extract_blocks(text, "zone"):
        raise ValueError("primary PCB must be the no-pour routing source")
    left, top, right, bottom = board_bounds(text)
    inset = float(policy["edge_inset_mm"])
    if right - left <= 2 * inset or bottom - top <= 2 * inset:
        raise ValueError("copper-pour edge inset consumes the board outline")
    zone_uuid = uuid.uuid5(
        uuid.NAMESPACE_URL, f"pcb-repository:{design_name}:{policy['layer']}:{policy['net']}"
    )
    zone = f'''\n\t(zone
\t\t(net "{policy['net']}")
\t\t(layer "{policy['layer']}")
\t\t(uuid "{zone_uuid}")
\t\t(name "{policy['net']}_TOP")
\t\t(hatch edge 0.508)
\t\t(connect_pads
\t\t\t(clearance {policy['clearance_mm']:g})
\t\t)
\t\t(min_thickness {policy['minimum_fill_thickness_mm']:g})
\t\t(fill yes
\t\t\t(thermal_gap {policy['thermal_gap_mm']:g})
\t\t\t(thermal_bridge_width {policy['thermal_spoke_width_mm']:g})
\t\t\t(island_removal_mode 0)
\t\t)
\t\t(polygon
\t\t\t(pts
\t\t\t\t(xy {left + inset:g} {top + inset:g})
\t\t\t\t(xy {right - inset:g} {top + inset:g})
\t\t\t\t(xy {right - inset:g} {bottom - inset:g})
\t\t\t\t(xy {left + inset:g} {bottom - inset:g})
\t\t\t)
\t\t)
\t)\n'''
    stripped = text.rstrip()
    if not stripped.endswith(")"):
        raise ValueError("primary PCB is not a complete s-expression")
    return stripped[:-1] + zone + ")\n"


def validate_clearance(text: str, expected: float) -> None:
    zones = extract_blocks(text, "zone")
    if not zones:
        raise ValueError("with-pour variant contains no copper zone")
    values = []
    for zone in zones:
        match = re.search(r"\(clearance\s+([-+0-9.eE]+)\)", zone)
        if not match:
            raise ValueError("copper zone is missing an explicit clearance")
        values.append(float(match.group(1)))
    mismatches = [value for value in values if abs(value - expected) > 1e-9]
    if mismatches:
        raise ValueError(
            f"zone clearance must be {expected:g} mm; found {sorted(set(mismatches))}"
        )


def expected_variants(design: Path, policy: dict) -> dict[Path, str]:
    source = design / f"{design.name}.kicad_pcb"
    if not source.is_file():
        raise ValueError(f"missing primary PCB: {source}")
    routing_source = source.read_text(encoding="utf-8")
    if extract_blocks(routing_source, "zone"):
        raise ValueError("primary PCB must contain explicit routing only, with no copper zone")
    if f'(net "{policy["net"]}")' not in routing_source:
        raise ValueError(
            f"primary PCB has no {policy['net']} net; add an explicit copper-pour opt-out"
        )
    variants = design / "variants"
    with_pour_path = variants / f"{design.name}_{policy.get('with_pour_suffix', 'With_Pour')}.kicad_pcb"
    return {with_pour_path: add_zone(routing_source, design.name, policy)}


def audit(design: Path, expected: dict[Path, str]) -> list[str]:
    problems = []
    parent = design / "variants"
    actual = set(parent.glob("*.kicad_pcb")) if parent.is_dir() else set()
    legacy_no_pour = parent / f"{design.name}_No_Pour.kicad_pcb"
    extra = actual - set(expected)
    if legacy_no_pour in extra:
        problems.append("primary PCB is the no-pour source; remove redundant variant: " + legacy_no_pour.name)
        extra.remove(legacy_no_pour)
    if extra:
        problems.append("unexpected PCB variant(s): " + ", ".join(sorted(path.name for path in extra)))
    for path, content in expected.items():
        if not path.is_file():
            problems.append(f"missing variant: {path.name}")
        elif path.read_text(encoding="utf-8") != content:
            problems.append(f"stale variant: {path.name}")
    return problems


def export(expected: dict[Path, str], force: bool) -> Path | None:
    if not expected:
        return None
    design = next(iter(expected)).parent.parent
    problems = audit(design, expected)
    if problems and not force and any(path.exists() for path in expected):
        raise ValueError("variants differ; pass --force to replace them")
    parent = next(iter(expected)).parent
    parent.mkdir(parents=True, exist_ok=True)
    backup = None
    existing = [path for path in expected if path.is_file()]
    if existing and problems:
        backup = Path(tempfile.mkdtemp(prefix="copper-pour-variants-backup-"))
        for path in existing:
            shutil.copy2(path, backup / path.name)
    for path, content in expected.items():
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    return backup


def main() -> int:
    args = parse_args()
    try:
        design = args.design.resolve()
        policy = load_policy(design)
        if policy is None:
            stale = design / "variants" / f"{design.name}_With_Pour.kicad_pcb"
            if not stale.is_file():
                print(f"SKIP [{design.name}]: copper-pour production variant is explicitly disabled")
                return 0
            if args.mode == "audit":
                print(f"ERROR [{design.name}]: disabled copper-pour variant still exists: {stale.name}")
                return 1
            backup = Path(tempfile.mkdtemp(prefix="copper-pour-variants-backup-"))
            shutil.copy2(stale, backup / stale.name)
            stale.unlink()
            print(f"REMOVED [{design.name}]: {stale}")
            print(f"BACKUP: {backup}")
            return 0
        expected = expected_variants(design, policy)
        if args.mode == "audit":
            problems = audit(design, expected)
            if problems:
                for problem in problems:
                    print(f"ERROR [{design.name}]: {problem}")
                return 1
            print(f"PASS [{design.name}]: routing primary and with-pour production variant are current")
            return 0
        backup = export(expected, args.force)
        for path in expected:
            print(f"GENERATED [{design.name}]: {path}")
        if backup:
            print(f"BACKUP: {backup}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
