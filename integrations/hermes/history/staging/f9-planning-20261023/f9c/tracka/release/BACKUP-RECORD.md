# F9 release backup (WSL → Windows), 2026-10-24

This is a copy of the WSL-only F9 release artifacts. Nothing was rebuilt or changed. `SOURCE-SHA256SUMS` was computed in WSL inside the staging folder and verified on Windows after the copy (all OK).

| File | sha256 |
|---|---|
| `f9c1/hermes-gateway-dev-f293e72-f9c1.tar.gz` (the Track A candidate, validated 51/51) | `4f899311cbd587feb5b5bd39a91361f75c69c5b58b3973b2bb5c6d596b9c41c9` |
| `f9c1/MANIFEST.sha256` (14,323 entries; equals the tarball member) | `0caa044e2f10de3a2ba2e8ac17614fd969da823b14b90f5f1dbb1350d6c0a93e` |
| `f9b1-base/hermes-gateway-dev-f293e72-f9b1.tar.gz` (the accepted F9-B base) | `6da1a721c4ae75cd9b5990c7961a6186e7a0a974e852ec11df4fa6c7199aeab3` |
| `f9b1-base/MANIFEST.sha256` (the accepted F9-B MANIFEST) | `0fff1dea07f43aa1bb6c479d00219aa7ccb25bd66b690ae7b51fcc50d2194461` |

**Already on Windows (not duplicated):**
- the F8r4 rollback target `f8-dev-install-20261023/phase-b/package-f8r4/hermes-gateway-dev-f293e72-f8r4.tar.gz` (`16c7417d…`);
- the f9c overlay sources and build scripts `tracka/pkgfiles`, `tracka/build`. These are identical to the WSL copies the build used (18 files, excluding test bytecode).

**Rebuild f9c1** (WSL; not performed):
1. Extract `f9b1-base/*.tar.gz` so that `/root/f9b/build/pkg` holds its `pkg` content.
2. Put `tracka/pkgfiles` at `/root/f9ca/tracka/pkgfiles`.
3. Run `tracka/build/build-f9c.sh`.

The script refuses unless the base MANIFEST is `0fff1dea…`. It prunes the base to that MANIFEST, overlays exactly 14 new and 2 changed files, and writes a deterministic tar. Two in-place builds were byte-identical; a rebuild from this backup has not been performed.

**Content scan before the copy:**
- no credentials, `.env`, auth files, databases or personal memories;
- the synthetic test key is absent;
- the only key-like strings are upstream Hermes test fixtures, the redaction module's pattern comment and desktop-notarization detection code.
