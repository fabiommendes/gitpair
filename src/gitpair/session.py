"""One sync run: pair the hosts, scan, plan, apply, record decisions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from gitpair import config as cfg
from gitpair import execute
from gitpair.hosts import CommandError, Host, RemoteHost
from gitpair.plan import NO_CHANGE, Action, Item, Plan


@dataclass
class Outcome:
    done: list[Item] = field(default_factory=list)
    failed: list[tuple[Item, CommandError]] = field(default_factory=list)
    config_note: str | None = None


def connect(
    config: cfg.Config, me: str | None = None, peer: str | None = None
) -> tuple[Host, Host]:
    local, remote = config.pair(me, peer)
    return Host(local), RemoteHost(remote)


def run(
    config: cfg.Config,
    plan: Plan,
    on_item: Callable[[Item], None] = lambda item: None,
) -> Outcome:
    """Apply every chosen action and save new track/ignore decisions."""
    outcome = Outcome()
    original = config.path.read_text()
    for item in plan.items:
        if item.choice in (None, Action.SKIP):
            continue
        on_item(item)
        try:
            execute.apply(plan, item)
        except CommandError as error:
            outcome.failed.append((item, error))
        else:
            outcome.done.append(item)
    outcome.config_note = save_decisions(config, plan.remote, outcome, original)
    return outcome


def save_decisions(
    config: cfg.Config, remote: Host, outcome: Outcome, original: str
) -> str | None:
    track = [i.repo for i in outcome.done if i.new and i.choice not in NO_CHANGE]
    ignore = [i.repo for i in outcome.done if i.choice is Action.IGNORE]
    if not track and not ignore:
        return None
    text = cfg.update_repos(config.path, track, ignore)
    note = f"config updated: {len(track)} tracked, {len(ignore)} ignored"
    if not config.push_config:
        return note
    target = cfg.remote_path(config.path)
    try:
        current = remote.shell(f"cat {target} 2>/dev/null || true")
        if current.strip() not in ("", original.strip()):
            return f"{note}; {remote.name} has a different config, copy it by hand"
        remote.shell(f'mkdir -p "$(dirname {target})" && cat > {target}', input=text)
    except CommandError as error:
        return f"{note}; could not copy it to {remote.name}: {error.stderr}"
    return f"{note} on both hosts"
