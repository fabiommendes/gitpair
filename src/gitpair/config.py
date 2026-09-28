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

__all__ = [
    "load",
    "update_repos",
    #: Dataclasses
    "Config",
    "HostConfig",
    "RepoOptions",
    #: Exceptions
    "ConfigError",
    #: Paths
    "remote_path",
    "config_path",
    "DEFAULT_PATH",
]

DEFAULT_PATH = Path("~/.config/gitpair/config.toml").expanduser()


class ConfigError(Exception):
    """The config file is missing, invalid, or does not match the CLI flags."""


@dataclass(frozen=True)
class HostConfig:
    """One ``[hosts.NAME]`` table."""

    name: str
    hostname: str
    ssh: str
    root: str


@dataclass(frozen=True)
class RepoOptions:
    """Per-repository options, from ``[repo.NAME]`` or the ``autopush`` default."""

    sync_ignored: tuple[str, ...] = ()
    autopush: bool = False


@dataclass
class Config:
    """The parsed config file, shared by every host."""

    path: Path
    hosts: dict[str, HostConfig]
    track: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)
    depth: int = 3
    push_config: bool = True
    autopush: bool = False
    repo_options: dict[str, RepoOptions] = field(default_factory=dict)

    def is_tracked(self, repo: str) -> bool:
        """True when ``repo`` is in ``repos.track`` or has a ``[repo.NAME]`` table."""
        return repo in self.track or repo in self.repo_options

    def options(self, repo: str) -> RepoOptions:
        """``repo``'s options, or the defaults when it has no ``[repo.NAME]`` table."""
        return self.repo_options.get(repo, RepoOptions(autopush=self.autopush))

    def is_ignored(self, repo: str) -> bool:
        """True when ``repo`` matches one of the ``repos.ignore`` patterns."""
        return any(fnmatch(repo, pattern) for pattern in self.ignore)

    def pair(self, me: str | None, peer: str | None) -> tuple[HostConfig, HostConfig]:
        """Decide which host is local and which one is remote.

        Args:
            me: host name from ``--as``, or ``None`` to detect it from the
                machine's hostname.
            peer: host name from ``--remote``, or ``None`` when there is
                exactly one other host to choose from.

        Raises:
            ConfigError: ``me`` or ``peer`` name an unknown host, ``me``
                and ``peer`` are the same host, the local host cannot be
                detected, or ``peer`` is ambiguous.
        """
        if me:
            if me not in self.hosts:
                raise ConfigError(f"unknown host {me!r}")
            if me == peer:
                raise ConfigError(
                    f"--as and --remote must be different hosts, got {me!r}"
                )
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
        """The host whose ``hostname`` matches this machine.

        Raises:
            ConfigError: no host in the config matches this machine's
                hostname.
        """
        current = socket.gethostname().split(".")[0]
        for host in self.hosts.values():
            if host.hostname.split(".")[0] == current:
                return host
        raise ConfigError(
            f"this machine ({current}) is not listed in {self.path}; "
            "add it or use --as NAME"
        )


def load(path: Path = DEFAULT_PATH) -> Config:
    """Parse the TOML config file at ``path``.

    Raises:
        ConfigError: the file does not exist, is not valid TOML, declares
            fewer than two hosts, a host has no ``ssh`` destination, a
            ``sync_ignored`` entry escapes the repository, or a value has
            the wrong type (see :mod:`gitpair.config`'s module docstring for
            the shape every key must have).
    """
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    try:
        doc = tomlkit.parse(path.read_text()).unwrap()
    except tomlkit.exceptions.ParseError as error:
        raise ConfigError(f"invalid TOML in {path}: {error}") from None
    hosts = {}
    for name, data in doc.get("hosts", {}).items():
        _check_table(data, f"hosts.{name}")
        if "ssh" not in data:
            raise ConfigError(f"host {name!r} has no 'ssh' destination")
        for key in ("ssh", "hostname", "root"):
            if key in data:
                _check_str(data[key], f"hosts.{name}.{key}")
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
    track = repos.get("track", [])
    _check_str_list(track, "repos.track")
    ignore = repos.get("ignore", [])
    _check_str_list(ignore, "repos.ignore")
    depth = settings.get("depth", 3)
    _check_int(depth, "settings.depth")
    push_config = settings.get("push_config", True)
    _check_bool(push_config, "settings.push_config")
    autopush = settings.get("autopush", False)
    _check_bool(autopush, "settings.autopush")
    return Config(
        path=path,
        hosts=hosts,
        track=list(track),
        ignore=list(ignore),
        depth=depth,
        push_config=push_config,
        autopush=autopush,
        repo_options={
            repo: _repo_options(repo, data, autopush)
            for repo, data in doc.get("repo", {}).items()
        },
    )


def update_repos(path: Path, track: list[str], ignore: list[str]) -> str:
    """Append entries to the repos lists, keeping comments and layout.

    Args:
        track: repository names to add to ``repos.track``, if not already
            listed.
        ignore: patterns to add to ``repos.ignore``, if not already listed.

    Returns:
        The file's new content.
    """
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


def remote_path(path: Path, /) -> str:
    """Shell expression for the same config file on the other host.

    >>> remote_path(Path.home() / ".config/gitpair/config.toml")
    '"$HOME"/.config/gitpair/config.toml'
    >>> remote_path(Path("/etc/gitpair.toml"))
    '/etc/gitpair.toml'
    """
    try:
        return '"$HOME"/' + shlex.quote(str(path.relative_to(Path.home())))
    except ValueError:
        return shlex.quote(str(path))


def config_path() -> Path:
    """The config path: ``$GITPAIR_CONFIG``, or :data:`DEFAULT_PATH`."""
    return Path(os.environ.get("GITPAIR_CONFIG") or DEFAULT_PATH).expanduser()


def _repo_options(repo: str, data: dict, autopush: bool) -> RepoOptions:
    _check_table(data, f'repo."{repo}"')
    entries = data.get("sync_ignored", [])
    _check_str_list(entries, f'repo."{repo}".sync_ignored')
    for entry in entries:
        parts = PurePosixPath(entry).parts
        if not entry or entry.startswith("/") or ".." in parts or ".git" in parts:
            raise ConfigError(
                f"repo {repo!r}: sync_ignored entries must be relative paths "
                f"inside the repository, got {entry!r}"
            )
    if "autopush" in data:
        _check_bool(data["autopush"], f'repo."{repo}".autopush')
    return RepoOptions(
        sync_ignored=tuple(entry.rstrip("/") for entry in entries),
        autopush=data.get("autopush", autopush),
    )


def _check_table(value: object, key: str, /) -> None:
    """Raise :class:`ConfigError` naming ``key`` unless ``value`` is a table."""
    if not isinstance(value, dict):
        raise ConfigError(f"{key} must be a table, got {value!r}")


def _check_str(value: object, key: str, /) -> None:
    """Raise :class:`ConfigError` naming ``key`` unless ``value`` is a string."""
    if not isinstance(value, str):
        raise ConfigError(f"{key} must be a string, got {value!r}")


def _check_int(value: object, key: str, /) -> None:
    """Raise :class:`ConfigError` naming ``key`` unless ``value`` is an integer."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"{key} must be an integer, got {value!r}")


def _check_bool(value: object, key: str, /) -> None:
    """Raise :class:`ConfigError` naming ``key`` unless ``value`` is a boolean."""
    if not isinstance(value, bool):
        raise ConfigError(f"{key} must be a boolean, got {value!r}")


def _check_str_list(value: object, key: str, /) -> None:
    """Raise :class:`ConfigError` naming ``key`` unless it is a list of strings."""
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{key} must be a list of strings, got {value!r}")
