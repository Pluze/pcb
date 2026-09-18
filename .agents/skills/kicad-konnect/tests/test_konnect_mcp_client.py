from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "konnect_mcp_client.py"
SPEC = importlib.util.spec_from_file_location("konnect_mcp_client", SCRIPT)
assert SPEC and SPEC.loader
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


class KonnectClientSummaryTests(unittest.TestCase):
    def response(self, payload: object, *, failed: bool = False) -> dict:
        return {
            "result": {
                "isError": failed,
                "content": [{"type": "text", "text": json.dumps(payload)}],
            }
        }

    def test_tool_descriptions_collapse_to_names(self) -> None:
        payload = {
            "loaded": ["pcb_board"],
            "tools_added": 2,
            "tools": [
                {"name": "get_board_info", "description": "x" * 2000},
                {"name": "get_board_extents", "description": "y" * 2000},
            ],
        }
        summary = client.summarize_response("load_toolset", self.response(payload))
        self.assertEqual(summary["status"], "pass")
        self.assertEqual(
            summary["payload"]["tools"],
            {"count": 2, "names": ["get_board_info", "get_board_extents"]},
        )

    def test_large_lists_and_strings_are_bounded(self) -> None:
        payload = {"items": [{"message": "z" * 2000, "index": i} for i in range(40)]}
        summary = client.summarize_response("query_traces", self.response(payload))
        items = summary["payload"]["items"]
        self.assertEqual(items["count"], 40)
        self.assertEqual(items["omitted"], 28)
        self.assertIn("chars omitted", items["items"][0]["message"])

    def test_failure_identity_survives_summary(self) -> None:
        payload = {"error": {"kind": "handler_error", "reason": "IPC unavailable"}}
        summary = client.summarize_response("score_placement", self.response(payload, failed=True))
        self.assertEqual(summary["status"], "fail")
        self.assertEqual(summary["payload"]["error"]["kind"], "handler_error")

    def test_full_response_log_preserves_unabridged_payload(self) -> None:
        response = self.response({"message": "m" * 4000})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "details.json"
            written = client.write_details_log([response], ["example"], path)
            text = written.read_text(encoding="utf-8")
            self.assertIn("m" * 4000, text)
            self.assertIn('"name": "example"', text)

    def test_unique_live_ipc_socket_is_discovered_without_agent_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api-123.sock"
            path.touch()
            with mock.patch.object(Path, "is_socket", return_value=True):
                self.assertEqual(
                    client.discover_ipc_socket({}, [Path(directory)]),
                    f"ipc://{path.resolve()}",
                )

    def test_explicit_ipc_socket_wins_and_ambiguity_is_not_guessed(self) -> None:
        self.assertEqual(
            client.discover_ipc_socket({"KICAD_API_SOCKET": "ipc:///chosen"}, []),
            "ipc:///chosen",
        )
        with tempfile.TemporaryDirectory() as directory:
            for index in range(2):
                (Path(directory) / f"api-{index}.sock").touch()
            with mock.patch.object(Path, "is_socket", return_value=True):
                self.assertIsNone(client.discover_ipc_socket({}, [Path(directory)]))


if __name__ == "__main__":
    unittest.main()
