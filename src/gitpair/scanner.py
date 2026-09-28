"""Find git repositories under a root directory and report their state.

Usage: ``scanner.py scan ROOT DEPTH`` or ``scanner.py manifest REPO PATH...``.

This module only uses the standard library: its source is piped to
``python3 -`` on the remote host, so the remote needs nothing but git and
python installed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

__all__ = ["scan", "find_repos", "repo_state", "manifest"]

SKIP_DIRS = {"node_modules", "__pycache__", "target", "dist", "build"}


def scan(root: str, depth: int) -> dict:
    """Find repositories under ``root`` and report their state.

    Returns:
        ``{"root": abs_root, "repos": {rel_path: state}}``.
    """
    root = os.path.abspath(os.path.expanduser(root))
    repos = {}
    for path in find_repos(root, depth):
        repos[os.path.relpath(path, root)] = repo_state(path)
    return {"root": root, "repos": repos}


def find_repos(root: str, depth: int):
    """Yield the path of every git repository found under ``root``.

    A directory is a repository when it has a ``.git`` entry; its
    subdirectories are not searched. Otherwise, hidden directories,
    ``SKIP_DIRS`` and symlinked directories are skipped, and the search
    stops after ``depth`` levels.
    """
    if not os.path.isdir(root):
        return
    if os.path.exists(os.path.join(root, ".git")):
        yield root
        return
    if depth <= 0:
        return
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name)
    except PermissionError:
        return
    for entry in entries:
        if entry.name.startswith(".") or entry.name in SKIP_DIRS:
            continue
        if entry.is_dir(follow_symlinks=False):
            yield from find_repos(entry.path, depth - 1)


def repo_state(path: str) -> dict:
    """Branch, HEAD, dirty/untracked state and ``origin`` URL of one repository."""
    status = _git(path, "status", "--porcelain", "--untracked-files=normal")
    lines = status.splitlines() if status is not None else []
    return {
        "branch": _git(path, "symbolic-ref", "--quiet", "--short", "HEAD"),
        "head": _git(path, "rev-parse", "--verify", "--quiet", "HEAD"),
        "dirty": any(not line.startswith("??") for line in lines),
        "untracked": any(line.startswith("??") for line in lines),
        "origin": _git(path, "remote", "get-url", "origin"),
    }


def manifest(repo: str, entries: list) -> dict:
    """Size and mtime of every regular file under ``entries``.

    Returns:
        ``{rel_path: [size, mtime]}``, relative to ``repo``.
    """
    files: dict = {}
    for entry in entries:
        full = os.path.join(repo, entry)
        if os.path.isfile(full) and not os.path.islink(full):
            _add_file(files, repo, full)
        elif os.path.isdir(full) and not os.path.islink(full):
            for dirpath, _, filenames in os.walk(full):
                for name in filenames:
                    path = os.path.join(dirpath, name)
                    if os.path.isfile(path) and not os.path.islink(path):
                        _add_file(files, repo, path)
    return files


def _add_file(files: dict, repo: str, path: str) -> None:
    info = os.stat(path)
    files[os.path.relpath(path, repo)] = [info.st_size, int(info.st_mtime)]


def _git(path: str, *args: str) -> str | None:
    result = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


if __name__ == "__main__":
    if sys.argv[1] == "manifest":
        json.dump(manifest(sys.argv[2], sys.argv[3:]), sys.stdout)
    else:
        json.dump(scan(sys.argv[2], int(sys.argv[3])), sys.stdout)
