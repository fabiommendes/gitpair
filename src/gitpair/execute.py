"""Apply the actions chosen for each item of a plan."""

from __future__ import annotations

import contextlib
import shlex
import tarfile
import tempfile

from gitpair.hosts import CommandError, Host
from gitpair.plan import (
    ORIGIN_TIMEOUT,
    Action,
    Item,
    Plan,
    RepoState,
    Step,
    origin_env,
    origin_state,
    peer_ref,
    resolved_files,
)

__all__ = ["apply"]

INCOMING = "refs/gitpair/incoming/{branch}"
BACKUP = "refs/gitpair/backup/{branch}"


def apply(plan: Plan, item: Item) -> None:
    """Run ``item``'s chosen action, then its extra steps.

    Args:
        plan: source of the ``local``/``remote`` hosts to run commands on.
        item: the repository and the action already chosen for it.

    Raises:
        CommandError: a step failed. A file removed on either side between
            planning and applying (``_copy_there`` and ``_copy_here`` read
            the filesystem again) raises ``OSError``, which is converted
            to a ``CommandError`` so one missing file does not abort the
            whole run.
    """
    local, remote = plan.local, plan.remote
    try:
        match item.choice:
            case Action.PULL:
                _pull(local, remote, _need(item.local), _need(item.remote))
            case Action.PUSH:
                _push(local, remote, _need(item.local), _need(item.remote))
            case Action.MERGE:
                _merge(local, remote, _need(item.local), _need(item.remote))
            case Action.TAKE_REMOTE:
                _take_remote(local, remote, _need(item.local))
            case Action.TAKE_LOCAL:
                _take_local(local, remote, _need(item.local), _need(item.remote))
            case Action.CLONE_HERE:
                _clone_here(local, remote, item.repo, _need(item.remote))
            case Action.CLONE_THERE:
                _clone_there(local, remote, item.repo, _need(item.local))
        for extra in item.extras:
            match extra.step:
                case Step.FILES_THERE:
                    if files := resolved_files(item, extra):
                        _copy_there(
                            local, remote, _need(item.local), _need(item.remote), files
                        )
                case Step.FILES_HERE:
                    if files := resolved_files(item, extra):
                        _copy_here(
                            local, remote, _need(item.local), _need(item.remote), files
                        )
                case Step.ORIGIN:
                    _push_origin(local, _need(item.local))
    except OSError as error:
        raise CommandError(local.name, ["apply", item.repo], str(error)) from error


#
# Internals
#


def _copy_there(
    local: Host, remote: Host, lstate: RepoState, rstate: RepoState, files: list[str]
) -> None:
    with tempfile.TemporaryFile() as archive:
        with tarfile.open(fileobj=archive, mode="w") as tar:
            for name in files:
                tar.add(f"{lstate.path}/{name}", arcname=name, recursive=False)
        archive.seek(0)
        remote.run_binary(["tar", "-x", "-f", "-", "-C", rstate.path], stdin=archive)


def _copy_here(
    local: Host, remote: Host, lstate: RepoState, rstate: RepoState, files: list[str]
) -> None:
    with tempfile.TemporaryFile() as archive:
        remote.run_binary(
            ["tar", "-c", "-f", "-", "-C", rstate.path, "--null", "-T", "-"],
            input="\0".join(files).encode(),
            stdout=archive,
        )
        archive.seek(0)
        with tarfile.open(fileobj=archive, mode="r") as tar:
            # The "data" filter rejects absolute paths, ".." and special files.
            tar.extractall(lstate.path, filter="data")


def _push_origin(local: Host, lstate: RepoState) -> None:
    """Fast-forward origin to HEAD. Never forces.

    Raises:
        CommandError: origin has diverged, or the push itself failed.
    """
    branch = lstate.branch or ""
    state = origin_state(local, lstate.path, branch)
    if state == "diverged":
        raise CommandError(
            local.name,
            ["git", "push", "origin", branch],
            "origin has diverged, not pushing",
        )
    if state == "behind":
        local.run(
            [
                "git",
                "-C",
                lstate.path,
                "push",
                "--quiet",
                "origin",
                f"HEAD:refs/heads/{branch}",
            ],
            env=origin_env(local, lstate.path),
            timeout=ORIGIN_TIMEOUT,
        )


def _pull(local: Host, remote: Host, lstate: RepoState, rstate: RepoState) -> None:
    local.git(lstate.path, "merge", "--ff-only", "--quiet", _ref_for(remote, lstate))


def _push(local: Host, remote: Host, lstate: RepoState, rstate: RepoState) -> None:
    incoming = _send(local, remote, lstate, rstate.path)
    try:
        remote.git(rstate.path, "merge", "--ff-only", "--quiet", incoming)
    finally:
        _delete_incoming(remote, rstate.path, incoming)


def _merge(local: Host, remote: Host, lstate: RepoState, rstate: RepoState) -> None:
    try:
        local.git(
            lstate.path, "merge", "--no-edit", "--quiet", _ref_for(remote, lstate)
        )
    except CommandError:
        _abort_merge(local, lstate)
        raise
    _push(local, remote, lstate, rstate)


def _abort_merge(local: Host, lstate: RepoState) -> None:
    # The merge may never have started, e.g. when a dirty work tree blocked it.
    with contextlib.suppress(CommandError):
        local.git(lstate.path, "merge", "--abort")


def _take_remote(local: Host, remote: Host, lstate: RepoState) -> None:
    backup = BACKUP.format(branch=lstate.branch)
    local.git(lstate.path, "update-ref", backup, "HEAD")
    local.git(lstate.path, "reset", "--hard", "--quiet", _ref_for(remote, lstate))


def _take_local(
    local: Host, remote: Host, lstate: RepoState, rstate: RepoState
) -> None:
    incoming = _send(local, remote, lstate, rstate.path)
    try:
        remote.git(
            rstate.path, "update-ref", BACKUP.format(branch=rstate.branch), "HEAD"
        )
        remote.git(rstate.path, "reset", "--hard", "--quiet", incoming)
    finally:
        _delete_incoming(remote, rstate.path, incoming)


def _clone_here(local: Host, remote: Host, repo: str, rstate: RepoState) -> None:
    path = _target_path(local, repo)
    local.run(
        ["git", "clone", "--quiet", remote.url(rstate.path), path],
        env=remote.peer_env(),
    )
    if rstate.origin:
        local.git(path, "remote", "set-url", "origin", rstate.origin)
    else:
        local.git(path, "remote", "remove", "origin")


def _clone_there(local: Host, remote: Host, repo: str, lstate: RepoState) -> None:
    path = _target_path(remote, repo)
    remote.shell(f"test ! -e {shlex.quote(path)}")
    remote.run(["git", "init", "--quiet", "--initial-branch=gitpair-init", path])
    local.git(
        lstate.path,
        "push", "--quiet", remote.url(path),
        "refs/heads/*:refs/heads/*", "refs/tags/*:refs/tags/*",
        env=remote.peer_env(),
    )  # fmt: skip
    remote.git(path, "symbolic-ref", "HEAD", f"refs/heads/{lstate.branch}")
    remote.git(path, "reset", "--hard", "--quiet")
    if lstate.origin:
        remote.git(path, "remote", "add", "origin", lstate.origin)


def _send(local: Host, remote: Host, lstate: RepoState, rpath: str) -> str:
    """Push the local branch to a scratch ref on the peer and return the ref.

    Pushing to the checked out branch of a non-bare repository is refused by
    git, so the peer fast-forwards from the scratch ref instead.
    """
    incoming = INCOMING.format(branch=lstate.branch)
    local.git(
        lstate.path,
        "push", "--quiet", "--force", remote.url(rpath),
        f"refs/heads/{lstate.branch}:{incoming}",
        env=remote.peer_env(),
    )  # fmt: skip
    return incoming


def _delete_incoming(remote: Host, rpath: str, incoming: str) -> None:
    """Delete the scratch ref left by :func:`_send`, even after a failure.

    Suppresses a ``CommandError`` from the delete itself so a fast-forward or
    reset failure is what gets reported, not a follow-up cleanup error.
    """
    with contextlib.suppress(CommandError):
        remote.git(rpath, "update-ref", "-d", incoming)


def _ref_for(remote: Host, lstate: RepoState) -> str:
    return peer_ref(remote, lstate.branch or "")


def _target_path(host: Host, repo: str) -> str:
    return f"{host.root}/{repo}"


def _need(state: RepoState | None) -> RepoState:
    assert state is not None
    return state
