# gitpair

gitpair is a CLI that keeps the git repositories of two machines in sync over
ssh. It scans both hosts, builds a plan, applies safe fast-forwards on its own
and asks the user about everything else in a Textual UI. The config file is
shared by both hosts; the local host is detected at runtime.

Read `README.md` for user-facing behavior and `docs/how-it-works.md` for the git
commands behind each action before changing anything in `plan.py` or
`execute.py`.

## Working with the human

- Be direct and brief. Bullet points over paragraphs. Prefix bullets with an
  identifier (`D1`, `D2`) when you list decisions so they are easy to answer.
- Show at most three open decisions at a time.
- Decide small, reversible things yourself and state the decision in one line.
  Ask only when a choice is hard to undo: config format changes, new refs
  written to users' repositories, anything that can lose commits or work.
- Do not praise ideas. Point out problems.

## Writing style

User-facing text (README, docs, CLI messages, docstrings) is in English, in
plain language. No marketing words, no emojis, no em-dashes. Say what the tool
does, not how great it is.

## Project layout

| Path                         | Description                                                           |
| :--------------------------- | :-------------------------------------------------------------------- |
| `README.md`                  | User documentation and quick start.                                   |
| `docs/`                      | Longer user documentation: configuration and internals.               |
| `examples/config.toml`       | Complete config example. Keep it valid; tests may load it.            |
| `CHANGELOG.md`               | User-visible changes, Keep a Changelog format.                        |
| `ROADMAP.md`                 | Planned releases and their scope.                                     |
| `BACKLOG.md`                 | Unscheduled ideas, known limitations and small issues.                |
| `GLOSSARY.md`                | Project vocabulary. Use these terms in code and docs.                 |
| `dev/specs/`                 | Feature specs, written before non-trivial implementation.             |
| `dev/issues/`                | Bugs that need more than a quick fix. Delete once fixed.              |
| `src/gitpair/config.py`      | Load and update the shared TOML config; detect local and remote host. |
| `src/gitpair/scanner.py`     | Finds repositories and reports their state. Runs on both hosts.       |
| `src/gitpair/hosts.py`       | `Host` runs commands locally; `RemoteHost` wraps them in ssh.         |
| `src/gitpair/plan.py`        | Public plan API: `build`, `describe`, the enums and dataclasses.      |
| `src/gitpair/_model.py`      | Private. `Action`, `Item`, `Plan`, `RepoState`, `Extra`, `Step`.       |
| `src/gitpair/_facts.py`      | Private. Gathers plan facts: all the host I/O, no decisions.          |
| `src/gitpair/_decide.py`     | Private. Turns facts into `Item`s: pure, no host access.               |
| `src/gitpair/execute.py`     | Git commands for each `Action`.                                       |
| `src/gitpair/session.py`     | One run: connect, apply the plan, save track/ignore decisions.        |
| `src/gitpair/tui.py`         | Textual app to review the plan and answer questions.                  |
| `src/gitpair/cli.py`         | argparse entry point and Rich output.                                 |
| `tests/conftest.py`          | `World` fixture: two fake hosts in a temp dir, no ssh needed.         |

## Rules that are easy to break

- `scanner.py` is piped to `python3 -` on the remote. Standard library only,
  must run on Python 3.7, no imports from `gitpair`.
- Every command that reaches the remote goes through `Host.run`, which quotes
  arguments with `shlex.join`. Never build a shell string from repository
  names, branch names or paths. `Host.shell` is only for fixed scripts built
  from config values, and those must be quoted too.
- The remote never connects back to the local host. Moving commits to the
  remote uses a push to `refs/gitpair/incoming/<branch>` followed by a
  fast-forward on the remote.
- No action may lose commits or uncommitted work unless the user picked it in
  the UI. Destructive actions save the old HEAD in `refs/gitpair/backup/`.
  `--auto` only runs actions that `plan.py` marked as automatic.
- Repositories not in `repos.track` always need a decision, even when the sync
  itself would be automatic.
- Ignored files are copied with `tar` over ssh, never with rsync, which is not
  installed everywhere. Files from the remote are extracted with
  `tarfile`'s `data` filter; do not remove it.
- Commands that talk to `origin` run with `ORIGIN_ENV` and `ORIGIN_TIMEOUT`
  (`plan.py`): no prompts, English messages, bounded time. Never force-push
  to origin.
- Rich and Textual parse `[...]` as markup. Escape any text that comes from git
  or the filesystem (`rich.markup.escape`).

## Workflow

1. For non-trivial features, write a spec in `dev/specs/` first and agree on it
   with the human. Small fixes can go straight to code.
2. Write tests that exercise real git repositories through the `World`
   fixture. Assert on repository state (HEAD, files, refs), not on internal
   calls. Mocks are only acceptable for the ssh boundary.
3. Implement.
4. Run `uv run task format`, then `uv run task ci`. The task is not done while
   `ci` fails. CI runs the same command.
5. Add a `CHANGELOG.md` entry under `Unreleased` for user-visible changes and
   update `README.md` or `docs/` if behavior changed.
6. Remove finished items from `BACKLOG.md` or `ROADMAP.md`. Delete specs and
   issues that are fully implemented; the changelog and git history keep the
   record.

If you find a bug outside the task at hand, add it to `BACKLOG.md` (small) or
`dev/issues/` (needs investigation) instead of fixing it silently.

## Commands

| Command                 | Action                                  |
| :---------------------- | :-------------------------------------- |
| `uv sync`               | Install dependencies.                   |
| `uv run task test`      | Run tests.                              |
| `uv run task format`    | Format and auto-fix with ruff.          |
| `uv run task lint`      | ruff format check, ruff lint, mypy.     |
| `uv run task ci`        | Lint and tests, as run by CI.           |
| `uv run gitpair plan`   | Try the CLI against your own config.    |

Real ssh is not covered by the test suite. When you change `hosts.py` or the
git URLs, test against a real second machine or ask the human to do it.
