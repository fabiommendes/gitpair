"""Compare both hosts and decide what to do with each repository."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from gitpair.config import Config, RepoOptions
from gitpair.hosts import CommandError, Host

ORIGIN_TIMEOUT = 120


def origin_env(host: Host, path: str) -> dict[str, str]:
    """Environment for git commands that reach ``origin``.

    Accessing origin must never hang on a password prompt. LC_ALL keeps git
    messages in English, since some errors are recognized by their text.
    ``core.sshCommand`` (used to pick a key for GitHub, for example) is kept
    and extended with ``BatchMode=yes`` rather than replaced.
    """
    try:
        ssh_command = host.git(path, "config", "--get", "core.sshCommand")
    except CommandError:
        ssh_command = ""
    return {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_SSH_COMMAND": f"{ssh_command or 'ssh'} -o BatchMode=yes",
        "LC_ALL": "C",
    }


class Action(StrEnum):
    SKIP = "skip"
    KEEP = "keep"
    PULL = "pull"
    PUSH = "push"
    MERGE = "merge"
    TAKE_REMOTE = "take-remote"
    TAKE_LOCAL = "take-local"
    CLONE_HERE = "clone-here"
    CLONE_THERE = "clone-there"
    TRACK = "track"
    IGNORE = "ignore"

    def describe(self, local: str, remote: str) -> str:
        return DESCRIPTIONS[self].format(local=local, remote=remote)


DESCRIPTIONS = {
    Action.SKIP: "skip for now",
    Action.KEEP: "commits already in sync",
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

NO_CHANGE = {Action.SKIP, Action.IGNORE}


@dataclass(frozen=True)
class RepoState:
    path: str
    branch: str | None
    head: str | None
    dirty: bool
    untracked: bool
    origin: str | None

    @classmethod
    def from_scan(cls, root: str, repo: str, data: dict) -> RepoState:
        return cls(path=os.path.join(root, repo), **data)


class Step(StrEnum):
    """Work done after the commits are in sync."""

    FILES_THERE = "files-there"
    FILES_HERE = "files-here"
    ORIGIN = "origin"


@dataclass
class Extra:
    step: Step
    description: str
    files: list[str] = field(default_factory=list)


@dataclass
class Item:
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

    @property
    def needs_decision(self) -> bool:
        return self.choice is None

    @property
    def branch(self) -> str | None:
        state = self.local or self.remote
        return state.branch if state else None


@dataclass
class Plan:
    local: Host
    remote: Host
    items: list[Item] = field(default_factory=list)

    @property
    def pending(self) -> list[Item]:
        return [item for item in self.items if not item.in_sync]


def build(
    config: Config,
    local: Host,
    remote: Host,
    local_scan: dict,
    remote_scan: dict,
    progress: Callable[[Iterable[str]], Iterable[str]] = iter,
) -> Plan:
    repos = local_scan["repos"].keys() | remote_scan["repos"].keys()
    plan = Plan(local, remote)
    for repo in progress(sorted(repos)):
        if config.is_ignored(repo):
            continue
        lstate = state_of(local_scan, repo)
        rstate = state_of(remote_scan, repo)
        new = not config.is_tracked(repo)
        if lstate and rstate:
            item = compare(repo, lstate, rstate, local, remote)
        else:
            item = one_sided(repo, lstate, rstate, local, remote)
        if new:
            mark_new(item)
        elif item.comparable:
            add_extras(item, config.options(repo), local, remote)
        plan.items.append(item)
    return plan


def state_of(scan: dict, repo: str) -> RepoState | None:
    if repo not in scan["repos"]:
        return None
    return RepoState.from_scan(scan["root"], repo, scan["repos"][repo])


def compare(
    repo: str, lstate: RepoState, rstate: RepoState, local: Host, remote: Host
) -> Item:
    item = Item(repo, lstate, rstate, status="", options=[Action.SKIP])
    if not lstate.head or not rstate.head:
        return info(item, "empty repository")
    if not lstate.branch or not rstate.branch:
        return info(item, "detached HEAD")
    if lstate.branch != rstate.branch:
        return info(
            item,
            f"on {lstate.branch} at {local.name}, {rstate.branch} at {remote.name}",
        )
    item.comparable = True
    if lstate.head == rstate.head:
        item.in_sync = True
        return info(item, "in sync")

    try:
        item.ahead, item.behind = divergence(local, remote, lstate, rstate)
    except CommandError as error:
        return info(item, f"fetch failed: {error.stderr}")

    dirty = [
        host.name for host, state in ((local, lstate), (remote, rstate)) if state.dirty
    ]
    if item.ahead and item.behind:
        item.status = f"diverged ({item.ahead} ahead, {item.behind} behind)"
        item.options = [Action.MERGE]
        if not lstate.dirty:
            item.options.append(Action.TAKE_REMOTE)
        if not rstate.dirty:
            item.options.append(Action.TAKE_LOCAL)
        item.options.append(Action.SKIP)
    else:
        action = Action.PUSH if item.ahead else Action.PULL
        count = item.ahead or item.behind
        item.status = f"{'ahead' if item.ahead else 'behind'} by {count}"
        item.options = [action, Action.SKIP]
        if not dirty:
            item.choice = action
    if dirty:
        item.status += f"; dirty on {', '.join(dirty)}"
    return item


def divergence(
    local: Host, remote: Host, lstate: RepoState, rstate: RepoState
) -> tuple[int, int]:
    """Fetch the peer branch and count commits (ahead, behind)."""
    ref = peer_ref(remote, lstate.branch or "")
    local.git(
        lstate.path,
        "fetch", "--quiet", "--no-tags", remote.url(rstate.path),
        f"+refs/heads/{rstate.branch}:{ref}",
        env=remote.peer_env(),
    )  # fmt: skip
    counts = local.git(
        lstate.path, "rev-list", "--left-right", "--count", f"HEAD...{ref}"
    )
    ahead, behind = counts.split()
    return int(ahead), int(behind)


def one_sided(
    repo: str,
    lstate: RepoState | None,
    rstate: RepoState | None,
    local: Host,
    remote: Host,
) -> Item:
    item = Item(repo, lstate, rstate, status="", options=[Action.SKIP])
    state = lstate or rstate
    assert state is not None
    where = local.name if lstate else remote.name
    if not state.head or not state.branch:
        return info(item, f"only on {where}, no branch to clone")
    action = Action.CLONE_THERE if lstate else Action.CLONE_HERE
    item.status = f"only on {where}"
    item.options = [action, Action.SKIP]
    item.choice = action
    return item


def add_extras(item: Item, options: RepoOptions, local: Host, remote: Host) -> None:
    """Plan the copy of ignored files and the push to origin."""
    lstate, rstate = item.local, item.remote
    assert lstate is not None and rstate is not None
    notes = []
    if options.sync_ignored:
        notes += plan_files(item, options.sync_ignored, local, remote)
    if options.autopush and lstate.origin:
        notes += plan_origin(item, local)
    if notes:
        item.status += "; " + "; ".join(notes)
    if item.extras and item.in_sync:
        item.in_sync = False
        item.options = [Action.KEEP, Action.SKIP]
        item.choice = Action.KEEP
    elif notes:
        item.in_sync = False  # show the warning in the plan


def plan_files(
    item: Item, entries: tuple[str, ...], local: Host, remote: Host
) -> list[str]:
    lstate, rstate = item.local, item.remote
    assert lstate is not None and rstate is not None
    tracked = [e for e in entries if not is_ignored_by_git(local, lstate.path, e)]
    entries = tuple(e for e in entries if e not in tracked)
    notes = [f"not ignored by git: {', '.join(tracked)}"] if tracked else []
    if not entries:
        return notes
    try:
        here = local.manifest(lstate.path, list(entries))
        there = remote.manifest(rstate.path, list(entries))
    except CommandError as error:
        return [*notes, f"could not list ignored files: {error.stderr}"]
    to_there, to_here, clashes = compare_files(here, there)
    if to_there:
        item.extras.append(
            Extra(
                Step.FILES_THERE,
                f"copy {count(to_there, 'file')} to {remote.name}",
                to_there,
            )
        )
    if to_here:
        item.extras.append(
            Extra(
                Step.FILES_HERE,
                f"copy {count(to_here, 'file')} to {local.name}",
                to_here,
            )
        )
    if clashes:
        notes.append(f"{count(clashes, 'file')} differ with the same mtime")
    return notes


def is_ignored_by_git(host: Host, path: str, entry: str) -> bool:
    """True when git ignores ``entry``, as a file or as a directory."""
    for candidate in (entry, entry + "/"):
        try:
            host.git(path, "check-ignore", "--quiet", candidate)
        except CommandError:
            continue
        return True
    return False


def compare_files(
    here: dict[str, list[int]], there: dict[str, list[int]]
) -> tuple[list[str], list[str], list[str]]:
    """Split files into (copy there, copy here, same mtime but different)."""
    to_there, to_here, clashes = [], [], []
    for name in sorted(here.keys() | there.keys()):
        mine, theirs = here.get(name), there.get(name)
        if mine == theirs:
            continue
        if theirs is None or mine is not None and mine[1] > theirs[1]:
            to_there.append(name)
        elif mine is None or theirs[1] > mine[1]:
            to_here.append(name)
        else:
            clashes.append(name)
    return to_there, to_here, clashes


def plan_origin(item: Item, local: Host) -> list[str]:
    lstate, rstate = item.local, item.remote
    assert lstate is not None and rstate is not None
    extra = Extra(Step.ORIGIN, "push to origin")
    if not item.in_sync:
        # The final commit depends on the chosen action: check when applying.
        item.extras.append(extra)
        return []
    try:
        state = origin_state(local, lstate.path, lstate.branch or "")
    except CommandError as error:
        return [f"could not fetch origin: {error.stderr}"]
    if state == "behind":
        item.extras.append(extra)
    elif state == "diverged":
        return ["origin has diverged"]
    return []


def origin_state(local: Host, path: str, branch: str) -> str:
    """Compare HEAD with origin: "up-to-date", "behind" or "diverged".

    Fetches ``refs/heads/<branch>`` explicitly (so a tag with the same name
    is never picked) and compares against ``FETCH_HEAD`` rather than
    ``refs/remotes/origin/<branch>``, which is only updated when
    ``remote.origin.fetch`` is configured.
    """
    try:
        local.run(
            [
                "git", "-C", path, "fetch", "--quiet", "--no-tags", "origin",
                f"refs/heads/{branch}",
            ],
            env=origin_env(local, path),
            timeout=ORIGIN_TIMEOUT,
        )  # fmt: skip
    except CommandError as error:
        if "couldn't find remote ref" in error.stderr:
            return "behind"  # the branch does not exist on origin yet
        raise
    if is_ancestor(local, path, "HEAD", "FETCH_HEAD"):
        return "up-to-date"
    if is_ancestor(local, path, "FETCH_HEAD", "HEAD"):
        return "behind"
    return "diverged"


def is_ancestor(host: Host, path: str, commit: str, of: str) -> bool:
    try:
        host.git(path, "merge-base", "--is-ancestor", commit, of)
    except CommandError:
        return False
    return True


def count(items: list, noun: str) -> str:
    return f"{len(items)} {noun}{'' if len(items) == 1 else 's'}"


def describe(item: Item, local: str, remote: str) -> str:
    """The chosen action followed by the extra steps."""
    if item.choice is None:
        return "?"
    text = item.choice.describe(local, remote)
    if item.choice in NO_CHANGE or not item.extras:
        return text
    return " + ".join([text, *(extra.description for extra in item.extras)])


def mark_new(item: Item) -> None:
    """Repositories missing from the config always need a decision."""
    item.new = True
    item.in_sync = False
    item.choice = None
    item.status = f"new, {item.status}"
    if item.options == [Action.SKIP]:
        item.options = [Action.TRACK, Action.SKIP]
    item.options.insert(-1, Action.IGNORE)


def info(item: Item, status: str) -> Item:
    item.status = status
    item.options = [Action.SKIP]
    item.choice = Action.SKIP
    return item


def peer_ref(remote: Host, branch: str) -> str:
    return f"refs/gitpair/{remote.name}/{branch}"
