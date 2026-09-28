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

    A directory is a repository when its ``.git`` entry is a regular file
    (a worktree or submodule's gitdir pointer) or a directory that contains
    a ``HEAD`` file. Either way, its subdirectories are not searched: a
    ``.git`` directory missing ``HEAD`` is not a repository either, and is
    not descended into, so a broken repository is never silently replaced
    by whatever real repositories happen to be nested under it. Otherwise,
    hidden directories, ``SKIP_DIRS`` and symlinked directories are
    skipped, and the search stops after ``depth`` levels.
    """
    if not os.path.isdir(root):
        return
    git_path = os.path.join(root, ".git")
    if os.path.isfile(git_path):
        yield root
        return
    if os.path.isdir(git_path):
        if os.path.isfile(os.path.join(git_path, "HEAD")):
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
    """Branch, HEAD, dirty/untracked state, ``origin`` URL and error of one repository.

    Distinguishes a repository with no commit yet (an unborn branch: HEAD is
    a valid symbolic ref, but ``rev-parse HEAD`` has nothing to resolve) from
    one where git itself does not work (``rev-parse --git-dir`` or
    ``status`` exits non-zero, e.g. a ``.git`` directory missing its
    content). The former reports ``head=None`` with ``error=None``; the
    latter reports every other field at its empty default and ``error`` set
    to the first line of git's stderr.
    """
    git_dir, error = _git_checked(path, "rev-parse", "--git-dir")
    if error is not None:
        return _error_state(error)
    status, error = _git_checked(
        path, "status", "--porcelain", "--untracked-files=normal"
    )
    if error is not None:
        return _error_state(error)
    lines = status.splitlines() if status else []
    return {
        "branch": _git(path, "symbolic-ref", "--quiet", "--short", "HEAD"),
        "head": _git(path, "rev-parse", "--verify", "--quiet", "HEAD"),
        "dirty": any(not line.startswith("??") for line in lines),
        "untracked": any(line.startswith("??") for line in lines),
        "origin": _git(path, "remote", "get-url", "origin"),
        "error": None,
    }


def _error_state(error: str) -> dict:
    return {
        "branch": None,
        "head": None,
        "dirty": False,
        "untracked": False,
        "origin": None,
        "error": error,
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


def _git_checked(path: str, *args: str) -> tuple[str | None, str | None]:
    """Like ``_git``, but returns ``(None, first stderr line)`` on failure."""
    result = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True)
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout).strip()
        return None, stderr.splitlines()[0] if stderr else ""
    return result.stdout.strip(), None


if __name__ == "__main__":
    if sys.argv[1] == "manifest":
        json.dump(manifest(sys.argv[2], sys.argv[3:]), sys.stdout)
    else:
        json.dump(scan(sys.argv[2], int(sys.argv[3])), sys.stdout)
