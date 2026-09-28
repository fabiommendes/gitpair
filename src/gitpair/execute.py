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
)

INCOMING = "refs/gitpair/incoming/{branch}"
BACKUP = "refs/gitpair/backup/{branch}"


def apply(plan: Plan, item: Item) -> None:
    """Run the chosen action. Raises CommandError when a step fails.

    A file removed on either side between planning and applying (``copy_there``
    and ``copy_here`` read the filesystem again) raises ``OSError``; it is
    converted to a ``CommandError`` so one missing file does not abort the
    whole run.
    """
    local, remote = plan.local, plan.remote
    try:
        match item.choice:
            case Action.PULL:
                pull(local, remote, need(item.local), need(item.remote))
            case Action.PUSH:
                push(local, remote, need(item.local), need(item.remote))
            case Action.MERGE:
                merge(local, remote, need(item.local), need(item.remote))
            case Action.TAKE_REMOTE:
                take_remote(local, remote, need(item.local))
            case Action.TAKE_LOCAL:
                take_local(local, remote, need(item.local), need(item.remote))
            case Action.CLONE_HERE:
                clone_here(local, remote, item.repo, need(item.remote))
            case Action.CLONE_THERE:
                clone_there(local, remote, item.repo, need(item.local))
        for extra in item.extras:
            match extra.step:
                case Step.FILES_THERE:
                    copy_there(
                        local, remote, need(item.local), need(item.remote), extra.files
                    )
                case Step.FILES_HERE:
                    copy_here(
                        local, remote, need(item.local), need(item.remote), extra.files
                    )
                case Step.ORIGIN:
                    push_origin(local, need(item.local))
    except OSError as error:
        raise CommandError(local.name, ["apply", item.repo], str(error)) from error


def copy_there(
    local: Host, remote: Host, lstate: RepoState, rstate: RepoState, files: list[str]
) -> None:
    with tempfile.TemporaryFile() as archive:
        with tarfile.open(fileobj=archive, mode="w") as tar:
            for name in files:
                tar.add(f"{lstate.path}/{name}", arcname=name, recursive=False)
        archive.seek(0)
        remote.run_binary(["tar", "-x", "-f", "-", "-C", rstate.path], stdin=archive)


def copy_here(
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


def push_origin(local: Host, lstate: RepoState) -> None:
    """Fast-forward origin to HEAD. Never forces."""
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


def pull(local: Host, remote: Host, lstate: RepoState, rstate: RepoState) -> None:
    local.git(lstate.path, "merge", "--ff-only", "--quiet", ref_for(remote, lstate))


def push(local: Host, remote: Host, lstate: RepoState, rstate: RepoState) -> None:
    incoming = send(local, remote, lstate, rstate.path)
    remote.git(rstate.path, "merge", "--ff-only", "--quiet", incoming)
    remote.git(rstate.path, "update-ref", "-d", incoming)


def merge(local: Host, remote: Host, lstate: RepoState, rstate: RepoState) -> None:
    try:
        local.git(lstate.path, "merge", "--no-edit", "--quiet", ref_for(remote, lstate))
    except CommandError:
        abort_merge(local, lstate)
        raise
    push(local, remote, lstate, rstate)


def abort_merge(local: Host, lstate: RepoState) -> None:
    # The merge may never have started, e.g. when a dirty work tree blocked it.
    with contextlib.suppress(CommandError):
        local.git(lstate.path, "merge", "--abort")


def take_remote(local: Host, remote: Host, lstate: RepoState) -> None:
    backup = BACKUP.format(branch=lstate.branch)
    local.git(lstate.path, "update-ref", backup, "HEAD")
    local.git(lstate.path, "reset", "--hard", "--quiet", ref_for(remote, lstate))


def take_local(local: Host, remote: Host, lstate: RepoState, rstate: RepoState) -> None:
    incoming = send(local, remote, lstate, rstate.path)
    remote.git(rstate.path, "update-ref", BACKUP.format(branch=rstate.branch), "HEAD")
    remote.git(rstate.path, "reset", "--hard", "--quiet", incoming)
    remote.git(rstate.path, "update-ref", "-d", incoming)


def clone_here(local: Host, remote: Host, repo: str, rstate: RepoState) -> None:
    path = target_path(local, repo)
    local.run(
        ["git", "clone", "--quiet", remote.url(rstate.path), path],
        env=remote.peer_env(),
    )
    if rstate.origin:
        local.git(path, "remote", "set-url", "origin", rstate.origin)
    else:
        local.git(path, "remote", "remove", "origin")


def clone_there(local: Host, remote: Host, repo: str, lstate: RepoState) -> None:
    path = target_path(remote, repo)
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


def send(local: Host, remote: Host, lstate: RepoState, rpath: str) -> str:
    """Push the local branch to a scratch ref on the peer and return the ref.

    Pushing to the checked out branch of a non-bare repository is refused by
    git, so the peer fast-forwards from the scratch ref instead."""
    incoming = INCOMING.format(branch=lstate.branch)
    local.git(
        lstate.path,
        "push", "--quiet", "--force", remote.url(rpath),
        f"refs/heads/{lstate.branch}:{incoming}",
        env=remote.peer_env(),
    )  # fmt: skip
    return incoming


def ref_for(remote: Host, lstate: RepoState) -> str:
    return peer_ref(remote, lstate.branch or "")


def target_path(host: Host, repo: str) -> str:
    return f"{host.root}/{repo}"


def need(state: RepoState | None) -> RepoState:
    assert state is not None
    return state
