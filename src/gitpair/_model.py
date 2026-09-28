"""Data structures shared by the plan's fact-gathering and decision phases.

Implements symbols re-exported by :mod:`gitpair.plan`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum

from gitpair.hosts import Host


class Action(StrEnum):
    """A git action, or the lack of one, offered for a repository."""

    SKIP = "skip"
    NONE = "none"
    PULL = "pull"
    PUSH = "push"
    MERGE = "merge"
    TAKE_REMOTE = "take-remote"
    TAKE_LOCAL = "take-local"
    CLONE_HERE = "clone-here"
    CLONE_THERE = "clone-there"
    TRACK = "track"
    IGNORE = "ignore"

    def describe(self, local: str, remote: str, /) -> str:
        """Human-readable sentence for this action, naming the two hosts.

        >>> Action.PULL.describe("here", "there")
        'fast-forward here from there'
        """
        return _DESCRIPTIONS[self].format(local=local, remote=remote)


_DESCRIPTIONS = {
    Action.SKIP: "skip for now",
    Action.NONE: "no git changes",
    Action.PULL: "fast-forward {local} from {remote}",
    Action.PUSH: "fast-forward {remote} from {local}",
    Action.MERGE: "merge {remote} into {local}, then fast-forward {remote}",
    Action.TAKE_REMOTE: "reset {local} to {remote} (backup kept)",
    Action.TAKE_LOCAL: "reset {remote} to {local} (backup kept)",
    Action.CLONE_HERE: "clone into {local} and track",
    Action.CLONE_THERE: "clone into {remote} and track",
    Action.TRACK: "track (nothing to sync now)",
    Action.IGNORE: "ignore from now on",
}

#: Actions that change nothing in either repository.
NO_CHANGE = {Action.SKIP, Action.IGNORE}


class FilesPolicy(StrEnum):
    """How to handle conflicting :attr:`Item.file_conflicts`.

    A conflict is an ignored file present on both hosts with a different
    mtime. It is never copied until this policy is chosen, either by the
    user or, in ``--auto``, forced to :attr:`SKIP_CONFLICTS`.
    """

    NEWER_WINS = "newer-wins"
    SKIP_CONFLICTS = "skip-conflicts"

    def describe(self) -> str:
        """Human-readable label for this policy.

        >>> FilesPolicy.NEWER_WINS.describe()
        'newer wins'
        """
        return _FILES_POLICY_DESCRIPTIONS[self]


_FILES_POLICY_DESCRIPTIONS = {
    FilesPolicy.NEWER_WINS: "newer wins",
    FilesPolicy.SKIP_CONFLICTS: "skip conflicting files",
}


@dataclass(frozen=True)
class RepoState:
    """State of one repository on one host, as reported by ``scanner.py``."""

    path: str
    branch: str | None
    head: str | None
    dirty: bool
    untracked: bool
    origin: str | None
    #: First line of git's stderr when git itself failed in this repository
    #: (e.g. a ``.git`` directory with no usable content). ``None`` when git
    #: worked, including the unborn-branch case (no commit yet).
    error: str | None = None

    @classmethod
    def from_scan(cls, root: str, repo: str, data: dict) -> RepoState:
        """Build from one entry of a :func:`gitpair.scanner.scan` result.

        Args:
            root: the scan's root directory, as returned in ``scan["root"]``.
            repo: the repository's path relative to ``root``.
            data: the repository's entry in ``scan["repos"]``. Entries from
                an older scanner without an ``"error"`` key default to
                ``error=None``.
        """
        return cls(path=os.path.join(root, repo), **data)


class Step(StrEnum):
    """Work done after the commits are in sync."""

    FILES_THERE = "files-there"
    FILES_HERE = "files-here"
    ORIGIN = "origin"


@dataclass
class Extra:
    """One extra step run after the chosen :class:`Action`."""

    step: Step
    description: str
    files: list[str] = field(default_factory=list)


@dataclass
class Item:
    """The decision for one repository: its state and the chosen action.

    Every field but ``choice`` and ``files_policy`` is set once, when
    :mod:`gitpair._decide` builds the item. Both start as ``None`` for
    items that need a decision and are mutated by the TUI as the user
    answers questions.
    """

    repo: str
    local: RepoState | None
    remote: RepoState | None
    status: str
    options: list[Action]
    choice: Action | None = None
    new: bool = False
    in_sync: bool = False
    ahead: int = 0
    behind: int = 0
    comparable: bool = False
    extras: list[Extra] = field(default_factory=list)
    file_conflicts: list[str] = field(default_factory=list)
    files_policy: FilesPolicy | None = None

    @property
    def needs_decision(self) -> bool:
        """True while the git action, or the policy for its file conflicts, is open.

        A chosen :attr:`~Action.SKIP` never runs extras, so a pending
        ``files_policy`` does not matter for it.
        """
        if self.choice is None:
            return True
        if self.choice is Action.SKIP:
            return False
        return bool(self.file_conflicts) and self.files_policy is None

    @property
    def branch(self) -> str | None:
        """The repository's branch, from whichever side has one."""
        state = self.local or self.remote
        return state.branch if state else None


@dataclass
class Plan:
    """The result of comparing both hosts: every repository and its item."""

    local: Host
    remote: Host
    items: list[Item] = field(default_factory=list)

    @property
    def pending(self) -> list[Item]:
        """Items that are not already in sync."""
        return [item for item in self.items if not item.in_sync]
