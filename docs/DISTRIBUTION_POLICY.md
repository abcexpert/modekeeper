# Distribution Policy

## Purpose

This repository is a public showroom/stub surface for ModeKeeper.

## Public surface

- GitHub public repository content intended for evaluation.
- Public PyPI package `modekeeper`.
- Buyer/procurement evidence generation scripts and docs.

## Excluded from this public snapshot

- Internal-only operational infrastructure.
- Commercial implementation internals not required for public evaluation.
- Secrets, credentials, and private deployment material.

## Release rules

- Use `bin/mk-release-stub` for wheel-only uploads.
- CI performs validation only and does not publish artifacts.
- Any boundary breach is a release blocker.
