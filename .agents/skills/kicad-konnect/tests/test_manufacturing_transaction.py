from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "manufacturing_transaction.py"
SPEC = importlib.util.spec_from_file_location("manufacturing_transaction", SCRIPT)
assert SPEC and SPEC.loader
transaction = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transaction)


class ManufacturingTransactionTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[list[dict], dict[str, Path]]:
        packages = []
        generated = {}
        for name in ("Alpha", "Beta"):
            output = root / "published" / name
            output.mkdir(parents=True)
            (output / "payload.txt").write_text(f"old-{name}\n", encoding="utf-8")
            source = root / "generated" / name
            source.mkdir(parents=True)
            (source / "payload.txt").write_text(f"new-{name}\n", encoding="utf-8")
            packages.append({"name": name, "output": output})
            generated[name] = source
        return packages, generated

    def test_success_replaces_complete_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packages, generated = self.fixture(root)
            backup = transaction.replace_directories(
                packages, generated, force=True, stale=[], kind="fixture",
            )
            self.assertIsNotNone(backup)
            for item in packages:
                self.assertEqual(
                    (item["output"] / "payload.txt").read_text(encoding="utf-8"),
                    f"new-{item['name']}\n",
                )
            self.assertFalse(list((root / "published").glob(".*fixture-*")))

    def test_install_failure_restores_entire_old_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packages, generated = self.fixture(root)
            real_rename = transaction._rename
            calls = 0

            def fail_during_second_install(source: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 4:
                    raise OSError("injected interruption")
                real_rename(source, destination)

            with mock.patch.object(transaction, "_rename", side_effect=fail_during_second_install):
                with self.assertRaisesRegex(OSError, "injected interruption"):
                    transaction.replace_directories(
                        packages, generated, force=True, stale=[], kind="fixture",
                    )

            for item in packages:
                self.assertEqual(
                    (item["output"] / "payload.txt").read_text(encoding="utf-8"),
                    f"old-{item['name']}\n",
                )
            self.assertFalse(list((root / "published").glob(".*fixture-*")))


if __name__ == "__main__":
    unittest.main()
