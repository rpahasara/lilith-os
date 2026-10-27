# Hermes DEV build lineage (F7–F9, 2026-10-22 to 2026-10-26)

Historical source that produced the DEV Hermes releases `f293e72-f8r1` … `f293e72-f9c2`: plans, designs, result and
acceptance records, build and packaging scripts, local mirror and simulation harnesses, mutation tests, release
scripts of superseded releases, and the 2026-10-22 PROD read-only export plan. It is kept for provenance and
reconstruction. **It is not the current source and nothing here is meant to be run as is**: the scripts name hosts,
paths and operator workstations of the time, and several act as root on a host. The current DEV release is
`integrations/hermes/release/dev-f9c2/`; the current Router V2 tree is `integrations/hermes/home/`.

| Path | Origin |
|---|---|
| `staging/dev-build-20261022/` | F7 local reconstruction of the PROD Hermes tree and its offline test; `hermes-home-dev/plugins/lilith_os/adapter.py` is the 10-22 DEV candidate adapter (`76948218…`), the base of the planned memory-context overlay |
| `staging/dev-candidate-20261022/` | the first DEV candidate's change list, env-file template (names only) and adapter diff |
| `staging/export-plan/`, `staging/prod-readonly-20261022/`, `staging/quarantine-20261022-222752/REVIEW.md` | the 10-22 PROD read-only inspection and sanitized-export procedure, its verifier and the quarantine review |
| `staging/f8-dev-install-20261023/` | F8 runbooks, build tools, Phase A (f8r1/f8r2) and Phase B (f8r3/f8r4) designs, gate-by-gate operator scripts, results and acceptances, mirror harnesses |
| `staging/f8-pkg-build/` | input checksum list for the F8 package build |
| `staging/f9-planning-20261023/` | F9 plan; f9a (onboarding off), f9b (operate profile); f9c Privacy FORGET work: design, slices 1–3, restore gate and fix, executor, rollback anchor prototype, Track A (release f9c1/f9c2, DEV ops) and Track B (privacy anchor) results and tooling |
| `release-members/` | the only members of superseded release packages f8r3, f8r4 and f9c1 that exist nowhere else |
| `wsl-release-copies/`, `wsl/` | release scripts and units recovered from local WSL simulation rollbacks, and WSL-only mirror/debug scripts (f8r2–f9ca); `name.<sha8>.ext` marks a second distinct version of the same file |

## Adaptations from the original bytes

The original bytes of every file are in the owner's encrypted recovery archive (`lilith-runtime-source-20261027`).
Only these files differ from them:

| File | Change | Original SHA-256 |
|---|---|---|
| `staging/f8-dev-install-20261023/phase-b/mirror-tools/run_suite_r3.sh` | gate client token → `__LILITH_GATE_CLIENT_TOKEN__` (4×) | `08ff6643b82dd5f8a5821845010e9f56add46e3ff0213f189b756eb03d80dfda` |
| `staging/f8-dev-install-20261023/phase-b/PHASE-B-DESIGN-f8r3.md` | same (2×) | `ec82b2e3ba878a563682c86079f579a5dc05f825938296dd900327cbeaeff6e5` |
| `wsl/f8r4/mirror/gate_matrix.sh` | same (1×) | `f8aaa9d9f06f9401510c4bfe29f6e3f346db4309ec4c0b5d899f2caf2fc162bd` |
| `wsl/f8r4/mirror/run_suite_r4.sh` | same (4×) | `c1b8bc134647ec6a32455d232bdbdbf053e3bcc5155c1ebbba97e858e4df7285` |
| `wsl-release-copies/f293e72-f8r3/bin/verify_release.py` | same (2×) | `0cee72cbb9b620a2d5fcefcacfc26aa864d009e9cc7bec612391c62ded6b88aa` |
| `staging/f8-dev-install-20261023/phase-b/dev-run/PHASE-B-RESULT.md` | final newline added (repository Markdown rule) | `2d37052193eb1ac343d2ec0722fdb75866c759565ae79e526cab37558fa4d065` |

`synthprov.sh` (two versions) writes a synthetic `gsk_F8R3SY…` placeholder for a fake provider in a local mirror; it
is not a key.

## Deliberately not here

| Category | Why | Where it is preserved |
|---|---|---|
| Run outputs, logs, TSV results, evidence tarballs, PROD inventories | operator evidence, not source | encrypted archive |
| Intermediate Core API / owner-memory patch sets (f9c slices, restore gate/fix, executor, anchor, Track A, Track B) | they patch this repository; the final state of each line is in Git history (Track A and Track B cumulative patches: every post-image blob present), the intermediate iterations are superseded | encrypted archive |
| Track B `b4-option1-wip.patch` | abandoned alternative, never merged | encrypted archive |
| Superseded release manifests (f8r1–f9c1, ~1.8 MB each), upstream source tar and blob list, package input tars, `egg-info` | rebuildable from the pin, or superseded by the f9c2 manifest | encrypted archive |
| Runtime `config.yaml` versions with the gate token, historical `router.yaml`/`SOUL.md` copies | credential-bearing or persona runtime files | encrypted archive (`sensitive/`) |
| DEV_SYNTHETIC K-PCK pin and keygen result | custody-adjacent synthetic authority material | encrypted archive |
