# Contributing to BoardMedic

Thanks for helping improve BoardMedic.

The project values **reproducible evidence, safe defaults and explicit uncertainty** over clever shortcuts.

## Development setup

```bash
git clone https://github.com/egecagintepe/BoardMedic.git
cd BoardMedic
python -m venv .venv
```

Activate the virtual environment, then:

```bash
python -m pip install --upgrade pip
pip install -e .
python -m pytest
ruff check .
```

## Before opening a pull request

Please make sure:

- tests pass;
- `ruff check .` passes;
- new parsers include realistic fixtures;
- safety-sensitive changes include negative tests;
- destructive behavior remains opt-in;
- no real credentials, firmware dumps or private logs are committed;
- documentation is updated when user-visible behavior changes.

## Adding a board profile

Prefer a YAML profile over board-specific Python code.

A useful profile should define, where known:

- identity and aliases;
- SoC family;
- expected USB IDs / recovery modes;
- serial baud candidates;
- storage expectations;
- MMC controller paths;
- boot media;
- known failure signatures;
- recovery capabilities.

Add fixtures and tests that prove both correct matching and safe refusal.

## Safety-sensitive changes

Changes to storage classification, destructive authorization, command execution, target verification, wipe/flash logic or privilege handling deserve extra review.

Do not test destructive commands on a real workstation disk.

Use:

- mocks;
- temporary files;
- fixtures;
- safely controlled loopback/test images where appropriate.

## Diagnostic quality

Findings should distinguish:

- **OBSERVED** — directly collected evidence;
- **DERIVED** — mechanically calculated from evidence;
- **INFERRED** — a reasoned technical conclusion;
- **HYPOTHESIS** — a plausible cause that is not proven.

Avoid claims such as “the NAND is definitely dead” unless the evidence actually proves it.

## Commit style

Clear conventional-style messages are preferred, for example:

```text
feat(probes): add Allwinner FEL detection
fix(safety): reject recovery media parent disks
docs(profiles): document Amlogic profile fields
test(mmc): add CRC-error fixture
```
