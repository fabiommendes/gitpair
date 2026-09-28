# Configuration

gitpair reads a single TOML file. The same file is meant to live on every host.

Location, in order of precedence:

1. `--config PATH`
2. `$GITPAIR_CONFIG`
3. `~/.config/gitpair/config.toml`

A complete example lives in [`examples/config.toml`](../examples/config.toml).

## `[settings]`

| Key           | Default | Description                                                                 |
| :------------ | :------ | :-------------------------------------------------------------------------- |
| `depth`       | `3`     | How many directory levels below `root` to search for repositories.          |
| `push_config` | `true`  | After tracking or ignoring a repository, copy the config to the other host. |
| `autopush`    | `false` | Default for `autopush` in repositories without their own setting.           |

Set `push_config = false` if a dotfile manager (chezmoi, yadm, stow) already
distributes the file. gitpair then only edits the local copy.

## `[hosts.<name>]`

One table per machine. At least two are required.

| Key        | Default   | Description                                                             |
| :--------- | :-------- | :---------------------------------------------------------------------- |
| `ssh`      | required  | ssh destination used to reach this host: `user@host`, or a `Host` alias. |
| `hostname` | `<name>`  | Value compared with the machine hostname to detect the local host.       |
| `root`     | `~/git`   | Directory that holds the repositories on this host.                     |

gitpair compares the short hostname (the part before the first dot) of the
machine with the short form of each `hostname`. Use `--as NAME` when that does
not work, for example inside containers.

Repositories are matched by their path relative to `root`, so the roots may
differ between hosts.

## `[repos]`

| Key      | Description                                                                 |
| :------- | :-------------------------------------------------------------------------- |
| `track`  | Repository paths, relative to `root`, that are synced without questions.    |
| `ignore` | Glob patterns (`fnmatch`) of repositories gitpair must not touch or report. |

Any repository found under `root` that matches neither list is new, and gitpair
asks about it. The answer is written back to this file.

## `[repo."<path>"]`

Options for one repository. The path is relative to `root` and must be quoted
when it contains `/`. Declaring the table also tracks the repository.

| Key            | Default               | Description                                                   |
| :------------- | :-------------------- | :------------------------------------------------------------ |
| `sync_ignored` | `[]`                  | Files or directories ignored by git to copy between hosts.    |
| `autopush`     | `settings.autopush`   | Push the synced branch to `origin` when origin is behind.     |

### `sync_ignored`

Each entry is a path relative to the repository. Entries that git does not
ignore (checked with `git check-ignore`) are skipped with a warning, since git
already syncs them. Paths outside the repository and inside `.git` are
rejected when the config is loaded.

gitpair compares the size and modification time of every regular file under
the entries on both hosts:

- a file present on one host only is copied to the other automatically;
- a file present on both hosts with a different size or mtime is a conflict:
  it is not copied until you decide. gitpair asks for a `files_policy`:
  "newer wins" copies each conflicting file in the direction of the newer
  mtime (the previous, unconditional behavior); "skip conflicts" leaves
  conflicting files alone and still copies the one-sided ones. `--auto`
  treats an undecided policy as skip, so the safe, one-sided copies and the
  git action still run automatically;
- files with the same mtime but different sizes are reported and left alone,
  always, regardless of the policy;
- deletions are not propagated. Delete the file on both hosts.

Symbolic links are skipped. The comparison relies on mtimes, so keep the
clocks of both machines synchronized (NTP).

Files are copied with `tar` over the same ssh connection, after the git
action for that repository. Skipping the repository in the UI also skips the
copy. The `data` extraction filter used on the receiving side drops the
group and other write bits of copied files; `tar -x` on the remote follows
directory symlinks that already exist there.

### `autopush`

After the git action, gitpair fetches the branch from `origin` on the local
host and pushes `HEAD` when origin is behind or does not have the branch.
If origin has commits that the synced branch does not have, gitpair reports
"origin has diverged" and does not push.

Access to origin runs with `GIT_TERMINAL_PROMPT=0` and ssh in batch mode, so
credentials must work without prompts (ssh keys, a credential helper). Each
fetch or push has a two-minute timeout.

## Repository discovery

gitpair walks `root` up to `depth` levels and stops at the first directory
that contains `.git`, so nested repositories and submodules are not reported
separately. Hidden directories and `node_modules`, `__pycache__`, `target`,
`dist` and `build` are skipped. Symlinked directories under `root` are
skipped too.

A repository not yet in `repos.track`, `repos.ignore` or a `[repo."<path>"]`
table is new. Its first run gets no extra steps (`sync_ignored`, `autopush`):
they start applying from the next run, once you have tracked it or given it
a `[repo."<path>"]` table.
