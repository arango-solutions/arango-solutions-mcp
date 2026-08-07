# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Installable `arangodb_mcp` source package and `arangodb-mcp` console command.
- Wheel-only isolated installation and package-data verification gate.
- Tag release automation for PyPI trusted publishing, GHCR digest publication, SPDX SBOMs,
  GitHub attestations, keyless cosign signing, Trivy scanning, and post-publication verification.

### Changed

- Catalog metadata and AQL manuals are distributed as package data and loaded through
  `importlib.resources`.
- The container runtime installs the built wheel into a read-only, non-root virtual environment
  instead of copying repository source.

### Security

- Release jobs use job-scoped least privileges, short-lived OIDC credentials, immutable image
  digests, provenance attestations, and signature identity verification.
