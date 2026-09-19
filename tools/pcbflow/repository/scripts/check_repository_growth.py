#!/usr/bin/env python3
"""Reject repository content that would create opaque or excessive Git history."""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys


MAX_GIT_BLOB = 5 * 1024 * 1024
MAX_IMAGE_BLOB = 2 * 1024 * 1024
MAX_UNTRACKED_BYTES = 25 * 1024 * 1024
MAX_IGNORED_BYTES = 50 * 1024 * 1024
MAX_UNTRACKED_FILES = 500
MAX_IGNORED_FILES = 2000

IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
DOCUMENT_EXTENSIONS = {".pdf"}
PROHIBITED_EXTENSIONS = {
    ".7z", ".avi", ".doc", ".docx", ".gz", ".mkv", ".mov", ".mp4",
    ".ppt", ".pptx", ".rar", ".tar", ".tgz", ".xls", ".xlsx", ".zip",
}
PROHIBITED_NAMES = {".DS_Store", "Thumbs.db"}
PROHIBITED_PARTS = {".history", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
PROHIBITED_SUFFIXES = {
    ".kicad_prl", ".kicad_pro-bak", ".kicad_sch-bak", ".kicad_pcb-bak",
    ".pyc", ".pyo", ".lck", ".dsn", ".ses",
}


def git(*args: str, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", *args], input=input_bytes, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        sys.stderr.write(result.stderr.decode("utf-8", "replace"))
        raise SystemExit(result.returncode)
    return result.stdout


def split_z(data: bytes) -> list[str]:
    return [item.decode("utf-8", "surrogateescape") for item in data.split(b"\0") if item]


def staged_paths() -> list[str]:
    return split_z(git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"))


def tracked_paths() -> list[str]:
    return split_z(git("ls-files", "-z"))


def index_blob(path: str) -> tuple[int, bytes]:
    spec = f":{path}"
    size = int(git("cat-file", "-s", spec).strip())
    prefix = git("cat-file", "blob", spec)[:200] if size <= MAX_GIT_BLOB else b""
    return size, prefix


def is_lfs_pointer(data: bytes) -> bool:
    return data.startswith(b"version https://git-lfs.github.com/spec/v1\n")


def asset_path_allowed(path: PurePosixPath) -> bool:
    parts = path.parts
    return len(parts) >= 4 and parts[0] == "Designs" and "assets" in parts[2:-1]


def path_errors(path_text: str, size: int, prefix: bytes) -> list[str]:
    path = PurePosixPath(path_text)
    suffix = path.suffix.lower()
    errors: list[str] = []
    if path.name in PROHIBITED_NAMES:
        errors.append("OS metadata is not versionable")
    if any(part in PROHIBITED_PARTS for part in path.parts):
        errors.append("cache or local-history path is prohibited")
    if path.name.endswith("-backups") or suffix in PROHIBITED_SUFFIXES:
        errors.append("backup, lock, router exchange, or interpreter cache is prohibited")
    if suffix in PROHIBITED_EXTENSIONS:
        errors.append("archive, office container, or video belongs outside ordinary Git")
    if suffix in IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS and not asset_path_allowed(path):
        errors.append("reader-facing image/PDF must be under Designs/<name>/assets/")
    if suffix in IMAGE_EXTENSIONS and size > MAX_IMAGE_BLOB and not is_lfs_pointer(prefix):
        errors.append(f"image exceeds {MAX_IMAGE_BLOB // (1024 * 1024)} MiB")
    if size > MAX_GIT_BLOB and not is_lfs_pointer(prefix):
        errors.append(f"blob exceeds {MAX_GIT_BLOB // (1024 * 1024)} MiB")
    return errors


def check_index(paths: list[str]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        size, prefix = index_blob(path)
        for reason in path_errors(path, size, prefix):
            failures.append(f"{path}: {reason} ({size} bytes)")
    return failures


def history_errors() -> list[str]:
    objects = git("rev-list", "--objects", "--all")
    records = git(
        "cat-file", "--batch-check=%(objecttype) %(objectsize) %(rest)",
        input_bytes=objects,
    ).decode("utf-8", "surrogateescape")
    failures: list[str] = []
    for record in records.splitlines():
        fields = record.split(" ", 2)
        if len(fields) != 3 or fields[0] != "blob":
            continue
        size = int(fields[1])
        path = fields[2]
        if size > MAX_GIT_BLOB:
            failures.append(f"history: {path}: blob exceeds {MAX_GIT_BLOB // (1024 * 1024)} MiB ({size} bytes)")
    return failures


def file_totals(paths: list[str]) -> tuple[int, int]:
    total = 0
    existing = 0
    for path_text in paths:
        path = Path(path_text)
        if path.is_file() and not path.is_symlink():
            existing += 1
            total += path.stat().st_size
    return existing, total


def report_worktree() -> list[str]:
    untracked = split_z(git("ls-files", "--others", "--exclude-standard", "-z"))
    ignored = split_z(git("ls-files", "--others", "--ignored", "--exclude-standard", "-z"))
    untracked_count, untracked_size = file_totals(untracked)
    ignored_count, ignored_size = file_totals(ignored)
    print(f"untracked: {untracked_count} files, {untracked_size} bytes")
    print(f"ignored: {ignored_count} files, {ignored_size} bytes")

    failures: list[str] = []
    if untracked_count > MAX_UNTRACKED_FILES or untracked_size > MAX_UNTRACKED_BYTES:
        failures.append(
            f"untracked workspace growth exceeds {MAX_UNTRACKED_FILES} files or "
            f"{MAX_UNTRACKED_BYTES // (1024 * 1024)} MiB"
        )
    if ignored_count > MAX_IGNORED_FILES or ignored_size > MAX_IGNORED_BYTES:
        failures.append(
            f"ignored workspace growth exceeds {MAX_IGNORED_FILES} files or "
            f"{MAX_IGNORED_BYTES // (1024 * 1024)} MiB"
        )
    root = Path.cwd().resolve()
    for current, dirs, _files in os.walk(root):
        current_path = Path(current)
        if current_path == root / ".git":
            dirs[:] = []
            continue
        for name in list(dirs):
            candidate = current_path / name
            relative = candidate.relative_to(root).as_posix()
            if name == ".history":
                failures.append(f"{relative}: local-history directory must be removed")
            if name == ".git" and candidate != root / ".git":
                failures.append(f"{relative}: nested Git repository is prohibited")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-tracked", action="store_true", help="check the complete current index")
    parser.add_argument("--history", action="store_true", help="check every reachable historical blob")
    parser.add_argument("--report-worktree", action="store_true", help="report untracked/ignored growth and forbidden directories")
    args = parser.parse_args()

    paths = tracked_paths() if args.all_tracked else staged_paths()
    failures = check_index(paths)
    if args.history:
        failures.extend(history_errors())
    if args.report_worktree:
        failures.extend(report_worktree())

    print(f"checked: {len(paths)} {'tracked' if args.all_tracked else 'staged'} paths")
    if failures:
        print("repository growth check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("repository growth check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
