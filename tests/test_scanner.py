"""Unit tests for scanner.find_repos: no subprocess, only the filesystem."""

from __future__ import annotations

import os
from pathlib import Path

from gitpair.scanner import find_repos


def make_repo(path: Path) -> None:
    path.mkdir(parents=True)
    (path / ".git").mkdir()


def test_finds_a_repo_at_the_root(tmp_path: Path):
    make_repo(tmp_path / "app")
    assert list(find_repos(str(tmp_path), 3)) == [str(tmp_path / "app")]


def test_finds_nested_repos_sorted_by_name(tmp_path: Path):
    make_repo(tmp_path / "b")
    make_repo(tmp_path / "a")
    assert list(find_repos(str(tmp_path), 3)) == [
        str(tmp_path / "a"),
        str(tmp_path / "b"),
    ]


def test_depth_limit_stops_the_search(tmp_path: Path):
    make_repo(tmp_path / "one/two/three")
    assert list(find_repos(str(tmp_path), 2)) == []
    assert list(find_repos(str(tmp_path), 3)) == [str(tmp_path / "one/two/three")]


def test_repo_inside_a_repo_is_not_descended_into(tmp_path: Path):
    make_repo(tmp_path / "outer")
    make_repo(tmp_path / "outer/inner")
    assert list(find_repos(str(tmp_path), 5)) == [str(tmp_path / "outer")]


def test_skip_dirs_are_not_searched(tmp_path: Path):
    make_repo(tmp_path / "node_modules/pkg")
    make_repo(tmp_path / "__pycache__/pkg")
    make_repo(tmp_path / "target/pkg")
    make_repo(tmp_path / "dist/pkg")
    make_repo(tmp_path / "build/pkg")
    assert list(find_repos(str(tmp_path), 5)) == []


def test_hidden_directories_are_not_searched(tmp_path: Path):
    make_repo(tmp_path / ".hidden/app")
    assert list(find_repos(str(tmp_path), 5)) == []


def test_symlinked_directory_is_not_followed(tmp_path: Path):
    make_repo(tmp_path / "real")
    (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
    assert list(find_repos(str(tmp_path), 5)) == [str(tmp_path / "real")]


def test_missing_root_yields_nothing(tmp_path: Path):
    assert list(find_repos(str(tmp_path / "missing"), 3)) == []


def test_root_itself_a_repo_is_returned_regardless_of_depth(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    assert list(find_repos(str(tmp_path), 0)) == [str(tmp_path)]


def test_zero_depth_finds_nothing_below_the_root(tmp_path: Path):
    make_repo(tmp_path / "app")
    assert list(find_repos(str(tmp_path), 0)) == []


def test_permission_error_is_swallowed(tmp_path: Path, monkeypatch):
    (tmp_path / "locked").mkdir()

    def raise_permission_error(path):
        raise PermissionError

    monkeypatch.setattr(os, "scandir", raise_permission_error)
    assert list(find_repos(str(tmp_path), 3)) == []
