#!/usr/bin/env python3
"""Generate square KiCad boards with concentric front/back circular contacts."""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path


KICAD_FORMAT_VERSION = 20250610
BOARD_CENTER_MM = 100.0
DEFAULT_EDGE_CLEARANCE_MM = 0.5
DEFAULT_VIA_DIAMETER_MM = 1.5
DEFAULT_VIA_DRILL_MM = 0.8


@dataclass(frozen=True)
class BoardSpec:
    front_diameter: float
    back_diameter: float
    board_side: float


def positive_number(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from exc
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("value must be a finite number greater than zero")
    return number


def parse_spec(value: str) -> BoardSpec:
    fields = [field.strip() for field in value.split(",")]
    if len(fields) != 3:
        raise argparse.ArgumentTypeError("spec must be FRONT_DIAMETER,BACK_DIAMETER,BOARD_SIDE")
    return BoardSpec(*(positive_number(field) for field in fields))


def load_csv_specs(path: Path) -> list[BoardSpec]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        rows = list(csv.reader(source))
    if not rows:
        raise ValueError(f"CSV file is empty: {path}")

    first = [cell.strip().lower() for cell in rows[0]]
    aliases = {
        "front": "front",
        "front_diameter": "front",
        "back": "back",
        "back_diameter": "back",
        "side": "side",
        "board_side": "side",
    }
    mapped = [aliases.get(cell) for cell in first]
    has_header = {"front", "back", "side"}.issubset(set(mapped))
    if has_header:
        indexes = {name: mapped.index(name) for name in ("front", "back", "side")}
        data_rows = rows[1:]
    else:
        indexes = {"front": 0, "back": 1, "side": 2}
        data_rows = rows

    specs: list[BoardSpec] = []
    for line_number, row in enumerate(data_rows, start=2 if has_header else 1):
        if not row or all(not cell.strip() for cell in row):
            continue
        try:
            specs.append(
                BoardSpec(
                    positive_number(row[indexes["front"]].strip()),
                    positive_number(row[indexes["back"]].strip()),
                    positive_number(row[indexes["side"]].strip()),
                )
            )
        except (IndexError, argparse.ArgumentTypeError) as exc:
            raise ValueError(f"invalid CSV row {line_number}: {row!r}: {exc}") from exc
    if not specs:
        raise ValueError(f"CSV contains no board specifications: {path}")
    return specs


def validate_spec(
    spec: BoardSpec,
    edge_clearance: float,
    via_diameter: float,
    via_drill: float,
) -> None:
    if via_drill >= via_diameter:
        raise ValueError("via drill must be smaller than via diameter")
    if via_diameter - via_drill < 0.3:
        raise ValueError("via requires at least 0.15 mm annular ring on each side")
    if via_diameter > min(spec.front_diameter, spec.back_diameter):
        raise ValueError("via diameter must fit inside both circular contacts")
    needed_side = max(spec.front_diameter, spec.back_diameter) + 2 * edge_clearance
    if spec.board_side < needed_side:
        raise ValueError(
            f"board side {spec.board_side:g} mm is too small; need at least "
            f"{needed_side:g} mm for the requested copper-to-edge clearance"
        )


def fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def slug_number(value: float) -> str:
    text = fmt(value).replace("-", "m").replace(".", "p")
    return re.sub(r"[^A-Za-z0-9_-]", "_", text)


def default_stem(spec: BoardSpec) -> str:
    return (
        f"Circular_Contact_F{slug_number(spec.front_diameter)}"
        f"_B{slug_number(spec.back_diameter)}_S{slug_number(spec.board_side)}"
    )


def stable_uuid(stem: str, item: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"pcb-repo:{stem}:{item}"))


def render_board(spec: BoardSpec, stem: str, via_diameter: float, via_drill: float) -> str:
    center = BOARD_CENTER_MM
    half_side = spec.board_side / 2
    left = center - half_side
    right = center + half_side
    top = center - half_side
    bottom = center + half_side
    uid = lambda item: stable_uuid(stem, item)

    return f'''(kicad_pcb
  (version {KICAD_FORMAT_VERSION})
  (generator "pcb-repo-circular-contact-generator")
  (generator_version "10.0")
  (general
    (thickness 1.6)
  )
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)
  )
  (setup
    (pad_to_mask_clearance 0)
  )
  (net 0 "")
  (footprint "Circular_Contact_Asymmetric"
    (layer "F.Cu")
    (uuid "{uid('footprint')}")
    (at {fmt(center)} {fmt(center)})
    (property "Reference" "J1"
      (at 0 0 0)
      (layer "F.Fab")
      (hide yes)
      (uuid "{uid('reference')}")
      (effects (font (size 1 1) (thickness 0.15)))
    )
    (property "Value" "FRONT_{fmt(spec.front_diameter)}mm_BACK_{fmt(spec.back_diameter)}mm"
      (at 0 0 0)
      (layer "F.Fab")
      (hide yes)
      (uuid "{uid('value')}")
      (effects (font (size 1 1) (thickness 0.15)))
    )
    (attr smd)
    (duplicate_pad_numbers_are_jumpers no)
    (pad "1" smd circle
      (at 0 0)
      (size {fmt(spec.front_diameter)} {fmt(spec.front_diameter)})
      (layers "F.Cu" "F.Mask")
      (net "CONTACT")
      (uuid "{uid('front-pad')}")
    )
    (pad "1" smd circle
      (at 0 0)
      (size {fmt(spec.back_diameter)} {fmt(spec.back_diameter)})
      (layers "B.Cu" "B.Mask")
      (net "CONTACT")
      (uuid "{uid('back-pad')}")
    )
  )
  (gr_rect
    (start {fmt(left)} {fmt(top)})
    (end {fmt(right)} {fmt(bottom)})
    (stroke (width 0.05) (type default))
    (fill none)
    (layer "Edge.Cuts")
    (uuid "{uid('outline')}")
  )
  (via
    (at {fmt(center)} {fmt(center)})
    (size {fmt(via_diameter)})
    (drill {fmt(via_drill)})
    (layers "F.Cu" "B.Cu")
    (net "CONTACT")
    (uuid "{uid('via')}")
  )
)\n'''


def write_board(path: Path, contents: str, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file without --force: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(contents, encoding="utf-8")
    temporary.replace(path)


def find_kicad_cli(explicit: Path | None) -> Path:
    candidates = [explicit] if explicit else []
    found = shutil.which("kicad-cli")
    if found:
        candidates.append(Path(found))
    candidates.append(Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"))
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise ValueError("kicad-cli not found; pass --kicad-cli PATH")


def validate_with_kicad(cli: Path, planned: list[tuple[Path, str]]) -> None:
    with tempfile.TemporaryDirectory(prefix="circular-contact-drc-") as directory:
        root = Path(directory)
        for output, contents in planned:
            candidate = root / output.name
            candidate.write_text(contents, encoding="utf-8")
            report = root / f"{output.stem}-drc.json"
            result = subprocess.run(
                [
                    str(cli), "pcb", "drc", "--output", str(report),
                    "--format", "json", "--severity-error",
                    "--exit-code-violations", str(candidate),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode:
                detail = (result.stderr or result.stdout).strip() or "no diagnostic output"
                raise ValueError(f"{output.name}: KiCad DRC failed: {detail}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate KiCad .kicad_pcb files for square boards with concentric "
            "front/back exposed copper contacts and a central through interconnect."
        )
    )
    parser.add_argument("front_diameter", nargs="?", type=positive_number, help="front contact diameter, mm")
    parser.add_argument("back_diameter", nargs="?", type=positive_number, help="back contact diameter, mm")
    parser.add_argument("board_side", nargs="?", type=positive_number, help="square board side, mm")
    parser.add_argument(
        "--spec",
        action="append",
        default=[],
        type=parse_spec,
        metavar="FRONT,BACK,SIDE",
        help="add a batch specification; may be repeated",
    )
    parser.add_argument("--csv", type=Path, help="load batch rows: front,back,side (optional header)")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd(), help="output directory")
    parser.add_argument("--name", help="filename stem; valid only for one generated board")
    parser.add_argument("--edge-clearance", type=positive_number, default=DEFAULT_EDGE_CLEARANCE_MM)
    parser.add_argument("--via-diameter", type=positive_number, default=DEFAULT_VIA_DIAMETER_MM)
    parser.add_argument("--via-drill", type=positive_number, default=DEFAULT_VIA_DRILL_MM)
    parser.add_argument("--drc", action="store_true", help="validate every candidate with KiCad DRC before writing")
    parser.add_argument("--kicad-cli", type=Path)
    parser.add_argument("--force", action="store_true", help="replace existing output files atomically")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    positional = (args.front_diameter, args.back_diameter, args.board_side)
    if any(value is not None for value in positional) and not all(value is not None for value in positional):
        parser.error("provide all three positional values: FRONT_DIAMETER BACK_DIAMETER BOARD_SIDE")

    specs = list(args.spec)
    if all(value is not None for value in positional):
        specs.insert(0, BoardSpec(*positional))
    if args.csv:
        try:
            specs.extend(load_csv_specs(args.csv))
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
    if not specs:
        parser.error("provide three positional values, at least one --spec, or --csv")
    if args.name and len(specs) != 1:
        parser.error("--name can only be used when generating exactly one board")

    seen_paths: set[Path] = set()
    planned: list[tuple[Path, str]] = []
    try:
        for spec in specs:
            validate_spec(spec, args.edge_clearance, args.via_diameter, args.via_drill)
            stem = args.name or default_stem(spec)
            output = (args.output_dir / f"{stem}.kicad_pcb").resolve()
            if output in seen_paths:
                raise ValueError(f"duplicate output requested: {output}")
            seen_paths.add(output)
            if output.exists() and not args.force:
                raise FileExistsError(f"refusing to overwrite existing file without --force: {output}")
            planned.append((output, render_board(spec, stem, args.via_diameter, args.via_drill)))
        if args.drc:
            validate_with_kicad(find_kicad_cli(args.kicad_cli), planned)
        for output, contents in planned:
            write_board(output, contents, args.force)
            print(output)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
