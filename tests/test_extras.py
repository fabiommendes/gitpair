from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from conftest import World, commit, git

from gitpair import config as cfg
from gitpair import session
from gitpair.plan import Action, Item, Plan, Step

GITIGNORE = "storage/\n.env\n"


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


# Ignored files


@pytest.fixture
def files_world(world: World) -> World:
    world.extra_config = '\n[repo.app]\nsync_ignored = ["storage", ".env"]\n'
    world.repo("app", gitignore=GITIGNORE)
    return world


def test_ignored_files_are_copied_both_ways_newest_wins(files_world: World):
    here, there = files_world.here / "app", files_world.there / "app"
    write(here / "storage/a.txt", "a", 1000)
    write(here / ".env", "SECRET=1", 1000)
    write(here / "storage/shared.txt", "old", 1000)
    write(there / "storage/b/c.txt", "c", 1000)
    write(there / "storage/shared.txt", "new", 2000)

    plan = files_world.plan()
    item = only(plan)
    assert item.choice is Action.KEEP
    assert [(e.step, e.files) for e in item.extras] == [
        (Step.FILES_THERE, [".env", "storage/a.txt"]),
        (Step.FILES_HERE, ["storage/b/c.txt", "storage/shared.txt"]),
    ]

    outcome = run(files_world, plan)
    assert not outcome.failed
    for side in (here, there):
        assert (side / "storage/a.txt").read_text() == "a"
        assert (side / "storage/b/c.txt").read_text() == "c"
        assert (side / "storage/shared.txt").read_text() == "new"
        assert (side / ".env").read_text() == "SECRET=1"
    assert (here / "storage/shared.txt").stat().st_mtime == 2000
    assert files_world.plan().pending == []


def test_ignored_files_are_copied_after_fast_forward(files_world: World):
    here, there = files_world.here / "app", files_world.there / "app"
    head = commit(there, "new.txt")
    write(there / "storage/data.bin", "data", 1000)

    plan = files_world.plan()
    item = only(plan)
    assert item.choice is Action.PULL
    assert [e.step for e in item.extras] == [Step.FILES_HERE]

    assert not run(files_world, plan).failed
    assert git(here, "rev-parse", "HEAD") == head
    assert (here / "storage/data.bin").read_text() == "data"


def test_deleted_files_are_copied_back_not_deleted(files_world: World):
    write(files_world.there / "app/storage/kept.txt", "x", 1000)
    plan = files_world.plan()
    assert [e.step for e in only(plan).extras] == [Step.FILES_HERE]


def test_skipped_repo_copies_nothing(files_world: World):
    write(files_world.here / "app/storage/a.txt", "a", 1000)
    plan = files_world.plan()
    only(plan).choice = Action.SKIP
    run(files_world, plan)
    assert not (files_world.there / "app/storage/a.txt").exists()


def test_missing_file_between_plan_and_apply_does_not_abort_the_run(world: World):
    world.extra_config = '\n[repo.app]\nsync_ignored = ["storage"]\n'
    world.repo("app", gitignore=GITIGNORE)
    world.track.append("other")
    world.repo("other")
    other_head = commit(world.there / "other", "new.txt")
    write(world.here / "app/storage/a.txt", "a", 1000)

    plan = world.plan()
    app_item = next(i for i in plan.pending if i.repo == "app")
    other_item = next(i for i in plan.pending if i.repo == "other")
    assert app_item.choice is Action.KEEP
    assert [e.step for e in app_item.extras] == [Step.FILES_THERE]
    other_item.choice = Action.PULL

    (world.here / "app/storage/a.txt").unlink()  # removed after planning

    outcome = run(world, plan)
    assert [i.repo for i, _ in outcome.failed] == ["app"]
    assert other_item in outcome.done
    assert git(world.here / "other", "rev-parse", "HEAD") == other_head


def test_entries_not_ignored_by_git_are_reported_and_skipped(world: World):
    world.extra_config = '\n[repo.app]\nsync_ignored = ["src"]\n'
    world.repo("app", gitignore=GITIGNORE)
    write(world.here / "app/src/main.py", "x", 1000)

    item = only(world.plan())
    assert item.choice is Action.SKIP
    assert item.extras == []
    assert "not ignored by git: src" in item.status


def test_files_with_same_mtime_and_different_size_are_reported(files_world: World):
    write(files_world.here / "app/storage/x.txt", "short", 1000)
    write(files_world.there / "app/storage/x.txt", "much longer", 1000)
    item = only(files_world.plan())
    assert item.extras == []
    assert "1 file differ with the same mtime" in item.status


# Autopush


@pytest.fixture
def origin(world: World) -> Path:
    """A bare origin shared by both hosts, holding the first commit."""
    world.extra_config = "\n[repo.app]\nautopush = true\n"
    world.repo("app")
    bare = world.tmp / "origin.git"
    subprocess.run(
        ["git", "clone", "--quiet", "--bare", str(world.here / "app"), str(bare)],
        check=True,
    )
    git(world.here / "app", "remote", "add", "origin", str(bare))
    git(world.there / "app", "remote", "set-url", "origin", str(bare))
    for side in (world.here, world.there):
        git(side / "app", "fetch", "--quiet", "origin")
    return bare


def test_autopush_pushes_synced_commits_to_origin(world: World, origin: Path):
    head = commit(world.here / "app", "a.txt")
    git(world.there / "app", "pull", "--quiet", str(world.here / "app"), "main")

    plan = world.plan()
    item = only(plan)
    assert item.choice is Action.KEEP
    assert [e.step for e in item.extras] == [Step.ORIGIN]

    assert not run(world, plan).failed
    assert git(origin, "rev-parse", "main") == head
    assert world.plan().pending == []


def test_autopush_runs_after_pull(world: World, origin: Path):
    head = commit(world.there / "app", "b.txt")
    plan = world.plan()
    item = only(plan)
    assert item.choice is Action.PULL
    assert [e.step for e in item.extras] == [Step.ORIGIN]

    assert not run(world, plan).failed
    assert git(origin, "rev-parse", "main") == head


def test_autopush_creates_missing_branch(world: World, origin: Path):
    for side in (world.here, world.there):
        git(side / "app", "checkout", "--quiet", "-b", "feature")
    plan = world.plan()
    assert [e.step for e in only(plan).extras] == [Step.ORIGIN]
    assert not run(world, plan).failed
    assert git(origin, "rev-parse", "feature") == git(
        world.here / "app", "rev-parse", "HEAD"
    )


def test_autopush_never_forces_diverged_origin(world: World, origin: Path):
    other = world.tmp / "other"
    subprocess.run(["git", "clone", "--quiet", str(origin), str(other)], check=True)
    theirs = commit(other, "other.txt")
    git(other, "push", "--quiet", "origin", "main")
    commit(world.there / "app", "b.txt")

    plan = world.plan()
    outcome = run(world, plan)
    assert [item.repo for item, _ in outcome.failed] == ["app"]
    assert "origin has diverged" in str(outcome.failed[0][1])
    assert git(origin, "rev-parse", "main") == theirs


def test_diverged_origin_is_reported_when_in_sync(world: World, origin: Path):
    other = world.tmp / "other"
    subprocess.run(["git", "clone", "--quiet", str(origin), str(other)], check=True)
    commit(other, "other.txt")
    git(other, "push", "--quiet", "origin", "main")
    for side in (world.here, world.there):
        commit(side / "app", "same.txt", "same")
    git(world.here / "app", "reset", "--quiet", "--hard", "HEAD~1")
    git(world.here / "app", "pull", "--quiet", str(world.there / "app"), "main")

    item = only(world.plan())
    assert item.choice is Action.SKIP
    assert "origin has diverged" in item.status


def test_autopush_works_without_a_fetch_refspec(world: World):
    # Without remote.origin.fetch, `git fetch origin <branch>` only updates
    # FETCH_HEAD: refs/remotes/origin/<branch> is never created.
    world.extra_config = "\n[repo.app]\nautopush = true\n"
    world.repo("app")
    bare = world.tmp / "origin.git"
    subprocess.run(
        ["git", "clone", "--quiet", "--bare", str(world.here / "app"), str(bare)],
        check=True,
    )
    git(world.here / "app", "remote", "add", "origin", str(bare))
    git(world.here / "app", "config", "--unset", "remote.origin.fetch")
    git(world.there / "app", "remote", "set-url", "origin", str(bare))
    git(world.there / "app", "config", "--unset", "remote.origin.fetch")

    head = commit(world.here / "app", "a.txt")
    git(world.there / "app", "pull", "--quiet", str(world.here / "app"), "main")

    plan = world.plan()
    item = only(plan)
    assert item.choice is Action.KEEP
    assert [e.step for e in item.extras] == [Step.ORIGIN]

    assert not run(world, plan).failed
    assert git(bare, "rev-parse", "main") == head


def test_autopush_off_by_default(world: World):
    world.repo("app")
    world.track.append("app")
    commit(world.here / "app", "a.txt")
    assert only(world.plan()).extras == []


# Config


def test_repo_table_tracks_and_inherits_default_autopush(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[settings]\nautopush = true\n[hosts.a]\nssh = "a"\n[hosts.b]\nssh = "b"\n'
        '[repo."web/site"]\nsync_ignored = ["media/"]\n'
    )
    config = cfg.load(path)
    assert config.is_tracked("web/site")
    assert config.options("web/site") == cfg.RepoOptions(("media",), autopush=True)
    assert config.options("other").autopush is True


@pytest.mark.parametrize("entry", ["/etc", "../x", "a/../../b", ".git/config", ""])
def test_sync_ignored_rejects_paths_outside_the_repo(tmp_path: Path, entry: str):
    path = tmp_path / "config.toml"
    path.write_text(
        '[hosts.a]\nssh = "a"\n[hosts.b]\nssh = "b"\n'
        f'[repo.app]\nsync_ignored = ["{entry}"]\n'
    )
    with pytest.raises(cfg.ConfigError, match="sync_ignored"):
        cfg.load(path)
