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
GOALS = ("schematic-validate", "validate", "manufacturing-refresh", "release-ready")
MAX_ERROR_CHARS = 1200
MANUFACTURING_AUDIT_SCRIPTS = (
    "pcb_workflow.py",
    "manage_manufacturing_outputs.py",
    "manufacturing_discovery.py",
    "manufacturing_transaction.py",
    "export_circuitpro_u4_packages.py",
    "export_kapton_lightburn_templates.py",
    "validate_circuitpro_u4_package.py",
)


@dataclass(frozen=True)
class Phase:
    name: str
    command: tuple[str, ...] | None = None
    cacheable: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("goal", choices=("plan", *GOALS))
    parser.add_argument("--for-goal", choices=GOALS, default="validate")
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


def topology_designs(designs: list[Path], explicitly_selected: bool) -> list[Path]:
    selected = [design for design in designs if (design / "schematic_topology.json").is_file()]
    if explicitly_selected and len(selected) != len(designs):
        missing = sorted(design.name for design in designs if design not in selected)
        raise ValueError(
            "schematic-validate requires schematic_topology.json: " + ", ".join(missing)
        )
    if not selected:
        raise ValueError("no topology-driven schematic designs found")
    return selected


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
    if goal == "schematic-validate":
        evidence = root / ".work" / "pcb-workflow" / "schematic"
        router = scripts / "schematic_topology_router.py"
        validator = scripts / "validate_schematic_design.py"
        for design in designs:
            topology = design / "schematic_topology.json"
            phases.extend((
                Phase(
                    f"schematic-route-plan-{design.name}",
                    (
                        sys.executable, str(router), str(topology),
                        "--plan", str(evidence / f"{design.name}-route-plan.json"),
                    ),
                ),
                Phase(
                    f"schematic-validation-{design.name}",
                    (
                        sys.executable, str(validator), str(topology),
                        "--report", str(evidence / f"{design.name}-validation.json"),
                        "--render", str(evidence / f"{design.name}-schematic.png"),
                    ),
                ),
            ))
        return phases
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
    scripts = root / ".agents" / "skills" / "kicad-konnect" / "scripts"
    if phase.name == "design-contract":
        paths.append(scripts / "pcb_workflow.py")
        for design in designs:
            paths.extend((
                design / f"{design.name}.kicad_pro",
                design / f"{design.name}.kicad_sch",
                design / f"{design.name}.kicad_pcb",
                design / "README.md",
                design / "VALIDATION.md",
            ))
        return paths
    if phase.name == "manufacturing-audit":
        paths.extend(scripts / name for name in MANUFACTURING_AUDIT_SCRIPTS)
    else:
        return paths
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


def cache_key(phase: Phase, designs: list[Path]) -> str:
    scope = ",".join(path.name for path in designs)
    return f"{phase.name}:{scope}"


def error_excerpt(stdout: str, stderr: str) -> str:
    source = stderr if stderr.strip() else stdout
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    excerpt = " | ".join(lines[-12:])
    if len(excerpt) > MAX_ERROR_CHARS:
        excerpt = excerpt[-MAX_ERROR_CHARS:]
    return excerpt


def is_silent_kicad_abort(returncode: int, stdout: str, stderr: str) -> bool:
    message = f"{stdout}\n{stderr}".lower()
    return (
        ("kicad-cli" in message and "no diagnostic output" in message)
        or (returncode in (134, -6) and not stdout.strip() and not stderr.strip())
    )


def classify_failure(returncode: int, stdout: str, stderr: str) -> tuple[str, str]:
    """Classify only stable failure signatures with an actionable next step."""
    message = f"{stdout}\n{stderr}".lower()
    if "no kicad ipc socket found" in message or "ipc_socket_path" in message:
        return "ipc-unavailable", "configure/open the intended KiCad IPC project or use a file-backed operation"
    if "lock file" in message or "cannot lock" in message or "already open" in message:
        return "editor-lock", "close the owning KiCad editor before file-backed mutation"
    if is_silent_kicad_abort(returncode, stdout, stderr):
        return "execution-environment", "rerun the absolute KiCad CLI command in the permitted execution context"
    if any(signature in message for signature in (
        "operation not permitted", "permission denied", "sandbox",
    )):
        return "execution-environment", "rerun the command in the permitted execution context"
    if any(signature in message for signature in (
        "no such file or directory", "command not found", "kicad-cli not found",
    )):
        return "missing-input", "verify the resolved executable and input paths"
    if "violation" in message or "drc" in message or "erc" in message:
        return "validation", "inspect the validator report and fix the design evidence"
    return "command", "inspect the phase log before changing a retry precondition"


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
        failure_class, next_action = classify_failure(
            result.returncode, result.stdout, result.stderr,
        )
        if is_silent_kicad_abort(result.returncode, result.stdout, result.stderr):
            error = "kicad-cli aborted without diagnostic output"
        elif not error:
            error = f"command exited {result.returncode} without diagnostic output"
        error = error.replace(str(root.resolve()), ".").replace(str(Path.home()), "~")
        outcome["error"] = error
        outcome["failure_class"] = failure_class
        outcome["next_action"] = next_action
    return outcome


def execute(root: Path, goal: str, designs: list[Path], apply: bool, no_cache: bool) -> dict:
    if goal == "manufacturing-refresh" and not apply:
        raise ValueError("manufacturing-refresh changes generated outputs; pass --apply")
    work = root / ".work" / "pcb-workflow"
    if goal == "schematic-validate":
        (work / "schematic").mkdir(parents=True, exist_ok=True)
    phases = phase_plan(root, goal, apply, designs)
    run_id = time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
    run_dir = work / "runs" / run_id
    cache_path = work / "cache.json"
    cache = read_cache(cache_path)
    outcomes: list[dict] = []

    for phase in phases:
        phase_key = cache_key(phase, designs) if phase.cacheable else None
        if phase.cacheable:
            phase_hash = fingerprint(root, designs, phase)
            if not no_cache and cache.get(phase_key) == phase_hash:
                outcomes.append({"name": phase.name, "status": "pass", "cached": True})
                continue
        if phase.command is None:
            problems = validate_contract(designs)
            outcome = {"name": phase.name, "status": "fail" if problems else "pass"}
            if problems:
                outcome["error"] = " | ".join(problems)[:MAX_ERROR_CHARS]
        else:
            safe_name = phase.name.replace(":", "-").replace("/", "-")
            outcome = run_phase(phase, root, run_dir / f"{safe_name}.log")
        outcomes.append(outcome)
        if outcome["status"] != "pass":
            break
        if phase.cacheable:
            assert phase_key is not None
            cache[phase_key] = fingerprint(root, designs, phase)
            write_cache(cache_path, cache)

    status = "pass" if len(outcomes) == len(phases) and all(
        item["status"] == "pass" for item in outcomes
    ) else "fail"
    details = {
        "status": status,
        "goal": goal,
        "designs": [path.name for path in designs],
        "phases": outcomes,
    }
    if run_dir.is_dir():
        (run_dir / "summary.json").write_text(
            json.dumps(details, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    result = {
        "status": status,
        "goal": goal,
        "designs": [path.name for path in designs],
        "phases": {
            item["name"]: "cached" if item.get("cached") else item["status"]
            for item in outcomes
        },
    }
    if status == "fail" and outcomes:
        failed = outcomes[-1]
        result["failed_phase"] = failed["name"]
        if "error" in failed:
            result["error"] = failed["error"]
        if "failure_class" in failed:
            result["failure_class"] = failed["failure_class"]
            result["next_action"] = failed["next_action"]
    if status == "fail" and run_dir.is_dir():
        result["log_dir"] = relative(run_dir, root)
    return result


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        designs = discover_designs(root, args.design)
        goal = args.for_goal if args.goal == "plan" else args.goal
        if goal == "schematic-validate":
            designs = topology_designs(designs, bool(args.design))
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
