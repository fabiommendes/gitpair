from __future__ import annotations

from conftest import World, commit

from gitpair.plan import Action
from gitpair.tui import PlanApp


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


async def test_quit_returns_false(world: World):
    world.repo("app")
    app = PlanApp(world.plan())
    async with app.run_test() as pilot:
        await pilot.press("s")
        await pilot.press("q")
    assert app.return_value is False
