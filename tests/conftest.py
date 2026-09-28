"""Two fake hosts on the same machine.

The "remote" host runs commands locally with its own ``HOME`` and reaches its
repositories through plain paths, so the tests need no ssh server."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from gitpair import config as cfg
from gitpair import plan as planning
from gitpair.hosts import Host

CONFIG = """\
[settings]
depth = 2

[hosts.here]
ssh = "here"
root = "{here}"

[hosts.there]
ssh = "there"
root = "{there}"

[repos]
track = [{track}]
ignore = ["archived/*"]
"""


class FakeRemote(Host):
    def __init__(self, config: cfg.HostConfig, home: Path):
        super().__init__(config)
        self.home = home

    def wrap(self, args: list[str]) -> list[str]:
        return ["env", f"HOME={self.home}", *args]


def git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def commit(repo: Path, name: str, content: str | None = None) -> str:
    (repo / name).write_text(content or name)
    git(repo, "add", name)
    git(repo, "commit", "--quiet", "-m", f"add {name}")
    return git(repo, "rev-parse", "HEAD")


@dataclass
class World:
    tmp: Path
    here: Path
    there: Path
    track: list[str]
    loaded: cfg.Config | None = None
    extra_config: str = ""

    def repo(self, name: str, gitignore: str | None = None) -> Path:
        """Create a repo on ``here`` with one commit and clone it to ``there``."""
        origin = self.here / name
        origin.mkdir(parents=True)
        git(origin, "init", "--quiet", "--initial-branch=main")
        commit(origin, "README")
        if gitignore:
            commit(origin, ".gitignore", gitignore)
        subprocess.run(
            ["git", "clone", "--quiet", str(origin), str(self.there / name)],
            check=True,
        )
        return origin

    def config(self) -> cfg.Config:
        path = self.tmp / "home-here/.config/gitpair/config.toml"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            track = ", ".join(f'"{repo}"' for repo in self.track)
            text = CONFIG.format(here=self.here, there=self.there, track=track)
            path.write_text(text + self.extra_config)
        return cfg.load(path)

    def plan(self) -> planning.Plan:
        config = self.loaded = self.config()
        local = Host(config.hosts["here"])
        remote = FakeRemote(config.hosts["there"], self.tmp / "home-there")
        return planning.build(
            config, local, remote, local.scan(config.depth), remote.scan(config.depth)
        )


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    for var, value in {
        "HOME": str(tmp_path / "home-here"),
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }.items():
        monkeypatch.setenv(var, value)
    (tmp_path / "home-there").mkdir()
    here, there = tmp_path / "here", tmp_path / "there"
    here.mkdir()
    there.mkdir()
    return World(tmp_path, here, there, track=[])
