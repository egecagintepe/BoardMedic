"""Session management for BoardMedic."""

from __future__ import annotations

import json
import os
import socket
from datetime import UTC, datetime
from pathlib import Path

from boardmedic.core.runner import CommandRunner, get_current_platform
from boardmedic.models import (
    CommandResult,
    DiagnosticSession,
    SessionInfo,
)


def _get_session_dir_name(profile_id: str | None = None) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    suffix = f"_{profile_id}" if profile_id else ""
    return f"{ts}{suffix}"


class Session:
    """
    Manages a BoardMedic diagnostic session.

    Handles session directory creation, data accumulation, command logging,
    and raw evidence storage.
    """

    def __init__(
        self,
        profile_id: str | None = None,
        fixture_path: Path | None = None,
        session_base: Path | None = None,
        dry_run: bool = False,
        elevated: bool = False,
    ) -> None:
        self.platform = get_current_platform()
        self.dry_run = dry_run

        # Session data
        self.data = DiagnosticSession()
        self.data.info = SessionInfo(
            platform=self.platform,
            profile_id=profile_id,
            fixture_path=str(fixture_path) if fixture_path else None,
            dry_run=dry_run,
            elevated=elevated,
        )

        # Try to get host info safely
        try:
            self.data.info.host_username = os.environ.get("USER") or os.environ.get("USERNAME")
        except Exception:
            pass
        try:
            self.data.info.host_hostname = socket.gethostname()
        except Exception:
            pass

        # Session directory
        base = session_base or Path("boardmedic-sessions")
        dir_name = _get_session_dir_name(profile_id)
        self.session_dir = base / dir_name
        self.data.info.session_dir = str(self.session_dir)

        # Command runner
        self.runner = CommandRunner(dry_run=dry_run)

    def ensure_dirs(self) -> None:
        """Create session directory structure."""
        (self.session_dir / "raw").mkdir(parents=True, exist_ok=True)
        (self.session_dir / "logs").mkdir(parents=True, exist_ok=True)

    def save_raw(self, name: str, content: str) -> None:
        """Save raw evidence to session raw/ directory."""
        self.ensure_dirs()
        raw_path = self.session_dir / "raw" / name
        raw_path.write_text(content, encoding="utf-8", errors="replace")
        self.data.raw_evidence[name] = str(raw_path)

    def log_command(self, result: CommandResult) -> None:
        """Append a command result to the session log."""
        self.ensure_dirs()
        self.data.commands.append(result)
        log_path = self.session_dir / "logs" / "commands.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(result.model_dump_json() + "\n")

    def save_session_json(self) -> Path:
        """Persist the session data to session.json."""
        self.ensure_dirs()
        path = self.session_dir / "session.json"
        path.write_text(
            self.data.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return path

    def save_findings_json(self) -> Path:
        """Persist findings to findings.json."""
        self.ensure_dirs()
        path = self.session_dir / "findings.json"
        findings = [f.model_dump(mode="json") for f in self.data.findings]
        path.write_text(json.dumps(findings, indent=2), encoding="utf-8")
        return path
