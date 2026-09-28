# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-28

### Added

- `gitpair plan`, `gitpair sync` (terminal UI or `--auto`) and `gitpair init`.
- Shared config with automatic detection of the local host.
- Automatic fast-forward in both directions when one host is ahead on the
  checked out branch and both work trees are clean.
- Questions for dirty work trees, diverged branches and repositories missing
  from the config: merge, reset either side with a backup ref, clone, track,
  ignore or skip.
- Clone of tracked repositories that exist on only one host.
- Track and ignore decisions written back to the config and copied to the
  other host.
- Per-repository options in `[repo."<path>"]` tables:
  - `sync_ignored`: copy gitignored files and directories between hosts,
    deletions are not propagated.
  - `autopush`: fast-forward `origin` after syncing, never forcing. Global
    default in `settings.autopush`.
- Config values are now type-checked on load (`depth` an int, `push_config`,
  `autopush` and per-repo `autopush` booleans, `sync_ignored` a list of
  strings, host tables with string fields); a wrong type raises `ConfigError`
  naming the key.

### Changed

- `sync_ignored`: a file present on both hosts with a different size or
  mtime is now a conflict and asks before copying, instead of always copying
  the newer one. The choices are "newer wins" (the previous behavior) or
  skip the conflicting files; the one-sided copies stay automatic. `--auto`
  skips conflicts and still runs the safe part.
- `Action.KEEP` is renamed to `Action.NONE` ("no git changes"), to make clear
  that only the extra steps (copying files, pushing to origin) run for it.
- Clarified that `gitpair plan` fetches into `refs/gitpair/*` and updates
  `FETCH_HEAD`; it does not touch branches, work trees, uncommitted files or
  `origin` (the README used to say it changes nothing at all).
- `gitpair plan` and the terminal UI's plan table are more compact: a new
  leading column shows the repository's status as icons (in sync, ahead,
  behind, diverged, dirty, new, only on one host, git error, empty/no
  branch, conflicting ignored files), and the "Action" column shows an icon
  (automatic, needs a decision, or skip) followed by a short label instead
  of the full sentence. A legend for the icons used in the table is printed
  under it. `gitpair plan --plain` uses ASCII letters instead, for scripts
  and terminals without unicode support.

### Fixed

- `--as` and `--remote` are now accepted both before and after the
  subcommand (`gitpair --remote c3po plan` and `gitpair plan --remote c3po`).
- ssh connections to the peer now time out after 10s instead of hanging on a
  powered-off machine.
- Autopush now keeps the user's own `core.sshCommand` (used to pick an ssh
  key, for example) instead of overriding it.
- Fixed autopush wrongly reporting `origin` as diverged when `origin` has no
  `remote.<name>.fetch` refspec configured.
- A `.git` directory with no usable content (for example an empty directory
  left behind by a failed clone) is no longer treated as a repository, and a
  directory where git itself fails is no longer reported as "empty
  repository". Both are now listed with the git error as their status, and
  neither offers to track the repository, only ignore or skip.
- Push and take-local now delete the scratch `refs/gitpair/incoming/<branch>`
  ref on the remote even when the fast-forward or reset that follows it
  fails, instead of leaving it behind.

[Unreleased]: https://github.com/fabiommendes/gitpair/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/fabiommendes/gitpair/releases/tag/v0.1.0
