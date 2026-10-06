"""Fixture loading utilities."""

from __future__ import annotations

from pathlib import Path


class FixtureData:
    """
    Loaded fixture data for offline diagnostics.

    Fixtures are directories containing realistic simulated output files.
    """

    def __init__(self) -> None:
        self.usb_text: str | None = None
        self.lsblk_json: str | None = None
        self.dmesg_text: str | None = None
        self.ip_addr_text: str | None = None
        self.sysfs_data: dict[str, str] | None = None
        self.block_devices: list[str] | None = None
        self.root_disk: str | None = None
        self.profile_id: str | None = None
        self.description: str | None = None

    @classmethod
    def load(cls, path: Path) -> FixtureData:
        """Load fixture data from a directory."""
        fixture = cls()

        if not path.exists():
            return fixture

        # Read fixture files
        def read_file(name: str) -> str | None:
            p = path / name
            if p.exists():
                return p.read_text(encoding="utf-8", errors="replace")
            return None

        fixture.usb_text = read_file("usb.txt")
        fixture.lsblk_json = read_file("lsblk.json")
        fixture.dmesg_text = read_file("dmesg.txt")
        fixture.ip_addr_text = read_file("ip_addr.txt")

        # Read fixture metadata
        meta_path = path / "fixture.yaml"
        if meta_path.exists():
            try:
                import yaml
                meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
                if isinstance(meta, dict):
                    fixture.profile_id = meta.get("profile_id")
                    fixture.description = meta.get("description")
                    fixture.root_disk = meta.get("root_disk")
                    fixture.block_devices = meta.get("block_devices")
            except Exception:
                pass

        # Load sysfs data from mmc_sysfs/ directory
        sysfs_dir = path / "mmc_sysfs"
        if sysfs_dir.exists():
            sysfs_data: dict[str, str] = {}
            for f in sysfs_dir.rglob("*"):
                if f.is_file():
                    rel = str(f.relative_to(sysfs_dir))
                    try:
                        sysfs_data[rel] = f.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        pass
            if sysfs_data:
                fixture.sysfs_data = sysfs_data

        return fixture
