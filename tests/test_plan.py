"""Pure unit tests for plan.py helpers that need no host or ssh."""

from __future__ import annotations

from conftest import git

from gitpair._decide import compare_files
from gitpair.config import HostConfig
from gitpair.hosts import Host
from gitpair.plan import Action, Extra, Item, Step, describe, origin_env


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


def make_item(choice: Action, extras: list[Extra] | None = None) -> Item:
    return Item(
        "app",
        None,
        None,
        status="",
        options=[choice],
        choice=choice,
        extras=extras or [],
    )


def test_describe_with_no_choice_is_a_question_mark():
    item = Item("app", None, None, status="", options=[Action.SKIP])
    assert describe(item, "here", "there") == "?"


def test_describe_names_the_two_hosts():
    item = make_item(Action.PULL)
    assert describe(item, "here", "there") == "fast-forward here from there"


def test_describe_appends_extra_step_descriptions():
    extras = [Extra(Step.FILES_THERE, "copy 1 file to there")]
    item = make_item(Action.KEEP, extras)
    assert (
        describe(item, "here", "there")
        == "commits already in sync + copy 1 file to there"
    )


def test_describe_skip_ignores_extras():
    extras = [Extra(Step.ORIGIN, "push to origin")]
    item = make_item(Action.SKIP, extras)
    assert describe(item, "here", "there") == "skip for now"
