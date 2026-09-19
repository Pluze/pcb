#!/usr/bin/env python3
"""Run zone refill, DRC, 2-D export, and 3-D review without opening KiCad."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("board", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--kicad-cli", type=Path)
    return parser.parse_args()


def find_kicad_cli(explicit: Path | None) -> Path:
    if explicit is not None:
        explicit = explicit.expanduser().resolve()
        if not explicit.is_file() or not os.access(explicit, os.X_OK):
            raise ValueError(f"requested kicad-cli is not executable: {explicit}")
        return explicit
    candidates = []
    found = shutil.which("kicad-cli")
    if found:
        candidates.append(Path(found))
    candidates.append(Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"))
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise ValueError("kicad-cli not found")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], log: Path) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    log.write_text(
        f"COMMAND: {' '.join(command)}\nEXIT: {result.returncode}\n\n"
        f"STDOUT\n{result.stdout}\nSTDERR\n{result.stderr}",
        encoding="utf-8",
    )
    if result.returncode:
        message = (result.stderr or result.stdout).strip()
        if result.returncode in (134, -6) and not message:
            message = "kicad-cli aborted without diagnostic output; rerun in the permitted execution context"
        raise RuntimeError(message or f"command exited {result.returncode}")


def drc_summary(report: Path) -> dict:
    data = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
        isinstance(data.get(key), list) for key in ("violations", "unconnected_items")
    ):
        raise ValueError("invalid DRC report: missing violation or unconnected arrays")
    violations = data["violations"]
    unconnected = data["unconnected_items"]
    severities: dict[str, int] = {}
    types: dict[str, int] = {}
    for item in violations:
        severity = item.get("severity", "unknown")
        kind = item.get("type", "unknown")
        severities[severity] = severities.get(severity, 0) + 1
        types[kind] = types.get(kind, 0) + 1
    return {
        "violations": len(violations),
        "unconnected": len(unconnected),
        "severities": severities,
        "types": types,
    }


def review(board: Path, output_dir: Path, cli: Path) -> dict:
    board = board.expanduser().resolve()
    if not board.is_file():
        raise ValueError(f"board does not exist: {board}")
    project = board.with_suffix(".kicad_pro")
    if not project.is_file():
        raise ValueError("review requires a sibling .kicad_pro; stage the intended project rules explicitly")
    output_dir = output_dir.resolve()
    if output_dir == board.parent or board.parent.is_relative_to(output_dir):
        raise ValueError("review output must be isolated from the source project")
    output_dir.mkdir(parents=True, exist_ok=True)
    # A fresh workspace prevents old rules or reports from contaminating a rerun.
    workspace = Path(tempfile.mkdtemp(prefix="snapshot-", dir=output_dir))
    sources = [board, project]
    rules = board.with_suffix(".kicad_dru")
    if rules.is_file():
        sources.append(rules)
    source_hashes = {path: sha256(path) for path in sources}
    for path in sources:
        shutil.copy2(path, workspace / path.name)
    staged = workspace / board.name
    output_dir = workspace
    report = output_dir / "drc.json"
    svg = output_dir / "review.svg"
    png = output_dir / "review.png"
    run([
        str(cli), "pcb", "drc", "--refill-zones", "--save-board",
        "--format", "json", "--output", str(report), str(staged),
    ], output_dir / "drc.log")
    run([
        str(cli), "pcb", "export", "svg", "--check-zones",
        "--fit-page-to-board", "--exclude-drawing-sheet", "--mode-single",
        "--layers", "F.Cu,F.Silkscreen,Edge.Cuts", "--output", str(svg), str(staged),
    ], output_dir / "svg.log")
    run([
        str(cli), "pcb", "render", "--side", "top", "--width", "1200",
        "--height", "900", "--quality", "basic", "--output", str(png), str(staged),
    ], output_dir / "render.log")
    for artifact in (report, svg, png):
        if not artifact.is_file() or artifact.stat().st_size == 0:
            raise ValueError(f"missing or empty review artifact: {artifact.name}")
    evidence = drc_summary(report)
    source_unchanged = all(path.is_file() and sha256(path) == digest
                           for path, digest in source_hashes.items())
    status = "pass" if (
        source_unchanged
        and evidence["unconnected"] == 0
        and all(level == "warning" for level in evidence["severities"])
    ) else "fail"
    return {
        "status": status,
        "board": board.name,
        "source_unchanged": source_unchanged,
        "inputs": {path.name: digest for path, digest in source_hashes.items()},
        "coverage": "saved PCB geometry and project rules; schematic parity and visual approval not included",
        "drc": evidence,
        "artifacts": {
            "drc": str(report),
            "svg": str(svg),
            "png": str(png),
        },
        "details": str(output_dir),
    }


def main() -> int:
    args = parse_args()
    try:
        output = args.output_dir or Path(tempfile.mkdtemp(prefix="pcb-headless-review-"))
        result = review(args.board, output.resolve(), find_kicad_cli(args.kicad_cli))
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        result = {"status": "fail", "error": str(exc)[:800]}
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return int(result["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
