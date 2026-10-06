"""Storage enumeration and normalization.

SECURITY CRITICAL: This module identifies storage devices and must never
emit destructive commands.  All identification logic is strictly read-only.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

from boardmedic.core.runner import CommandRunner
from boardmedic.models import (
    SafetyStatus,
    StorageClass,
    StorageDevice,
    StoragePartition,
)

# ---------------------------------------------------------------------------
# Root disk detection
# ---------------------------------------------------------------------------


def get_root_disk_linux() -> str | None:
    """
    Return the block device backing the root filesystem on Linux.

    Example: '/dev/mmcblk0'
    """
    try:
        result = _get_lsblk_json()
        if result is None:
            return None
        # Walk block devices looking for / mountpoint
        for dev in result.get("blockdevices", []):
            found = _find_root_in_lsblk(dev)
            if found:
                return found
    except Exception:
        pass
    return None


def _find_root_in_lsblk(dev: dict) -> str | None:
    """Recursively search lsblk device tree for root mountpoint."""
    mp = dev.get("mountpoint") or dev.get("mountpoints", [None])[0]
    if mp == "/":
        return f"/dev/{dev['name']}"
    for child in dev.get("children", []):
        found = _find_root_in_lsblk(child)
        if found:
            # Return parent disk name
            return f"/dev/{dev['name']}"
    return None


def _get_root_parent_disk_linux(runner: CommandRunner) -> str | None:
    """Return parent disk of the root partition, e.g. /dev/mmcblk0."""
    try:
        r = runner.run(
            ["findmnt", "-n", "-o", "SOURCE", "/"],
            timeout=5, tool_name="findmnt"
        )
        if r.exit_code == 0 and r.stdout.strip():
            src = r.stdout.strip()
            # e.g. /dev/mmcblk0p2 -> /dev/mmcblk0
            # e.g. /dev/sda1 -> /dev/sda
            parent = _partition_to_disk(src)
            return parent
    except Exception:
        pass
    return None


def _partition_to_disk(part: str) -> str:
    """Convert partition path to parent disk path."""
    # /dev/mmcblk0p2 -> /dev/mmcblk0
    m = re.match(r"(/dev/mmcblk\d+)p\d+", part)
    if m:
        return m.group(1)
    # /dev/sda1 -> /dev/sda
    m2 = re.match(r"(/dev/[a-z]+)\d+", part)
    if m2:
        return m2.group(1)
    return part


# ---------------------------------------------------------------------------
# Linux lsblk parsing
# ---------------------------------------------------------------------------


_lsblk_cache: dict | None = None


def _get_lsblk_json(runner: CommandRunner | None = None) -> dict | None:
    """Run lsblk --json and return parsed dict."""
    global _lsblk_cache
    if _lsblk_cache is not None:
        return _lsblk_cache
    if runner is None:
        runner = CommandRunner()
    r = runner.run(
        ["lsblk", "--json", "-o",
         "NAME,PATH,MODEL,SERIAL,SIZE,ROTA,RM,HOTPLUG,TYPE,TRAN,"
         "MOUNTPOINT,MOUNTPOINTS,LABEL,UUID,FSTYPE,PKNAME,VENDOR,"
         "HCTL,MAJ:MIN"],
        timeout=15, tool_name="lsblk"
    )
    if r.exit_code != 0 or not r.stdout:
        return None
    try:
        data = json.loads(r.stdout)
        _lsblk_cache = data
        return data
    except json.JSONDecodeError:
        return None


def parse_lsblk_json(raw_json: str) -> list[StorageDevice]:
    """Parse lsblk JSON output into StorageDevice objects."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return []

    devices: list[StorageDevice] = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        d = _parse_lsblk_disk(dev)
        devices.append(d)
    return devices


def _parse_lsblk_disk(dev: dict) -> StorageDevice:
    """Convert a single lsblk disk entry to StorageDevice."""
    name = dev.get("name", "")
    path = dev.get("path") or f"/dev/{name}"
    size_str = dev.get("size", "")
    size_bytes = _parse_size_str(size_str, dev.get("size"))

    removable = _truthy(dev.get("rm")) or _truthy(dev.get("hotplug"))
    transport = (dev.get("tran") or "").lower() or None
    model = dev.get("model") or None
    serial = dev.get("serial") or None
    vendor = dev.get("vendor") or None

    # Determine storage class from transport
    storage_class = _classify_transport(name, transport, removable)

    # Collect mount points from children
    mount_points: list[str] = []
    partitions: list[StoragePartition] = []
    for child in dev.get("children", []):
        mp_list = child.get("mountpoints") or []
        if child.get("mountpoint"):
            mp_list = [child["mountpoint"]]
        for mp in mp_list:
            if mp and mp not in mount_points:
                mount_points.append(mp)
        part = StoragePartition(
            name=child.get("name", ""),
            path=child.get("path"),
            size_bytes=_parse_size_str(child.get("size", "")),
            filesystem=child.get("fstype"),
            label=child.get("label"),
            uuid=child.get("uuid"),
            mountpoint=mp_list[0] if mp_list else None,
        )
        partitions.append(part)

    return StorageDevice(
        name=name,
        path=path,
        model=model.strip() if model else None,
        serial=serial,
        vendor=vendor.strip() if vendor else None,
        size_bytes=size_bytes,
        removable=removable,
        transport=transport,
        storage_class=storage_class,
        partitions=partitions,
        mount_points=mount_points,
        raw=dev,
    )


def _parse_size_str(size_str: Any | None, fallback: Any | None = None) -> int | None:
    """Parse size string like '29.1G' or '512G' to bytes."""
    if size_str is None:
        size_str = fallback
    if size_str is None:
        return None
    if isinstance(size_str, (int, float)):
        return int(size_str)
    s = str(size_str).strip().upper()
    units = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    m = re.match(r"^([\d.]+)\s*([BKMGT]?)$", s)
    if m:
        val = float(m.group(1))
        unit = m.group(2) or "B"
        return int(val * units.get(unit, 1))
    return None


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v != 0
    if isinstance(v, str):
        return v.lower() in ("1", "true", "yes")
    return False


def _classify_transport(name: str, transport: str | None, removable: bool) -> StorageClass:
    """Heuristically classify storage based on name/transport/removable."""
    if transport == "usb":
        return StorageClass.USB_FLASH
    if transport == "nvme" or name.startswith("nvme"):
        return StorageClass.NVME
    if transport == "sata":
        return StorageClass.SATA
    if transport == "mmc" or name.startswith("mmcblk"):
        if removable:
            return StorageClass.SD_CARD
        return StorageClass.EMMC_INTERNAL
    return StorageClass.UNKNOWN


# ---------------------------------------------------------------------------
# Windows storage probing
# ---------------------------------------------------------------------------


def probe_storage_windows(runner: CommandRunner) -> list[StorageDevice]:
    """Enumerate storage on Windows using PowerShell Get-Disk."""
    script = (
        "Get-Disk | "
        "Select-Object Number, FriendlyName, UniqueId, Size, IsBoot, IsSystem, "
        "BusType, PartitionStyle, IsReadOnly, IsRemovable | "
        "ConvertTo-Json -Depth 3"
    )
    result = runner.powershell(script, timeout=20, tool_name="Get-Disk")
    devices: list[StorageDevice] = []
    if result.exit_code != 0 or not result.stdout:
        return devices
    try:
        raw = json.loads(result.stdout.strip())
        if isinstance(raw, dict):
            raw = [raw]
        for entry in raw:
            num = entry.get("Number", 0)
            name = f"Disk {num}"
            path = f"\\\\.\\PhysicalDrive{num}"
            size_bytes = entry.get("Size")
            if isinstance(size_bytes, str):
                try:
                    size_bytes = int(size_bytes)
                except ValueError:
                    size_bytes = None
            removable = bool(entry.get("IsRemovable", False))
            bus_type = (entry.get("BusType") or "").lower()
            is_boot = bool(entry.get("IsBoot", False))
            is_system = bool(entry.get("IsSystem", False))

            storage_class = StorageClass.UNKNOWN
            if bus_type == "usb":
                storage_class = StorageClass.USB_FLASH
            elif bus_type == "nvme":
                storage_class = StorageClass.NVME
            elif bus_type in ("sata", "ata"):
                storage_class = StorageClass.SATA
            elif bus_type == "mmc":
                storage_class = StorageClass.SD_CARD if removable else StorageClass.EMMC_INTERNAL

            dev = StorageDevice(
                name=name,
                path=path,
                model=entry.get("FriendlyName"),
                serial=entry.get("UniqueId"),
                size_bytes=size_bytes,
                removable=removable,
                transport=bus_type or None,
                storage_class=storage_class,
                is_system_disk=is_system or is_boot,
                raw=entry,
            )
            if is_system or is_boot:
                dev.safety_status = SafetyStatus.PROTECTED_SYSTEM_DISK
            devices.append(dev)
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return devices


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------


def parse_storage_from_fixture(lsblk_json_text: str) -> list[StorageDevice]:
    """Parse storage devices from a fixture lsblk JSON text."""
    return parse_lsblk_json(lsblk_json_text)


# ---------------------------------------------------------------------------
# Main storage probe
# ---------------------------------------------------------------------------


class StorageProbe:
    """Cross-platform storage enumeration."""

    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def probe(
        self,
        fixture_lsblk: str | None = None,
    ) -> list[StorageDevice]:
        global _lsblk_cache
        _lsblk_cache = None  # reset cache

        if fixture_lsblk is not None:
            return parse_storage_from_fixture(fixture_lsblk)
        if sys.platform.startswith("linux"):
            return self._probe_linux()
        if sys.platform.startswith("win"):
            return probe_storage_windows(self.runner)
        return []

    def _probe_linux(self) -> list[StorageDevice]:
        """Enumerate storage on Linux via lsblk."""
        r = self.runner.run(
            ["lsblk", "--json", "-b", "-o",
             "NAME,PATH,MODEL,SERIAL,SIZE,ROTA,RM,HOTPLUG,TYPE,TRAN,"
             "MOUNTPOINT,MOUNTPOINTS,LABEL,UUID,FSTYPE,PKNAME,VENDOR"],
            timeout=15, tool_name="lsblk"
        )
        if r.exit_code != 0 or not r.stdout:
            return []
        return parse_lsblk_json(r.stdout)

    def get_root_parent_disk(self) -> str | None:
        """Return the disk device that backs the running root filesystem."""
        if sys.platform.startswith("linux"):
            return _get_root_parent_disk_linux(self.runner)
        if sys.platform.startswith("win"):
            return self._get_windows_system_disk()
        return None

    def _get_windows_system_disk(self) -> str | None:
        """Return Windows system disk path."""
        script = (
            "Get-Disk | Where-Object {$_.IsSystem -eq $true} | "
            "Select-Object -ExpandProperty Number"
        )
        r = self.runner.powershell(script, timeout=10)
        if r.exit_code == 0 and r.stdout.strip():
            try:
                num = int(r.stdout.strip())
                return f"\\\\.\\PhysicalDrive{num}"
            except ValueError:
                pass
        return None
