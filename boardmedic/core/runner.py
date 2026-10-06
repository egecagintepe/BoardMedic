"""Command execution abstraction for BoardMedic.

All external subprocess calls MUST go through this module.
Never scatter subprocess.run() calls throughout the codebase.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

from boardmedic.models import CommandResult

# ---------------------------------------------------------------------------
# Secret redaction patterns
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    (re.compile(r"(password[=:\s]+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(passwd[=:\s]+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(token[=:\s]+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(secret[=:\s]+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(key[=:\s]+)[A-Za-z0-9+/]{20,}={0,2}", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(auth[=:\s]+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(api[_-]?key[=:\s]+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    # SSH private key markers
    (re.compile(r"-----BEGIN [A-Z]+ PRIVATE KEY-----.*?-----END [A-Z]+ PRIVATE KEY-----",
                re.DOTALL), "[PRIVATE_KEY_REDACTED]"),
    # Generic base64-looking tokens (GitHub/etc style)
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "[GH_TOKEN_REDACTED]"),
]

# ---------------------------------------------------------------------------
# Dangerous command pattern detection
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS = [
    re.compile(r"\bdd\b"),
    re.compile(r"\bwipefs\b"),
    re.compile(r"\bblkdiscard\b"),
    re.compile(r"\bsgdisk\b.*--zap"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bmmc\s+erase\b"),
    re.compile(r"\bflash\b"),
    re.compile(r"\bformat\b"),
    re.compile(r"\bshred\b"),
    re.compile(r"\bfdisk\b"),
    re.compile(r"\bparted\b.*rm\b"),
    re.compile(r"\bpartprobe\b"),
    re.compile(r"\bze?ro\s+/dev/"),
]


def redact_secrets(text: str) -> str:
    """Redact known secret patterns from text."""
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def is_dangerous_command(cmd: list[str] | str) -> bool:
    """Check if a command matches known dangerous patterns."""
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
    return any(p.search(cmd_str) for p in _DANGEROUS_PATTERNS)


def get_current_platform() -> str:
    """Return normalized platform string."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform.startswith("darwin"):
        return "macos"
    return "unknown"


class CommandRunner:
    """
    Central command execution abstraction.

    All external process invocations should use this class.
    Provides: timeout, capture, logging, dry-run, safety classification,
    secret redaction, and structured result objects.
    """

    def __init__(
        self,
        dry_run: bool = False,
        cwd: str | Path | None = None,
        default_timeout: float = 30.0,
        log_commands: bool = True,
    ) -> None:
        self.dry_run = dry_run
        self.cwd = str(cwd) if cwd else None
        self.default_timeout = default_timeout
        self.log_commands = log_commands
        self._history: list[CommandResult] = []
        self.platform = get_current_platform()

    @property
    def history(self) -> list[CommandResult]:
        return list(self._history)

    def run(
        self,
        cmd: list[str],
        timeout: float | None = None,
        cwd: str | Path | None = None,
        elevated: bool = False,
        destructive: bool = False,
        tool_name: str | None = None,
        env: dict | None = None,
    ) -> CommandResult:
        """
        Execute a command and return a structured CommandResult.

        If dry_run is True and the command is destructive, the command is
        NOT executed but the result is logged with dry_run=True.
        """
        effective_timeout = timeout if timeout is not None else self.default_timeout
        effective_cwd = str(cwd) if cwd else self.cwd

        cmd_str = " ".join(shlex.quote(str(c)) for c in cmd)
        cmd_str_redacted = redact_secrets(cmd_str)

        # Build result template
        result = CommandResult(
            command=cmd,
            command_str=cmd_str_redacted,
            platform=self.platform,
            cwd=effective_cwd,
            elevated=elevated,
            destructive=destructive,
            dry_run=self.dry_run,
            tool_name=tool_name,
        )

        # Safety: never run destructive commands in dry-run mode
        if self.dry_run and destructive:
            result.exit_code = 0
            result.stdout = f"[DRY-RUN] Would execute: {cmd_str_redacted}"
            result.stderr = ""
            if self.log_commands:
                self._history.append(result)
            return result

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=effective_timeout,
                cwd=effective_cwd,
                env=env,
            )
            elapsed = time.monotonic() - start
            result.exit_code = proc.returncode
            result.stdout = redact_secrets(proc.stdout or "")
            result.stderr = redact_secrets(proc.stderr or "")
            result.duration_seconds = elapsed
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            result.timed_out = True
            result.exit_code = -1
            result.error_message = f"Command timed out after {effective_timeout}s"
            result.duration_seconds = elapsed
        except FileNotFoundError:
            elapsed = time.monotonic() - start
            result.exit_code = -1
            result.error_message = f"Command not found: {cmd[0]}"
            result.duration_seconds = elapsed
        except PermissionError as e:
            elapsed = time.monotonic() - start
            result.exit_code = -1
            result.error_message = f"Permission denied: {e}"
            result.duration_seconds = elapsed
        except Exception as e:
            elapsed = time.monotonic() - start
            result.exit_code = -1
            result.error_message = f"Unexpected error: {e}"
            result.duration_seconds = elapsed

        if self.log_commands:
            self._history.append(result)
        return result

    def run_shell(
        self,
        cmd_str: str,
        timeout: float | None = None,
        cwd: str | Path | None = None,
        elevated: bool = False,
        destructive: bool = False,
        tool_name: str | None = None,
    ) -> CommandResult:
        """Execute a shell string command. Use with care."""
        try:
            parts = shlex.split(cmd_str)
        except ValueError:
            # Fallback: use shell=True equivalent via list
            parts = ["cmd", "/c", cmd_str] if self.platform == "windows" else ["sh", "-c", cmd_str]
        return self.run(
            parts, timeout=timeout, cwd=cwd, elevated=elevated,
            destructive=destructive, tool_name=tool_name
        )

    def check_tool(self, tool: str) -> bool:
        """Check if an external tool is available on PATH."""
        import shutil
        return shutil.which(tool) is not None

    def which(self, tool: str) -> str | None:
        """Return full path to a tool or None."""
        import shutil
        return shutil.which(tool)

    def powershell(
        self,
        script: str,
        timeout: float | None = None,
        tool_name: str | None = None,
    ) -> CommandResult:
        """Run a PowerShell script block (Windows only)."""
        if self.platform != "windows":
            result = CommandResult(
                command=["powershell", "-Command", script],
                command_str=f"powershell -Command {script}",
                platform=self.platform,
                tool_name=tool_name,
            )
            result.exit_code = -1
            result.error_message = "PowerShell not available on this platform"
            self._history.append(result)
            return result
        return self.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            timeout=timeout,
            tool_name=tool_name,
        )
