# Releasing (Public)

This document describes the public release process for the ModeKeeper open-source surface.

## Scope and boundaries

Public release artifacts are published to:

- GitHub (source tags and GitHub Releases)
- PyPI (`modekeeper` package)

This document intentionally excludes internal/commercial operational workflows. Any licensed or commercial distribution tracks are managed separately and are not part of the public release procedure described here.

## Public release readiness

Before creating a release:

- Ensure `main` is green in CI and ready to ship.
- Ensure release notes content is appropriate for public audiences.
- Ensure version metadata is final and consistent with the intended public package version.
- Ensure your local checkout is clean and up to date.

## Public release procedure

1. Finalize the release version in repository metadata.
2. Create and push a version tag using the release remote (`github` when present, otherwise `origin`).
3. Publish a GitHub Release for that tag (notes/changelog should be public-safe).
4. Publish the corresponding package version to PyPI.
5. Verify the release boundary end to end:
   - tag is visible in GitHub
   - GitHub Release exists and is publicly readable
   - package is installable from PyPI at the expected version

## Runtime execution boundary (customer-managed)

Publishing a public release does not execute customer workloads. Runtime operation remains customer-managed:

- customers run ModeKeeper in their own environments
- customers control cluster/runtime permissions and data access boundaries
- release publication updates distributable software only (source/package), not customer-side execution state

## Public vs licensed/commercial surfaces

ModeKeeper has a public release-facing surface (GitHub + PyPI) and may have separately licensed/commercial delivery paths.

For public docs and release communication:

- describe only the public artifacts and public install/update path
- avoid implying unified public+private orchestration
- keep internal sequencing and private operational tooling out of public release documentation
