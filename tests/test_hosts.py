from __future__ import annotations

import json

import pytest

from gitpair.config import HostConfig
from gitpair.hosts import SSH_OPTIONS, CommandError, Host, RemoteHost


@pytest.fixture
def host_config() -> HostConfig:
    return HostConfig(name="there", hostname="there", ssh="there", root="~/git")


def test_ssh_options_bound_connect_time(host_config):
    assert "-o" in SSH_OPTIONS
    assert "ConnectTimeout=10" in SSH_OPTIONS


def test_remote_host_wrap_carries_connect_timeout(host_config):
    host = RemoteHost(host_config)
    wrapped = host.wrap(["git", "status"])
    assert "ConnectTimeout=10" in wrapped


def test_host_python_reports_non_json_output_as_command_error(host_config, monkeypatch):
    host = Host(host_config)
    monkeypatch.setattr(host, "run", lambda *a, **k: "bash: /etc/profile: noisy junk")
    with pytest.raises(CommandError, match="noisy junk"):
        host.python("scan", "~/git", "3")


def test_host_python_parses_valid_json(host_config, monkeypatch):
    host = Host(host_config)
    monkeypatch.setattr(
        host, "run", lambda *a, **k: json.dumps({"root": "/x", "repos": {}})
    )
    assert host.python("scan", "~/git", "3") == {"root": "/x", "repos": {}}


def test_base_host_peer_env_is_empty(host_config):
    assert Host(host_config).peer_env() == {}


def test_remote_host_peer_env_carries_the_same_ssh_options(host_config):
    host = RemoteHost(host_config)
    env = host.peer_env()
    assert "ControlPath=~/.ssh/gitpair-%C" in env["GIT_SSH_COMMAND"]
    assert "ConnectTimeout=10" in env["GIT_SSH_COMMAND"]
