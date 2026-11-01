from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import World, commit

from gitpair import cli
from gitpair import config as cfg


def write(path: Path, content: str, mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    os.utime(path, (mtime, mtime))


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
