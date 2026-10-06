# Board Profiles in BoardMedic

BoardMedic is profile-driven. Profiles provide board-specific expectations (controller addresses, UART baud rates, USB recovery IDs, and expected storage boundaries) to generic diagnostic and recovery engines.

## Profile Structure

Profiles are written in YAML and stored in the `profiles/` directory.

### Example Profile

```yaml
id: dc-a568b
display_name: "DC-A568B / RK3568 Industrial Board"
aliases:
  - dc_a568
  - ztl-a568
  - rk3568-dc-a568b
soc_family: "Rockchip RK3568"
soc_model: "RK3568"
cpu_arch: "arm64"
vendor: "Dingchang / DCSMT / Zhitongli"
pcb_identifier: "DC-A568B"

serial:
  default_baud: 1500000
  baud_candidates: [1500000, 115200, 921600]
  voltage_level: "3.3V TTL"
  notes: "RK3568 default debug UART baud is 1.5M"

storage_expectations:
  - role: emmc_internal
    controller_bus: fe310000.mmc
    removable: false
    min_size_gib: 20.0
    max_size_gib: 40.0
    description: "Internal eMMC (typically 32GB KLMAG1JETD-B041 or similar)"

  - role: sd_card
    controller_bus: fe2b0000.mmc
    removable: true
    min_size_gib: 4.0
    max_size_gib: 2048.0
    description: "MicroSD Card slot used for boot and recovery"

usb_ids:
  - vid: "2207"
    pid: "350a"
    description: "RK3568 MaskROM"
    mode: maskrom

  - vid: "2207"
    pid: "350b"
    description: "RK3568 Loader"
    mode: loader

recovery_capabilities:
  - sd_boot
  - uart
  - rockchip_usb
  - ssh
  - linux_userspace
```

## Adding a New Board

1. Copy `profiles/_template.yaml` to `profiles/<board-id>.yaml`.
2. Fill in the SoC model, UART baud candidates, known controller buses, and USB vendor/product IDs.
3. Validate your profile using the CLI:
   ```bash
   boardmedic profiles validate
   boardmedic profiles show <board-id>
   ```
