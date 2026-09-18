#!/usr/bin/env python3
"""Run self-discovered PCB repository goals with bounded model-visible output."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


EXCLUDED_DIRS = {".git", ".work", "__pycache__", ".pytest_cache"}
GOALS = ("validate", "manufacturing-refresh", "release-ready")
MAX_ERROR_CHARS = 1200


@dataclass(frozen=True)
class Phase:
    name: str
    command: tuple[str, ...] | None = None
    cacheable: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("goal", choices=("plan", *GOALS))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--design", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    return parser.parse_args()


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def discover_designs(root: Path, selected: list[str] | None = None) -> list[Path]:
    designs_root = root / "Designs"
    if not designs_root.is_dir():
        raise ValueError("missing Designs directory")
    designs = sorted(
        path for path in designs_root.iterdir()
        if path.is_dir() and (path / f"{path.name}.kicad_pcb").is_file()
    )
    if selected:
        wanted = set(selected)
        designs = [path for path in designs if path.name in wanted]
        missing = wanted - {path.name for path in designs}
        if missing:
            raise ValueError(f"unknown design(s): {', '.join(sorted(missing))}")
    if not designs:
        raise ValueError("no active KiCad PCB designs found")
    return designs


def validate_contract(designs: list[Path]) -> list[str]:
    problems: list[str] = []
    for design in designs:
        required = (
            design / f"{design.name}.kicad_pro",
            design / f"{design.name}.kicad_sch",
            design / f"{design.name}.kicad_pcb",
            design / "README.md",
            design / "VALIDATION.md",
        )
        for path in required:
            if not path.is_file() or path.stat().st_size == 0:
                problems.append(f"{design.name}: missing or empty {path.name}")
    return problems


def phase_plan(root: Path, goal: str, apply: bool, designs: list[Path]) -> list[Phase]:
    scripts = root / ".agents" / "skills" / "kicad-konnect" / "scripts"
    manage = scripts / "manage_manufacturing_outputs.py"
    growth = (
        root / ".agents" / "skills" / "pcb-repository-governance"
        / "scripts" / "check_repository_growth.py"
    )
    selection = tuple(
        item for design in designs for item in ("--design", design.name)
    )
    phases = [Phase("design-contract", cacheable=True)]
    if goal == "manufacturing-refresh" or (goal == "release-ready" and apply):
        phases.append(Phase(
            "manufacturing-export",
            (
                sys.executable, str(manage), "export", "--root", str(root / "Designs"),
                *selection, "--force",
            ),
        ))
    phases.append(Phase(
        "manufacturing-audit",
        (
            sys.executable, str(manage), "audit", "--root", str(root / "Designs"),
            *selection,
        ),
        cacheable=True,
    ))
    if goal == "release-ready":
        phases.extend((
            Phase("diff-check", ("git", "diff", "--check")),
            Phase(
                "repository-growth",
                (sys.executable, str(growth), "--report-worktree"),
            ),
        ))
    return phases


def phase_inputs(root: Path, designs: list[Path], phase: Phase) -> list[Path]:
    paths: list[Path] = []
    if phase.name == "design-contract":
        for design in designs:
            paths.extend((
                design / f"{design.name}.kicad_pro",
                design / f"{design.name}.kicad_sch",
                design / f"{design.name}.kicad_pcb",
                design / "README.md",
                design / "VALIDATION.md",
            ))
        return paths
    scripts = root / ".agents" / "skills" / "kicad-konnect" / "scripts"
    paths.extend(path for path in scripts.glob("*.py") if path.is_file())
    for design in designs:
        for candidate in design.rglob("*"):
            if not candidate.is_file() or any(part in EXCLUDED_DIRS for part in candidate.parts):
                continue
            if candidate.suffix in {".kicad_pro", ".kicad_pcb", ".gtl", ".gbl", ".gm1", ".gm2", ".drl", ".dxf"}:
                paths.append(candidate)
    return paths


def fingerprint(root: Path, designs: list[Path], phase: Phase) -> str:
    digest = hashlib.sha256()
    digest.update(phase.name.encode())
    digest.update(sys.version.encode())
    cli = shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
    cli_path = Path(cli)
    if cli_path.is_file():
        stat = cli_path.stat()
        digest.update(f"{cli_path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    for path in sorted(set(phase_inputs(root, designs, phase))):
        if not path.is_file():
            digest.update(f"missing:{relative(path, root)}".encode())
            continue
        digest.update(relative(path, root).encode())
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def read_cache(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def write_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(cache, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def error_excerpt(stdout: str, stderr: str) -> str:
    source = stderr if stderr.strip() else stdout
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    excerpt = " | ".join(lines[-12:])
    if len(excerpt) > MAX_ERROR_CHARS:
        excerpt = excerpt[-MAX_ERROR_CHARS:]
    return excerpt


def run_phase(phase: Phase, root: Path, log_path: Path) -> dict:
    started = time.monotonic()
    result = subprocess.run(
        phase.command,
        cwd=root,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPYCACHEPREFIX": "/tmp/pcb-workflow-pycache"},
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"COMMAND: {' '.join(phase.command or ())}\n"
        f"EXIT: {result.returncode}\n\nSTDOUT\n{result.stdout}\nSTDERR\n{result.stderr}",
        encoding="utf-8",
    )
    outcome = {
        "name": phase.name,
        "status": "pass" if result.returncode == 0 else "fail",
        "duration_ms": round((time.monotonic() - started) * 1000),
    }
    if result.returncode:
        error = error_excerpt(result.stdout, result.stderr)
        error = error.replace(str(root.resolve()), ".").replace(str(Path.home()), "~")
        outcome["error"] = error
    return outcome


def execute(root: Path, goal: str, designs: list[Path], apply: bool, no_cache: bool) -> dict:
    if goal == "manufacturing-refresh" and not apply:
        raise ValueError("manufacturing-refresh changes generated outputs; pass --apply")
    phases = phase_plan(root, goal, apply, designs)
    work = root / ".work" / "pcb-workflow"
    run_id = time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
    run_dir = work / "runs" / run_id
    cache_path = work / "cache.json"
    cache = read_cache(cache_path)
    outcomes: list[dict] = []

    for phase in phases:
        phase_hash = fingerprint(root, designs, phase)
        if phase.cacheable and not no_cache and cache.get(phase.name) == phase_hash:
            outcomes.append({"name": phase.name, "status": "pass", "cached": True})
            continue
        if phase.command is None:
            problems = validate_contract(designs)
            outcome = {"name": phase.name, "status": "fail" if problems else "pass"}
            if problems:
                outcome["error"] = " | ".join(problems)[:MAX_ERROR_CHARS]
        else:
            outcome = run_phase(phase, root, run_dir / f"{phase.name}.log")
        outcomes.append(outcome)
        if outcome["status"] != "pass":
            break
        if phase.cacheable:
            cache[phase.name] = fingerprint(root, designs, phase)
            write_cache(cache_path, cache)

    status = "pass" if len(outcomes) == len(phases) and all(
        item["status"] == "pass" for item in outcomes
    ) else "fail"
    result = {
        "status": status,
        "goal": goal,
        "designs": [path.name for path in designs],
        "phases": outcomes,
    }
    if run_dir.is_dir():
        result["log_dir"] = relative(run_dir, root)
    return result


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        designs = discover_designs(root, args.design)
        goal = "validate" if args.goal == "plan" else args.goal
        phases = phase_plan(root, goal, args.apply, designs)
        if args.goal == "plan":
            result = {
                "status": "planned",
                "goal": goal,
                "designs": [path.name for path in designs],
                "phases": [phase.name for phase in phases],
                "mutates": any(phase.name == "manufacturing-export" for phase in phases),
            }
        else:
            result = execute(root, args.goal, designs, args.apply, args.no_cache)
    except (OSError, ValueError) as exc:
        result = {"status": "fail", "goal": args.goal, "error": str(exc)[:MAX_ERROR_CHARS]}
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return int(result["status"] == "fail")


if __name__ == "__main__":
    raise SystemExit(main())
