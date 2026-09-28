"""Command line entry point."""

from __future__ import annotations

import argparse
import shlex
import socket
import sys
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from gitpair import __version__, session
from gitpair import config as cfg
from gitpair import plan as planning
from gitpair.hosts import CommandError
from gitpair.plan import Action, Plan

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
    main = argparse.ArgumentParser(
        prog="gitpair",
        description="Keep git repositories in sync between two machines over ssh.",
    )
    main.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    main.add_argument(
        "--config", type=Path, default=cfg.config_path(), help="config file"
    )
    main.add_argument("--as", dest="me", metavar="HOST", help="name of this host")
    main.add_argument("--remote", metavar="HOST", help="host to sync with")
    commands = main.add_subparsers(dest="command")
    sync = commands.add_parser("sync", help="review the plan and sync (default)")
    sync.add_argument(
        "--auto",
        action="store_true",
        help="apply only the safe fast-forwards and clones, never ask",
    )
    commands.add_parser("plan", help="show what would be done and exit")
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
    plan = make_plan(config, args.me, args.remote)
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
                status.update(f"comparing [{index}/{len(repos)}] {repo}")
                yield repo

    return planning.build(config, local, remote, local_scan, remote_scan, progress)


def show_plan(plan: Plan) -> None:
    names = plan.local.name, plan.remote.name
    table = Table(title=f"{names[0]} (here) <-> {names[1]}")
    for column in ("Repository", "Branch", "Status", "Action"):
        table.add_column(column)
    for item in plan.pending:
        action = (
            escape(planning.describe(item, *names))
            if item.choice
            else "[yellow]ask: " + " / ".join(item.options) + "[/]"
        )
        table.add_row(item.repo, item.branch or "-", escape(item.status), action)
    console.print(table)
    console.print(f"{len(plan.items) - len(plan.pending)} repositories in sync")


def announce(plan: Plan):
    names = plan.local.name, plan.remote.name

    def on_item(item):
        assert item.choice is not None
        text = escape(planning.describe(item, *names))
        console.print(f"[bold]{escape(item.repo)}[/]: {text}")

    return on_item


def report(outcome: session.Outcome) -> int:
    for item, error in outcome.failed:
        console.print(f"[red]failed[/] {item.repo}: {escape(str(error))}")
    console.print(f"[green]{len(outcome.done)} done[/], {len(outcome.failed)} failed")
    if outcome.config_note:
        console.print(outcome.config_note)
    return 1 if outcome.failed else 0


if __name__ == "__main__":
    sys.exit(main())
