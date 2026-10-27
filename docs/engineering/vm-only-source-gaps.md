# VM-only source gaps

Deployed artifacts whose bytes existed only on a host (and in that host's disk snapshot), not in Git and not on any
development machine. None may be reconstructed by guesswork or replaced by a DEV file. Recorded 2026-10-27 from the
read-only PROD and DEV audits of that day.

**Update 2026-10-27:** the owner-approved, bounded read-only PROD source export recovered the PROD rows below. It read
176 inventoried paths and verified 175 (all 37 that the audit had hashed matched); one was withheld by its credential
pre-scan. The recovered source is in open pull requests and is **not on `main` until they merge**. Per-file hashes
and transforms are in `integrations/hermes/history/prod/provenance/*.json` and
`integrations/hermes/home/variants/prod-lilith-01/PROD-RECOVERY.json` on those branches.

Status vocabulary:
- `FOUND_ON_PROD`
- `EXPORTED_AND_HASH_VERIFIED`
- `SANITIZED_FOR_GIT` (named private values replaced by placeholders; Git bytes differ from PROD)
- `IN_OPEN_PR`
- `MERGED_TO_MAIN`
- `PRIVATE_RUNTIME_ASSET`
- `CREDENTIAL_EXCLUDED`
- `HISTORICAL_DUPLICATE` (already in Git, or identical to another recovered file)
- `STILL_VM_ONLY`
- `UNKNOWN`

Current preservation: PROD files are on `lilith-01` and in GCP snapshot `lilith-01-preserve-20261027`; DEV files are
on `lilith-dev-01` and in `lilith-dev-01-preserve-20261027`. A disk snapshot is crash-consistent recovery, not a
source archive. The exact recovered PROD bytes are also kept in owner custody.

## PROD `lilith-01` (`~` = `/home/lilith/.hermes`)

Change sets:
- A = [#272](https://github.com/rpahasara/lilith-os/pull/272) Working Memory and Router
- B = [#273](https://github.com/rpahasara/lilith-os/pull/273) career
- C = [#274](https://github.com/rpahasara/lilith-os/pull/274) automation
- D = [#275](https://github.com/rpahasara/lilith-os/pull/275) history

| # | Deployed artifact | Full SHA-256 | Status | Git path (open PR) |
|---|---|---|---|---|
| 1 | `~/lilith_router/world_context.py` (91,351 B): Working Memory and seven-lane wiring | `46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104` | EXPORTED_AND_HASH_VERIFIED, byte-exact, IN_OPEN_PR (A) | `integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py` |
| 2 | `~/lilith_router/world_context.py.bak.*` (8 stages) and `_patched/world_context.py` | per file in provenance | 8 distinct stages EXPORTED_AND_HASH_VERIFIED, IN_OPEN_PR (A); `_patched/world_context.py` is a HISTORICAL_DUPLICATE of the s12fix stage | `integrations/hermes/history/prod/world_context/` |
| 3 | `~/lilith_router/router.yaml` (every lane live) | `7d14b571abc73766782fbe2d534e85a4fb1fef628592b478b9747f7c76639586` | EXPORTED_AND_HASH_VERIFIED, SANITIZED_FOR_GIT (Discord channel id), IN_OPEN_PR (A); exact bytes restored from a custody value by `assemble_prod_complete.py` | `integrations/hermes/home/variants/prod-lilith-01/router.yaml.tmpl` |
| 4 | `~/lilith_router/_patched/` | per file in provenance | `config.py`, `gateway_integration.py`, `test_planning.py` IN_OPEN_PR (D); `planning.py`, `planning_capabilities.py` HISTORICAL_DUPLICATE (on `main` under `docs/architecture/slice-12/`); `router.yaml` HISTORICAL_DUPLICATE of the `golive12` backup | `integrations/hermes/history/prod/lilith_router/_patched/` |
| 5 | `~/lilith_router/tests/*`: 13 test modules + `__init__.py` | per file in the PROD audit | 7 IN_OPEN_PR (A); 6 HISTORICAL_DUPLICATE (on `main` under `docs/architecture/slice-*`); superseded `.bak` tests in D | `integrations/hermes/home/variants/prod-lilith-01/lilith_router/tests/` |
| 6 | `~/lilith_router/CURRENT_STATE.md` | `1a4bfbbf0212fffa8c892a2790b521760ae0725ba63113cb7cadf6f486612de2` | SANITIZED_FOR_GIT (channel id), IN_OPEN_PR (D); its 10 cumulative backups are kept in owner custody only | `integrations/hermes/history/prod/lilith_router/CURRENT_STATE.md` |
| 7 | `~/lilith_router/tools/probe_groq.py` | `0b0a184d108c936d52a7a32ac790d484792e54b372d58ca51b04fb8f55d58d31` | IN_OPEN_PR (D), inert history (never run) | `integrations/hermes/history/prod/lilith_router/tools/` |
| 8 | `~/lilith-os/apps/career/*.py` (10) | per file in provenance | IN_OPEN_PR (B); 4 SANITIZED_FOR_GIT (owner mailbox addresses), 6 byte-exact | `integrations/hermes/history/prod/hermes-home/lilith-os/apps/career/` |
| 9 | `~/automation/productivity/*.py` and backups, `prompts/morning_brief.txt`, `config.json` | per file in provenance | IN_OPEN_PR (C), byte-exact; `logs/`, `state/`, `followups/` are PRIVATE_RUNTIME_ASSET | `integrations/hermes/history/prod/hermes-home/automation/productivity/` |
| 10 | `~/lilith-os/api/app.py.bak.*` (18) | per file in provenance | 11 IN_OPEN_PR (D), including the hand-patched `743a804a…`; 7 HISTORICAL_DUPLICATE (five copies of `bb0a4139…` = repo `519b309`, `c20ba90e…` already in Git history, and one copy of an identical pair) | `integrations/hermes/history/prod/hermes-home/lilith-os/api/` |
| 11 | `/home/lilith/*.py` 2026-08-26 prototypes (8) | per file in provenance | IN_OPEN_PR (D) | `integrations/hermes/history/prod/home-lilith/` |
| 12 | Router module `.bak` lineage and the 08-26 checkpoint | per file in provenance | non-redundant files IN_OPEN_PR (D); duplicates of slice files are HISTORICAL_DUPLICATE | `integrations/hermes/history/prod/lilith_router/` |
| 13 | systemd units (`hermes-gateway`, `lilith-os-api`, 5 watcher service/timer pairs) | per file in provenance | IN_OPEN_PR (C), byte-exact | `integrations/hermes/history/prod/systemd/` |
| 14 | `~/lilith_router/checkpoints/run.py.20260826-122342` (1,519,743 B) | `dba8b053183a1c01bc4abb546d6f4d7f859dffaa7baa3e71e662e3c2e77851ff` | FOUND_ON_PROD, withheld by the credential pre-scan (one `keyed_literal` match): STILL_VM_ONLY | none until a separately approved review of that match |
| 15 | `~/lilith_router/checkpoints/config.yaml.20260826-122342`, `~/config.yaml` (Hermes PROD) | not hashed (live) | PRIVATE_RUNTIME_ASSET (runtime configuration); template only by policy; the live `config.yaml` was not read | owner custody / future template |
| 16 | `~/SOUL.md` `d082db5a…`, `~/memories/USER.md` `6d7804ef…`, SOUL backups | as listed | PRIVATE_RUNTIME_ASSET: **never in Git** (ADR-0008, ADR-0016); not read | none |

CREDENTIAL_EXCLUDED, never read and never part of a source export: `.env`, `auth.json`, `*.env`, Google tokens, authority `*.key` files, `state.db` and
other databases. These belong to separate custody and backup domains.

PROD Hermes code itself is not a gap: upstream `f293e72` + `integrations/hermes/patches/prod-lilith-01.patch`
rebuild every patched file byte-exact. The PROD virtualenv (111 distributions, not built from a lock) is not
reproducible exactly; that is a dependency gap, not a source gap.

## DEV `lilith-dev-01`

| Artifact | Kind | Status |
|---|---|---|
| `/etc/hermes-provider-gate-dev/gate.json` with the live client token, the Groq project key, the console token | credentials | host-only **by design**; never in Git |
| `60-origin-executor.conf` drop-ins (×3), `/etc/hermes-forget/executor.json`, `/etc/hermes-gateway-dev/critical.sha256` | generated configuration | regenerable from `integrations/hermes/release/dev-f9c2/bin/install_f9c.sh`, `pin_critical.sh` and the FM-2 transition tooling |
| `/etc/lilith-os-dev/canonical-runtime.json`, owner registration | host configuration | host-only; protected by the DEV snapshot and the transition records |
| The authoring diff that produced DEV `gateway_integration.py` `5ce4bbd4…` | source lineage | the result bytes are in Git; the authoring patch was never kept as a file |
