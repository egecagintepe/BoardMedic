"""Integration tests using fixture data."""

from __future__ import annotations

from pathlib import Path

import pytest

from boardmedic.diagnostics import Diagnostics
from boardmedic.models import MMCState, RecoveryResultCode
from boardmedic.recovery.planner import RecoveryPlanner
from boardmedic.reporting import ReportGenerator

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# DC-A568B eMMC stuck not-ready fixture
# ---------------------------------------------------------------------------

def test_dc_a568b_fixture_diagnose():
    """Full diagnostics run on the eMMC stuck fixture."""
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(
        profile_id="dc-a568b",
        fixture_path=fixture_path,
    )
    session = diag.run()

    assert session is not None
    assert session.mmc_state is not None


def test_dc_a568b_stuck_not_ready_classification():
    """eMMC stuck fixture must classify as CARD_RESPONDS_NOT_READY or ENUMERATION_FAILED."""
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    assert session.mmc_state in (
        MMCState.CARD_RESPONDS_NOT_READY,
        MMCState.ENUMERATION_FAILED,
    ), f"Expected stuck/failed state, got {session.mmc_state}"


def test_dc_a568b_findings_generated():
    """At least one finding should be generated for the stuck fixture."""
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    assert len(session.findings) > 0
    finding_ids = {f.id for f in session.findings}
    assert "EMMC_INIT_NOT_READY" in finding_ids


def test_dc_a568b_no_block_device_in_findings():
    """The stuck fixture finding must mention no block device."""
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    finding = next((f for f in session.findings if f.id == "EMMC_INIT_NOT_READY"), None)
    if finding:
        # Check evidence mentions no block device
        ev_text = " ".join(e.description for e in finding.evidence).lower()
        assert "mmcblk" in ev_text or "block" in ev_text


def test_dc_a568b_sd_card_detected():
    """SD card (root device) should be in storage devices."""
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    storage_names = {d.name for d in session.storage_devices}
    assert "mmcblk0" in storage_names


def test_dc_a568b_sd_not_emmc_target():
    """512GB SD card must not become a valid destructive target for dc-a568b."""
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    from boardmedic.profiles import get_registry
    from boardmedic.safety import SafetyEngine

    registry = get_registry(reload=True)
    profile = registry.get("dc-a568b")
    assert profile is not None

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    sd = next((d for d in session.storage_devices if d.name == "mmcblk0"), None)
    if sd:
        engine = SafetyEngine(root_disk="/dev/mmcblk0")
        engine.classify_all(session.storage_devices)
        decision = engine.verify_target(sd, profile=profile)
        assert not decision.approved, "SD card (root) must never be a destructive target"


# ---------------------------------------------------------------------------
# Rockchip MaskROM fixture
# ---------------------------------------------------------------------------

def test_rockchip_maskrom_fixture():
    fixture_path = FIXTURES_DIR / "rockchip_maskrom_detected"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    assert len(session.rockchip_devices) > 0
    assert any(d.mode == "maskrom" for d in session.rockchip_devices)

    finding_ids = {f.id for f in session.findings}
    assert "ROCKCHIP_MASKROM_ACTIVE" in finding_ids


# ---------------------------------------------------------------------------
# Healthy board fixture
# ---------------------------------------------------------------------------

def test_healthy_board_fixture():
    fixture_path = FIXTURES_DIR / "healthy_linux_board"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    assert session.mmc_state == MMCState.BLOCK_DEVICE_PRESENT
    finding_ids = {f.id for f in session.findings}
    # Must NOT generate stuck/failed finding
    assert "EMMC_INIT_NOT_READY" not in finding_ids
    # Should generate healthy finding
    assert "EMMC_BLOCK_DEVICE_PRESENT" in finding_ids


# ---------------------------------------------------------------------------
# Dangerous host disk fixture
# ---------------------------------------------------------------------------

def test_dangerous_host_disk_fixture():
    fixture_path = FIXTURES_DIR / "dangerous_host_disk"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    from boardmedic.profiles import get_registry
    from boardmedic.safety import SafetyEngine

    registry = get_registry(reload=True)
    profile = registry.get("dc-a568b")

    from boardmedic.collectors.storage import parse_storage_from_fixture
    lsblk_file = fixture_path / "lsblk.json"
    if not lsblk_file.exists():
        pytest.skip("lsblk fixture not available")

    devices = parse_storage_from_fixture(lsblk_file.read_text())
    engine = SafetyEngine(root_disk="/dev/sda")
    engine.classify_all(devices)

    sda = next(d for d in devices if d.name == "sda")
    decision = engine.verify_target(sda, profile=profile)
    assert not decision.approved, "Host OS disk must always be refused"


# ---------------------------------------------------------------------------
# Dry-run integration
# ---------------------------------------------------------------------------

def test_dry_run_does_not_execute_destructive():
    """Dry-run must never execute destructive commands."""
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(
        profile_id="dc-a568b",
        fixture_path=fixture_path,
        dry_run=True,
    )
    session = diag.run()

    # Any destructive commands in history should be marked dry_run
    for cmd in session.commands:
        if cmd.destructive:
            assert cmd.dry_run, f"Destructive command not marked dry_run: {cmd.command_str}"


# ---------------------------------------------------------------------------
# Recovery plan
# ---------------------------------------------------------------------------

def test_recovery_plan_generated():
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    planner = RecoveryPlanner()
    from boardmedic.profiles import get_registry
    profile = get_registry().get("dc-a568b")
    plan = planner.plan(session, profile=profile)

    assert plan is not None
    assert len(plan.steps) > 0


def test_recovery_plan_has_nondestructive_first():
    """First steps in recovery plan should not be destructive."""
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    planner = RecoveryPlanner()
    plan = planner.plan(session)

    # First step must not be destructive
    assert not plan.steps[0].destructive


def test_recovery_plan_code_stuck_not_ready():
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    planner = RecoveryPlanner()
    plan = planner.plan(session)
    assert plan.result_code == RecoveryResultCode.EMMC_STUCK_NOT_READY


# ---------------------------------------------------------------------------
# Report from fixture
# ---------------------------------------------------------------------------

def test_report_from_dc_a568b_fixture():
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    gen = ReportGenerator()
    report = gen.generate(session, format="markdown")

    assert "EMMC_INIT_NOT_READY" in report.content
    assert "Diagnostic Findings" in report.content
    assert "Evidence" in report.content


def test_json_report_from_dc_a568b_fixture():
    import json as _json
    fixture_path = FIXTURES_DIR / "dc_a568b" / "emmc_stuck_not_ready"
    if not fixture_path.exists():
        pytest.skip("Fixture not available")

    diag = Diagnostics(profile_id="dc-a568b", fixture_path=fixture_path)
    session = diag.run()

    gen = ReportGenerator()
    report = gen.generate(session, format="json")
    data = _json.loads(report.content)
    assert "findings" in data
    finding_ids = [f["id"] for f in data["findings"]]
    assert "EMMC_INIT_NOT_READY" in finding_ids
