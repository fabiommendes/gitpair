from __future__ import annotations

import os
from pathlib import Path

from conftest import World, commit

from gitpair.plan import Action, FilesPolicy
from gitpair.tui import PlanApp


def write(path: Path, content: str, mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    os.utime(path, (mtime, mtime))


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


async def test_quit_returns_false(world: World):
    world.repo("app")
    app = PlanApp(world.plan())
    async with app.run_test() as pilot:
        await pilot.press("s")
        await pilot.press("q")
    assert app.return_value is False
