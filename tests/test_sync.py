from __future__ import annotations

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


def test_different_branches_are_reported_and_skipped(world: World):
    world.track.append("app")
    world.repo("app")
    git(world.there / "app", "checkout", "--quiet", "-b", "feature")
    commit(world.there / "app", "f.txt")

    item = only(world.plan())
    assert item.choice is Action.SKIP
    assert item.status == "on main at here, feature at there"


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
