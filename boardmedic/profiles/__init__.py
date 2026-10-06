"""Board profile schema and loader."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Profile sub-models
# ---------------------------------------------------------------------------


class ProfileUSBEntry(BaseModel):
    """Expected USB VID/PID entries for a board."""

    vid: str
    pid: str | None = None
    description: str | None = None
    mode: str | None = None  # maskrom | loader | normal | adb | fastboot


class ProfileSerialConfig(BaseModel):
    """Serial/UART configuration for a board."""

    voltage: str | None = None  # e.g. "3.3V TTL"
    baud_candidates: list[int] = Field(default_factory=lambda: [115200])
    data_bits: int = 8
    parity: str = "N"
    stop_bits: int = 1
    notes: str | None = None


class ProfileStorageExpectation(BaseModel):
    """Expected storage for a board."""

    type: str  # emmc | sd | nand | nor
    label: str
    min_gib: float | None = None
    max_gib: float | None = None
    removable: bool | None = None
    bus_path: str | None = None  # e.g. fe310000.mmc
    mmc_host: str | None = None
    notes: str | None = None


class ProfileBootMedia(BaseModel):
    """A supported boot media entry."""

    type: str  # emmc | sd | usb | network | rockchip_usb
    priority: int = 0
    notes: str | None = None


class ProfileRecoveryCapability(BaseModel):
    """A recovery method available for this board."""

    method: str  # sd_boot | rockchip_usb | uart | ssh | adb | fastboot
    notes: str | None = None
    requires: list[str] = Field(default_factory=list)


class ProfileFailureSignature(BaseModel):
    """A known failure pattern for this board."""

    id: str
    pattern: str  # regex pattern to match in dmesg/logs
    description: str
    severity: str = "error"
    finding_id: str | None = None


# ---------------------------------------------------------------------------
# Main profile schema
# ---------------------------------------------------------------------------


class BoardProfile(BaseModel):
    """Complete board profile definition."""

    # Identity
    id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    vendor: str | None = None
    pcb: str | None = None
    revision: str | None = None

    # SoC
    soc_family: str
    soc_model: str | None = None
    cpu_arch: str = "arm64"
    cpu_cores: int | None = None
    typical_ram_gb: float | None = None

    # USB
    usb_ids: list[ProfileUSBEntry] = Field(default_factory=list)
    rockchip_modes: list[str] = Field(default_factory=list)  # maskrom | loader

    # Serial
    serial: ProfileSerialConfig | None = None

    # Storage
    storage: list[ProfileStorageExpectation] = Field(default_factory=list)

    # Boot
    boot_media: list[ProfileBootMedia] = Field(default_factory=list)
    known_dtb: list[str] = Field(default_factory=list)
    known_mmc_controllers: list[str] = Field(default_factory=list)

    # Recovery
    recovery_capabilities: list[ProfileRecoveryCapability] = Field(default_factory=list)

    # Failure signatures
    failure_signatures: list[ProfileFailureSignature] = Field(default_factory=list)

    # Known kernel messages
    known_kernel_messages: list[str] = Field(default_factory=list)
    known_boot_messages: list[str] = Field(default_factory=list)

    # Metadata
    notes: str | None = None
    safe_assumptions: list[str] = Field(default_factory=list)
    unsafe_assumptions: list[str] = Field(default_factory=list)

    # Rules to enable
    enabled_rules: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", v):
            raise ValueError(
                f"Profile id '{v}' must be lowercase alphanumeric with hyphens, "
                "no leading/trailing hyphens."
            )
        return v

    @field_validator("soc_family")
    @classmethod
    def validate_soc_family(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("soc_family must not be empty")
        return v

    @field_validator("usb_ids")
    @classmethod
    def validate_usb_ids(cls, v: list[ProfileUSBEntry]) -> list[ProfileUSBEntry]:
        for entry in v:
            if not re.match(r"^[0-9a-fA-F]{4}$", entry.vid):
                raise ValueError(f"USB VID '{entry.vid}' must be 4 hex digits")
            if entry.pid and not re.match(r"^[0-9a-fA-F]{4}$", entry.pid):
                raise ValueError(f"USB PID '{entry.pid}' must be 4 hex digits")
        return v

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Profile registry
# ---------------------------------------------------------------------------


class ProfileRegistry:
    """Loads and validates board profiles from YAML files."""

    def __init__(self) -> None:
        self._profiles: dict[str, BoardProfile] = {}
        self._errors: dict[str, str] = {}

    def load_directory(self, directory: Path) -> None:
        """Load all .yaml profile files from a directory."""
        if not directory.exists():
            return
        for yaml_file in sorted(directory.glob("*.yaml")):
            if yaml_file.name.startswith("_"):
                continue  # skip template files
            self.load_file(yaml_file)

    def load_file(self, path: Path) -> BoardProfile | None:
        """Load and validate a single profile YAML file."""
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                self._errors[path.name] = "YAML root must be a mapping"
                return None
            profile = BoardProfile.model_validate(raw)
            self._profiles[profile.id] = profile
            return profile
        except yaml.YAMLError as e:
            self._errors[path.name] = f"YAML parse error: {e}"
            return None
        except Exception as e:
            self._errors[path.name] = str(e)
            return None

    def load_from_dict(self, data: dict[str, Any]) -> BoardProfile:
        """Load a profile from a dict (for testing)."""
        profile = BoardProfile.model_validate(data)
        self._profiles[profile.id] = profile
        return profile

    def get(self, profile_id: str) -> BoardProfile | None:
        """Get a profile by ID or alias."""
        if profile_id in self._profiles:
            return self._profiles[profile_id]
        # Try aliases
        for profile in self._profiles.values():
            if profile_id in profile.aliases:
                return profile
        return None

    def list_profiles(self) -> list[BoardProfile]:
        return list(self._profiles.values())

    def has_errors(self) -> bool:
        return bool(self._errors)

    def errors(self) -> dict[str, str]:
        return dict(self._errors)

    def validate_all(self) -> tuple[list[str], list[tuple[str, str]]]:
        """Returns (valid_ids, [(name, error), ...])."""
        return list(self._profiles.keys()), list(self._errors.items())


# ---------------------------------------------------------------------------
# Default profile directory
# ---------------------------------------------------------------------------


def default_profiles_dir() -> Path:
    """Return the built-in profiles directory."""
    return Path(__file__).parent.parent.parent / "profiles"


_registry: ProfileRegistry | None = None


def get_registry(reload: bool = False) -> ProfileRegistry:
    """Get the global profile registry, loading from default directory."""
    global _registry
    if _registry is None or reload:
        _registry = ProfileRegistry()
        _registry.load_directory(default_profiles_dir())
    return _registry
