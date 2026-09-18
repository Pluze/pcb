"""Recoverable batch replacement for validated manufacturing directories."""

from __future__ import annotations

import datetime as dt
import os
import shutil
import tempfile
from pathlib import Path


def _rename(source: Path, destination: Path) -> None:
    source.rename(destination)


def replace_directories(
    packages: list[dict],
    generated: dict[str, Path],
    *,
    force: bool,
    stale: list[Path],
    kind: str,
) -> Path | None:
    """Stage every replacement, then install all or roll the batch back."""
    outputs = [item["output"] for item in packages]
    affected = [path for path in outputs if path.exists()] + stale
    if affected and not force:
        raise ValueError("output exists; rerun export with --force after reviewing the audit")

    backup = None
    if affected:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = Path(tempfile.mkdtemp(prefix=f"{kind}-backup-{stamp}-"))
        for index, path in enumerate(affected):
            shutil.copytree(path, backup / f"{index:03d}-{path.name}")

    token = f"{os.getpid()}"
    staged: dict[Path, Path] = {}
    displaced: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for item in packages:
            output = item["output"]
            output.parent.mkdir(parents=True, exist_ok=True)
            stage = output.parent / f".{output.name}.{kind}-new-{token}"
            if stage.exists():
                shutil.rmtree(stage)
            shutil.copytree(generated[item["name"]], stage)
            staged[output] = stage

        for index, path in enumerate(affected):
            rollback = path.parent / f".{path.name}.{kind}-old-{token}-{index}"
            if rollback.exists():
                shutil.rmtree(rollback)
            _rename(path, rollback)
            displaced.append((path, rollback))

        for output, stage in staged.items():
            _rename(stage, output)
            installed.append(output)
    except BaseException:
        for output in reversed(installed):
            if output.exists():
                shutil.rmtree(output)
        for original, rollback in reversed(displaced):
            if rollback.exists():
                _rename(rollback, original)
        for stage in staged.values():
            if stage.exists():
                shutil.rmtree(stage)
        raise

    for _, rollback in displaced:
        shutil.rmtree(rollback)
    return backup
