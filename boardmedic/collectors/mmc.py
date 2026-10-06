"""MMC/eMMC diagnostics collector."""

from __future__ import annotations

import re
from pathlib import Path

from boardmedic.core.runner import CommandRunner
from boardmedic.models import MMCState

# ---------------------------------------------------------------------------
# MMC kernel message patterns
# ---------------------------------------------------------------------------

MMC_PATTERNS = {
    "stuck_busy": re.compile(
        r"Card stuck being busy|card is busy|BUSY.*not clearing", re.IGNORECASE
    ),
    "init_failed": re.compile(
        r"Failed to initialize a non-removable card|mmc\d+: error -\d+ initialising",
        re.IGNORECASE
    ),
    "not_ready": re.compile(
        r"READY bit.*never set|not ready|OCR.*never.*READY|cmd1.*timeout|CMD1.*not ready",
        re.IGNORECASE
    ),
    "timeout": re.compile(r"error -110|timed? ?out|ETIMEDOUT", re.IGNORECASE),
    "crc_error": re.compile(r"CRC error|crc err", re.IGNORECASE),
    "io_error": re.compile(r"\bio error\b|I\/O error|blk_update_request.*err", re.IGNORECASE),
    "device_present": re.compile(r"mmcblk\d+:", re.IGNORECASE),
    "mmc_host": re.compile(r"([a-f0-9]+\.mmc):", re.IGNORECASE),
}

# OCR READY bit is bit 31
OCR_READY_BIT = 0x80000000


class MMCHostInfo:
    """Collected MMC host sysfs/debugfs information."""

    def __init__(self, host_name: str) -> None:
        self.host_name = host_name
        self.sysfs_path: str | None = None
        self.card_present: bool | None = None
        self.card_type: str | None = None
        self.bus_hz: int | None = None
        self.bus_width: int | None = None
        self.timing: str | None = None
        self.cid: str | None = None
        self.csd: str | None = None
        self.ext_csd: str | None = None
        self.block_device: str | None = None
        self.debugfs_data: dict[str, str] = {}
        self.raw_sysfs: dict[str, str] = {}

    def to_dict(self) -> dict:
        return {
            "host_name": self.host_name,
            "sysfs_path": self.sysfs_path,
            "card_present": self.card_present,
            "card_type": self.card_type,
            "bus_hz": self.bus_hz,
            "bus_width": self.bus_width,
            "timing": self.timing,
            "cid": self.cid,
            "block_device": self.block_device,
        }


class MMCDiagnostics:
    """MMC/eMMC diagnostic collector."""

    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def collect_hosts(
        self,
        fixture_dmesg: str | None = None,
        fixture_sysfs: dict[str, str] | None = None,
    ) -> list[MMCHostInfo]:
        """
        Collect information about all MMC hosts.

        If fixture data is provided, use it instead of real sysfs.
        """
        hosts: list[MMCHostInfo] = []

        if fixture_sysfs is not None:
            hosts = self._collect_from_fixture_sysfs(fixture_sysfs)
        else:
            hosts = self._collect_from_sysfs()

        return hosts

    def _collect_from_sysfs(self) -> list[MMCHostInfo]:
        """Collect MMC host info from /sys/class/mmc_host."""
        hosts: list[MMCHostInfo] = []
        mmc_host_path = Path("/sys/class/mmc_host")
        if not mmc_host_path.exists():
            return hosts

        for host_dir in sorted(mmc_host_path.iterdir()):
            host_name = host_dir.name  # e.g. mmc0, mmc1
            info = MMCHostInfo(host_name)
            info.sysfs_path = str(host_dir)

            # Try to read device tree path / bus-path via uevent
            uevent_path = host_dir / "uevent"
            if uevent_path.exists():
                try:
                    uevent = uevent_path.read_text()
                    for line in uevent.splitlines():
                        if "OF_NAME" in line or "OF_FULLNAME" in line:
                            info.raw_sysfs["uevent_" + line.split("=")[0]] = line
                except OSError:
                    pass

            # Check for card-specific directory
            for child in host_dir.iterdir() if host_dir.exists() else []:
                if re.match(r"mmc\d+:\d+", child.name):
                    info.card_present = True
                    # Try to read CID
                    for attr in ["cid", "csd", "type", "name"]:
                        attr_path = child / attr
                        if attr_path.exists():
                            try:
                                val = attr_path.read_text().strip()
                                if attr == "cid":
                                    info.cid = val
                                elif attr == "csd":
                                    info.csd = val
                                elif attr == "type":
                                    info.card_type = val
                                info.raw_sysfs[attr] = val
                            except OSError:
                                pass
                    # Check for block device
                    block_path = child / "block"
                    if block_path.exists():
                        for blk in block_path.iterdir():
                            info.block_device = f"/dev/{blk.name}"
                            break

            hosts.append(info)
        return hosts

    def _collect_from_fixture_sysfs(self, fixture: dict[str, str]) -> list[MMCHostInfo]:
        """Build MMC host info from fixture data (key=path, value=content)."""
        host_names: set[str] = set()

        for key in fixture:
            # e.g. "/sys/class/mmc_host/mmc0/uevent"
            m = re.search(r"mmc_host/(mmc\d+)", key)
            if m:
                host_names.add(m.group(1))
            # Also check for controller name like "fe310000.mmc"
            m2 = re.search(r"([a-f0-9]+\.mmc)", key)
            if m2:
                host_names.add(m2.group(1))

        if not host_names:
            # Create a default host from fixture if nothing found
            host_names = {"mmc0"}

        hosts = []
        for hn in sorted(host_names):
            info = MMCHostInfo(hn)
            # Populate from fixture
            for key, val in fixture.items():
                if hn in key:
                    attr = Path(key).name
                    info.raw_sysfs[attr] = val
                    if attr == "cid":
                        info.cid = val.strip()
                    elif attr == "type":
                        info.card_type = val.strip()

            # Check card presence heuristically
            card_keys = [k for k in fixture if re.search(r"mmc\d+:\d+", k)]
            info.card_present = bool(card_keys) or any(
                "cid" in k or "type" in k for k in fixture
            )
            hosts.append(info)
        return hosts

    def analyze_dmesg(
        self,
        dmesg_text: str,
        target_controller: str | None = None,
    ) -> dict[str, list[str]]:
        """
        Analyze dmesg text for MMC-related messages.

        Returns dict of pattern_name -> matching lines.
        """
        matches: dict[str, list[str]] = {k: [] for k in MMC_PATTERNS}
        matches["ocr_values"] = []

        for line in dmesg_text.splitlines():
            # Filter to target controller if specified
            if target_controller and target_controller not in line:
                # Still check for generic mmc patterns even without controller name
                if not re.search(r"\bmmc\d+\b|\bmmcblk\d+\b", line, re.IGNORECASE):
                    continue

            for name, pattern in MMC_PATTERNS.items():
                if name == "device_present":
                    continue
                if pattern.search(line):
                    matches[name].append(line.strip())

            # Extract OCR values like 0x40ff8080
            ocr_m = re.search(r"0x([0-9a-fA-F]{8})", line)
            if ocr_m and ("ocr" in line.lower() or "cmd1" in line.lower() or "mmc" in line.lower()):
                matches["ocr_values"].append(line.strip())

        # Check for mmcblk devices in dmesg
        blk_matches = MMC_PATTERNS["device_present"].findall(dmesg_text)
        matches["block_device_appearances"] = blk_matches

        return matches

    def classify_mmc_state(
        self,
        hosts: list[MMCHostInfo],
        dmesg_matches: dict[str, list[str]],
        block_devices: list[str],
    ) -> MMCState:
        """
        Classify the MMC state based on collected evidence.

        Conservative: requires positive evidence to upgrade state.
        Dmesg evidence takes priority when sysfs is unavailable (e.g., Windows/fixture).
        """
        has_host = bool(hosts)
        card_present = any(h.card_present for h in hosts)
        has_block_dev = bool(block_devices)

        has_stuck_busy = bool(dmesg_matches.get("stuck_busy"))
        has_init_failed = bool(dmesg_matches.get("init_failed"))
        has_not_ready = bool(dmesg_matches.get("not_ready"))
        has_timeout = bool(dmesg_matches.get("timeout"))
        has_ocr = bool(dmesg_matches.get("ocr_values"))

        # If dmesg clearly shows eMMC failure, use that even without sysfs hosts
        # (covers Windows / fixture-only mode where /sys/class/mmc_host is absent)
        if has_block_dev:
            if dmesg_matches.get("io_error"):
                return MMCState.IO_ERRORS
            return MMCState.BLOCK_DEVICE_PRESENT

        # Strong dmesg evidence of stuck-not-ready (prioritize over missing sysfs)
        if has_stuck_busy or (has_ocr and has_timeout) or (has_ocr and has_not_ready):
            return MMCState.CARD_RESPONDS_NOT_READY

        if has_init_failed:
            return MMCState.ENUMERATION_FAILED

        if not has_host:
            # Only classify as host-not-present if dmesg also shows nothing
            if not has_ocr and not has_stuck_busy and not has_init_failed:
                return MMCState.HOST_NOT_PRESENT
            # dmesg suggests controller exists even though sysfs doesn't show it
            return MMCState.ENUMERATION_FAILED

        if card_present and not has_block_dev:
            return MMCState.ENUMERATION_FAILED

        if has_host and not card_present:
            return MMCState.HOST_PRESENT_NO_CARD_RESPONSE

        return MMCState.HEALTH_UNKNOWN

    def check_ocr_ready(self, ocr_value_str: str) -> bool:
        """Return True if OCR READY bit (bit 31) is set."""
        try:
            val = int(ocr_value_str, 16)
            return bool(val & OCR_READY_BIT)
        except ValueError:
            return False

    def collect_dmesg(
        self,
        fixture_dmesg: str | None = None,
        filter_mmc: bool = True,
    ) -> str:
        """Collect dmesg output, filtered for MMC if requested."""
        if fixture_dmesg is not None:
            if filter_mmc:
                lines = [
                    ln for ln in fixture_dmesg.splitlines()
                    if re.search(r"mmc|mmcblk|emmc|sdio", ln, re.IGNORECASE)
                ]
                return "\n".join(lines)
            return fixture_dmesg

        result = self.runner.run(["dmesg"], timeout=10, tool_name="dmesg")
        if result.exit_code != 0:
            return ""
        text = result.stdout
        if filter_mmc:
            lines = [
                ln for ln in text.splitlines()
                if re.search(r"mmc|mmcblk|emmc|sdio", ln, re.IGNORECASE)
            ]
            return "\n".join(lines)
        return text
