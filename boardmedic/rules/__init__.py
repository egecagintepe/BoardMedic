"""Diagnostic rules engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from boardmedic.models import (
    BootChain,
    BootStage,
    BootStageResult,
    Confidence,
    DiagnosticFinding,
    DiagnosticSession,
    EvidenceItem,
    EvidenceType,
    MMCState,
    Severity,
    StageStatus,
)

# ---------------------------------------------------------------------------
# Rule base class
# ---------------------------------------------------------------------------


class DiagnosticRule(ABC):
    """
    Abstract base for a diagnostic rule.

    Each rule inspects session data and may produce a DiagnosticFinding.
    Rules are stateless and re-entrant.
    """

    id: str
    description: str
    tags: list[str] = []

    @abstractmethod
    def evaluate(self, session: DiagnosticSession) -> DiagnosticFinding | None:
        """Evaluate the rule against a session. Return finding or None."""
        ...

    def _ev(
        self,
        type_: EvidenceType,
        description: str,
        source: str | None = None,
        raw_value: str | None = None,
    ) -> EvidenceItem:
        return EvidenceItem(
            type=type_, description=description,
            source=source, raw_value=raw_value
        )

    def observed(self, desc: str, source: str | None = None, raw: str | None = None) -> EvidenceItem:
        return self._ev(EvidenceType.OBSERVED, desc, source, raw)

    def derived(self, desc: str, source: str | None = None, raw: str | None = None) -> EvidenceItem:
        return self._ev(EvidenceType.DERIVED, desc, source, raw)

    def inferred(self, desc: str, source: str | None = None, raw: str | None = None) -> EvidenceItem:
        return self._ev(EvidenceType.INFERRED, desc, source, raw)

    def hypothesis(self, desc: str, source: str | None = None, raw: str | None = None) -> EvidenceItem:
        return self._ev(EvidenceType.HYPOTHESIS, desc, source, raw)


# ---------------------------------------------------------------------------
# Concrete rules
# ---------------------------------------------------------------------------


class EMMCStuckNotReadyRule(DiagnosticRule):
    """Detect eMMC stuck in not-ready state (CMD1 never completes)."""

    id = "EMMC_STUCK_NOT_READY"
    description = "Internal eMMC responds during initialization but never transitions to READY"
    tags = ["emmc", "mmc", "initialization"]

    def evaluate(self, session: DiagnosticSession) -> DiagnosticFinding | None:
        if session.mmc_state not in (
            MMCState.CARD_RESPONDS_NOT_READY,
            MMCState.ENUMERATION_FAILED,
        ):
            return None

        evidence: list[EvidenceItem] = []
        raw_ev = session.raw_evidence

        # Look for MMC host in dmesg
        dmesg = raw_ev.get("dmesg.txt", "")

        # Check for specific OCR pattern
        import re
        ocr_values = re.findall(r"0x([0-9a-fA-F]{8})", dmesg)
        has_ocr = bool(ocr_values)
        has_stuck_busy = bool(re.search(r"Card stuck being busy|card is busy", dmesg, re.IGNORECASE))
        has_init_fail = bool(re.search(r"Failed to initialize a non-removable", dmesg, re.IGNORECASE))
        has_no_blkdev = "mmcblk" not in dmesg

        # Find controller references
        controller_refs = re.findall(r"([a-f0-9]+\.mmc)", dmesg)
        controllers = list(set(controller_refs))

        if controllers:
            evidence.append(self.observed(
                f"MMC controller(s) detected: {', '.join(controllers)}",
                source="dmesg"
            ))

        if has_ocr:
            # Check if ready bit is ever set
            from boardmedic.collectors.mmc import OCR_READY_BIT
            not_ready_values = []
            for v in ocr_values:
                try:
                    if not (int(v, 16) & OCR_READY_BIT):
                        not_ready_values.append(f"0x{v}")
                except ValueError:
                    pass
            if not_ready_values:
                sample = not_ready_values[:3]
                evidence.append(self.observed(
                    f"OCR values observed with READY bit (bit 31) NOT set: {', '.join(sample)}",
                    source="dmesg",
                    raw=not_ready_values[0] if not_ready_values else None,
                ))
                evidence.append(self.derived(
                    "READY bit (bit 31) was never asserted during CMD1 polling",
                    source="dmesg OCR analysis"
                ))

        if has_stuck_busy:
            evidence.append(self.observed(
                "Kernel reported 'Card stuck being busy' during eMMC initialization",
                source="dmesg"
            ))

        if has_init_fail:
            evidence.append(self.observed(
                "Kernel reported 'Failed to initialize a non-removable card'",
                source="dmesg"
            ))

        if has_no_blkdev:
            evidence.append(self.derived(
                "No /dev/mmcblkX device created for this controller",
                source="block device enumeration"
            ))

        evidence.append(self.inferred(
            "eMMC initialization is failing before block-device enumeration completes",
            source="combined dmesg + block device evidence"
        ))

        if session.mmc_state == MMCState.CARD_RESPONDS_NOT_READY:
            confidence = Confidence.HIGH
            severity = Severity.ERROR
        else:
            confidence = Confidence.MEDIUM
            severity = Severity.ERROR

        return DiagnosticFinding(
            id="EMMC_INIT_NOT_READY",
            severity=severity,
            confidence=confidence,
            summary="Internal eMMC responds during initialization but never transitions to READY state",
            detail=(
                "The eMMC controller is present and the device responds to CMD1 "
                "during initialization, but the READY bit in the OCR register "
                "never becomes asserted. Linux cannot complete block-device enumeration "
                "and no /dev/mmcblk device appears."
            ),
            evidence=evidence,
            interpretation=(
                "Failure occurs before normal block-device enumeration. "
                "The device is communicating but not completing initialization. "
                "This does NOT definitively confirm that the NAND storage itself is dead."
            ),
            possible_causes=[
                "eMMC internal controller fault (power/program/erase circuits)",
                "Power integrity issue (insufficient or noisy supply to eMMC VCC/VCCQ)",
                "Reset timing issue (eMMC not properly reset before initialization)",
                "Signal integrity issue on eMMC bus (CMD/CLK/DAT lines)",
                "Clock frequency too high for device in degraded state",
                "eMMC firmware corruption in internal boot partition",
                "Hardware damage to eMMC package or PCB traces",
                "Board-specific initialization timing mismatch",
            ],
            recommended_next_steps=[
                "Verify power supply to eMMC (measure VCC and VCCQ on oscilloscope)",
                "Try Rockchip USB Loader/MaskROM recovery (upgrade_tool or rkdeveloptool)",
                "Attempt driver unbind/rebind on the MMC controller",
                "Try reduced clock frequency (already attempted per fixture data)",
                "Check UART output for U-Boot eMMC initialization errors",
                "Inspect PCB for cold solder joints or damage near eMMC package",
                "If Rockchip USB tools show the device: attempt eMMC initialization via loader",
                "Consider eMMC replacement as last resort if all else fails",
            ],
            rule_id=self.id,
            tags=self.tags,
            affected_stages=[BootStage.BOOT_MEDIA],
        )


class EMMCNotDetectedRule(DiagnosticRule):
    """Detect case where MMC host controller is not present at all."""

    id = "EMMC_HOST_NOT_PRESENT"
    description = "MMC host controller not visible in sysfs"
    tags = ["emmc", "mmc", "hardware"]

    def evaluate(self, session: DiagnosticSession) -> DiagnosticFinding | None:
        if session.mmc_state != MMCState.HOST_NOT_PRESENT:
            return None

        return DiagnosticFinding(
            id="EMMC_HOST_NOT_DETECTED",
            severity=Severity.ERROR,
            confidence=Confidence.MEDIUM,
            summary="MMC host controller not detected in sysfs",
            evidence=[
                self.observed("/sys/class/mmc_host contains no hosts", source="sysfs"),
                self.derived("MMC controller driver may not be loaded or device has power issue"),
            ],
            possible_causes=[
                "MMC controller driver not loaded",
                "Kernel device tree misconfiguration",
                "Power domain issue preventing controller initialization",
                "Boot from wrong kernel/DTB",
                "Hardware failure of MMC controller on SoC",
            ],
            recommended_next_steps=[
                "Check kernel boot log for DTB loading errors",
                "Verify correct device tree blob (DTB) for this board",
                "Check if MMC controller appears in /sys/bus/platform/devices",
                "Try loading MMC controller module manually",
            ],
            rule_id=self.id,
            tags=self.tags,
            affected_stages=[BootStage.BOOT_MEDIA],
        )


class RockchipMaskROMRule(DiagnosticRule):
    """Detect Rockchip device in MaskROM mode."""

    id = "ROCKCHIP_MASKROM_DETECTED"
    description = "Rockchip device detected in MaskROM mode"
    tags = ["rockchip", "usb", "maskrom"]

    def evaluate(self, session: DiagnosticSession) -> DiagnosticFinding | None:
        maskrom_devices = [
            d for d in session.rockchip_devices
            if d.mode == "maskrom"
        ]
        if not maskrom_devices:
            return None

        dev = maskrom_devices[0]
        return DiagnosticFinding(
            id="ROCKCHIP_MASKROM_ACTIVE",
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary="Rockchip device detected in MaskROM mode via USB",
            detail=(
                f"USB device {dev.usb.vid}:{dev.usb.pid} ({dev.usb.description}) "
                "is in MaskROM mode, indicating the boot ROM is running and "
                "no valid bootloader was found on storage."
            ),
            evidence=[
                self.observed(
                    f"USB VID:PID {dev.usb.vid}:{dev.usb.pid} matches Rockchip MaskROM",
                    source="USB enumeration"
                ),
                self.inferred(
                    "Device boot ROM is active - no valid bootloader found on primary boot media",
                    source="USB PID table"
                ),
            ],
            possible_causes=[
                "eMMC/NAND is blank or corrupted bootloader",
                "SD card bootloader not found",
                "Boot media selection jumper/resistor issue",
                "Intentional MaskROM mode entered via hardware button",
            ],
            recommended_next_steps=[
                "Use rkdeveloptool or upgrade_tool to flash bootloader",
                "Verify upgrade_tool/rkdeveloptool recognizes the device",
                "Download correct Rockchip loader for this SoC (RK3568)",
                "Flash miniloader, then U-Boot, then full image",
            ],
            rule_id=self.id,
            tags=self.tags,
            affected_stages=[BootStage.BOOTROM, BootStage.BOOT_MEDIA],
        )


class RockchipLoaderRule(DiagnosticRule):
    """Detect Rockchip device in Loader mode."""

    id = "ROCKCHIP_LOADER_DETECTED"
    description = "Rockchip device detected in Loader mode"
    tags = ["rockchip", "usb", "loader"]

    def evaluate(self, session: DiagnosticSession) -> DiagnosticFinding | None:
        loader_devices = [
            d for d in session.rockchip_devices
            if d.mode == "loader"
        ]
        if not loader_devices:
            return None

        dev = loader_devices[0]
        return DiagnosticFinding(
            id="ROCKCHIP_LOADER_ACTIVE",
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary="Rockchip device detected in Loader mode via USB",
            detail=(
                f"USB device {dev.usb.vid}:{dev.usb.pid} ({dev.usb.description}) "
                "is running the Rockchip USB loader, allowing low-level flash operations."
            ),
            evidence=[
                self.observed(
                    f"USB VID:PID {dev.usb.vid}:{dev.usb.pid} matches Rockchip Loader",
                    source="USB enumeration"
                ),
                self.inferred(
                    "Rockchip miniloader is active and accepting USB commands",
                    source="USB PID table"
                ),
            ],
            possible_causes=[
                "Normal USB recovery mode",
                "Bootloader entered recovery deliberately",
            ],
            recommended_next_steps=[
                "Use rkdeveloptool or upgrade_tool for flash operations",
                "Query chip information: rkdeveloptool ci",
                "Flash complete image or individual partitions",
            ],
            rule_id=self.id,
            tags=self.tags,
            affected_stages=[BootStage.USB_RECOVERY],
        )


class HealthyEMMCRule(DiagnosticRule):
    """Confirm healthy eMMC state."""

    id = "EMMC_HEALTHY"
    description = "eMMC block device is present and accessible"
    tags = ["emmc", "healthy"]

    def evaluate(self, session: DiagnosticSession) -> DiagnosticFinding | None:
        if session.mmc_state != MMCState.BLOCK_DEVICE_PRESENT:
            return None

        return DiagnosticFinding(
            id="EMMC_BLOCK_DEVICE_PRESENT",
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary="Internal eMMC block device is present and enumerated",
            evidence=[
                self.observed("eMMC block device found in /dev/mmcblkX", source="block device scan"),
            ],
            interpretation="eMMC initialization completed successfully",
            possible_causes=[],
            recommended_next_steps=["Verify read/write health with badblocks or similar tool"],
            rule_id=self.id,
            tags=self.tags,
        )


# ---------------------------------------------------------------------------
# Boot chain builder
# ---------------------------------------------------------------------------


class BootChainAnalyzer:
    """Build a boot chain analysis from session data."""

    def analyze(self, session: DiagnosticSession) -> BootChain:
        stages: list[BootStageResult] = []

        # POWER - infer from any successful boot
        power_status = StageStatus.UNKNOWN
        power_evidence: list[str] = []
        if session.usb_devices or session.network_interfaces or session.storage_devices:
            power_status = StageStatus.LIKELY_PASS
            power_evidence.append("USB/network/storage enumeration successful implies power OK")
        stages.append(BootStageResult(
            stage=BootStage.POWER,
            status=power_status,
            evidence=power_evidence,
        ))

        # BOOTROM - infer from rockchip detection or linux boot
        bootrom_status = StageStatus.UNKNOWN
        bootrom_evidence: list[str] = []
        if any(d.mode == "maskrom" for d in session.rockchip_devices):
            bootrom_status = StageStatus.PASS
            bootrom_evidence.append("BootROM active (MaskROM mode detected via USB)")
        elif any(d.mode == "loader" for d in session.rockchip_devices):
            bootrom_status = StageStatus.PASS
            bootrom_evidence.append("BootROM completed (Loader mode detected via USB)")
        elif session.storage_devices:
            bootrom_status = StageStatus.LIKELY_PASS
            bootrom_evidence.append("Storage enumerated implies BootROM successfully handed off")
        stages.append(BootStageResult(
            stage=BootStage.BOOTROM,
            status=bootrom_status,
            evidence=bootrom_evidence,
        ))

        # BOOT_MEDIA - check what's accessible
        boot_media_status = StageStatus.UNKNOWN
        boot_media_evidence: list[str] = []
        sd_devices = [d for d in session.storage_devices
                      if d.storage_class.value in ("sd_card", "emmc_internal")]
        if sd_devices:
            boot_media_status = StageStatus.LIKELY_PASS
            boot_media_evidence.append(f"Storage device(s) present: {[d.name for d in sd_devices]}")
        stages.append(BootStageResult(
            stage=BootStage.BOOT_MEDIA,
            status=boot_media_status,
            evidence=boot_media_evidence,
        ))

        # USB_RECOVERY
        usb_recovery_status = StageStatus.UNKNOWN
        usb_recovery_evidence: list[str] = []
        if session.rockchip_devices:
            usb_recovery_status = StageStatus.PASS
            usb_recovery_evidence.append(
                f"Rockchip device in {session.rockchip_devices[0].mode} mode"
            )
        stages.append(BootStageResult(
            stage=BootStage.USB_RECOVERY,
            status=usb_recovery_status,
            evidence=usb_recovery_evidence,
        ))

        # KERNEL - check via network or storage presence
        kernel_status = StageStatus.UNKNOWN
        kernel_evidence: list[str] = []
        if session.network_interfaces and any(
            iface.ipv4 for iface in session.network_interfaces
        ):
            kernel_status = StageStatus.LIKELY_PASS
            kernel_evidence.append("Network interfaces with IP addresses visible")
        elif session.storage_devices:
            kernel_status = StageStatus.LIKELY_PASS
            kernel_evidence.append("Storage devices enumerated (implies kernel running)")
        stages.append(BootStageResult(
            stage=BootStage.KERNEL,
            status=kernel_status,
            evidence=kernel_evidence,
        ))

        # ROOTFS
        rootfs_status = StageStatus.UNKNOWN
        rootfs_evidence: list[str] = []
        for dev in session.storage_devices:
            for part in dev.partitions:
                if part.mountpoint == "/":
                    rootfs_status = StageStatus.PASS
                    rootfs_evidence.append(f"Root filesystem mounted at / from {part.path}")
                    break
            for mp in dev.mount_points:
                if mp == "/":
                    rootfs_status = StageStatus.PASS
                    rootfs_evidence.append(f"Root filesystem mounted from {dev.path}")
                    break
        stages.append(BootStageResult(
            stage=BootStage.ROOTFS,
            status=rootfs_status,
            evidence=rootfs_evidence,
        ))

        # NETWORK
        net_status = StageStatus.UNKNOWN
        net_evidence: list[str] = []
        active_ifaces = [i for i in session.network_interfaces if i.ipv4]
        if active_ifaces:
            net_status = StageStatus.PASS
            net_evidence.append(f"Active interfaces: {[i.name for i in active_ifaces]}")
        elif session.network_interfaces:
            net_status = StageStatus.LIKELY_FAIL
            net_evidence.append("Network interfaces present but no IP addresses")
        stages.append(BootStageResult(
            stage=BootStage.NETWORK,
            status=net_status,
            evidence=net_evidence,
        ))

        return BootChain(stages=stages)


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------


ALL_RULES: list[DiagnosticRule] = [
    EMMCStuckNotReadyRule(),
    EMMCNotDetectedRule(),
    RockchipMaskROMRule(),
    RockchipLoaderRule(),
    HealthyEMMCRule(),
]


def run_all_rules(session: DiagnosticSession) -> list[DiagnosticFinding]:
    """Run all diagnostic rules against a session and return findings."""
    findings: list[DiagnosticFinding] = []
    for rule in ALL_RULES:
        try:
            finding = rule.evaluate(session)
            if finding is not None:
                findings.append(finding)
        except Exception as e:
            # Rules must not crash the session
            findings.append(DiagnosticFinding(
                id=f"RULE_ERROR_{rule.id}",
                severity=Severity.WARNING,
                confidence=Confidence.LOW,
                summary=f"Rule {rule.id} raised an exception: {e}",
            ))
    return findings
