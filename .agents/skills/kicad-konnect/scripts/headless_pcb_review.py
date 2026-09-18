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
    candidates = [explicit] if explicit else []
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
    violations = data.get("violations", [])
    unconnected = data.get("unconnected_items", [])
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
    output_dir.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(board)
    staged = output_dir / "review.kicad_pcb"
    report = output_dir / "drc.json"
    svg = output_dir / "review.svg"
    png = output_dir / "review.png"
    shutil.copy2(board, staged)
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
    evidence = drc_summary(report)
    source_unchanged = source_hash == sha256(board)
    status = "pass" if (
        source_unchanged
        and evidence["unconnected"] == 0
        and evidence["severities"].get("error", 0) == 0
    ) else "fail"
    return {
        "status": status,
        "board": board.name,
        "source_unchanged": source_unchanged,
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
