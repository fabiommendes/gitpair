# Contributing to gitpair

Thanks for taking the time to help. Bug reports, fixes, docs and new features
are all welcome.

## Reporting bugs

Open an issue with:

- the output of `gitpair --version`;
- `git --version` and the OS of both hosts;
- the relevant part of `gitpair plan` and what you expected instead.

Remove host names, paths and URLs you do not want to publish.

If you found a way to make gitpair run unintended commands or destroy data,
follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Proposing features

Open an issue before writing a large change. gitpair tries to stay small: one
config file, two hosts, no daemon, no server. Features that fit this shape are
easier to accept.

## Development setup

You need [uv](https://docs.astral.sh/uv/) and git 2.28 or newer.

```sh
git clone https://github.com/fabiommendes/gitpair
cd gitpair
uv sync
uv run task ci      # lint, type check and tests
```

Tasks, defined in `pyproject.toml`:

| Task                  | What it does                            |
| :-------------------- | :-------------------------------------- |
| `uv run task test`    | Run the test suite.                     |
| `uv run task format`  | Format and auto-fix with ruff.          |
| `uv run task lint`    | ruff format check, ruff lint and mypy.  |
| `uv run task ci`      | Everything CI runs.                     |
| `uv run task release` | CI checks, then build the distribution. |

The tests create real git repositories in temporary directories. The "remote"
host is simulated by running commands locally with a different `HOME`, so no
ssh server is needed. See `tests/conftest.py`.

## Pull requests

- Branch from `main` and keep each pull request about one thing.
- Add or update tests. Bug fixes should come with a test that fails without
  the fix.
- Run `uv run task ci` before pushing. CI runs the same command.
- Add an entry under `Unreleased` in [CHANGELOG.md](CHANGELOG.md) for changes
  users will notice.
- Update the README or `docs/` when behavior or configuration changes.

## Code style

- ruff formats and lints the code; do not fight it.
- `src/gitpair/scanner.py` runs on the remote host with whatever `python3` is
  there. Keep it standard library only and compatible with Python 3.7.
- Anything that changes repositories must be safe to interrupt and must never
  discard commits or uncommitted work without an explicit choice from the user.

## Releasing

One-time setup, done: `release.yml` publishes with a
[PyPI trusted publisher](https://docs.pypi.org/trusted-publishers/), not a
token. It needs, on PyPI, a trusted publisher for owner `fabiommendes`,
repository `gitpair`, workflow `release.yml`, environment `pypi`; and, on
GitHub, a repository environment named `pypi` that the workflow deploys to.

Maintainers only, for every release:

1. Move the `Unreleased` entries in `CHANGELOG.md` to a new version section.
2. Bump `version` in `pyproject.toml` and `__version__` in
   `src/gitpair/__init__.py`.
3. Tag `vX.Y.Z` and push the tag. The release workflow builds and publishes to
   PyPI.

## Code of conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
