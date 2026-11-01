"""Stories: setting up and running gitpair."""

from __future__ import annotations

import pytest
from conftest import THREE_HOSTS, World, commit, git

from gitpair import cli
from gitpair import config as cfg


@pytest.mark.story("user: Create the config file")
def test_init_writes_template_once(tmp_path, capsys):
    path = tmp_path / "gitpair.toml"
    assert cli.main(["--config", str(path), "init"]) == 0
    assert "[hosts." in path.read_text()
    assert cli.main(["--config", str(path), "init"]) == 1


@pytest.mark.story("user: Preview a sync without changing anything")
def test_plan_prints_table_and_changes_nothing(cli_world: World, capsys):
    cli_world.track.append("app")
    cli_world.repo("app")
    before = commit(cli_world.here / "app", "new.txt")
    config = cli_world.config()

    assert cli.main(["--config", str(config.path), "plan"]) == 0
    out = capsys.readouterr().out
    assert "ahead by 1" in out
    assert "▶ push" in out  # compact action: ▶ push
    assert "↑" in out  # ahead icon in the status column
    assert "↑ ahead" in out and "▶ automatic" in out  # legend
    assert git(cli_world.there / "app", "rev-parse", "HEAD") != before


@pytest.mark.story("user: Preview a sync without changing anything")
def test_plan_plain_uses_no_unicode_icons(cli_world: World, capsys):
    cli_world.track.append("app")
    cli_world.repo("app")
    commit(cli_world.here / "app", "new.txt")
    config = cli_world.config()

    assert cli.main(["--config", str(config.path), "plan", "--plain"]) == 0
    out = capsys.readouterr().out
    assert "ahead by 1" in out
    assert "> push" in out
    # none of the unicode status/action icons leaked into the plain output
    # (table borders are drawn with unicode box characters regardless)
    for icon in "✓↑↓⇅✎✚→←✗∅⚑▶":
        assert icon not in out


@pytest.mark.story("user: Sync unattended from a cron job")
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


@pytest.mark.story("user: Use one config file on both machines")
def test_local_host_matches_short_hostname(config, monkeypatch):
    monkeypatch.setattr("socket.gethostname", lambda: "c3po-laptop.home")
    assert config.local_host().name == "c3po"


@pytest.mark.story("user: Use one config file on both machines")
def test_with_two_hosts_the_other_one_is_remote(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text(THREE_HOSTS.split("[hosts.bb8]")[0])
    monkeypatch.setattr("socket.gethostname", lambda: "r2d2")
    local, remote = cfg.load(path).pair(None, None)
    assert (local.name, remote.name) == ("r2d2", "c3po")
    assert remote.root == "~/src"
