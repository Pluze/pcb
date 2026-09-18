#!/usr/bin/env python3
"""Efficient JSONL client for a locally installed Konnect MCP server.

The client keeps one Konnect process alive for an entire workflow, can inject a
default board path from tool schemas, and fails predictably in strict mode.
"""

import argparse
import glob
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time
from typing import Any, Optional


META_TOOLS = {
    "load_toolset",
    "list_toolboxes",
    "load_user_config",
    "save_user_config",
}

SUMMARY_LIST_ITEMS = 12
SUMMARY_STRING_CHARS = 480
SUMMARY_DICT_ITEMS = 30


def find_konnect() -> str:
    configured = os.environ.get("KONNECT_BIN")
    if configured and Path(configured).is_file():
        return configured

    pattern = str(
        Path.home()
        / "Documents/KiCad/*/3rdparty/plugins/com_github_mixelpixx_konnect/bin/konnect"
    )
    matches = sorted(glob.glob(pattern), reverse=True)
    if matches:
        return matches[0]
    raise SystemExit("Konnect not found; set KONNECT_BIN to its executable path")


def discover_board(explicit: Optional[str]) -> Optional[str]:
    candidate = explicit or os.environ.get("KONNECT_BOARD")
    if candidate:
        path = Path(candidate).expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"Board does not exist: {path}")
        return str(path)

    cwd = Path.cwd()
    project_stems = {path.stem for path in cwd.glob("*.kicad_pro")}
    project_boards = [cwd / f"{stem}.kicad_pcb" for stem in project_stems]
    project_boards = [path for path in project_boards if path.is_file()]
    boards = project_boards or list(cwd.glob("*.kicad_pcb"))
    if len(boards) == 1:
        return str(boards[0].resolve())
    return None


def discover_ipc_socket(
    environment: dict[str, str], roots: Optional[list[Path]] = None
) -> Optional[str]:
    explicit = environment.get("KICAD_API_SOCKET")
    if explicit:
        return explicit
    search_roots = roots or [Path("/tmp/kicad"), Path("/private/tmp/kicad")]
    candidates: dict[str, Path] = {}
    for root in search_roots:
        for pattern in ("api.sock", "api-*.sock"):
            for path in root.glob(pattern):
                if path.is_socket():
                    resolved = path.resolve()
                    candidates[str(resolved)] = resolved
    if len(candidates) != 1:
        return None
    return f"ipc://{next(iter(candidates.values()))}"


def send(proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def receive(proc: subprocess.Popen[str], wanted_id: int, timeout: int) -> dict[str, Any]:
    assert proc.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events = selector.select(max(0, deadline - time.monotonic()))
        if not events:
            break
        line = proc.stdout.readline()
        if not line:
            break
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("id") == wanted_id:
            return data
    raise TimeoutError(f"No MCP response for id {wanted_id} within {timeout}s")


def request(
    proc: subprocess.Popen[str], request_id: int, method: str, params: dict[str, Any], timeout: int
) -> dict[str, Any]:
    send(
        proc,
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
    )
    return receive(proc, request_id, timeout)


def tool_schemas(proc: subprocess.Popen[str], request_id: int, timeout: int) -> dict[str, dict[str, Any]]:
    response = request(proc, request_id, "tools/list", {}, timeout)
    tools = response.get("result", {}).get("tools", [])
    return {tool["name"]: tool.get("inputSchema", {}) for tool in tools if "name" in tool}


def schema_accepts_board(schema: dict[str, Any]) -> bool:
    return "board" in schema.get("properties", {})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", help="Default .kicad_pcb path injected when a tool accepts board")
    parser.add_argument("--timeout", type=int, default=120, help="Per-request timeout in seconds")
    parser.add_argument("--startup-retries", type=int, default=2, help="Initialization attempts")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print complete tool payloads instead of the default bounded summary",
    )
    parser.add_argument("--details", type=Path, help="Full-response log path for default summary output")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when any tool reports an error")
    parser.add_argument(
        "--toolset",
        action="append",
        default=[],
        help="Load this toolset before listing schemas (repeatable; useful with the list action)",
    )
    parser.add_argument("action", choices=("list", "call", "callseq"))
    parser.add_argument("remainder", nargs="*")
    return parser.parse_args()


def build_steps(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.action == "list":
        if args.remainder:
            raise SystemExit("list takes no additional arguments")
        return [{"name": "$list"}]
    if args.action == "call":
        if not args.remainder:
            raise SystemExit("call requires TOOL [JSON_ARGS]")
        arguments = json.loads(args.remainder[1]) if len(args.remainder) > 1 else {}
        return [{"name": args.remainder[0], "arguments": arguments}]
    if len(args.remainder) != 1:
        raise SystemExit("callseq requires one JSON_STEPS array")
    steps = json.loads(args.remainder[0])
    if not isinstance(steps, list):
        raise SystemExit("callseq JSON must be an array")
    return steps


def start_process(timeout: int, retries: int) -> tuple[subprocess.Popen[str], dict[str, Any]]:
    last_error: Optional[Exception] = None
    for attempt in range(max(1, retries)):
        env = os.environ.copy()
        env["TMPDIR"] = "/tmp"
        if ipc_socket := discover_ipc_socket(env):
            env["KICAD_API_SOCKET"] = ipc_socket
        proc = subprocess.Popen(
            [find_konnect(), "--client", "codex"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
            env=env,
            cwd=os.getcwd(),
        )
        try:
            initialized = request(
                proc,
                1,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "codex", "version": "1.1"},
                },
                timeout,
            )
            send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
            return proc, initialized
        except (BrokenPipeError, TimeoutError, OSError) as error:
            last_error = error
            proc.kill()
            proc.wait()
            if attempt + 1 < max(1, retries):
                time.sleep(0.25 * (attempt + 1))
    raise SystemExit(f"Unable to initialize Konnect: {last_error}")


def content_payload(response: dict[str, Any]) -> Any:
    if "error" in response:
        return {"error": response["error"]}
    content = response.get("result", {}).get("content", [])
    values: list[Any] = []
    for item in content:
        value: Any = item.get("text", item)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
        values.append(value)
    if len(values) == 1:
        return values[0]
    return values


def response_failed(response: dict[str, Any]) -> bool:
    return "error" in response or bool(response.get("result", {}).get("isError"))


def summarize_value(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Return a bounded, decision-oriented representation of an MCP payload."""
    if isinstance(value, str):
        if len(value) <= SUMMARY_STRING_CHARS:
            return value
        omitted = len(value) - SUMMARY_STRING_CHARS
        return f"{value[:SUMMARY_STRING_CHARS]}... [{omitted} chars omitted]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if depth >= 5:
        if isinstance(value, (list, dict)):
            return {"type": type(value).__name__, "count": len(value), "omitted": True}
        return str(value)
    if isinstance(value, list):
        if key == "tools" and all(isinstance(item, dict) and "name" in item for item in value):
            names = [item["name"] for item in value]
            return {"count": len(names), "names": names}
        items = [summarize_value(item, depth=depth + 1) for item in value[:SUMMARY_LIST_ITEMS]]
        if len(value) <= SUMMARY_LIST_ITEMS:
            return items
        return {"count": len(value), "items": items, "omitted": len(value) - len(items)}
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        entries = list(value.items())
        for child_key, child_value in entries[:SUMMARY_DICT_ITEMS]:
            result[str(child_key)] = summarize_value(
                child_value,
                key=str(child_key),
                depth=depth + 1,
            )
        if len(entries) > SUMMARY_DICT_ITEMS:
            result["_omitted_keys"] = len(entries) - SUMMARY_DICT_ITEMS
        return result
    return str(value)


def summarize_response(name: str, response: dict[str, Any]) -> dict[str, Any]:
    status = "fail" if response_failed(response) else "pass"
    if name == "$list":
        tools = response.get("result", {}).get("tools", [])
        return {
            "name": "list_tools",
            "status": status,
            "tool_count": len(tools),
            "tools": [
                {
                    "name": tool.get("name"),
                    "required": tool.get("inputSchema", {}).get("required", []),
                }
                for tool in tools
            ],
        }
    return {
        "name": name,
        "status": status,
        "payload": summarize_value(content_payload(response)),
    }


def write_details_log(
    responses: list[dict[str, Any]], response_names: list[str], requested: Optional[Path]
) -> Path:
    if requested:
        path = requested.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        descriptor, raw_path = tempfile.mkstemp(prefix="konnect-mcp-details-", suffix=".json")
        os.close(descriptor)
        path = Path(raw_path)
    document = {
        "responses": [
            {"name": name, "response": response}
            for name, response in zip(response_names, responses)
        ]
    }
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    steps = build_steps(args)
    board = discover_board(args.board)
    proc, _initialized = start_process(args.timeout, args.startup_retries)
    responses: list[dict[str, Any]] = []
    response_names: list[str] = []
    schemas: dict[str, dict[str, Any]] = {}
    next_id = 2
    failed = False

    try:
        if args.toolset:
            response = request(
                proc,
                next_id,
                "tools/call",
                {"name": "load_toolset", "arguments": {"name": args.toolset}},
                args.timeout,
            )
            next_id += 1
            responses.append(response)
            response_names.append("load_toolset")
            failed = failed or response_failed(response)
        for step in steps:
            name = step["name"]
            if name == "$list":
                response = request(proc, next_id, "tools/list", {}, args.timeout)
                next_id += 1
            else:
                arguments = dict(step.get("arguments", {}))
                if board and name not in META_TOOLS:
                    schema = schemas.get(name)
                    if schema and schema_accepts_board(schema):
                        arguments.setdefault("board", board)
                response = request(
                    proc,
                    next_id,
                    "tools/call",
                    {"name": name, "arguments": arguments},
                    args.timeout,
                )
                next_id += 1

                if name == "load_toolset" and not response_failed(response):
                    schemas.update(tool_schemas(proc, next_id, args.timeout))
                    next_id += 1

            responses.append(response)
            response_names.append(name)
            failed = failed or response_failed(response)

        if not args.raw:
            details = write_details_log(responses, response_names, args.details)
            result = {
                "status": "fail" if failed else "pass",
                "steps": [
                    summarize_response(name, response)
                    for name, response in zip(response_names, responses)
                ],
                "details": str(details),
            }
            print(json.dumps(result, separators=(",", ":")))
        else:
            print(json.dumps([content_payload(item) for item in responses], indent=2))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

    if args.strict and failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
