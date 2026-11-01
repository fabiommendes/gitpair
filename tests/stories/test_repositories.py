"""Stories: cloning, tracking and ignoring repositories."""

from __future__ import annotations

import tomllib

import pytest
from conftest import World, commit, git

from gitpair import session
from gitpair.plan import Action, Item, Plan


def only(plan: Plan) -> Item:
    assert len(plan.pending) == 1, plan.pending
    return plan.pending[0]


def run(world: World, plan: Plan) -> session.Outcome:
    assert world.loaded is not None
    outcome = session.run(world.loaded, plan)
    assert not outcome.failed, outcome.failed
    return outcome


@pytest.mark.story("user: Clone a repository missing on one machine")
def test_tracked_repo_missing_on_remote_is_cloned_there(world: World):
    world.track.append("group/app")
    repo = world.here / "group/app"
    repo.mkdir(parents=True)
    git(repo, "init", "--quiet", "--initial-branch=trunk")
    git(repo, "remote", "add", "origin", "git@example.com:me/app.git")
    head = commit(repo, "README")

    plan = world.plan()
    assert only(plan).choice is Action.CLONE_THERE
    run(world, plan)

    clone = world.there / "group/app"
    assert git(clone, "rev-parse", "HEAD") == head
    assert git(clone, "symbolic-ref", "--short", "HEAD") == "trunk"
    assert git(clone, "status", "--porcelain") == ""
    assert git(clone, "remote", "get-url", "origin") == "git@example.com:me/app.git"


@pytest.mark.story("user: Clone a repository missing on one machine")
def test_tracked_repo_missing_locally_is_cloned_here(world: World):
    world.track.append("app")
    repo = world.there / "app"
    repo.mkdir()
    git(repo, "init", "--quiet", "--initial-branch=main")
    head = commit(repo, "README")

    plan = world.plan()
    assert only(plan).choice is Action.CLONE_HERE
    run(world, plan)

    clone = world.here / "app"
    assert git(clone, "rev-parse", "HEAD") == head
    assert git(clone, "remote") == ""


@pytest.mark.story("user: Track or ignore a new repository")
def test_new_repo_asks_and_is_tracked_after_sync(world: World):
    world.repo("app")
    commit(world.there / "app", "new.txt")

    plan = world.plan()
    item = only(plan)
    assert item.new and item.needs_decision
    assert item.options == [Action.PULL, Action.IGNORE, Action.SKIP]

    item.choice = Action.PULL
    outcome = run(world, plan)
    assert outcome.config_note == "config updated: 1 tracked, 0 ignored on both hosts"
    for home in ("home-here", "home-there"):
        path = world.tmp / home / ".config/gitpair/config.toml"
        assert tomllib.loads(path.read_text())["repos"]["track"] == ["app"]


@pytest.mark.story("user: Track or ignore a new repository")
def test_new_repo_can_be_ignored(world: World):
    world.repo("app")
    plan = world.plan()
    item = only(plan)
    assert item.options == [Action.TRACK, Action.IGNORE, Action.SKIP]

    item.choice = Action.IGNORE
    run(world, plan)
    assert world.plan().items == []
