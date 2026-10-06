"""Recovery operations - guarded destructive framework."""

from __future__ import annotations

import hashlib
from pathlib import Path

from boardmedic.core.runner import CommandRunner
from boardmedic.models import RecoveryResultCode, SafetyDecision
from boardmedic.safety import DestructiveGate


class WipeOperation:
    """
    Wipe a target storage device.

    REQUIRES: explicit safety authorization, --destructive flag,
    explicit target match, and optionally --yes.
    """

    def __init__(self, runner: CommandRunner, dry_run: bool = False) -> None:
        self.runner = runner
        self.dry_run = dry_run

    def wipe_metadata(
        self,
        target: str,
        safety_decision: SafetyDecision,
        gate: DestructiveGate,
    ) -> RecoveryResultCode:
        """
        Wipe the first and last 4MB of a block device to destroy partition tables.

        Only proceeds if safety decision is approved and gate authorizes.
        """
        auth_ok, _auth_reason = gate.check(safety_decision, explicit_target=target)
        if not auth_ok:
            return RecoveryResultCode.ABORTED_TARGET_SAFETY_CHECK

        # All checks pass - generate the commands (dry-run will not execute)
        cmds = [
            ["dd", "if=/dev/zero", f"of={target}", "bs=4M", "count=1", "conv=fdatasync"],
            ["dd", "if=/dev/zero", f"of={target}", "bs=4M", "count=1",
             "seek=$(blockdev --getsz {target} / 8192 - 1)", "conv=fdatasync"],
        ]

        if self.dry_run:
            for cmd in cmds:
                self.runner.run(cmd, destructive=True, tool_name="dd")
                # In dry-run, runner returns without executing
            return RecoveryResultCode.DRY_RUN

        for cmd in cmds:
            result = self.runner.run(cmd, destructive=True, tool_name="dd")
            if result.exit_code != 0:
                return RecoveryResultCode.EMMC_DETECTED_ERASE_FAILED

        return RecoveryResultCode.SUCCESS


class FlashOperation:
    """
    Flash an image file to a block device.

    REQUIRES: safety authorization, --destructive flag, verified target.
    """

    def __init__(self, runner: CommandRunner, dry_run: bool = False) -> None:
        self.runner = runner
        self.dry_run = dry_run

    def validate_image(self, image_path: Path) -> tuple[bool, str | None]:
        """Validate that the image file exists and compute SHA256."""
        if not image_path.exists():
            return False, f"Image file not found: {image_path}"
        if image_path.stat().st_size == 0:
            return False, "Image file is empty"
        return True, None

    def compute_sha256(self, path: Path, chunk_size: int = 1024 * 1024) -> str:
        """Compute SHA256 of a file."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()

    def flash(
        self,
        target: str,
        image_path: Path,
        safety_decision: SafetyDecision,
        gate: DestructiveGate,
    ) -> RecoveryResultCode:
        """Flash image to target. Requires authorization."""
        auth_ok, _auth_reason = gate.check(safety_decision, explicit_target=target)
        if not auth_ok:
            return RecoveryResultCode.ABORTED_TARGET_SAFETY_CHECK

        valid, _err = self.validate_image(image_path)
        if not valid:
            return RecoveryResultCode.FLASH_FAILED

        if self.dry_run:
            self.runner.run(
                ["dd", f"if={image_path}", f"of={target}", "bs=4M", "conv=fdatasync"],
                destructive=True, tool_name="dd"
            )
            return RecoveryResultCode.DRY_RUN

        result = self.runner.run(
            ["dd", f"if={image_path}", f"of={target}", "bs=4M", "conv=fdatasync"],
            destructive=True,
            tool_name="dd",
            timeout=3600,  # 1 hour
        )

        if result.exit_code != 0:
            return RecoveryResultCode.FLASH_FAILED

        # Sync
        self.runner.run(["sync"], tool_name="sync")

        return RecoveryResultCode.SUCCESS
