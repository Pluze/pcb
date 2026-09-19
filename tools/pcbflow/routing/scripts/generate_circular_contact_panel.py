#!/usr/bin/env python3
"""Generate a panel with one process boundary and separate coupon-cut geometry."""

from __future__ import annotations

import argparse
import csv
import math
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


KICAD_FORMAT_VERSION = 20250610
DEFAULT_CENTER_MM = 100.0


@dataclass(frozen=True)
class BoardSpec:
    front_diameter: float
    back_diameter: float
    board_side: float


@dataclass
class Shelf:
    groups: list[BoardSpec]


def positive_number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("value must be a finite number greater than zero")
    return number


def load_csv_specs(path: Path) -> list[BoardSpec]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        required = {"front_diameter", "back_diameter", "board_side"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV header must include {', '.join(sorted(required))}")
        specs = [
            BoardSpec(
                positive_number(row["front_diameter"]),
                positive_number(row["back_diameter"]),
                positive_number(row["board_side"]),
            )
            for row in reader
            if row and any(value.strip() for value in row.values() if value)
        ]
    if not specs:
        raise ValueError("CSV contains no board specifications")
    return specs


def fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def stable_uuid(stem: str, item: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"pcb-repo:{stem}:{item}"))


def group_width(spec: BoardSpec, count: int, gap: float) -> float:
    return count * spec.board_side + (count - 1) * gap


def shelf_width(shelf: Shelf, count: int, gap: float) -> float:
    return sum(group_width(spec, count, gap) for spec in shelf.groups) + gap * (
        len(shelf.groups) - 1
    )


def shelf_height(shelf: Shelf) -> float:
    return max(spec.board_side for spec in shelf.groups)


def pack_shelves(
    specs: list[BoardSpec], count: int, gap: float, max_width: float
) -> list[Shelf]:
    shelves = [Shelf([spec]) for spec in sorted(specs, key=lambda item: item.board_side, reverse=True)]
    if any(shelf_width(shelf, count, gap) > max_width for shelf in shelves):
        raise ValueError("one variant row is wider than the usable stock width")

    while True:
        candidates: list[tuple[float, float, int, int, Shelf]] = []
        for left in range(len(shelves)):
            for right in range(left + 1, len(shelves)):
                merged = Shelf(shelves[left].groups + shelves[right].groups)
                width = shelf_width(merged, count, gap)
                if width <= max_width:
                    saved_height = min(shelf_height(shelves[left]), shelf_height(shelves[right]))
                    candidates.append((-saved_height, width, left, right, merged))
        if not candidates:
            break
        _, _, left, right, merged = min(candidates)
        shelves[left] = merged
        del shelves[right]

    return sorted(shelves, key=shelf_height, reverse=True)


def parse_manual_rows(values: list[str], specs: list[BoardSpec], minimum_each: int) -> list[list[BoardSpec]]:
    by_side = {spec.board_side: spec for spec in specs}
    rows: list[list[BoardSpec]] = []
    totals = {spec: 0 for spec in specs}
    for value in values:
        row: list[BoardSpec] = []
        for field in value.split(","):
            try:
                side_text, count_text = field.split(":", 1)
                side = positive_number(side_text.strip())
                count = int(count_text.strip())
            except (ValueError, argparse.ArgumentTypeError) as exc:
                raise ValueError(f"invalid --row entry {field!r}; use SIDE:COUNT") from exc
            if count < 1:
                raise ValueError("every --row count must be at least 1")
            matches = [candidate for candidate in by_side if math.isclose(candidate, side)]
            if len(matches) != 1:
                raise ValueError(f"--row board side {side:g} does not uniquely match the CSV")
            spec = by_side[matches[0]]
            row.extend([spec] * count)
            totals[spec] += count
        rows.append(row)
    missing = [fmt(spec.board_side) for spec, total in totals.items() if total < minimum_each]
    if missing:
        raise ValueError(
            f"manual rows provide fewer than {minimum_each} copies for board side(s): {', '.join(missing)}"
        )
    return rows


def render_panel(
    specs: list[BoardSpec],
    stem: str,
    count: int,
    gap: float,
    stock_width: float,
    stock_height: float,
    fiducial_distance: float,
    fiducial_diameter: float,
    via_diameter: float,
    via_drill: float,
    stock_edge_margin: float,
    processing_rail: float,
    manual_rows: Optional[list[list[BoardSpec]]],
) -> tuple[str, dict[str, float | int]]:
    reserve = fiducial_distance + fiducial_diameter / 2
    max_content_width = stock_width - 2 * (reserve + stock_edge_margin + processing_rail)
    max_content_height = stock_height - 2 * (reserve + stock_edge_margin + processing_rail)
    if manual_rows:
        rows = manual_rows
    else:
        shelves = pack_shelves(specs, count, gap, max_content_width)
        rows = [[spec for spec in shelf.groups for _ in range(count)] for shelf in shelves]
    row_widths = [sum(spec.board_side for spec in row) + gap * (len(row) - 1) for row in rows]
    row_heights = [max(spec.board_side for spec in row) for row in rows]
    panel_width = max(row_widths)
    panel_height = sum(row_heights) + gap * (len(rows) - 1)
    if panel_width > max_content_width:
        raise ValueError(
            f"panel requires {panel_width:g} mm width but only {max_content_width:g} mm is available"
        )
    if panel_height > max_content_height:
        raise ValueError(
            f"panel requires {panel_height:g} mm height but only {max_content_height:g} mm is available"
        )

    cx = cy = DEFAULT_CENTER_MM
    stock_left = cx - stock_width / 2
    stock_right = cx + stock_width / 2
    stock_top = cy - stock_height / 2
    stock_bottom = cy + stock_height / 2
    panel_left = cx - panel_width / 2
    panel_top = cy - panel_height / 2
    outline_width = panel_width + 2 * processing_rail
    outline_height = panel_height + 2 * processing_rail
    outline_left = cx - outline_width / 2
    outline_right = cx + outline_width / 2
    outline_top = cy - outline_height / 2
    outline_bottom = cy + outline_height / 2

    lines = [
        "(kicad_pcb",
        f"  (version {KICAD_FORMAT_VERSION})",
        '  (generator "pcb-repo-circular-contact-panel-generator")',
        '  (generator_version "10.0")',
        "  (general (thickness 1.6))",
        '  (paper "A4")',
        "  (layers",
        '    (0 "F.Cu" signal)',
        '    (31 "B.Cu" signal)',
        '    (32 "B.Adhes" user "B.Adhesive")',
        '    (33 "F.Adhes" user "F.Adhesive")',
        '    (34 "B.Paste" user)',
        '    (35 "F.Paste" user)',
        '    (36 "B.SilkS" user "B.Silkscreen")',
        '    (37 "F.SilkS" user "F.Silkscreen")',
        '    (38 "B.Mask" user)',
        '    (39 "F.Mask" user)',
        '    (40 "Dwgs.User" user "User.Drawings")',
        '    (41 "Cmts.User" user "User.Comments")',
        '    (44 "Edge.Cuts" user)',
        '    (45 "Margin" user)',
        '    (46 "B.CrtYd" user "B.Courtyard")',
        '    (47 "F.CrtYd" user "F.Courtyard")',
        '    (48 "B.Fab" user)',
        '    (49 "F.Fab" user)',
        '    (50 "User.1" user "Coupon.Cuts")',
        "  )",
        "  (setup (pad_to_mask_clearance 0))",
        '  (net 0 "")',
    ]

    placements: list[tuple[BoardSpec, float, float]] = []
    y = panel_top
    for row, width, row_height in zip(rows, row_widths, row_heights):
        x = cx - width / 2
        for spec in row:
            placements.append((spec, x + spec.board_side / 2, y + spec.board_side / 2))
            x += spec.board_side + gap
        y += row_height + gap

    for index, (spec, x, y) in enumerate(placements, start=1):
        net_name = f"CONTACT_{index:02d}"
        lines.append(f'  (net {index} "{net_name}")')
        lines.extend(
            [
                '  (footprint "Circular_Contact_Asymmetric"',
                '    (layer "F.Cu")',
                f'    (uuid "{stable_uuid(stem, f"footprint-{index}")}")',
                f"    (at {fmt(x)} {fmt(y)})",
                f'    (property "Reference" "J{index}"',
                '      (at 0 0 0) (layer "F.Fab") (hide yes)',
                f'      (uuid "{stable_uuid(stem, f"reference-{index}")}")',
                '      (effects (font (size 1 1) (thickness 0.15)))',
                "    )",
                f'    (property "Value" "FRONT_{fmt(spec.front_diameter)}mm_BACK_{fmt(spec.back_diameter)}mm"',
                '      (at 0 0 0) (layer "F.Fab") (hide yes)',
                f'      (uuid "{stable_uuid(stem, f"value-{index}")}")',
                '      (effects (font (size 1 1) (thickness 0.15)))',
                "    )",
                "    (attr smd)",
                "    (duplicate_pad_numbers_are_jumpers no)",
                f'    (pad "1" smd circle (at 0 0) (size {fmt(spec.front_diameter)} {fmt(spec.front_diameter)})',
                f'      (layers "F.Cu" "F.Mask") (net {index} "{net_name}")',
                f'      (uuid "{stable_uuid(stem, f"front-pad-{index}")}"))',
                f'    (pad "1" smd circle (at 0 0) (size {fmt(spec.back_diameter)} {fmt(spec.back_diameter)})',
                f'      (layers "B.Cu" "B.Mask") (net {index} "{net_name}")',
                f'      (uuid "{stable_uuid(stem, f"back-pad-{index}")}"))',
                "  )",
                f"  (gr_rect (start {fmt(x - spec.board_side / 2)} {fmt(y - spec.board_side / 2)})",
                f"    (end {fmt(x + spec.board_side / 2)} {fmt(y + spec.board_side / 2)})",
                '    (stroke (width 0.05) (type default)) (fill none) (layer "User.1")',
                f'    (uuid "{stable_uuid(stem, f"outline-{index}")}"))',
                f"  (via (at {fmt(x)} {fmt(y)}) (size {fmt(via_diameter)}) (drill {fmt(via_drill)})",
                f'    (layers "F.Cu" "B.Cu") (net {index})',
                f'    (uuid "{stable_uuid(stem, f"via-{index}")}"))',
            ]
        )

    lines.extend(
        [
            f"  (gr_rect (start {fmt(outline_left)} {fmt(outline_top)}) (end {fmt(outline_right)} {fmt(outline_bottom)})",
            '    (stroke (width 0.05) (type default)) (fill none) (layer "Edge.Cuts")',
            f'    (uuid "{stable_uuid(stem, "processing-outline")}"))',
            f"  (gr_rect (start {fmt(stock_left)} {fmt(stock_top)}) (end {fmt(stock_right)} {fmt(stock_bottom)})",
            '    (stroke (width 0.2) (type dash)) (fill none) (layer "Dwgs.User")',
            f'    (uuid "{stable_uuid(stem, "stock-outline")}"))',
            f'  (gr_text "RAW FR4 {fmt(stock_width)} x {fmt(stock_height)} mm - NOT A CUT"',
            f"    (at {fmt(cx)} {fmt(stock_top + 2.5)}) (layer \"Dwgs.User\")",
            f'    (uuid "{stable_uuid(stem, "stock-label")}")',
            '    (effects (font (size 1.2 1.2) (thickness 0.2))))',
        ]
    )

    fid_x = (outline_left - fiducial_distance, outline_right + fiducial_distance)
    fid_y = (outline_top - fiducial_distance, outline_bottom + fiducial_distance)
    fid_index = 0
    for x in fid_x:
        for y in fid_y:
            fid_index += 1
            lines.extend(
                [
                    f"  (gr_circle (center {fmt(x)} {fmt(y)}) (end {fmt(x + fiducial_diameter / 2)} {fmt(y)})",
                    '    (stroke (width 0.15) (type dash)) (fill none) (layer "Dwgs.User")',
                    f'    (uuid "{stable_uuid(stem, f"expected-fiducial-{fid_index}")}"))',
                ]
            )
    lines.append(")")
    metrics: dict[str, float | int] = {
        "board_count": len(placements),
        "panel_width": panel_width,
        "panel_height": panel_height,
        "board_outline_width": outline_width,
        "board_outline_height": outline_height,
        "fiducial_envelope_width": outline_width + 2 * reserve,
        "fiducial_envelope_height": outline_height + 2 * reserve,
        "minimum_stock_edge_margin": min(
            (stock_width - outline_width - 2 * reserve) / 2,
            (stock_height - outline_height - 2 * reserve) / 2,
        ),
    }
    return "\n".join(lines) + "\n", metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--count-each", type=int, default=3)
    parser.add_argument("--gap", type=positive_number, default=2.0)
    parser.add_argument("--stock-width", type=positive_number, default=150.0)
    parser.add_argument("--stock-height", type=positive_number, default=100.0)
    parser.add_argument("--fiducial-distance", type=positive_number, default=4.0)
    parser.add_argument("--fiducial-diameter", type=positive_number, default=1.5)
    parser.add_argument(
        "--stock-edge-margin",
        type=float,
        default=0.0,
        help="required clearance from the fiducial outer edge to the raw-stock edge, mm",
    )
    parser.add_argument(
        "--processing-rail",
        type=positive_number,
        default=0.75,
        help="clearance from the outer coupon envelope to the single BoardOutline, mm",
    )
    parser.add_argument(
        "--row",
        action="append",
        default=[],
        metavar="SIDE:COUNT[,SIDE:COUNT...]",
        help="explicit row layout keyed by board side; repeat for additional rows",
    )
    parser.add_argument("--via-diameter", type=positive_number, default=2.0)
    parser.add_argument("--via-drill", type=positive_number, default=1.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.count_each < 1:
        parser.error("--count-each must be at least 1")
    if args.stock_edge_margin < 0:
        parser.error("--stock-edge-margin cannot be negative")
    if args.via_drill >= args.via_diameter:
        parser.error("via drill must be smaller than via diameter")
    if args.output.exists() and not args.force:
        parser.error(f"refusing to overwrite existing file without --force: {args.output}")
    try:
        specs = load_csv_specs(args.csv)
        manual_rows = parse_manual_rows(args.row, specs, args.count_each) if args.row else None
        contents, metrics = render_panel(
            specs,
            args.output.stem,
            args.count_each,
            args.gap,
            args.stock_width,
            args.stock_height,
            args.fiducial_distance,
            args.fiducial_diameter,
            args.via_diameter,
            args.via_drill,
            args.stock_edge_margin,
            args.processing_rail,
            manual_rows,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(contents, encoding="utf-8")
        temporary.replace(args.output)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(args.output.resolve())
    print(", ".join(f"{key}={fmt(value) if isinstance(value, float) else value}" for key, value in metrics.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
