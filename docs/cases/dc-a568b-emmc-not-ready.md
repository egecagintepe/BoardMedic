# Case Study: DC-A568B eMMC "Card Stuck Being Busy" Diagnosis

## Background

A real-world embedded board recovery scenario involving the **Dingchang DC-A568B** (Rockchip RK3568 industrial IoT board with 32GB onboard eMMC).

The board failed to boot from internal storage. When booted into rescue Linux via MicroSD, `lsblk` listed only the SD card (`mmcblk0`), with no sign of the internal eMMC block device (`mmcblk1`).

An inexperienced engineer might immediately assume:
> *"The eMMC flash memory is dead, throw away the board or replace the BGA chip."*

BoardMedic was used to analyze the diagnostic evidence scientifically.

## Diagnostic Evidence Collected

From the kernel log (`dmesg`):
```text
[    1.842010] mmc1: host does not support reading read-only switch, assuming write-enable
[    1.849200] mmc1: queuing unknown CIS tuple 0x01 (2 bytes)
[    1.856100] mmc1: queuing unknown CIS tuple 0x1a (5 bytes)
[    1.862400] mmc1: queuing unknown CIS tuple 0x1b (8 bytes)
[    1.870100] mmc1: queuing unknown CIS tuple 0x14 (0 bytes)
[    1.902300] mmc1: Card stuck being busy! __mmc_poll_for_busy
[    1.908500] mmc1: error -110 doing runtime resume
[    2.124500] mmc1: req done (CMD1): 0: 40ff8080 00000000 00000000 00000000
[    2.132000] mmc1: Card stuck being busy! __mmc_poll_for_busy
[    2.356700] mmc1: req done (CMD1): 0: 40ff8080 00000000 00000000 00000000
[    2.364100] mmc1: Card stuck being busy! __mmc_poll_for_busy
[    2.588900] mmc1: req done (CMD1): 0: 40ff8080 00000000 00000000 00000000
[    2.596000] mmc1: Card stuck being busy! __mmc_poll_for_busy
[    2.821100] mmc1: req done (CMD1): 0: 40ff8080 00000000 00000000 00000000
[    2.828200] mmc1: Card stuck being busy! __mmc_poll_for_busy
[    2.834500] mmc1: error -110 whilst initialising MMC card
[    2.840200] mmc1: Failed to initialize a non-removable card
```

## Technical Analysis

### OCR Register Value: `0x40ff8080`
In the eMMC standard (JEDEC eMMC specification):
- Bit 31 of the OCR (Operation Conditions Register) is the **Card power up status bit** (commonly called the `READY` bit or `busy` bit).
- When Bit 31 is `1`, the card has completed its internal power-on initialization and is ready for commands.
- When Bit 31 is `0`, the card is busy and still powering up or initializing internal states.

In this capture:
- Value = `0x40ff8080`
- In binary: `0100 0000 1111 1111 1000 0000 1000 0000`
- Bit 31 is **0**!
- Bit 30 is `1` (Access Mode: Sector Mode / High Capacity)
- Bits 15-23 indicate voltage window support (2.7V - 3.6V)

### Findings
1. **The MMC host controller (`fe310000.mmc`) is alive and functioning**: It sends CMD1 clock pulses and receives valid response packets from the card.
2. **The eMMC chip is alive and communicating**: It successfully receives CMD1 and replies with OCR `0x40ff8080`.
3. **The eMMC never enters READY**: Polling continues until timeout (`-110` / `ETIMEDOUT`). Because it never reports READY, the Linux MMC core aborts enumeration before creating block device nodes.

## Distinguishing "Initialization Failure" from "Dead NAND"

BoardMedic's rule engine explicitly reports `EMMC_INIT_NOT_READY` with confidence `HIGH`, and warns:
> *"The device is communicating but not completing initialization. This does NOT definitively confirm that the NAND storage itself is dead."*

Possible root causes:
- Power rail anomaly on VCC or VCCQ (noise, drop below threshold under initialization load)
- Signal integrity degradation on CMD or CLK traces
- Controller firmware deadlock inside the eMMC package
- Flash memory physical wear-out

## Resolution Hierarchy

1. Verify voltage rails with a digital oscilloscope during boot.
2. Boot into Rockchip USB MaskROM mode using shorted test point / button and test communication using `rkdeveloptool`.
3. Check UART logs during early U-Boot SPL stages.
4. Try unbinding and rebinding the controller with reduced clock speeds.
