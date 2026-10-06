"""Tests for command runner - dry-run, secret redaction, timeout, missing tools."""

from __future__ import annotations

import sys

from boardmedic.core.runner import (
    CommandRunner,
    is_dangerous_command,
    redact_secrets,
)

# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

def test_redact_password():
    text = "password=mysecretpassword123"
    result = redact_secrets(text)
    assert "mysecretpassword123" not in result
    assert "REDACTED" in result


def test_redact_token():
    text = "token=ghp_abcdefghijk1234567890"
    result = redact_secrets(text)
    assert "ghp_abcdefghijk" not in result


def test_redact_api_key():
    text = "api_key=sk-1234567890abcdef"
    result = redact_secrets(text)
    assert "sk-1234567890" not in result


def test_safe_text_unchanged():
    text = "lsblk --json -o NAME,SIZE,TYPE"
    result = redact_secrets(text)
    assert result == text


# ---------------------------------------------------------------------------
# Dangerous command detection
# ---------------------------------------------------------------------------

def test_dd_is_dangerous():
    assert is_dangerous_command(["dd", "if=/dev/zero", "of=/dev/sda"])


def test_wipefs_is_dangerous():
    assert is_dangerous_command(["wipefs", "-a", "/dev/sda"])


def test_mkfs_is_dangerous():
    assert is_dangerous_command(["mkfs.ext4", "/dev/sda1"])


def test_lsblk_is_safe():
    assert not is_dangerous_command(["lsblk", "--json"])


def test_ip_is_safe():
    assert not is_dangerous_command(["ip", "addr"])


# ---------------------------------------------------------------------------
# Command runner basic
# ---------------------------------------------------------------------------

def test_runner_echo():
    runner = CommandRunner()
    if sys.platform.startswith("win"):
        result = runner.run(["cmd", "/c", "echo", "hello"])
    else:
        result = runner.run(["echo", "hello"])
    assert result.exit_code == 0
    assert "hello" in result.stdout


def test_runner_missing_tool():
    runner = CommandRunner()
    result = runner.run(["nonexistent_tool_xyz_12345"])
    assert result.exit_code == -1
    assert result.error_message is not None
    assert "not found" in result.error_message.lower()


def test_runner_timeout():
    runner = CommandRunner()
    if sys.platform.startswith("win"):
        # timeout.exe fails with stdin redirection; use powershell
        result = runner.run(
            ["powershell", "-NonInteractive", "-Command", "Start-Sleep -Seconds 30"],
            timeout=0.3
        )
    else:
        result = runner.run(["sleep", "30"], timeout=0.3)
    assert result.timed_out is True, f"Expected timeout, got exit_code={result.exit_code}, error={result.error_message}"
    assert result.exit_code == -1


def test_dry_run_blocks_destructive():
    """Destructive commands must not execute in dry-run mode."""
    runner = CommandRunner(dry_run=True)
    result = runner.run(
        ["dd", "if=/dev/zero", "of=/dev/null", "count=1"],
        destructive=True,
    )
    # Should return immediately with dry-run note
    assert result.dry_run is True
    assert "DRY-RUN" in result.stdout or "dry" in result.stdout.lower()
    # exit_code should be 0 (simulated success)
    assert result.exit_code == 0


def test_runner_history():
    runner = CommandRunner()
    if sys.platform.startswith("win"):
        runner.run(["cmd", "/c", "echo", "test"])
    else:
        runner.run(["echo", "test"])
    assert len(runner.history) >= 1


def test_check_tool_existing():
    runner = CommandRunner()
    # python should always be available
    assert runner.check_tool("python") or runner.check_tool("python3")


def test_check_tool_missing():
    runner = CommandRunner()
    assert not runner.check_tool("totally_nonexistent_tool_xyz_99999")


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def test_platform_detection():
    from boardmedic.core.runner import get_current_platform
    platform = get_current_platform()
    assert platform in ("windows", "linux", "macos", "unknown")


def test_platform_info_runs():
    """PlatformInfo should run without crashing regardless of what's installed."""
    from boardmedic.platform import PlatformInfo
    info = PlatformInfo()
    assert info.platform is not None
    assert info.os_version
    assert isinstance(info.tools, dict)
    assert isinstance(info.elevated, bool)
