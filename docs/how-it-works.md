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
   `sync_ignored` on both hosts and check whether `origin` is behind.
4. **Decide.** The terminal UI lists everything that is not in sync. Safe
   actions are preselected; the rest wait for an answer.
5. **Apply.** Run the chosen actions and their extra steps (copy ignored
   files, push to origin), then record new `track` and `ignore`
   entries in the config.

All commands run from the local machine. The remote never needs to open a
connection back, which matters when the local host is a laptop behind NAT.

ssh connections are multiplexed (`ControlMaster=auto`, socket in
`~/.ssh/gitpair-%C`), so a run opens one TCP connection to the remote.

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
- `refs/gitpair/backup/<branch>`: commit that a reset replaced.

They do not show up in `git branch` and are never pushed to other remotes.
Remove them with `git for-each-ref --format='%(refname)' refs/gitpair | xargs -n1 git update-ref -d`.
