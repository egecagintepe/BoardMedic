"""Transports package - SSH, UART, ADB transport abstractions."""

from __future__ import annotations

from typing import Optional


class Transport:
    """Abstract transport for communicating with a board."""

    name: str = "abstract"

    def is_available(self) -> bool:
        return False

    def execute(self, command: str, timeout: float = 30.0) -> tuple[int, str, str]:
        """Execute command. Returns (exit_code, stdout, stderr)."""
        raise NotImplementedError


class SSHTransport(Transport):
    """SSH transport using system OpenSSH."""

    name = "ssh"

    def __init__(
        self,
        target: str,
        port: int = 22,
        username: str = "root",
        identity_file: str | None = None,
        connect_timeout: int = 10,
    ) -> None:
        self.target = target
        self.port = port
        self.username = username
        # SECURITY: never store password
        self.identity_file = identity_file
        self.connect_timeout = connect_timeout

    def is_available(self) -> bool:
        import shutil
        return bool(shutil.which("ssh"))

    def execute(self, command: str, timeout: float = 30.0) -> tuple[int, str, str]:
        from boardmedic.core.runner import CommandRunner
        runner = CommandRunner()
        cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", f"ConnectTimeout={self.connect_timeout}",
            "-o", "BatchMode=yes",
            "-p", str(self.port),
        ]
        if self.identity_file:
            cmd += ["-i", self.identity_file]
        cmd += [f"{self.username}@{self.target}", command]

        result = runner.run(cmd, timeout=timeout + self.connect_timeout)
        return (result.exit_code or -1, result.stdout, result.stderr)
