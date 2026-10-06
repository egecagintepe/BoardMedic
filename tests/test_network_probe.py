"""Tests for network probe parsing."""

from __future__ import annotations

from boardmedic.probes.network import parse_network_from_fixture

IP_ADDR_OUTPUT = """\
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff
    inet 192.168.1.100/24 brd 192.168.1.255 scope global dynamic eth0
       valid_lft 86388sec preferred_lft 86388sec
    inet6 fe80::a8bb:ccff:fedd:eeff/64 scope link
       valid_lft forever preferred_lft forever
3: wlan0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN group default qlen 1000
    link/ether 11:22:33:44:55:66 brd ff:ff:ff:ff:ff:ff
"""


def test_parse_interface_names():
    ifaces = parse_network_from_fixture(IP_ADDR_OUTPUT)
    names = {i.name for i in ifaces}
    assert "lo" in names
    assert "eth0" in names
    assert "wlan0" in names


def test_parse_mtu():
    ifaces = parse_network_from_fixture(IP_ADDR_OUTPUT)
    eth0 = next(i for i in ifaces if i.name == "eth0")
    assert eth0.mtu == 1500


def test_parse_mac():
    ifaces = parse_network_from_fixture(IP_ADDR_OUTPUT)
    eth0 = next(i for i in ifaces if i.name == "eth0")
    assert eth0.mac is not None
    assert ":" in eth0.mac


def test_parse_ipv4():
    ifaces = parse_network_from_fixture(IP_ADDR_OUTPUT)
    eth0 = next(i for i in ifaces if i.name == "eth0")
    assert len(eth0.ipv4) > 0
    assert any("192.168" in ip for ip in eth0.ipv4)


def test_parse_ipv6():
    ifaces = parse_network_from_fixture(IP_ADDR_OUTPUT)
    eth0 = next(i for i in ifaces if i.name == "eth0")
    assert len(eth0.ipv6) > 0


def test_interface_state_up():
    ifaces = parse_network_from_fixture(IP_ADDR_OUTPUT)
    eth0 = next(i for i in ifaces if i.name == "eth0")
    assert eth0.state == "up"


def test_interface_state_down():
    ifaces = parse_network_from_fixture(IP_ADDR_OUTPUT)
    wlan0 = next(i for i in ifaces if i.name == "wlan0")
    assert wlan0.state == "down"


def test_empty_input():
    ifaces = parse_network_from_fixture("")
    assert ifaces == []
