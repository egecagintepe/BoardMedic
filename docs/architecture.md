# BoardMedic Architecture

BoardMedic is designed around a modular, non-destructive, evidence-based architecture for diagnosing and recovering embedded Linux/Android systems.

## Core Design Principles

1. **Safety First**: Destructive operations are guarded by multi-layer hardware validation, root filesystem detection, interactive gates, and `--destructive` command-line flags.
2. **Evidence-Based Reasoning**: Every finding is backed by observable evidence, labeled explicitly as `OBSERVED`, `DERIVED`, `INFERRED`, or `HYPOTHESIS`.
3. **Reproducibility via Fixtures**: Probes and collectors can run either against live hardware or against captured fixture data for deterministic offline testing.
4. **Cross-Platform Operation**: Seamless operation across Linux and Windows with graceful degradation when host tools (e.g., `lsusb`, `debugfs`) are absent.

## Component Overview

```
                      +-------------------+
                      |     Typer CLI     |
                      +---------+---------+
                                |
                      +---------v---------+
                      |    Diagnostics    |
                      |    Orchestrator   |
                      +----+---------+----+
                           |         |
         +-----------------+         +-----------------+
         |                                             |
+--------v--------+                           +--------v--------+
| Probes &        |                           | Rule Engine     |
| Collectors      |                           | & Boot Chain    |
+-----------------+                           +-----------------+
| - USB Probe     |                           | - eMMC Stuck    |
| - Serial Probe  |                           | - eMMC Absent   |
| - Network Probe |                           | - Rockchip Mode |
| - Storage Probe |                           | - Boot Analysis |
| - MMC Collector |                           +--------+--------+
+--------+--------+                                    |
         |                                    +--------v--------+
+--------v--------+                           | Recovery        |
| Safety Engine   +-------------------------->+ Planner         |
+-----------------+                           +-----------------+
| - Root Guard    |                           | - Risk-ordered  |
| - Profile Match |                           | - Wipe / Flash  |
| - Gate Check    |                           +-----------------+
+-----------------+
```

### 1. `boardmedic.models`
Defines strictly typed Pydantic models for the entire system:
- Enums: `Platform`, `ToolStatus`, `BootStage`, `StageStatus`, `Severity`, `Confidence`, `EvidenceType`, `StorageClass`, `SafetyStatus`, `MMCState`, `RecoveryResultCode`
- Entities: `USBDevice`, `RockchipDevice`, `SerialPort`, `NetworkInterface`, `StorageDevice`, `BootChain`, `DiagnosticFinding`, `RecoveryPlan`, `DiagnosticSession`, `Report`

### 2. `boardmedic.core`
- `runner.py`: `CommandRunner` executes subprocess commands with:
  - Dangerous command interception (`dd`, `wipefs`, `mkfs`)
  - Automatic secret/token redaction in logs
  - Configurable timeouts
  - Dry-run virtualization
- `session.py`: `SessionManager` manages run directory artifacts, raw evidence logs (`dmesg.txt`, `lsblk.json`, `usb.txt`), and session metadata JSON.

### 3. `boardmedic.probes`
- `usb.py`: Cross-platform USB enumeration (via `lsusb` on Linux, PowerShell `Get-PnpDevice` on Windows). Detects Rockchip MaskROM (`0x350a`) and Loader (`0x350b`) devices.
- `serial.py`: Port enumeration and banner/log capture with configurable baud rate (e.g., 1,500,000 for Rockchip RK3568).
- `network.py`: Interface IP and ARP neighbor probing via `ip` command or Windows NetIPAddress.
- `adb.py`: Host tooling checks for `adb`, `fastboot`, `rkdeveloptool`, and `upgrade_tool`.

### 4. `boardmedic.collectors`
- `storage.py`: Storage device enumeration using `lsblk` JSON on Linux or PowerShell `Get-Disk` on Windows. Extracts size, transport, removable status, partitions, and mountpoints.
- `mmc.py`: MMC controller and card diagnostics. Parses `dmesg` logs for OCR registers (e.g., `0x40ff8080`), CMD1 polling loops, and card state transitions.

### 5. `boardmedic.safety`
- `SafetyEngine`: Classifies devices as `PROTECTED_CURRENT_ROOT`, `PROTECTED_SYSTEM_DISK`, `PROTECTED_RECOVERY_MEDIA`, `PROTECTED_BOOT_DEVICE`, `UNKNOWN_UNSAFE`, or `POSSIBLE_TARGET`.
- `verify_target`: Confirms candidate matches profile size boundaries, controller bus path, and is completely unmounted.
- `DestructiveGate`: Runtime confirmation barrier requiring `--destructive`, interactive confirmation, and verified status before executing wipe/flash operations.

### 6. `boardmedic.rules`
Declarative diagnostic rules evaluating a `DiagnosticSession`:
- `EMMCStuckNotReadyRule`: Detects cards stuck in busy state (OCR bit 31 low).
- `EMMCNotDetectedRule`: Detects missing MMC host controllers.
- `RockchipMaskROMRule`: Identifies devices in low-level BootROM recovery mode.
- `RockchipLoaderRule`: Identifies devices running secondary Rockchip loader.
- `HealthyEMMCRule`: Verifies functional eMMC block devices.
- `BootChainAnalyzer`: Evaluates 7-stage boot progress (`POWER`, `BOOTROM`, `BOOT_MEDIA`, `USB_RECOVERY`, `KERNEL`, `ROOTFS`, `NETWORK`).

### 7. `boardmedic.recovery`
- `RecoveryPlanner`: Builds risk-ordered recovery plans prioritizing non-destructive diagnostics and driver reprobing before destructive flashing.
- `WipeOperation` & `FlashOperation`: Low-level gated operations with sha256 verification and dry-run safety.

### 8. `boardmedic.reporting`
- Generates structured Markdown and JSON reports.
- Includes data anonymization filters for IP addresses, MAC addresses, and host paths.
