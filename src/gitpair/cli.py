"""Command line entry point."""

from __future__ import annotations

import argparse
import shlex
import socket
import sys
from argparse import SUPPRESS
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from gitpair import __version__, session
from gitpair import config as cfg
from gitpair import plan as planning
from gitpair.hosts import CommandError
from gitpair.plan import Action, FilesPolicy, Item, Plan

console = Console()

TEMPLATE = """\
# gitpair config. Keep the same file on every host.

[settings]
depth = 3            # how deep to look for repositories under root
push_config = true   # copy config changes to the other host

[hosts.{name}]
ssh = "{name}"       # ssh destination the other host uses to reach this one
root = "~/git"

[hosts.OTHER]
ssh = "OTHER"
root = "~/git"

[repos]
track = []
ignore = []
"""


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            return init(args.config)
        return sync(args)
    except (cfg.ConfigError, CommandError) as error:
        console.print(f"[red]error:[/] {escape(str(error))}")
        return 1
    except KeyboardInterrupt:
        return 130


def parser() -> argparse.ArgumentParser:
    # A shared parent so --as/--remote work both before and after the
    # subcommand: `gitpair --remote c3po plan` and `gitpair plan --remote c3po`.
    # SUPPRESS keeps a value set on one side from being wiped out by the
    # other side's default when both parsers share this argument (argparse
    # copies the subparser's whole namespace onto the parent's, defaults
    # included). Read with getattr(args, "me"/"remote", None).
    host_options = argparse.ArgumentParser(add_help=False)
    host_options.add_argument(
        "--as", dest="me", metavar="HOST", default=SUPPRESS, help="name of this host"
    )
    host_options.add_argument(
        "--remote", metavar="HOST", default=SUPPRESS, help="host to sync with"
    )

    main = argparse.ArgumentParser(
        prog="gitpair",
        description="Keep git repositories in sync between two machines over ssh.",
        parents=[host_options],
    )
    main.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    main.add_argument(
        "--config", type=Path, default=cfg.config_path(), help="config file"
    )
    commands = main.add_subparsers(dest="command")
    sync = commands.add_parser(
        "sync", parents=[host_options], help="review the plan and sync (default)"
    )
    sync.add_argument(
        "--auto",
        action="store_true",
        help="apply only the safe fast-forwards and clones, never ask",
    )
    commands.add_parser(
        "plan", parents=[host_options], help="show what would be done and exit"
    )
    commands.add_parser("init", help="write a config template")
    return main


def init(path: Path) -> int:
    if path.exists():
        console.print(f"{path} already exists")
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.format(name=socket.gethostname().split(".")[0]))
    console.print(f"wrote {path}; edit the OTHER host and copy the file to it")
    return 0


def sync(args: argparse.Namespace) -> int:
    if not args.config.exists():
        return suggest_init(args.config)
    config = cfg.load(args.config)
    plan = make_plan(config, getattr(args, "me", None), getattr(args, "remote", None))
    if args.command == "plan":
        show_plan(plan)
        return 0
    if not plan.pending:
        console.print("[green]everything in sync[/]")
        return 0
    if getattr(args, "auto", False):
        for item in plan.items:
            if item.choice is None:
                item.choice = Action.SKIP
            # The one-sided copies and the git action are still safe; only
            # skip the conflicting files, which need an explicit choice.
            if item.file_conflicts and item.files_policy is None:
                item.files_policy = FilesPolicy.SKIP_CONFLICTS
    else:
        from gitpair.tui import PlanApp

        if not PlanApp(plan).run():
            console.print("nothing done")
            return 0
    return report(session.run(config, plan, on_item=announce(plan)))


def suggest_init(path: Path) -> int:
    option = "" if path == cfg.config_path() else f" --config {shlex.quote(str(path))}"
    console.print(f"no config found at {escape(str(path))}", soft_wrap=True)
    console.print(
        f"create one with: [bold]gitpair{escape(option)} init[/]", soft_wrap=True
    )
    return 1


def make_plan(config: cfg.Config, me: str | None, peer: str | None) -> Plan:
    local, remote = session.connect(config, me, peer)
    with console.status(f"scanning {local.name} and {remote.name}..."):
        local_scan = local.scan(config.depth)
        remote_scan = remote.scan(config.depth)

    def progress(repos):
        repos = list(repos)
        with console.status("comparing...") as status:
            for index, repo in enumerate(repos, 1):
                status.update(f"comparing [{index}/{len(repos)}] {escape(repo)}")
                yield repo

    return planning.build(config, local, remote, local_scan, remote_scan, progress)


def show_plan(plan: Plan) -> None:
    names = plan.local.name, plan.remote.name
    table = Table(title=f"{names[0]} (here) <-> {names[1]}")
    for column in ("Repository", "Branch", "Status", "Action"):
        table.add_column(column)
    for item in plan.pending:
        action = (
            "[yellow]" + escape(pending_text(item)) + "[/]"
            if item.needs_decision
            else escape(planning.describe(item, *names))
        )
        table.add_row(
            escape(item.repo), escape(item.branch or "-"), escape(item.status), action
        )
    console.print(table)
    console.print(f"{len(plan.items) - len(plan.pending)} repositories in sync")


def pending_text(item: Item, /) -> str:
    """ "ask: " followed by the options for whichever decision is still open."""
    if item.choice is None:
        return "ask: " + " / ".join(item.options)
    return "ask: " + " / ".join(FilesPolicy)


def announce(plan: Plan):
    names = plan.local.name, plan.remote.name

    def on_item(item):
        assert item.choice is not None
        text = escape(planning.describe(item, *names))
        console.print(f"[bold]{escape(item.repo)}[/]: {text}")

    return on_item


def report(outcome: session.Outcome) -> int:
    for item, error in outcome.failed:
        console.print(f"[red]failed[/] {escape(item.repo)}: {escape(str(error))}")
    console.print(f"[green]{len(outcome.done)} done[/], {len(outcome.failed)} failed")
    if outcome.config_note:
        console.print(escape(outcome.config_note))
    return 1 if outcome.failed else 0


if __name__ == "__main__":
    sys.exit(main())
