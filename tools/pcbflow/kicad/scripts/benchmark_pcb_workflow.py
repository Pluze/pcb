#!/usr/bin/env python3
"""A/B benchmark common PCB workflows against goal-level orchestration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from pcb_workflow import discover_designs, topology_designs
from manage_manufacturing_outputs import EXPORTERS


SCENARIOS = (
    "manufacturing-full",
    "manufacturing-single",
    "repeat-unchanged",
    "schematic-validate",
    "new-pcb",
    "existing-pcb-inspection",
    "headless-pcb-review",
    "release-ready",
)
MAX_ERROR_CHARS = 800


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--design")
    parser.add_argument("--order", choices=("a-b", "b-a"), default="a-b")
    parser.add_argument("--report-dir", type=Path)
    return parser.parse_args()


def find_kicad_cli() -> Path:
    found = shutil.which("kicad-cli")
    candidates = [Path(found)] if found else []
    candidates.append(Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise ValueError("kicad-cli not found")


def manufacturing_commands(root: Path, designs: list[Path]) -> list[tuple[str, ...]]:
    scripts = root / "tools" / "pcbflow" / "kicad" / "scripts"
    return [
        (sys.executable, str(scripts / exporter), "audit", str(design))
        for design in designs
        for exporter in EXPORTERS
    ]


def scenario_commands(
    root: Path,
    scenario: str,
    selected: str | None,
    scratch: Path,
) -> tuple[list[tuple[str, ...]], list[tuple[str, ...]], dict]:
    scripts = root / "tools" / "pcbflow" / "kicad" / "scripts"
    workflow = scripts / "pcb_workflow.py"
    designs = discover_designs(root, [selected] if selected else None)
    metadata: dict = {"designs": [design.name for design in designs]}

    if scenario == "manufacturing-single":
        design = designs[0] if selected else next(
            (item for item in designs if item.name == "LM555_LED_Flasher"), designs[0]
        )
        designs = [design]
        metadata["designs"] = [design.name]
        baseline = manufacturing_commands(root, designs)
        candidate = [
            (
                sys.executable, str(workflow), "validate", "--root", str(root),
                "--design", design.name, "--no-cache",
            )
        ]
    elif scenario in ("manufacturing-full", "repeat-unchanged"):
        baseline = manufacturing_commands(root, designs)
        candidate_command = [
            sys.executable, str(workflow), "validate", "--root", str(root)
        ]
        if scenario == "manufacturing-full":
            candidate_command.append("--no-cache")
        candidate = [tuple(candidate_command)]
    elif scenario == "release-ready":
        baseline = [(sys.executable, str(scripts / "check_design.py"), "--root", str(root / "Designs"))]
        baseline.extend(manufacturing_commands(root, designs))
        baseline.extend((
            ("git", "diff", "--check"),
            (
                sys.executable,
                str(
                    root / "tools" / "pcbflow" / "repository"
                    / "scripts" / "check_repository_growth.py"
                ),
                "--report-worktree",
            ),
        ))
        candidate = [
            (
                sys.executable, str(workflow), "release-ready", "--root", str(root),
                "--no-cache",
            )
        ]
        metadata["candidate_extra_coverage"] = ["design-contract"]
    elif scenario == "schematic-validate":
        designs = topology_designs(designs, bool(selected))
        design = designs[0]
        topology = design / "schematic_topology.json"
        evidence = scratch / "baseline-schematic"
        evidence.mkdir(parents=True)
        baseline = [
            (
                sys.executable, str(scripts / "schematic_topology_router.py"),
                str(topology), "--plan", str(evidence / "route-plan.json"),
            ),
            (
                sys.executable, str(scripts / "validate_schematic_design.py"),
                str(topology), "--report", str(evidence / "validation.json"),
                "--render", str(evidence / "schematic.png"),
            ),
        ]
        candidate = [
            (
                sys.executable, str(workflow), "schematic-validate", "--root", str(root),
                "--design", design.name, "--no-cache",
            )
        ]
        metadata["designs"] = [design.name]
    elif scenario == "new-pcb":
        generator = (
            root / "tools" / "pcbflow" / "routing"
            / "scripts" / "generate_circular_contact_board.py"
        )
        cli = find_kicad_cli()
        baseline_dir = scratch / "baseline-board"
        candidate_dir = scratch / "candidate-board"
        board_name = "Benchmark_Circular_Contact"
        baseline_board = baseline_dir / f"{board_name}.kicad_pcb"
        baseline = [
            (
                sys.executable, str(generator), "8", "10", "18.75",
                "--name", board_name, "--output-dir", str(baseline_dir),
            ),
            (
                str(cli), "pcb", "drc", "--output", str(scratch / "baseline-drc.json"),
                "--format", "json", "--severity-error", "--exit-code-violations",
                str(baseline_board),
            ),
        ]
        candidate = [
            (
                sys.executable, str(generator), "8", "10", "18.75",
                "--name", board_name, "--output-dir", str(candidate_dir),
                "--drc", "--kicad-cli", str(cli),
            )
        ]
        metadata["designs"] = [board_name]
        metadata["candidate_extra_coverage"] = ["atomic-write-after-drc"]
    elif scenario == "existing-pcb-inspection":
        design = next(
            (item for item in designs if item.name == "Ionto_Current_Source_Core"),
            designs[0],
        )
        client = scripts / "konnect_mcp_client.py"
        board = design / f"{design.name}.kicad_pcb"
        steps = json.dumps([
            {
                "name": "load_toolset",
                "arguments": {
                    "name": [
                        "pcb_board",
                        "pcb_components",
                        "pcb_routing",
                        "placement",
                        "verification",
                        "pcb_export",
                    ]
                },
            },
            {"name": "get_board_info", "arguments": {}},
            {"name": "get_board_extents", "arguments": {}},
        ], separators=(",", ":"))
        common = (
            sys.executable, str(client), "--board", str(board), "--strict",
        )
        baseline = [(*common, "--raw", "callseq", steps)]
        candidate = [(*common, "callseq", steps)]
        metadata["designs"] = [design.name]
        metadata["candidate_extra_coverage"] = [
            "bounded-semantic-tool-output",
            "full-response-log",
        ]
    elif scenario == "headless-pcb-review":
        design = next(
            (item for item in designs if item.name == "Ionto_Current_Source_Core"),
            designs[0],
        )
        cli = find_kicad_cli()
        board = design / f"{design.name}.kicad_pcb"
        baseline_dir = scratch / "baseline-review"
        candidate_dir = scratch / "candidate-review"
        baseline_dir.mkdir()
        baseline_board = baseline_dir / "review.kicad_pcb"
        shutil.copy2(board, baseline_board)
        baseline = [
            (
                str(cli), "pcb", "drc", "--refill-zones", "--save-board",
                "--format", "json", "--output", str(baseline_dir / "drc.json"),
                str(baseline_board),
            ),
            (
                str(cli), "pcb", "export", "svg", "--check-zones",
                "--fit-page-to-board", "--exclude-drawing-sheet", "--mode-single",
                "--layers", "F.Cu,F.Silkscreen,Edge.Cuts", "--output",
                str(baseline_dir / "review.svg"), str(baseline_board),
            ),
            (
                str(cli), "pcb", "render", "--side", "top", "--width", "1200",
                "--height", "900", "--quality", "basic", "--output",
                str(baseline_dir / "review.png"), str(baseline_board),
            ),
        ]
        candidate = [
            (
                sys.executable, str(scripts / "headless_pcb_review.py"), str(board),
                "--output-dir", str(candidate_dir), "--kicad-cli", str(cli),
            )
        ]
        metadata["designs"] = [design.name]
        metadata["candidate_extra_coverage"] = [
            "source-unchanged-proof",
            "parsed-drc-summary",
            "retained-per-phase-logs",
        ]
    else:
        raise ValueError(f"unsupported scenario: {scenario}")
    return baseline, candidate, metadata


def compact_error(stdout: str, stderr: str, root: Path) -> str:
    source = stderr if stderr.strip() else stdout
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    excerpt = " | ".join(lines[-8:])[-MAX_ERROR_CHARS:]
    return excerpt.replace(str(root.resolve()), ".").replace(str(Path.home()), "~")


def run_group(commands: list[tuple[str, ...]], root: Path) -> dict:
    started = time.monotonic()
    characters = 0
    lines = 0
    exit_codes: list[int] = []
    error = ""
    for command in commands:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPYCACHEPREFIX": "/tmp/pcb-workflow-pycache"},
        )
        output = result.stdout + result.stderr
        characters += len(output)
        lines += len([line for line in output.splitlines() if line.strip()])
        exit_codes.append(result.returncode)
        if result.returncode:
            error = compact_error(result.stdout, result.stderr, root)
            break
    outcome = {
        "status": "pass" if len(exit_codes) == len(commands) and not any(exit_codes) else "fail",
        "logical_calls": len(exit_codes),
        "planned_calls": len(commands),
        "duration_s": round(time.monotonic() - started, 3),
        "output_characters": characters,
        "output_lines": lines,
        "exit_codes": exit_codes,
    }
    if error:
        outcome["error"] = error
    return outcome


def reduction(a: int | float, b: int | float) -> float | None:
    return round((1 - b / a) * 100, 1) if a else None


def remove_legacy_reports(report_dir: Path) -> None:
    for path in report_dir.glob("*.json"):
        if len(path.name) > 9 and path.name[:8].isdigit() and path.name[8] == "-":
            path.unlink()


def run_benchmark(root: Path, scenario: str, selected: str | None, order: str) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"pcb-benchmark-{scenario}-") as directory:
        scratch = Path(directory)
        baseline, candidate, metadata = scenario_commands(root, scenario, selected, scratch)
        if scenario == "repeat-unchanged":
            warmup = [*candidate[0], "--no-cache"]
            warm = run_group([tuple(warmup)], root)
            if warm["status"] != "pass":
                return {"status": "fail", "scenario": scenario, "warmup": warm}
        results: dict[str, dict] = {}
        sequence = (("A", baseline), ("B", candidate)) if order == "a-b" else (
            ("B", candidate), ("A", baseline)
        )
        for label, commands in sequence:
            results[label] = run_group(commands, root)
    matched = results["A"]["status"] == results["B"]["status"] == "pass"
    return {
        "status": "pass" if matched else "fail",
        "scenario": scenario,
        "order": order,
        **metadata,
        "A": results["A"],
        "B": results["B"],
        "reduction_percent": {
            "logical_calls": reduction(results["A"]["logical_calls"], results["B"]["logical_calls"]),
            "output_characters": reduction(results["A"]["output_characters"], results["B"]["output_characters"]),
            "output_lines": reduction(results["A"]["output_lines"], results["B"]["output_lines"]),
        },
    }


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        result = run_benchmark(root, args.scenario, args.design, args.order)
        report_dir = (args.report_dir or root / ".work" / "pcb-workflow" / "benchmarks").resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        remove_legacy_reports(report_dir)
        result["recorded_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        report = report_dir / f"{args.scenario}-{args.order}.json"
        temporary = report.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(report)
        result["report"] = report.relative_to(root).as_posix() if report.is_relative_to(root) else report.name
    except (OSError, ValueError) as exc:
        result = {"status": "fail", "scenario": args.scenario, "error": str(exc)[:MAX_ERROR_CHARS]}
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return int(result["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
