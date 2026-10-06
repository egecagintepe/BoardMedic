"""Core data models for BoardMedic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Platform(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


class ToolStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_SUPPORTED = "not_supported"
    PERMISSION_REQUIRED = "permission_required"
    FAILED = "failed"


class BootStage(str, Enum):
    POWER = "power"
    BOOTROM = "bootrom"
    USB_RECOVERY = "usb_recovery"
    BOOT_MEDIA = "boot_media"
    SPL = "spl"
    UBOOT = "uboot"
    KERNEL = "kernel"
    ROOTFS = "rootfs"
    USERSPACE = "userspace"
    NETWORK = "network"
    APPLICATION = "application"


class StageStatus(str, Enum):
    PASS = "pass"
    LIKELY_PASS = "likely_pass"
    UNKNOWN = "unknown"
    LIKELY_FAIL = "likely_fail"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class Severity(str, Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceType(str, Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    INFERRED = "inferred"
    HYPOTHESIS = "hypothesis"


class StorageClass(str, Enum):
    SYSTEM_DISK = "system_disk"
    EMMC_INTERNAL = "emmc_internal"
    SD_CARD = "sd_card"
    USB_FLASH = "usb_flash"
    NVME = "nvme"
    SATA = "sata"
    UNKNOWN = "unknown"


class SafetyStatus(str, Enum):
    PROTECTED_SYSTEM_DISK = "protected_system_disk"
    PROTECTED_BOOT_DEVICE = "protected_boot_device"
    PROTECTED_CURRENT_ROOT = "protected_current_root"
    PROTECTED_RECOVERY_MEDIA = "protected_recovery_media"
    UNKNOWN_UNSAFE = "unknown_unsafe"
    POSSIBLE_TARGET = "possible_target"
    VERIFIED_TARGET = "verified_target"


class MMCState(str, Enum):
    HOST_NOT_PRESENT = "mmc_host_not_present"
    HOST_PRESENT_NO_CARD_RESPONSE = "mmc_host_present_no_card_response"
    CARD_RESPONDS_NOT_READY = "mmc_card_responds_not_ready"
    ENUMERATION_FAILED = "mmc_enumeration_failed"
    BLOCK_DEVICE_PRESENT = "mmc_block_device_present"
    READ_ONLY = "mmc_read_only"
    IO_ERRORS = "mmc_io_errors"
    HEALTH_UNKNOWN = "mmc_health_unknown"


class RecoveryResultCode(str, Enum):
    SUCCESS = "SUCCESS"
    EMMC_NOT_DETECTED = "EMMC_NOT_DETECTED"
    EMMC_STUCK_NOT_READY = "EMMC_STUCK_NOT_READY"
    EMMC_DETECTED_ERASE_FAILED = "EMMC_DETECTED_ERASE_FAILED"
    EMMC_ERASED_VERIFY_FAILED = "EMMC_ERASED_VERIFY_FAILED"
    EMMC_RECOVERED_READWRITE_OK = "EMMC_RECOVERED_READWRITE_OK"
    EMMC_RECOVERED_AND_LINUX_INSTALLED = "EMMC_RECOVERED_AND_LINUX_INSTALLED"
    USB_RECOVERY_NOT_DETECTED = "USB_RECOVERY_NOT_DETECTED"
    FLASH_FAILED = "FLASH_FAILED"
    VERIFY_FAILED = "VERIFY_FAILED"
    ABORTED_TARGET_SAFETY_CHECK = "ABORTED_TARGET_SAFETY_CHECK"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    DRY_RUN = "DRY_RUN"
    PENDING = "PENDING"


class DestructiveAuth(str, Enum):
    """Authorization state for destructive operations."""
    NOT_REQUESTED = "not_requested"
    REQUESTED = "requested"
    AUTHORIZED = "authorized"
    DENIED = "denied"


# ---------------------------------------------------------------------------
# Command execution models
# ---------------------------------------------------------------------------


class CommandResult(BaseModel):
    """Result of an executed external command."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    command: list[str]
    command_str: str
    platform: str
    cwd: str | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    elevated: bool = False
    destructive: bool = False
    dry_run: bool = False
    timed_out: bool = False
    error_message: str | None = None
    tool_name: str | None = None

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# USB device models
# ---------------------------------------------------------------------------


class USBDevice(BaseModel):
    """Normalized USB device representation."""

    bus: int | None = None
    device: int | None = None
    vid: str  # hex string e.g. "2207"
    pid: str  # hex string e.g. "350a"
    manufacturer: str | None = None
    product: str | None = None
    serial: str | None = None
    driver: str | None = None
    class_code: str | None = None
    description: str | None = None
    raw: str | None = None

    @property
    def vid_pid(self) -> str:
        return f"{self.vid}:{self.pid}"

    @property
    def is_rockchip(self) -> bool:
        return self.vid.lower() == "2207"


class RockchipDevice(BaseModel):
    """Rockchip USB device with mode detection."""

    usb: USBDevice
    mode: str = "unknown"  # maskrom | loader | unknown
    chip_info: str | None = None
    tool_used: str | None = None  # upgrade_tool | rkdeveloptool

    # Known Rockchip PIDs for mode identification
    MASKROM_PIDS: list[str] = Field(
        default_factory=lambda: ["350a", "330c", "320b", "330d", "330e", "350b"]
    )
    LOADER_PIDS: list[str] = Field(
        default_factory=lambda: ["320d", "330c", "320a", "350c"]
    )

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Serial port models
# ---------------------------------------------------------------------------


class SerialPort(BaseModel):
    """Normalized serial port."""

    port: str
    description: str | None = None
    hwid: str | None = None
    manufacturer: str | None = None
    vid: str | None = None
    pid: str | None = None
    is_usb: bool = False


class SerialCapture(BaseModel):
    """Result of a serial port capture session."""

    port: str
    baud: int
    duration_seconds: float
    data: str = ""
    lines: list[str] = Field(default_factory=list)
    error: str | None = None
    timed_out: bool = False


# ---------------------------------------------------------------------------
# Network models
# ---------------------------------------------------------------------------


class NetworkInterface(BaseModel):
    """Normalized network interface."""

    name: str
    state: str = "unknown"
    mac: str | None = None
    ipv4: list[str] = Field(default_factory=list)
    ipv6: list[str] = Field(default_factory=list)
    mtu: int | None = None
    type: str | None = None


class NetworkNeighbor(BaseModel):
    """ARP/neighbor table entry."""

    ip: str
    mac: str | None = None
    interface: str | None = None
    state: str | None = None


# ---------------------------------------------------------------------------
# Storage models
# ---------------------------------------------------------------------------


class StoragePartition(BaseModel):
    """A storage partition."""

    name: str
    path: str | None = None
    size_bytes: int | None = None
    filesystem: str | None = None
    label: str | None = None
    uuid: str | None = None
    mountpoint: str | None = None
    boot: bool = False
    type: str | None = None


class StorageDevice(BaseModel):
    """Normalized storage device."""

    # Identity
    name: str  # e.g. sda, mmcblk0, Disk 0
    path: str | None = None  # e.g. /dev/sda, \\\\.\\PhysicalDrive0
    model: str | None = None
    serial: str | None = None
    vendor: str | None = None

    # Physical properties
    size_bytes: int | None = None
    removable: bool = False
    transport: str | None = None  # usb, nvme, mmc, sata, unknown
    bus_path: str | None = None  # e.g. fe310000.mmc

    # Partition info
    partition_table: str | None = None
    partitions: list[StoragePartition] = Field(default_factory=list)
    mount_points: list[str] = Field(default_factory=list)

    # Classification
    storage_class: StorageClass = StorageClass.UNKNOWN
    safety_status: SafetyStatus = SafetyStatus.UNKNOWN_UNSAFE
    is_system_disk: bool = False
    is_current_root: bool = False
    is_recovery_media: bool = False

    # MMC-specific
    mmc_host: str | None = None
    mmc_type: str | None = None  # SD, MMC, SDIO

    # Raw data
    raw: dict[str, Any] | None = None

    @property
    def size_gib(self) -> float | None:
        if self.size_bytes is not None:
            return self.size_bytes / (1024**3)
        return None


# ---------------------------------------------------------------------------
# Evidence and findings
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    """A single piece of evidence."""

    type: EvidenceType
    description: str
    source: str | None = None
    raw_value: str | None = None
    timestamp: datetime | None = None


class DiagnosticFinding(BaseModel):
    """A diagnostic finding with full evidence chain."""

    id: str
    severity: Severity
    confidence: Confidence
    summary: str
    detail: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    interpretation: str | None = None
    possible_causes: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    rule_id: str | None = None
    tags: list[str] = Field(default_factory=list)

    # Boot chain impact
    affected_stages: list[BootStage] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Boot chain model
# ---------------------------------------------------------------------------


class BootStageResult(BaseModel):
    """Result for a single boot chain stage."""

    stage: BootStage
    status: StageStatus
    evidence: list[str] = Field(default_factory=list)
    notes: str | None = None


class BootChain(BaseModel):
    """Full boot chain analysis."""

    stages: list[BootStageResult] = Field(default_factory=list)

    def get_stage(self, stage: BootStage) -> BootStageResult | None:
        for s in self.stages:
            if s.stage == stage:
                return s
        return None


# ---------------------------------------------------------------------------
# Safety decision
# ---------------------------------------------------------------------------


class SafetyDecision(BaseModel):
    """Result of a safety evaluation for a destructive operation."""

    target: str | None = None
    approved: bool = False
    reason: str
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    result_code: RecoveryResultCode = RecoveryResultCode.PENDING


# ---------------------------------------------------------------------------
# Recovery models
# ---------------------------------------------------------------------------


class RecoveryStep(BaseModel):
    """A single step in a recovery plan."""

    order: int
    id: str
    title: str
    description: str
    destructive: bool = False
    disruptive: bool = False
    requires_elevated: bool = False
    requires_tools: list[str] = Field(default_factory=list)
    estimated_duration: str | None = None
    commands: list[str] = Field(default_factory=list)
    skip_reason: str | None = None
    status: str = "pending"  # pending | done | skipped | failed


class RecoveryPlan(BaseModel):
    """A full recovery plan for a session."""

    profile_id: str | None = None
    target_device: str | None = None
    steps: list[RecoveryStep] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: list[str] = Field(default_factory=list)
    result_code: RecoveryResultCode = RecoveryResultCode.PENDING


# ---------------------------------------------------------------------------
# Session model
# ---------------------------------------------------------------------------


class SessionInfo(BaseModel):
    """Metadata for a diagnostic session."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    platform: str = "unknown"
    profile_id: str | None = None
    fixture_path: str | None = None
    session_dir: str | None = None
    host_username: str | None = None
    host_hostname: str | None = None
    boardmedic_version: str = "0.1.0"
    elevated: bool = False
    dry_run: bool = False


class DiagnosticSession(BaseModel):
    """Complete diagnostic session data."""

    info: SessionInfo = Field(default_factory=SessionInfo)
    usb_devices: list[USBDevice] = Field(default_factory=list)
    rockchip_devices: list[RockchipDevice] = Field(default_factory=list)
    serial_ports: list[SerialPort] = Field(default_factory=list)
    network_interfaces: list[NetworkInterface] = Field(default_factory=list)
    storage_devices: list[StorageDevice] = Field(default_factory=list)
    boot_chain: BootChain | None = None
    findings: list[DiagnosticFinding] = Field(default_factory=list)
    recovery_plan: RecoveryPlan | None = None
    commands: list[CommandResult] = Field(default_factory=list)
    raw_evidence: dict[str, str] = Field(default_factory=dict)
    mmc_state: MMCState | None = None
    result_code: RecoveryResultCode = RecoveryResultCode.PENDING

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------


class Report(BaseModel):
    """Generated diagnostic report."""

    session_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    format: str = "markdown"
    content: str = ""
    output_path: str | None = None
    anonymized: bool = False


# ---------------------------------------------------------------------------
# Device candidate model
# ---------------------------------------------------------------------------


class DeviceCandidate(BaseModel):
    """A candidate device match against a board profile."""

    profile_id: str
    profile_name: str
    confidence: Confidence
    matched_criteria: list[str] = Field(default_factory=list)
    unmatched_criteria: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
