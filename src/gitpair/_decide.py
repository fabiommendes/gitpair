"""Turn gathered facts into the final plan: no I/O, no host access.

Implements symbols re-exported by :mod:`gitpair.plan`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from gitpair._facts import (
    CompareFacts,
    CompareOutcome,
    ExtrasFacts,
    IgnoredFilesFacts,
    OriginFacts,
    RepoFacts,
)
from gitpair._model import NO_CHANGE, Action, Extra, FilesPolicy, Item, RepoState, Step
from gitpair.config import Config


def decide(
    config: Config, facts: list[RepoFacts], local_name: str, remote_name: str
) -> list[Item]:
    """Build the final :class:`~gitpair._model.Item` for every gathered repository.

    Args:
        facts: one :class:`~gitpair._facts.RepoFacts` per repository, as
            returned by :func:`gitpair._facts.gather`.
        local_name: name of the local host, used in status text.
        remote_name: name of the remote host, used in status text.

    Returns:
        One :class:`~gitpair._model.Item` per entry in ``facts``, in the same order.
    """
    return [
        _decide_item(config, repo_facts, local_name, remote_name)
        for repo_facts in facts
    ]


def compare_files(
    here: dict[str, list[int]], there: dict[str, list[int]], /
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Split files into (copy there, copy here, conflicts, clashes).

    Each mapping gives ``[size, mtime]`` per relative path. A name missing on
    one side always lands in the matching list: copying it loses nothing. A
    name present on both sides with a different mtime also lands there,
    picking the newer copy, but is repeated in ``conflicts``: it is only
    copied once the item's ``files_policy`` is decided (see
    :func:`resolved_files`). Same mtime but a different size is a clash:
    reported, never copied.

    >>> compare_files({"a": [1, 100], "only_here": [1, 1]}, {"a": [1, 50]})
    (['a', 'only_here'], [], ['a'], [])
    >>> compare_files({"a": [1, 100]}, {"a": [2, 100]})
    ([], [], [], ['a'])
    """
    to_there, to_here, conflicts, clashes = [], [], [], []
    for name in sorted(here.keys() | there.keys()):
        mine, theirs = here.get(name), there.get(name)
        if mine == theirs:
            continue
        both_sides = mine is not None and theirs is not None
        if theirs is None or mine is not None and mine[1] > theirs[1]:
            to_there.append(name)
            if both_sides:
                conflicts.append(name)
        elif mine is None or theirs[1] > mine[1]:
            to_here.append(name)
            if both_sides:
                conflicts.append(name)
        else:
            clashes.append(name)
    return to_there, to_here, conflicts, clashes


def resolved_files(item: Item, extra: Extra, /) -> list[str]:
    """Files from ``extra`` that will actually be copied, given ``item.files_policy``.

    Conflicting files (:attr:`~gitpair._model.Item.file_conflicts`) are kept
    only when the policy is :attr:`~gitpair._model.FilesPolicy.NEWER_WINS`.
    They are dropped for :attr:`~gitpair._model.FilesPolicy.SKIP_CONFLICTS`
    and for the undecided default (``None``), so a conflict is never copied
    without an explicit choice. Every other file is always kept.

    >>> item = Item("app", None, None, "", [], file_conflicts=["a"])
    >>> resolved_files(item, Extra(Step.FILES_THERE, "", ["a", "b"]))
    ['b']
    """
    if not item.file_conflicts or item.files_policy is FilesPolicy.NEWER_WINS:
        return extra.files
    conflicts = set(item.file_conflicts)
    return [name for name in extra.files if name not in conflicts]


def count(items: list, noun: str) -> str:
    """Pluralize ``noun`` for the number of ``items``.

    >>> count(["a"], "file")
    '1 file'
    >>> count(["a", "b"], "file")
    '2 files'
    """
    return f"{len(items)} {noun}{'' if len(items) == 1 else 's'}"


def describe(item: Item, local: str, remote: str) -> str:
    """The chosen action followed by the extra steps.

    A file conflict adds one more piece, naming the count and the chosen
    :class:`~gitpair._model.FilesPolicy` (falling back to "skip conflicting
    files", the same default :func:`resolved_files` uses, when it is not
    decided yet, which should not happen for an item passed here).

    >>> item = Item("app", None, None, "ahead by 1", [Action.PUSH], choice=Action.PUSH)
    >>> describe(item, "here", "there")
    'fast-forward there from here'
    """
    if item.choice is None:
        return "?"
    text = item.choice.describe(local, remote)
    if item.choice in NO_CHANGE:
        return text
    pieces = [
        piece
        for extra in item.extras
        if (piece := _describe_extra(item, extra, local, remote)) is not None
    ]
    if item.file_conflicts:
        pieces.append(_describe_conflicts(item))
    if not pieces:
        return text
    return " + ".join([text, *pieces])


def _describe_extra(item: Item, extra: Extra, local: str, remote: str) -> str | None:
    """``extra``'s description, adjusted for a skipped conflict; ``None`` drops it."""
    file_step = extra.step in (Step.FILES_THERE, Step.FILES_HERE)
    if not item.file_conflicts or not file_step:
        return extra.description
    files = resolved_files(item, extra)
    if not files:
        return None
    if len(files) == len(extra.files):
        return extra.description
    name = remote if extra.step is Step.FILES_THERE else local
    return f"copy {count(files, 'file')} to {name}"


def _describe_conflicts(item: Item) -> str:
    # None behaves like SKIP_CONFLICTS in resolved_files(): match the text.
    policy = item.files_policy or FilesPolicy.SKIP_CONFLICTS
    return f"{count(item.file_conflicts, 'conflict')}: {policy.describe()}"


#
# Internals
#


@dataclass(frozen=True)
class _ItemFields:
    """An :class:`Item`'s fields except ``repo``, ``local``, ``remote`` and ``new``."""

    status: str
    options: list[Action]
    choice: Action | None = None
    comparable: bool = False
    in_sync: bool = False
    ahead: int = 0
    behind: int = 0
    extras: list[Extra] = field(default_factory=list)
    file_conflicts: list[str] = field(default_factory=list)
    #: True when git itself failed on one side. Kept out of Item: it only
    #: needs to steer _mark_new (no track offered for a broken directory).
    error: bool = False


def _decide_item(
    config: Config, facts: RepoFacts, local_name: str, remote_name: str
) -> Item:
    if facts.local is not None and facts.remote is not None:
        assert facts.compare is not None
        fields = _decide_compare(
            facts.local, facts.remote, local_name, remote_name, facts.compare
        )
    else:
        fields = _decide_one_sided(facts.local, facts.remote, local_name, remote_name)

    new = not config.is_tracked(facts.repo)
    if new:
        fields = _mark_new(fields)
    elif fields.comparable:
        fields = _decide_extras(fields, facts.extras, local_name, remote_name)

    return Item(
        repo=facts.repo,
        local=facts.local,
        remote=facts.remote,
        status=fields.status,
        options=fields.options,
        choice=fields.choice,
        new=new,
        in_sync=fields.in_sync,
        ahead=fields.ahead,
        behind=fields.behind,
        comparable=fields.comparable,
        extras=fields.extras,
        file_conflicts=fields.file_conflicts,
    )


def _decide_compare(
    lstate: RepoState,
    rstate: RepoState,
    local_name: str,
    remote_name: str,
    facts: CompareFacts,
) -> _ItemFields:
    if facts.outcome is CompareOutcome.GIT_ERROR:
        return _git_error_fields(lstate, rstate, local_name, remote_name)
    if facts.outcome is CompareOutcome.EMPTY:
        return _ItemFields("empty repository", [Action.SKIP], Action.SKIP)
    if facts.outcome is CompareOutcome.DETACHED:
        return _ItemFields("detached HEAD", [Action.SKIP], Action.SKIP)
    if facts.outcome is CompareOutcome.BRANCH_MISMATCH:
        status = f"on {lstate.branch} at {local_name}, {rstate.branch} at {remote_name}"
        return _ItemFields(status, [Action.SKIP], Action.SKIP)
    if facts.outcome is CompareOutcome.IN_SYNC:
        return _ItemFields(
            "in sync", [Action.SKIP], Action.SKIP, comparable=True, in_sync=True
        )
    if facts.outcome is CompareOutcome.FETCH_FAILED:
        return _ItemFields(
            f"fetch failed: {facts.error}", [Action.SKIP], Action.SKIP, comparable=True
        )
    return _decide_divergence(
        lstate, rstate, local_name, remote_name, facts.ahead, facts.behind
    )


def _decide_divergence(
    lstate: RepoState,
    rstate: RepoState,
    local_name: str,
    remote_name: str,
    ahead: int,
    behind: int,
) -> _ItemFields:
    dirty = [
        name
        for name, state in ((local_name, lstate), (remote_name, rstate))
        if state.dirty
    ]
    if ahead and behind:
        status = f"diverged ({ahead} ahead, {behind} behind)"
        options = [Action.MERGE]
        if not lstate.dirty:
            options.append(Action.TAKE_REMOTE)
        if not rstate.dirty:
            options.append(Action.TAKE_LOCAL)
        options.append(Action.SKIP)
        choice = None
    else:
        action = Action.PUSH if ahead else Action.PULL
        total = ahead or behind
        status = f"{'ahead' if ahead else 'behind'} by {total}"
        options = [action, Action.SKIP]
        choice = action if not dirty else None
    if dirty:
        status += f"; dirty on {', '.join(dirty)}"
    return _ItemFields(
        status, options, choice, comparable=True, ahead=ahead, behind=behind
    )


def _git_error_fields(
    lstate: RepoState, rstate: RepoState, local_name: str, remote_name: str
) -> _ItemFields:
    where = local_name if lstate.error else remote_name
    message = lstate.error if lstate.error else rstate.error
    status = f"git error on {where}: {message}"
    return _ItemFields(status, [Action.SKIP], Action.SKIP, error=True)


def _decide_one_sided(
    lstate: RepoState | None,
    rstate: RepoState | None,
    local_name: str,
    remote_name: str,
) -> _ItemFields:
    state = lstate or rstate
    assert state is not None
    where = local_name if lstate else remote_name
    if state.error:
        status = f"git error on {where}: {state.error}"
        return _ItemFields(status, [Action.SKIP], Action.SKIP, error=True)
    if not state.head or not state.branch:
        status = f"only on {where}, no branch to clone"
        return _ItemFields(status, [Action.SKIP], Action.SKIP)
    action = Action.CLONE_THERE if lstate else Action.CLONE_HERE
    return _ItemFields(f"only on {where}", [action, Action.SKIP], action)


def _mark_new(fields: _ItemFields) -> _ItemFields:
    """Repositories missing from the config always need a decision.

    A repository where git failed is never offered :attr:`~Action.TRACK`:
    there is nothing to track while the directory is broken.
    """
    options = list(fields.options)
    if options == [Action.SKIP] and not fields.error:
        options = [Action.TRACK, Action.SKIP]
    options.insert(-1, Action.IGNORE)
    return replace(
        fields,
        status=f"new, {fields.status}",
        options=options,
        choice=None,
        in_sync=False,
    )


def _decide_extras(
    fields: _ItemFields, extras: ExtrasFacts, local_name: str, remote_name: str
) -> _ItemFields:
    """Fold the copy of ignored files and the push to origin into ``fields``."""
    notes: list[str] = []
    new_extras: list[Extra] = []
    file_conflicts: list[str] = []
    if extras.ignored_files is not None:
        files_extras, files_notes, conflicts = _decide_ignored_files(
            extras.ignored_files, local_name, remote_name
        )
        new_extras += files_extras
        notes += files_notes
        file_conflicts = conflicts
    if extras.origin is not None:
        origin_extra, origin_notes = _decide_origin(extras.origin)
        if origin_extra is not None:
            new_extras.append(origin_extra)
        notes += origin_notes

    status = fields.status
    if notes:
        status = status + "; " + "; ".join(notes)

    in_sync, options, choice = fields.in_sync, fields.options, fields.choice
    if new_extras and in_sync:
        in_sync = False
        options = [Action.NONE, Action.SKIP]
        choice = Action.NONE
    elif notes:
        in_sync = False  # show the warning in the plan

    return replace(
        fields,
        status=status,
        in_sync=in_sync,
        options=options,
        choice=choice,
        extras=new_extras,
        file_conflicts=file_conflicts,
    )


def _decide_ignored_files(
    facts: IgnoredFilesFacts, local_name: str, remote_name: str
) -> tuple[list[Extra], list[str], list[str]]:
    """Extras, status notes, and the names that are conflicts (need a decision)."""
    notes: list[str] = []
    if facts.not_ignored:
        notes.append(f"not ignored by git: {', '.join(facts.not_ignored)}")
    if facts.error:
        notes.append(f"could not list ignored files: {facts.error}")
        return [], notes, []
    if facts.here is None or facts.there is None:
        return [], notes, []
    to_there, to_here, conflicts, clashes = compare_files(facts.here, facts.there)
    extras: list[Extra] = []
    if to_there:
        extras.append(
            Extra(
                Step.FILES_THERE,
                f"copy {count(to_there, 'file')} to {remote_name}",
                to_there,
            )
        )
    if to_here:
        extras.append(
            Extra(
                Step.FILES_HERE,
                f"copy {count(to_here, 'file')} to {local_name}",
                to_here,
            )
        )
    if conflicts:
        notes.append(f"{count(conflicts, 'conflict')}, direction undecided")
    if clashes:
        notes.append(f"{count(clashes, 'file')} differ with the same mtime")
    return extras, notes, conflicts


def _decide_origin(facts: OriginFacts) -> tuple[Extra | None, list[str]]:
    extra = Extra(Step.ORIGIN, "push to origin")
    if not facts.checked:
        return extra, []
    if facts.error:
        return None, [f"could not fetch origin: {facts.error}"]
    if facts.state == "behind":
        return extra, []
    if facts.state == "diverged":
        return None, ["origin has diverged"]
    return None, []
