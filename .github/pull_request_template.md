## Summary

Describe what changed and why.

## Validation

- [ ] `python -m pytest` passes
- [ ] `ruff check .` passes
- [ ] CLI behavior was smoke-tested where relevant
- [ ] Documentation was updated where relevant

## Safety review

- [ ] This change does not weaken system/root/recovery-media protection
- [ ] Destructive operations remain explicitly gated
- [ ] Dry-run remains non-destructive
- [ ] No secrets, credentials, private logs or firmware dumps are included
- [ ] New safety-sensitive behavior includes negative tests

## Evidence / fixtures

List fixtures, logs or reproducible inputs used to validate the change.

## Notes

Anything maintainers should know before merging.
