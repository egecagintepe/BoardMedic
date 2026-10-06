"""ADB and Fastboot probes."""

from __future__ import annotations

from boardmedic.core.runner import CommandRunner
from boardmedic.models import ToolStatus


class ADBDevice:
    """Normalized ADB device."""
    def __init__(self, serial: str, state: str) -> None:
        self.serial = serial
        self.state = state

    def __repr__(self) -> str:
        return f"ADBDevice(serial={self.serial!r}, state={self.state!r})"


class FastbootDevice:
    """Normalized fastboot device."""
    def __init__(self, serial: str, state: str = "fastboot") -> None:
        self.serial = serial
        self.state = state

    def __repr__(self) -> str:
        return f"FastbootDevice(serial={self.serial!r})"


def probe_adb(runner: CommandRunner) -> tuple[ToolStatus, list[ADBDevice]]:
    """
    Probe ADB for connected devices.

    Returns (tool_status, devices).
    Does NOT reboot or erase during detection.
    """
    if not runner.check_tool("adb"):
        return ToolStatus.UNAVAILABLE, []

    result = runner.run(["adb", "devices"], timeout=15, tool_name="adb")
    if result.exit_code != 0:
        return ToolStatus.FAILED, []

    devices: list[ADBDevice] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            serial, state = parts[0].strip(), parts[1].strip()
            if serial and state:
                devices.append(ADBDevice(serial=serial, state=state))

    return ToolStatus.AVAILABLE, devices


def probe_fastboot(runner: CommandRunner) -> tuple[ToolStatus, list[FastbootDevice]]:
    """
    Probe fastboot for connected devices.

    Does NOT erase or reboot.
    """
    if not runner.check_tool("fastboot"):
        return ToolStatus.UNAVAILABLE, []

    result = runner.run(["fastboot", "devices"], timeout=15, tool_name="fastboot")
    if result.exit_code != 0:
        return ToolStatus.FAILED, []

    devices: list[FastbootDevice] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if parts:
            serial = parts[0]
            devices.append(FastbootDevice(serial=serial))

    return ToolStatus.AVAILABLE, devices


class RockchipToolProbe:
    """Probe for Rockchip upgrade_tool and rkdeveloptool."""

    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner
        self.upgrade_tool: str | None = runner.which("upgrade_tool")
        self.rkdeveloptool: str | None = runner.which("rkdeveloptool")

    def tool_status(self) -> dict[str, ToolStatus]:
        return {
            "upgrade_tool": ToolStatus.AVAILABLE if self.upgrade_tool else ToolStatus.UNAVAILABLE,
            "rkdeveloptool": ToolStatus.AVAILABLE if self.rkdeveloptool else ToolStatus.UNAVAILABLE,
        }

    def list_devices(self) -> list[str]:
        """
        List connected Rockchip devices (read-only).
        Tries rkdeveloptool first, then upgrade_tool.
        """
        if self.rkdeveloptool:
            result = self.runner.run(
                ["rkdeveloptool", "ld"],
                timeout=10,
                tool_name="rkdeveloptool",
            )
            if result.exit_code == 0 and result.stdout:
                return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if self.upgrade_tool:
            result = self.runner.run(
                ["upgrade_tool", "LD"],
                timeout=10,
                tool_name="upgrade_tool",
            )
            if result.exit_code == 0 and result.stdout:
                return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return []

    def get_chip_info(self) -> str | None:
        """Query chip information (read-only)."""
        if self.rkdeveloptool:
            result = self.runner.run(
                ["rkdeveloptool", "ci"],
                timeout=10,
                tool_name="rkdeveloptool",
            )
            if result.exit_code == 0 and result.stdout:
                return result.stdout.strip()
        return None
