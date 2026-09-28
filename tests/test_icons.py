"""Unit tests for the plan table's icons, using hand-built Items.

No git and no Host I/O: :func:`gitpair.plan.icons` is pure, a function of
the Item alone (and the two host names for extras).
"""

from __future__ import annotations

from gitpair.plan import (
    Action,
    Extra,
    FilesPolicy,
    Item,
    RepoState,
    Step,
    icons,
    legend,
)

HERE, THERE = "here", "there"


def state(*, dirty: bool = False, error: str | None = None) -> RepoState:
    return RepoState(
        path="app",
        branch="main",
        head="abc123",
        dirty=dirty,
        untracked=False,
        origin=None,
        error=error,
    )


def test_in_sync() -> None:
    item = Item(
        "app",
        state(),
        state(),
        "in sync",
        [Action.SKIP],
        choice=Action.SKIP,
        comparable=True,
        in_sync=True,
    )
    assert icons(item, HERE, THERE) == ("✓", "in sync", "–", "skip")


def test_ahead_is_automatic() -> None:
    item = Item(
        "app",
        state(),
        state(),
        "ahead by 1",
        [Action.PUSH, Action.SKIP],
        choice=Action.PUSH,
        comparable=True,
        ahead=1,
    )
    assert icons(item, HERE, THERE) == ("↑", "ahead by 1", "▶", "push")


def test_behind_is_automatic() -> None:
    item = Item(
        "app",
        state(),
        state(),
        "behind by 2",
        [Action.PULL, Action.SKIP],
        choice=Action.PULL,
        comparable=True,
        behind=2,
    )
    assert icons(item, HERE, THERE) == ("↓", "behind by 2", "▶", "pull")


def test_ahead_with_dirty_work_tree_needs_decision() -> None:
    item = Item(
        "app",
        state(dirty=True),
        state(),
        "ahead by 1; dirty on here",
        [Action.PUSH, Action.SKIP],
        comparable=True,
        ahead=1,
    )
    status_icon, status, action_icon, action_text = icons(item, HERE, THERE)
    assert status_icon == "✎↑"  # dirty + ahead
    assert status == "ahead by 1; dirty on here"
    assert action_icon == "?"
    assert action_text == "push"  # SKIP is dropped, it is always implicit


def test_diverged_offers_all_options() -> None:
    item = Item(
        "app",
        state(),
        state(),
        "diverged (1 ahead, 1 behind)",
        [Action.MERGE, Action.TAKE_REMOTE, Action.TAKE_LOCAL, Action.SKIP],
        comparable=True,
        ahead=1,
        behind=1,
    )
    status_icon, _, action_icon, action_text = icons(item, HERE, THERE)
    assert status_icon == "⇅"
    assert action_icon == "?"
    assert action_text == "merge/take-remote/take-local"


def test_only_here_is_a_clone_there() -> None:
    item = Item("app", state(), None, "only on here", [Action.CLONE_THERE, Action.SKIP])
    status_icon, _, action_icon, action_text = icons(item, HERE, THERE)
    assert status_icon == "→"
    assert action_icon == "?"  # options remain open until a decision is made
    assert action_text == "clone-there"


def test_only_there_resolved_is_automatic() -> None:
    item = Item(
        "app",
        None,
        state(),
        "only on there",
        [Action.CLONE_HERE, Action.SKIP],
        choice=Action.CLONE_HERE,
    )
    status_icon, _, action_icon, action_text = icons(item, HERE, THERE)
    assert status_icon == "←"
    assert action_icon == "▶"
    assert action_text == "clone-here"


def test_git_error() -> None:
    item = Item(
        "app",
        state(error="fatal: not a git repository"),
        state(),
        "git error on here: fatal: not a git repository",
        [Action.SKIP],
        choice=Action.SKIP,
    )
    status_icon, _, action_icon, action_text = icons(item, HERE, THERE)
    assert status_icon == "✗"
    assert action_icon == "–"
    assert action_text == "skip"


def test_empty_repository_is_skipped() -> None:
    item = Item(
        "app",
        state(),
        state(),
        "empty repository",
        [Action.SKIP],
        choice=Action.SKIP,
    )
    status_icon, _, action_icon, action_text = icons(item, HERE, THERE)
    assert status_icon == "∅"
    assert action_icon == "–"
    assert action_text == "skip"


def test_new_repository_needs_a_decision() -> None:
    item = Item(
        "app",
        state(),
        state(),
        "new, ahead by 1",
        [Action.PUSH, Action.IGNORE, Action.SKIP],
        new=True,
        comparable=True,
        ahead=1,
    )
    status_icon, _, action_icon, action_text = icons(item, HERE, THERE)
    assert status_icon == "✚↑"  # new + ahead
    assert action_icon == "?"
    assert action_text == "push/ignore"


def test_file_conflicts_stack_a_flag_and_ask_for_a_policy() -> None:
    item = Item(
        "app",
        state(),
        state(),
        "in sync; 1 conflict, direction undecided",
        [Action.NONE, Action.SKIP],
        choice=Action.NONE,
        comparable=True,
        file_conflicts=["shared.txt"],
    )
    status_icon, _, action_icon, action_text = icons(item, HERE, THERE)
    assert status_icon.endswith("⚑")
    assert action_icon == "?"
    assert action_text == "newer-wins/skip-conflicts"


def test_file_conflicts_resolved_is_automatic() -> None:
    item = Item(
        "app",
        state(),
        state(),
        "in sync",
        [Action.NONE, Action.SKIP],
        choice=Action.NONE,
        comparable=True,
        file_conflicts=["shared.txt"],
        files_policy=FilesPolicy.NEWER_WINS,
    )
    _, _, action_icon, action_text = icons(item, HERE, THERE)
    assert action_icon == "▶"
    assert action_text == "none"


def test_extras_append_to_the_automatic_action() -> None:
    item = Item(
        "app",
        state(),
        state(),
        "ahead by 1",
        [Action.PUSH, Action.SKIP],
        choice=Action.PUSH,
        comparable=True,
        ahead=1,
        extras=[
            Extra(Step.FILES_THERE, "copy 2 files to there", ["a", "b"]),
            Extra(Step.ORIGIN, "push to origin"),
        ],
    )
    _, _, _, action_text = icons(item, HERE, THERE)
    assert action_text == "push + 2 files → there + origin"


def test_files_here_extra_names_the_local_host() -> None:
    item = Item(
        "app",
        state(),
        state(),
        "behind by 1",
        [Action.PULL, Action.SKIP],
        choice=Action.PULL,
        comparable=True,
        behind=1,
        extras=[Extra(Step.FILES_HERE, "copy 1 file to here", ["a"])],
    )
    _, _, _, action_text = icons(item, HERE, THERE)
    assert action_text == "pull + 1 file → here"


def test_skip_chosen_by_the_user() -> None:
    item = Item(
        "app",
        state(),
        state(),
        "ahead by 1",
        [Action.PUSH, Action.SKIP],
        choice=Action.SKIP,
        comparable=True,
        ahead=1,
    )
    _, _, action_icon, action_text = icons(item, HERE, THERE)
    assert action_icon == "–"
    assert action_text == "skip"


def test_plain_mode_uses_only_ascii() -> None:
    item = Item(
        "app",
        state(dirty=True),
        state(),
        "ahead by 1; dirty on here",
        [Action.PUSH, Action.SKIP],
        comparable=True,
        ahead=1,
        new=True,
        extras=[Extra(Step.FILES_THERE, "copy 1 file to there", ["a"])],
    )
    item.choice = Action.NONE  # pretend it is resolved, to exercise extras too
    status_icon, status, action_icon, action_text = icons(item, HERE, THERE, plain=True)
    full = status_icon + status + action_icon + action_text
    assert full.isascii()
    assert status_icon == "Nd^"
    assert action_icon == ">"


def test_legend_lists_only_icons_in_use() -> None:
    in_sync = Item(
        "a",
        state(),
        state(),
        "in sync",
        [Action.SKIP],
        choice=Action.SKIP,
        comparable=True,
        in_sync=True,
    )
    ahead = Item(
        "b",
        state(),
        state(),
        "ahead by 1",
        [Action.PUSH, Action.SKIP],
        choice=Action.PUSH,
        comparable=True,
        ahead=1,
    )
    assert legend([in_sync, ahead]) == "✓ in sync  ↑ ahead  ▶ automatic  – skip"


def test_legend_is_empty_for_no_items() -> None:
    assert legend([]) == ""


def test_legend_plain_matches_plain_icons() -> None:
    item = Item(
        "a",
        state(),
        state(),
        "ahead by 1",
        [Action.PUSH, Action.SKIP],
        choice=Action.PUSH,
        comparable=True,
        ahead=1,
    )
    assert legend([item], plain=True) == "^ ahead  > automatic"
