# Security Policy

BoardMedic interacts with low-level hardware, storage devices and recovery tooling. Safety bugs can cause data loss or expose sensitive diagnostic information.

## Reporting a vulnerability

Please avoid publishing exploit details for any issue that could:

- bypass destructive-target validation;
- allow the host OS disk, current root device or recovery media to be erased;
- execute an unintended command through untrusted input;
- expose passwords, private keys, tokens or authorization headers;
- cause unsafe privilege escalation;
- silently weaken dry-run or destructive-operation gates.

Use GitHub's private vulnerability reporting feature when available. If it is not available, contact the repository owner privately before opening a public issue.

## Safety expectations

A valid fix must preserve these invariants:

1. No destructive action may be selected from disk enumeration order alone.
2. Host system disks and the active root/boot device must never be valid destructive targets.
3. Recovery media must be protected.
4. Ambiguous target identity must fail closed.
5. Dry-run must never write to physical storage.
6. Secret material must not be intentionally persisted to reports or command logs.
7. Detection and diagnosis must remain non-destructive by default.

## Diagnostic data

Before attaching logs to a public issue, inspect them for:

- usernames and hostnames;
- IP and MAC addresses;
- company-internal paths;
- serial numbers;
- SSH material;
- API keys and tokens;
- passwords or command-line credentials.

Use anonymized reports whenever practical.

## Supported versions

BoardMedic is currently an early v0.x project. Security fixes are applied to the latest development line.
