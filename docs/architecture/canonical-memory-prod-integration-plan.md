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
| Router (`~/.hermes/lilith_router`) | Router V2 + seven Cutover 2 lanes; `gateway_integration.py` **`4db8bb58…`** (C2 `99fe9064` → T4 `7f83cf9c` → T4 wording `4db8bb58`, deployed 2026-11-04 07:36Z); lean social `social_lean.py` `5c4c2d1f` (Groq Qwen); `world_context.py` `91deea97` with `_prod_world_context.py` `ebe62158`; social guard `3a0906b5`; `router.yaml` lanes live | V (deploy records 2026-11-03/04) |
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
| R2 | PROD, read-only | `prod_integration_audit_ro.py` (§6.1), one approved read; workstation `gcloud` reads of the snapshot schedule and the latest snapshot | no |
| R3 | source, offline | (a) `PROD_PATHS` → isolated store (D-7 A); (b) PROD installer mode + return + simulation on a PROD-shaped fake host; (c) overlay rebased onto `4db8bb58` with `native_self_status` merge tests and the corpus with the feature off; (d) compat pins updated from R2; (e) machine-ID pin (D-9); (f) the broker question (§2) settled in source; (g) collision-safe service uid/gid selection (§10.2); (h) `prod_compat_ro.sh` rebased onto the no-SQLite rule | no |
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

1. **Read-only audit (R2): `prod_integration_audit_ro.py`.** One root Python process reads its own source from
   stdin (`sudo -n /usr/bin/python3 -I -B -`, payload pinned by SHA-256), so nothing is written and no bytecode is
   cached.
   - **Live databases are never opened by SQLite.** `cognitive_memory.db`, `privacy_governance.db` and `lilith.db`
     are judged by byte digest and file metadata. `state.db` gets metadata only. Their `-wal`, `-shm` and `-journal`
     companions are only `lstat`ed, so no lock, journal, WAL or shared-memory file can be created or changed. Under
     D-7 (isolated store) their schema is not needed. If a schema or row count is ever needed, it comes from an
     isolated copy of an existing snapshot, under its own approval, never from the live files.
   - **No access time changes:** every read is `O_RDONLY | O_NOATIME | O_NOFOLLOW`, and the audit refuses if
     `O_NOATIME` is missing. The root mount's atime option is recorded.
   - **Command boundary:** the only subprocesses are `/usr/bin/systemctl show` and `list-units`, with fixed
     arguments, a fixed environment and a 30 s timeout. Users and groups come from `pwd`/`grp`; memory from
     `/proc/meminfo`; disk from `statvfs`. Git and the Hermes Python are not executed (`.git/HEAD` and `pyvenv.cfg`
     are read).
   - **Host restriction:** root only; the short hostname must be `lilith-01`; refuses the DEV machine ID. All three
     guards run before any other read.
   - **Sanitized output:** every value must match `[A-Za-z0-9._:/=,|+@-]{1,240}`, or that observation is an error.
     Digests, sizes, modes, counts, versions and states only. The two 15B2a keys are `lstat`ed only. Credential files
     (`.env`, `groq.env`, `auth.json`) are never touched. The Telegram allowlist is a count; the machine ID is a
     SHA-256.
   - **Exact pins:** 22 full SHA-256 pins from the last accepted windows (identity files, `config.yaml`,
     `router.yaml`, 12 router modules, 4 Hermes files, Core API `app.py`), each reported `MATCH` or `DIFF`. A DIFF is
     a drift finding, not an audit error.
   - **Fail closed:** any missing file, permission error, empty or partial command output, timeout, unparseable or
     unsafe value, or exception is an `ERR` line. `PROD_INTEGRATION_AUDIT_COMPLETE` (exit 0) appears only with zero
     errors and every expected observation made. Otherwise the result is `…_INCOMPLETE` (exit 3); a refusal is
     `…_REFUSED` (exit 2).
   - **Unavoidable side effects of any login:** OS Login session records, sudo and journal entries. None touches a
     LILITH file.
   - `prod_compat_ro.sh` (the P3 pre-window check) still opens SQLite with `mode=ro`, so it is superseded for R2. It
     must be rebased onto the same no-SQLite rule (R3d) before any window uses it.
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
   - `state.db`: no existing row changed, judged on isolated copies of the window's pre and post snapshots (never on
     the live file); during the window, metadata only (append-only growth allowed);
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
| D-7 | store: isolated canonical store vs in-place migration of the live stores and keys | **provisionally chosen by the owner 2026-11-04: isolated**; existing cognitive memory, Privacy databases and 15B2a keys stay untouched |
| D-8 | relying party: RP id, origin, principal | a domain the owner controls |
| D-9 | approve the one machine-ID read and pin | approve with R2 |
| D-10 | K-ROOT location, passphrase custody, offline backup | owner device, offline, one verified backup |
| D-11 | K-PCK custody folder and offline backup | new WSL folder plus one verified offline backup |
| D-12 | owner credential form | WSL software credential (validated), or hardware if preferred |
| — | already decided | D-1 new PROD keys only; D-2 canonical-records-only FORGET; D-3 USER.md authoritative; D-4 manual unlock; D-5 console then Telegram DM, never Discord; D-6 V1 HMAC (provisional) |

Installation mode: the owner prefers staged in-place on `lilith-01` (§4.1 A), conditional on the R2 audit confirming
sufficient resources.

### 7.1 What each open decision needs (no key or credential is generated by preparing this)

**D-8: relying party.** Three strings, fixed for the life of the PROD owner registration. Every owner proof binds
them, so changing one later means a new registration and new owner credentials. The rules are enforced by
`lilith_authority_host/inputs.py`:

| Item | Rule | Example shape |
| --- | --- | --- |
| RP id | a lowercase DNS name with a letter TLD; 253 characters at most; never `.invalid` | `example.org` or `lilith.example.org` |
| Origin | exactly `https://<rp-id>`, or `https://<sub>.<rp-id>` | `https://lilith.example.org` |
| Principal | `user:<name>@<domain>`; name `[A-Za-z0-9._%+-]{1,64}`; never the DEV synthetic identity | `user:owner@example.org` |

To decide: which domain you control and will keep renewing; the principal's local part; and which credential form
(D-12) goes with it. A WSL software credential needs no web page at that origin (assumption, matching the DEV
pattern). A hardware authenticator used through a browser needs a page actually served at that HTTPS origin, which
is new infrastructure.

**D-10: K-ROOT (registry root).**
- **Form:** one Ed25519 key, stored as PKCS#8 DER encrypted under a passphrase of at least 12 characters (entered at
  the terminal, never echoed), written once with mode `0600` (`owner_prod_owner_tool.py root-keygen`). Its public
  anchor is printed.
- **Purpose:** it signs registry v1 and any later registry update. Without it the registry cannot change, but the
  running services keep working.
- **To decide:**
  - the machine it is generated on: the workstation in WSL, or another offline device;
  - where the encrypted file lives;
  - where the passphrase lives (never beside the file);
  - one verified offline backup: medium and location, plus the restore test (load with the passphrase on a second
    copy).

**D-11: K-PCK (Privacy checkpoint).**
- **Form:** `privacy_checkpoint_tool.py keygen` creates a **new** custody directory (`0700`) holding a raw Ed25519
  key, `kpck.key` (`0600`, **unencrypted at rest**), its public pin and the checkpoint chain.
- **Purpose:** it signs every post-reboot unlock and each checkpoint. Losing it means PROD Privacy can never be
  unlocked again, and personal recall stays off for good.
- **To decide:**
  - the custody directory's location (inside WSL, never the DEV folder);
  - whether that disk is encrypted;
  - one verified offline backup, encrypted, made **before** activation (R7). The DEV backup was never made.

**D-12: owner credential.**
- **Option A, a WSL software credential (the DEV pattern):** no new hardware, validated end to end on DEV. The
  private key sits on the workstation, so a workstation compromise is an owner compromise.
- **Option B, a hardware authenticator:** the key never leaves the device. But the owner tooling and WSL USB access
  (usbipd) are untested, and the browser route needs the D-8 origin served. That is offline engineering before R5.

To decide: A or B, and the backup or loss plan. On loss, a new credential needs a new owner registration under K-ROOT.

## 8. Risks and blockers

| Risk / blocker | Mitigation |
| --- | --- |
| B: PROD installer mode not built (C-3) | R3b, offline with a PROD-shaped simulation |
| B: overlay base drift (C-2) | R3c rebase + corpus |
| B: owner decisions D-7 to D-12 | §7 |
| ~~R: Python/wheel mismatch (C-5)~~ | observed in run 1: system Python 3.12.3, glibc 2.39 (§10) |
| R: memory headroom on e2-small | observed in run 1: 1,299 MB available, 5.8 GB disk free; DEV needs about 95 MB for the stack (§10) |
| B: uid/gid collisions (gid 995 in use on PROD) | R3g: collision-safe id selection (§10.2) |
| B: Telegram owner-ID source unresolved | needed only at R10; §10.3 |
| R: intermittent OS Login refusal on `lilith-01` (2026-11-04) | every window starts with a stable-SSH check and HOLDs on refusal |
| R: per-boot unlock dependency (unattended upgrades may reboot) | D-4 accepted; the socket enabled; recall fails closed |
| R: K-PCK loss means no unlock ever | the verified offline backup is an R7 prerequisite |
| R: the public repository | no PROD identifiers beyond hashes; the machine ID only in the reviewed pin commit (D-9) |

## 9. Next PR scope (this PR)

Documentation and offline tests only:
- this record;
- `integrations/hermes/overlays/prod-canonical-memory-context/prod_integration_audit_ro.py` (prepared, not run);
- its offline test `tests/test_prod_integration_audit.py`. It runs the audit on a synthetic root with a live WAL
  store and secrets, and proves:
  - no byte, inode, mtime or atime changes, and no new file;
  - the fail-closed paths: missing, permission, symlink, failed, empty, partial or timed-out commands, unsafe
    values, exceptions and missing observations;
  - streaming hashing (a 64 MiB file under a 3 MiB peak) and the 4 MiB whole-read limit;
  - the PROD-shaped fixture: run 1's five errors reproduced under the old rules, COMPLETE now; the os-release link
    variants; no other symlink followed;
  - the refusals happen before any read;
  - sanitization and the static command boundary.

No runtime, release, router or Core API file changes. Nothing is installed, and PROD is not contacted. The PROD
deploy workflow stays `disabled_manually`.

## 10. PROD audit run 1 (2026-11-05) and R3 findings

### 10.1 Run 1: INCOMPLETE, kept as evidence

One owner-authorized run (`I authorize P3-PROD-AUDIT-RO 5a90108c6ce8 d1f1cf453cd4d271`) ended
`PROD_INTEGRATION_AUDIT_INCOMPLETE errors=5 observed=70 expected=70` (exit 3). That is a STOP. The run is never
reinterpreted as COMPLETE and was not retried. Its output is sealed on the owner workstation.

**The five errors were audit defects, each caught by fail-closed:**
- `host os` OSError: `/etc/os-release` is Ubuntu's symlink to `../usr/lib/os-release`, and `O_NOFOLLOW` refused it;
- four timer units ValueError: a timer has no `MainPID` / `NRestarts`, so the service-only schema could never be
  complete.

The fix follows exactly that one link when its target resolves to `usr/lib/os-release`, which is itself opened with
`O_NOFOLLOW`. Services and timers now have their own property sets, plus `LoadState`, so a missing unit cannot pass
as inactive. On a PROD-shaped fixture, the run-1 helper reproduces exactly these five errors with the same counts;
the fixed helper is COMPLETE. The next run needs its own authorization and must be COMPLETE with zero errors.

**Observed in run 1** (individual observations; the run as a whole is INCOMPLETE):
- **All 22 pins MATCH:** identity files, `config.yaml`, `router.yaml`, the 12 router modules (`gateway_integration`
  `4db8bb58`), the 4 Hermes files and `app.py`.
- **Host:** system Python 3.12.3 and glibc 2.39 (C-5 resolved); 2 vCPU; 1,299 of 1,961 MB available; 5.8 GB disk
  free; root mounted `relatime`.
- **Hermes:** `f293e72`, venv Python 3.11.
- **New components absent:** every canonical-memory path, socket and settings file. The principal observations
  used guessed names and are not evidence (§11).
- **Stores and keys:** the 15B2a keys are present (32 B, `0600`); store digests are recorded.
- **Services:** the gateway and Core API are active with 0 restarts. Failed units: only the two known ones.
- **Allowlist:** the Telegram allowlist key count in `config.yaml` is **0**.
- **ids:** gid **995 in use**.

**Run 2 (2026-11-05, `I authorize P3-PROD-AUDIT-RO 13e4ff72d6df 298abaf159da14a7`): COMPLETE.**
`PROD_INTEGRATION_AUDIT_COMPLETE observed=70`, 0 errors, exit 0. Results:
- **Pins:** 22/22 MATCH.
- **Host:** `ubuntu-24.04`; 1,300 MB available, 5.8 GB free.
- **Store digests:** all unchanged from run 1. Every other stable observation is identical to run 1.
- **Services:** the gateway and Core API run with the same PIDs.
- **Timers:** `lilith-career-watcher.timer` and `lilith-gmail-watcher.timer` are active. `lilith-morning-brief-watcher.timer`
  and `lilith-meeting-prep-watcher.timer` are `LoadState=not-found`. Those two names in the audit's unit list were
  guesses (the failed unit is `lilith-meeting-prep.service`). This is a naming finding about the audit, not a PROD
  fault. Their real timer names are to be confirmed before any window uses unit states.

The staged in-place installation's resource condition is met.

### 10.2 R3g: collision-safe service ids

DEV's numeric ids (recorded 995/985) must never be assumed on PROD, and gid 995 is taken there. The PROD installer:
- creates each service principal by **name** with `useradd --system` / `groupadd --system`, letting the OS pick a
  free system id;
- refuses if the name already exists with any other shape;
- records the chosen ids in the install record;
- pins every later check (units, tmpfiles, ownership, the deployer-boundary proof) to the recorded names and ids,
  never to DEV's numbers.

The return removes exactly the recorded principals and nothing else. The R2 audit reports the four names absent and
which of 985/995 are in use. The installer's preflight repeats that check in the same session as the creation.

### 10.3 Telegram owner-ID source: unresolved (needed only at R10)

From the Hermes source at `f293e72` (offline), the gateway's Telegram allowlist comes from:
- the `TELEGRAM_ALLOWED_USERS` value (profile secret scope or the process environment: `~/.hermes/.env` or the unit
  environment);
- `config.yaml` `telegram.allow_from`, which Hermes copies into that variable;
- the DM pairing store `{HERMES_HOME}/platforms/pairing`;
- the allow-all flags `TELEGRAM_ALLOW_ALL_USERS` / `GATEWAY_ALLOW_ALL_USERS`.

Run 1's count of 0 rules out `config.yaml`.

The router's `telegram_owner_dm` channel never reads any of these. Its owner ID comes only from the root-owned
`canonical_memory.json`, which the owner supplies at R10. So the source matters for one check only: the owner ID in
the settings must be one the gateway already admits.

**Proposed, if the owner wants it:** a separate, narrowly scoped, owner-approved provenance check. It never prints
an ID, token or value. It reports only:
1. which of the four sources holds a value: key-name presence in `.env`, the pairing-store entry count and whether
   each allow-all flag is set;
2. the number of admitted Telegram IDs;
3. for each admitted ID, `sha256("lilith-tg-owner-v1\0" + id)`, so the owner can confirm, by computing the same
   fingerprint locally, that the ID they intend to configure is admitted.

Reading `.env` means touching a credential file (only key names are matched, in memory). For that reason this check
is not part of the R2 audit; it would run only under its own approval, or by the owner.

## 11. R3 offline engineering status (2026-11-05)

| Item | Where | Status |
| --- | --- | --- |
| R3a isolated store | draft PR `feat/prod-canonical-r3a-isolated-store` | `PROD_PATHS` → `/home/lilith/.hermes/lilith-os/canonical` (new secrets inside); an OWNER_PROD host refuses any store path in the live data directory (`PROD_PATH_IN_LIVE_DATA`, `..` included); DEV unchanged. Host-tree tool only |
| R3b/R3g inert install, stage 1 | draft PR `feat/prod-canonical-r3b-inert-install` (stacked on R3a) | foundation only: the two principals by name with OS-allocated ids, the empty isolated directory, `/etc/lilith-authority-dev`, `deployment.json`; journaled; verify-everything-then-remove return. Later stages (release staging, units, witness, host tree, context units) are not built |
| R3c overlay rebase | draft PR `feat/prod-canonical-r3c-overlay-rebase` | base `4db8bb58`; the 4 hunks apply with offsets; T4 routes kept; 120-turn corpus with the feature off is identical to the deployed router apart from generated goal IDs (which differ between two baseline runs too) |
| R3d compat | this PR | `prod_compat_ro.sh` (SQLite `mode=ro`) removed; a COMPLETE audit run ends `PROD_COMPAT_PASS` / `PROD_COMPAT_FAIL <reasons>`; timer names from the preserved PROD units; principals = the installer's real accounts |
| R3e machine-ID pin | procedure below | not pinned |
| R3f broker | settled in source, below | no broker process on PROD |

**Correction (principals).** Runs 1 and 2 checked four guessed principal names. Their `user=no,group=no` results are
therefore not evidence about the real accounts (`lilith-authority-dev`, `lilith-recovery-witness`). The release and
install paths were verified absent. The corrected audit (and the R3b preflight, in the install session itself) checks
the real names.

**R3f: the broker process is not needed.** First Memory's owner evidence (`OwnerEvidenceV2`) is issued and signed by
the trusted signer (`first_memory_conversation`: "the evidence issuer, i.e. the trusted signer"). The
registration's `brokerReleases` names the authority release the evidence is issued by
(`first_memory_owner_credential_dev registration <release-sha>`). Recall (`context_response` → signer), admission and
the canonical-records FORGET never contact `lilith-memory-broker`. The PROD install includes no broker. The PROD
registration lists the PROD authority release.

**Release rebuild: not required so far.** R3a changes a host-tree tool. R3b is install tooling. R3c is router overlay
files. None is among the 57 signed runtime members, so the authority release stays `88a1168` (archive `53ae457b…`).
`LILITH_ENV=prod` is planned as a systemd drop-in installed by a later R3b stage, not a change to the signed unit
files. If that stage instead needs a changed member, a new attested A = B build and its own DEV transition follow.

**R3e: machine-ID pin procedure (recommended; needs the owner's D-9 approval).** The COMPLETE run 2 already recorded
`sha256(/etc/machine-id)` for `lilith-01`. The recommendation is one reviewed commit:
- change the two PROD keygens to compare `sha256(machine-id)` with a pinned digest, instead of a pinned raw ID;
- pin that digest from run 2.

No new PROD read is then needed, and the raw machine ID never enters the public repository. The alternative, pinning
the raw ID as P3 designed, needs one separately approved read of `/etc/machine-id`. Either way the keygens still
refuse the DEV machine.

**Owner inputs remain explicit and unresolved:**
- D-8: RP id, origin, principal;
- D-10: K-ROOT;
- D-11: K-PCK;
- D-12: credential form.

No registration, credential or key exists or is generated by any of this.

## 12. R3 completion (2026-11-05): installer stages, D-9, merge order

**Inert installer (R3b, PR #319 on #318).**
- Stage 1, the foundation: principals by name with OS-allocated ids; the isolated store directory;
  `/etc/lilith-authority-dev`; `deployment.json`.
- Stages 2–5 (`owner_prod_inert_stages.py`):
  - release: the attested `88a1168` with its venv and `current`;
  - units: signer and witness units (witness = the E-23 NEW bytes) and tmpfiles, each `.service` with a
    `LILITH_ENV=prod` drop-in, and no reload, enable or start;
  - host tree: the `88a1168` tree and `canonical-config` DISABLED;
  - context: the context service and its units, not enabled, with **no grant** and no router settings.
- Each stage is its own owner window, single-use and journaled. Each has a verify-all-then-remove return, runs in
  strict order and returns in reverse.
- None of this starts a service, activates Privacy, creates a key or credential, registers an owner or writes a grant.
  Those remain R5 (ceremony), R6/R7 (start, Privacy) and R8–R10.

**D-9 (PR #321).** Both PROD keygens can pin `lilith-01` by `PROD_MACHINE_ID_SHA256`, the SHA-256 of the exact
`/etc/machine-id` bytes, as run 2 recorded it:
- **Host identity:** the host file must be one exact ID line, hash to the pin, not be the DEV ID, and run on hostname
  `lilith-01`.
- **Custody evidence:** unchanged. The raw ID read on the host still goes into `custodyEvidence.machineId`, which the
  signed `pr1_bootstrap.py` requires. Those publications must not be committed; records cite digests.
- **Release:** no signed member changes, so no rebuild.
- **Status:** the pin is unset until the owner approves D-9.

**Signed release.** No R3 change touches any of the 57 signed members, so `88a1168` (archive `53ae457b…`, manifest
`072001af…`) stays the PROD release and no new attested build is needed.

**Combined-stack check.** #317, #318/#319, #320 and #321 merge into main without conflict (18 files). The combined
Linux suites are recorded in the PR descriptions.

**Recommended merge order** (each its own owner approval, one at a time, each waiting for main's validation and the
routine DEV deploy):
1. #320 (overlay files only, under `integrations/hermes/`);
2. #321 (tools and tests);
3. #318 (host-tree tool);
4. #319 (retargeted to main after #318; tools and tests);
5. #317 (record, audit, gate).

**Deployment classification:**
- **DEV:** each is `DEPLOY_REQUIRED` except where the classifier says otherwise. That means one routine DEV Core API
  redeploy of unchanged Core API code per merge. None changes the DEV signer, witness, host tree or Hermes, because
  those change only through their own transition or install windows.
- **PROD:** none deploys PROD; the PROD workflow is dispatch-only and `disabled_manually`.
- **The DEV host tree:** R3a changes a host-tree tool, so DEV keeps running its installed tree until a separately
  approved DEV host-tree update. The change is PROD-only by construction.

**Next approval boundary** (none is executed by any of this):
- owner decisions D-9, D-8, D-10, D-11 and D-12;
- the merges;
- one read-only audit (or the stage-1 preflight in the install session) for the corrected timer and principal names;
- the R5 key ceremony;
- the R6 inert install windows (stages 1–5, one approval each), each starting with a fresh snapshot.

## 13. R3 merges and outstanding return hardening (2026-11-05)

**Merged to main, one owner approval each.** Every merge was followed by a successful Repository validation, a
successful DEV deploy gate (`DEPLOY_REQUIRED`, ubuntu-24.04, `FEDERATION_BOUNDARY=PASS`,
`AUTHORITY_BOUNDARY_PROOF=PASS`) and a read-only DEV invariant read. In each read the only change was the Core API
release and its process; signer, witness, broker, canonical stores, Privacy and FORGET were unchanged. None of
these merges deployed PROD.

| PR | Content | Main after merge |
| --- | --- | --- |
| #320 | overlay rebase (R3c) | `210ae94` |
| #321 | D-9 digest pin, unset (R3e) | `c547d18` |
| #318 | isolated store paths (R3a) | `cd77846` |
| #319 | inert installer stages 1–5 (R3b) | `32009ea` |
| #324 | R3b correction: venv return integrity | `eb81eb6` |

**#324 (owner review finding).** The stage `release` return did not verify the generated venv before removing
it, and recursively deleted an interrupted venv. Its recursive walk also followed a symlinked venv root, deleting
the link target's contents. The install now journals a complete venv manifest (type, mode, owner, file SHA-256 or
link target; links never followed). The return removes the venv only when it matches that manifest exactly, entry
by entry, and never recursively. An interrupted venv (no manifest) is `VENV_UNVERIFIED`: a STOP for owner
adjudication.

**Outstanding before the first real PROD installation** (owner-recorded hardening; not built; no install or return
has run on a real host):

- **H-1. Non-venv mode verification.** For non-venv items, the return checks file content, link targets and
  unexpected directory entries, but not the mode or owner of files and directories. Verify each item's recorded
  mode (and owner) before removal, as the venv manifest already does.
- **H-2. Verification-to-deletion race.** The return verifies everything and then removes it. A concurrent
  filesystem change between those two steps could change what `unlink` or `rmdir` act on. Candidate approach:
  - descriptor-relative removal (`openat`/`O_NOFOLLOW`, `unlinkat` against verified parent directory descriptors);
  - a fresh `lstat` of each entry, matched to its verified inode, immediately before removing it;
  - an exclusive host lock and a maintenance window for the return.

**Owner rule (2026-11-05):** H-1 and H-2 must be implemented, tested with negative controls and reviewed
**before the first real PROD installation** (R6 stage 1), so that every install window has a ready, verified
recovery path. No PROD install window may be proposed until both are merged.
