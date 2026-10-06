# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-06

### Added
- Complete Typer CLI with commands: `doctor`, `detect`, `probe`, `profiles`, `collect`, `diagnose`, `report`, `recover`, and `session`.
- Cross-platform hardware probes for USB (Linux `lsusb` and Windows `Get-PnpDevice`), Serial/UART (`pyserial`), Network (`ip` / PowerShell), and host flashing tools (`adb`, `fastboot`, `rkdeveloptool`, `upgrade_tool`).
- Rockchip SoC detection table covering RK3568, RK3588, RK3399, RK3328, RK3288, and RK3128 in MaskROM and Loader modes.
- Storage enumeration and Safety Engine protecting system disks, current root (`/`), boot/EFI partitions, and recovery SD media.
- Destructive operations gate (`DestructiveGate`) requiring `--destructive` flag, target re-verification, and interactive confirmation.
- MMC diagnostics engine analyzing Linux kernel `dmesg` OCR registers, busy loops, and initialization states.
- Declarative rule engine evaluating eMMC health, stuck states, BootROM recovery, and boot chain progression.
- Risk-ordered recovery planner prioritizing non-destructive actions, driver reprobing, and bootloader recovery over destructive erasing.
- Comprehensive report generation supporting Markdown and structured JSON with automated IP/MAC/path anonymization.
- Board profile engine with full production support for Dingchang DC-A568B / RK3568 industrial IoT board and customizable `_template.yaml`.
- Realistic offline diagnostic fixtures for DC-A568B eMMC failure, Rockchip MaskROM, healthy Linux boards, and dangerous host disk protection.
- Complete automated test suite with 137 unit and integration tests passing across platforms.
- Architecture, safety, recovery, profiles, and case study documentation.
