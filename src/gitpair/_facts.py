"""Gather plain facts about both hosts: all the I/O, no decisions.

Every function here that reaches a host either returns data or, for the
failures the plan can still report (a failed fetch, a failed manifest
listing, a failed origin check), captures the error as a fact instead of
raising. :mod:`gitpair._decide` turns those facts into the plan.

Implements symbols re-exported by :mod:`gitpair.plan`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from gitpair._model import RepoState
from gitpair.config import Config, RepoOptions
from gitpair.hosts import CommandError, Host

ORIGIN_TIMEOUT = 120


def gather(
    config: Config,
    local: Host,
    remote: Host,
    local_scan: dict,
    remote_scan: dict,
    progress: Callable[[Iterable[str]], Iterable[str]] = iter,
) -> list[RepoFacts]:
    """Run every host command the plan needs and collect the results.

    Args:
        local_scan: result of ``local.scan(config.depth)``.
        remote_scan: result of ``remote.scan(config.depth)``.
        progress: wraps the sorted repository names while gathering, e.g.
            to drive a progress indicator. Must yield the same names it
            is given.

    Returns:
        One :class:`RepoFacts` per repository not ignored by ``config``.
    """
    repos = local_scan["repos"].keys() | remote_scan["repos"].keys()
    facts = []
    for repo in progress(sorted(repos)):
        if config.is_ignored(repo):
            continue
        facts.append(_gather_repo(config, local, remote, local_scan, remote_scan, repo))
    return facts


def origin_env(host: Host, path: str) -> dict[str, str]:
    """Environment for git commands that reach ``origin``.

    Accessing origin must never hang on a password prompt. ``LC_ALL`` keeps
    git messages in English, since some errors are recognized by their
    text. ``core.sshCommand`` (used to pick a key for GitHub, for example)
    is kept and extended with ``BatchMode=yes`` rather than replaced.
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


def origin_state(local: Host, path: str, branch: str) -> str:
    """Compare HEAD with origin: ``"up-to-date"``, ``"behind"`` or ``"diverged"``.

    Fetches ``refs/heads/<branch>`` explicitly (so a tag with the same name
    is never picked) and compares against ``FETCH_HEAD`` rather than
    ``refs/remotes/origin/<branch>``, which is only updated when
    ``remote.origin.fetch`` is configured.

    Raises:
        CommandError: the fetch failed for a reason other than the branch
            not existing on origin yet (which is reported as ``"behind"``).
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
    if _is_ancestor(local, path, "HEAD", "FETCH_HEAD"):
        return "up-to-date"
    if _is_ancestor(local, path, "FETCH_HEAD", "HEAD"):
        return "behind"
    return "diverged"


def peer_ref(remote: Host, branch: str) -> str:
    """Ref name used to fetch ``branch`` from ``remote`` without touching local refs.

    >>> from gitpair.config import HostConfig
    >>> host = Host(HostConfig(name="there", hostname="there", ssh="there", root="~"))
    >>> peer_ref(host, "main")
    'refs/gitpair/there/main'
    """
    return f"refs/gitpair/{remote.name}/{branch}"


#
# Facts
#


class CompareOutcome(StrEnum):
    """Why a repository present on both hosts is, or is not, comparable."""

    GIT_ERROR = "git-error"
    EMPTY = "empty"
    DETACHED = "detached"
    BRANCH_MISMATCH = "branch-mismatch"
    IN_SYNC = "in-sync"
    FETCH_FAILED = "fetch-failed"
    COMPARED = "compared"


@dataclass(frozen=True)
class CompareFacts:
    """Facts from comparing a repository present on both hosts."""

    outcome: CompareOutcome
    ahead: int = 0
    behind: int = 0
    error: str | None = None


@dataclass(frozen=True)
class IgnoredFilesFacts:
    """Facts needed to decide which ignored files to copy.

    ``here`` and ``there`` are ``None`` when no entry was left to compare
    (everything was ``not_ignored``) or when listing them failed.
    """

    not_ignored: tuple[str, ...] = ()
    here: dict[str, list[int]] | None = None
    there: dict[str, list[int]] | None = None
    error: str | None = None


@dataclass(frozen=True)
class OriginFacts:
    """Facts about the repository's relationship with ``origin``.

    ``checked`` is false when the item was not in sync at gathering time:
    the final commit pushed to origin depends on the action the user picks,
    so the check is deferred to apply time.
    """

    checked: bool = False
    state: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ExtrasFacts:
    """Facts for the extra steps run once commits are in sync."""

    ignored_files: IgnoredFilesFacts | None = None
    origin: OriginFacts | None = None


@dataclass(frozen=True)
class RepoFacts:
    """Everything gathered for one repository, before any decision is made."""

    repo: str
    local: RepoState | None
    remote: RepoState | None
    compare: CompareFacts | None = None
    extras: ExtrasFacts = field(default_factory=ExtrasFacts)


#
# Internals
#


def _gather_repo(
    config: Config,
    local: Host,
    remote: Host,
    local_scan: dict,
    remote_scan: dict,
    repo: str,
) -> RepoFacts:
    lstate = _state_of(local_scan, repo)
    rstate = _state_of(remote_scan, repo)
    compare = None
    comparable = False
    if lstate is not None and rstate is not None:
        compare = _gather_compare(local, remote, lstate, rstate)
        comparable = compare.outcome not in (
            CompareOutcome.GIT_ERROR,
            CompareOutcome.EMPTY,
            CompareOutcome.DETACHED,
            CompareOutcome.BRANCH_MISMATCH,
        )
    extras = ExtrasFacts()
    if comparable and config.is_tracked(repo):
        assert lstate is not None and rstate is not None and compare is not None
        in_sync = compare.outcome is CompareOutcome.IN_SYNC
        extras = _gather_extras(
            local, remote, lstate, rstate, config.options(repo), in_sync
        )
    return RepoFacts(
        repo=repo, local=lstate, remote=rstate, compare=compare, extras=extras
    )


def _state_of(scan: dict, repo: str) -> RepoState | None:
    if repo not in scan["repos"]:
        return None
    return RepoState.from_scan(scan["root"], repo, scan["repos"][repo])


def _gather_compare(
    local: Host, remote: Host, lstate: RepoState, rstate: RepoState
) -> CompareFacts:
    if lstate.error or rstate.error:
        return CompareFacts(CompareOutcome.GIT_ERROR)
    if not lstate.head or not rstate.head:
        return CompareFacts(CompareOutcome.EMPTY)
    if not lstate.branch or not rstate.branch:
        return CompareFacts(CompareOutcome.DETACHED)
    if lstate.branch != rstate.branch:
        return CompareFacts(CompareOutcome.BRANCH_MISMATCH)
    if lstate.head == rstate.head:
        return CompareFacts(CompareOutcome.IN_SYNC)
    try:
        ahead, behind = _divergence(local, remote, lstate, rstate)
    except CommandError as error:
        return CompareFacts(CompareOutcome.FETCH_FAILED, error=error.stderr)
    return CompareFacts(CompareOutcome.COMPARED, ahead=ahead, behind=behind)


def _divergence(
    local: Host, remote: Host, lstate: RepoState, rstate: RepoState
) -> tuple[int, int]:
    """Fetch the peer branch and count commits (ahead, behind).

    Raises:
        CommandError: the fetch or the count failed.
    """
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


def _gather_extras(
    local: Host,
    remote: Host,
    lstate: RepoState,
    rstate: RepoState,
    options: RepoOptions,
    in_sync: bool,
) -> ExtrasFacts:
    ignored_files = None
    if options.sync_ignored:
        ignored_files = _gather_ignored_files(
            local, remote, lstate, rstate, options.sync_ignored
        )
    origin = None
    if options.autopush and lstate.origin:
        origin = _gather_origin(local, lstate, in_sync)
    return ExtrasFacts(ignored_files=ignored_files, origin=origin)


def _gather_ignored_files(
    local: Host,
    remote: Host,
    lstate: RepoState,
    rstate: RepoState,
    entries: tuple[str, ...],
) -> IgnoredFilesFacts:
    not_ignored = tuple(
        e for e in entries if not _is_ignored_by_git(local, lstate.path, e)
    )
    remaining = tuple(e for e in entries if e not in not_ignored)
    if not remaining:
        return IgnoredFilesFacts(not_ignored=not_ignored)
    try:
        here = local.manifest(lstate.path, list(remaining))
        there = remote.manifest(rstate.path, list(remaining))
    except CommandError as error:
        return IgnoredFilesFacts(not_ignored=not_ignored, error=error.stderr)
    return IgnoredFilesFacts(not_ignored=not_ignored, here=here, there=there)


def _is_ignored_by_git(host: Host, path: str, entry: str) -> bool:
    """True when git ignores ``entry``, as a file or as a directory."""
    for candidate in (entry, entry + "/"):
        try:
            host.git(path, "check-ignore", "--quiet", candidate)
        except CommandError:
            continue
        return True
    return False


def _gather_origin(local: Host, lstate: RepoState, in_sync: bool) -> OriginFacts:
    if not in_sync:
        # The final commit depends on the chosen action: check at apply time.
        return OriginFacts(checked=False)
    try:
        state = origin_state(local, lstate.path, lstate.branch or "")
    except CommandError as error:
        return OriginFacts(checked=True, error=error.stderr)
    return OriginFacts(checked=True, state=state)


def _is_ancestor(host: Host, path: str, commit: str, of: str) -> bool:
    try:
        host.git(path, "merge-base", "--is-ancestor", commit, of)
    except CommandError:
        return False
    return True
