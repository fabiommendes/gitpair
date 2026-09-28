"""Compact icons and short labels for the plan table.

Pure presentation over :class:`~gitpair._model.Item`: no host access, no
decisions, no Rich markup (callers escape and style the result). Implements
symbols re-exported by :mod:`gitpair.plan`.

Icons are single-codepoint symbols that render at one column width in every
common terminal (checked with Rich against an 80-column console). Emoji such
as flags or colored circles are avoided: many render two columns wide and
misalign the table.
"""

from __future__ import annotations

from gitpair._decide import count
from gitpair._model import Action, Extra, FilesPolicy, Item, Step

#: Status icons. Can stack in the plan table's first column, e.g. "✚✎↑".
IN_SYNC = "✓"  # ✓
AHEAD = "↑"  # ↑
BEHIND = "↓"  # ↓
DIVERGED = "⇅"  # ⇅
DIRTY = "✎"  # ✎
NEW = "✚"  # ✚
ONLY_HERE = "→"  # →  present locally only, would be copied there
ONLY_THERE = "←"  # ←  present remotely only, would be copied here
GIT_ERROR = "✗"  # ✗
EMPTY = "∅"  # ∅  empty repository, detached HEAD, branch mismatch, ...
CONFLICT = "⚑"  # ⚑  ignored files that differ on both hosts

#: Action icons, for the second icon in the "Action" column.
AUTOMATIC = "▶"  # ▶  chosen action, runs as-is
DECIDE = "?"  # a choice is still open
SKIP = "–"  # –  chosen action is to skip

_LABELS = {
    IN_SYNC: "in sync",
    AHEAD: "ahead",
    BEHIND: "behind",
    DIVERGED: "diverged",
    DIRTY: "dirty",
    NEW: "new",
    ONLY_HERE: "only here",
    ONLY_THERE: "only there",
    GIT_ERROR: "git error",
    EMPTY: "empty/no branch",
    CONFLICT: "conflicting files",
    AUTOMATIC: "automatic",
    DECIDE: "decide",
    SKIP: "skip",
}

#: Fixed order the legend lists icons in, when they are used.
_LEGEND_ORDER = [
    IN_SYNC,
    AHEAD,
    BEHIND,
    DIVERGED,
    DIRTY,
    NEW,
    ONLY_HERE,
    ONLY_THERE,
    GIT_ERROR,
    EMPTY,
    CONFLICT,
    AUTOMATIC,
    DECIDE,
    SKIP,
]

#: ASCII fallback for --plain, keyed by the unicode icon above.
_PLAIN = {
    IN_SYNC: "=",
    AHEAD: "^",
    BEHIND: "v",
    DIVERGED: "x",
    DIRTY: "d",
    NEW: "N",
    ONLY_HERE: ">",
    ONLY_THERE: "<",
    GIT_ERROR: "!",
    EMPTY: "-",
    CONFLICT: "C",
    AUTOMATIC: ">",
    DECIDE: "?",
    SKIP: "-",
}


def icons(
    item: Item, local: str, remote: str, /, *, plain: bool = False
) -> tuple[str, str, str, str]:
    """Icons and short labels for one plan row.

    Args:
        local: local host name, used for extras that copy files there.
        remote: remote host name, same use.
        plain: use the ASCII fallback instead of unicode icons.

    Returns:
        ``(status_icon, status_short, action_icon, action_short)``.
        ``status_icon`` can stack several icons, e.g. new + dirty + ahead.
        ``status_short`` is :attr:`~gitpair._model.Item.status`, already a
        short phrase. ``action_short`` names the pending decision, the
        chosen action, or the extra steps appended after it.

    >>> item = Item(
    ...     "app", None, None, "ahead by 1",
    ...     [Action.PUSH, Action.SKIP], choice=Action.PUSH,
    ...     comparable=True, ahead=1,
    ... )
    >>> icons(item, "here", "there")
    ('↑', 'ahead by 1', '▶', 'push')
    >>> icons(item, "here", "there", plain=True)
    ('^', 'ahead by 1', '>', 'push')
    """
    status = "".join(_render(icon, plain) for icon in _status_icons(item))
    action_icon = _render(_action_icon(item), plain)
    action_text = _action_text(item, local, remote, plain)
    return status, item.status, action_icon, action_text


def legend(items: list[Item], /, *, plain: bool = False) -> str:
    """One line naming every icon used by ``items``, in :data:`_LEGEND_ORDER`.

    Only the icons that actually appear are listed, so the legend stays
    short and specific to the table it follows.

    >>> item = Item(
    ...     "app", None, None, "in sync", [Action.SKIP], choice=Action.SKIP,
    ...     comparable=True, in_sync=True,
    ... )
    >>> legend([item])
    '✓ in sync  – skip'
    """
    used: set[str] = set()
    for item in items:
        used.update(_status_icons(item))
        used.add(_action_icon(item))
    parts = [
        f"{_render(icon, plain)} {_LABELS[icon]}"
        for icon in _LEGEND_ORDER
        if icon in used
    ]
    return "  ".join(parts)


#
# Internals
#


def _render(icon: str, plain: bool) -> str:
    return _PLAIN[icon] if plain else icon


def _status_icons(item: Item) -> list[str]:
    result = []
    if item.new:
        result.append(NEW)
    if _is_dirty(item):
        result.append(DIRTY)
    result.append(_primary_icon(item))
    if item.file_conflicts:
        result.append(CONFLICT)
    return result


def _is_dirty(item: Item) -> bool:
    return bool(
        (item.local and item.local.dirty) or (item.remote and item.remote.dirty)
    )


def _primary_icon(item: Item) -> str:
    if (item.local and item.local.error) or (item.remote and item.remote.error):
        return GIT_ERROR
    if item.local is None and item.remote is not None:
        return ONLY_THERE
    if item.remote is None and item.local is not None:
        return ONLY_HERE
    if item.in_sync:
        return IN_SYNC
    if item.ahead and item.behind:
        return DIVERGED
    if item.ahead:
        return AHEAD
    if item.behind:
        return BEHIND
    if not item.comparable:
        return EMPTY
    # Comparable, no divergence and not flagged in sync: a fetch failure, or
    # extra steps (ignored files, origin) layered on an otherwise-synced repo.
    return IN_SYNC


def _action_icon(item: Item) -> str:
    if item.needs_decision:
        return DECIDE
    if item.choice is Action.SKIP:
        return SKIP
    return AUTOMATIC


def _action_text(item: Item, local: str, remote: str, plain: bool) -> str:
    if item.needs_decision:
        if item.choice is None:
            options = [
                option.value for option in item.options if option is not Action.SKIP
            ]
            return "/".join(options) if options else Action.SKIP.value
        return "/".join(policy.value for policy in FilesPolicy)
    if item.choice is Action.SKIP:
        return Action.SKIP.value
    assert item.choice is not None
    parts = [item.choice.value]
    parts += [_extra_text(extra, local, remote, plain) for extra in item.extras]
    return " + ".join(parts)


def _extra_text(extra: Extra, local: str, remote: str, plain: bool) -> str:
    if extra.step is Step.ORIGIN:
        return "origin"
    dest = remote if extra.step is Step.FILES_THERE else local
    arrow = "->" if plain else "→"
    return f"{count(extra.files, 'file')} {arrow} {dest}"
