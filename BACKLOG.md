---
type: plan
status: active
tags: [gitpair, backlog, known-limitations]
relatedTo: [gitpair]
---

# Backlog

Unscheduled work and known limitations. Items are grouped by topic, not by
priority. Move items to [ROADMAP.md](ROADMAP.md) when they get a release.

## Known limitations

* [ ] Only the checked out branch is compared. Other branches are ignored
  unless the repository is cloned.
* [ ] Different branches checked out on each host are reported and skipped.
  Could offer to check out the same branch on one side.
* [ ] When the remote config differs from the local one, gitpair refuses to
  overwrite it and asks the user to copy it by hand. A three-way merge of the
  `repos` lists would remove most of these cases.
* [ ] More than two hosts are supported only pairwise (`--remote`). There is no
  "sync all hosts" mode.
* [ ] `clone-there` needs git 2.28+ on the remote (`git init --initial-branch`).

* [ ] Ignored files: deletions are not propagated, and conflicts are decided
  by mtime only. A per-host record of the last synced manifest would allow
  real deletions and conflict detection.
* [ ] Ignored files of a repository are only copied from the second run after
  it is cloned to a host.
* [ ] `autopush` pushes from the local host only. If only the remote has
  credentials for origin, it fails.
* [ ] No lock against two runs happening on both hosts at the same time: the
  forced push to `refs/gitpair/incoming/<branch>` can collide.

## Testing

* [ ] `RemoteHost` is only unit-tested. Add an optional integration test that
  runs against `ssh localhost` when `GITPAIR_SSH_TEST=1` is set.

## UI

* [ ] Show the commit list (`git log --oneline`) of the incoming commits in the
  question dialog.
* [ ] Show in-sync repositories behind a toggle.
* [ ] The "copy N files" text in an extra step is computed before the files
  policy is chosen, so with `skip conflicting files` it can count files that
  are not copied. Compute the description from `resolved_files` instead.

## From the 2026-09-28 review

* [ ] Optional integration test against `ssh localhost` behind an environment
  variable, so `run_binary`, `host:/path` URLs and the config copy run through
  the real ssh path in CI-like conditions (review item T4).
* [ ] Decide whether the project needs a `docs` task (doc-zero) or the README
  plus `docs/` are enough (review item P5).
