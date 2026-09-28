"""Shared configuration: the same file lives on every host.

Example::

    [settings]
    depth = 3            # how deep to look for repositories under root
    push_config = true   # copy config changes to the other host

    [hosts.r2d2]
    ssh = "chips@r2d2.local"
    root = "~/git"

    [hosts.c3po]
    hostname = "c3po-laptop"   # defaults to the table name
    ssh = "c3po"
    root = "~/git"

    [repos]
    track = ["conf", "ai/agents"]
    ignore = ["archived/*"]

    [repo."web/site"]          # declaring options also tracks the repo
    sync_ignored = ["media", ".env"]
    autopush = true
"""

from __future__ import annotations

import os
import shlex
import socket
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

import tomlkit
import tomlkit.exceptions

DEFAULT_PATH = Path("~/.config/gitpair/config.toml").expanduser()


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class HostConfig:
    name: str
    hostname: str
    ssh: str
    root: str


@dataclass(frozen=True)
class RepoOptions:
    sync_ignored: tuple[str, ...] = ()
    autopush: bool = False


@dataclass
class Config:
    path: Path
    hosts: dict[str, HostConfig]
    track: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)
    depth: int = 3
    push_config: bool = True
    autopush: bool = False
    repo_options: dict[str, RepoOptions] = field(default_factory=dict)

    def is_tracked(self, repo: str) -> bool:
        return repo in self.track or repo in self.repo_options

    def options(self, repo: str) -> RepoOptions:
        return self.repo_options.get(repo, RepoOptions(autopush=self.autopush))

    def is_ignored(self, repo: str) -> bool:
        return any(fnmatch(repo, pattern) for pattern in self.ignore)

    def pair(self, me: str | None, peer: str | None) -> tuple[HostConfig, HostConfig]:
        """Decide which host is local and which one is remote."""
        local = self.hosts[me] if me else self.local_host()
        others = [h for h in self.hosts.values() if h.name != local.name]
        if peer:
            if peer not in self.hosts:
                raise ConfigError(f"unknown host {peer!r}")
            return local, self.hosts[peer]
        if len(others) != 1:
            names = ", ".join(h.name for h in others)
            raise ConfigError(f"choose the remote with --remote ({names})")
        return local, others[0]

    def local_host(self) -> HostConfig:
        current = socket.gethostname().split(".")[0]
        for host in self.hosts.values():
            if host.hostname.split(".")[0] == current:
                return host
        raise ConfigError(
            f"this machine ({current}) is not listed in {self.path}; "
            "add it or use --as NAME"
        )


def load(path: Path = DEFAULT_PATH) -> Config:
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    try:
        doc = tomlkit.parse(path.read_text()).unwrap()
    except tomlkit.exceptions.ParseError as error:
        raise ConfigError(f"invalid TOML in {path}: {error}") from None
    hosts = {}
    for name, data in doc.get("hosts", {}).items():
        if "ssh" not in data:
            raise ConfigError(f"host {name!r} has no 'ssh' destination")
        hosts[name] = HostConfig(
            name=name,
            hostname=data.get("hostname", name),
            ssh=data["ssh"],
            root=data.get("root", "~/git"),
        )
    if len(hosts) < 2:
        raise ConfigError("the config must declare at least two hosts")
    repos = doc.get("repos", {})
    settings = doc.get("settings", {})
    autopush = settings.get("autopush", False)
    return Config(
        path=path,
        hosts=hosts,
        track=list(repos.get("track", [])),
        ignore=list(repos.get("ignore", [])),
        depth=settings.get("depth", 3),
        push_config=settings.get("push_config", True),
        autopush=autopush,
        repo_options={
            repo: repo_options(repo, data, autopush)
            for repo, data in doc.get("repo", {}).items()
        },
    )


def repo_options(repo: str, data: dict, autopush: bool) -> RepoOptions:
    entries = data.get("sync_ignored", [])
    for entry in entries:
        parts = PurePosixPath(entry).parts
        if not entry or entry.startswith("/") or ".." in parts or ".git" in parts:
            raise ConfigError(
                f"repo {repo!r}: sync_ignored entries must be relative paths "
                f"inside the repository, got {entry!r}"
            )
    return RepoOptions(
        sync_ignored=tuple(entry.rstrip("/") for entry in entries),
        autopush=data.get("autopush", autopush),
    )


def update_repos(path: Path, track: list[str], ignore: list[str]) -> str:
    """Append entries to the repos lists, keeping comments and layout.

    Returns the new file content."""
    doc = tomlkit.parse(path.read_text())
    repos = doc.setdefault("repos", tomlkit.table())
    for key, new in (("track", track), ("ignore", ignore)):
        items = repos.setdefault(key, tomlkit.array())
        for repo in new:
            if repo not in items:
                items.append(repo)
        items.multiline(len(items) > 3)
    text = tomlkit.dumps(doc)
    path.write_text(text)
    return text


def remote_path(path: Path) -> str:
    """Shell expression for the same config file on the other host."""
    try:
        return '"$HOME"/' + shlex.quote(str(path.relative_to(Path.home())))
    except ValueError:
        return shlex.quote(str(path))


def config_path() -> Path:
    return Path(os.environ.get("GITPAIR_CONFIG") or DEFAULT_PATH).expanduser()
