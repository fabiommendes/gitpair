# How it works

## One run

1. **Pair.** Load the config, find the host whose `hostname` matches this
   machine, and pick the other one as the remote.
2. **Scan.** Run `scanner.py` on both hosts. On the remote, its source is piped
   to `python3 -` over ssh, so nothing has to be installed there. Each scan
   returns the branch, HEAD, dirty state and `origin` URL of every repository.
3. **Plan.** For each repository present on both hosts with different HEADs,
   fetch the remote branch into `refs/gitpair/<remote>/<branch>` and count
   commits on each side with `git rev-list --left-right --count`.
   For repositories with options, also compare the ignored files listed in
   `sync_ignored` on both hosts and check whether `origin` is behind, which
   fetches into `FETCH_HEAD`. `gitpair plan` stops here: it never touches
   branches, work trees, uncommitted files or `origin` itself, but this step
   does write to `refs/gitpair/*` and `FETCH_HEAD`.
4. **Decide.** The terminal UI lists everything that is not in sync. Safe
   actions are preselected; the rest wait for an answer.
5. **Apply.** Run the chosen actions and their extra steps (copy ignored
   files, push to origin), then record new `track` and `ignore`
   entries in the config.

All commands run from the local machine. The remote never needs to open a
connection back, which matters when the local host is a laptop behind NAT.

ssh connections are multiplexed (`ControlMaster=auto`, socket in
`~/.ssh/gitpair-%C`, `ConnectTimeout=10`). Commands run through `RemoteHost`
(scan, `sh`, the extras that use `run_binary`) reuse the control socket
directly. Git commands whose argument is a `user@host:path` URL on the peer
(`fetch`, `push`, `clone`) open their own ssh process, so those additionally
carry a matching `GIT_SSH_COMMAND` to reuse the same control socket. Together
this means a run opens one TCP connection to the remote and authenticates
once, for both the `RemoteHost` traffic and the peer git operations.
Commands to `origin` are unrelated to this socket: they always use a fresh
ssh connection, keeping the user's own `core.sshCommand` if set.

fish, or any other login shell on the remote, works fine: every command sent
over ssh is quoted with `shlex.join`, whose output was tested under `fish -c`
with quotes, backslashes, `$HOME` and `~`. The only difference from a POSIX
shell is a literal double backslash (`\\`) inside the single quotes
`shlex.join` produces, which fish interprets differently.

## Git commands per action

`L` is the local repository, `R` the remote one, `R:` its ssh URL and `b` the
branch.

| Action      | Commands                                                                                                                              |
| :---------- | :------------------------------------------------------------------------------------------------------------------------------------ |
| pull        | on L: `git merge --ff-only refs/gitpair/<remote>/b`                                                                                   |
| push        | on L: `git push --force R: refs/heads/b:refs/gitpair/incoming/b`; on R: `git merge --ff-only refs/gitpair/incoming/b`, delete the ref |
| merge       | on L: `git merge --no-edit refs/gitpair/<remote>/b` (aborted on conflict), then push                                                  |
| take-remote | on L: save HEAD in `refs/gitpair/backup/b`, `git reset --hard refs/gitpair/<remote>/b`                                                |
| take-local  | push to `refs/gitpair/incoming/b`; on R: save HEAD in `refs/gitpair/backup/b`, `git reset --hard` to it                                |
| clone-here  | on L: `git clone R:`, then point `origin` to the remote's `origin` (or remove it)                                                     |
| clone-there | on R: `git init`; on L: push all branches and tags; on R: check out `b`, add `origin`                                                 |

Extra steps, run after the action unless the repository is skipped:

| Step        | Commands                                                                                              |
| :---------- | :---------------------------------------------------------------------------------------------------- |
| files there | on L: build a tar of the newer files (Python `tarfile`); on R: `tar -x -f - -C <repo>`                 |
| files here  | on R: `tar -c -f - -C <repo> --null -T -` with the file list on stdin; on L: extract with the `data` filter |
| origin      | on L: `git fetch origin b`, then `git push origin HEAD:refs/heads/b` if origin is an ancestor of HEAD  |

Pushing straight to `refs/heads/b` would fail when `b` is checked out on the
remote (`receive.denyCurrentBranch`). That is why pushes go to a scratch ref
and the remote fast-forwards from it.

## Refs created by gitpair

- `refs/gitpair/<host>/<branch>`: last fetched state of the peer branch.
- `refs/gitpair/incoming/<branch>`: scratch ref, deleted after use.
- `refs/gitpair/backup/<branch>`: commit that a reset replaced. There is one
  per branch: a second reset overwrites it. The previous HEAD is also in
  `git reflog` for that branch, so it is not the only copy.

They do not show up in `git branch` and are never pushed to other remotes.
Remove them with `git for-each-ref --format='%(refname)' refs/gitpair | xargs -n1 git update-ref -d`.
