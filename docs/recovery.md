# BoardMedic Recovery Strategy

BoardMedic structures device recovery into a progressive, risk-ordered methodology. It avoids jumping straight to destructive flashing when non-destructive or disruptive diagnostic steps can clarify or resolve the failure.

## Risk Hierarchy

1. **Passive Observation (Safe)**
   - Serial UART capture (reading U-Boot/SPL/Kernel logs)
   - USB enumeration (checking for MaskROM or Loader modes)
   - Network probe (ping/ARP scan for reachable targets)
   - Storage inspection (`lsblk`, sysfs examination)
2. **Disruptive Operations (Non-Destructive)**
   - Driver unbind/rebind (e.g., reloading `fe310000.mmc` driver in Linux sysfs)
   - Power-cycling controllers or toggling regulator resets
3. **Hardware Recovery Modes**
   - Booting secondary rescue Linux environment via MicroSD
   - Entering Rockchip MaskROM mode via hardware test point / key
4. **Destructive Operations (Guarded)**
   - eMMC metadata wipe (erasing corrupt GPT/MBR partition tables)
   - Complete partition flashing via `dd`, `rkdeveloptool`, or `upgrade_tool`

## Example Recovery Workflow

```bash
# 1. Gather complete diagnostic evidence from live board or rescue environment
boardmedic collect --profile dc-a568b

# 2. Run diagnostic evaluation
boardmedic diagnose --profile dc-a568b

# 3. Generate structured recovery plan
boardmedic recover plan --profile dc-a568b

# 4. If eMMC shows corrupt partition table blocking boot:
# Dry-run wipe first
boardmedic recover wipe --target /dev/mmcblk1 --profile dc-a568b --dry-run --destructive

# Execute authorized wipe
boardmedic recover wipe --target /dev/mmcblk1 --profile dc-a568b --destructive

# 5. Flash clean firmware image
boardmedic recover flash --target /dev/mmcblk1 --image path/to/image.img --profile dc-a568b --destructive
```
