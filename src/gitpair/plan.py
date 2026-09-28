"""Compare both hosts and decide what to do with each repository."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from gitpair._decide import count, decide, describe, resolved_files
from gitpair._facts import ORIGIN_TIMEOUT, gather, origin_env, origin_state, peer_ref
from gitpair._icons import icons, legend
from gitpair._model import (
    NO_CHANGE,
    Action,
    Extra,
    FilesPolicy,
    Item,
    Plan,
    RepoState,
    Step,
)
from gitpair.config import Config
from gitpair.hosts import Host

__all__ = [
    "build",
    "describe",
    "count",
    "resolved_files",
    "icons",
    "legend",
    #: Enums
    "Action",
    "Step",
    "FilesPolicy",
    #: Dataclasses
    "RepoState",
    "Extra",
    "Item",
    "Plan",
    #: Constants
    "NO_CHANGE",
    "ORIGIN_TIMEOUT",
    #: Helpers shared with execute.py, which applies the plan's actions
    "origin_env",
    "origin_state",
    "peer_ref",
]


def build(
    config: Config,
    local: Host,
    remote: Host,
    local_scan: dict,
    remote_scan: dict,
    progress: Callable[[Iterable[str]], Iterable[str]] = iter,
) -> Plan:
    """Compare both hosts and decide what to do with each repository.

    Runs in two phases: :func:`gitpair._facts.gather` collects plain data by
    running commands on both hosts, then :func:`gitpair._decide.decide`
    turns that data into a plan with no further host access.

    Args:
        local_scan: result of ``local.scan(config.depth)``.
        remote_scan: result of ``remote.scan(config.depth)``.
        progress: wraps the sorted repository names while gathering, e.g.
            to drive a progress indicator.

    Returns:
        A `Plan` with one item per repository not ignored by ``config``.
    """
    facts = gather(config, local, remote, local_scan, remote_scan, progress)
    items = decide(config, facts, local.name, remote.name)
    return Plan(local, remote, items)
