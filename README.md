# gitpair

[![CI](https://github.com/fabiommendes/gitpair/actions/workflows/ci.yml/badge.svg)](https://github.com/fabiommendes/gitpair/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gitpair.svg)](https://pypi.org/project/gitpair/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Keep the git repositories of two machines in sync over ssh.

You work on a desktop and a laptop. Both have a `~/git` folder with mostly the
same repositories, and you keep forgetting to push on one machine before
leaving it. gitpair connects to the other machine, compares every repository
on both sides and builds a plan:

- Repositories where one side is simply ahead on the same branch are
  fast-forwarded automatically.
- Diverged branches, dirty work trees and repositories it has never seen before
  are shown in a terminal UI where you decide what to do.
- Nothing goes through GitHub or any other server. Commits travel directly
  between the two machines, so unpushed and private work is synced too.

The configuration file is the same on both machines. gitpair figures out which
host it is running on and treats the other one as the remote.

## Installation

gitpair needs Python 3.11+ on the machine where you run it. The other machine
only needs `git` (2.28+), `python3` and an ssh server.

```sh
uv tool install gitpair
# or
pipx install gitpair
```

## Quick start

1. Make sure each machine can reach the other with `ssh <name>` without a
   password prompt (key authentication, and optionally an entry in
   `~/.ssh/config`).

2. Create the config and edit it:

   ```sh
   gitpair init
   $EDITOR ~/.config/gitpair/config.toml
   ```

   ```toml
   [hosts.desktop]
   ssh = "desktop.local"   # how the other machine reaches this one
   root = "~/git"          # where repositories live on this host

   [hosts.laptop]
   ssh = "laptop.local"
   root = "~/git"

   [repos]
   track = []
   ignore = ["archived/*"]
   ```

3. Copy the same file to the other machine.

4. Run it:

   ```sh
   gitpair plan   # show what would happen; never touches branches, work
                  # trees, uncommitted files or origin (see below)
   gitpair        # review the plan in the terminal UI and apply it
   ```

`gitpair plan` never touches branches, work trees, uncommitted files or
`origin`. It does fetch each repository's peer branch into
`refs/gitpair/<host>/<branch>` and update `FETCH_HEAD`, which is how it
counts commits ahead/behind; see
[docs/how-it-works.md](docs/how-it-works.md).

In the terminal UI, press `enter` on a row to answer its question, `a` to accept
the first option, `s` to skip, `x` to run the plan and `q` to quit without
changing anything. Rows you leave unanswered are skipped.

`gitpair plan` and the terminal UI show each repository's status and action as
icons, to keep the table narrow: `↑`/`↓` ahead or behind, `⇅` diverged, `✎`
dirty, `✚` new, `→`/`←` only on one host, `✗` git error, `∅` empty repository
or no branch to sync, `⚑` conflicting ignored files; `▶` for an action that
will run as shown, `?` for one that still needs a decision, `–` for skip. A
legend for the icons used in the current table is printed under it. Use
`gitpair plan --plain` for ASCII letters instead, in scripts or terminals
without unicode support.

For cron jobs or shell hooks, `gitpair sync --auto` applies only the automatic
actions and never asks.

## What gitpair does with each repository

| Situation                                        | Default                        | Other options                            |
| :----------------------------------------------- | :----------------------------- | :--------------------------------------- |
| Same commit on both hosts                        | nothing                        |                                          |
| Same branch, one side ahead, both trees clean    | fast-forward the other side    |                                          |
| Same branch, one side ahead, a dirty work tree   | ask                            | fast-forward, skip                       |
| Same branch, diverged                            | ask                            | merge, reset either side, skip           |
| Different branches checked out, or detached HEAD | skip and report                |                                          |
| Tracked repository missing on one host           | clone it there                 |                                          |
| Repository not in the config                     | ask                            | sync and track, ignore forever, skip     |

Resets keep the old commit in `refs/gitpair/backup/<branch>`. Fast-forwards use
`git merge --ff-only`, so git refuses to touch uncommitted changes that
would be overwritten.

## Per-repository options

```toml
[repo."work/api"]
sync_ignored = [".env", "data/fixtures"]   # gitignored paths copied with ssh
autopush = true                            # push to origin when it is behind
```

- `sync_ignored` copies files that git ignores (secrets, local data, build
  caches you do not want to rebuild) between the hosts. A file missing on one
  side is copied there automatically. A file present on both sides with a
  different size or mtime is a conflict: gitpair asks, offering "newer wins"
  (copy each conflicting file in the direction of the newer mtime) or skip
  the conflicting files (the one-sided files are still copied). In `--auto`,
  conflicts are skipped and the one-sided copies still run. Same mtime but a
  different size is only a warning; it is never copied. Deleted files are
  never deleted on the other host.
- `autopush` pushes the synced branch to `origin` when origin is behind. It
  never forces: if origin has diverged, gitpair reports it and does nothing.

Declaring a `[repo."..."]` table also tracks the repository.
`settings.autopush = true` turns autopush on for every repository.

When you track or ignore a new repository, gitpair updates the config file and
copies it to the other host, unless the copy there was edited separately. See
[docs/configuration.md](docs/configuration.md) for all settings and
[docs/how-it-works.md](docs/how-it-works.md) for the git commands behind each
action.

## Commands

```text
gitpair [--config PATH] [--as HOST] [--remote HOST] [sync [--auto] | plan [--plain] | init]
```

- `--config`: config file. Defaults to `$GITPAIR_CONFIG` or
  `~/.config/gitpair/config.toml`.
- `--as`: name of the current host, when the hostname does not match the config.
- `--remote`: host to sync with. Only required when the config lists more than
  two hosts.
- `plan --plain`: ASCII letters instead of unicode icons in the table.

## Contributing

Bug reports and pull requests are welcome. Read
[CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

[MIT](LICENSE)
