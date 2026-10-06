"""Tests for MMC diagnostics and state classification."""

from __future__ import annotations

import pytest

from boardmedic.collectors.mmc import OCR_READY_BIT, MMCDiagnostics
from boardmedic.core.runner import CommandRunner
from boardmedic.models import MMCState

DMESG_STUCK_NOT_READY = """\
[    1.678901] mmc1: SDHCI controller on fe310000.mmc [fe310000.mmc] using ADMA
[    2.200000] mmc1: CMD1 response: ocr=0x40ff8080
[    2.201000] mmc1: CMD1 response: ocr=0x40ff8080
[    2.202000] mmc1: CMD1 response: ocr=0x40ff8080
[    3.700000] mmc1: Card stuck being busy! Try to poll CMD13...
[    4.100000] mmc1: error -110 whilst initialising MMC card
[    4.200000] mmc1: Failed to initialize a non-removable card
"""

DMESG_HEALTHY = """\
[    1.678901] mmc1: SDHCI controller on fe310000.mmc [fe310000.mmc] using ADMA
[    2.100000] mmc1: new high speed MMC card at address 0001
[    2.200000] mmcblk1: mmc1:0001 CXBLLC 29.1 GiB
"""

DMESG_NO_MMC = """\
[    0.000000] Booting Linux on physical CPU 0x0000000000
[    6.000000] EXT4-fs (mmcblk0p2): mounted filesystem
"""


runner = CommandRunner()
diag = MMCDiagnostics(runner)


# ---------------------------------------------------------------------------
# OCR analysis
# ---------------------------------------------------------------------------

def test_ocr_ready_bit_not_set():
    """0x40ff8080 has bit 31 = 0, meaning NOT READY."""
    assert not diag.check_ocr_ready("40ff8080")


def test_ocr_ready_bit_set():
    """0xC0ff8080 has bit 31 = 1, meaning READY."""
    assert diag.check_ocr_ready("C0ff8080")


def test_ocr_ready_constant():
    assert OCR_READY_BIT == 0x80000000


# ---------------------------------------------------------------------------
# dmesg parsing
# ---------------------------------------------------------------------------

def test_stuck_not_ready_detected():
    matches = diag.analyze_dmesg(DMESG_STUCK_NOT_READY)
    assert len(matches["stuck_busy"]) > 0


def test_init_failed_detected():
    matches = diag.analyze_dmesg(DMESG_STUCK_NOT_READY)
    assert len(matches["init_failed"]) > 0


def test_timeout_detected():
    matches = diag.analyze_dmesg(DMESG_STUCK_NOT_READY)
    assert len(matches["timeout"]) > 0


def test_ocr_values_extracted():
    matches = diag.analyze_dmesg(DMESG_STUCK_NOT_READY)
    assert len(matches["ocr_values"]) > 0
    # 0x40ff8080 should appear
    assert any("40ff8080" in line.lower() for line in matches["ocr_values"])


def test_healthy_dmesg_no_errors():
    matches = diag.analyze_dmesg(DMESG_HEALTHY)
    assert len(matches["stuck_busy"]) == 0
    assert len(matches["init_failed"]) == 0
    assert len(matches["timeout"]) == 0


# ---------------------------------------------------------------------------
# State classification
# ---------------------------------------------------------------------------

def test_classify_stuck_not_ready():
    hosts = diag.collect_hosts(fixture_dmesg=DMESG_STUCK_NOT_READY,
                               fixture_sysfs={"fe310000.mmc/uevent": "OF_NAME=mmc"})
    matches = diag.analyze_dmesg(DMESG_STUCK_NOT_READY)
    state = diag.classify_mmc_state(hosts, matches, [])
    assert state == MMCState.CARD_RESPONDS_NOT_READY


def test_classify_block_device_present():
    hosts = diag.collect_hosts(fixture_dmesg=DMESG_HEALTHY,
                               fixture_sysfs={"fe310000.mmc/uevent": "OF_NAME=mmc"})
    matches = diag.analyze_dmesg(DMESG_HEALTHY)
    state = diag.classify_mmc_state(hosts, matches, ["/dev/mmcblk1"])
    assert state == MMCState.BLOCK_DEVICE_PRESENT


def test_classify_host_not_present():
    hosts = []
    matches = diag.analyze_dmesg("")
    state = diag.classify_mmc_state(hosts, matches, [])
    assert state == MMCState.HOST_NOT_PRESENT


def test_healthy_not_misclassified():
    """A healthy eMMC must NOT be classified as stuck/failed."""
    hosts = diag.collect_hosts(fixture_dmesg=DMESG_HEALTHY,
                               fixture_sysfs={"fe310000.mmc/uevent": "OF_NAME=mmc"})
    matches = diag.analyze_dmesg(DMESG_HEALTHY)
    state = diag.classify_mmc_state(hosts, matches, ["/dev/mmcblk1"])
    assert state != MMCState.CARD_RESPONDS_NOT_READY
    assert state != MMCState.ENUMERATION_FAILED


# ---------------------------------------------------------------------------
# DC-A568B fixture classification
# ---------------------------------------------------------------------------

def test_dc_a568b_fixture_classification():
    """The actual DC-A568B eMMC stuck fixture should classify correctly."""
    from pathlib import Path
    fixture_path = Path(__file__).parent.parent / "fixtures" / "dc_a568b" / "emmc_stuck_not_ready"
    dmesg_file = fixture_path / "dmesg.txt"
    if not dmesg_file.exists():
        pytest.skip("Fixture not available")

    dmesg_text = dmesg_file.read_text()
    hosts = diag.collect_hosts(
        fixture_dmesg=dmesg_text,
        fixture_sysfs={"fe310000.mmc/uevent": "OF_NAME=mmc"},
    )
    matches = diag.analyze_dmesg(dmesg_text, target_controller="fe310000.mmc")
    state = diag.classify_mmc_state(hosts, matches, [])

    assert state in (MMCState.CARD_RESPONDS_NOT_READY, MMCState.ENUMERATION_FAILED), (
        f"DC-A568B fixture should be classified as stuck/failed, got: {state}"
    )
