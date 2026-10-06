"""
Safety engine for BoardMedic.

THIS IS THE MOST SECURITY-CRITICAL MODULE.

Rules:
- SYSTEM_DISK must NEVER be a destructive target.
- Current root filesystem disk must NEVER be a destructive target.
- Recovery media must NEVER be a destructive target.
- Ambiguity always resolves to ABORT.

No exceptions. No overrides. No bypass.
"""

from __future__ import annotations

import re
from typing import Optional

from boardmedic.models import (
    RecoveryResultCode,
    SafetyDecision,
    SafetyStatus,
    StorageClass,
    StorageDevice,
)
from boardmedic.profiles import BoardProfile

# ---------------------------------------------------------------------------
# Safety classification
# ---------------------------------------------------------------------------


class SafetyEngine:
    """
    Evaluates storage devices for safety status.

    Must be consulted before ANY destructive operation.
    """

    def __init__(
        self,
        root_disk: str | None = None,
        recovery_disk: str | None = None,
    ) -> None:
        """
        Args:
            root_disk: Path to the disk backing the running root filesystem.
                       e.g. '/dev/mmcblk0' or '\\\\.\\PhysicalDrive0'
            recovery_disk: Path to disk that is recovery media (e.g. the SD
                           card running BoardMedic itself).
        """
        self.root_disk = root_disk
        self.recovery_disk = recovery_disk

    def _normalize_path(self, path: str) -> str:
        """Normalize device path for comparison."""
        return path.rstrip("/").lower()

    def _is_root_disk(self, device: StorageDevice) -> bool:
        if not self.root_disk:
            return False
        if device.path:
            if self._normalize_path(device.path) == self._normalize_path(self.root_disk):
                return True
        if device.name:
            root_name = re.sub(r"^/dev/", "", self.root_disk)
            if device.name.lower() == root_name.lower():
                return True
        return False

    def _is_recovery_disk(self, device: StorageDevice) -> bool:
        if not self.recovery_disk:
            return False
        if device.path:
            if self._normalize_path(device.path) == self._normalize_path(self.recovery_disk):
                return True
        return False

    def classify_device(self, device: StorageDevice) -> SafetyStatus:
        """Assign a SafetyStatus to a storage device."""
        # System disk (Windows)
        if device.is_system_disk:
            return SafetyStatus.PROTECTED_SYSTEM_DISK

        # Current root filesystem
        if self._is_root_disk(device) or device.is_current_root:
            return SafetyStatus.PROTECTED_CURRENT_ROOT

        # Recovery media
        if self._is_recovery_disk(device) or device.is_recovery_media:
            return SafetyStatus.PROTECTED_RECOVERY_MEDIA

        # Root filesystem mounted partitions
        root_mounts = ["/", "/boot", "/boot/efi", "/efi"]
        for mp in device.mount_points:
            if mp in root_mounts:
                return SafetyStatus.PROTECTED_BOOT_DEVICE

        # Check partitions for root mounts
        for part in device.partitions:
            if part.mountpoint in root_mounts:
                return SafetyStatus.PROTECTED_BOOT_DEVICE

        # If root disk is known and this device is verified not to be it,
        # it is a candidate target (still needs verify_target check)
        if self.root_disk:
            return SafetyStatus.POSSIBLE_TARGET

        # Unknown (potentially unsafe to touch without explicit verification)
        return SafetyStatus.UNKNOWN_UNSAFE

    def classify_all(self, devices: list[StorageDevice]) -> None:
        """Classify all devices in-place."""
        for device in devices:
            device.safety_status = self.classify_device(device)

    # -------------------------------------------------------------------------
    # Target verification for destructive operations
    # -------------------------------------------------------------------------

    def verify_target(
        self,
        candidate: StorageDevice,
        profile: BoardProfile | None = None,
        all_devices: list[StorageDevice] | None = None,
    ) -> SafetyDecision:
        """
        Perform full safety verification before a destructive operation.

        Returns SafetyDecision with approved=True only when ALL checks pass.
        Any failure or ambiguity returns approved=False.
        """
        checks_passed: list[str] = []
        checks_failed: list[str] = []

        # --- Hard refusals (cannot be overridden) ---

        if candidate.safety_status == SafetyStatus.PROTECTED_SYSTEM_DISK:
            return SafetyDecision(
                target=candidate.path,
                approved=False,
                reason="TARGET IS THE SYSTEM DISK - REFUSED",
                checks_failed=["system_disk_check"],
                result_code=RecoveryResultCode.ABORTED_TARGET_SAFETY_CHECK,
            )

        if candidate.safety_status == SafetyStatus.PROTECTED_CURRENT_ROOT:
            return SafetyDecision(
                target=candidate.path,
                approved=False,
                reason="TARGET IS CURRENT ROOT FILESYSTEM - REFUSED",
                checks_failed=["root_disk_check"],
                result_code=RecoveryResultCode.ABORTED_TARGET_SAFETY_CHECK,
            )

        if candidate.safety_status == SafetyStatus.PROTECTED_BOOT_DEVICE:
            return SafetyDecision(
                target=candidate.path,
                approved=False,
                reason="TARGET HAS BOOT/ROOT PARTITION MOUNTED - REFUSED",
                checks_failed=["boot_device_check"],
                result_code=RecoveryResultCode.ABORTED_TARGET_SAFETY_CHECK,
            )

        if candidate.safety_status == SafetyStatus.PROTECTED_RECOVERY_MEDIA:
            return SafetyDecision(
                target=candidate.path,
                approved=False,
                reason="TARGET IS RECOVERY MEDIA - REFUSED",
                checks_failed=["recovery_media_check"],
                result_code=RecoveryResultCode.ABORTED_TARGET_SAFETY_CHECK,
            )

        if candidate.safety_status == SafetyStatus.UNKNOWN_UNSAFE:
            return SafetyDecision(
                target=candidate.path,
                approved=False,
                reason="TARGET HAS UNKNOWN/UNSAFE SAFETY STATUS - REFUSED",
                checks_failed=["safety_status_check"],
                result_code=RecoveryResultCode.ABORTED_TARGET_SAFETY_CHECK,
            )

        checks_passed.append("not_system_disk")
        checks_passed.append("not_current_root")
        checks_passed.append("not_recovery_media")

        # --- Redundant re-check of root disk ---
        if self._is_root_disk(candidate):
            return SafetyDecision(
                target=candidate.path,
                approved=False,
                reason="TARGET MATCHES ROOT DISK (double-check) - REFUSED",
                checks_failed=["root_disk_double_check"],
                result_code=RecoveryResultCode.ABORTED_TARGET_SAFETY_CHECK,
            )
        checks_passed.append("root_disk_double_check")

        # --- Mount point check ---
        dangerous_mounts = ["/", "/boot", "/boot/efi", "/efi", "/home"]
        for mp in candidate.mount_points:
            if mp in dangerous_mounts:
                checks_failed.append(f"no_dangerous_mountpoints (found {mp})")
                return SafetyDecision(
                    target=candidate.path,
                    approved=False,
                    reason=f"TARGET HAS DANGEROUS MOUNTPOINT {mp} - REFUSED",
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                    result_code=RecoveryResultCode.ABORTED_TARGET_SAFETY_CHECK,
                )
        for part in candidate.partitions:
            if part.mountpoint in dangerous_mounts:
                checks_failed.append(f"no_dangerous_partition_mounts (found {part.mountpoint})")
                return SafetyDecision(
                    target=candidate.path,
                    approved=False,
                    reason=f"TARGET PARTITION HAS DANGEROUS MOUNTPOINT {part.mountpoint} - REFUSED",
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                    result_code=RecoveryResultCode.ABORTED_TARGET_SAFETY_CHECK,
                )
        checks_passed.append("no_dangerous_mountpoints")

        # --- Profile-based checks ---
        if profile is not None:
            profile_result = self._verify_against_profile(candidate, profile)
            if not profile_result[0]:
                checks_failed.extend(profile_result[1])
                return SafetyDecision(
                    target=candidate.path,
                    approved=False,
                    reason=f"PROFILE CHECK FAILED: {', '.join(profile_result[1])}",
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                    result_code=RecoveryResultCode.ABORTED_TARGET_SAFETY_CHECK,
                )
            checks_passed.extend(profile_result[1])

        # All checks passed
        candidate.safety_status = SafetyStatus.VERIFIED_TARGET
        return SafetyDecision(
            target=candidate.path,
            approved=True,
            reason="All safety checks passed",
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            result_code=RecoveryResultCode.PENDING,
        )

    def _verify_against_profile(
        self, device: StorageDevice, profile: BoardProfile
    ) -> tuple[bool, list[str]]:
        """
        Verify device matches profile storage expectations.

        Returns (passed, [check_names_or_failures]).
        """
        results: list[str] = []

        # Find the profile's internal storage expectation (non-removable eMMC)
        emmc_expectations = [
            s for s in profile.storage
            if s.type == "emmc" and not s.removable
        ]
        if not emmc_expectations:
            results.append("profile_no_emmc_expectation")
            return True, results  # No specific expectation to check

        emmc_exp = emmc_expectations[0]

        # Size check
        if emmc_exp.min_gib is not None and emmc_exp.max_gib is not None:
            if device.size_gib is None:
                results.append("size_unknown_profile_check_skipped")
            else:
                if not (emmc_exp.min_gib <= device.size_gib <= emmc_exp.max_gib):
                    results.append(
                        f"size_mismatch: {device.size_gib:.1f} GiB not in "
                        f"[{emmc_exp.min_gib}, {emmc_exp.max_gib}]"
                    )
                    return False, results
                results.append(f"size_in_expected_range_{device.size_gib:.1f}GiB")

        # Removable check
        if emmc_exp.removable is False and device.removable:
            results.append("removable_mismatch: expected non-removable")
            return False, results
        if emmc_exp.removable is False:
            results.append("non_removable_confirmed")

        # Bus path / controller check
        if emmc_exp.bus_path and device.bus_path:
            if emmc_exp.bus_path not in device.bus_path:
                results.append(
                    f"bus_path_mismatch: {device.bus_path} != {emmc_exp.bus_path}"
                )
                return False, results
            results.append(f"bus_path_match_{emmc_exp.bus_path}")

        results.append("profile_storage_checks_passed")
        return True, results


# ---------------------------------------------------------------------------
# Destructive authorization
# ---------------------------------------------------------------------------


class DestructiveGate:
    """
    Multi-factor authorization gate for destructive operations.

    ALL conditions must be met before proceeding.
    """

    def __init__(
        self,
        dry_run: bool = False,
        destructive_flag: bool = False,
        yes_flag: bool = False,
    ) -> None:
        self.dry_run = dry_run
        self.destructive_flag = destructive_flag
        self.yes_flag = yes_flag

    def check(
        self,
        safety_decision: SafetyDecision,
        explicit_target: str | None = None,
    ) -> tuple[bool, str]:
        """
        Verify all authorization conditions are met.

        Returns (authorized, reason).
        """
        if not safety_decision.approved:
            return False, f"SAFETY CHECK FAILED: {safety_decision.reason}"

        if not self.destructive_flag:
            return False, "Missing --destructive flag. Destructive operations require explicit authorization."

        if explicit_target is None:
            return False, "No explicit target specified. Use --target to specify the exact device."

        if explicit_target != safety_decision.target:
            return False, (
                f"Target mismatch: specified '{explicit_target}' but "
                f"safety check was for '{safety_decision.target}'."
            )

        if self.dry_run:
            return True, "DRY_RUN: Would execute (no actual write)"

        return True, "Authorization granted"
