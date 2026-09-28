---
type: doc
status: active
tags: [gitpair, glossary, vocabulary]
relatedTo: [gitpair]
---

# Glossary

Keep entries short and in alphabetical order. Use these terms in code, docs and
UI text. Ask the human before adding a new term defined in a conversation.

## Action

What gitpair does to one repository: `pull`, `push`, `merge`, `take-local`,
`take-remote`, `clone-here`, `clone-there`, `track`, `ignore`, `none` or
`skip`. `plan.Action` in code.

## Automatic action

An action gitpair runs without asking: a fast-forward between clean work trees
on the same branch, or cloning a tracked repository that is missing on one
host. The only actions `--auto` runs.

## Backup ref

`refs/gitpair/backup/<branch>`. The HEAD that a `take-local` or `take-remote`
reset replaced.

## Conflict

An ignored file listed in `sync_ignored`, present on both hosts with a
different `[size, mtime]`. Not copied until the item's `files_policy` is
decided: "newer wins" or skip. Same mtime but a different size is a warning
instead, never copied. `Item.file_conflicts` in code.

## Dirty

A work tree with uncommitted changes to tracked files. Untracked files do not
make a repository dirty.

## Extra step

Work done for a repository after its action: copy ignored files to either
host, or push to origin. `plan.Extra` and `plan.Step` in code. Skipped
together with the repository.

## Files policy

How to handle conflicting ignored files for one item: `newer-wins` (copy
each conflict in the direction of the newer mtime) or `skip-conflicts`
(leave conflicts alone, still copy the one-sided files). `plan.FilesPolicy`
in code, `Item.files_policy`.

## Host

One machine in the config (`[hosts.<name>]`). During a run, one host is the
local host and another is the remote host.

## Ignored files

Files and directories listed in a repository's `sync_ignored` option. git
ignores them, gitpair copies them between hosts.

## Incoming ref

`refs/gitpair/incoming/<branch>`. Scratch ref on the remote host that receives
pushed commits before the remote fast-forwards from it. Deleted after use.

## Item

One row of the plan: a repository, its state on both hosts, a status line, the
options offered and the chosen action. `plan.Item` in code.

## Local host

The host gitpair is running on, detected by matching the machine hostname with
`hostname` in the config, or chosen with `--as`.

## New repository

A repository found on a host that is in neither `repos.track` nor
`repos.ignore`. Always requires a decision.

## None

The action for a repository whose commits are already in sync but that has
extra steps to run: no git changes, only the extras.

## Peer ref

`refs/gitpair/<host>/<branch>`. The remote branch as fetched into the local
repository during planning.

## Plan

The list of items built from both scans. Reviewed in the UI, then applied.

## Remote host

The host gitpair connects to over ssh. With two hosts in the config, the one
that is not local.

## Root

Directory that holds the repositories on a host (`root` in the config).
Repositories are identified by their path relative to it.

## Tracked repository

A repository listed in `repos.track`. Synced without questions when the
action is automatic.
