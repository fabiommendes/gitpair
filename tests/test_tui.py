from __future__ import annotations

import os
from pathlib import Path

from conftest import World

from gitpair.tui import PlanApp


def write(path: Path, content: str, mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    os.utime(path, (mtime, mtime))


async def test_quit_returns_false(world: World):
    world.repo("app")
    app = PlanApp(world.plan())
    async with app.run_test() as pilot:
        await pilot.press("s")
        await pilot.press("q")
    assert app.return_value is False
