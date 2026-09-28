"""Run commands on the local machine or on the peer over ssh."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from importlib import resources
from typing import IO

from gitpair.config import HostConfig

__all__ = [
    "Host",
    "RemoteHost",
    "CommandError",
    "SSH_OPTIONS",
]

SSH_OPTIONS = [
    "-o", "ControlMaster=auto",
    "-o", "ControlPath=~/.ssh/gitpair-%C",
    "-o", "ControlPersist=60",
    "-o", "ConnectTimeout=10",
]  # fmt: skip


class CommandError(Exception):
    """A command run on ``host`` exited with a non-zero status, or timed out."""

    def __init__(self, host: str, args: list[str], stderr: str):
        self.host = host
        self.args_ = args
        self.stderr = stderr.strip()
        super().__init__(f"[{host}] {shlex.join(args)}: {self.stderr}")


class Host:
    """A machine that runs commands. The base class runs them locally."""

    def __init__(self, config: HostConfig):
        self.config = config
        self.name = config.name
        self.root = config.root

    def run(
        self,
        args: list[str],
        *,
        input: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> str:
        """Run ``args`` and return its stripped stdout.

        Args:
            env: extra variables merged over a copy of this process's
                environment; the child never sees a bare, unset environment.
            timeout: seconds to wait before killing the command.

        Raises:
            CommandError: the command exited with a non-zero status or
                exceeded ``timeout``.
        """
        try:
            result = subprocess.run(
                self.wrap(args),
                input=input,
                capture_output=True,
                text=True,
                env={**os.environ, **env} if env else None,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise CommandError(self.name, args, f"timed out after {timeout}s") from None
        if result.returncode != 0:
            raise CommandError(self.name, args, result.stderr or result.stdout)
        return result.stdout.strip()

    def run_binary(
        self,
        args: list[str],
        *,
        stdin: IO[bytes] | None = None,
        input: bytes | None = None,
        stdout: IO[bytes] | None = None,
    ) -> None:
        """Run a command that reads or writes binary streams, like tar.

        Raises:
            CommandError: the command exited with a non-zero status.
        """
        result = subprocess.run(
            self.wrap(args),
            stdin=stdin,
            input=input,
            stdout=stdout or subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")
            raise CommandError(self.name, args, stderr)

    def git(self, path: str, *args: str, env: dict[str, str] | None = None) -> str:
        """Run ``git -C path args...``.

        Raises:
            CommandError: git exited with a non-zero status.
        """
        return self.run(["git", "-C", path, *args], env=env)

    def shell(self, script: str, *, input: str | None = None) -> str:
        """Run ``script`` with ``sh -c``.

        Raises:
            CommandError: the script exited with a non-zero status.
        """
        return self.run(["sh", "-c", script], input=input)

    def scan(self, depth: int) -> dict:
        """Find repositories under ``config.root`` and report their state.

        Updates ``self.root`` to the scan's expanded, absolute root.

        Raises:
            CommandError: ``scanner.py`` could not run or its output was
                not valid JSON.
        """
        data = self.python("scan", self.config.root, str(depth))
        self.root = data["root"]
        return data

    def manifest(self, repo_path: str, entries: list[str]) -> dict[str, list[int]]:
        """Size and mtime of every regular file under ``entries``.

        Raises:
            CommandError: ``scanner.py`` could not run or its output was
                not valid JSON.
        """
        return self.python("manifest", repo_path, *entries)

    def python(self, *args: str) -> dict:
        """Run ``scanner.py`` with ``args`` and parse its JSON output.

        Raises:
            CommandError: the output is not valid JSON, e.g. a noisy login
                shell (``/etc/profile``) printing to stdout on the remote.
        """
        source = resources.files("gitpair").joinpath("scanner.py").read_text()
        output = self.run(["python3", "-", *args], input=source)
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            raise CommandError(
                self.name, ["python3", "-", *args], output[:200]
            ) from None

    def url(self, path: str) -> str:
        """Git URL used by the local machine to reach ``path`` on this host."""
        return path

    def wrap(self, args: list[str]) -> list[str]:
        """Command line that runs ``args`` on this host. Identity for the local host."""
        return args

    def peer_env(self) -> dict[str, str]:
        """Extra environment for a git command whose argument reaches this host.

        The base class runs locally, so nothing is needed.
        """
        return {}


class RemoteHost(Host):
    """A machine reached over ssh, using the multiplexed connection ``wrap`` opens."""

    def url(self, path: str) -> str:
        return f"{self.config.ssh}:{path}"

    def wrap(self, args: list[str]) -> list[str]:
        return ["ssh", *SSH_OPTIONS, self.config.ssh, shlex.join(args)]

    def peer_env(self) -> dict[str, str]:
        """Reuse the multiplexed ssh connection for git's own ssh transport.

        Without this, ``git fetch``/``push``/``clone`` against a
        ``user@host:path`` URL opens and authenticates a brand new ssh
        connection instead of reusing the one ``wrap`` keeps alive.
        """
        return {"GIT_SSH_COMMAND": shlex.join(["ssh", *SSH_OPTIONS])}
