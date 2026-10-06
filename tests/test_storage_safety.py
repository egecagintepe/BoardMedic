"""Tests for storage enumeration and safety classification."""

from __future__ import annotations

from boardmedic.collectors.storage import parse_storage_from_fixture
from boardmedic.models import SafetyStatus, StorageClass
from boardmedic.safety import SafetyEngine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LSBLK_SD_ONLY = """{
  "blockdevices": [
    {
      "name": "mmcblk0", "path": "/dev/mmcblk0",
      "size": "503316480000", "rm": true, "hotplug": true,
      "type": "disk", "tran": "mmc",
      "mountpoint": null, "mountpoints": [null],
      "children": [
        {"name": "mmcblk0p1", "path": "/dev/mmcblk0p1", "size": "536870912",
         "type": "part", "fstype": "vfat", "mountpoint": "/boot", "mountpoints": ["/boot"]},
        {"name": "mmcblk0p2", "path": "/dev/mmcblk0p2", "size": "502779609088",
         "type": "part", "fstype": "ext4", "mountpoint": "/", "mountpoints": ["/"],
         "uuid": "aabbccdd-1234"}
      ]
    }
  ]
}"""

LSBLK_SD_AND_EMMC = """{
  "blockdevices": [
    {
      "name": "mmcblk0", "path": "/dev/mmcblk0",
      "size": "503316480000", "rm": true, "hotplug": true,
      "type": "disk", "tran": "mmc",
      "mountpoint": null, "mountpoints": [null],
      "children": [
        {"name": "mmcblk0p2", "path": "/dev/mmcblk0p2", "size": "502779609088",
         "type": "part", "fstype": "ext4", "mountpoint": "/", "mountpoints": ["/"]}
      ]
    },
    {
      "name": "mmcblk1", "path": "/dev/mmcblk1",
      "size": "31268536320", "rm": false, "hotplug": false,
      "type": "disk", "tran": "mmc",
      "mountpoint": null, "mountpoints": [null],
      "children": []
    }
  ]
}"""

LSBLK_SATA_SYSTEM = """{
  "blockdevices": [
    {
      "name": "sda", "path": "/dev/sda",
      "model": "Samsung SSD 870",
      "size": "500107862016", "rm": false, "hotplug": false,
      "type": "disk", "tran": "sata",
      "mountpoint": null, "mountpoints": [null],
      "children": [
        {"name": "sda2", "path": "/dev/sda2", "size": "499570991104",
         "type": "part", "fstype": "ext4", "mountpoint": "/", "mountpoints": ["/"]}
      ]
    }
  ]
}"""

LSBLK_LARGE_SD = """{
  "blockdevices": [
    {
      "name": "mmcblk0", "path": "/dev/mmcblk0",
      "size": "495017787392", "rm": true, "hotplug": true,
      "type": "disk", "tran": "mmc",
      "mountpoint": null, "mountpoints": [null],
      "children": [
        {"name": "mmcblk0p2", "path": "/dev/mmcblk0p2", "size": "490000000000",
         "type": "part", "fstype": "ext4", "mountpoint": "/", "mountpoints": ["/"]}
      ]
    }
  ]
}"""


# ---------------------------------------------------------------------------
# Storage parsing tests
# ---------------------------------------------------------------------------

def test_parse_sd_only():
    devices = parse_storage_from_fixture(LSBLK_SD_ONLY)
    assert len(devices) == 1
    assert devices[0].name == "mmcblk0"
    assert devices[0].removable is True
    assert devices[0].storage_class == StorageClass.SD_CARD


def test_parse_sd_and_emmc():
    devices = parse_storage_from_fixture(LSBLK_SD_AND_EMMC)
    assert len(devices) == 2
    names = {d.name for d in devices}
    assert "mmcblk0" in names
    assert "mmcblk1" in names
    emmc = next(d for d in devices if d.name == "mmcblk1")
    assert emmc.removable is False
    assert emmc.storage_class == StorageClass.EMMC_INTERNAL


def test_parse_size_bytes():
    devices = parse_storage_from_fixture(LSBLK_SD_AND_EMMC)
    emmc = next(d for d in devices if d.name == "mmcblk1")
    assert emmc.size_bytes == 31268536320
    assert emmc.size_gib is not None
    assert 28.0 < emmc.size_gib < 32.0


def test_parse_sata_disk():
    devices = parse_storage_from_fixture(LSBLK_SATA_SYSTEM)
    assert len(devices) == 1
    assert devices[0].name == "sda"
    assert devices[0].transport == "sata"
    assert devices[0].removable is False


def test_parse_mount_points():
    devices = parse_storage_from_fixture(LSBLK_SD_ONLY)
    sd = devices[0]
    assert "/" in sd.mount_points or any(p.mountpoint == "/" for p in sd.partitions)


# ---------------------------------------------------------------------------
# Safety engine - classification
# ---------------------------------------------------------------------------

def test_root_disk_protected():
    devices = parse_storage_from_fixture(LSBLK_SATA_SYSTEM)
    engine = SafetyEngine(root_disk="/dev/sda")
    engine.classify_all(devices)
    sda = devices[0]
    assert sda.safety_status in (
        SafetyStatus.PROTECTED_CURRENT_ROOT,
        SafetyStatus.PROTECTED_BOOT_DEVICE,
    )


def test_system_disk_flag_protected():
    devices = parse_storage_from_fixture(LSBLK_SATA_SYSTEM)
    devices[0].is_system_disk = True
    engine = SafetyEngine()
    engine.classify_all(devices)
    assert devices[0].safety_status == SafetyStatus.PROTECTED_SYSTEM_DISK


def test_recovery_sd_protected():
    """512GB SD card used as recovery media must be protected."""
    devices = parse_storage_from_fixture(LSBLK_LARGE_SD)
    engine = SafetyEngine(
        root_disk="/dev/mmcblk0",
        recovery_disk="/dev/mmcblk0",
    )
    engine.classify_all(devices)
    assert devices[0].safety_status in (
        SafetyStatus.PROTECTED_CURRENT_ROOT,
        SafetyStatus.PROTECTED_RECOVERY_MEDIA,
    )


def test_512gb_sd_cannot_be_emmc_target():
    """A 512GB SD card must fail the DC-A568B eMMC profile size check."""
    from boardmedic.profiles import get_registry
    registry = get_registry(reload=True)
    profile = registry.get("dc-a568b")
    assert profile is not None

    devices = parse_storage_from_fixture(LSBLK_LARGE_SD)
    sd = devices[0]

    engine = SafetyEngine(root_disk="/dev/sda")  # root is elsewhere
    engine.classify_all(devices)

    # The SD card size (~461 GiB) should fail the 20-40 GiB profile check
    decision = engine.verify_target(sd, profile=profile)
    assert not decision.approved, "512GB SD must not pass DC-A568B eMMC target check"


def test_emmc_becomes_verified_target():
    """A 29.1 GiB non-removable eMMC should pass all safety checks."""
    from boardmedic.profiles import get_registry
    registry = get_registry(reload=True)
    profile = registry.get("dc-a568b")

    devices = parse_storage_from_fixture(LSBLK_SD_AND_EMMC)
    emmc = next(d for d in devices if d.name == "mmcblk1")

    # Root is on mmcblk0 (SD card)
    engine = SafetyEngine(root_disk="/dev/mmcblk0")
    engine.classify_all(devices)

    # eMMC should not be protected
    assert emmc.safety_status not in (
        SafetyStatus.PROTECTED_SYSTEM_DISK,
        SafetyStatus.PROTECTED_CURRENT_ROOT,
        SafetyStatus.PROTECTED_BOOT_DEVICE,
        SafetyStatus.PROTECTED_RECOVERY_MEDIA,
    )

    decision = engine.verify_target(emmc, profile=profile)
    assert decision.approved, f"29.1 GiB non-removable eMMC should pass. Reason: {decision.reason}"


def test_unknown_disk_cannot_become_target():
    """A disk with UNKNOWN_UNSAFE status must fail target check."""
    from boardmedic.profiles import get_registry
    registry = get_registry(reload=True)
    profile = registry.get("dc-a568b")

    devices = parse_storage_from_fixture(LSBLK_SD_AND_EMMC)
    emmc = next(d for d in devices if d.name == "mmcblk1")

    # Don't classify - leaves status at UNKNOWN_UNSAFE
    engine = SafetyEngine()  # No root disk specified

    decision = engine.verify_target(emmc, profile=profile)
    assert not decision.approved


# ---------------------------------------------------------------------------
# Destructive gate
# ---------------------------------------------------------------------------

def test_destructive_gate_requires_flag():
    from boardmedic.models import SafetyDecision
    from boardmedic.safety import DestructiveGate

    decision = SafetyDecision(
        target="/dev/mmcblk1",
        approved=True,
        reason="ok",
    )
    gate = DestructiveGate(dry_run=False, destructive_flag=False)
    ok, reason = gate.check(decision, explicit_target="/dev/mmcblk1")
    assert not ok
    assert "destructive" in reason.lower()


def test_destructive_gate_requires_target():
    from boardmedic.models import SafetyDecision
    from boardmedic.safety import DestructiveGate

    decision = SafetyDecision(
        target="/dev/mmcblk1",
        approved=True,
        reason="ok",
    )
    gate = DestructiveGate(dry_run=False, destructive_flag=True)
    ok, reason = gate.check(decision, explicit_target=None)
    assert not ok
    assert "target" in reason.lower()


def test_destructive_gate_target_mismatch():
    from boardmedic.models import SafetyDecision
    from boardmedic.safety import DestructiveGate

    decision = SafetyDecision(
        target="/dev/mmcblk1",
        approved=True,
        reason="ok",
    )
    gate = DestructiveGate(dry_run=False, destructive_flag=True)
    ok, reason = gate.check(decision, explicit_target="/dev/mmcblk2")
    assert not ok
    assert "mismatch" in reason.lower()


def test_destructive_gate_approved():
    from boardmedic.models import SafetyDecision
    from boardmedic.safety import DestructiveGate

    decision = SafetyDecision(
        target="/dev/mmcblk1",
        approved=True,
        reason="ok",
    )
    gate = DestructiveGate(dry_run=False, destructive_flag=True)
    ok, reason = gate.check(decision, explicit_target="/dev/mmcblk1")
    assert ok


def test_destructive_gate_dry_run():
    from boardmedic.models import SafetyDecision
    from boardmedic.safety import DestructiveGate

    decision = SafetyDecision(
        target="/dev/mmcblk1",
        approved=True,
        reason="ok",
    )
    gate = DestructiveGate(dry_run=True, destructive_flag=True)
    ok, reason = gate.check(decision, explicit_target="/dev/mmcblk1")
    assert ok
    assert "DRY_RUN" in reason
