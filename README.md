# 🩺 BoardMedic

> **Evidence-driven diagnostics and guarded recovery for embedded Linux & Android boards.**

[![CI](https://github.com/egecagintepe/BoardMedic/actions/workflows/ci.yml/badge.svg)](https://github.com/egecagintepe/BoardMedic/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20Linux-4C8BF5)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/status-v0.1.0%20early%20release-orange)

BoardMedic is a command-line toolkit for engineers who get handed an embedded board with one instruction:

> **“It does not boot. Find out what is alive, what is broken, preserve the evidence, and tell me what we can safely try next.”**

Instead of manually bouncing between USB enumeration, UART, network tools, storage inspection, kernel logs, Android tooling and vendor recovery utilities, BoardMedic brings those paths into one profile-driven workflow.

---

## What BoardMedic does

BoardMedic can help answer:

- **What device is connected?**
- **Which communication paths are alive?**
- **How far does the boot chain get?**
- **Which storage devices exist?**
- **What evidence points to the failure domain?**
- **What recovery path should be tried next?**
- **Which actions would be destructive?**
- **What exact device would a destructive action touch?**

It is intentionally **conservative while detecting** and **aggressive only after explicit destructive authorization**.

---

## Highlights

| Capability | What it does |
|---|---|
| **USB detection** | Enumerates connected USB devices and recognizes Rockchip recovery VID/PID patterns where evidence is sufficient. |
| **UART / serial** | Discovers COM/tty devices and performs read-only serial capture, including high-speed Rockchip baud rates. |
| **Network inspection** | Collects local interfaces, addresses and neighbor information without blindly scanning large networks. |
| **ADB / Fastboot** | Detects tools and connected Android targets when available. |
| **Rockchip probing** | Wraps `rkdeveloptool` / `upgrade_tool` for safe discovery and recovery planning. |
| **Storage classification** | Normalizes disks and protects the host OS disk, current root device and recovery media. |
| **MMC / eMMC diagnostics** | Collects MMC host state, kernel evidence, OCR/CID/CSD/EXT_CSD where available, and classifies initialization failures. |
| **Boot-chain reasoning** | Evaluates stages such as POWER, BOOTROM, BOOT_MEDIA, U-Boot, KERNEL, ROOTFS and NETWORK. |
| **Evidence engine** | Separates **OBSERVED**, **DERIVED**, **INFERRED** and **HYPOTHESIS** instead of overstating a diagnosis. |
| **Recovery planner** | Produces ordered, risk-aware next steps based on what the system can actually prove. |
| **Guarded recovery** | Supports dry-run and explicitly authorized wipe/flash workflows behind multiple safety gates. |
| **Sessions & reports** | Stores raw evidence, findings, command logs and Markdown/JSON reports for repeatable engineering work. |
| **Board profiles** | Keeps board-specific knowledge in validated YAML profiles so new boards can be added without rewriting the core. |

---

## First supported board profile

The first full profile targets the **DC-A568B / DC_A568 / ZTL-A568 family based on Rockchip RK3568**.

The profile captures board-specific knowledge such as:

- expected Rockchip family and USB recovery behavior
- typical 3.3 V UART with 1,500,000 baud candidate
- known ZTL-A568 device-tree family
- internal eMMC controller path
- expected eMMC capacity window
- SD boot capability
- known MMC failure signatures
- Loader / MaskROM / UART / SD / Linux recovery paths

The motivating failure case included a board that could boot Linux from SD while its internal eMMC responded to initialization commands but never reached READY. BoardMedic models that as an initialization failure — **not as proof that the NAND itself is definitely dead**.

---

## Safety is a feature, not an afterthought

BoardMedic may generate or execute destructive recovery operations, so storage safety is treated as a first-class subsystem.

A destructive target must pass multiple independent checks. Depending on platform and profile, that can include:

- not the host operating-system disk
- not the current root device
- not the current boot/recovery media
- stable identity across enumeration
- expected device type
- expected controller / host path
- expected capacity range
- explicit target selection
- explicit `--destructive` authorization
- confirmation challenge unless intentionally bypassed with `--yes`

If identity is ambiguous, the correct result is:

```text
ABORTED_TARGET_SAFETY_CHECK
```

**BoardMedic should refuse a recovery rather than guess which disk to erase.**

---

## Installation

### Requirements

- Python **3.11+**
- Windows 10/11 or Ubuntu/Debian Linux
- Optional platform tools depending on what you want to probe:
  - `adb`
  - `fastboot`
  - `ssh`
  - `lsusb`
  - `lsblk`
  - `rkdeveloptool`
  - Rockchip `upgrade_tool`

Missing optional tools should degrade gracefully instead of crashing the entire application.

### Development install

```bash
git clone https://github.com/egecagintepe/BoardMedic.git
cd BoardMedic

python -m venv .venv
```

**Windows**

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

**Linux**

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

Then:

```bash
boardmedic --help
```

---

## Quick start

### 1. Check the host environment

```bash
boardmedic doctor
```

BoardMedic reports which capabilities are available, missing, unsupported or permission-restricted.

### 2. Inspect connected hardware

```bash
boardmedic detect usb
boardmedic detect serial
boardmedic detect network
boardmedic detect storage
```

### 3. Inspect board profiles

```bash
boardmedic profiles list
boardmedic profiles show dc-a568b
boardmedic profiles validate
```

### 4. Diagnose a board

```bash
boardmedic diagnose --profile dc-a568b
```

Or reproduce a known case completely offline with fixtures:

```bash
boardmedic diagnose \
  --fixture fixtures/dc_a568b/emmc_stuck_not_ready \
  --profile dc-a568b
```

### 5. Generate a recovery strategy

```bash
boardmedic recover plan --profile dc-a568b
```

The plan is non-destructive. It tells you what BoardMedic recommends doing next and why.

### 6. Generate a report

```bash
boardmedic report --profile dc-a568b --format markdown
boardmedic report --profile dc-a568b --format json
```

---

## Example: evidence-backed eMMC diagnosis

A finding can look conceptually like this:

```text
Profile
DC-A568B / RK3568

Boot paths
SD Linux          PASS
Network           PASS
Rockchip USB      UNKNOWN
UART              NOT TESTED
Internal eMMC     FAIL

Critical finding
MMC_CARD_RESPONDS_NOT_READY

Observed
- MMC controller is present
- repeated CMD1 responses were received
- no internal mmcblk device appeared

Derived
- READY bit remained clear

Inferred
- eMMC initialization does not complete before block-device enumeration

Hypotheses
- eMMC internal/controller fault
- local power-integrity problem
- reset/timing problem
- signal-integrity or board-level issue

Recommended next step
Check Rockchip Loader / MaskROM recovery.

No destructive action was performed.
```

That distinction between evidence and hypothesis is fundamental to BoardMedic.

---

## Recovery and destructive operations

### Dry-run first

Recovery workflows are designed to support dry-run:

```bash
boardmedic recover wipe \
  --target /dev/mmcblk1 \
  --profile dc-a568b \
  --dry-run \
  --destructive
```

Dry-run should perform detection, validation, safety checks and command generation **without writing to storage**.

### Destructive execution

A real destructive operation requires explicit authorization and a target that passes the safety engine.

Never copy a destructive command from a report and run it manually unless you independently understand and verify the target.

---

## Architecture

```text
                         ┌──────────────────────┐
                         │    BoardMedic CLI    │
                         └──────────┬───────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  │                                   │
          ┌───────▼────────┐                 ┌────────▼───────┐
          │ Probes /       │                 │ Safety Engine  │
          │ Collectors     │                 │                │
          │ USB / UART     │                 │ Host disk      │
          │ Network / MMC  │                 │ Root / boot    │
          │ ADB / Rockchip │                 │ Recovery media │
          └───────┬────────┘                 └────────┬───────┘
                  │                                   │
                  └─────────────────┬─────────────────┘
                                    │
                           ┌────────▼────────┐
                           │ Diagnostic     │
                           │ Rules + Models │
                           └────────┬────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
             ┌──────▼──────┐                 ┌──────▼──────┐
             │ Reporting   │                 │ Recovery    │
             │ MD / JSON   │                 │ Planner     │
             └─────────────┘                 └─────────────┘
```

Board-specific knowledge belongs in profiles; reusable logic belongs in the core.

---

## Sessions

Diagnostic work can be preserved as repeatable sessions containing normalized state and raw evidence.

Typical session data may include:

```text
boardmedic-sessions/
└── <timestamp>_<profile>/
    ├── session.json
    ├── device.json
    ├── findings.json
    ├── commands.jsonl
    ├── report.md
    ├── report.json
    ├── raw/
    └── logs/
```

Useful commands:

```bash
boardmedic session list
boardmedic session show <session_id>
```

Secrets such as passwords, private keys, authorization headers and access tokens must never be intentionally stored in diagnostic sessions.

---

## Adding support for another board

Simple boards should usually require **profile data, fixtures and tests — not a fork of the core**.

Typical workflow:

1. Copy `profiles/_template.yaml`.
2. Fill in identity, SoC family and aliases.
3. Define expected transports and recovery modes.
4. Define storage expectations and controller paths.
5. Add known serial settings and failure signatures.
6. Run profile validation.
7. Add one or more fixtures.
8. Add tests for both positive and unsafe cases.

Protocol-specific code should only be necessary when the board introduces genuinely new behavior.

---

## Development

```bash
python -m pytest
ruff check .
```

The project is designed around unit tests, parser tests, safety tests, fixture-based integration tests and CLI tests.

**Destructive tests must never target real physical storage.** Use mocks, fixtures, temporary files or controlled test images.

---

## Project status

BoardMedic **v0.1.0** is an early engineering release.

The software architecture, fixture-driven diagnostics, CLI, reporting and safety model are intended to be usable today, while real-world hardware validation will continue across additional boards and recovery scenarios.

Software test success is **not** the same thing as universal hardware validation.

---

## What BoardMedic is not

- It is **not** an automatic “flash whatever firmware I found” utility.
- It is **not** a guarantee that a board can be recovered.
- It is **not** a replacement for an oscilloscope, logic analyzer, BGA rework station or hardware expertise.
- It does **not** treat one kernel error string as proof of a dead component.
- It should never make Internet access mandatory for basic diagnostics.
- It should never silently choose a destructive target.

---

## Contributing

Contributions are welcome, especially:

- new board profiles
- new fixtures
- USB / serial / MMC parsers
- recovery adapters
- safety tests
- better evidence rules
- documentation and reproducible case studies

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

---

## Security

BoardMedic interacts with storage and recovery tooling. A bug in target classification can be serious.

If you find a safety issue, destructive-target bypass, secret exposure or command-injection path, please follow [SECURITY.md](SECURITY.md) instead of publishing an exploit workflow in a public issue.

---

## License

BoardMedic is licensed under the **MIT License**. See [LICENSE](LICENSE).

---

<p align="center">
  <strong>Detect what is alive. Preserve the evidence. Recover only what you can prove is safe to touch.</strong>
</p>
