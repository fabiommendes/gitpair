"""Unit tests for the plan's decision phase, using hand-built facts.

No git and no Host I/O: these exercise gitpair._decide.decide directly, the
pure counterpart of the git-backed scenarios in test_sync.py and
test_extras.py.
"""

from __future__ import annotations

from pathlib import Path

from gitpair import config as cfg
from gitpair._decide import decide
from gitpair._facts import (
    CompareFacts,
    CompareOutcome,
    ExtrasFacts,
    IgnoredFilesFacts,
    OriginFacts,
    RepoFacts,
    gather,
)
from gitpair.hosts import Host
from gitpair.plan import (
    Action,
    FilesPolicy,
    RepoState,
    Step,
    describe,
    resolved_files,
)

HERE, THERE = "here", "there"


def make_config(
    *, track: tuple[str, ...] = (), ignore: tuple[str, ...] = ()
) -> cfg.Config:
    hosts = {
        HERE: cfg.HostConfig(name=HERE, hostname=HERE, ssh=HERE, root="~/git"),
        THERE: cfg.HostConfig(name=THERE, hostname=THERE, ssh=THERE, root="~/git"),
    }
    return cfg.Config(
        path=Path("/dev/null"), hosts=hosts, track=list(track), ignore=list(ignore)
    )


def state(
    *, branch: str | None = "main", head: str | None = "sha", dirty: bool = False
) -> RepoState:
    return RepoState(
        path="app", branch=branch, head=head, dirty=dirty, untracked=False, origin=None
    )


def build(facts: RepoFacts, config: cfg.Config | None = None):
    items = decide(config or make_config(track=("app",)), [facts], HERE, THERE)
    return items[0]


# Compare outcomes


def test_empty_repository_is_skipped():
    facts = RepoFacts(
        "app", state(head=None), state(), CompareFacts(CompareOutcome.EMPTY)
    )
    item = build(facts)
    assert item.status == "empty repository"
    assert item.options == [Action.SKIP]
    assert item.choice is Action.SKIP
    assert not item.comparable
    assert not item.in_sync


def test_detached_head_is_skipped():
    facts = RepoFacts(
        "app", state(branch=None), state(), CompareFacts(CompareOutcome.DETACHED)
    )
    item = build(facts)
    assert item.status == "detached HEAD"
    assert item.choice is Action.SKIP
    assert not item.comparable


def test_different_branches_are_reported():
    lstate, rstate = state(branch="main"), state(branch="feature")
    facts = RepoFacts(
        "app", lstate, rstate, CompareFacts(CompareOutcome.BRANCH_MISMATCH)
    )
    item = build(facts)
    assert item.status == "on main at here, feature at there"
    assert item.choice is Action.SKIP
    assert not item.comparable


def test_in_sync():
    facts = RepoFacts("app", state(), state(), CompareFacts(CompareOutcome.IN_SYNC))
    item = build(facts)
    assert item.status == "in sync"
    assert item.choice is Action.SKIP
    assert item.comparable
    assert item.in_sync


def test_fetch_failure_is_reported_but_stays_comparable():
    facts = RepoFacts(
        "app", state(), state(), CompareFacts(CompareOutcome.FETCH_FAILED, error="boom")
    )
    item = build(facts)
    assert item.status == "fetch failed: boom"
    assert item.choice is Action.SKIP
    assert item.comparable  # extras still apply for a tracked repo


def test_ahead_is_pushed_automatically():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.COMPARED, ahead=1, behind=0),
    )
    item = build(facts)
    assert item.status == "ahead by 1"
    assert item.options == [Action.PUSH, Action.SKIP]
    assert item.choice is Action.PUSH


def test_behind_is_pulled_automatically():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.COMPARED, ahead=0, behind=2),
    )
    item = build(facts)
    assert item.status == "behind by 2"
    assert item.options == [Action.PULL, Action.SKIP]
    assert item.choice is Action.PULL


def test_ahead_with_local_dirty_needs_a_decision():
    facts = RepoFacts(
        "app",
        state(dirty=True),
        state(),
        CompareFacts(CompareOutcome.COMPARED, ahead=1, behind=0),
    )
    item = build(facts)
    assert item.status == "ahead by 1; dirty on here"
    assert item.options == [Action.PUSH, Action.SKIP]
    assert item.choice is None


def test_behind_with_remote_dirty_needs_a_decision():
    facts = RepoFacts(
        "app",
        state(),
        state(dirty=True),
        CompareFacts(CompareOutcome.COMPARED, ahead=0, behind=1),
    )
    item = build(facts)
    assert item.status == "behind by 1; dirty on there"
    assert item.choice is None


def test_diverged_both_clean_offers_merge_and_both_resets():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.COMPARED, ahead=1, behind=1),
    )
    item = build(facts)
    assert item.status == "diverged (1 ahead, 1 behind)"
    assert item.options == [
        Action.MERGE,
        Action.TAKE_REMOTE,
        Action.TAKE_LOCAL,
        Action.SKIP,
    ]
    assert item.choice is None


def test_diverged_local_dirty_drops_take_remote():
    facts = RepoFacts(
        "app",
        state(dirty=True),
        state(),
        CompareFacts(CompareOutcome.COMPARED, ahead=1, behind=1),
    )
    item = build(facts)
    assert item.options == [Action.MERGE, Action.TAKE_LOCAL, Action.SKIP]
    assert item.status == "diverged (1 ahead, 1 behind); dirty on here"


def test_diverged_remote_dirty_drops_take_local():
    facts = RepoFacts(
        "app",
        state(),
        state(dirty=True),
        CompareFacts(CompareOutcome.COMPARED, ahead=1, behind=1),
    )
    item = build(facts)
    assert item.options == [Action.MERGE, Action.TAKE_REMOTE, Action.SKIP]
    assert item.status == "diverged (1 ahead, 1 behind); dirty on there"


def test_diverged_both_dirty_only_offers_merge():
    facts = RepoFacts(
        "app",
        state(dirty=True),
        state(dirty=True),
        CompareFacts(CompareOutcome.COMPARED, ahead=1, behind=1),
    )
    item = build(facts)
    assert item.options == [Action.MERGE, Action.SKIP]
    assert item.status == "diverged (1 ahead, 1 behind); dirty on here, there"


# One-sided repositories


def test_only_local_with_a_branch_is_cloned_there():
    facts = RepoFacts("app", state(), None)
    item = build(facts)
    assert item.status == "only on here"
    assert item.options == [Action.CLONE_THERE, Action.SKIP]
    assert item.choice is Action.CLONE_THERE


def test_only_remote_with_a_branch_is_cloned_here():
    facts = RepoFacts("app", None, state())
    item = build(facts)
    assert item.status == "only on there"
    assert item.choice is Action.CLONE_HERE


def test_only_local_without_a_branch_has_nothing_to_clone():
    facts = RepoFacts("app", state(branch=None), None)
    item = build(facts)
    assert item.status == "only on here, no branch to clone"
    assert item.choice is Action.SKIP


def test_one_sided_new_repo_can_be_ignored():
    facts = RepoFacts("app", state(), None)
    item = build(facts, make_config())
    assert item.new
    assert item.options == [Action.CLONE_THERE, Action.IGNORE, Action.SKIP]
    assert item.choice is None


# New repositories


def test_new_repo_in_sync_can_be_tracked_or_ignored():
    facts = RepoFacts("app", state(), state(), CompareFacts(CompareOutcome.IN_SYNC))
    item = build(facts, make_config())
    assert item.new
    assert item.status == "new, in sync"
    assert item.options == [Action.TRACK, Action.IGNORE, Action.SKIP]
    assert item.choice is None
    assert not item.in_sync


def test_new_repo_behind_can_be_pulled_or_ignored():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.COMPARED, ahead=0, behind=1),
    )
    item = build(facts, make_config())
    assert item.status == "new, behind by 1"
    assert item.options == [Action.PULL, Action.IGNORE, Action.SKIP]
    assert item.choice is None


def test_new_repo_never_gets_extras():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(origin=OriginFacts(checked=True, state="behind")),
    )
    item = build(facts, make_config())
    assert item.new
    assert item.extras == []
    assert item.status == "new, in sync"


# sync_ignored extras


def test_sync_ignored_entries_not_ignored_by_git_are_reported():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(ignored_files=IgnoredFilesFacts(not_ignored=("src",))),
    )
    item = build(facts)
    assert item.status == "in sync; not ignored by git: src"
    assert item.extras == []
    assert item.choice is Action.SKIP
    assert not item.in_sync  # flipped to show the warning


def test_sync_ignored_manifest_failure_is_reported():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(ignored_files=IgnoredFilesFacts(error="boom")),
    )
    item = build(facts)
    assert item.status == "in sync; could not list ignored files: boom"
    assert item.extras == []


def test_sync_ignored_conflict_needs_a_files_policy():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(
            ignored_files=IgnoredFilesFacts(here={"a": [1, 100]}, there={"a": [1, 50]})
        ),
    )
    item = build(facts)
    # the git action is safe and auto-decided; only the conflict is open
    assert item.choice is Action.NONE
    assert item.options == [Action.NONE, Action.SKIP]
    assert not item.in_sync
    assert item.file_conflicts == ["a"]
    assert item.files_policy is None
    assert item.needs_decision
    assert "1 conflict" in item.status
    # undecided behaves like skip: the conflict is not copied by default
    assert resolved_files(item, item.extras[0]) == []


def test_sync_ignored_one_sided_file_is_not_a_conflict():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(
            ignored_files=IgnoredFilesFacts(
                here={"a": [1, 100], "only_here": [1, 1]}, there={"a": [1, 50]}
            )
        ),
    )
    item = build(facts)
    assert item.file_conflicts == ["a"]
    assert [e.files for e in item.extras] == [["a", "only_here"]]


def test_newer_wins_policy_copies_the_conflicting_file():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(
            ignored_files=IgnoredFilesFacts(here={"a": [1, 100]}, there={"a": [1, 50]})
        ),
    )
    item = build(facts)
    item.files_policy = FilesPolicy.NEWER_WINS
    assert not item.needs_decision
    extra = item.extras[0]
    assert resolved_files(item, extra) == ["a"]
    assert describe(item, HERE, THERE) == (
        "no git changes + copy 1 file to there + 1 conflict: newer wins"
    )


def test_skip_conflicts_policy_drops_the_conflicting_file():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(
            ignored_files=IgnoredFilesFacts(
                here={"a": [1, 100], "only_here": [1, 1]}, there={"a": [1, 50]}
            )
        ),
    )
    item = build(facts)
    item.files_policy = FilesPolicy.SKIP_CONFLICTS
    assert not item.needs_decision
    extra = item.extras[0]
    assert resolved_files(item, extra) == ["only_here"]
    assert describe(item, HERE, THERE) == (
        "no git changes + copy 1 file to there + 1 conflict: skip conflicting files"
    )


def test_sync_ignored_identical_files_stay_in_sync():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(
            ignored_files=IgnoredFilesFacts(here={"a": [1, 100]}, there={"a": [1, 100]})
        ),
    )
    item = build(facts)
    assert item.in_sync
    assert item.extras == []
    assert item.status == "in sync"


# Autopush extras


def test_origin_not_checked_while_not_in_sync_still_schedules_the_push():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.COMPARED, ahead=0, behind=1),
        extras=ExtrasFacts(origin=OriginFacts(checked=False)),
    )
    item = build(facts)
    assert item.status == "behind by 1"
    assert item.choice is Action.PULL
    assert [e.step for e in item.extras] == [Step.ORIGIN]


def test_origin_up_to_date_changes_nothing():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(origin=OriginFacts(checked=True, state="up-to-date")),
    )
    item = build(facts)
    assert item.in_sync
    assert item.extras == []
    assert item.status == "in sync"


def test_origin_behind_schedules_push_and_flips_to_keep():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(origin=OriginFacts(checked=True, state="behind")),
    )
    item = build(facts)
    assert item.choice is Action.NONE
    assert [e.step for e in item.extras] == [Step.ORIGIN]
    assert not item.in_sync


def test_origin_diverged_is_reported_without_scheduling_a_push():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(origin=OriginFacts(checked=True, state="diverged")),
    )
    item = build(facts)
    assert item.status == "in sync; origin has diverged"
    assert item.choice is Action.SKIP
    assert item.extras == []
    assert not item.in_sync


def test_origin_fetch_failure_is_reported():
    facts = RepoFacts(
        "app",
        state(),
        state(),
        CompareFacts(CompareOutcome.IN_SYNC),
        extras=ExtrasFacts(origin=OriginFacts(checked=True, error="boom")),
    )
    item = build(facts)
    assert item.status == "in sync; could not fetch origin: boom"
    assert item.extras == []


# gather() filters ignored repositories before any host is touched


def test_gather_skips_ignored_repos_without_touching_a_host():
    config = make_config(ignore=("archived/*",))
    archived_state = {
        "branch": "main", "head": "a", "dirty": False,
        "untracked": False, "origin": None,
    }  # fmt: skip
    scanned = {"root": "/x", "repos": {"archived/old": archived_state}}
    empty_scan = {"root": "/y", "repos": {}}
    local = Host(cfg.HostConfig(name=HERE, hostname=HERE, ssh=HERE, root="~"))
    remote = Host(cfg.HostConfig(name=THERE, hostname=THERE, ssh=THERE, root="~"))
    assert gather(config, local, remote, scanned, empty_scan) == []
