# BoardMedic Storage Safety Architecture

The highest priority constraint of BoardMedic is: **never destroy the host development workstation or the wrong embedded storage device**.

## Threat Model

When working with embedded Linux devices:
1. An engineer may run recovery scripts on a host PC where `/dev/sda` or `Disk 0` is the workstation's NVMe/SATA SSD with all their data.
2. An embedded recovery SD card may be booted into RAM or a live rootfs. Wiping the recovery SD card instead of internal eMMC renders the board unbootable.
3. Drive identifiers change between kernel boots (e.g. `mmcblk0` vs `mmcblk1`). Hardcoded device paths are inherently hazardous.

## Multi-Layer Protection Pipeline

```
[Target Device Path]
         |
         v
+-------------------------------------------------------+
| Layer 1: Identity & Role Classification               |
| - Is device marked as Windows System Disk?            |
| - Does device match current root filesystem (/)?      |
| - Does device host /boot, /boot/efi, or /home?        |
| - Is device designated as recovery media?             |
+---------------------------+---------------------------+
                            | PASS
                            v
+-------------------------------------------------------+
| Layer 2: Board Profile Verification                   |
| - Does disk size match profile eMMC range?            |
| - Is removable flag consistent (eMMC = non-removable)?|
| - Does bus path match expected MMC controller?        |
+---------------------------+---------------------------+
                            | PASS
                            v
+-------------------------------------------------------+
| Layer 3: SafetyEngine verify_target()                 |
| - Must be classified as POSSIBLE_TARGET               |
| - All double-checks pass                              |
| - Status upgraded to VERIFIED_TARGET                  |
+---------------------------+---------------------------+
                            | PASS
                            v
+-------------------------------------------------------+
| Layer 4: DestructiveGate Authorization                |
| - Explicit --destructive CLI flag provided            |
| - Dry-run mode intercepted if active                  |
| - Interactive device confirmation typed by operator   |
+---------------------------+---------------------------+
                            | PASS
                            v
                   [Execution Allowed]
```

## Safety Statuses

| Status | Meaning | Action Permitted |
|--------|---------|------------------|
| `PROTECTED_SYSTEM_DISK` | Host operating system drive | Hard Refusal |
| `PROTECTED_CURRENT_ROOT` | Device where `/` is currently mounted | Hard Refusal |
| `PROTECTED_BOOT_DEVICE` | Holds `/boot` or `/boot/efi` partition | Hard Refusal |
| `PROTECTED_RECOVERY_MEDIA` | Drive used to boot rescue Linux | Hard Refusal |
| `UNKNOWN_UNSAFE` | Unclassified disk or unknown root device | Refusal |
| `POSSIBLE_TARGET` | Passed role checks, unmounted | Eligible for verification |
| `VERIFIED_TARGET` | Passed role checks AND profile validation | Eligible for gated action |

## Destructive Gate Flags

Destructive commands (`boardmedic recover wipe`, `boardmedic recover flash`) require:
```bash
# Refused with exit code 5:
boardmedic recover wipe --target /dev/mmcblk1

# Approved only after safety validation and target confirmation:
boardmedic recover wipe --target /dev/mmcblk1 --destructive --yes
```

If `--dry-run` is active, commands are intercepted and logged without executing.
