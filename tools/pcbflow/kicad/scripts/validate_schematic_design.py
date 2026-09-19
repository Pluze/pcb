#!/usr/bin/env python3
"""Validate a KiCad schematic against a declarative pin-level topology.

This reusable repository tool combines static topology checks with Konnect's
connectivity, geometry, render, and ERC checks.  It never edits the schematic.
The JSON report distinguishes hard failures from visual-review evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from konnect_mcp_client import content_payload, request, start_process


def call(proc: Any, request_id: int, name: str, arguments: dict[str, Any], timeout: int) -> Any:
    response = request(
        proc,
        request_id,
        "tools/call",
        {"name": name, "arguments": arguments},
        timeout,
    )
    payload = content_payload(response)
    if isinstance(payload, dict) and "error" in payload:
        raise RuntimeError(f"{name}: {json.dumps(payload, ensure_ascii=False)}")
    return payload


def endpoint_parts(endpoint: str) -> tuple[str, str]:
    if "." not in endpoint:
        raise ValueError(f"Endpoint must be REF.PIN: {endpoint!r}")
    ref, number = endpoint.rsplit(".", 1)
    return ref, number


def strict_inside(value: float, low: float, high: float, tolerance: float = 1e-6) -> bool:
    return low + tolerance < value < high - tolerance


def wire_crosses_box(wire: dict[str, Any], box: dict[str, float]) -> bool:
    x1, y1, x2, y2 = wire["x1"], wire["y1"], wire["x2"], wire["y2"]
    if abs(y1 - y2) < 1e-6:
        if not strict_inside(y1, box["y_min"], box["y_max"]):
            return False
        return max(min(x1, x2), box["x_min"]) < min(max(x1, x2), box["x_max"])
    if abs(x1 - x2) < 1e-6:
        if not strict_inside(x1, box["x_min"], box["x_max"]):
            return False
        return max(min(y1, y2), box["y_min"]) < min(max(y1, y2), box["y_max"])
    return True


def symbol_body_box(component: dict[str, Any], pins: list[dict[str, Any]]) -> dict[str, float]:
    """Remove outward pin extensions from a transformed symbol bound.

    Konnect's component bounds intentionally include pins.  Treating those
    bounds as the symbol body reports legal routing beside an IC or resistor as
    a body crossing.  Exact transformed pin direction and length identify the
    body-side end of each outward pin without any library-specific exceptions.
    """
    body = dict(component["bounds"])
    west_body_edges: list[float] = []
    east_body_edges: list[float] = []
    north_body_edges: list[float] = []
    south_body_edges: list[float] = []
    for pin in pins:
        angle = int(round(float(pin["orientation_degrees"]))) % 360
        length = float(pin.get("length_mm", 0.0))
        if angle == 180:
            west_body_edges.append(float(pin["x"]) + length)
        elif angle == 0:
            east_body_edges.append(float(pin["x"]) - length)
        elif angle == 90:
            north_body_edges.append(float(pin["y"]) + length)
        elif angle == 270:
            south_body_edges.append(float(pin["y"]) - length)

    if west_body_edges:
        body["x_min"] = max(body["x_min"], min(west_body_edges))
    if east_body_edges:
        body["x_max"] = min(body["x_max"], max(east_body_edges))
    if north_body_edges:
        body["y_min"] = max(body["y_min"], min(north_body_edges))
    if south_body_edges:
        body["y_max"] = min(body["y_max"], max(south_body_edges))
    return body


def wire_leaves_pin_outward(wire: dict[str, Any], pin: dict[str, Any], tolerance: float = 1e-6) -> bool:
    endpoints = ((wire["x1"], wire["y1"], wire["x2"], wire["y2"]), (wire["x2"], wire["y2"], wire["x1"], wire["y1"]))
    for x, y, other_x, other_y in endpoints:
        if abs(x - pin["x"]) > tolerance or abs(y - pin["y"]) > tolerance:
            continue
        dx, dy = other_x - x, other_y - y
        angle = int(round(float(pin["orientation_degrees"]))) % 360
        return (
            (angle == 0 and dx > 0 and abs(dy) <= tolerance)
            or (angle == 90 and dy < 0 and abs(dx) <= tolerance)
            or (angle == 180 and dx < 0 and abs(dy) <= tolerance)
            or (angle == 270 and dy > 0 and abs(dx) <= tolerance)
        )
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topology", type=Path, help="Topology JSON containing schematic and nets")
    parser.add_argument("--report", type=Path, help="Write JSON report")
    parser.add_argument("--render", type=Path, help="Write a PNG for mandatory human visual review")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    topology = json.loads(args.topology.read_text())
    schematic = topology["schematic"]
    nets = topology["nets"]
    endpoint_owner: dict[str, str] = {}
    duplicate_endpoints: list[dict[str, str]] = []
    references: set[str] = set()
    for net in nets:
        groups = net.get("groups")
        endpoint_groups = groups if groups else [net]
        for endpoint in (
            endpoint
            for group in endpoint_groups
            for endpoint in group["endpoints"]
        ):
            if endpoint in endpoint_owner:
                duplicate_endpoints.append(
                    {"endpoint": endpoint, "first_net": endpoint_owner[endpoint], "second_net": net["name"]}
                )
            endpoint_owner[endpoint] = net["name"]
            references.add(endpoint_parts(endpoint)[0])

    proc, _ = start_process(args.timeout, 2)
    request_id = 2
    try:
        call(
            proc,
            request_id,
            "load_toolset",
            {"name": ["sch_components", "sch_analysis", "sch_batch", "sch_export"]},
            args.timeout,
        )
        request_id += 1
        pin_data = call(
            proc,
            request_id,
            "batch_get_schematic_pin_locations",
            {"schematic": schematic, "references": sorted(references)},
            args.timeout,
        )
        request_id += 1
        layout = call(proc, request_id, "get_schematic_layout", {"schematic": schematic, "include_wires": True}, args.timeout)
        request_id += 1
        wires = call(proc, request_id, "list_schematic_wires", {"schematic": schematic}, args.timeout)
        request_id += 1
        overlap = call(proc, request_id, "check_schematic_overlaps", {"schematic": schematic}, args.timeout)
        request_id += 1
        wire_validation = call(proc, request_id, "validate_wire_connections", {"schematic": schematic}, args.timeout)
        request_id += 1
        component_validation = call(proc, request_id, "validate_component_connections", {"schematic": schematic}, args.timeout)
        request_id += 1
        orphans = call(proc, request_id, "find_orphan_items", {"schematic": schematic}, args.timeout)
        request_id += 1
        shorts = call(proc, request_id, "find_shorted_nets", {"schematic": schematic}, args.timeout)
        request_id += 1
        erc = call(proc, request_id, "run_erc", {"schematic": schematic}, args.timeout)
        request_id += 1

        pin_items = pin_data.get("components", pin_data) if isinstance(pin_data, dict) else pin_data
        pins_by_reference = {
            component["reference"]: component["pins"]
            for component in pin_items
        }
        actual_pins = {
            (component["reference"], str(pin["number"]))
            for component in pin_items
            for pin in component["pins"]
        }
        missing_endpoints = [
            endpoint
            for endpoint in endpoint_owner
            if endpoint_parts(endpoint) not in actual_pins
        ]

        wire_items = wires.get("wires", wires) if isinstance(wires, dict) else wires
        wire_through_symbols: list[dict[str, Any]] = []
        for wire in wire_items:
            for component in layout["components"]:
                component_pins = pins_by_reference.get(component["reference"], [])
                body_box = symbol_body_box(component, component_pins)
                if wire_crosses_box(wire, body_box):
                    if any(
                        wire_leaves_pin_outward(wire, pin)
                        for pin in component_pins
                    ):
                        continue
                    wire_through_symbols.append(
                        {
                            "wire_uuid": wire.get("uuid"),
                            "reference": component["reference"],
                            "body_box": body_box,
                        }
                    )

        render_result = None
        if args.render:
            args.render.parent.mkdir(parents=True, exist_ok=True)
            render_result = call(
                proc,
                request_id,
                "render_schematic_png",
                {"schematic": schematic, "output": str(args.render), "width": 2400},
                args.timeout,
            )
            request_id += 1

        report = {
            "topology": str(args.topology),
            "schematic": schematic,
            "topology_checks": {
                "net_count": len(nets),
                "endpoint_count": len(endpoint_owner),
                "duplicate_endpoints": duplicate_endpoints,
                "missing_endpoints": missing_endpoints,
            },
            "geometry_checks": {
                "symbol_overlaps": overlap,
                "wire_through_symbols": wire_through_symbols,
                "wire_validation": wire_validation,
            },
            "connectivity_checks": {
                "component_validation": component_validation,
                "orphans": orphans,
                "shorted_named_nets": shorts,
            },
            "erc": erc,
            "render": render_result,
            "visual_review_required": [
                "text-on-wire or text-on-symbol",
                "ambiguous crossings or junctions",
                "vertical/crowded values",
                "excessive detours and poor block balance",
                "feedback and return paths understandable without labels",
            ],
        }

        hard_failures = bool(duplicate_endpoints or missing_endpoints or wire_through_symbols)
        for result in (overlap, wire_validation, component_validation, orphans, shorts, erc):
            if isinstance(result, dict):
                for key in ("error_count", "errors", "overlap_count", "floating_count", "unconnected_count", "short_count", "orphan_count"):
                    value = result.get(key)
                    if isinstance(value, int) and value > 0:
                        hard_failures = True
                    elif isinstance(value, list) and value:
                        hard_failures = True
        report["hard_failures"] = hard_failures

        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        raise SystemExit(1 if hard_failures else 0)
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()
