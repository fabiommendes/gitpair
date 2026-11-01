"""Stories: copying ignored files between the hosts."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import World

from gitpair import session
from gitpair.plan import Action, FilesPolicy, Item, Plan, Step
from gitpair.tui import PlanApp


def write(path: Path, content: str, mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    os.utime(path, (mtime, mtime))


def only(plan: Plan) -> Item:
    assert len(plan.pending) == 1, plan.pending
    return plan.pending[0]


def run(world: World, plan: Plan) -> session.Outcome:
    assert world.loaded is not None
    return session.run(world.loaded, plan)


@pytest.mark.story("user: Copy gitignored files between machines")
def test_ignored_files_are_copied_both_ways_newest_wins(files_world: World):
    here, there = files_world.here / "app", files_world.there / "app"
    write(here / "storage/a.txt", "a", 1000)
    write(here / ".env", "SECRET=1", 1000)
    write(here / "storage/shared.txt", "old", 1000)
    write(there / "storage/b/c.txt", "c", 1000)
    write(there / "storage/shared.txt", "new", 2000)

    plan = files_world.plan()
    item = only(plan)
    assert item.choice is Action.NONE
    assert [(e.step, e.files) for e in item.extras] == [
        (Step.FILES_THERE, [".env", "storage/a.txt"]),
        (Step.FILES_HERE, ["storage/b/c.txt", "storage/shared.txt"]),
    ]
    assert item.file_conflicts == ["storage/shared.txt"]
    assert item.needs_decision
    item.files_policy = FilesPolicy.NEWER_WINS  # explicit: conflicts need a choice

    outcome = run(files_world, plan)
    assert not outcome.failed
    for side in (here, there):
        assert (side / "storage/a.txt").read_text() == "a"
        assert (side / "storage/b/c.txt").read_text() == "c"
        assert (side / "storage/shared.txt").read_text() == "new"
        assert (side / ".env").read_text() == "SECRET=1"
    assert (here / "storage/shared.txt").stat().st_mtime == 2000
    assert files_world.plan().pending == []


@pytest.mark.story("user: Copy gitignored files between machines")
def test_conflicting_file_asks_and_is_not_copied_by_default(files_world: World):
    here, there = files_world.here / "app", files_world.there / "app"
    write(here / "storage/shared.txt", "old", 1000)
    write(there / "storage/shared.txt", "new", 2000)

    plan = files_world.plan()
    item = only(plan)
    assert item.file_conflicts == ["storage/shared.txt"]
    assert item.files_policy is None
    assert item.needs_decision

    outcome = run(files_world, plan)  # files_policy left undecided
    assert not outcome.failed
    assert (here / "storage/shared.txt").read_text() == "old"
    assert (there / "storage/shared.txt").read_text() == "new"


@pytest.mark.story("user: Copy gitignored files between machines")
async def test_conflicting_files_are_asked_after_the_action(world: World):
    world.extra_config = '\n[repo.app]\nsync_ignored = ["storage"]\n'
    world.repo("app", gitignore="storage/\n")
    write(world.here / "app/storage/shared.txt", "old", 1000)
    write(world.there / "app/storage/shared.txt", "new", 2000)
    plan = world.plan()
    item = plan.items[0]
    assert item.file_conflicts == ["storage/shared.txt"]
    app = PlanApp(plan)

    async with app.run_test() as pilot:
        assert app.title == "gitpair: 1 to decide, 0 in sync"
        await pilot.press("enter")  # open the git action question
        await pilot.press("enter")  # accept the first option: no git changes
        # the item still needs a files policy: a second question follows
        await pilot.press("enter")  # accept the first option: newer wins
        assert item.choice is Action.NONE
        assert item.files_policy is FilesPolicy.NEWER_WINS
        assert app.title == "gitpair: 0 to decide, 0 in sync"
