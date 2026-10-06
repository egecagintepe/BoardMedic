"""Tests for USB probe - parsing and Rockchip detection."""

from __future__ import annotations

from boardmedic.core.runner import CommandRunner
from boardmedic.models import USBDevice
from boardmedic.probes.usb import (
    ROCKCHIP_VID,
    USBProbe,
    identify_rockchip_devices,
    probe_usb_from_fixture,
)

LSUSB_SAMPLE = """\
Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
Bus 001 Device 002: ID 0bda:8153 Realtek Semiconductor Corp. USB 10/100/1000 LAN
Bus 001 Device 003: ID 2207:350a Fuzhou Rockchip Electronics Co., Ltd. RK3568 MaskROM
"""

LSUSB_LOADER = """\
Bus 001 Device 004: ID 2207:350b Fuzhou Rockchip Electronics Co., Ltd. RK3568 Loader
"""


def test_parse_lsusb_basic():
    devices = probe_usb_from_fixture(LSUSB_SAMPLE)
    assert len(devices) == 4


def test_parse_lsusb_vids():
    devices = probe_usb_from_fixture(LSUSB_SAMPLE)
    vids = {d.vid for d in devices}
    assert "1d6b" in vids
    assert "0bda" in vids
    assert "2207" in vids


def test_parse_lsusb_description():
    devices = probe_usb_from_fixture(LSUSB_SAMPLE)
    rk = next(d for d in devices if d.vid == "2207")
    assert "Rockchip" in rk.description or "rockchip" in rk.description.lower()


def test_rockchip_detection_maskrom():
    devices = probe_usb_from_fixture(LSUSB_SAMPLE)
    rk_devices = identify_rockchip_devices(devices)
    assert len(rk_devices) == 1
    assert rk_devices[0].mode == "maskrom"
    assert rk_devices[0].usb.vid == "2207"
    assert rk_devices[0].usb.pid == "350a"


def test_rockchip_detection_loader():
    devices = probe_usb_from_fixture(LSUSB_LOADER)
    rk_devices = identify_rockchip_devices(devices)
    assert len(rk_devices) == 1
    assert rk_devices[0].mode == "loader"
    assert rk_devices[0].usb.pid == "350b"


def test_no_rockchip_in_normal_usb():
    normal_usb = "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub\n"
    devices = probe_usb_from_fixture(normal_usb)
    rk_devices = identify_rockchip_devices(devices)
    assert len(rk_devices) == 0


def test_empty_usb_output():
    devices = probe_usb_from_fixture("")
    assert devices == []


def test_usb_device_is_rockchip_property():
    dev = USBDevice(vid="2207", pid="350a")
    assert dev.is_rockchip is True

    dev2 = USBDevice(vid="0bda", pid="8153")
    assert dev2.is_rockchip is False


def test_usb_probe_with_fixture():
    runner = CommandRunner()
    probe = USBProbe(runner)
    devices, rk_devices = probe.probe(fixture_text=LSUSB_SAMPLE)
    assert len(devices) == 4
    assert len(rk_devices) == 1
    assert rk_devices[0].mode == "maskrom"


def test_rockchip_vid_constant():
    assert ROCKCHIP_VID == "2207"
