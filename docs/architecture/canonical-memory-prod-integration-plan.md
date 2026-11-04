# Canonical memory: PROD integration plan (planning only, 2026-11-04)

Status: PLANNING. This record authorizes nothing. PROD (`lilith-01`) was not contacted while it was written. It
builds on the [PROD release plan](canonical-memory-prod-release-plan.md) (P0–P8), the
[P3 preparation](canonical-memory-p3-release-preparation.md) and the
[P3 DEV transition](canonical-memory-p3-dev-transition.md). Where this record differs from them, the change is named
and argued.

    upgrade the existing LILITH;  never replace her identity;  never rewrite her memories;  nothing activates unasked

Evidence classes used below: **V** = verified (source in this repository, or a recorded read-only observation, with
its date); **A** = assumption; **M** = missing evidence (§6 lists the read that closes it).

## 1. Existing PROD architecture

| Component | State | Class |
| --- | --- | --- |
| Host | `lilith-01`, GCE e2-small (2 shared vCPU, 2 GB RAM, 20 GB disk, no swap assumed), `asia-southeast1-b`; OS Login over IAP; one boot disk; daily snapshot schedule `lilith-01-daily` (30 days) attached 2026-11-01 | V (records 2026-11-01/02) |
| Hermes gateway | `hermes-gateway`: NousResearch/hermes-agent `f293e72` (v0.20.5) + 15B2a containment + Router V2 seam; Python 3.11 venv; `run.py` `31fef97d` (P1 persist fix); channels Telegram, Discord, `lilith_os` (console). WhatsApp disconnected and out of scope | V (2026-10-22, 11-03) |
| Router (`~/.hermes/lilith_router`) | Router V2 + seven Cutover 2 lanes; `gateway_integration.py` **`4db8bb58…`** (C2 `99fe9064` → T4 `7f83cf9c` → T4 wording `4db8bb58`, deployed 2026-11-04 07:36Z); lean social `social_lean.py` `5c4c2d1f` (Groq Qwen); `world_context` `ebe62158`; social guard `3a0906b5`; `router.yaml` lanes live | V (deploy records 2026-11-03/04) |
| Identity | `SOUL.md` (~32 KB) and `memories/USER.md` (1,241 B, static since 09-06) loaded by Hermes; `MEMORY.md` empty; `memories/{decisions,projects,relationships,tasks}/` notes | V (2026-10-27, 11-02) |
| Conversation history | Hermes `state.db` (3,600+ messages; all channels persisted since P1) | V (2026-11-03) |
| Core API | `lilith-os-api`: single-file FastAPI `app.py` `53dfae2a` (Cutover 1), reads/writes enforced, loopback trusted; `lilith.db` (World Model 31 beliefs, goals, CRM, drafts). No `lilith_memory` package. PROD deploy workflow `disabled_manually` | V (2026-11-01) |
| Cognitive store | `lilith-os/data/cognitive_memory.db`: 15B1/15B2a schema v1, L04 **0 rows**, L18 **3 SHADOW** candidates; `privacy_governance.db` Privacy **V1**, 0 requests; two 15B2a 32-byte keys (`actor_authority.key`, `privacy_authority.key`) | V (2026-10-27, 11-04) |
| Canonical-memory authority | **none**: no signer, witness, broker, anchor, freshness gate, context service, host tree or grant | V (2026-11-04 inventory) |
| Timers | morning brief (daily), gmail / career / meeting-prep watchers; career-watcher and meeting-prep fail every run (OAuth `invalid_grant`) | V (2026-11-03) |
| Open behaviour exception | **E-T4**: "what am I working toward right now?" is still misread (owner: no further PROD change for it now) | V (2026-11-04) |

## 2. The canonical-memory components and their dependencies

What DEV runs (validated end to end at F7 on 2026-11-04, release `88a1168`):

```
Hermes turn ─(router seam: canonical_memory.owner_channel → note)─> context socket (root, per connection)
   └─> canonical_context_service ─> release root CLI `first-memory-context` ─> First Memory host tree
          ├─> L04 canonical store + owner ledgers (read)          ├─> Privacy freshness gate (boot-bound READY)
          └─> signer (`clients.signer_recovery`, HOLD store)        └─> grant file (channel scope, expiry)
admission / FORGET (owner CLI) ─> signer (K-ACT) + witness (K-WIT, K-PAN anchor) + owner credential
                                  + owner proof naming an allowed broker release (`verifier.py` BROKER_RELEASE_NOT_ALLOWED)
```

| Dependency | Fact | Class |
| --- | --- | --- |
| Recall needs a **running signer** | `cli.context_response` calls `clients.signer_recovery` and reads the HOLD store | V (source) |
| Recall needs Privacy **READY** | the context service answers UNAVAILABLE without the boot-bound marker (fail closed) | V (DEV, D-4) |
| Admission / FORGET need a **broker release** in the owner registration | `contracts.py` requires a non-empty `broker_releases`; `verifier.py` refuses a proof whose `brokerRelease` is not listed | V (source) |
| Whether admission needs the broker **process** running on PROD | not established | **M** (offline source check, R3) |
| Core API involvement | none for the read route: the host tree carries its own `lilith_memory` modules; Privacy host steps can run from the authority release venv | A (to prove offline, R3) |
| Router change | one module (`canonical_memory.py`) plus a 4-hunk patch to `gateway_integration.py`; `gateway/run.py` byte-identical | V (prepared overlay) |
| Overlay base | prepared against `99fe90649e316ef992db7c05575c19eafe56e703d505f44f39c5577903fe9587`; PROD now runs `4db8bb58da3fbdef80fb550c74709bb3ea62c605afadec56aa96b28d2568ca8b`. The patch **applies cleanly** to `4db8bb58` (offsets 53–57 lines, dry run 2026-11-04); its effect on the new `native_self_status` route is untested | V / **M** |
| Resource headroom | DEV (same e2-small) runs signer 39 MB, witness 37 MB, broker 18 MB RSS, with 1.28 GB available beside its gateway (100 MB). PROD gateway was ~245 MB in October; PROD free memory now unknown | V (DEV 2026-11-04) / **M** (PROD) |
| Python | the authority release builds its venv with `/usr/bin/python3` from **cp312** wheels; DEV is Python 3.12. PROD's system Python is unknown (Hermes uses its own 3.11 venv) | V / **M** |
| Service principals | DEV uses dedicated users and groups (uid/gid 995/985 recorded); PROD collisions unknown | **M** |

## 3. Compatibility requirements and conflicts

| # | Finding | Effect | Resolution |
| --- | --- | --- | --- |
| C-1 | **`PROD_PATHS` (P2) point at PROD's live `cognitive_memory.db`, `privacy_governance.db` and the two existing 15B2a keys** | as written, the PROD install would migrate LILITH's live stores (v1 → v3, V1 → v2) and give the existing 15B2a keys a new authority role | owner decision **D-7** (§4.5); recommended: an isolated canonical store, existing stores and keys untouched |
| C-2 | the router overlay base is `99fe9064`; PROD runs `4db8bb58` | `prod_compat_ro.sh` would FAIL its router pin (correctly); the overlay must be rebased | rebase the overlay and its tests onto `4db8bb58`, re-run the Cutover 2 corpus with the feature off and add the `native_self_status` route to the merge tests (R3) |
| C-3 | the PROD installer mode does not exist | no inert PROD install is possible today | build it offline (R3): `deployment.json` OWNER_PROD, `LILITH_ENV=prod` units, PROD paths, context units with no grant, and its reviewed return |
| C-4 | `owner_prod_keygen` refuses until `PROD_MACHINE_ID` is pinned | correct, by design | one owner-approved read of `/etc/machine-id`, then a reviewed pin commit |
| C-5 | cp312 wheels vs PROD system Python | an inert install fails at venv creation if PROD lacks Python 3.12 | the audit reads it; a mismatch means a rebuilt wheelhouse and a new attested build, not a PROD Python change |
| C-6 | per-boot Privacy unlock (D-4) | after any PROD reboot, personal recall is off until the owner unlocks | accepted (D-4); the context socket must be **enabled** on PROD |
| C-7 | the Hermes gateway exits `failed` on SIGTERM | any window that restarts it must accept `inactive\|failed` with MainPID 0 (Cutover 2 lesson) | reuse the C2 `stopped()` rule |
| C-8 | ready lane replies (Reasoning, Planning, Ethics) don't see the note | accepted RC1 limitation | documented |
| C-9 | D-2 scope | FORGET covers canonical records only; Telegram and `state.db` copies are never erased | documented; never claimed otherwise |

No conflict was found with the providers (Groq lean route, openai-codex Sol), the World Model, goals, career or the
timers: none of them is read or written by any canonical-memory component.

## 4. Integration decisions (options, trade-offs, recommendation)

### 4.1 Installation mode

| Option | For | Against |
| --- | --- | --- |
| **A. Staged in-place on `lilith-01`** (inert install → Privacy activation → console read route → Telegram DM) | the exact shape validated on DEV (same e2-small, same units, same ladder); no new network trust boundary; every step returns independently; nothing user-visible until the read-route step | PROD runs more root services; per-boot unlock |
| B. Sidecar VM for the authority services, recall over the network | isolates keys from the gateway host | a new host, network path and trust boundary that DEV never validated; doubles snapshot and recovery scope; recall needs a network client the context service does not have |
| C. Wait and keep DEV-only | zero PROD risk | LILITH never uses canonical memory in real conversations |

**Recommended: A**, staged and inert first. It is the only option that ships what DEV validated without new
infrastructure.

### 4.2 Relying party (owner credential)

| Option | For | Against |
| --- | --- | --- |
| **A. A domain the owner controls** (RP id = that domain, origin `https://<domain>`) | stable for life; `.invalid` is refused by design | the owner must own one |
| B. A subdomain of an existing owner domain | same, without a new purchase | ties LILITH's authority to that domain's future |

Recommended: A or B, owner's choice (**D-8**). The principal string `user:<name>@<domain>` is part of every proof,
so choose once.

### 4.3 PROD identity and machine-ID pinning

One owner-approved read of `/etc/machine-id` (the audit itself prints only its SHA-256), then a reviewed commit pins
it in both PROD host keygens (a test proves they are equal). `deployment.json` (`{"environment":"prod","profile":
"OWNER_PROD","schemaVersion":1}`) selects the profile; `LILITH_ENV=prod` must match. The DEV host never gets
`deployment.json` (checked at every DEV acceptance). **D-9**: approve the read.

### 4.4 Credentials and key custody (all new; D-1 already decided: no DEV key ever)

| Key | Where (recommended) | Backup | Decision |
| --- | --- | --- | --- |
| K-ROOT (registry root) | owner workstation or phone, offline; passphrase held by the owner | one verified offline copy | **D-10** (location) |
| K-ACT, K-WIT, K-PAN | generated on PROD by the PROD keygens, systemd credentials (as DEV) | not exported (re-key on loss) | fixed by design |
| K-PCK (Privacy checkpoint) | a new WSL custody folder, never the DEV one | one verified offline copy **before** activation (DEV never made one) | **D-11** (location) |
| Owner credential | a new WSL software credential (as DEV) or a hardware authenticator | per form | **D-12** (form) |

The two existing 15B2a keys stay untouched under the recommended D-7.

### 4.5 Existing memory data (D-7, new)

| Option | For | Against |
| --- | --- | --- |
| **A. Isolated canonical store** (a new `lilith-os/canonical/` directory: new L04 v3 and Privacy v2 databases, new secrets, created empty by the install) | LILITH's live `cognitive_memory.db`, `privacy_governance.db` and 15B2a keys stay byte-identical; no migration of live data; the router's 15B2a containment keeps its own store; the return is "remove the new directory" | a source change to `PROD_PATHS` (host-tree file, not the signed release payload), with tests; two stores to describe |
| B. In-place migration (P2 as written) | one store | migrates live databases under a live router; reuses existing keys for a new role; a much harder return |

**Recommended: A.** What would be migrated in B is empty (0 L04 rows) or shadow-only (3 L18 SHADOW candidates), so A
loses nothing. USER.md stays authoritative (D-3); facts reach canonical memory only through the reviewed importer
(proposals → owner decisions → individual consented admission). The origin statement is re-admitted under PROD
authority by the owner; DEV admissions are never copied.

### 4.6 Hermes router, world context and providers

One new module plus four hunks in `gateway_integration.py`, rebased onto `4db8bb58`. Off unless the root-owned
settings file and a grant both exist. The note is merged into main-agent routes and the lean social policy only.
Unchanged: `run.py`, `router.yaml`, `config.yaml`, SOUL.md, USER.md loading, `world_context`, providers, tools and
Discord. Channel isolation: `lilith_os` first; Telegram only for the owner's private DM (user id = chat id = a
configured owner id); everything else is `public` and never receives personal memory.

### 4.7 Failure recovery and rollback

| Stage | Return |
| --- | --- |
| Inert install | stop and disable the new units; remove the new directories, units and `deployment.json`; under D-7 A, no LILITH byte to restore. The step's fresh snapshot is the backstop |
| Privacy activation | as above (the isolated store goes with it) |
| Console read route | remove the grant (one file, next turn); then restore `gateway_integration.py` to `4db8bb58` and remove `canonical_memory.py` (C2-style return, one gateway restart) |
| Telegram DM | remove `telegram_owner_dm` from the grant (one file) |
| Any | the window's fresh snapshot. Restoring a snapshot taken before a FORGET or checkpoint rolls Privacy back, and the gate then refuses until reconciled (correct) |

### 4.8 DEV_SYNTHETIC vs OWNER_PROD

| | DEV_SYNTHETIC (`lilith-dev-01`) | OWNER_PROD (`lilith-01`, proposed) |
| --- | --- | --- |
| Selection | no `deployment.json` | `deployment.json` OWNER_PROD + `LILITH_ENV=prod` |
| Key IDs | `dev.*`, `kpan.dev…`, `kpck…dev` | `prod.owner-prod.actor.1`, `prod.witness.owner-prod.1`, `kpan.owner-prod.01`, `prod.registry-root.owner-prod.1`, `kpck.owner-prod.01`, policy `policy.owner-prod.v1` |
| Owner registration | synthetic RP | the owner's real RP and principal (D-8), `LILITH_OWNER_REGISTRATION_PROD` |
| Stores | drill DBs (`f9-drill/`) | an isolated canonical store (D-7 A) |
| Machine | DEV machine-id pinned | PROD machine-id pinned (D-9) |
| Fallback | — | none: a PROD context refuses DEV roots, anchors and keys (P2 tests) |
| FORGET | V1 HMAC, canonical records only (D-6) | same |
| Unlock | owner, per boot | owner, per boot (D-4) |
| Names | `-dev` | still `-dev` (documented naming debt) |

## 5. Minimal incremental plan

Each row is its own owner approval and window. LILITH's behaviour is unchanged until R9.

| Step | Where | What | User-visible |
| --- | --- | --- | --- |
| R0 | source | this record, the read-only audit script and its offline test (this PR) | no |
| R1 | owner | decisions D-7 to D-12 (§7) | no |
| R2 | PROD, read-only | `prod_integration_audit_ro.sh` + `prod_compat_ro.sh`, one approved read; workstation `gcloud` reads of the snapshot schedule and the latest snapshot | no |
| R3 | source, offline | (a) `PROD_PATHS` → isolated store (D-7 A); (b) PROD installer mode + return + simulation on a PROD-shaped fake host; (c) overlay rebased onto `4db8bb58` with `native_self_status` merge tests and the corpus with the feature off; (d) compat pins updated from R2; (e) machine-ID pin (D-9); (f) the broker question (§2) settled in source | no |
| R4 | DEV | only if R3 changes the signed release payload: attested build A = B and a DEV transition (P3 ladder). If R3 touches only host-tree and tooling files, the release stays `88a1168` and DEV gets only a host-tree update | no |
| R5 | owner + PROD | key ceremony (P4 order: K-ROOT, K-ACT, K-WIT, K-PAN, registry, anchor, owner credential, K-PCK, verified backups) | no |
| R6 | PROD | fresh snapshot; inert install (authority release `88a1168`, witness, host tree, context units with **no grant**, `canonicalLtmEnabled=false`) | no |
| R7 | PROD | Privacy activation: pins, genesis, K-PCK checkpoint, first unlock → READY | no |
| R8 | owner + PROD | origin statement re-admitted (one capability enabled for one consented turn, then disabled); importer proposals from a read-only `memories/` copy reviewed (`decide`), nothing admitted without a reviewed family | no (records only) |
| R9 | owner + PROD | console read route: overlay installed, settings without a Telegram id, grant v3 `[lilith_os]`; owner console check | **yes** (console only) |
| R10 | owner + PROD | Telegram owner DM: settings gain the owner id, grant adds `telegram_owner_dm`; owner DM check and a Discord check | **yes** |

Needs new components: the PROD installer mode (R3b) and the isolated store paths (R3a). Everything else already
exists and was validated on DEV.

## 6. Validation and readiness

1. **Read-only audit (R2).** `prod_integration_audit_ro.sh` closes every **M** above: OS, system Python and glibc,
   memory and disk, identity and router hashes, store shapes and schema digests, the absence of every new path and
   principal, uid/gid collisions, units and failed units, and the allowlist count. It writes nothing, prints no
   content, and refuses any host but `lilith-01`. `prod_compat_ro.sh` stays the pre-window pin check, with pins
   updated in R3d.
2. **Snapshots and backups.** A scheduled snapshot READY within 24 h, plus a fresh manual snapshot at the start of
   R6, R7, R9 and R10 (`lilith-01-canonical-<step>-<UTC>`). K-ROOT and K-PCK offline backups are verified before R7.
3. **Pins.**
   - Authority release `88a1168bd41797109772ffce7df7352c1ae40e4c`, manifest
     `072001af671feca6564906d3d685f89bfc608f9d595aed58bae0f72a25777684`, archive
     `53ae457b8b907e12282ed468da0387620b7a376a46ab1c450709b67540b43c07`, attestation `b2f08910…` (or a new attested
     build if R4 applies).
   - Router base `4db8bb58da3fbdef80fb550c74709bb3ea62c605afadec56aa96b28d2568ca8b`; lean `5c4c2d1f…`.
   - Host tree and overlay files pinned by R3.
4. **Pre-installation invariants.** All must hold, or there is no window:
   - the compat check PASS;
   - every new path and principal absent;
   - the gateway and Core API running with 0 failed units beyond the two known ones;
   - no `deployment.json`;
   - disk ≥ 1 GB free and memory ≥ 400 MB available;
   - the snapshot READY;
   - no other PROD window open (C2 and T4 return windows closed or explicitly waived).
5. **Identity and memory preservation.** These are judged before and after every window and must be equal:
   - SOUL.md, USER.md, MEMORY.md, `config.yaml`, `router.yaml`;
   - the router files other than the two the overlay changes in R9;
   - `run.py`, the console adapter and Core API `app.py`;
   - `lilith.db`, `cognitive_memory.db` and `privacy_governance.db` digests (D-7 A);
   - the `state.db` row fingerprint (append-only growth allowed, no existing row changed);
   - the two 15B2a key metadata.
6. **Functional acceptance.**
   - **R6/R7:** LILITH is unchanged. The owner's five-prompt identity baseline, the career route ("how's my job
     search going?") and casual replies still on `groq_lean`. E-T4 is unchanged (still open, never claimed fixed).
   - **R9:** the console recalls the origin; voice and routing are unchanged; the corpus is byte-identical with the
     feature off.
   - **R10:** the Telegram DM recalls the origin; a Telegram group, another user and Discord receive no personal
     memory.
7. **STOP conditions.**
   - Any pin, invariant or preservation check differs.
   - Any unexpected unit state, a failed migration of the new store, or the Privacy gate not READY when expected.
   - The OS Login or sudo refusal seen on 2026-11-04.
   - A provider error in an acceptance turn.

   A STOP gets no retry, repair or automatic return. Recovery is the step's reviewed return, under the owner's word.
8. **Owner approvals before any PROD mutation:**
   - D-7 to D-12;
   - the R2 read;
   - the R3 PR merges;
   - R5 per ceremony step;
   - R6, R7, R8, R9 and R10 each as one window;
   - every provider request;
   - the grant writes.

## 7. Outstanding owner decisions

| # | Decision | Recommendation |
| --- | --- | --- |
| D-7 | store: isolated canonical store vs in-place migration of the live stores and keys | isolated (§4.5) |
| D-8 | relying party: RP id, origin, principal | a domain the owner controls |
| D-9 | approve the one machine-ID read and pin | approve with R2 |
| D-10 | K-ROOT location, passphrase custody, offline backup | owner device, offline, one verified backup |
| D-11 | K-PCK custody folder and offline backup | new WSL folder plus one verified offline backup |
| D-12 | owner credential form | WSL software credential (validated), or hardware if preferred |
| — | already decided | D-1 new PROD keys only; D-2 canonical-records-only FORGET; D-3 USER.md authoritative; D-4 manual unlock; D-5 console then Telegram DM, never Discord; D-6 V1 HMAC (provisional) |

## 8. Risks and blockers

| Risk / blocker | Mitigation |
| --- | --- |
| B: PROD installer mode not built (C-3) | R3b, offline with a PROD-shaped simulation |
| B: overlay base drift (C-2) | R3c rebase + corpus |
| B: owner decisions D-7 to D-12 | §7 |
| R: Python/wheel mismatch (C-5) | R2 reads it first |
| R: memory headroom on e2-small with a ~245 MB gateway | R2; the DEV evidence suggests about 100 MB extra |
| R: intermittent OS Login refusal on `lilith-01` (2026-11-04) | every window starts with a stable-SSH check and HOLDs on refusal |
| R: per-boot unlock dependency (unattended upgrades may reboot) | D-4 accepted; the socket enabled; recall fails closed |
| R: K-PCK loss means no unlock ever | the verified offline backup is an R7 prerequisite |
| R: the public repository | no PROD identifiers beyond hashes; the machine ID only in the reviewed pin commit (D-9) |

## 9. Next PR scope (this PR)

Documentation and offline tests only:
- this record;
- `integrations/hermes/overlays/prod-canonical-memory-context/prod_integration_audit_ro.sh` (prepared, not run);
- its static safety test `tests/test_prod_integration_audit.py`.

No runtime, release, router or Core API file changes. Nothing is installed, and PROD is not contacted. The PROD
deploy workflow stays `disabled_manually`.
