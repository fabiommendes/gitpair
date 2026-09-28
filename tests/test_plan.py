"""Pure unit tests for plan.py helpers that need no host or ssh."""

from __future__ import annotations

from conftest import git

from gitpair.config import HostConfig
from gitpair.hosts import Host
from gitpair.plan import compare_files, origin_env


def test_compare_files_every_name_lands_in_one_bucket_or_matches():
    here = {"a": [1, 100], "b": [2, 200], "same": [3, 300], "only_here": [4, 400]}
    there = {"a": [1, 50], "b": [2, 250], "same": [3, 300], "only_there": [5, 500]}
    to_there, to_here, clashes = compare_files(here, there)
    assert to_there == ["a", "only_here"]
    assert to_here == ["b", "only_there"]
    assert clashes == []


def test_compare_files_same_mtime_different_content_is_a_clash():
    here = {"x": [10, 1000]}
    there = {"x": [20, 1000]}
    to_there, to_here, clashes = compare_files(here, there)
    assert (to_there, to_here, clashes) == ([], [], ["x"])


def test_compare_files_identical_entries_are_skipped():
    here = {"x": [10, 1000]}
    there = {"x": [10, 1000]}
    assert compare_files(here, there) == ([], [], [])


def test_compare_files_missing_on_one_side_always_copies():
    assert compare_files({"a": [1, 1]}, {}) == (["a"], [], [])
    assert compare_files({}, {"a": [1, 1]}) == ([], ["a"], [])


def test_origin_env_keeps_core_ssh_command(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet")
    git(repo, "config", "core.sshCommand", "ssh -i ~/.ssh/id_custom")
    host = Host(HostConfig(name="x", hostname="x", ssh="x", root="~"))
    env = origin_env(host, str(repo))
    assert env["GIT_SSH_COMMAND"] == "ssh -i ~/.ssh/id_custom -o BatchMode=yes"


def test_origin_env_defaults_to_plain_ssh(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet")
    host = Host(HostConfig(name="x", hostname="x", ssh="x", root="~"))
    env = origin_env(host, str(repo))
    assert env["GIT_SSH_COMMAND"] == "ssh -o BatchMode=yes"
