from __future__ import annotations

import tomllib

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


def test_repos_with_same_head_are_in_sync(world: World):
    world.track.append("app")
    world.repo("app")
    plan = world.plan()
    assert plan.pending == []
    assert plan.items[0].in_sync


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


def test_dirty_work_tree_asks(world: World):
    world.track.append("app")
    world.repo("app")
    commit(world.here / "app", "new.txt")
    (world.there / "app/README").write_text("local edit")

    item = only(world.plan())
    assert item.needs_decision
    assert item.options == [Action.PUSH, Action.SKIP]
    assert "dirty on there" in item.status


def test_push_cleans_up_incoming_ref_when_remote_merge_fails(world: World):
    world.track.append("app")
    world.repo("app")
    commit(world.here / "app", "README", "local change")
    (world.there / "app/README").write_text("dirty remote edit")

    plan = world.plan()
    item = only(plan)
    assert item.needs_decision
    item.choice = Action.PUSH

    remote = world.there / "app"
    before_head = git(remote, "rev-parse", "HEAD")

    outcome = session.run(world.loaded, plan)
    assert [failed_item for failed_item, _ in outcome.failed] == [item]

    assert git(remote, "rev-parse", "HEAD") == before_head
    assert (remote / "README").read_text() == "dirty remote edit"
    assert git(remote, "for-each-ref", "refs/gitpair/incoming") == ""


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


def test_different_branches_are_reported_and_skipped(world: World):
    world.track.append("app")
    world.repo("app")
    git(world.there / "app", "checkout", "--quiet", "-b", "feature")
    commit(world.there / "app", "f.txt")

    item = only(world.plan())
    assert item.choice is Action.SKIP
    assert item.status == "on main at here, feature at there"


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


def test_new_repo_can_be_ignored(world: World):
    world.repo("app")
    plan = world.plan()
    item = only(plan)
    assert item.options == [Action.TRACK, Action.IGNORE, Action.SKIP]

    item.choice = Action.IGNORE
    run(world, plan)
    assert world.plan().items == []


def test_ignore_patterns_hide_repos(world: World):
    world.repo("archived/old")
    assert world.plan().items == []


def test_config_is_not_pushed_over_a_different_remote_copy(world: World):
    world.repo("app")
    remote_config = world.tmp / "home-there/.config/gitpair/config.toml"
    remote_config.parent.mkdir(parents=True)
    remote_config.write_text("# edited by hand\n")

    plan = world.plan()
    only(plan).choice = Action.TRACK
    outcome = run(world, plan)
    assert outcome.config_note is not None
    assert "there has a different config" in outcome.config_note
    assert remote_config.read_text() == "# edited by hand\n"
