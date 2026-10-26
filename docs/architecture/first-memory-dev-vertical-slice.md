# First Memory — DEV Vertical Slice (Source)

Status:

- **SOURCE ONLY.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE`. Base: main `45fc250` (PR #257: RR-39 governed
  issuance + release layout v3).
- Nothing here enrolls an owner, signs, migrates a DB, installs a release, changes a service, or creates a memory.
- **Not claimed:** a real human identity, a hardware authenticator, biometric user verification, PROD, or a DR-5 EQUAL.

## 1. What closes the slice

One DEV project-codename memory, admitted to canonical L04 with owner-authorized evidence from the real signer, and
recalled from canonical storage in a different conversation.

```text
conversation turn ──offer──▶ first_memory_conversation (no write)
owner device ──assertion over the exact challenge──▶ host
host ──ISSUE_OWNER_EVIDENCE + hold snapshot──▶ signer (verify owner proof, PREPARE/CONSUME/ISSUE, witness)
host ──L04 V2 adapter──▶ RESERVE (signer) → L04 apply + link (one txn) → CONFIRM (signer)
new conversation ──recall──▶ accepted read (owner proof → evidence → registry → link → CONSUMED use)
```

## 2. Components

| Area | Change |
| --- | --- |
| Signer runtime (`server.build_core`) | Constructs the RR-39 `IssuanceHandlerV1` with fixed-path readers only: the signer view, the durable ledger, the witness client, the systemd-delivered K-ACT (loaded per request, never retained) and the root-installed owner registration (read per request). A missing input refuses that request explicitly. HEALTH / self-view are byte-compatible: always `NOT_READY` (the signer can never establish its own readiness) |
| Signer profile | `dev_runtime_profile()`: K-ACT `test-only.dev-synthetic.actor.b1b3d.1`, `policy.dev-synthetic.v1`, authority domain `authority.dev-synthetic.memory`, logical owner `owner.dev-synthetic.v1` |
| Owner registration | `/etc/lilith-owner-proof-dev/owner-registration.json` (`root:root 0644` in `0755`): the DEV_SYNTHETIC owner identity, owner-proof settings and the registered owner PUBLIC credentials. Outside the frozen installer's exact `/etc/lilith-authority-dev` listings; readable by the signer under `ProtectSystem=strict`. Strict parser: `lilith_authority_host.inputs.read_owner_registration` |
| Evidence-use transport | `RESERVE_EVIDENCE_USE`, `CONFIRM_EVIDENCE_USE`, `ABANDON_EVIDENCE_USE` (each under the same readiness gate as issuance, with the complete root hold snapshot, ledger exactly at the witness, released only after `RECORD_LEDGER_ADVANCE`) and the read-only `LOOKUP_EVIDENCE_USE`. Writer `DurableAuthorityLedgerV1.append_use`; single use is the shared journal's (`EVIDENCE_ALREADY_USED`, `USE_NOT_RESERVED`) |
| Action binding | The signer's ISSUE journal op also records the challenge's `actionDigest` (hash-chained). A RESERVE must name exactly that action; LOOKUP reports it, as the accepted read requires |
| Root clients | `lilith_authority_root.clients.signer_issue` / `signer_use` |
| L04 migration | `owner-memory-control/tools/first_memory_l04_migration.py`: read-only `plan`; `apply` = verified online backup (`backup.create_backup`, role cognitive), then exactly `l04_v2_adapter.LINK_DDL` in one IMMEDIATE transaction, re-verified. One empty table; nothing else |
| Governed tuple + config | `GOVERNED_TUPLE` = `SYNTHETIC_PROJECT_CODENAME_FACT / project.synthetic / codename`, capability `canonical_memory.project_codename.mutate` (never the suppressed First Interaction identity). Creation is governed by the server-owned `lilith_memory.config` file `/etc/lilith-first-memory-dev/canonical-config.json`: absent, malformed, `canonicalLtmEnabled=false` or without the capability ⇒ `MEMORY_CREATION_NOT_AUTHORIZED` before any signer call |
| Runtime host | `owner-memory-control/tools/first_memory_dev_host.py`: a narrow owner-run host, separate from `/os/conversation`, Hermes and the UI. It composes the accepted `first_memory_conversation` with the F9c2 Privacy DB and current-boot freshness gate, the F9c2 cognitive DB, the registration, the installed K-ROOT trust anchor and registry, and the signer transport. It holds **no** root privilege: it refuses to run with any uid or gid 0 and reaches the signer only through the root bridge on inherited fd 3, sending no hold snapshot. A fresh composition per turn |
| Root bridge | `lilith-authority-ledger-dev first-memory <remember\|recall> <session>` (`lilith_authority_root.cli`, release code only, root). It refuses unless the fixed host tree `/opt/lilith-first-memory-dev/current` and its parents are root-owned, not group/other-writable and symlink-free; forks the host and drops it **permanently** to `lilith` (real, effective and saved uid/gid; no supplementary groups; verified, and regaining uid 0 must fail) before exec of the release venv Python with `-I`; never imports host code. Over one inherited socket pair it forwards only `ISSUE_OWNER_EVIDENCE` and the four evidence-use operations (each re-validated by the signer's own frame parser), refuses any caller `holdStore`, and adds the complete hold-store snapshot it reads itself. No listener, path, command or file argument |
| Owner device | `owner-memory-control/tools/first_memory_owner_credential_dev.py`: `create` (a P-256 software credential; the private key stays in a 0600 file on the owner device), `assert` (one assertion over a printed challenge), `registration <release-sha> <public>…` (verifies each proof of possession; prints the root-installable document) |
| Release layout | Unchanged (archive layout v3). The payload moves by exactly: 10 changed members (`lilith_authority_dev/{core,credential,ledger,protocol,profile,server}.py`, `lilith_authority_host/{inputs,paths}.py`, `lilith_authority_root/{clients,cli}.py`) and the 2 v3 additions (`issuance.py`, `lilith_owner_memory/verifier.py`), pinned by `test_rr39_layout_v3` |

## 3. Owner authentication: what this does and does not prove

The relying party is the synthetic `owner.lilith.invalid`, so no browser or platform authenticator can serve it. The
owner credential is a **software authenticator**: its user-presence and user-verification flags are self-asserted by
the owner tool, and possession of the device key file is the only factor. The signer verifies a real WebAuthn
signature by a registered credential over the exact challenge (single use, 60-second window), so an admitted memory
is owner-authorized **in the DEV_SYNTHETIC sense**: the holder of the owner-device key approved exactly that value.

Before any memory may be called owner-authorized in the human sense, a separate decision must add: a real relying
party and origin, a platform or hardware authenticator with genuine user verification, its attested enrollment, and a
non-synthetic owner principal. None of that is in scope here, and nothing weakens the existing checks to fit it.

## 4. Proof (local, offline)

`authority-dev/tests/test_first_memory_dev_vertical.py` (9, real signer core over its frame protocol, real host,
real L04 / Privacy / freshness):

1. no registered owner, a withdrawn registration, no consent, a foreign authenticator, an unregistered credential,
   a HELD custody hold, or disabled creation ⇒ no admission and no journal entry;
2. valid governed evidence and consent ⇒ exactly one L04 admission and one link; signer journal
   `GENESIS, PREPARE, CONSUME, ISSUE, RESERVE, CONFIRM`;
3. a fresh session and composition recall it from canonical storage;
4. with conversation history removed, recall is unchanged;
5. a new unverified boot, a restored pre-FORGET Privacy store, the stale Core API Privacy path, a non-authoritative DB
   path, a replayed assertion, a second RESERVE and an unreserved CONFIRM are each refused explicitly;
6. the historical First Interaction FORGET stays held and its identity cannot be composed;
7. the signer's HEALTH stays `NOT_READY`; recovery and use operations without their handlers refuse.

The end-to-end flow above runs through the real root bridge on a socket pair. `authority-dev/tests/test_first_memory_bridge.py`
(13, as root with the system `nobody` account) proves the boundary: a dropped process cannot regain uid 0 by any
setuid/seteuid/setresuid/setgid/setgroups call; a host tree another principal can change (writable file or directory,
symlink, wrong owner) is refused and never executed; the forked host runs with all ids unprivileged and reaches only
the bridge; malformed, duplicate-key, extra-field, non-allowed (HEALTH, recovery, SIGN) and caller-`holdStore`
requests never reach the signer; writes carry root's own, freshly read hold-store snapshot.

## 5. Shortest DEV activation (future; every step owner-authorized unless marked read-only)

1. Merge; build the release from the merge commit with the v3 tooling (A = B, attested), and pin it.
2. Release transition: stage → signer stop → select → signer start (K-ACT load) → retire. The witness payload is
   unchanged, so the witness keeps running.
3. Read-only: confirm the governing custody hold is RELEASED under FULL_READINESS (else the existing release ceremony).
4. Owner device: `create`; then `registration <release-sha> <public>`.
5. One root session: install the registration file; stage the exact-SHA source tree for the host at
   `/opt/lilith-first-memory-dev/current` (root-owned, `0755`/`0644`); as `lilith`, run the L04 migration `apply`
   (backup first). Creation is still disabled.
6. Per boot: the existing Privacy unlock (freshness READY).
7. Authorize creation: write the canonical config (`canonicalLtmEnabled=true` + the codename capability).
8. As root: `lilith-authority-ledger-dev first-memory remember <session>` (the owner signs the printed challenge within
   60 s), then `… first-memory recall <new-session>` in a new invocation. Optionally set creation back to disabled.
