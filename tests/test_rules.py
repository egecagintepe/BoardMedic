"""Tests for diagnostic rules engine."""

from __future__ import annotations

from boardmedic.models import (
    DiagnosticSession,
    MMCState,
    RockchipDevice,
    USBDevice,
)
from boardmedic.rules import (
    EMMCNotDetectedRule,
    EMMCStuckNotReadyRule,
    HealthyEMMCRule,
    RockchipMaskROMRule,
    run_all_rules,
)


def make_session(**kwargs) -> DiagnosticSession:
    session = DiagnosticSession()
    for k, v in kwargs.items():
        setattr(session, k, v)
    return session


# ---------------------------------------------------------------------------
# eMMC stuck not-ready rule
# ---------------------------------------------------------------------------

STUCK_DMESG = """\
[    1.678901] mmc1: SDHCI controller on fe310000.mmc [fe310000.mmc] using ADMA
[    2.200000] mmc1: CMD1 response: ocr=0x40ff8080
[    3.700000] mmc1: Card stuck being busy! Try to poll CMD13...
[    4.200000] mmc1: Failed to initialize a non-removable card
"""


def test_stuck_not_ready_rule_fires():
    session = make_session(
        mmc_state=MMCState.CARD_RESPONDS_NOT_READY,
        raw_evidence={"dmesg.txt": STUCK_DMESG},
    )
    rule = EMMCStuckNotReadyRule()
    finding = rule.evaluate(session)
    assert finding is not None
    assert finding.id == "EMMC_INIT_NOT_READY"


def test_stuck_not_ready_severity_is_error():
    session = make_session(
        mmc_state=MMCState.CARD_RESPONDS_NOT_READY,
        raw_evidence={"dmesg.txt": STUCK_DMESG},
    )
    rule = EMMCStuckNotReadyRule()
    finding = rule.evaluate(session)
    assert finding.severity.value == "error"


def test_stuck_not_ready_confidence_high():
    session = make_session(
        mmc_state=MMCState.CARD_RESPONDS_NOT_READY,
        raw_evidence={"dmesg.txt": STUCK_DMESG},
    )
    rule = EMMCStuckNotReadyRule()
    finding = rule.evaluate(session)
    assert finding.confidence.value == "high"


def test_stuck_not_ready_has_evidence():
    session = make_session(
        mmc_state=MMCState.CARD_RESPONDS_NOT_READY,
        raw_evidence={"dmesg.txt": STUCK_DMESG},
    )
    rule = EMMCStuckNotReadyRule()
    finding = rule.evaluate(session)
    assert len(finding.evidence) > 0


def test_stuck_not_ready_has_possible_causes():
    session = make_session(
        mmc_state=MMCState.CARD_RESPONDS_NOT_READY,
        raw_evidence={"dmesg.txt": STUCK_DMESG},
    )
    rule = EMMCStuckNotReadyRule()
    finding = rule.evaluate(session)
    assert len(finding.possible_causes) > 0


def test_stuck_not_ready_has_next_steps():
    session = make_session(
        mmc_state=MMCState.CARD_RESPONDS_NOT_READY,
        raw_evidence={"dmesg.txt": STUCK_DMESG},
    )
    rule = EMMCStuckNotReadyRule()
    finding = rule.evaluate(session)
    assert len(finding.recommended_next_steps) > 0


def test_stuck_not_ready_does_not_claim_dead_nand():
    """Rule must NOT definitively claim NAND is dead."""
    session = make_session(
        mmc_state=MMCState.CARD_RESPONDS_NOT_READY,
        raw_evidence={"dmesg.txt": STUCK_DMESG},
    )
    rule = EMMCStuckNotReadyRule()
    finding = rule.evaluate(session)
    # Check neither summary nor interpretation makes certain NAND-dead claim
    combined = (finding.summary + " " + (finding.interpretation or "")).lower()
    assert "definitely dead" not in combined
    assert "nand is dead" not in combined


def test_stuck_not_ready_rule_skips_healthy():
    session = make_session(
        mmc_state=MMCState.BLOCK_DEVICE_PRESENT,
        raw_evidence={},
    )
    rule = EMMCStuckNotReadyRule()
    finding = rule.evaluate(session)
    assert finding is None


# ---------------------------------------------------------------------------
# eMMC not detected rule
# ---------------------------------------------------------------------------

def test_host_not_present_rule_fires():
    session = make_session(mmc_state=MMCState.HOST_NOT_PRESENT, raw_evidence={})
    rule = EMMCNotDetectedRule()
    finding = rule.evaluate(session)
    assert finding is not None
    assert finding.id == "EMMC_HOST_NOT_DETECTED"


def test_host_not_present_skips_if_present():
    session = make_session(mmc_state=MMCState.BLOCK_DEVICE_PRESENT, raw_evidence={})
    rule = EMMCNotDetectedRule()
    assert rule.evaluate(session) is None


# ---------------------------------------------------------------------------
# Rockchip MaskROM rule
# ---------------------------------------------------------------------------

def test_maskrom_rule_fires():
    rk_dev = RockchipDevice(
        usb=USBDevice(vid="2207", pid="350a", description="RK3568 MaskROM"),
        mode="maskrom",
    )
    session = make_session(rockchip_devices=[rk_dev], raw_evidence={})
    rule = RockchipMaskROMRule()
    finding = rule.evaluate(session)
    assert finding is not None
    assert finding.id == "ROCKCHIP_MASKROM_ACTIVE"


def test_maskrom_rule_skips_loader():
    rk_dev = RockchipDevice(
        usb=USBDevice(vid="2207", pid="350b", description="RK3568 Loader"),
        mode="loader",
    )
    session = make_session(rockchip_devices=[rk_dev], raw_evidence={})
    rule = RockchipMaskROMRule()
    finding = rule.evaluate(session)
    assert finding is None


def test_maskrom_rule_skips_no_rockchip():
    session = make_session(rockchip_devices=[], raw_evidence={})
    rule = RockchipMaskROMRule()
    assert rule.evaluate(session) is None


# ---------------------------------------------------------------------------
# Healthy eMMC rule
# ---------------------------------------------------------------------------

def test_healthy_emmc_rule_fires():
    session = make_session(mmc_state=MMCState.BLOCK_DEVICE_PRESENT, raw_evidence={})
    rule = HealthyEMMCRule()
    finding = rule.evaluate(session)
    assert finding is not None
    assert finding.id == "EMMC_BLOCK_DEVICE_PRESENT"


def test_healthy_rule_skips_stuck():
    session = make_session(mmc_state=MMCState.CARD_RESPONDS_NOT_READY, raw_evidence={})
    rule = HealthyEMMCRule()
    assert rule.evaluate(session) is None


# ---------------------------------------------------------------------------
# run_all_rules integration
# ---------------------------------------------------------------------------

def test_run_all_rules_stuck_scenario():
    session = make_session(
        mmc_state=MMCState.CARD_RESPONDS_NOT_READY,
        raw_evidence={"dmesg.txt": STUCK_DMESG},
        rockchip_devices=[],
    )
    findings = run_all_rules(session)
    finding_ids = {f.id for f in findings}
    assert "EMMC_INIT_NOT_READY" in finding_ids


def test_run_all_rules_maskrom_scenario():
    rk_dev = RockchipDevice(
        usb=USBDevice(vid="2207", pid="350a"),
        mode="maskrom",
    )
    session = make_session(
        mmc_state=MMCState.HEALTH_UNKNOWN,
        rockchip_devices=[rk_dev],
        raw_evidence={},
    )
    findings = run_all_rules(session)
    finding_ids = {f.id for f in findings}
    assert "ROCKCHIP_MASKROM_ACTIVE" in finding_ids


def test_rules_do_not_crash_on_empty_session():
    session = DiagnosticSession()
    findings = run_all_rules(session)
    # Should not raise, may have 0 findings
    assert isinstance(findings, list)
