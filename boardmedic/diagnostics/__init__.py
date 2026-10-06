"""Main diagnostics orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from boardmedic.collectors.mmc import MMCDiagnostics
from boardmedic.collectors.storage import StorageProbe
from boardmedic.core.runner import CommandRunner
from boardmedic.models import DiagnosticSession, MMCState, SafetyStatus
from boardmedic.probes.adb import probe_adb, probe_fastboot
from boardmedic.probes.network import NetworkProbe
from boardmedic.probes.serial import SerialProbe
from boardmedic.probes.usb import USBProbe
from boardmedic.profiles import BoardProfile, get_registry
from boardmedic.rules import BootChainAnalyzer, run_all_rules
from boardmedic.safety import SafetyEngine
from boardmedic.utils.fixtures import FixtureData


class Diagnostics:
    """
    Top-level diagnostics orchestrator.

    Coordinates all probes, collectors, and rule engines
    into a cohesive DiagnosticSession.
    """

    def __init__(
        self,
        dry_run: bool = False,
        fixture_path: Path | None = None,
        profile_id: str | None = None,
        elevated: bool = False,
    ) -> None:
        self.dry_run = dry_run
        self.fixture_path = fixture_path
        self.profile_id = profile_id
        self.elevated = elevated
        self.runner = CommandRunner(dry_run=dry_run)

    def _load_fixture(self) -> FixtureData | None:
        if self.fixture_path is None:
            return None
        from boardmedic.utils.fixtures import FixtureData
        return FixtureData.load(self.fixture_path)

    def _get_profile(self) -> BoardProfile | None:
        if not self.profile_id:
            return None
        registry = get_registry()
        return registry.get(self.profile_id)

    def run(self) -> DiagnosticSession:
        """Execute full diagnostics and return populated session."""
        from boardmedic.core.session import Session

        session_mgr = Session(
            profile_id=self.profile_id,
            fixture_path=self.fixture_path,
            dry_run=self.dry_run,
            elevated=self.elevated,
        )
        session = session_mgr.data

        fixture = self._load_fixture()
        profile = self._get_profile()

        # ---- USB ----
        usb_probe = USBProbe(self.runner)
        fixture_usb = fixture.usb_text if fixture else None
        usb_devices, rk_devices = usb_probe.probe(fixture_text=fixture_usb)
        session.usb_devices = usb_devices
        session.rockchip_devices = rk_devices
        if fixture_usb:
            session_mgr.save_raw("usb.txt", fixture_usb)
        elif usb_devices:
            raw_usb = "\n".join(str(d.model_dump()) for d in usb_devices)
            session_mgr.save_raw("usb.txt", raw_usb)

        # ---- Serial ----
        serial_probe = SerialProbe(self.runner)
        serial_ports = serial_probe.enumerate()
        session.serial_ports = serial_ports

        # ---- Network ----
        net_probe = NetworkProbe(self.runner)
        fixture_net = fixture.ip_addr_text if fixture else None
        ifaces, _neighbors = net_probe.probe(fixture_ip_addr=fixture_net)
        session.network_interfaces = ifaces
        if fixture_net:
            session_mgr.save_raw("ip_addr.txt", fixture_net)

        # ---- ADB / Fastboot ----
        probe_adb(self.runner)
        probe_fastboot(self.runner)

        # ---- Storage ----
        storage_probe = StorageProbe(self.runner)
        fixture_lsblk = fixture.lsblk_json if fixture else None
        storage_devices = storage_probe.probe(fixture_lsblk=fixture_lsblk)
        if fixture_lsblk:
            session_mgr.save_raw("lsblk.json", fixture_lsblk)

        # Safety classification
        root_disk = storage_probe.get_root_parent_disk()
        fixture_root = fixture.root_disk if fixture else None
        effective_root = fixture_root or root_disk
        safety_engine = SafetyEngine(root_disk=effective_root)
        safety_engine.classify_all(storage_devices)
        session.storage_devices = storage_devices

        # ---- MMC Diagnostics ----
        mmc_diag = MMCDiagnostics(self.runner)
        fixture_dmesg = fixture.dmesg_text if fixture else None
        fixture_sysfs = fixture.sysfs_data if fixture else None
        fixture_block_devices = fixture.block_devices if fixture else None

        dmesg_text = mmc_diag.collect_dmesg(fixture_dmesg=fixture_dmesg)
        if dmesg_text:
            session_mgr.save_raw("dmesg.txt", dmesg_text)
            session.raw_evidence["dmesg.txt"] = dmesg_text

        mmc_hosts = mmc_diag.collect_hosts(
            fixture_dmesg=fixture_dmesg,
            fixture_sysfs=fixture_sysfs,
        )

        # Find target controller from profile
        target_controller = None
        if profile and profile.known_mmc_controllers:
            target_controller = profile.known_mmc_controllers[0]

        dmesg_matches = mmc_diag.analyze_dmesg(dmesg_text, target_controller=target_controller)

        # Block devices - from storage or fixture
        block_devices: list[str] = []
        if fixture_block_devices:
            block_devices = fixture_block_devices
        else:
            for dev in storage_devices:
                if dev.mmc_host or dev.storage_class.value == "emmc_internal":
                    if dev.path:
                        block_devices.append(dev.path)

        mmc_state = mmc_diag.classify_mmc_state(mmc_hosts, dmesg_matches, block_devices)
        session.mmc_state = mmc_state

        # ---- Run diagnostic rules ----
        findings = run_all_rules(session)
        session.findings = findings

        # ---- Boot chain analysis ----
        analyzer = BootChainAnalyzer()
        session.boot_chain = analyzer.analyze(session)

        # Copy runner history
        session.commands = self.runner.history

        return session
