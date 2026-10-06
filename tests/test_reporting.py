"""Tests for report generation."""

from __future__ import annotations

import json

from boardmedic.models import (
    Confidence,
    DiagnosticFinding,
    DiagnosticSession,
    EvidenceItem,
    EvidenceType,
    MMCState,
    Severity,
)
from boardmedic.reporting import (
    ReportGenerator,
    anonymize_text,
    generate_json_report,
    generate_markdown_report,
)


def make_session_with_findings() -> DiagnosticSession:
    session = DiagnosticSession()
    session.mmc_state = MMCState.CARD_RESPONDS_NOT_READY
    session.raw_evidence = {"dmesg.txt": "mmc1: CMD1 response: ocr=0x40ff8080"}
    session.findings = [
        DiagnosticFinding(
            id="EMMC_INIT_NOT_READY",
            severity=Severity.ERROR,
            confidence=Confidence.HIGH,
            summary="Internal eMMC initialization failing",
            evidence=[
                EvidenceItem(
                    type=EvidenceType.OBSERVED,
                    description="OCR 0x40ff8080 observed",
                    source="dmesg",
                ),
                EvidenceItem(
                    type=EvidenceType.DERIVED,
                    description="READY bit never set",
                    source="OCR analysis",
                ),
                EvidenceItem(
                    type=EvidenceType.HYPOTHESIS,
                    description="eMMC may have internal fault",
                    source="inference",
                ),
            ],
            possible_causes=["Power integrity issue", "eMMC internal failure"],
            recommended_next_steps=["Check power supply", "Try USB recovery"],
        )
    ]
    return session


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def test_markdown_report_generates():
    session = make_session_with_findings()
    md = generate_markdown_report(session)
    assert isinstance(md, str)
    assert len(md) > 100


def test_markdown_contains_findings_section():
    session = make_session_with_findings()
    md = generate_markdown_report(session)
    assert "Diagnostic Findings" in md


def test_markdown_contains_finding_id():
    session = make_session_with_findings()
    md = generate_markdown_report(session)
    assert "EMMC_INIT_NOT_READY" in md


def test_markdown_contains_evidence_labels():
    session = make_session_with_findings()
    md = generate_markdown_report(session)
    assert "OBSERVED" in md
    assert "DERIVED" in md
    assert "HYPOTHESIS" in md


def test_markdown_contains_session_info():
    session = make_session_with_findings()
    md = generate_markdown_report(session)
    assert "Session" in md
    assert session.info.id[:8] in md


def test_markdown_contains_mmc_state():
    session = make_session_with_findings()
    md = generate_markdown_report(session)
    assert "MMC" in md


def test_markdown_has_limitations_section():
    session = make_session_with_findings()
    md = generate_markdown_report(session)
    assert "Limitations" in md


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------

def test_json_report_is_valid_json():
    session = make_session_with_findings()
    json_str = generate_json_report(session)
    data = json.loads(json_str)
    assert isinstance(data, dict)


def test_json_report_contains_findings():
    session = make_session_with_findings()
    json_str = generate_json_report(session)
    data = json.loads(json_str)
    assert "findings" in data
    assert len(data["findings"]) > 0


def test_json_report_schema_stable():
    """Ensure key fields are present in JSON output."""
    session = make_session_with_findings()
    json_str = generate_json_report(session)
    data = json.loads(json_str)
    assert "info" in data
    assert "findings" in data
    assert "mmc_state" in data
    assert "usb_devices" in data
    assert "storage_devices" in data


# ---------------------------------------------------------------------------
# Anonymization
# ---------------------------------------------------------------------------

def test_anonymize_ip():
    text = "Connected to 192.168.1.100"
    result = anonymize_text(text)
    assert "192.168.1.100" not in result
    assert "REDACTED" in result


def test_anonymize_mac():
    text = "MAC: aa:bb:cc:dd:ee:ff"
    result = anonymize_text(text)
    assert "aa:bb:cc:dd:ee:ff" not in result


def test_anonymize_home_path():
    text = "/home/engineer/boardmedic"
    result = anonymize_text(text)
    assert "/home/engineer" not in result


def test_anonymize_preserves_technical_data():
    """Anonymization must not destroy device paths or OCR values."""
    text = "Device /dev/mmcblk1 OCR=0x40ff8080"
    result = anonymize_text(text)
    assert "/dev/mmcblk1" in result
    assert "0x40ff8080" in result


def test_anonymize_report_flag():
    session = make_session_with_findings()
    gen = ReportGenerator()
    report = gen.generate(session, format="markdown", anonymize=True)
    assert report.anonymized is True


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

def test_report_generator_markdown():
    session = make_session_with_findings()
    gen = ReportGenerator()
    report = gen.generate(session, format="markdown")
    assert report.format == "markdown"
    assert len(report.content) > 100


def test_report_generator_json():
    session = make_session_with_findings()
    gen = ReportGenerator()
    report = gen.generate(session, format="json")
    assert report.format == "json"
    data = json.loads(report.content)
    assert "findings" in data
