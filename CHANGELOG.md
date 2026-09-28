# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
  - `sync_ignored`: copy gitignored files and directories between hosts, newer
    file wins, deletions are not propagated.
  - `autopush`: fast-forward `origin` after syncing, never forcing. Global
    default in `settings.autopush`.

### Fixed

- `--as` and `--remote` are now accepted both before and after the
  subcommand (`gitpair --remote c3po plan` and `gitpair plan --remote c3po`).
- ssh connections to the peer now time out after 10s instead of hanging on a
  powered-off machine.
- Autopush now keeps the user's own `core.sshCommand` (used to pick an ssh
  key, for example) instead of overriding it.
- Fixed autopush wrongly reporting `origin` as diverged when `origin` has no
  `remote.<name>.fetch` refspec configured.
