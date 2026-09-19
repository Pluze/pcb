#!/usr/bin/env python3
"""Plan and optionally apply readable orthogonal KiCad schematic wiring.

The input is a JSON design contract: named nets containing ``REF.PIN``
endpoints.  Symbol bounds, exact pin positions, and pin escape directions are
read from Konnect.  The router uses a Manhattan grid, keeps wires outside
symbol bodies, reserves an outward escape segment at every pin, and prevents
different nets from sharing or crossing a grid node.

This is deliberately a schematic topology router, not a PCB autorouter.  It
does not place symbols and it does not waive rendered visual review or ERC.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import heapq
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

from konnect_mcp_client import content_payload, request, start_process


Point = tuple[int, int]
State = tuple[Point, int]
DIRS: tuple[Point, ...] = ((1, 0), (0, 1), (-1, 0), (0, -1))


@dataclass(frozen=True)
class Pin:
    ref: str
    number: str
    point: Point
    escape: Point


def tool_call(proc: Any, request_id: int, name: str, arguments: dict[str, Any], timeout: int) -> Any:
    response = request(
        proc,
        request_id,
        "tools/call",
        {"name": name, "arguments": arguments},
        timeout,
    )
    payload = content_payload(response)
    if isinstance(payload, dict) and ("error" in payload or payload.get("errors")):
        raise RuntimeError(f"{name} failed: {json.dumps(payload, ensure_ascii=False)}")
    return payload


def snap(value: float, grid: float) -> int:
    return int(round(value / grid))


def unsnap(value: int, grid: float) -> float:
    return round(value * grid, 6)


def endpoint_parts(text: str) -> tuple[str, str]:
    if "." not in text:
        raise ValueError(f"Endpoint must be REF.PIN, got {text!r}")
    return text.rsplit(".", 1)


def points_on_segment(a: Point, b: Point) -> Iterable[Point]:
    if a[0] != b[0] and a[1] != b[1]:
        raise ValueError(f"Non-orthogonal segment: {a} -> {b}")
    dx = 0 if a[0] == b[0] else (1 if b[0] > a[0] else -1)
    dy = 0 if a[1] == b[1] else (1 if b[1] > a[1] else -1)
    p = a
    yield p
    while p != b:
        p = (p[0] + dx, p[1] + dy)
        yield p


def simplify(path: list[Point]) -> list[Point]:
    if len(path) < 3:
        return path
    result = [path[0]]
    for index in range(1, len(path) - 1):
        a, b, c = result[-1], path[index], path[index + 1]
        if (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1]):
            continue
        result.append(b)
    result.append(path[-1])
    return result


def astar(
    start: Point,
    goals: set[Point],
    blocked: set[Point],
    limits: tuple[int, int, int, int],
    bend_cost: int,
) -> list[Point] | None:
    if start in goals:
        return [start]
    x_min, x_max, y_min, y_max = limits
    queue: list[tuple[int, int, State]] = []
    counter = 0
    start_state: State = (start, -1)
    heapq.heappush(queue, (0, counter, start_state))
    best: dict[State, int] = {start_state: 0}
    parent: dict[State, State] = {}

    def heuristic(point: Point) -> int:
        return min(abs(point[0] - goal[0]) + abs(point[1] - goal[1]) for goal in goals)

    while queue:
        _, _, state = heapq.heappop(queue)
        point, previous_direction = state
        cost = best[state]
        if point in goals:
            path = [point]
            while state in parent:
                state = parent[state]
                path.append(state[0])
            return list(reversed(path))
        for direction, (dx, dy) in enumerate(DIRS):
            nxt = (point[0] + dx, point[1] + dy)
            if not (x_min <= nxt[0] <= x_max and y_min <= nxt[1] <= y_max):
                continue
            if nxt in blocked and nxt not in goals:
                continue
            step = 10 + (bend_cost if previous_direction not in (-1, direction) else 0)
            next_state = (nxt, direction)
            new_cost = cost + step
            if new_cost >= best.get(next_state, math.inf):
                continue
            best[next_state] = new_cost
            parent[next_state] = state
            counter += 1
            heapq.heappush(queue, (new_cost + 10 * heuristic(nxt), counter, next_state))
    return None


def add_path(tree: set[Point], path: list[Point]) -> None:
    for a, b in zip(path, path[1:]):
        tree.update(points_on_segment(a, b))
    tree.add(path[-1])


def route_net(
    pins: list[Pin],
    permanent_blocked: set[Point],
    other_net_nodes: set[Point],
    limits: tuple[int, int, int, int],
    bend_cost: int,
    backbone: dict[str, Any] | None = None,
    grid: float = 1.27,
) -> tuple[list[list[Point]], set[Point]]:
    paths: list[list[Point]] = []
    tree: set[Point] = set()
    carved = {pin.point for pin in pins} | {pin.escape for pin in pins}
    occupied_pin_conflicts = carved & other_net_nodes
    if occupied_pin_conflicts:
        raise RuntimeError(
            f"Pin escape is already occupied by another net at {sorted(occupied_pin_conflicts)[:5]}"
        )
    blocked = (permanent_blocked - carved) | other_net_nodes

    if backbone:
        axis = backbone.get("axis")
        coordinate = snap(float(backbone["coordinate_mm"]), grid)
        if axis == "y":
            trunk_start = (min(pin.escape[0] for pin in pins), coordinate)
            trunk_end = (max(pin.escape[0] for pin in pins), coordinate)
        elif axis == "x":
            trunk_start = (coordinate, min(pin.escape[1] for pin in pins))
            trunk_end = (coordinate, max(pin.escape[1] for pin in pins))
        else:
            raise ValueError("backbone.axis must be 'x' or 'y'")
        trunk_nodes = set(points_on_segment(trunk_start, trunk_end))
        conflicts = trunk_nodes & blocked
        if conflicts:
            raise RuntimeError(f"Backbone intersects an obstacle at {sorted(conflicts)[:5]}")
        paths.append([trunk_start, trunk_end])
        tree.update(trunk_nodes)
        remaining = list(pins)
    else:
        first = pins[0]
        first_escape = [first.point, first.escape]
        paths.append(first_escape)
        add_path(tree, first_escape)
        remaining = list(pins[1:])

    while remaining:
        best_choice: tuple[int, int, list[Point]] | None = None
        for index, pin in enumerate(remaining):
            local_blocked = blocked - tree
            path = astar(pin.escape, tree, local_blocked, limits, bend_cost)
            if path is None:
                continue
            score = len(path)
            if best_choice is None or score < best_choice[0]:
                best_choice = (score, index, path)
        if best_choice is None:
            unresolved = ", ".join(f"{pin.ref}.{pin.number}" for pin in remaining)
            raise RuntimeError(f"No orthogonal route to existing tree for: {unresolved}")
        _, index, path = best_choice
        pin = remaining.pop(index)
        escape_path = [pin.point, pin.escape]
        paths.append(escape_path)
        add_path(tree, escape_path)
        paths.append(path)
        add_path(tree, path)

    used: set[Point] = set()
    for path in paths:
        add_path(used, path)
    return paths, used


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Topology JSON file")
    parser.add_argument("--apply", action="store_true", help="Write planned wire segments to KiCad")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="With --apply, delete existing wires and matching generated net labels before writing",
    )
    parser.add_argument("--plan", type=Path, help="Write the route plan JSON here")
    parser.add_argument("--only-net", action="append", default=[], help="Route only this named net (repeatable)")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if args.replace and not args.apply:
        parser.error("--replace requires --apply")

    spec = json.loads(args.spec.read_text())
    schematic = str(Path(spec["schematic"]))
    grid = float(spec.get("grid_mm", 1.27))
    escape_steps = max(1, int(round(float(spec.get("escape_mm", grid)) / grid)))
    clearance_steps = max(0, int(math.ceil(float(spec.get("symbol_clearance_mm", grid)) / grid)))
    margin_steps = max(4, int(math.ceil(float(spec.get("routing_margin_mm", 12.7)) / grid)))
    bend_cost = int(spec.get("bend_cost", 35))
    nets = spec["nets"]
    if args.only_net:
        requested = set(args.only_net)
        nets = [net for net in nets if net["name"] in requested]
        missing = requested - {net["name"] for net in nets}
        if missing:
            raise ValueError(f"Unknown net names: {', '.join(sorted(missing))}")

    endpoint_owner: dict[str, str] = {}
    references: set[str] = set()
    routing_units: list[dict[str, Any]] = []
    for net in nets:
        groups = net.get("groups")
        if groups:
            for group_index, group in enumerate(groups, start=1):
                if "interface" not in group:
                    raise ValueError(f"Net {net['name']} group {group_index} needs an interface")
                routing_units.append(
                    {
                        "name": net["name"],
                        "unit": group.get("block", f"group_{group_index}"),
                        "endpoints": group["endpoints"],
                        "interface": group["interface"],
                        "backbone": group.get("backbone"),
                    }
                )
        else:
            routing_units.append(net)

    for unit in routing_units:
        endpoint_count = len(unit["endpoints"]) + (1 if unit.get("interface") else 0)
        if endpoint_count < 2:
            raise ValueError(f"Net {unit['name']} needs at least two endpoints")
        owner = f"{unit['name']}:{unit.get('unit', 'local')}"
        for endpoint in unit["endpoints"]:
            if endpoint in endpoint_owner:
                raise ValueError(
                    f"Endpoint {endpoint} is assigned to both {endpoint_owner[endpoint]} and {owner}"
                )
            endpoint_owner[endpoint] = owner
            references.add(endpoint_parts(endpoint)[0])

    proc, _ = start_process(args.timeout, 2)
    request_id = 2
    try:
        tool_call(
            proc,
            request_id,
            "load_toolset",
            {"name": ["sch_components", "sch_batch", "sch_wiring", "sch_analysis"]},
            args.timeout,
        )
        request_id += 1
        pin_payload = tool_call(
            proc,
            request_id,
            "batch_get_schematic_pin_locations",
            {"schematic": schematic, "references": sorted(references)},
            args.timeout,
        )
        request_id += 1
        layout = tool_call(
            proc,
            request_id,
            "get_schematic_layout",
            {"schematic": schematic, "include_wires": False},
            args.timeout,
        )
        request_id += 1

        pin_items = pin_payload.get("components", pin_payload) if isinstance(pin_payload, dict) else pin_payload
        pin_lookup: dict[tuple[str, str], dict[str, Any]] = {}
        for component in pin_items:
            for pin in component["pins"]:
                pin_lookup[(component["reference"], str(pin["number"]))] = pin

        blocked: set[Point] = set()
        all_x: list[int] = []
        all_y: list[int] = []
        for component in layout["components"]:
            bounds = component["bounds"]
            x0 = snap(bounds["x_min"], grid) - clearance_steps
            x1 = snap(bounds["x_max"], grid) + clearance_steps
            y0 = snap(bounds["y_min"], grid) - clearance_steps
            y1 = snap(bounds["y_max"], grid) + clearance_steps
            all_x.extend((x0, x1))
            all_y.extend((y0, y1))
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    blocked.add((x, y))

        prepared: list[tuple[dict[str, Any], list[Pin]]] = []
        label_plans: list[dict[str, Any]] = []
        for net in routing_units:
            pins: list[Pin] = []
            for endpoint in net["endpoints"]:
                ref, number = endpoint_parts(endpoint)
                raw = pin_lookup.get((ref, number))
                if raw is None:
                    raise ValueError(f"Pin not found in schematic: {endpoint}")
                point = (snap(raw["x"], grid), snap(raw["y"], grid))
                angle = int(round(float(raw["orientation_degrees"]))) % 360
                direction = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}.get(angle)
                if direction is None:
                    raise ValueError(f"Unsupported pin angle {angle} for {endpoint}")
                escape = (point[0] + escape_steps * direction[0], point[1] + escape_steps * direction[1])
                pins.append(Pin(ref, number, point, escape))
                all_x.extend((point[0], escape[0]))
                all_y.extend((point[1], escape[1]))
                blocked.difference_update(points_on_segment(point, escape))
            interface = net.get("interface")
            if interface:
                point = (snap(float(interface["x_mm"]), grid), snap(float(interface["y_mm"]), grid))
                angle = int(interface.get("orientation_degrees", 0)) % 360
                direction = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}.get(angle)
                if direction is None:
                    raise ValueError(f"Unsupported interface angle {angle} for {net['name']}")
                escape = (point[0] + escape_steps * direction[0], point[1] + escape_steps * direction[1])
                virtual_ref = f"@{net['name']}"
                virtual_number = str(net.get("unit", "interface"))
                pins.append(Pin(virtual_ref, virtual_number, point, escape))
                all_x.extend((point[0], escape[0]))
                all_y.extend((point[1], escape[1]))
                blocked.difference_update(points_on_segment(point, escape))
                label_plans.append(
                    {
                        "name": net["name"],
                        "unit": net.get("unit"),
                        "x": unsnap(point[0], grid),
                        "y": unsnap(point[1], grid),
                        "angle": angle,
                        "type": interface.get("type", "net_label"),
                    }
                )
            prepared.append((net, pins))

        reserved_pin_corridors: list[set[Point]] = []
        all_reserved_pin_nodes: set[Point] = set()
        for _, pins in prepared:
            reserved: set[Point] = set()
            for pin in pins:
                reserved.update(points_on_segment(pin.point, pin.escape))
            reserved_pin_corridors.append(reserved)
            all_reserved_pin_nodes.update(reserved)

        limits = (
            min(all_x) - margin_steps,
            max(all_x) + margin_steps,
            min(all_y) - margin_steps,
            max(all_y) + margin_steps,
        )
        occupied: set[Point] = set()
        plan_nets: list[dict[str, Any]] = []
        wire_segments: list[dict[str, float]] = []
        for unit_index, (net, pins) in enumerate(prepared):
            name = net["name"]
            unit_name = net.get("unit")
            unit_blocked = blocked | (all_reserved_pin_nodes - reserved_pin_corridors[unit_index])
            try:
                paths, used = route_net(
                    pins,
                    unit_blocked,
                    occupied,
                    limits,
                    bend_cost,
                    backbone=net.get("backbone"),
                    grid=grid,
                )
            except (RuntimeError, ValueError) as error:
                classification = "symbol_geometry_or_constraints"
                try:
                    route_net(
                        pins,
                        unit_blocked,
                        set(),
                        limits,
                        bend_cost,
                        backbone=net.get("backbone"),
                        grid=grid,
                    )
                    if occupied:
                        classification = "existing_routes_block_path"
                except (RuntimeError, ValueError):
                    pass
                suffix = f" ({unit_name})" if unit_name else ""
                if name.upper() in {"GND", "VCC", "VBAT", "VDD", "VSS", "VEE"}:
                    advice = (
                        "Use a small number of local power symbols or labeled power branches; "
                        "do not force a page-spanning physical rail through signal corridors."
                    )
                elif classification == "existing_routes_block_path":
                    advice = (
                        "A previously routed net consumes the required corridor. Review placement and lanes, "
                        "then change routing priority or rip up the blocking net; do not force a crossing."
                    )
                else:
                    advice = (
                        "The pin is unreachable even without earlier routes. Change symbol position/orientation, "
                        "module boundary, or an explicit lane constraint before retrying."
                    )
                raise RuntimeError(
                    f"Net {name}{suffix}: {error}; classification={classification}; suggestion={advice}"
                ) from error
            occupied.update(used)
            simplified = [simplify(path) for path in paths]
            plan_nets.append(
                {
                    "name": name,
                    "unit": unit_name,
                    "endpoints": [f"{pin.ref}.{pin.number}" for pin in pins],
                    "paths": [
                        [[unsnap(x, grid), unsnap(y, grid)] for x, y in path]
                        for path in simplified
                    ],
                }
            )
            for path in simplified:
                for a, b in zip(path, path[1:]):
                    if a == b:
                        continue
                    wire_segments.append(
                        {
                            "x1": unsnap(a[0], grid),
                            "y1": unsnap(a[1], grid),
                            "x2": unsnap(b[0], grid),
                            "y2": unsnap(b[1], grid),
                        }
                    )

        plan = {
            "schematic": schematic,
            "grid_mm": grid,
            "net_count": len(plan_nets),
            "segment_count": len(wire_segments),
            "nets": plan_nets,
            "wires": wire_segments,
            "labels": label_plans,
        }
        if args.plan:
            args.plan.parent.mkdir(parents=True, exist_ok=True)
            args.plan.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")

        if args.apply:
            if args.replace:
                existing_wires = tool_call(
                    proc,
                    request_id,
                    "list_schematic_wires",
                    {"schematic": schematic},
                    args.timeout,
                )
                request_id += 1
                wire_items = (
                    existing_wires.get("wires", existing_wires)
                    if isinstance(existing_wires, dict)
                    else existing_wires
                )
                wire_uuids = [wire["uuid"] for wire in wire_items if wire.get("uuid")]
                if wire_uuids:
                    plan["replace_wire_result"] = tool_call(
                        proc,
                        request_id,
                        "batch_delete_schematic_wire",
                        {"schematic": schematic, "uuids": wire_uuids},
                        args.timeout,
                    )
                    request_id += 1
                existing_labels = tool_call(
                    proc,
                    request_id,
                    "list_schematic_labels",
                    {"schematic": schematic},
                    args.timeout,
                )
                request_id += 1
                label_items = (
                    existing_labels.get("labels", existing_labels)
                    if isinstance(existing_labels, dict)
                    else existing_labels
                )
                generated_names = {label["name"] for label in label_plans}
                removed_labels: list[Any] = []
                for label in label_items:
                    label_name = label.get("net", label.get("name"))
                    if label_name not in generated_names:
                        continue
                    removed_labels.append(
                        tool_call(
                            proc,
                            request_id,
                            "delete_schematic_net_label",
                            {
                                "schematic": schematic,
                                "net": label_name,
                                "x": label["x"],
                                "y": label["y"],
                            },
                            args.timeout,
                        )
                    )
                    request_id += 1
                plan["replace_label_results"] = removed_labels
            result = tool_call(
                proc,
                request_id,
                "batch_add_wire",
                {"schematic": schematic, "wires": wire_segments},
                args.timeout,
            )
            request_id += 1
            plan["apply_result"] = result
            applied_labels: list[Any] = []
            for label in label_plans:
                applied_labels.append(
                    tool_call(
                        proc,
                        request_id,
                        "add_schematic_net_label",
                        {
                            "schematic": schematic,
                            "net": label["name"],
                            "x": label["x"],
                            "y": label["y"],
                            "rotation": label["angle"],
                            "label_type": label["type"],
                        },
                        args.timeout,
                    )
                )
                request_id += 1
            plan["apply_label_results"] = applied_labels

        json.dump(plan, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()
