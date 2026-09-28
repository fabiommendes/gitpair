"""Run commands on the local machine or on the peer over ssh."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from importlib import resources
from typing import IO

from gitpair.config import HostConfig

SSH_OPTIONS = [
    "-o", "ControlMaster=auto",
    "-o", "ControlPath=~/.ssh/gitpair-%C",
    "-o", "ControlPersist=60",
]  # fmt: skip


class CommandError(Exception):
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
        """Run a command that reads or writes binary streams, like tar."""
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

    def git(self, path: str, *args: str) -> str:
        return self.run(["git", "-C", path, *args])

    def shell(self, script: str, *, input: str | None = None) -> str:
        return self.run(["sh", "-c", script], input=input)

    def scan(self, depth: int) -> dict:
        data = self.python("scan", self.config.root, str(depth))
        self.root = data["root"]
        return data

    def manifest(self, repo_path: str, entries: list[str]) -> dict[str, list[int]]:
        """Size and mtime of every regular file under ``entries``."""
        return self.python("manifest", repo_path, *entries)

    def python(self, *args: str) -> dict:
        """Run ``scanner.py`` with ``args`` and parse its JSON output."""
        source = resources.files("gitpair").joinpath("scanner.py").read_text()
        return json.loads(self.run(["python3", "-", *args], input=source))

    def url(self, path: str) -> str:
        """Git URL used by the local machine to reach ``path`` on this host."""
        return path

    def wrap(self, args: list[str]) -> list[str]:
        return args


class RemoteHost(Host):
    def url(self, path: str) -> str:
        return f"{self.config.ssh}:{path}"

    def wrap(self, args: list[str]) -> list[str]:
        return ["ssh", *SSH_OPTIONS, self.config.ssh, shlex.join(args)]
