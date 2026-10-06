"""Report generation engine."""

from __future__ import annotations

import json
import re
from datetime import timezone
from typing import Optional

from boardmedic.models import (
    BootStage,
    Confidence,
    DiagnosticFinding,
    DiagnosticSession,
    EvidenceType,
    MMCState,
    RecoveryPlan,
    Report,
    Severity,
    StageStatus,
)

# ---------------------------------------------------------------------------
# Anonymization
# ---------------------------------------------------------------------------

_ANON_PATTERNS = [
    # MAC addresses
    (re.compile(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}"), "[MAC_REDACTED]"),
    # IPv4
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[IP_REDACTED]"),
    # IPv6 (simplified)
    (re.compile(r"\b([0-9a-fA-F]{1,4}:){4,7}[0-9a-fA-F]{1,4}\b"), "[IPv6_REDACTED]"),
    # Hostname-like patterns (avoid destroying device paths)
    # Username in paths
    (re.compile(r"/home/([^/\s]+)"), "/home/[USER_REDACTED]"),
    (re.compile(r"C:\\Users\\([^\\]+)"), r"C:\\Users\\[USER_REDACTED]"),
]


def anonymize_text(text: str) -> str:
    """Replace identifiable information in text."""
    for pattern, replacement in _ANON_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# Markdown report generator
# ---------------------------------------------------------------------------

_SEVERITY_EMOJI = {
    Severity.CRITICAL: "🔴",
    Severity.ERROR: "[WARN]",
    Severity.WARNING: "[INFO]",
    Severity.INFO: "🔵",
}

_STAGE_STATUS_LABEL = {
    StageStatus.PASS: "[OK] PASS",
    StageStatus.LIKELY_PASS: "[INFO] LIKELY PASS",
    StageStatus.UNKNOWN: "[o] UNKNOWN",
    StageStatus.LIKELY_FAIL: "[WARN] LIKELY FAIL",
    StageStatus.FAIL: "[X] FAIL",
    StageStatus.NOT_APPLICABLE: "-- N/A",
}

_EVIDENCE_LABELS = {
    EvidenceType.OBSERVED: "**OBSERVED**",
    EvidenceType.DERIVED: "**DERIVED**",
    EvidenceType.INFERRED: "**INFERRED**",
    EvidenceType.HYPOTHESIS: "**HYPOTHESIS**",
}

_MMC_STATE_LABELS = {
    MMCState.HOST_NOT_PRESENT: "[X] Host controller not detected",
    MMCState.HOST_PRESENT_NO_CARD_RESPONSE: "[WARN] Host present, no card response",
    MMCState.CARD_RESPONDS_NOT_READY: "[WARN] Card responds but NEVER transitions to READY",
    MMCState.ENUMERATION_FAILED: "[X] Card enumeration failed",
    MMCState.BLOCK_DEVICE_PRESENT: "[OK] Block device present",
    MMCState.READ_ONLY: "[INFO] Block device present (read-only)",
    MMCState.IO_ERRORS: "[WARN] Block device present but I/O errors",
    MMCState.HEALTH_UNKNOWN: "[o] State unknown",
}


def generate_markdown_report(
    session: DiagnosticSession,
    anonymize: bool = False,
) -> str:
    """Generate a human-readable Markdown diagnostic report."""
    lines: list[str] = []
    info = session.info

    def a(text: str) -> str:
        return anonymize_text(text) if anonymize else text

    lines += [
        "# BoardMedic Diagnostic Report",
        "",
        "---",
        "",
    ]

    # ---- Session Information ----
    lines += ["## Session Information", ""]
    lines += [
        "| Field | Value |",
        "|-------|-------|",
        f"| Session ID | `{info.id}` |",
        f"| Generated | {info.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')} |",
        f"| BoardMedic Version | {info.boardmedic_version} |",
        f"| Platform | {info.platform} |",
        f"| Profile | {info.profile_id or '(none)'} |",
        f"| Elevated | {'Yes' if info.elevated else 'No'} |",
        f"| Dry Run | {'Yes' if info.dry_run else 'No'} |",
        f"| Fixture | {info.fixture_path or '(live system)'} |",
        "",
    ]
    if not anonymize:
        lines += [
            f"| Host | {a(info.host_hostname or 'unknown')} |",
            f"| User | {a(info.host_username or 'unknown')} |",
            "",
        ]
    if anonymize:
        lines += ["", "> **Note**: This report has been anonymized.", ""]

    # ---- USB Devices ----
    lines += ["## USB Devices", ""]
    if session.usb_devices:
        lines.append("| VID | PID | Description |")
        lines.append("|-----|-----|-------------|")
        for dev in session.usb_devices:
            desc = a(dev.description or "")
            lines.append(f"| `{dev.vid}` | `{dev.pid}` | {desc} |")
    else:
        lines.append("_No USB devices detected._")
    lines.append("")

    # Rockchip
    if session.rockchip_devices:
        lines += ["### Rockchip USB Devices", ""]
        for rk in session.rockchip_devices:
            lines.append(f"- **{rk.usb.vid}:{rk.usb.pid}** -- Mode: `{rk.mode}` -- {rk.usb.description or ''}")
        lines.append("")

    # ---- Serial Ports ----
    lines += ["## Serial Ports", ""]
    if session.serial_ports:
        for p in session.serial_ports:
            lines.append(f"- `{p.port}` -- {p.description or '(no description)'}")
    else:
        lines.append("_No serial ports detected._")
    lines.append("")

    # ---- Network ----
    lines += ["## Network Interfaces", ""]
    if session.network_interfaces:
        lines.append("| Interface | State | IPv4 | MAC |")
        lines.append("|-----------|-------|------|-----|")
        for iface in session.network_interfaces:
            ipv4 = ", ".join(a(ip) for ip in iface.ipv4) if iface.ipv4 else "-"
            mac = a(iface.mac or "-")
            lines.append(f"| `{iface.name}` | {iface.state} | {ipv4} | {mac} |")
    else:
        lines.append("_No network interfaces detected._")
    lines.append("")

    # ---- Storage ----
    lines += ["## Storage Devices", ""]
    if session.storage_devices:
        lines.append("| Device | Size | Class | Removable | Safety | Mountpoints |")
        lines.append("|--------|------|-------|-----------|--------|-------------|")
        for dev in session.storage_devices:
            size_str = f"{dev.size_gib:.1f} GiB" if dev.size_gib else "?"
            mps = ", ".join(dev.mount_points) if dev.mount_points else "-"
            lines.append(
                f"| `{dev.path or dev.name}` | {size_str} | "
                f"{dev.storage_class.value} | "
                f"{'Yes' if dev.removable else 'No'} | "
                f"`{dev.safety_status.value}` | {mps} |"
            )
    else:
        lines.append("_No storage devices detected._")
    lines.append("")

    # ---- MMC/eMMC ----
    lines += ["## MMC/eMMC Status", ""]
    if session.mmc_state:
        label = _MMC_STATE_LABELS.get(session.mmc_state, session.mmc_state.value)
        lines.append(f"**MMC State**: {label}")
    else:
        lines.append("**MMC State**: Not assessed")
    lines.append("")

    # ---- Boot Chain ----
    lines += ["## Boot Chain Analysis", ""]
    if session.boot_chain:
        lines.append("| Stage | Status | Evidence |")
        lines.append("|-------|--------|----------|")
        for stage in session.boot_chain.stages:
            label = _STAGE_STATUS_LABEL.get(stage.status, stage.status.value)
            ev = "; ".join(stage.evidence) if stage.evidence else "-"
            lines.append(f"| {stage.stage.value.upper()} | {label} | {ev} |")
    else:
        lines.append("_Boot chain analysis not available._")
    lines.append("")

    # ---- Findings ----
    lines += ["## Diagnostic Findings", ""]
    if session.findings:
        # Sort by severity
        sev_order = {Severity.CRITICAL: 0, Severity.ERROR: 1, Severity.WARNING: 2, Severity.INFO: 3}
        sorted_findings = sorted(session.findings, key=lambda f: sev_order.get(f.severity, 99))

        for finding in sorted_findings:
            emoji = _SEVERITY_EMOJI.get(finding.severity, "")
            lines.append(f"### {emoji} {finding.id}")
            lines.append("")
            lines.append(f"- **Severity**: {finding.severity.value.upper()}")
            lines.append(f"- **Confidence**: {finding.confidence.value.upper()}")
            lines.append(f"- **Summary**: {finding.summary}")
            if finding.detail:
                lines.append("")
                lines.append(finding.detail)
            lines.append("")

            if finding.evidence:
                lines.append("#### Evidence")
                lines.append("")
                for ev in finding.evidence:
                    prefix = _EVIDENCE_LABELS.get(ev.type, ev.type.value)
                    lines.append(f"- {prefix}: {ev.description}")
                    if ev.raw_value:
                        lines.append(f"  - Raw: `{ev.raw_value}`")
                lines.append("")

            if finding.interpretation:
                lines.append("#### Interpretation")
                lines.append("")
                lines.append(finding.interpretation)
                lines.append("")

            if finding.possible_causes:
                lines.append("#### Possible Causes")
                lines.append("")
                for cause in finding.possible_causes:
                    lines.append(f"- {cause}")
                lines.append("")

            if finding.recommended_next_steps:
                lines.append("#### Recommended Next Steps")
                lines.append("")
                for step in finding.recommended_next_steps:
                    lines.append(f"1. {step}")
                lines.append("")
    else:
        lines.append("_No diagnostic findings._")
        lines.append("")

    # ---- Recovery Plan ----
    if session.recovery_plan:
        plan = session.recovery_plan
        lines += ["## Recovery Plan", ""]
        lines.append(f"**Result Code**: `{plan.result_code.value}`")
        lines.append("")
        if plan.notes:
            for note in plan.notes:
                lines.append(f"> {note}")
            lines.append("")
        for step in plan.steps:
            dest_badge = " [!]️ **DESTRUCTIVE**" if step.destructive else ""
            disrupt_badge = " [*] DISRUPTIVE" if step.disruptive else ""
            lines.append(f"### Step {step.order}: {step.title}{dest_badge}{disrupt_badge}")
            lines.append("")
            lines.append(step.description)
            if step.skip_reason:
                lines.append("")
                lines.append(f"_Skip condition: {step.skip_reason}_")
            if step.commands:
                lines.append("")
                lines.append("```bash")
                for cmd in step.commands:
                    lines.append(cmd)
                lines.append("```")
            lines.append("")

    # ---- Limitations ----
    lines += [
        "## Limitations",
        "",
        "- BoardMedic reports are based on available evidence only.",
        "- Software testing only -- no hardware validation occurred.",
        "- Fixture-based analysis may not reflect all real-world conditions.",
        "- Destructive conclusions require additional hardware-level investigation.",
        "- This report does not constitute a guarantee of hardware condition.",
        "",
        "---",
        f"*Generated by BoardMedic {info.boardmedic_version}*",
        "",
    ]

    content = "\n".join(lines)
    if anonymize:
        content = anonymize_text(content)
    return content


def generate_json_report(
    session: DiagnosticSession,
    anonymize: bool = False,
) -> str:
    """Generate a structured JSON report."""
    data = session.model_dump(mode="json")
    content = json.dumps(data, indent=2, default=str)
    if anonymize:
        content = anonymize_text(content)
    return content


class ReportGenerator:
    """Generates diagnostic reports in multiple formats."""

    def generate(
        self,
        session: DiagnosticSession,
        format: str = "markdown",
        anonymize: bool = False,
    ) -> Report:
        if format == "markdown":
            content = generate_markdown_report(session, anonymize=anonymize)
        elif format == "json":
            content = generate_json_report(session, anonymize=anonymize)
        else:
            content = generate_markdown_report(session, anonymize=anonymize)

        return Report(
            session_id=session.info.id,
            format=format,
            content=content,
            anonymized=anonymize,
        )
