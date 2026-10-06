"""Platform detection and capability reporting."""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import sys
from typing import Optional

from boardmedic.models import Platform, ToolStatus

LINUX_TOOLS = [
    "lsusb", "lsblk", "ip", "udevadm", "ssh", "adb", "fastboot",
    "upgrade_tool", "rkdeveloptool", "dmesg", "findmnt", "blkid",
    "mmcli", "fdisk", "parted", "dd", "wipefs",
]

WINDOWS_TOOLS = [
    "powershell", "adb", "fastboot", "upgrade_tool", "rkdeveloptool",
    "ssh", "pnputil",
]


def detect_platform() -> Platform:
    if sys.platform.startswith("win"):
        return Platform.WINDOWS
    if sys.platform.startswith("linux"):
        return Platform.LINUX
    if sys.platform.startswith("darwin"):
        return Platform.MACOS
    return Platform.UNKNOWN


def is_elevated() -> bool:
    """Return True if the process has elevated/admin privileges."""
    if sys.platform.startswith("win"):
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    else:
        return os.geteuid() == 0


def get_os_version() -> str:
    """Return a human-readable OS version string."""
    if sys.platform.startswith("win"):
        ver = platform.version()
        release = platform.release()
        return f"Windows {release} ({ver})"
    if sys.platform.startswith("linux"):
        try:
            import distro  # type: ignore[import]
            return distro.name(pretty=True)
        except ImportError:
            pass
        # Fallback: /etc/os-release
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        return f"Linux {platform.release()}"
    return f"{sys.platform} {platform.release()}"


def check_tool(name: str) -> ToolStatus:
    """Check availability of an external tool."""
    if shutil.which(name):
        return ToolStatus.AVAILABLE
    return ToolStatus.UNAVAILABLE


def check_debugfs() -> ToolStatus:
    """Check if Linux debugfs is mounted and accessible."""
    debugfs_path = "/sys/kernel/debug"
    if sys.platform.startswith("win"):
        return ToolStatus.NOT_SUPPORTED
    if not os.path.exists(debugfs_path):
        return ToolStatus.UNAVAILABLE
    try:
        entries = os.listdir(debugfs_path)
        if entries:
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE
    except PermissionError:
        return ToolStatus.PERMISSION_REQUIRED


def check_serial_support() -> ToolStatus:
    """Check if serial port support (pyserial) is available."""
    try:
        import serial  # type: ignore[import]
        return ToolStatus.AVAILABLE
    except ImportError:
        return ToolStatus.UNAVAILABLE


def check_pyusb() -> ToolStatus:
    """Check if pyusb is available."""
    try:
        import usb.core  # type: ignore[import]
        return ToolStatus.AVAILABLE
    except ImportError:
        return ToolStatus.UNAVAILABLE


class PlatformInfo:
    """Aggregated platform capability report."""

    def __init__(self) -> None:
        self.platform = detect_platform()
        self.os_version = get_os_version()
        self.python_version = sys.version
        self.elevated = is_elevated()
        self.tools: dict[str, ToolStatus] = {}
        self.capabilities: dict[str, ToolStatus] = {}
        self._probe()

    def _probe(self) -> None:
        tool_list = WINDOWS_TOOLS if self.platform == Platform.WINDOWS else LINUX_TOOLS
        for tool in tool_list:
            self.tools[tool] = check_tool(tool)

        self.capabilities["serial"] = check_serial_support()
        self.capabilities["pyusb"] = check_pyusb()
        self.capabilities["debugfs"] = check_debugfs()

    def tool_status(self, name: str) -> ToolStatus:
        return self.tools.get(name, ToolStatus.UNAVAILABLE)

    def is_tool_available(self, name: str) -> bool:
        return self.tool_status(name) == ToolStatus.AVAILABLE

    def as_dict(self) -> dict:
        return {
            "platform": self.platform.value,
            "os_version": self.os_version,
            "python_version": self.python_version,
            "elevated": self.elevated,
            "tools": {k: v.value for k, v in self.tools.items()},
            "capabilities": {k: v.value for k, v in self.capabilities.items()},
        }
