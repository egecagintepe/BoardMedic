"""Recovery planning engine."""

from __future__ import annotations

from boardmedic.models import (
    DiagnosticSession,
    RecoveryPlan,
    RecoveryResultCode,
    RecoveryStep,
)
from boardmedic.profiles import BoardProfile


class RecoveryPlanner:
    """
    Generates evidence-based recovery plans.

    DOES NOT execute destructive actions.
    Generates ordered steps based on available evidence and capabilities.
    """

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def plan(
        self,
        session: DiagnosticSession,
        profile: BoardProfile | None = None,
    ) -> RecoveryPlan:
        """Generate a recovery plan based on session findings."""
        steps: list[RecoveryStep] = []
        notes: list[str] = []
        result_code = RecoveryResultCode.PENDING

        if self.dry_run:
            notes.append("DRY-RUN MODE: This plan would NOT execute any destructive steps.")

        # Analyze findings
        finding_ids = {f.id for f in session.findings}
        has_emmc_not_ready = "EMMC_INIT_NOT_READY" in finding_ids
        has_emmc_not_detected = "EMMC_HOST_NOT_DETECTED" in finding_ids
        has_healthy_emmc = "EMMC_BLOCK_DEVICE_PRESENT" in finding_ids

        # Check USB Rockchip availability
        has_rockchip_usb = bool(session.rockchip_devices)

        # Check profile
        profile_id = profile.id if profile else (session.info.profile_id or "unknown")
        rockchip_profile = profile and profile.soc_family.lower().startswith("rockchip")

        order = 0

        # ----------------------------------------------------------------
        # Step 1: SD boot / verify working environment
        # ----------------------------------------------------------------
        order += 1
        steps.append(RecoveryStep(
            order=order,
            id="verify_environment",
            title="Verify Working Boot Environment",
            description=(
                "Ensure you are booted into a known-good Linux environment "
                "(e.g., from an SD card). Verify you have shell access, "
                "sufficient RAM, and necessary tools."
            ),
            destructive=False,
            commands=["uname -a", "free -h", "df -h"],
        ))

        # ----------------------------------------------------------------
        # Step 2: Collect full diagnostics
        # ----------------------------------------------------------------
        order += 1
        steps.append(RecoveryStep(
            order=order,
            id="collect_diagnostics",
            title="Collect Full Diagnostics",
            description=(
                "Run boardmedic collect --profile " + profile_id + " to gather "
                "complete diagnostic evidence before attempting any recovery."
            ),
            destructive=False,
            commands=[f"boardmedic collect --profile {profile_id}"],
        ))

        # ----------------------------------------------------------------
        # Step 3: Check Rockchip USB if applicable
        # ----------------------------------------------------------------
        if rockchip_profile or has_rockchip_usb:
            order += 1
            steps.append(RecoveryStep(
                order=order,
                id="check_rockchip_usb",
                title="Check Rockchip USB Recovery Connection",
                description=(
                    "Connect OTG/USB cable between host PC and board USB OTG port. "
                    "Check if device appears as Rockchip VID 0x2207 "
                    "(MaskROM or Loader mode)."
                ),
                destructive=False,
                disruptive=False,
                requires_tools=["rkdeveloptool", "upgrade_tool"],
                commands=["lsusb | grep 2207", "rkdeveloptool ld"],
            ))

        # ----------------------------------------------------------------
        # Step 4: eMMC driver reprobe (non-destructive but disruptive)
        # ----------------------------------------------------------------
        if has_emmc_not_ready or has_emmc_not_detected:
            order += 1
            # Find expected MMC controller from profile
            controller = "fe310000.mmc"  # default for RK3568
            if profile and profile.known_mmc_controllers:
                controller = profile.known_mmc_controllers[0]

            steps.append(RecoveryStep(
                order=order,
                id="reprobe_mmc_driver",
                title="Attempt MMC Driver Unbind/Rebind",
                description=(
                    f"Unbind and rebind the MMC controller '{controller}' "
                    "to trigger a clean re-initialization. "
                    "DISRUPTIVE but NOT destructive - may briefly affect other MMC devices."
                ),
                destructive=False,
                disruptive=True,
                requires_elevated=True,
                commands=[
                    f"echo {controller} > /sys/bus/platform/drivers/sdhci-of-dwcmshc/unbind",
                    f"echo {controller} > /sys/bus/platform/drivers/sdhci-of-dwcmshc/bind",
                    "sleep 2",
                    "lsblk",
                ],
                notes="Requires root. Check lsblk after for new mmcblk device.",
            ))

        # ----------------------------------------------------------------
        # Step 5: eMMC read test if it enumerates
        # ----------------------------------------------------------------
        order += 1
        steps.append(RecoveryStep(
            order=order,
            id="emmc_read_test",
            title="eMMC Read Test (if device enumerates)",
            description=(
                "If /dev/mmcblk1 (or similar) appears after reprobe, "
                "perform a read-only test to verify the device is accessible."
            ),
            destructive=False,
            requires_elevated=True,
            commands=[
                "lsblk",
                "dd if=/dev/mmcblk1 of=/dev/null bs=4M count=10 2>&1",
            ],
            skip_reason="Skip if eMMC device does not enumerate",
        ))

        # ----------------------------------------------------------------
        # Step 6: Rockchip Loader/MaskROM flash (if available)
        # ----------------------------------------------------------------
        if rockchip_profile:
            order += 1
            steps.append(RecoveryStep(
                order=order,
                id="rockchip_usb_flash",
                title="Rockchip USB Recovery (Loader/MaskROM)",
                description=(
                    "If the board enters Loader or MaskROM mode via USB OTG, "
                    "use rkdeveloptool or upgrade_tool to flash the complete "
                    "firmware image. This is a DESTRUCTIVE operation requiring "
                    "explicit authorization (--destructive flag)."
                ),
                destructive=True,
                requires_tools=["rkdeveloptool"],
                commands=[
                    "rkdeveloptool ld",
                    "rkdeveloptool db <loader.bin>",
                    "rkdeveloptool wl 0 <image.img>",
                    "rkdeveloptool rd",
                ],
                skip_reason="Requires Rockchip USB connection and explicit --destructive flag",
            ))

        # ----------------------------------------------------------------
        # Step 7: eMMC wipe/reinitialize (DESTRUCTIVE, highly guarded)
        # ----------------------------------------------------------------
        if has_emmc_not_ready:
            order += 1
            steps.append(RecoveryStep(
                order=order,
                id="emmc_wipe_reinit",
                title="eMMC Wipe and Reinitialize (DESTRUCTIVE - LAST RESORT)",
                description=(
                    "DESTRUCTIVE OPERATION. Wipe the eMMC metadata regions to "
                    "force clean re-initialization. "
                    "Requires: --destructive flag, verified target, explicit confirmation. "
                    "WARNING: ALL DATA ON eMMC WILL BE PERMANENTLY DESTROYED."
                ),
                destructive=True,
                requires_elevated=True,
                commands=[
                    "# boardmedic recover wipe --target /dev/mmcblk1 --destructive --yes",
                ],
                skip_reason="Only attempt if all safe options exhausted. Requires explicit authorization.",
                estimated_duration="2-10 minutes",
            ))

        # ----------------------------------------------------------------
        # Step 8: Flash image to eMMC
        # ----------------------------------------------------------------
        order += 1
        steps.append(RecoveryStep(
            order=order,
            id="flash_image",
            title="Flash Recovery Image to eMMC (DESTRUCTIVE)",
            description=(
                "If eMMC enumerates (or after wipe), flash a known-good "
                "firmware image. Requires verified target and explicit authorization."
            ),
            destructive=True,
            requires_elevated=True,
            commands=[
                "# boardmedic recover flash --target /dev/mmcblk1 "
                "--image firmware.img --destructive --yes",
            ],
            skip_reason="Requires eMMC enumeration and --destructive flag",
        ))

        # ----------------------------------------------------------------
        # Step 9: Verify written image
        # ----------------------------------------------------------------
        order += 1
        steps.append(RecoveryStep(
            order=order,
            id="verify_flash",
            title="Verify Written Image",
            description=(
                "After flashing, compute SHA256 of written data and compare "
                "to source image. Read back and compare."
            ),
            destructive=False,
            requires_elevated=True,
            commands=[
                "sha256sum firmware.img",
                "dd if=/dev/mmcblk1 bs=4M count=<N> | sha256sum",
            ],
        ))

        # ----------------------------------------------------------------
        # Step 10: Boot without recovery media
        # ----------------------------------------------------------------
        order += 1
        steps.append(RecoveryStep(
            order=order,
            id="boot_from_emmc",
            title="Boot From eMMC (Remove Recovery Media)",
            description=(
                "Remove the recovery SD card and attempt to boot from internal eMMC. "
                "Verify the system boots normally."
            ),
            destructive=False,
            commands=["# Power off, remove SD, power on", "# Verify boot via UART or SSH"],
        ))

        # Determine overall result code
        if has_emmc_not_ready:
            result_code = RecoveryResultCode.EMMC_STUCK_NOT_READY
        elif has_emmc_not_detected:
            result_code = RecoveryResultCode.EMMC_NOT_DETECTED
        elif has_healthy_emmc:
            result_code = RecoveryResultCode.EMMC_BLOCK_DEVICE_PRESENT if False else RecoveryResultCode.PENDING

        notes.append(
            "Recovery steps are ordered by risk. Always attempt non-destructive steps first."
        )
        notes.append(
            "Destructive steps require --destructive flag and explicit target confirmation."
        )
        if self.dry_run:
            result_code = RecoveryResultCode.DRY_RUN

        return RecoveryPlan(
            profile_id=profile_id,
            steps=steps,
            notes=notes,
            result_code=result_code,
        )
