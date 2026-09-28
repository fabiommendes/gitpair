from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import FakeRemote, World, commit, git

from gitpair import cli, session
from gitpair import config as cfg
from gitpair.hosts import Host


def write(path: Path, content: str, mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    os.utime(path, (mtime, mtime))


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
    assert "▶ push" in out  # compact action: ▶ push
    assert "↑" in out  # ahead icon in the status column
    assert "↑ ahead" in out and "▶ automatic" in out  # legend
    assert git(cli_world.there / "app", "rev-parse", "HEAD") != before


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


def test_sync_auto_skips_conflicts_but_copies_one_sided_files(cli_world: World, capsys):
    cli_world.extra_config = '\n[repo.app]\nsync_ignored = ["storage"]\n'
    cli_world.repo("app", gitignore="storage/\n")
    here, there = cli_world.here / "app", cli_world.there / "app"
    write(here / "storage/a.txt", "a", 1000)
    write(here / "storage/shared.txt", "old", 1000)
    write(there / "storage/shared.txt", "new", 2000)
    config = cli_world.config()

    assert cli.main(["--config", str(config.path), "sync", "--auto"]) == 0
    assert (there / "storage/a.txt").read_text() == "a"
    assert (here / "storage/shared.txt").read_text() == "old"
    assert (there / "storage/shared.txt").read_text() == "new"


@pytest.mark.parametrize(
    "argv",
    [
        ["--remote", "there", "plan"],
        ["plan", "--remote", "there"],
        ["--as", "here", "sync", "--remote", "there", "--auto"],
        ["sync", "--as", "here", "--remote", "there", "--auto"],
    ],
)
def test_as_and_remote_are_accepted_before_or_after_the_subcommand(argv):
    args = cli.parser().parse_args(argv)
    assert args.remote == "there"


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


def test_repo_name_with_markup_characters_is_shown_literally(cli_world: World, capsys):
    cli_world.track.append("[bold]weird")
    cli_world.repo("[bold]weird")
    commit(cli_world.here / "[bold]weird", "new.txt")
    config = cli_world.config()

    assert cli.main(["--config", str(config.path), "plan"]) == 0
    out = capsys.readouterr().out
    assert "[bold]weird" in out


def test_invalid_toml_is_reported_without_traceback(tmp_path, capsys):
    path = tmp_path / "config.toml"
    path.write_text("[hosts\n")
    assert cli.main(["--config", str(path), "plan"]) == 1
    assert "invalid TOML" in capsys.readouterr().out
