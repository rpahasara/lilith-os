# Source consolidation, October 2026

On 2026-10-27 the LILITH runtime source that existed only on the owner's workstation (Windows staging folders, WSL
build directories, local Git) was reviewed and brought into this private repository under
[ADR-0016](../adr/0016-private-repository-holds-reviewed-runtime-source.md). This record says what was added, what was
left out and why, and how to rebuild the runtime from Git. It is for a maintainer who has never seen those folders.

Nothing in this consolidation changed PROD, DEV, canonical memory, Privacy state or any credential.

## Where things live now

| Holder | Holds |
|---|---|
| This repository | Core API, owner-memory control, broker, authority and witness services (already here); Hermes integration patches and DEV release source, Router V2 and plugins, F7–F9 build lineage (`integrations/hermes/`, new) |
| PROD `lilith-01`, DEV `lilith-dev-01` | the installed releases, environment configuration and credentials, live cognitive data, canonical memory, Privacy state, signer and witness operation; the PROD-only files in [vm-only-source-gaps.md](vm-only-source-gaps.md) |
| GCP disk snapshots `lilith-01-preserve-20261027`, `lilith-dev-01-preserve-20261027` | crash-consistent copies of both hosts |
| Owner's encrypted recovery archive `lilith-runtime-source-20261027` (SHA-256 `9835426b…5dafde5`) | the original bytes of everything reviewed here, including the token-bearing DEV release tarball, historical configs, private research history, superseded release manifests and operator evidence; its off-PC copy is a separate owner operation |
| Owner custody | recovery passphrases, owner-device and authority keys, provider and console credentials |

## Upstream pin

NousResearch/hermes-agent `f293e7206b4ddd66042329442c6afebc19a8808d` (0.20.5, MIT). Not vendored: see
`integrations/hermes/UPSTREAM.md`.

## Change sets

Review and merge in this order. Each is independent of the others in content; the order is for reading.

| # | Pull request | Branch | Adds | Files |
|---|---|---|---|---|
| 1 | [#267](https://github.com/rpahasara/lilith-os/pull/267) | `source/consolidation-policy-v0.1` | ADR-0016, this record, the VM-only gap list | 4 |
| 2 | [#268](https://github.com/rpahasara/lilith-os/pull/268) | `source/hermes-runtime-source-v0.1` | `integrations/hermes/`: upstream pin and licence, PROD and DEV patch sets with digests, DEV release `f293e72-f9c2` non-upstream members (four token-bearing files as templates), DEV FORGET executor overlay, planned memory-context overlay, reconstruction and verification tools and tests | 74 |
| 3 | [#269](https://github.com/rpahasara/lilith-os/pull/269) | `source/router-v2-cognition-source-v0.1` | `integrations/hermes/home/`: Router V2 modules not tracked elsewhere, PROD/DEV variants, plugins, `MODULES.json` source map, assembly tool and tests | 26 |
| 4 | [#270](https://github.com/rpahasara/lilith-os/pull/270) | `source/hermes-build-lineage-v0.1` | `integrations/hermes/history/`: F7–F9 designs, results, build and simulation tooling, superseded release scripts, PROD export procedure | 309 |

## Environment variants

| File | PROD `lilith-01` | DEV `lilith-dev-01` |
|---|---|---|
| Hermes `gateway/run.py` | `2774eee5…` | `5928c9f0…` |
| Hermes `agent/agent_runtime_helpers.py`, `agent/turn_context.py` | upstream | `bdeecae2…`, `70f1ea4d…` |
| `lilith_router/gateway_integration.py` | `aef31314…` | `5ce4bbd4…` |
| `lilith_router/world_context.py` | `46b8187e…0104` (91,351 B), **VM-only** | `5c1fbf98…` (723 B import stub) |
| `router.yaml` | `7d14b571…`, **VM-only** | `7bb4fbb5…` (shadow, lanes off) |
| `plugins/lilith_os/adapter.py` | `39fa27b9…` | `8c3b0055…` |

Every other Router V2 and plugin file is byte-identical in both environments. Full digests are in
`integrations/hermes/patches/*.sha256` and `integrations/hermes/home/MODULES.json`.

## Rebuilding from Git

The statuses below were established on 2026-10-27 against the PR branches listed above and the preserved
workstation source. The tools and files they cover are not on `main` until the relevant pull requests merge. Full
runtime reconstruction and live deployment remain unverified.

| Target | How | Status on 2026-10-27 (PR branches) |
|---|---|---|
| Patched Hermes source, PROD and DEV | `integrations/hermes/tools/reconstruct_hermes_src.py` over a clone at the pin | SOURCE_BUILD_VERIFIED: all 6 PROD and 8 DEV files byte-exact |
| DEV release files held in Git | `integrations/hermes/tools/verify_dev_f9c2_source.py` | SOURCE_BUILD_VERIFIED against the deployed manifest |
| Token-bearing DEV release files | `integrations/hermes/tools/render_dev_f9c2_templates.py --token-file …` | SOURCE_BUILD_VERIFIED: 4/4 byte-exact with the custody value |
| DEV `HERMES_HOME` code tree | `integrations/hermes/home/tools/assemble_home.py --variant dev-f9c2` | SOURCE_BUILD_VERIFIED: complete, byte-exact |
| PROD `HERMES_HOME` code tree | same, `--variant prod-lilith-01 --allow-gaps` | PARTIAL: all files except `world_context.py` and `router.yaml` |
| Full DEV runtime (with interpreter and wheels) | release README, steps 1–5 | RUNTIME_RECONSTRUCTION not verified |
| Any deployment from this source | — | LIVE_DEPLOYMENT_NOT_TESTED |

PROD's virtualenv was installed without a lock and has drifted; it cannot be reproduced exactly from any source.

## Coverage of the reviewed workstation source

The 2026-10-27 preservation selected 1,105 unique files plus three repository-local items.

| Group | Count | Outcome |
|---|---|---|
| Deployed DEV release `f293e72-f9c2` (tarball) | 1 | non-upstream members in change set 2; four token-bearing members as templates; upstream, interpreter and wheels rebuilt from pin and lock; the tarball itself stays in the archive |
| Hermes staging, WSL build and superseded-release members | 482 | 307 in change set 4; 17 represented in change sets 2–3, by the PROD patch, or already tracked; 158 left out by category (below) |
| Operator driver scripts from 100+ ceremony work folders | 616 | left out, see below |
| Historical DEV configs with the gate token, a DEV `router.yaml`, DEV `SOUL.md` | 6 | left out: credential-bearing or persona |
| 16 unpushed local commits | 16 | see below |
| `fm02v2` uncommitted change set | 14 files | superseded by `main` |
| `hsin-relaxed-idle.vrma` (untracked) | 1 | not added, see below |

Reused instead of copied: 15 Router V2 lane and memory modules already tracked under `docs/architecture/slice-*` and
`services/core-api/lilith_memory`, `scripts/deployer_authority_boundary_proof.sh` (a DEV release member), and the
Hermes memory-context module `services/owner-memory-control/lilith_owner_memory/hermes_memory_context.py`.

### Left out on purpose

| Category | Reason | Preserved in |
|---|---|---|
| Provider-gate client token and every file that embeds it unredacted (the f9c2 tarball, 4 release files, 6 historical configs, 5 historical scripts) | credential | archive (`sensitive/`); Git holds templates with `__LILITH_GATE_CLIENT_TOKEN__` |
| WSL simulation `.env` and `provider.env` files (113), TLS test keys (10) | credentials; never read | WSL only (simulation data) |
| Owner, K-PCK and acceptance custody directories, `.ssh` | custody domain; never traversed | owner custody |
| DEV `SOUL.md` copies, PROD `SOUL.md`/`USER.md` | persona and profile runtime files (ADR-0008) | archive / PROD host |
| Owner origin-statement material | private personal memory | owner-held, outside every archive |
| Upstream Hermes checkout and source tar, Python interpreter, wheels, `egg-info` | third-party, rebuildable from the pin and lock | archive |
| Superseded release manifests (f8r1–f9c1) | superseded by the f9c2 manifest | archive |
| Run outputs, logs, TSV results, evidence tarballs, PROD inventories | operator evidence, not source | archive |
| Intermediate Core API / owner-memory patch sets from F9 | they patch this repository; the final state of each line is in Git history | archive |
| Track B `b4-option1-wip.patch` | abandoned alternative | archive |
| DEV_SYNTHETIC K-PCK pin and keygen result | synthetic custody material, must not read as owner authority | archive |
| 616 operator driver scripts (`.py`, `.sh`, `.ps1`) | single-use ceremony drivers bound to one ceremony's hosts, SHAs and paths; their governing records and every reusable tool are already tracked under `docs/architecture/` and `scripts/` | archive (`source/operator-drivers/`); a later reviewed selection may promote individual drivers |

### Local Git work

| Item | Finding | Outcome |
|---|---|---|
| `84973ba` test(owner-memory): A1–A7 atomicity hardening | same tree for every service file as `43087e7` on `main` | not incorporated: already on `main` |
| `5b8fd4b` docs: trusted DEV snapshot tool design | same patch-id as `e1fe8b9` on `main` | not incorporated: already on `main` |
| 14 research-history commits (`docs/research-history-reconciliation`, tag `local-private/research-history-full-ff47e69`) | add archived original PDFs/DOCX and private research history | not pushed: private research history; kept in the local repository and the archive |
| `fm02v2` working tree (14 files) | 3 files equal `main`; 7 equal blobs already on `main`'s history; the other 4 are older versions of `first_interaction_v1.py`, `l04_v2_adapter.py` and two tests that `main` has since hardened | not incorporated: superseded; the worktree is left untouched |

### Hsin animation

The untracked `public/assets/assets/animations/hsin-relaxed-idle.vrma` (118,448 B, `7de5b0a0…`) is a UniGLTF export
with zero animation length and 52 channels, written about three hours before the tracked
`public/assets/animations/hsin-relaxed-idle.vrma` (1,348,388 B, `f45abc44…`, an 11.8 s idle exported by
three.js). The tracked file is the one the avatar scene loads. The untracked file is an earlier intermediate export
at a mistaken doubled path, not a newer revision, and its asset rights are not separately recorded. It was not
added. It stays in the archive and in the working copy.

## Remaining gaps

- PROD-only source and configuration: [vm-only-source-gaps.md](vm-only-source-gaps.md). `PROD_ONLY_SOURCE_GAPS=OPEN`.
- The off-PC copy of the encrypted archive has not been made.
- DEV credentials (gate token, Groq key, console token) are host-only by design; rebuilding the DEV release needs the
  gate token from custody.
- The PROD virtualenv is not reproducible; the DEV wheel set is hash-locked but was not re-downloaded here.
- The release offline tests (`integrations/hermes/release/dev-f9c2/tests/`) need a Hermes runtime and were not re-run
  in this consolidation.
