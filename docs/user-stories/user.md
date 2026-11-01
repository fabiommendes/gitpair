---
type: stories
status: active
role: user
---

# User user stories

A developer with the same git repositories on two machines, usually a desktop
and a laptop, who runs gitpair on either one over ssh. The user owns both
machines and the shared config.

## Setting up and running

### Create the config file

    status: implemented

The user installed gitpair and has no config yet. They run `gitpair init`,
which writes a commented template once and never overwrites an existing file,
and then fill in the two hosts and their roots.

### Preview a sync without changing anything

    status: implemented

Before letting gitpair act, the user wants to see what it would do. They run
`gitpair plan` and read a table with the status and action of each
repository. Branches, work trees, uncommitted files and origin stay untouched.
`--plain` prints ASCII instead of icons.

### Use one config file on both machines

    status: implemented
    relatedTo: [adr/0007]

The user wants to keep a single config for both machines. They copy the same
file to each one; gitpair finds the local host by its hostname, or by `--as`,
and treats the other host as the remote.

### Sync unattended from a cron job

    status: implemented
    relatedTo: [adr/0005]

The user wants the machines kept in sync without sitting at the terminal. They
run `gitpair sync --auto` from cron or a shell hook; it runs only the automatic
actions, skips everything that needs a decision, and never asks.

## Syncing commits

### Get the other machine's new commits

    status: implemented

The user committed on the other machine and left it. On this machine, gitpair
sees the same branch behind with clean work trees and fast-forwards it without
asking.

### Keep a dirty work tree safe

    status: implemented

One side is ahead but the other has uncommitted changes. gitpair asks before
fast-forwarding, and git refuses to overwrite changes that would conflict, so
the user's uncommitted work is never lost.

### Resolve diverged branches

    status: implemented

The user committed on both machines without syncing. gitpair asks what to do:
merge the two sides, take one side and reset the other (keeping the replaced
commit in a backup ref), or skip. The user answers in the terminal UI and runs
the plan.

### Send my new commits to the other machine

    status: implemented
    relatedTo: [adr/0002]

The user committed here and is about to leave. gitpair pushes the commits to
the other machine and fast-forwards its branch there, even when that branch is
checked out, without the other machine connecting back.

## Repositories

### Clone a repository missing on one machine

    status: implemented

The user tracks a repository that exists on only one machine. gitpair clones
it to the other one, pointing its origin at the same URL, without asking.

### Track or ignore a new repository

    status: implemented
    relatedTo: [adr/0005]

The user created a repository that is not in the config. gitpair always asks:
sync and track it, ignore it forever, or skip it this time. The answer is
written to the config and copied to the other machine.

## Ignored files

### Copy gitignored files between machines

    status: implemented
    relatedTo: [adr/0003, adr/0004]

The user keeps files git ignores, such as `.env` or local data, and wants
them on both machines. They list them in `sync_ignored`; gitpair copies the
files missing on one side and asks before copying a file changed on both.
Deleted files are copied back, never deleted on the other machine.
