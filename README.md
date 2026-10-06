# BoardMedic

**Cross-platform embedded board diagnostics and recovery toolkit.**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://github.com/boardmedic/boardmedic/actions/workflows/ci.yml/badge.svg)](https://github.com/boardmedic/boardmedic/actions)

---

## What is BoardMedic?

BoardMedic is a reusable, cross-platform toolkit for diagnosing and recovering embedded Linux/Android boards. It was born from a real RK3568 industrial board recovery case, but is designed to be board-agnostic.

It answers:

- **WHAT DEVICE IS CONNECTED?**
- **WHAT COMMUNICATION PATHS ARE AVAILABLE?** (USB, Serial, Network, ADB, SSH)
- **WHAT PARTS OF THE BOOT CHAIN ARE WORKING?**
- **WHAT STORAGE DEVICES EXIST AND ARE THEY SAFE TO TOUCH?**
- **WHAT FAILED AND WHAT EVIDENCE SUPPORTS THAT?**
- **WHAT RECOVERY OPTIONS EXIST?**
- **WHAT WOULD BE DESTRUCTIVE AND EXACTLY WHAT WOULD IT TOUCH?**

## What BoardMedic is NOT

- It is NOT a simple one-board flashing script
- It is NOT a vendor firmware tool
- It does NOT require hardware to be connected (fixture mode)
- It does NOT phone home or collect telemetry
- It does NOT run blind destructive commands

## ⚠ Safety Warning

BoardMedic contains a recovery subsystem that can generate destructive commands (wipe, flash). These operations require:

1. `--destructive` flag explicitly passed
2. Explicit `--target` device path
3. Safety verification that target is NOT the host OS disk, root partition, or recovery media
4. User confirmation (or `--yes`)

**The tool will never erase your host PC disk, current root filesystem, or recovery media.** Safety checks cannot be bypassed.

---

## Installation

```bash
pip install boardmedic
```

Or from source:

```bash
git clone https://github.com/boardmedic/boardmedic
cd boardmedic
pip install -e ".[dev]"
```

**Requirements:** Python 3.11+, Windows 10/11 or Ubuntu/Debian Linux

**Optional:** `pyserial` (serial port capture), `pyusb` (USB enumeration)

---

## Quick Start

```bash
# Check your host environment
boardmedic doctor

# List available board profiles
boardmedic profiles list

# Run full diagnostics using a fixture (no hardware needed)
boardmedic diagnose --profile dc-a568b --fixture fixtures/dc_a568b/emmc_stuck_not_ready

# Generate a report
boardmedic report --profile dc-a568b --fixture fixtures/dc_a568b/emmc_stuck_not_ready

# Generate a recovery plan
boardmedic recover plan --profile dc-a568b --fixture fixtures/dc_a568b/emmc_stuck_not_ready
```

---

## Typical Workflow

```bash
# 1. Check host environment
boardmedic doctor

# 2. List profiles
boardmedic profiles list

# 3. Detect what's connected
boardmedic detect usb
boardmedic detect serial
boardmedic detect network
boardmedic detect storage

# 4. Collect full evidence
boardmedic collect --profile dc-a568b

# 5. Run diagnostics
boardmedic diagnose --profile dc-a568b

# 6. Generate a report
boardmedic report --format markdown --output report.md

# 7. Get a recovery plan
boardmedic recover plan --profile dc-a568b
```

---

## Board Profiles

Profiles live in `profiles/` as YAML files. Each profile encodes:

- Board identity and SoC
- Expected USB VID/PID (Rockchip, ADB, Fastboot)
- Serial/UART settings
- Expected storage (eMMC size, controller path, removable flag)
- Known failure signatures (dmesg patterns)
- Recovery capabilities

### Supported Profiles

| ID | Board | SoC |
|----|-------|-----|
| `dc-a568b` | DC-A568B / ZTL-A568 | Rockchip RK3568 |

### View a Profile

```bash
boardmedic profiles show dc-a568b
boardmedic profiles validate
```

---

## Detection

```bash
boardmedic detect usb       # USB including Rockchip MaskROM/Loader
boardmedic detect serial    # Serial/UART ports
boardmedic detect network   # Network interfaces
boardmedic detect storage   # Storage devices with safety classification
```

---

## Probes

```bash
boardmedic probe usb
boardmedic probe serial --port COM5 --baud 1500000 --seconds 15
boardmedic probe adb
boardmedic probe fastboot
boardmedic probe rockchip
boardmedic probe storage
boardmedic probe mmc
boardmedic probe ssh 192.168.1.100 --user root
```

---

## Diagnostics

```bash
boardmedic diagnose --profile dc-a568b
boardmedic diagnose --profile dc-a568b --fixture fixtures/dc_a568b/emmc_stuck_not_ready
```

Output includes:
- Boot chain analysis (POWER → BOOTROM → BOOT_MEDIA → KERNEL → ROOTFS → NETWORK)
- Diagnostic findings with severity, confidence, evidence chain
- Evidence classified as: OBSERVED / DERIVED / INFERRED / HYPOTHESIS

---

## Recovery Planning

```bash
boardmedic recover plan --profile dc-a568b
boardmedic recover plan --profile dc-a568b --dry-run
```

Recovery plan is evidence-based and ordered: non-destructive steps first, destructive steps clearly marked and guarded.

---

## Destructive Recovery Safeguards

Destructive operations require ALL of:

```bash
boardmedic recover wipe \
  --target /dev/mmcblk1 \
  --destructive \         # Must explicitly pass this
  --yes                   # Skip confirmation
```

Before any destructive action, the safety engine checks:
- Target is NOT the current root filesystem device
- Target is NOT the host OS disk
- Target is NOT the recovery media
- Target passes profile size/controller verification
- All mount points are safe

```bash
# Always test with --dry-run first
boardmedic recover wipe --target /dev/mmcblk1 --destructive --dry-run
```

---

## Reports

```bash
boardmedic report                           # Markdown to stdout
boardmedic report --format json             # JSON to stdout
boardmedic report --output report.md        # Write to file
boardmedic report --anonymize               # Redact IPs, MACs, usernames
```

---

## DC-A568B Example

The DC-A568B with RK3568 SoC was the motivating real-world case. See [docs/cases/dc-a568b-emmc-not-ready.md](docs/cases/dc-a568b-emmc-not-ready.md) for the full case study.

```bash
# Run with the provided eMMC-stuck-not-ready fixture
boardmedic diagnose \
  --profile dc-a568b \
  --fixture fixtures/dc_a568b/emmc_stuck_not_ready

# Expected output includes:
# EMMC_INIT_NOT_READY [ERROR, HIGH confidence]
# Boot chain: INTERNAL_EMMC FAIL
# Recovery plan with 10 ordered steps
```

---

## Adding a New Board Profile

1. Copy the template:
   ```bash
   cp profiles/_template.yaml profiles/my-board.yaml
   ```

2. Fill in the required fields:
   - `id` (lowercase-with-hyphens)
   - `display_name`
   - `soc_family`
   - `cpu_arch`

3. Add board-specific knowledge:
   - USB VID/PID for Rockchip/recovery modes
   - Serial baud rate candidates
   - eMMC size range and controller path
   - Known dmesg failure signatures

4. Validate:
   ```bash
   boardmedic profiles validate
   ```

5. Create a fixture directory for testing:
   ```bash
   mkdir -p fixtures/my_board/basic
   # Add usb.txt, lsblk.json, dmesg.txt, ip_addr.txt
   # Add fixture.yaml with profile_id, root_disk
   ```

6. Test:
   ```bash
   boardmedic diagnose --profile my-board --fixture fixtures/my_board/basic
   ```

No Python code is required for simple board profiles.

---

## Adding a New Probe

1. Create `boardmedic/probes/myprobe.py`
2. Implement a class with `probe()` method
3. Use `CommandRunner` for all subprocess calls
4. Return typed model objects
5. Handle missing tools gracefully (return empty list / ToolStatus.UNAVAILABLE)
6. Add to `boardmedic/diagnostics/__init__.py` orchestration
7. Add CLI sub-command to `boardmedic/cli.py`

---

## Adding a New Diagnostic Rule

1. Subclass `DiagnosticRule` in `boardmedic/rules/__init__.py`
2. Set `id`, `description`, `tags`
3. Implement `evaluate(session)` → `Optional[DiagnosticFinding]`
4. Add to `ALL_RULES` list
5. Reference in profile `enabled_rules` if board-specific

---

## Architecture Overview

```
boardmedic/
├── cli.py              # Typer CLI - all commands
├── models/             # Typed Pydantic models (source of truth)
├── core/
│   ├── runner.py       # Central command executor (ALL subprocess calls)
│   └── session.py      # Session lifecycle management
├── platform/           # OS detection, tool availability
├── profiles/           # YAML profile schema, registry, loader
├── probes/             # Read-only device detection
│   ├── usb.py          # USB + Rockchip detection
│   ├── serial.py       # Serial port enumeration + capture
│   ├── network.py      # Network interface detection
│   └── adb.py          # ADB, fastboot, Rockchip tools
├── collectors/
│   ├── storage.py      # Storage enumeration (lsblk/Get-Disk)
│   └── mmc.py          # MMC/eMMC sysfs + dmesg analysis
├── safety/             # Safety engine + destructive gate
├── diagnostics/        # Orchestrator - ties all probes together
├── rules/              # Diagnostic rule engine
├── recovery/
│   ├── planner.py      # Recovery plan generator
│   └── operations.py   # Guarded destructive operations
├── reporting/          # Markdown + JSON report generation
├── transports/         # SSH transport abstraction
└── utils/
    └── fixtures.py     # Fixture loading for offline testing
```

---

## Security Model

- **No telemetry**: No data is sent anywhere
- **No cloud dependency**: Works fully offline
- **Secret redaction**: Passwords, tokens, keys are redacted from logs
- **Privilege detection**: Reports `PERMISSION_REQUIRED` instead of auto-elevating
- **Destructive gate**: Multi-factor authorization required for all writes
- **Target verification**: Protects host disk, root filesystem, recovery media
- **Dry-run**: Every destructive path supports `--dry-run`

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success, no critical findings |
| 1 | Diagnostic findings present |
| 2 | Invalid usage / bad arguments |
| 3 | Permission required |
| 4 | Dependency / tool missing |
| 5 | Safety refusal |
| 6 | Recovery failure |

---

## OS Compatibility

| Feature | Windows | Linux |
|---------|---------|-------|
| USB detection | ✅ PowerShell/Get-PnpDevice | ✅ lsusb |
| Serial ports | ✅ pyserial | ✅ pyserial |
| Network | ✅ Get-NetIPAddress | ✅ ip addr |
| Storage | ✅ Get-Disk | ✅ lsblk |
| MMC/eMMC | ⚠ Limited (no sysfs) | ✅ Full |
| ADB/Fastboot | ✅ | ✅ |
| Rockchip tools | ✅ | ✅ |
| SSH transport | ✅ | ✅ |

---

## Limitations

- **Hardware not validated**: All testing is software-based using fixtures
- **MMC debugfs**: Requires root on Linux (`PERMISSION_REQUIRED` reported otherwise)
- **Windows eMMC**: Limited MMC diagnostics on Windows (no kernel sysfs)
- **pyusb optional**: USB enumeration falls back to lsusb/PowerShell if pyusb missing
- **No JTAG/SWD**: Hardware debugging interfaces not yet supported
- **No built-in firmware**: Does not bundle vendor firmware images

---

## License

MIT — see [LICENSE](LICENSE)

## Contributing

BoardMedic is designed for extensibility. The primary extension points are:
- New board profiles (YAML, no code required for simple boards)
- New probes (`boardmedic/probes/`)
- New diagnostic rules (`boardmedic/rules/`)
- New transport implementations (`boardmedic/transports/`)
