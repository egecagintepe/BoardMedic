"""Network detection probe."""

from __future__ import annotations

import json
import re
import sys

from boardmedic.core.runner import CommandRunner
from boardmedic.models import NetworkInterface, NetworkNeighbor

# ---------------------------------------------------------------------------
# Linux network probes
# ---------------------------------------------------------------------------


def _parse_ip_addr(output: str) -> list[NetworkInterface]:
    """Parse 'ip addr' output into NetworkInterface objects."""
    interfaces: list[NetworkInterface] = []
    current: dict | None = None

    for line in output.splitlines():
        # Interface line: "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ..."
        m = re.match(r"^\d+:\s+(\S+):\s+<([^>]*)>.*mtu\s+(\d+)", line)
        if m:
            if current:
                interfaces.append(_build_iface(current))
            flags = m.group(2)
            current = {
                "name": m.group(1).rstrip(":"),
                "mtu": int(m.group(3)),
                "flags": flags,
                "state": "up" if "UP" in flags.upper() and "LOWER_UP" in flags.upper() else "down",
                "mac": None,
                "ipv4": [],
                "ipv6": [],
            }
        if current is None:
            continue
        # MAC: "    link/ether aa:bb:cc:dd:ee:ff ..."
        m2 = re.match(r"\s+link/ether\s+([0-9a-fA-F:]+)", line)
        if m2:
            current["mac"] = m2.group(1)
        # IPv4: "    inet 192.168.1.1/24 ..."
        m3 = re.match(r"\s+inet\s+([\d.]+/\d+)", line)
        if m3:
            current["ipv4"].append(m3.group(1))
        # IPv6: "    inet6 fe80::1/64 ..."
        m4 = re.match(r"\s+inet6\s+([0-9a-fA-F:]+/\d+)", line)
        if m4:
            current["ipv6"].append(m4.group(1))

    if current:
        interfaces.append(_build_iface(current))
    return interfaces


def _build_iface(d: dict) -> NetworkInterface:
    return NetworkInterface(
        name=d["name"],
        state=d.get("state", "unknown"),
        mac=d.get("mac"),
        ipv4=d.get("ipv4", []),
        ipv6=d.get("ipv6", []),
        mtu=d.get("mtu"),
    )


def _parse_ip_neigh(output: str) -> list[NetworkNeighbor]:
    """Parse 'ip neigh' output."""
    neighbors: list[NetworkNeighbor] = []
    for line in output.splitlines():
        # "192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE"
        parts = line.split()
        if len(parts) >= 2:
            ip = parts[0]
            iface = None
            mac = None
            state = None
            for i, p in enumerate(parts):
                if p == "dev" and i + 1 < len(parts):
                    iface = parts[i + 1]
                elif p == "lladdr" and i + 1 < len(parts):
                    mac = parts[i + 1]
                elif p in ("REACHABLE", "STALE", "DELAY", "PROBE", "FAILED", "NOARP", "PERMANENT"):
                    state = p.lower()
            neighbors.append(NetworkNeighbor(ip=ip, mac=mac, interface=iface, state=state))
    return neighbors


def probe_network_linux(runner: CommandRunner) -> tuple[list[NetworkInterface], list[NetworkNeighbor]]:
    """Probe network state on Linux."""
    ifaces: list[NetworkInterface] = []
    neighbors: list[NetworkNeighbor] = []

    r = runner.run(["ip", "addr"], timeout=10, tool_name="ip")
    if r.exit_code == 0 and r.stdout:
        ifaces = _parse_ip_addr(r.stdout)

    r2 = runner.run(["ip", "neigh"], timeout=10, tool_name="ip")
    if r2.exit_code == 0 and r2.stdout:
        neighbors = _parse_ip_neigh(r2.stdout)

    return ifaces, neighbors


# ---------------------------------------------------------------------------
# Windows network probes
# ---------------------------------------------------------------------------


def probe_network_windows(runner: CommandRunner) -> tuple[list[NetworkInterface], list[NetworkNeighbor]]:
    """Probe network state on Windows using PowerShell."""
    script = (
        "Get-NetIPAddress | "
        "Select-Object InterfaceAlias, IPAddress, PrefixLength, AddressFamily | "
        "ConvertTo-Json -Depth 3"
    )
    result = runner.powershell(script, timeout=15, tool_name="Get-NetIPAddress")
    ifaces: list[NetworkInterface] = []
    if result.exit_code == 0 and result.stdout:
        try:
            raw = json.loads(result.stdout.strip())
            if isinstance(raw, dict):
                raw = [raw]
            # Group by alias
            by_alias: dict[str, dict] = {}
            for entry in raw:
                alias = entry.get("InterfaceAlias", "unknown")
                if alias not in by_alias:
                    by_alias[alias] = {"name": alias, "ipv4": [], "ipv6": []}
                af = entry.get("AddressFamily", 0)
                ip = entry.get("IPAddress", "")
                prefix = entry.get("PrefixLength", "")
                addr = f"{ip}/{prefix}"
                if af == 2:  # IPv4
                    by_alias[alias]["ipv4"].append(addr)
                elif af == 23:  # IPv6
                    by_alias[alias]["ipv6"].append(addr)
            for _alias, data in by_alias.items():
                ifaces.append(NetworkInterface(
                    name=data["name"],
                    state="unknown",
                    ipv4=data["ipv4"],
                    ipv6=data["ipv6"],
                ))
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return ifaces, []


# ---------------------------------------------------------------------------
# Fixture parsing
# ---------------------------------------------------------------------------


def parse_network_from_fixture(ip_addr_text: str) -> list[NetworkInterface]:
    return _parse_ip_addr(ip_addr_text)


# ---------------------------------------------------------------------------
# Main probe dispatcher
# ---------------------------------------------------------------------------


class NetworkProbe:
    """Cross-platform network probe."""

    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def probe(
        self, fixture_ip_addr: str | None = None
    ) -> tuple[list[NetworkInterface], list[NetworkNeighbor]]:
        if fixture_ip_addr is not None:
            return parse_network_from_fixture(fixture_ip_addr), []
        if sys.platform.startswith("linux"):
            return probe_network_linux(self.runner)
        if sys.platform.startswith("win"):
            return probe_network_windows(self.runner)
        return [], []
