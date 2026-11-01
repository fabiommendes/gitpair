"""Stories: syncing commits between the two hosts."""

from __future__ import annotations

import pytest
from conftest import World, commit, git

from gitpair import session
from gitpair.plan import Action, Item, Plan
from gitpair.tui import PlanApp


def only(plan: Plan) -> Item:
    assert len(plan.pending) == 1, plan.pending
    return plan.pending[0]


def run(world: World, plan: Plan) -> session.Outcome:
    assert world.loaded is not None
    outcome = session.run(world.loaded, plan)
    assert not outcome.failed, outcome.failed
    return outcome


@pytest.mark.story("user: Get the other machine's new commits")
def test_local_behind_is_pulled_automatically(world: World):
    world.track.append("app")
    world.repo("app")
    head = commit(world.there / "app", "new.txt")

    plan = world.plan()
    item = only(plan)
    assert item.choice is Action.PULL
    assert item.status == "behind by 1"

    run(world, plan)
    assert git(world.here / "app", "rev-parse", "HEAD") == head
    assert (world.here / "app/new.txt").exists()


@pytest.mark.story("user: Send my new commits to the other machine")
def test_local_ahead_is_pushed_into_checked_out_branch(world: World):
    world.track.append("app")
    world.repo("app")
    head = commit(world.here / "app", "new.txt")

    plan = world.plan()
    assert only(plan).choice is Action.PUSH

    run(world, plan)
    remote = world.there / "app"
    assert git(remote, "rev-parse", "HEAD") == head
    assert (remote / "new.txt").exists()
    assert git(remote, "status", "--porcelain") == ""
    assert git(remote, "for-each-ref", "refs/gitpair/incoming") == ""


@pytest.mark.story("user: Keep a dirty work tree safe")
def test_dirty_work_tree_asks(world: World):
    world.track.append("app")
    world.repo("app")
    commit(world.here / "app", "new.txt")
    (world.there / "app/README").write_text("local edit")

    item = only(world.plan())
    assert item.needs_decision
    assert item.options == [Action.PUSH, Action.SKIP]
    assert "dirty on there" in item.status


@pytest.mark.story("user: Resolve diverged branches")
def test_diverged_branches_ask_and_can_merge(world: World):
    world.track.append("app")
    world.repo("app")
    commit(world.here / "app", "a.txt")
    commit(world.there / "app", "b.txt")

    plan = world.plan()
    item = only(plan)
    assert item.needs_decision
    assert item.options == [
        Action.MERGE, Action.TAKE_REMOTE, Action.TAKE_LOCAL, Action.SKIP,
    ]  # fmt: skip

    item.choice = Action.MERGE
    run(world, plan)
    here, there = world.here / "app", world.there / "app"
    assert git(here, "rev-parse", "HEAD") == git(there, "rev-parse", "HEAD")
    assert (there / "a.txt").exists() and (there / "b.txt").exists()


@pytest.mark.story("user: Resolve diverged branches")
def test_take_remote_keeps_a_backup(world: World):
    world.track.append("app")
    world.repo("app")
    mine = commit(world.here / "app", "a.txt")
    theirs = commit(world.there / "app", "b.txt")

    plan = world.plan()
    only(plan).choice = Action.TAKE_REMOTE
    run(world, plan)
    here = world.here / "app"
    assert git(here, "rev-parse", "HEAD") == theirs
    assert git(here, "rev-parse", "refs/gitpair/backup/main") == mine


@pytest.mark.story("user: Resolve diverged branches")
def test_take_local_resets_remote(world: World):
    world.track.append("app")
    world.repo("app")
    mine = commit(world.here / "app", "a.txt")
    theirs = commit(world.there / "app", "b.txt")

    plan = world.plan()
    only(plan).choice = Action.TAKE_LOCAL
    run(world, plan)
    there = world.there / "app"
    assert git(there, "rev-parse", "HEAD") == mine
    assert git(there, "rev-parse", "refs/gitpair/backup/main") == theirs


@pytest.mark.story("user: Resolve diverged branches")
async def test_user_answers_question_and_runs_plan(world: World):
    world.track.append("app")
    world.repo("app")
    commit(world.here / "app", "a.txt")
    commit(world.there / "app", "b.txt")
    plan = world.plan()
    app = PlanApp(plan)

    async with app.run_test() as pilot:
        assert app.title == "gitpair: 1 to decide, 0 in sync"
        await pilot.press("enter")  # open the question for the selected row
        await pilot.press("down", "enter")  # second option: take remote
        assert plan.items[0].choice is Action.TAKE_REMOTE
        assert app.title == "gitpair: 0 to decide, 0 in sync"
        await pilot.press("x")

    assert app.return_value is True
