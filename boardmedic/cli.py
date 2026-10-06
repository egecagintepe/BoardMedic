"""
BoardMedic CLI

Cross-platform embedded board diagnostics and recovery toolkit.

EXIT CODES:
  0  - Success, no critical findings
  1  - Diagnostic findings present
  2  - Invalid usage / bad arguments
  3  - Permission required
  4  - Dependency / tool missing
  5  - Safety refusal
  6  - Recovery failure
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows console encoding safety
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from boardmedic import __version__

app = typer.Typer(
    name="boardmedic",
    help="Cross-platform embedded board diagnostics and recovery toolkit.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)

detect_app = typer.Typer(help="Detect connected devices and interfaces.", no_args_is_help=True)
probe_app = typer.Typer(help="Probe specific interfaces.", no_args_is_help=True)
profiles_app = typer.Typer(help="Manage board profiles.", no_args_is_help=True)
recover_app = typer.Typer(help="Recovery planning and operations.", no_args_is_help=True)
report_app = typer.Typer(help="Generate diagnostic reports.")
session_app = typer.Typer(help="Manage diagnostic sessions.", no_args_is_help=True)

app.add_typer(detect_app, name="detect")
app.add_typer(probe_app, name="probe")
app.add_typer(profiles_app, name="profiles")
app.add_typer(recover_app, name="recover")
app.add_typer(report_app, name="report")
app.add_typer(session_app, name="session")

console = Console()
err_console = Console(stderr=True)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"BoardMedic [bold cyan]{__version__}[/bold cyan]")
        raise typer.Exit(0)


@app.callback()
def main_callback(
    version: bool | None = typer.Option(
        None, "--version", "-V", callback=version_callback, is_eager=True,
        help="Show version and exit."
    ),
) -> None:
    """BoardMedic - Embedded board diagnostics and recovery toolkit."""


# ============================================================================
# doctor command
# ============================================================================


@app.command("doctor")
def cmd_doctor() -> None:
    """Check host environment and tool availability."""
    from boardmedic.platform import PlatformInfo, ToolStatus

    console.print(Panel(
        f"[bold cyan]BoardMedic {__version__}[/bold cyan] -- Host Environment Check",
        box=box.ROUNDED,
    ))

    info = PlatformInfo()

    # OS info
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Property", style="bold")
    table.add_column("Value")
    table.add_row("Platform", info.os_version)
    table.add_row("Python", sys.version.split()[0])
    table.add_row("Elevated / Admin", "[OK] Yes" if info.elevated else "[X] No")
    console.print(table)

    # Tools
    console.print("\n[bold]External Tools[/bold]")
    tool_table = Table(box=box.SIMPLE)
    tool_table.add_column("Tool", style="cyan")
    tool_table.add_column("Status")
    for name, status in sorted(info.tools.items()):
        if status == ToolStatus.AVAILABLE:
            status_str = "[green][OK] available[/green]"
        elif status == ToolStatus.PERMISSION_REQUIRED:
            status_str = "[yellow][LOCKED] permission required[/yellow]"
        elif status == ToolStatus.NOT_SUPPORTED:
            status_str = "[dim]-- not supported[/dim]"
        else:
            status_str = "[red][X] missing[/red]"
        tool_table.add_row(name, status_str)
    console.print(tool_table)

    # Capabilities
    console.print("\n[bold]Capabilities[/bold]")
    cap_table = Table(box=box.SIMPLE)
    cap_table.add_column("Capability", style="cyan")
    cap_table.add_column("Status")
    for name, status in info.capabilities.items():
        if status == ToolStatus.AVAILABLE:
            status_str = "[green][OK] available[/green]"
        elif status == ToolStatus.PERMISSION_REQUIRED:
            status_str = "[yellow][LOCKED] permission required[/yellow]"
        else:
            status_str = "[red][X] missing[/red]"
        cap_table.add_row(name, status_str)
    console.print(cap_table)

    console.print()
    console.print("[dim]Run [bold]boardmedic profiles list[/bold] to see available board profiles.[/dim]")


# ============================================================================
# detect commands
# ============================================================================


@detect_app.command("usb")
def cmd_detect_usb() -> None:
    """Detect USB devices including Rockchip devices."""
    from boardmedic.core.runner import CommandRunner
    from boardmedic.probes.usb import USBProbe

    runner = CommandRunner()
    probe = USBProbe(runner)
    devices, rk_devices = probe.probe()

    console.print(f"\n[bold]USB Devices[/bold] ({len(devices)} found)\n")
    if devices:
        t = Table(box=box.SIMPLE)
        t.add_column("VID", style="cyan")
        t.add_column("PID", style="cyan")
        t.add_column("Description")
        for d in devices:
            t.add_row(d.vid, d.pid or "?", d.description or "")
        console.print(t)
    else:
        console.print("[dim]No USB devices detected.[/dim]")

    if rk_devices:
        console.print(f"\n[bold yellow][*] Rockchip Devices[/bold yellow] ({len(rk_devices)} found)")
        for rk in rk_devices:
            console.print(
                f"  [cyan]{rk.usb.vid}:{rk.usb.pid}[/cyan] -- "
                f"Mode: [bold]{rk.mode}[/bold] -- {rk.usb.description or ''}"
            )


@detect_app.command("serial")
def cmd_detect_serial() -> None:
    """Detect serial/UART ports."""
    from boardmedic.probes.serial import enumerate_serial_ports

    ports = enumerate_serial_ports()
    console.print(f"\n[bold]Serial Ports[/bold] ({len(ports)} found)\n")
    if ports:
        t = Table(box=box.SIMPLE)
        t.add_column("Port", style="cyan")
        t.add_column("Description")
        t.add_column("VID:PID")
        for p in ports:
            vid_pid = f"{p.vid}:{p.pid}" if p.vid else "-"
            t.add_row(p.port, p.description or "", vid_pid)
        console.print(t)
    else:
        console.print("[dim]No serial ports detected.[/dim]")


@detect_app.command("network")
@probe_app.command("network")
def cmd_detect_network() -> None:
    """Detect network interfaces."""
    from boardmedic.core.runner import CommandRunner
    from boardmedic.probes.network import NetworkProbe

    runner = CommandRunner()
    probe = NetworkProbe(runner)
    ifaces, _neighbors = probe.probe()

    console.print(f"\n[bold]Network Interfaces[/bold] ({len(ifaces)} found)\n")
    if ifaces:
        t = Table(box=box.SIMPLE)
        t.add_column("Interface", style="cyan")
        t.add_column("State")
        t.add_column("IPv4")
        t.add_column("MAC")
        for i in ifaces:
            t.add_row(
                i.name,
                i.state,
                ", ".join(i.ipv4) if i.ipv4 else "-",
                i.mac or "-",
            )
        console.print(t)
    else:
        console.print("[dim]No network interfaces detected.[/dim]")


@detect_app.command("storage")
def cmd_detect_storage() -> None:
    """Detect storage devices."""
    from boardmedic.collectors.storage import StorageProbe
    from boardmedic.core.runner import CommandRunner
    from boardmedic.safety import SafetyEngine

    runner = CommandRunner()
    probe = StorageProbe(runner)
    devices = probe.probe()
    root_disk = probe.get_root_parent_disk()

    safety = SafetyEngine(root_disk=root_disk)
    safety.classify_all(devices)

    console.print(f"\n[bold]Storage Devices[/bold] ({len(devices)} found)\n")
    if devices:
        t = Table(box=box.SIMPLE)
        t.add_column("Device", style="cyan")
        t.add_column("Size")
        t.add_column("Class")
        t.add_column("Removable")
        t.add_column("Safety")
        for d in devices:
            size = f"{d.size_gib:.1f} GiB" if d.size_gib else "?"
            safety_color = "red" if "protected" in d.safety_status.value else "green"
            t.add_row(
                d.path or d.name,
                size,
                d.storage_class.value,
                "Yes" if d.removable else "No",
                f"[{safety_color}]{d.safety_status.value}[/{safety_color}]",
            )
        console.print(t)
    else:
        console.print("[dim]No storage devices detected.[/dim]")

    if root_disk:
        console.print(f"\n[dim]Root disk: [bold]{root_disk}[/bold] (protected)[/dim]")


# ============================================================================
# probe commands
# ============================================================================


@probe_app.command("usb")
def cmd_probe_usb() -> None:
    """Probe USB for Rockchip devices."""
    cmd_detect_usb()


@probe_app.command("serial")
def cmd_probe_serial(
    port: str | None = typer.Option(None, "--port", "-p", help="Serial port to capture from"),
    baud: int = typer.Option(115200, "--baud", "-b", help="Baud rate"),
    seconds: float = typer.Option(10.0, "--seconds", "-s", help="Capture duration in seconds"),
) -> None:
    """Probe serial/UART port."""
    from boardmedic.probes.serial import capture_serial

    if not port:
        cmd_detect_serial()
        return

    console.print(f"\n[bold]Capturing from [cyan]{port}[/cyan] at {baud} baud for {seconds}s...[/bold]\n")
    cap = capture_serial(port, baud, seconds)
    if cap.error:
        err_console.print(f"[red]Error: {cap.error}[/red]")
        raise typer.Exit(4)
    if cap.lines:
        for line in cap.lines:
            console.print(line)
    else:
        console.print("[dim]No data received.[/dim]")


@probe_app.command("adb")
def cmd_probe_adb() -> None:
    """Probe ADB for connected Android devices."""
    from boardmedic.core.runner import CommandRunner
    from boardmedic.models import ToolStatus
    from boardmedic.probes.adb import probe_adb

    runner = CommandRunner()
    status, devices = probe_adb(runner)

    if status == ToolStatus.UNAVAILABLE:
        console.print("[yellow]ADB not found on PATH.[/yellow]")
        raise typer.Exit(4)
    console.print(f"\n[bold]ADB Devices[/bold] ({len(devices)} found)\n")
    if devices:
        for d in devices:
            console.print(f"  [cyan]{d.serial}[/cyan] -- {d.state}")
    else:
        console.print("[dim]No ADB devices.[/dim]")


@probe_app.command("fastboot")
def cmd_probe_fastboot() -> None:
    """Probe fastboot for connected devices."""
    from boardmedic.core.runner import CommandRunner
    from boardmedic.models import ToolStatus
    from boardmedic.probes.adb import probe_fastboot

    runner = CommandRunner()
    status, devices = probe_fastboot(runner)

    if status == ToolStatus.UNAVAILABLE:
        console.print("[yellow]fastboot not found on PATH.[/yellow]")
        raise typer.Exit(4)
    console.print(f"\n[bold]Fastboot Devices[/bold] ({len(devices)} found)\n")
    if devices:
        for d in devices:
            console.print(f"  [cyan]{d.serial}[/cyan]")
    else:
        console.print("[dim]No fastboot devices.[/dim]")


@probe_app.command("rockchip")
def cmd_probe_rockchip() -> None:
    """Probe for Rockchip upgrade_tool / rkdeveloptool devices."""
    from boardmedic.core.runner import CommandRunner
    from boardmedic.probes.adb import RockchipToolProbe

    runner = CommandRunner()
    probe = RockchipToolProbe(runner)
    tool_status = probe.tool_status()

    console.print("\n[bold]Rockchip Tools[/bold]")
    for tool, status in tool_status.items():
        if status.value == "available":
            console.print(f"  [green][OK] {tool}[/green]")
        else:
            console.print(f"  [red][X] {tool}[/red]")

    if any(s.value == "available" for s in tool_status.values()):
        devices = probe.list_devices()
        if devices:
            console.print("\n[bold]Connected Rockchip Devices:[/bold]")
            for d in devices:
                console.print(f"  {d}")
        else:
            console.print("\n[dim]No Rockchip devices listed by tools.[/dim]")

    # Also show USB
    from boardmedic.probes.usb import USBProbe
    usb_probe = USBProbe(runner)
    _, rk_devices = usb_probe.probe()
    if rk_devices:
        console.print("\n[bold yellow]Rockchip USB Devices:[/bold yellow]")
        for rk in rk_devices:
            console.print(
                f"  [cyan]{rk.usb.vid}:{rk.usb.pid}[/cyan] -- "
                f"Mode: [bold]{rk.mode}[/bold]"
            )


@probe_app.command("storage")
def cmd_probe_storage() -> None:
    """Probe storage devices."""
    cmd_detect_storage()


@probe_app.command("mmc")
def cmd_probe_mmc() -> None:
    """Probe MMC/eMMC state."""
    from boardmedic.collectors.mmc import MMCDiagnostics
    from boardmedic.core.runner import CommandRunner

    runner = CommandRunner()
    diag = MMCDiagnostics(runner)
    hosts = diag.collect_hosts()
    dmesg = diag.collect_dmesg()
    matches = diag.analyze_dmesg(dmesg)
    state = diag.classify_mmc_state(hosts, matches, [])

    console.print(f"\n[bold]MMC/eMMC State[/bold]: {state.value}\n")
    if hosts:
        for h in hosts:
            console.print(f"  Host: [cyan]{h.host_name}[/cyan]")
            if h.cid:
                console.print(f"  CID: {h.cid}")
            if h.block_device:
                console.print(f"  Block device: [green]{h.block_device}[/green]")
    if matches.get("stuck_busy"):
        console.print("\n  [red][!] Stuck busy detected[/red]")
    if matches.get("init_failed"):
        console.print("  [red][!] Init failed detected[/red]")


@probe_app.command("ssh")
def cmd_probe_ssh(
    target: str = typer.Argument(..., help="Target host (IP or hostname)"),
    port: int = typer.Option(22, "--port", "-p"),
    user: str = typer.Option("root", "--user", "-u"),
    key: str | None = typer.Option(None, "--key", "-i", help="Path to SSH identity file"),
    timeout: int = typer.Option(10, "--timeout", "-t"),
) -> None:
    """Test SSH connectivity to target board."""
    from boardmedic.core.runner import CommandRunner

    runner = CommandRunner()
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no",
           "-o", f"ConnectTimeout={timeout}",
           "-o", "BatchMode=yes"]
    if key:
        cmd += ["-i", key]
    cmd += [f"{user}@{target}", "-p", str(port), "echo boardmedic_ok"]

    console.print(f"\n[bold]Testing SSH to [cyan]{target}:{port}[/cyan]...[/bold]")
    result = runner.run(cmd, timeout=timeout + 5)
    if result.exit_code == 0 and "boardmedic_ok" in result.stdout:
        console.print("[green][OK] SSH connection successful[/green]")
    else:
        console.print(f"[red][X] SSH failed (exit {result.exit_code})[/red]")
        if result.stderr:
            console.print(f"[dim]{result.stderr[:200]}[/dim]")


# ============================================================================
# profiles commands
# ============================================================================


@profiles_app.command("list")
def cmd_profiles_list() -> None:
    """List all available board profiles."""
    from boardmedic.profiles import get_registry

    registry = get_registry()
    profiles = registry.list_profiles()

    console.print(f"\n[bold]Board Profiles[/bold] ({len(profiles)} available)\n")
    if profiles:
        t = Table(box=box.SIMPLE)
        t.add_column("ID", style="cyan")
        t.add_column("Name")
        t.add_column("SoC Family")
        t.add_column("Aliases")
        for p in profiles:
            t.add_row(
                p.id,
                p.display_name,
                p.soc_family,
                ", ".join(p.aliases) if p.aliases else "-",
            )
        console.print(t)
    else:
        console.print("[yellow]No profiles found in profiles/ directory.[/yellow]")

    if registry.has_errors():
        console.print("\n[red]Profile errors:[/red]")
        for name, err in registry.errors().items():
            console.print(f"  [red]{name}[/red]: {err}")


@profiles_app.command("show")
def cmd_profiles_show(
    profile_id: str = typer.Argument(..., help="Profile ID to display"),
) -> None:
    """Show details of a board profile."""

    from boardmedic.profiles import get_registry

    registry = get_registry()
    profile = registry.get(profile_id)
    if not profile:
        err_console.print(f"[red]Profile '{profile_id}' not found.[/red]")
        raise typer.Exit(2)

    console.print(Panel(
        f"[bold cyan]{profile.display_name}[/bold cyan]",
        title="Board Profile",
        box=box.ROUNDED,
    ))

    info = Table(box=box.SIMPLE, show_header=False)
    info.add_column("Field", style="bold")
    info.add_column("Value")
    info.add_row("ID", profile.id)
    info.add_row("Vendor", profile.vendor or "-")
    info.add_row("PCB", profile.pcb or "-")
    info.add_row("SoC Family", profile.soc_family)
    info.add_row("SoC Model", profile.soc_model or "-")
    info.add_row("CPU Arch", profile.cpu_arch)
    info.add_row("Aliases", ", ".join(profile.aliases) if profile.aliases else "-")
    console.print(info)

    if profile.serial:
        console.print("\n[bold]Serial/UART[/bold]")
        console.print(f"  Voltage: {profile.serial.voltage or '?'}")
        console.print(f"  Baud candidates: {profile.serial.baud_candidates}")

    if profile.storage:
        console.print("\n[bold]Expected Storage[/bold]")
        for s in profile.storage:
            size_info = ""
            if s.min_gib and s.max_gib:
                size_info = f" ({s.min_gib}-{s.max_gib} GiB)"
            console.print(f"  [{s.type.upper()}] {s.label}{size_info}")
            if s.bus_path:
                console.print(f"    Controller: {s.bus_path}")

    if profile.usb_ids:
        console.print("\n[bold]USB IDs[/bold]")
        for u in profile.usb_ids:
            pid_str = f":{u.pid}" if u.pid else ":*"
            console.print(f"  {u.vid}{pid_str} -- {u.description or u.mode or '-'}")

    if profile.recovery_capabilities:
        console.print("\n[bold]Recovery Capabilities[/bold]")
        for r in profile.recovery_capabilities:
            console.print(f"  [+] {r.method}")


@profiles_app.command("validate")
def cmd_profiles_validate() -> None:
    """Validate all board profiles."""
    from boardmedic.profiles import get_registry

    registry = get_registry(reload=True)
    valid, errors = registry.validate_all()

    console.print("\n[bold]Profile Validation[/bold]\n")
    console.print(f"  [green]Valid profiles: {len(valid)}[/green]")
    for pid in valid:
        console.print(f"  [OK] {pid}")

    if errors:
        console.print(f"\n  [red]Invalid profiles: {len(errors)}[/red]")
        for name, err in errors:
            console.print(f"  [X] {name}: {err}")
        raise typer.Exit(2)
    console.print("\n[green]All profiles valid.[/green]")


# ============================================================================
# collect / diagnose commands
# ============================================================================


@app.command("collect")
def cmd_collect(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Board profile ID"),
    fixture: Path | None = typer.Option(None, "--fixture", "-f", help="Path to fixture directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Don't execute destructive commands"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Session output directory"),
) -> None:
    """Collect diagnostic evidence from connected board."""
    console.print(Panel(
        f"[bold cyan]BoardMedic {__version__}[/bold cyan] -- Collecting Evidence",
        box=box.ROUNDED,
    ))

    if fixture:
        console.print(f"[dim]Using fixture: {fixture}[/dim]\n")

    from boardmedic.diagnostics import Diagnostics
    from boardmedic.platform import is_elevated

    diag = Diagnostics(
        dry_run=dry_run,
        fixture_path=fixture,
        profile_id=profile,
        elevated=is_elevated(),
    )

    with console.status("[bold green]Collecting..."):
        session = diag.run()

    _print_session_summary(session)
    _print_findings_summary(session)

    console.print(f"\n[dim]Findings: {len(session.findings)}[/dim]")
    exit_code = 1 if any(f.severity.value in ("error", "critical") for f in session.findings) else 0
    raise typer.Exit(exit_code)


@app.command("diagnose")
def cmd_diagnose(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Board profile ID"),
    fixture: Path | None = typer.Option(None, "--fixture", "-f", help="Path to fixture directory"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    output_dir: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Run full diagnostics and show findings."""
    console.print(Panel(
        f"[bold cyan]BoardMedic {__version__}[/bold cyan] -- Diagnostics",
        box=box.ROUNDED,
    ))

    from boardmedic.diagnostics import Diagnostics
    from boardmedic.platform import is_elevated

    diag = Diagnostics(
        dry_run=dry_run,
        fixture_path=fixture,
        profile_id=profile,
        elevated=is_elevated(),
    )

    with console.status("[bold green]Running diagnostics..."):
        session = diag.run()

    _print_session_summary(session)
    _print_boot_chain(session)
    _print_findings_summary(session)

    exit_code = 1 if any(f.severity.value in ("error", "critical") for f in session.findings) else 0
    raise typer.Exit(exit_code)


# ============================================================================
# report commands
# ============================================================================


@report_app.callback(invoke_without_command=True)
def cmd_report(
    ctx: typer.Context,
    profile: str | None = typer.Option(None, "--profile", "-p"),
    fixture: Path | None = typer.Option(None, "--fixture", "-f"),
    format: str = typer.Option("markdown", "--format", help="Report format: markdown | json"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file"),
    anonymize: bool = typer.Option(False, "--anonymize", help="Anonymize report"),
) -> None:
    """Generate a diagnostic report."""
    if ctx.invoked_subcommand is not None:
        return

    from boardmedic.diagnostics import Diagnostics
    from boardmedic.platform import is_elevated
    from boardmedic.reporting import ReportGenerator

    diag = Diagnostics(
        fixture_path=fixture,
        profile_id=profile,
        elevated=is_elevated(),
    )
    with console.status("[bold green]Running diagnostics for report..."):
        session = diag.run()

    gen = ReportGenerator()
    report = gen.generate(session, format=format, anonymize=anonymize)

    if output:
        output.write_text(report.content, encoding="utf-8")
        console.print(f"[green]Report written to: {output}[/green]")
    else:
        console.print(report.content)


# ============================================================================
# recover commands
# ============================================================================


@recover_app.command("plan")
def cmd_recover_plan(
    profile: str | None = typer.Option(None, "--profile", "-p"),
    fixture: Path | None = typer.Option(None, "--fixture", "-f"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Generate a recovery plan (non-destructive)."""
    console.print(Panel(
        f"[bold cyan]BoardMedic {__version__}[/bold cyan] -- Recovery Planner",
        box=box.ROUNDED,
    ))

    from boardmedic.diagnostics import Diagnostics
    from boardmedic.platform import is_elevated
    from boardmedic.profiles import get_registry
    from boardmedic.recovery.planner import RecoveryPlanner

    diag = Diagnostics(
        dry_run=dry_run,
        fixture_path=fixture,
        profile_id=profile,
        elevated=is_elevated(),
    )
    with console.status("[bold green]Analyzing for recovery plan..."):
        session = diag.run()

    registry = get_registry()
    board_profile = registry.get(profile) if profile else None

    planner = RecoveryPlanner(dry_run=dry_run)
    plan = planner.plan(session, profile=board_profile)
    session.recovery_plan = plan

    console.print(f"\n[bold]Recovery Plan[/bold] -- Status: [cyan]{plan.result_code.value}[/cyan]")
    if dry_run:
        console.print("[yellow](DRY-RUN: No destructive steps will execute)[/yellow]")
    console.print()

    for note in plan.notes:
        console.print(f"[dim][i] {note}[/dim]")
    console.print()

    for step in plan.steps:
        color = "red" if step.destructive else ("yellow" if step.disruptive else "green")
        badge = " [!] DESTRUCTIVE" if step.destructive else (" [*] DISRUPTIVE" if step.disruptive else "")
        console.print(f"[{color}]Step {step.order}:[/{color}] {step.title}{badge}")
        console.print(f"  {step.description[:120]}...")
        if step.skip_reason:
            console.print(f"  [dim]Skip: {step.skip_reason}[/dim]")
        console.print()


@recover_app.command("status")
def cmd_recover_status() -> None:
    """Show current recovery status."""
    console.print("[dim]No active recovery session.[/dim]")


@recover_app.command("wipe")
def cmd_recover_wipe(
    target: str = typer.Option(..., "--target", help="Target block device"),
    destructive: bool = typer.Option(False, "--destructive", help="Required for destructive ops"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    profile: str | None = typer.Option(None, "--profile", "-p"),
) -> None:
    """Wipe a target storage device. DESTRUCTIVE OPERATION."""
    from boardmedic.collectors.storage import StorageProbe
    from boardmedic.core.runner import CommandRunner
    from boardmedic.profiles import get_registry
    from boardmedic.recovery.operations import WipeOperation
    from boardmedic.safety import DestructiveGate, SafetyEngine

    console.print(Panel(
        "[bold red][!] DESTRUCTIVE OPERATION -- WIPE[/bold red]",
        box=box.HEAVY,
    ))

    if not destructive:
        err_console.print("[red]ERROR: --destructive flag required for this operation.[/red]")
        raise typer.Exit(5)

    runner = CommandRunner(dry_run=dry_run)
    storage_probe = StorageProbe(runner)
    devices = storage_probe.probe()
    root_disk = storage_probe.get_root_parent_disk()

    safety = SafetyEngine(root_disk=root_disk)
    safety.classify_all(devices)

    # Find target device
    target_dev = None
    for dev in devices:
        if dev.path == target or dev.name == target:
            target_dev = dev
            break

    if not target_dev:
        err_console.print(f"[red]Target device '{target}' not found.[/red]")
        raise typer.Exit(2)

    registry = get_registry()
    board_profile = registry.get(profile) if profile else None

    decision = safety.verify_target(target_dev, profile=board_profile, all_devices=devices)

    console.print(f"\nTarget: [cyan]{target_dev.path}[/cyan]")
    console.print(f"Size: {target_dev.size_gib:.1f} GiB" if target_dev.size_gib else "Size: ?")
    console.print(f"Removable: {'Yes' if target_dev.removable else 'No'}")
    console.print(f"Safety: {decision.reason}")
    console.print()

    if not decision.approved:
        err_console.print(f"[bold red]SAFETY CHECK FAILED: {decision.reason}[/bold red]")
        raise typer.Exit(5)

    if not yes and not dry_run:
        console.print(
            f"[bold red]WARNING: ALL DATA ON {target} WILL BE PERMANENTLY DESTROYED.[/bold red]"
        )
        confirm = typer.prompt("Type the device path to confirm", default="")
        if confirm != target:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    gate = DestructiveGate(dry_run=dry_run, destructive_flag=destructive, yes_flag=yes)
    wipe_op = WipeOperation(runner, dry_run=dry_run)
    result = wipe_op.wipe_metadata(target, decision, gate)

    if result.value == "DRY_RUN":
        console.print("[yellow]DRY-RUN: Wipe commands generated but not executed.[/yellow]")
    elif result.value == "SUCCESS":
        console.print("[green][OK] Wipe completed.[/green]")
    else:
        err_console.print(f"[red]Wipe failed: {result.value}[/red]")
        raise typer.Exit(6)


@recover_app.command("flash")
def cmd_recover_flash(
    target: str = typer.Option(..., "--target", help="Target block device"),
    image: Path = typer.Option(..., "--image", help="Image file to flash"),
    destructive: bool = typer.Option(False, "--destructive"),
    yes: bool = typer.Option(False, "--yes", "-y"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    profile: str | None = typer.Option(None, "--profile", "-p"),
) -> None:
    """Flash an image to a target device. DESTRUCTIVE OPERATION."""
    from boardmedic.collectors.storage import StorageProbe
    from boardmedic.core.runner import CommandRunner
    from boardmedic.profiles import get_registry
    from boardmedic.recovery.operations import FlashOperation
    from boardmedic.safety import DestructiveGate, SafetyEngine

    console.print(Panel(
        "[bold red][!] DESTRUCTIVE OPERATION -- FLASH[/bold red]",
        box=box.HEAVY,
    ))

    if not destructive:
        err_console.print("[red]ERROR: --destructive flag required.[/red]")
        raise typer.Exit(5)

    runner = CommandRunner(dry_run=dry_run)
    storage_probe = StorageProbe(runner)
    devices = storage_probe.probe()
    root_disk = storage_probe.get_root_parent_disk()

    safety = SafetyEngine(root_disk=root_disk)
    safety.classify_all(devices)

    target_dev = next((d for d in devices if d.path == target or d.name == target), None)
    if not target_dev:
        err_console.print(f"[red]Target device '{target}' not found.[/red]")
        raise typer.Exit(2)

    registry = get_registry()
    board_profile = registry.get(profile) if profile else None
    decision = safety.verify_target(target_dev, profile=board_profile, all_devices=devices)

    if not decision.approved:
        err_console.print(f"[bold red]SAFETY CHECK FAILED: {decision.reason}[/bold red]")
        raise typer.Exit(5)

    gate = DestructiveGate(dry_run=dry_run, destructive_flag=destructive, yes_flag=yes)
    flash_op = FlashOperation(runner, dry_run=dry_run)
    result = flash_op.flash(target, image, decision, gate)

    if result.value == "DRY_RUN":
        console.print("[yellow]DRY-RUN: Flash commands generated but not executed.[/yellow]")
    elif result.value == "SUCCESS":
        console.print("[green][OK] Flash completed.[/green]")
    else:
        err_console.print(f"[red]Flash failed: {result.value}[/red]")
        raise typer.Exit(6)


# ============================================================================
# session commands
# ============================================================================


@session_app.command("list")
def cmd_session_list(
    base: Path = typer.Option(Path("boardmedic-sessions"), "--base"),
) -> None:
    """List saved diagnostic sessions."""
    if not base.exists():
        console.print("[dim]No sessions found.[/dim]")
        return
    sessions = sorted(base.iterdir(), reverse=True)
    console.print(f"\n[bold]Sessions[/bold] in {base}/\n")
    for s in sessions:
        if s.is_dir():
            console.print(f"  [DIR] {s.name}")


@session_app.command("show")
def cmd_session_show(
    session_id: str = typer.Argument(...),
    base: Path = typer.Option(Path("boardmedic-sessions"), "--base"),
) -> None:
    """Show a saved session."""
    session_dir = base / session_id
    session_file = session_dir / "session.json"
    if not session_file.exists():
        err_console.print(f"[red]Session '{session_id}' not found.[/red]")
        raise typer.Exit(2)
    data = json.loads(session_file.read_text())
    console.print_json(json.dumps(data))


# ============================================================================
# Helper functions
# ============================================================================


def _print_session_summary(session) -> None:
    """Print a compact session summary."""
    console.print()
    console.print("[bold]Detected[/bold]:")
    console.print(f"  USB devices:      {len(session.usb_devices)}")
    console.print(f"  Rockchip devices: {len(session.rockchip_devices)}")
    console.print(f"  Serial ports:     {len(session.serial_ports)}")
    console.print(f"  Network ifaces:   {len(session.network_interfaces)}")
    console.print(f"  Storage devices:  {len(session.storage_devices)}")
    if session.mmc_state:
        console.print(f"  MMC state:        [bold]{session.mmc_state.value}[/bold]")


def _print_boot_chain(session) -> None:
    """Print boot chain table."""
    if not session.boot_chain:
        return

    from boardmedic.models import StageStatus
    console.print()
    console.print("[bold]Boot Chain[/bold]:")
    labels = {
        StageStatus.PASS: "[green][OK] PASS[/green]",
        StageStatus.LIKELY_PASS: "[yellow][INFO] LIKELY PASS[/yellow]",
        StageStatus.UNKNOWN: "[dim][o] UNKNOWN[/dim]",
        StageStatus.LIKELY_FAIL: "[orange1][WARN] LIKELY FAIL[/orange1]",
        StageStatus.FAIL: "[red][X] FAIL[/red]",
        StageStatus.NOT_APPLICABLE: "[dim]-- N/A[/dim]",
    }
    for stage in session.boot_chain.stages:
        label = labels.get(stage.status, stage.status.value)
        console.print(f"  {stage.stage.value.upper():<16} {label}")


def _print_findings_summary(session) -> None:
    """Print findings summary."""
    if not session.findings:
        console.print("\n[green]No diagnostic findings.[/green]")
        return

    console.print(f"\n[bold]Findings[/bold] ({len(session.findings)}):")
    for f in session.findings:
        sev_colors = {
            "critical": "bold red",
            "error": "red",
            "warning": "yellow",
            "info": "blue",
        }
        color = sev_colors.get(f.severity.value, "white")
        console.print(
            f"  [{color}]{f.severity.value.upper()}[/{color}] "
            f"[{f.confidence.value}] {f.id}: {f.summary}"
        )
