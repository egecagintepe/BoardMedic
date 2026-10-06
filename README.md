<div align="center">

# BoardMedic

**Cross-platform embedded board diagnostics and recovery toolkit.**

*"Someone dropped an unknown board on your desk and said: it doesn't boot. BoardMedic finds out what's alive, what's broken, and what recovery paths exist — without touching anything it shouldn't."*

---

[![CI](https://github.com/egecagintepe/BoardMedic/actions/workflows/ci.yml/badge.svg)](https://github.com/egecagintepe/BoardMedic/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey?logo=linux&logoColor=white)](https://github.com/egecagintepe/BoardMedic)
[![Tests](https://img.shields.io/badge/tests-137%20passed-brightgreen?logo=pytest&logoColor=white)](tests/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-orange?logo=ruff&logoColor=white)](https://github.com/astral-sh/ruff)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-blueviolet?logo=github)](CONTRIBUTING.md)
[![Board Profiles](https://img.shields.io/badge/board%20profiles-1-informational?logo=raspberrypi&logoColor=white)](profiles/)
[![Fixtures](https://img.shields.io/badge/test%20fixtures-offline%20capable-teal)](fixtures/)
[![Safety Gate](https://img.shields.io/badge/destructive%20ops-gated-red)](docs/safety.md)

</div>

---

## What is BoardMedic?

BoardMedic is a **reusable, board-agnostic** toolkit born from a real RK3568 industrial board recovery case. Engineers use it to systematically diagnose unknown or broken embedded Linux/Android boards — collecting evidence, classifying failures, and generating safe, ordered recovery plans.

It is **not** a one-board flashing script, a vendor utility, or a cloud tool. It runs entirely offline and never touches hardware it cannot verify is safe.

---

## Feature Highlights

<table>
<tr>
<td width="33%" valign="top">

### Multi-Path Detection
Automatically detects every available communication path to the board:
- USB (including Rockchip MaskROM/Loader)
- Serial / UART (multi-baud)
- Network (ADB over network, SSH)
- Fastboot
- Direct storage enumeration

</td>
<td width="33%" valign="top">

### Evidence-Based Diagnostics
Every finding comes with a full evidence chain:
- `OBSERVED` — directly measured
- `DERIVED` — computed from raw data
- `INFERRED` — pattern matched
- `HYPOTHESIS` — possible but unconfirmed
- Severity + confidence score per finding

</td>
<td width="33%" valign="top">

### Recovery Planning
Generates ordered, evidence-based recovery plans:
- Non-destructive steps always come first
- Destructive steps are clearly marked
- Every step guarded by the Safety Engine
- `--dry-run` available on every destructive path

</td>
</tr>
<tr>
<td width="33%" valign="top">

### Multi-Layer Safety Engine
Before any destructive operation, the Safety Engine verifies:
- Target is NOT the host OS disk
- Target is NOT the current root device
- Target is NOT recovery media
- Target passes profile size/controller checks
- Explicit `--destructive --target` flags required

</td>
<td width="33%" valign="top">

### Board Profile System
Boards are described in YAML — no Python required for simple profiles:
- SoC family + CPU arch
- USB VID/PID for all recovery modes
- Serial baud rate candidates
- eMMC size range + controller path
- Known dmesg failure signatures

</td>
<td width="33%" valign="top">

### Offline Fixture Testing
Run full diagnostics without physical hardware:
- Fixtures capture real USB/serial/storage/dmesg output
- Replay any failure scenario deterministically
- 137 tests, 0 hardware required
- CI matrix: Ubuntu + Windows x Python 3.11/3.12/3.13

</td>
</tr>
<tr>
<td width="33%" valign="top">

### Structured Reporting
Generate reports in multiple formats:
- Markdown (human-readable)
- JSON (machine-parseable)
- `--anonymize` flag redacts IPs, MACs, usernames
- Report persisted alongside session data

</td>
<td width="33%" valign="top">

### Zero Telemetry
- No data sent anywhere, ever
- Works fully offline
- Passwords/tokens/keys redacted from logs automatically
- Privilege detection: reports `PERMISSION_REQUIRED` instead of auto-elevating

</td>
<td width="33%" valign="top">

### Cross-Platform
Runs natively on both Windows and Linux:
- PowerShell / WMI / Get-PnpDevice on Windows
- lsusb / lsblk / sysfs / ip on Linux
- Same CLI, same output format, same test suite

</td>
</tr>
<tr>
<td width="33%" valign="top">

### Extensible Architecture
Designed for extension from day one:
- Add board profiles (YAML, no code needed)
- Add probes (`boardmedic/probes/`)
- Add diagnostic rules (`boardmedic/rules/`)
- Add transports (`boardmedic/transports/`)

</td>
<td width="33%" valign="top">

### Semantic Exit Codes
Every exit code carries meaning for scripting:
- `0` — clean, no critical findings
- `1` — findings present
- `3` — permission required
- `5` — safety refusal
- `6` — recovery failure

</td>
<td width="33%" valign="top">

### Session Persistence
Every diagnostics run produces a session directory:
- `session.json` — full typed session model
- `findings.json` — all diagnostic findings
- Persisted automatically on completion
- Report can be regenerated anytime

</td>
</tr>
</table>

---

## Boot Chain Analysis

BoardMedic traces the full embedded Linux boot chain stage by stage:

```
POWER --> BOOTROM --> BOOT_MEDIA --> KERNEL --> ROOTFS --> NETWORK
  |          |            |            |           |           |
  OK      MaskROM       eMMC         DTB        Mount       DHCP
          Loader        FAIL         Panic      Failure     Timeout
```

Each stage is independently assessed. Failures are localized with evidence and confidence scores before any recovery step is suggested.

---

## Quick Start

```bash
pip install boardmedic
```

Or from source:

```bash
git clone https://github.com/egecagintepe/BoardMedic.git
cd BoardMedic
pip install -e ".[dev]"
```

**Requirements:** Python 3.11+, Windows 10/11 or Ubuntu/Debian Linux
**Optional:** `pyserial` (serial capture), `pyusb` (USB enumeration)

---

## Typical Workflow

```bash
# 1. Verify host environment
boardmedic doctor

# 2. Browse available board profiles
boardmedic profiles list
boardmedic profiles show dc-a568b

# 3. Detect every available path to the board
boardmedic detect usb       # USB: VID/PID, Rockchip MaskROM/Loader
boardmedic detect serial    # Serial/UART ports
boardmedic detect network   # Network interfaces
boardmedic detect storage   # Storage + safety classification

# 4. Probe each path in detail
boardmedic probe usb
boardmedic probe serial --port COM5 --baud 1500000 --seconds 15
boardmedic probe adb
boardmedic probe fastboot
boardmedic probe rockchip
boardmedic probe storage
boardmedic probe mmc
boardmedic probe ssh 192.168.1.100 --user root

# 5. Run full diagnostics (with fixture for offline demo)
boardmedic diagnose --profile dc-a568b
boardmedic diagnose --profile dc-a568b --fixture fixtures/dc_a568b/emmc_stuck_not_ready

# 6. Generate a report
boardmedic report
boardmedic report --format json
boardmedic report --output report.md --anonymize

# 7. Get a recovery plan
boardmedic recover plan --profile dc-a568b
boardmedic recover plan --profile dc-a568b --dry-run
```

---

## Board Profiles

| ID | Board | SoC | Architecture | Status |
|----|-------|-----|-------------|--------|
| `dc-a568b` | DC-A568B / ZTL-A568 / DC_A568 | Rockchip RK3568 | ARM64 | Supported |
| `rk3399` | Generic RK3399 | Rockchip RK3399 | ARM64 | Planned |
| `rk3588` | Generic RK3588 | Rockchip RK3588 | ARM64 | Planned |
| `h616` | Allwinner H616 | Allwinner H616 | ARM | Planned |
| `s905x3` | Generic S905X3 | Amlogic S905X3 | ARM64 | Planned |
| `cm4` | Raspberry Pi CM4 | Broadcom BCM2711 | ARM64 | Planned |

Profiles are YAML files in `profiles/`. Adding a profile does not require writing Python.

---

## DC-A568B Real Case Study

The DC-A568B (Rockchip RK3568) was the original motivating case. See the full write-up:

**[docs/cases/dc-a568b-emmc-not-ready.md](docs/cases/dc-a568b-emmc-not-ready.md)**

```bash
# Reproduce the exact failure scenario offline
boardmedic diagnose \
  --profile dc-a568b \
  --fixture fixtures/dc_a568b/emmc_stuck_not_ready

# Expected output:
#   [ERROR]   EMMC_INIT_NOT_READY  (HIGH confidence)
#   Boot chain: POWER=OK  BOOTROM=OK  BOOT_MEDIA=FAIL
#   Recovery plan: 10 ordered steps
#   Steps 1-7: Non-destructive
#   Steps 8-10: Destructive (require --destructive --target)
```

---

## Destructive Recovery Safeguards

```bash
# WRONG -- will be rejected
boardmedic recover wipe --target /dev/mmcblk1

# CORRECT -- all gates must pass
boardmedic recover wipe \
  --target /dev/mmcblk1 \
  --destructive \
  --yes

# ALWAYS test with dry-run first
boardmedic recover wipe \
  --target /dev/mmcblk1 \
  --destructive \
  --dry-run
```

The Safety Engine checks **before** any write:

| Check | What it protects |
|-------|-----------------|
| `is_system_disk` | Host OS boot disk |
| `is_root_device` | Currently mounted root filesystem |
| `is_recovery_media` | The USB/SD you booted from |
| Profile size check | Prevents wrong-device targeting |
| Profile controller check | Verifies expected storage path |
| Mount point scan | Checks all active mount points |

---

## Architecture

```
boardmedic/
├── cli.py              # Typer CLI -- all user-facing commands
├── models/             # Typed Pydantic models (source of truth)
├── core/
│   ├── runner.py       # Central command executor (ALL subprocess calls)
│   └── session.py      # Session lifecycle management
├── platform/           # OS detection, tool availability
├── profiles/           # YAML profile schema, registry, loader
├── probes/             # Read-only device detection
│   ├── usb.py          # USB + Rockchip VID/PID detection
│   ├── serial.py       # Serial port enumeration + capture
│   ├── network.py      # Network interface detection
│   └── adb.py          # ADB, fastboot, Rockchip tools
├── collectors/
│   ├── storage.py      # Storage enumeration (lsblk / Get-Disk)
│   └── mmc.py          # MMC/eMMC sysfs + dmesg analysis
├── safety/             # Safety engine + destructive gate
├── diagnostics/        # Orchestrator -- ties all probes together
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

## OS Compatibility

| Feature | Windows | Linux |
|---------|:-------:|:-----:|
| USB detection | Yes (PowerShell / Get-PnpDevice) | Yes (lsusb) |
| Rockchip MaskROM detection | Yes | Yes |
| Serial ports | Yes (pyserial / COM ports) | Yes (pyserial / /dev/ttyUSB) |
| Network interfaces | Yes (Get-NetIPAddress) | Yes (ip addr) |
| Storage enumeration | Yes (Get-Disk) | Yes (lsblk) |
| MMC / eMMC (sysfs) | Limited (no kernel sysfs) | Full |
| MMC dmesg analysis | Yes | Yes |
| ADB / Fastboot | Yes | Yes |
| Rockchip tools (rkdeveloptool) | Yes | Yes |
| SSH transport | Yes | Yes |
| Safety engine | Yes | Yes |
| Fixture / offline mode | Yes | Yes |
| Report generation | Yes | Yes |

---

## Probe Reference

| Command | What it does |
|---------|-------------|
| `boardmedic probe usb` | Enumerate USB devices, identify Rockchip VID/PID |
| `boardmedic probe serial --port PORT --baud N` | Capture serial output for N seconds |
| `boardmedic probe adb` | Enumerate ADB devices and properties |
| `boardmedic probe fastboot` | Enumerate fastboot devices |
| `boardmedic probe rockchip` | Detect Rockchip-specific recovery tools |
| `boardmedic probe storage` | List storage devices with safety classification |
| `boardmedic probe mmc` | MMC/eMMC sysfs analysis + dmesg scan |
| `boardmedic probe ssh HOST` | SSH connectivity test |

---

## Exit Codes

| Code | Meaning | When |
|------|---------|------|
| `0` | Success -- no critical findings | All checks passed |
| `1` | Diagnostic findings present | Something was wrong |
| `2` | Invalid usage / bad arguments | Bad CLI usage |
| `3` | Permission required | Needs root / elevation |
| `4` | Dependency missing | Required tool not found |
| `5` | Safety refusal | Destructive gate blocked operation |
| `6` | Recovery failure | Recovery step failed |

---

## Adding a Board Profile

No Python required for simple profiles.

```bash
# 1. Copy the template
cp profiles/_template.yaml profiles/my-board.yaml

# 2. Edit the required fields
#    id, display_name, soc_family, cpu_arch,
#    usb.vid_pid_pairs, serial.baud_candidates,
#    storage.emmc_size_gb_range, failure_signatures

# 3. Validate
boardmedic profiles validate

# 4. Create a test fixture
mkdir -p fixtures/my_board/basic
# Add: usb.txt, lsblk.json, dmesg.txt, ip_addr.txt, fixture.yaml

# 5. Test
boardmedic diagnose --profile my-board --fixture fixtures/my_board/basic
```

---

## Adding a Probe

1. Create `boardmedic/probes/myprobe.py`
2. Implement a class with a `probe()` method
3. Use `CommandRunner` for **all** subprocess calls (never `subprocess` directly)
4. Return typed Pydantic model objects
5. Handle missing tools gracefully → return `ToolStatus.UNAVAILABLE`
6. Add to `boardmedic/diagnostics/__init__.py` orchestration
7. Add CLI sub-command to `boardmedic/cli.py`

---

## Adding a Diagnostic Rule

1. Subclass `DiagnosticRule` in `boardmedic/rules/__init__.py`
2. Set `id`, `description`, `tags`
3. Implement `evaluate(session)` → `Optional[DiagnosticFinding]`
4. Add to `ALL_RULES`
5. Reference in profile `enabled_rules` for board-specific activation

---

## Security Model

| Property | Detail |
|----------|--------|
| Telemetry | None -- no data sent anywhere |
| Cloud dependency | None -- fully offline capable |
| Secret redaction | Passwords, tokens, keys redacted from all logs |
| Privilege | Reports `PERMISSION_REQUIRED` -- never auto-elevates |
| Destructive gate | Multi-factor: `--destructive` + `--target` + safety checks |
| Dry-run | Every destructive path supports `--dry-run` |
| Recovery media | Protected by Safety Engine -- cannot be targeted |

---

## Limitations

> **Note:** BoardMedic has been **software-tested** using fixture replays. Hardware validation (physically connecting boards and running recovery operations) has not yet been independently verified.

| Limitation | Detail |
|-----------|--------|
| Hardware validation | Software-tested only (fixtures). No independent hardware CI. |
| Windows MMC | Limited MMC diagnostics -- no kernel sysfs on Windows |
| pyusb optional | USB enumeration falls back to lsusb / PowerShell if missing |
| JTAG / SWD | Hardware debug interfaces not yet supported |
| Built-in firmware | Does not bundle vendor firmware images |
| Root required | MMC debugfs requires root on Linux |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and the contribution workflow.

Primary extension points:

- **Board profiles** -- YAML in `profiles/`, no Python required for simple boards
- **Probes** -- `boardmedic/probes/`, implement `probe()` and return typed models
- **Diagnostic rules** -- `boardmedic/rules/`, subclass `DiagnosticRule`
- **Transports** -- `boardmedic/transports/`, implement the transport interface

---

## License

[MIT](LICENSE) -- use it, modify it, ship it.

---

<div align="center">

Built for the engineers who get handed a dead board and a deadline.

</div>


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
