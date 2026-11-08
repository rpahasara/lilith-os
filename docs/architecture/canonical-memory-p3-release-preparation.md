# Canonical memory P3: release preparation (offline, 2026-11-04)

Status: PREPARED, not executed. No merge, no DEV transition or restart, no PROD contact, no key, no provider request.
Stacked on P2 (draft rpahasara/lilith-os#314).

## 1. Stack and CI

| PR | Head | Base | CI | What it carries |
|---|---|---|---|---|
| #312 | `f919fc8` | `main` (`75ca0db`, unmoved) | 4/4 green | read route, D-2 service, importer, plan |
| #313 | `724da03` | #312 | 4/4 green | grant v3, PROD router overlay, plan updates |
| #314 | `f4cc8ee` | #313 | 4/4 green | the OWNER_PROD profile (P2) |
| P3 (this branch) | — | #314 | not opened | ceremony tools, transition contract, compat check, this record |

The stack is linear on main. Every merge is DEPLOY_REQUIRED, a routine DEV Core API deploy. #314 is the only one that
changes the signer release payload. The PR's "LILITH DEV deployment" check is a gate only (`DEV_DEPLOYMENT=NONE`).

## 2. OWNER_PROD ceremony tooling (explicit DEV/PROD separation)

The DEV ceremony tools (`lilith_authority_keygen_dev.py`, `lilith_authority_owner_dev.py`, `trackb_kpan_keygen.py`)
are **byte-identical** to main; a test compares them with `75ca0db`. Closed DEV ceremonies (M-B1, M-B3, M-B7, M-B8,
E-19) pin them. The production tools are separate, under `services/owner-memory-control/tools/`, source-only and never
installed:

| Tool | Forms | Key / document |
|---|---|---|
| `owner_prod_keygen.py` | `actor`, `witness` | K-ACT `prod.owner-prod.actor.1`, K-WIT `prod.witness.owner-prod.1`; the DEV tool's own generation, systemd-creds pipe and exclusive writes |
| `owner_prod_kpan_keygen.py` | `keygen` | K-PAN `kpan.owner-prod.01`, Privacy environment `OWNER_PROD`; its own instance of the DEV tool |
| `owner_prod_owner_tool.py` | `root-keygen`, `registry-v1`, `witness-anchor`, `reproduce` | K-ROOT `prod.registry-root.owner-prod.1`, the `prod` registry, anchor and genesis; its own instance of the DEV tool |
| `privacy_checkpoint_tool.py` (unchanged) | `keygen --environment OWNER_PROD --key-id kpck.owner-prod.01` into a NEW custody folder | K-PCK |

**No accidental use.** Both host keygens refuse with `PROD_MACHINE_ID_NOT_PINNED` until a reviewed commit pins the PROD
machine ID from a read-only observation. After that, they still refuse on any host other than `lilith-01` with that
ID and the root-installed OWNER_PROD `deployment.json`. The DEV machine ID is refused even if pinned by mistake.

**One shared-module fix was needed (found by the chain test).** `pr1_bootstrap.WitnessKeyPublicationV1` accepted only
`DEV_SYNTHETIC` publications. It now also accepts `OWNER_PROD`, but only for `prod` keys, and refuses either label on
the other environment. DEV bytes are unchanged, and `SHARED_HASHES` was re-pinned once.

## 3. No fallback (evidence: `test_owner_prod_ceremony`, `test_owner_prod_profile`)

| Attempt | Result |
|---|---|
| a PROD form on the committed source | `PROD_MACHINE_ID_NOT_PINNED` |
| a PROD form on the DEV host, a DEV-pinned machine, no or wrong `deployment.json` | `NOT_PROD_HOST`, `DEPLOYMENT_NOT_OWNER_PROD`, `DEPLOYMENT_INVALID` |
| a DEV K-ACT publication into a PROD registry | `PUBLICATION_SCOPE` |
| a DEV K-WIT into a PROD anchor | `PUBLICATION_SCOPE` |
| a `test-only.` root claiming `prod` | `GENESIS_REGISTRY_UNVERIFIED` |
| a PROD registry under a `dev` context | not verified |
| DEV label on a PROD witness key, PROD label on a DEV key | refused |
| a DEV signer profile with `prod` values, or the reverse | `ProfileError` (P2) |

The full PROD chain verifies under a `prod` context: K-ACT + K-WIT → K-ROOT registry → anchor → genesis candidate.

## 4. Rehearsal attested build and transition contract

| Item | Value |
|---|---|
| Rehearsal source | P3 head `706873c` (build mechanism of FM-2: `build_authority_dev_release.py`, FM-2 wheelhouse) |
| A (Windows) = B (WSL) | archive `f22bf71b…` (5,391,581 B), manifest `b136366b…`, inspection identity `6f5d1c04…` |
| Delta vs installed `d82f7da` (archive `9588c85b…`) | **exactly 18 payload members + the release manifest**; none added or removed; units, tmpfiles, CLIs, lock, wheels identical; layout v3 unchanged |
| Witness members in the delta | `lilith_recovery_witness/credential.py`, `server.py`, so the witness restarts from NEW |
| Contract | `tools/owner_prod_signer_upgrade.py` (`UPGRADE_OWNER_PROD_PROFILE_DEV_SYNTHETIC`): OLD = FM-2 NEW, the 18-member `PAYLOAD_DELTA` proven against the real archives and against git, `NEW_RELEASE = None` so `ready_to_transition()` is False until the merge build is pinned |

At P3 execution, the stage tool and the operator are derived from FM-2's (`fm2_release_stages.py`,
`fm2_operator.py`) by the same pinned transform FM-2 used (`tests/fm2_transform.py`). The renames go to this
contract, plus three block changes: the ending signer and witness incarnations (from one fresh read-only DEV status),
the contract pin, and the 18-member wording. That lands as one control-only PR after the merge build, because the
incarnations and NEW exist only then.

## 5. DEV transition runbook (FM-2 order; each mutating step its own owner go)

1. **Read-only status.**
   - Boot `cb0d71da` (or re-unlock Privacy first).
   - Privacy READY; FORGET idle.
   - Signer and witness incarnations; installed `d82f7da` only; DR-5 baseline.
   - `cm1_window.sh check` baseline digests.
2. **Merge** the stack in order (the owner's merges). Then the routine DEV Core API deploy, and post-deploy DR-5
   `EQUAL`.
3. **Build** NEW from the final merge commit, A = B, and attest. Then the contract PR, control-only, pinning NEW and
   deriving the stages and operator.
4. **The ladder:**
   - transfer;
   - F0 preflight `EXACT`;
   - stage, then F1;
   - signer stop (F2) and witness stop (F3);
   - select (F4): `current` points at NEW;
   - witness start from NEW, with the K-WIT and K-PAN loads (F5), then accept;
   - signer start from NEW, with the K-ACT load (F6), then accept;
   - retire OLD (F7).
5. **Host tree and Privacy:**
   - rebuild the DEV First Memory host tree from the merge (its modules changed);
   - `install_f9c.sh --repin` (the FORGET executor's frozen copy includes `privacy_forget_runner`);
   - Privacy status READY.
6. **Acceptance:**
   - DR-5 re-derived;
   - `cm1_window.sh check`: every no-write digest equal to step 1, apart from the expected release and incarnation
     lines;
   - context probe: `lilith_os` gets both memories, `telegram` gets the codename only;
   - one bounded recall turn, by separate approval (one provider request).

**Rollback.**
- **Before F4:** stop. OLD is still `current`; restart the stopped units from OLD.
- **From F4 to F6:** select OLD again (`current` → `d82f7da`) and start both units from OLD; the ladder's own return
  step.
- **After F7:** OLD is retired. A rollback then needs the restage of `d82f7da` from its archive `9588c85b` (still
  held in the FM-2 build evidence).

**Privacy READY:** a transition doesn't reboot, so the boot marker stays valid. A reboot at any point means the
three-step owner unlock before any recall.

**No writes:** canonical (L04) DB, Privacy DB, Core API DB, Hermes `memories/` and request dumps must stay equal. The
signer ledger, witness and broker state are compared with step 1. Any difference beyond what the FM-2 ladder recorded
on DEV for the same steps is a STOP for owner review.

## 6. PROD compatibility (prepared, not run)

`integrations/hermes/overlays/prod-canonical-memory-context/prod_compat_ro.sh` is read-only and content-free. It
checks three things:
- **The bases the overlay patches are as deployed:** router `99fe9064…`, lean reply `5c4c2d1f…`, config `69e839ad…`.
- **The feature is absent** (default OFF): no `canonical_memory.py` or settings, no `deployment.json`, authority
  release, context socket or grant.
- **The store shapes** the inert install migrates (counts and integrity), whether the Telegram allowlist exists (as a
  count only; the ID is never printed), and that the gateway and Core API units are untouched.

It also records digest prefixes for the console adapter, Core API `app.py` and Hermes `run.py`. Its first run is the
read-only start of the PROD window (P5), by separate approval. A FAIL means rebase before anything else.

## 7. PROD key-ceremony checklist (P4; owner decisions open)

**Owner decisions, open, not made here:**
1. **The owner credential's relying party:** the RP id and `https://` origin (a domain the owner controls; never
   `.invalid`) and the owner principal string. These go into `LILITH_OWNER_REGISTRATION_PROD`.
2. **Where PROD K-ROOT is generated and held** (the DEV K-ROOT lived on a phone through the Termux bundle), its
   passphrase custody, and its offline backup.
3. **Where the PROD K-PCK custody folder lives** (a new folder, never the DEV one) and its offline backup. The DEV
   K-PCK backup was never made; PROD must not repeat that.
4. Whether the PROD owner credential is a new WSL software credential or a hardware authenticator.

**Prerequisites before any key exists:**
- [ ] Stack merged; P3 DEV transition accepted (DEV runs the same release).
- [ ] PROD machine ID pinned by a reviewed commit in both host keygens (equal; a test checks).
- [ ] PROD compat check PASS.
- [ ] Fresh PROD snapshot READY.
- [ ] PROD authority release staged inert, with `deployment.json` (OWNER_PROD) and `LILITH_ENV=prod` units. The
  installer change for this is P5 work and is not prepared here.

**Ceremony order** (each its own go; nothing re-runs; every output is a public publication):
1. K-ROOT, on the workstation (`owner_prod_owner_tool.py root-keygen`).
2. K-ACT, on PROD (`owner_prod_keygen.py actor`).
3. K-WIT, on PROD (`owner_prod_keygen.py witness`).
4. K-PAN, on PROD (`owner_prod_kpan_keygen.py keygen`).
5. Registry v1 (`registry-v1`, policy `policy.owner-prod.v1`), the anchor (`witness-anchor`) and the off-host
   reproduction (`reproduce`).
6. The owner credential and the PROD owner registration.
7. K-PCK (`privacy_checkpoint_tool.py keygen --environment OWNER_PROD --key-id kpck.owner-prod.01`).
8. Verified offline backups of K-ROOT and K-PCK, before anything depends on them.

**Never:** a DEV key, custody folder, registry or credential on PROD; a key printed or copied; a re-run of a consumed
step.

## 8. Known limitations (no new tasks created)

- The PROD installer mode (`deployment.json`, `LILITH_ENV=prod` units) is not built yet. It belongs to P5.
- No PROD K-ACT rotation in RC1.
- D-6 V1 HMAC limits apply.
- Ready lane replies don't see the note.
- Telegram and console recall are validated offline only.
- Service, user and path names keep their `-dev` spelling on PROD.
