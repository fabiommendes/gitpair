from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from gitpair import config as cfg
from gitpair.hosts import RemoteHost

THREE_HOSTS = """\
[hosts.r2d2]
ssh = "chips@r2d2"

[hosts.c3po]
hostname = "c3po-laptop.lan"
ssh = "c3po"
root = "~/src"

[hosts.bb8]
ssh = "bb8"
"""


@pytest.fixture
def config(tmp_path: Path) -> cfg.Config:
    path = tmp_path / "config.toml"
    path.write_text(THREE_HOSTS)
    return cfg.load(path)


def test_local_host_matches_short_hostname(config, monkeypatch):
    monkeypatch.setattr("socket.gethostname", lambda: "c3po-laptop.home")
    assert config.local_host().name == "c3po"


def test_unknown_machine_is_an_error(config, monkeypatch):
    monkeypatch.setattr("socket.gethostname", lambda: "stranger")
    with pytest.raises(cfg.ConfigError, match="stranger"):
        config.local_host()


def test_with_two_hosts_the_other_one_is_remote(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text(THREE_HOSTS.split("[hosts.bb8]")[0])
    monkeypatch.setattr("socket.gethostname", lambda: "r2d2")
    local, remote = cfg.load(path).pair(None, None)
    assert (local.name, remote.name) == ("r2d2", "c3po")
    assert remote.root == "~/src"


def test_more_hosts_require_remote(config):
    with pytest.raises(cfg.ConfigError, match="--remote"):
        config.pair("r2d2", None)
    assert config.pair("r2d2", "bb8")[1].name == "bb8"


def test_unknown_as_host_is_a_config_error(config):
    with pytest.raises(cfg.ConfigError, match="unknown host 'skywalker'"):
        config.pair("skywalker", "bb8")


def test_as_and_remote_must_be_different(config):
    with pytest.raises(cfg.ConfigError, match="r2d2"):
        config.pair("r2d2", "r2d2")


def test_update_repos_keeps_comments(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('# mine\n[repos]\ntrack = ["a"]  # keep\n')
    cfg.update_repos(path, track=["b", "a"], ignore=["c"])
    text = path.read_text()
    assert "# mine" in text and "# keep" in text
    repos = tomllib.loads(text)["repos"]
    assert (repos["track"], repos["ignore"]) == (["a", "b"], ["c"])


def test_remote_host_quotes_commands_for_ssh(config):
    host = RemoteHost(config.hosts["c3po"])
    wrapped = host.wrap(["git", "-C", "/home/me/my repo", "status"])
    assert wrapped[0] == "ssh"
    assert wrapped[-2:] == ["c3po", "git -C '/home/me/my repo' status"]
    assert host.url("/home/me/app") == "c3po:/home/me/app"


def test_example_config_is_valid():
    example = Path(__file__).parent.parent / "examples/config.toml"
    config = cfg.load(example)
    assert set(config.hosts) == {"desktop", "laptop"}
    assert config.is_ignored("archived/old")
