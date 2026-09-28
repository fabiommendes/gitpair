from __future__ import annotations

import pytest
from conftest import FakeRemote, World, commit, git

from gitpair import cli, session
from gitpair import config as cfg
from gitpair.hosts import Host


@pytest.fixture
def cli_world(world: World, monkeypatch: pytest.MonkeyPatch) -> World:
    def connect(config, me, peer):
        return Host(config.hosts["here"]), FakeRemote(
            config.hosts["there"], world.tmp / "home-there"
        )

    monkeypatch.setattr(session, "connect", connect)
    monkeypatch.setenv("COLUMNS", "200")
    return world


def test_plan_prints_table_and_changes_nothing(cli_world: World, capsys):
    cli_world.track.append("app")
    cli_world.repo("app")
    before = commit(cli_world.here / "app", "new.txt")
    config = cli_world.config()

    assert cli.main(["--config", str(config.path), "plan"]) == 0
    out = capsys.readouterr().out
    assert "ahead by 1" in out
    assert "fast-forward there from here" in out
    assert git(cli_world.there / "app", "rev-parse", "HEAD") != before


def test_sync_auto_applies_safe_actions_and_skips_questions(cli_world: World, capsys):
    cli_world.track.append("app")
    cli_world.repo("app")
    cli_world.repo("unknown")
    head = commit(cli_world.here / "app", "new.txt")
    config = cli_world.config()

    assert cli.main(["--config", str(config.path), "sync", "--auto"]) == 0
    assert git(cli_world.there / "app", "rev-parse", "HEAD") == head
    assert "1 done, 0 failed" in capsys.readouterr().out
    assert "unknown" not in config.path.read_text()


def test_init_writes_template_once(tmp_path, capsys):
    path = tmp_path / "gitpair.toml"
    assert cli.main(["--config", str(path), "init"]) == 0
    assert "[hosts." in path.read_text()
    assert cli.main(["--config", str(path), "init"]) == 1


@pytest.mark.parametrize("command", [[], ["plan"], ["sync"]])
def test_missing_config_suggests_init(tmp_path, capsys, command):
    path = tmp_path / "missing.toml"
    assert cli.main(["--config", str(path), *command]) == 1
    out = capsys.readouterr().out
    assert f"no config found at {path}" in out
    assert f"gitpair --config {path} init" in out


def test_missing_default_config_suggests_plain_init(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cfg, "DEFAULT_PATH", tmp_path / "config.toml")
    assert cli.main(["--config", str(tmp_path / "config.toml")]) == 1
    assert "create one with: gitpair init" in capsys.readouterr().out


def test_errors_are_printed_without_markup(tmp_path, capsys):
    path = tmp_path / "config.toml"
    path.write_text('[hosts."[x]"]\n[hosts.y]\nssh = "y"\n')
    assert cli.main(["--config", str(path), "plan"]) == 1
    assert "host '[x]' has no 'ssh'" in capsys.readouterr().out


def test_invalid_toml_is_reported_without_traceback(tmp_path, capsys):
    path = tmp_path / "config.toml"
    path.write_text("[hosts\n")
    assert cli.main(["--config", str(path), "plan"]) == 1
    assert "invalid TOML" in capsys.readouterr().out
