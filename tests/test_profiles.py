"""Tests for board profile schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from boardmedic.profiles import BoardProfile, ProfileRegistry

# ---------------------------------------------------------------------------
# Valid profile construction
# ---------------------------------------------------------------------------

VALID_PROFILE_DATA = {
    "id": "test-board",
    "display_name": "Test Board",
    "soc_family": "Rockchip RK3568",
    "cpu_arch": "arm64",
}


def test_valid_profile_loads():
    profile = BoardProfile.model_validate(VALID_PROFILE_DATA)
    assert profile.id == "test-board"
    assert profile.display_name == "Test Board"
    assert profile.soc_family == "Rockchip RK3568"


def test_profile_defaults():
    profile = BoardProfile.model_validate(VALID_PROFILE_DATA)
    assert profile.aliases == []
    assert profile.usb_ids == []
    assert profile.storage == []
    assert profile.cpu_arch == "arm64"


def test_profile_with_usb_ids():
    data = {**VALID_PROFILE_DATA, "usb_ids": [
        {"vid": "2207", "pid": "350a", "description": "RK3568 MaskROM", "mode": "maskrom"}
    ]}
    profile = BoardProfile.model_validate(data)
    assert len(profile.usb_ids) == 1
    assert profile.usb_ids[0].vid == "2207"
    assert profile.usb_ids[0].pid == "350a"


# ---------------------------------------------------------------------------
# Invalid profile rejection
# ---------------------------------------------------------------------------

def test_invalid_id_uppercase():
    data = {**VALID_PROFILE_DATA, "id": "TEST-BOARD"}
    with pytest.raises(ValidationError):
        BoardProfile.model_validate(data)


def test_invalid_id_leading_hyphen():
    data = {**VALID_PROFILE_DATA, "id": "-test-board"}
    with pytest.raises(ValidationError):
        BoardProfile.model_validate(data)


def test_invalid_id_trailing_hyphen():
    data = {**VALID_PROFILE_DATA, "id": "test-board-"}
    with pytest.raises(ValidationError):
        BoardProfile.model_validate(data)


def test_invalid_id_spaces():
    data = {**VALID_PROFILE_DATA, "id": "test board"}
    with pytest.raises(ValidationError):
        BoardProfile.model_validate(data)


def test_empty_soc_family():
    data = {**VALID_PROFILE_DATA, "soc_family": ""}
    with pytest.raises(ValidationError):
        BoardProfile.model_validate(data)


def test_missing_display_name():
    data = {"id": "test-board", "soc_family": "RK3568", "cpu_arch": "arm64"}
    with pytest.raises(ValidationError):
        BoardProfile.model_validate(data)


def test_missing_required_id():
    data = {"display_name": "Test", "soc_family": "RK3568", "cpu_arch": "arm64"}
    with pytest.raises(ValidationError):
        BoardProfile.model_validate(data)


def test_invalid_usb_vid_too_short():
    data = {**VALID_PROFILE_DATA, "usb_ids": [{"vid": "220", "pid": "350a"}]}
    with pytest.raises(ValidationError):
        BoardProfile.model_validate(data)


def test_invalid_usb_pid_not_hex():
    data = {**VALID_PROFILE_DATA, "usb_ids": [{"vid": "2207", "pid": "ZZZZ"}]}
    with pytest.raises(ValidationError):
        BoardProfile.model_validate(data)


def test_extra_fields_rejected():
    data = {**VALID_PROFILE_DATA, "unknown_field": "value"}
    with pytest.raises(ValidationError):
        BoardProfile.model_validate(data)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_registry_load_from_dict():
    registry = ProfileRegistry()
    profile = registry.load_from_dict(VALID_PROFILE_DATA)
    assert profile.id == "test-board"
    assert registry.get("test-board") is not None


def test_registry_get_by_alias():
    registry = ProfileRegistry()
    data = {**VALID_PROFILE_DATA, "aliases": ["my-alias", "another-alias"]}
    registry.load_from_dict(data)
    assert registry.get("my-alias") is not None
    assert registry.get("another-alias") is not None
    assert registry.get("nonexistent") is None


def test_registry_invalid_profile_error():
    registry = ProfileRegistry()
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        bad_file = Path(tmpdir) / "bad-profile.yaml"
        bad_file.write_text("id: BAD ID\ndisplay_name: bad\nsoc_family: test\ncpu_arch: arm64\n")
        registry.load_file(bad_file)
        assert registry.has_errors()
        assert "bad-profile.yaml" in registry.errors()


def test_registry_skips_template():
    """Files starting with _ should be skipped."""
    registry = ProfileRegistry()
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        tpl = Path(tmpdir) / "_template.yaml"
        tpl.write_text("id: template\ndisplay_name: template\nsoc_family: test\ncpu_arch: arm64\n")
        registry.load_directory(Path(tmpdir))
        assert registry.get("template") is None


# ---------------------------------------------------------------------------
# DC-A568B profile loading
# ---------------------------------------------------------------------------

def test_dc_a568b_profile_loads():
    """The actual DC-A568B profile must load without errors."""
    from boardmedic.profiles import get_registry
    registry = get_registry(reload=True)
    profile = registry.get("dc-a568b")
    assert profile is not None, "dc-a568b profile must be loadable"


def test_dc_a568b_profile_details():
    from boardmedic.profiles import get_registry
    registry = get_registry(reload=True)
    profile = registry.get("dc-a568b")
    assert profile.soc_family == "Rockchip RK3568"
    assert "dc_a568" in profile.aliases or "ztl-a568" in profile.aliases
    # Must have eMMC expectation
    emmc = [s for s in profile.storage if s.type == "emmc"]
    assert emmc, "DC-A568B profile must define eMMC storage expectation"
    assert emmc[0].min_gib <= 30.0 <= emmc[0].max_gib
    assert emmc[0].removable is False


def test_dc_a568b_rockchip_usb_ids():
    from boardmedic.profiles import get_registry
    registry = get_registry(reload=True)
    profile = registry.get("dc-a568b")
    vid_pids = {(u.vid, u.pid) for u in profile.usb_ids}
    assert ("2207", "350a") in vid_pids  # MaskROM


def test_dc_a568b_serial_config():
    from boardmedic.profiles import get_registry
    registry = get_registry(reload=True)
    profile = registry.get("dc-a568b")
    assert profile.serial is not None
    assert 1500000 in profile.serial.baud_candidates


def test_dc_a568b_known_mmc_controller():
    from boardmedic.profiles import get_registry
    registry = get_registry(reload=True)
    profile = registry.get("dc-a568b")
    assert "fe310000.mmc" in profile.known_mmc_controllers
