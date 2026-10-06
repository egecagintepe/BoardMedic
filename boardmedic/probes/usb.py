"""USB device detection probes."""

from __future__ import annotations

import json
import re
import sys

from boardmedic.core.runner import CommandRunner
from boardmedic.models import RockchipDevice, USBDevice

# ---------------------------------------------------------------------------
# Rockchip known PID tables
# ---------------------------------------------------------------------------

ROCKCHIP_VID = "2207"

# PID -> (mode, description)
ROCKCHIP_PID_TABLE: dict[str, tuple[str, str]] = {
    "320a": ("loader", "RK3066 Loader"),
    "320b": ("maskrom", "RK3066 MaskROM"),
    "320c": ("loader", "RK3188 Loader"),
    "320d": ("loader", "RK3188 Loader"),
    "330a": ("loader", "RK3288 Loader"),
    "330b": ("maskrom", "RK3288 MaskROM"),
    "330c": ("loader", "RK3328/RK3399 Loader"),
    "330d": ("maskrom", "RK3399 MaskROM"),
    "330e": ("maskrom", "RK3368 MaskROM"),
    "350a": ("maskrom", "RK3568/RK3566 MaskROM"),
    "350b": ("loader", "RK3568/RK3566 Loader"),
    "350c": ("loader", "RK3566 Loader"),
    "350d": ("maskrom", "RK3588 MaskROM"),
    "350e": ("loader", "RK3588 Loader"),
    "310c": ("loader", "RK3399Pro Loader"),
    "0006": ("loader", "Rockchip Generic Loader"),
}


# ---------------------------------------------------------------------------
# Linux USB probe
# ---------------------------------------------------------------------------


def _parse_lsusb_line(line: str) -> USBDevice | None:
    """Parse a single lsusb -v or normal output line."""
    # Standard lsusb line: Bus 001 Device 002: ID 2207:350a Fuzhou Rockchip...
    m = re.match(
        r"Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s*(.*)",
        line.strip(),
    )
    if not m:
        return None
    bus, dev, vid, pid, desc = int(m.group(1)), int(m.group(2)), m.group(3).lower(), m.group(4).lower(), m.group(5).strip()
    return USBDevice(bus=bus, device=dev, vid=vid, pid=pid, description=desc or None, raw=line.strip())


def probe_usb_linux(runner: CommandRunner) -> list[USBDevice]:
    """Enumerate USB devices on Linux using lsusb."""
    result = runner.run(["lsusb"], timeout=10, tool_name="lsusb")
    devices: list[USBDevice] = []
    if result.exit_code != 0 or not result.stdout:
        return devices
    for line in result.stdout.splitlines():
        dev = _parse_lsusb_line(line)
        if dev:
            devices.append(dev)
    return devices


def probe_usb_from_fixture(fixture_text: str) -> list[USBDevice]:
    """Parse lsusb output from a fixture file."""
    devices: list[USBDevice] = []
    for line in fixture_text.splitlines():
        dev = _parse_lsusb_line(line)
        if dev:
            devices.append(dev)
    return devices


# ---------------------------------------------------------------------------
# Windows USB probe
# ---------------------------------------------------------------------------


def probe_usb_windows(runner: CommandRunner) -> list[USBDevice]:
    """Enumerate USB devices on Windows using PowerShell Get-PnpDevice."""
    script = (
        "Get-PnpDevice -PresentOnly | "
        "Where-Object { $_.InstanceId -like 'USB*' } | "
        "Select-Object InstanceId, FriendlyName, Status | "
        "ConvertTo-Json -Depth 3"
    )
    result = runner.powershell(script, timeout=20, tool_name="Get-PnpDevice")
    devices: list[USBDevice] = []
    if result.exit_code != 0 or not result.stdout:
        return devices
    try:
        raw = json.loads(result.stdout.strip())
        if isinstance(raw, dict):
            raw = [raw]
        for entry in raw:
            iid = entry.get("InstanceId", "")
            # Extract VID/PID from InstanceId like USB\VID_2207&PID_350A\...
            vm = re.search(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})", iid)
            if vm:
                vid, pid = vm.group(1).lower(), vm.group(2).lower()
                devices.append(USBDevice(
                    vid=vid, pid=pid,
                    description=entry.get("FriendlyName"),
                    raw=iid,
                ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return devices


# ---------------------------------------------------------------------------
# Rockchip detection
# ---------------------------------------------------------------------------


def identify_rockchip_devices(usb_devices: list[USBDevice]) -> list[RockchipDevice]:
    """Filter USB devices and identify Rockchip ones with mode detection."""
    rk_devices: list[RockchipDevice] = []
    for dev in usb_devices:
        if dev.vid.lower() != ROCKCHIP_VID:
            continue
        pid = dev.pid.lower() if dev.pid else ""
        mode = "unknown"
        if pid in ROCKCHIP_PID_TABLE:
            mode, chip_desc = ROCKCHIP_PID_TABLE[pid]
            if not dev.description:
                dev.description = chip_desc
        rk_dev = RockchipDevice(usb=dev, mode=mode)
        rk_devices.append(rk_dev)
    return rk_devices


# ---------------------------------------------------------------------------
# Main USB probe dispatcher
# ---------------------------------------------------------------------------


class USBProbe:
    """Cross-platform USB probe."""

    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def probe(
        self,
        fixture_text: str | None = None,
    ) -> tuple[list[USBDevice], list[RockchipDevice]]:
        """
        Enumerate USB devices.

        Returns (all_devices, rockchip_devices).
        Uses fixture_text if provided (for offline testing).
        """
        if fixture_text is not None:
            devices = probe_usb_from_fixture(fixture_text)
        elif sys.platform.startswith("linux"):
            devices = probe_usb_linux(self.runner)
        elif sys.platform.startswith("win"):
            devices = probe_usb_windows(self.runner)
        else:
            devices = []

        rk_devices = identify_rockchip_devices(devices)
        return devices, rk_devices
