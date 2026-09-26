# LILITH Slice History (Reconstruction)

Status: **RECONCILIATION RECORD** — documentation/research provenance only.
Reconstructed on 2026-09-26 from protected main
`b1add92209560c10204e2a05583cb4647bf627e7`. It changes no architecture, marks
nothing accepted, and authorizes nothing. Where this record disagrees with a
slice's own design, deployment, or acceptance record, **the slice record wins**
(see [document authority](../README.md#document-authority)); please correct
this reconstruction.

> **Primary-source pass (2026-09-26).** This record was first reconstructed
> without the historical source documents. They are now archived in
> [source-material/originals](source-material/originals/) and described in the
> [historical source manifest](source-material/source-manifest.md). Corrections
> are made in place where a fact changed, and every change is listed in
> [Primary-source corrections](#primary-source-corrections-2026-09-26) at the
> end, so the first-pass reading stays auditable. Source IDs: **S1** Cognitive
> Architecture V1 PDF (2026-09-07), **S2** Master v1.0, **M1.1** Master v1.1,
> **S3** Infrastructure v1.0 (plus **INF-1.1**, **INF-1.1.1**), **S4** OS
> Architecture v0.1 (2026-08-24), **S5** Project Roadmap (2026-09-06), **J1**
> Engineering Journal through Slice 3 (2026-09-07). **S3, INF-1.1, INF-1.1.1
> and S5 are PRIVATE HISTORICAL SOURCES** (not published; SHA-256 S3
> `ff7ed4dadb5ecd06c47e0a9ee87b6690fb810e34cd71dfae44e9d142c92caf90`, INF-1.1 `d38d6b5ad53485f4631a76f42e3bb3cc50c3201e1d43a2be2b7808755df4ce49`, INF-1.1.1
> `7777e68cfc7d6b123b7f1767fdd59daded6e56d83454d928ddea948c3aefe063`, S5 `e7e0d6494725ad7958e39641cfb11df56952df323d172639695109f724054729`);
> only public-safe facts from them are used here.

## How to read this record

### Evidence labels

- **OBSERVED** — stated in an in-repo record, commit, test, or workflow.
- **PRIMARY** — stated in a recovered historical source (S1–S5, J1, Master,
  Infrastructure). S3, INF-1.1, INF-1.1.1 and S5 are private: their existence
  is provable by SHA-256 (see the manifest), but their contents are not public. Primary sources are dated self-reports: stronger than
  session notes, weaker than tests or run records.
- **RUN** — a GitHub Actions run record (run ID, attempt, job, step and
  conclusion), read through the GitHub API during the primary-source pass.
- **REPORTED** — stated only in out-of-repo material: the reconciliation
  brief, or assistant session notes kept outside the repository. Not
  independently verified here.
- **INFERRED** — this reconstruction's interpretation of OBSERVED text.

### Maturity vocabulary (kept deliberately distinct)

| Term | Meaning in this record |
| --- | --- |
| DESIGN RECORD | A design exists; nothing is implemented or accepted by it. |
| SOURCE IMPLEMENTED | Code exists in the repository. |
| TEST PROVEN | Automated tests pass in CI or a sandbox, with synthetic data. |
| PRE-DEV LIVE | Deployed by hand onto `lilith-01` and accepted there **before** a DEV environment existed (Slices 7–15B2a, 2026-09-07 → 2026-09-10). `lilith-01` is the host later called PROD. |
| SHADOW | Deployed and computing, but its output is discarded or not consumed. |
| DEV PROVEN | Exact-SHA deployment and checks on `lilith-dev-01` (from 2026-09-14). |
| PROD DARK | Present or absent in PROD but inactive; audited as inert. |
| ACCEPTED | An in-repo acceptance record or deployment record states PASS/ACCEPTED. |

"Live" in older records means PRE-DEV LIVE on `lilith-01`; it never means real
canonical memory or owner authority, neither of which exists anywhere.

### Naming conflicts found (preserved, not resolved)

| ID | Conflict | Evidence |
| --- | --- | --- |
| C-1 | **"Slice 1" and "Slice 2" have two meanings — both now attested by primary sources dated 2026-09-07.** J1 Entries 9–10 and the source code call Cognitive Core V2 Slice 1 the *System & Automation Health Summary* and Slice 2 *Career/Application Intelligence* (frontend). S1 pp. 29–30 (and the repo Markdown §18) map "Slice 1 — real observation (watcher fleet, `career_events`)" and "Slice 2 — domain reasoning (Router V2, Hermes gateway)" (backend). M1.1 "Historical substrate mapping" adopts S1's backend mapping. | J1; `src/lib/command/core/capabilities.ts`, `playbooks/system-health.ts`; S1; [cognitive-architecture-v1.md §18](../architecture/cognitive-architecture-v1.md); M1.1 |
| C-2 | **Four phase schemes, none equal to slices.** S4 (2026-08-24): phases 0–6 (Foundation → OS Core v0.1 → Career CRM v1 → Visual Shell → Agents+Apps → Avatar+Voice → Home+Hybrid). S5 (2026-09-06): phases 0–10 plus milestones M1–M5. Repo roadmap (2026-09-13): phases 0–8 and autonomy levels A0–A5, still listing the first approval-gated write (done 2026-09-07) as FUTURE. M1.1 (2026-09-14): phases 0–9+, and §P.2 explicitly maps S4/S5/S1 sequences as HISTORICAL rather than competing schedules. | S4 §16; S5 §3; [roadmap.md](../roadmap/roadmap.md); M1.1 §09, §P.2 |
| C-3 | **"Slice 15" split.** Cognitive Architecture V1 names Slice 15 "Learning/Consolidation" and Slice 16 "Device/Session Sync". In practice Slice 15 grew into 15A → 15B1 → 15B2a → 15B2b (A, B, C) and absorbed owner authority, Privacy, broker isolation, and deployer authority. Slice 16 has not started. | CA-V1 §20; slice records |
| C-4 | **The B1 track's parent is INFERRED.** The 15B2b-B design infers that `15B2b-B1…` records are "the foundation track" of 15B2b-B; no earlier record states this. | [15B2b-B design](../architecture/slice-15b2b-b-owner-memory-control-design.md) |
| C-5 | **Stage names.** B1b-2b stages are named `B1B2B_I/II/III` in controls and "Stage I/II/III" in prose; Stage III was split so that only "Stage III-A A2" was built. | B1b-2b records |
| C-6 | **B1d is undefined.** It appears once in B1a ("remains root-capable until B1b/B1c/B1d"); the 15B2b-B design only PROPOSES a scope. | B1a, B1c acceptance, 15B2b-B design |
| C-7 | **B1b-3 is a named gate with no record.** Threat model T-24 names "B1b-2/B1b-3 isolation review"; 15B2b-B design proposes its scope (custody isolation). Not started. | threat model, 15B2b-B design |
| C-8 | **RQ numbering.** The in-repo register (REPO:RQ-001–050) and the Master (MASTER:RQ-001–121, now verified from the archived PDFs) number the same topics differently; 49 of 50 shared numbers conflict. | [crosswalk](rq-register-crosswalk.md) |
| C-9 | **Command System V1 date.** J1 Entry 6 dates it "7 Sep 2026"; its commits `9fe4184`/`fa94852` are dated 2026-09-06 (+0530). J1 was compiled on 7 Sep; entry dates may reflect compilation. | J1; git |
| C-10 | **Two versions of Cognitive Architecture V1.** S1 (the fingerprinted PDF, printed 2026-09-14 from the 2026-09-07 artifact) lacks the §7a state-durability clarification that the repo Markdown (`61796fb`, 2026-09-07) contains. M1.1 marks S1's looser "online writes nothing durable" as SUPERSEDED. | S1; repo Markdown; M1.1 §R |

## Slice hierarchy (derived from repository evidence)

```text
Pre-slice foundations (2026-08-25 → 2026-09-06)          OS shell, workspaces, Presence/Hsin, conversation seam
Command System V1 (2026-09-06)                           UI↔Core contract (CommandCore)
Cognitive Core V2 vertical slices (frontend + VM backend)
├── Slice 1  System health summary (code) | real observation (CA-V1 §18)   [C-1]
├── Slice 2  Career attention summary (code) | domain reasoning / Router V2 [C-1]
├── Slice 3  Durable Task Store
├── Slice 4  Approval-gated internal write (/os/drafts)
├── Slice 5  Capability Policy Engine
└── Slice 6  Integration Fabric (connectors)
Cognitive Architecture V1 (design authority, 2026-09-07)
Router-seam cognitive lanes (backend, PRE-DEV LIVE on lilith-01)
├── Slice 7  World Model + Working Memory
│   ├── Phase A (frontend edge) · Phase B (backend deploy)
│   ├── 7.1  World Model operationalization
│   ├── 7.2  World-Model-first cognitive lane (REPORTED; no in-repo record)
│   └── 7.3  Deterministic draft dedup (REPORTED; referenced by Slice 10 record)
├── Slice 8  Goal / Executive
├── Slice 9  Reasoning extraction (tool-less)
├── Slice 10 Global Workspace / Attention
├── Slice 11 Motivation / Homeostasis
├── Slice 12 Planning / Replanning
├── Slice 13 Ethical Deliberation (advisory)
├── Slice 14 Social Cognition grounding + Presence contract (SHADOW)
└── Slice 15 Learning / Memory (expanded; see C-3)
    ├── 15A   Learning/consolidation foundations (L18, SHADOW)
    ├── 15B1  Canonical LTM foundations (L04 mechanics, disabled)
    ├── 15B2a Canonical memory authority + Privacy containment (disabled)
    └── 15B2b Canonical runtime and owner control
        ├── 15B2b-A  Canonical runtime foundation (SOURCE ACCEPTED / DEV PROVEN / PROD DARK)
        ├── 15B2b-B  Owner Memory Control (DESIGN RECORD)
        │   ├── B1 foundation track (parent INFERRED, C-4)
        │   │   ├── B1a    Synthetic owner-proof contracts
        │   │   ├── B1b-1  Isolated broker software foundation (synthetic)
        │   │   ├── B1b-2a Persistent synthetic DEV boundary (source)
        │   │   ├── B1b-2b Trusted first install and runtime control (DEV)
        │   │   │   ├── Stage I   PROVISION_ONLY (accepted)
        │   │   │   ├── Stage II  ACTIVATE_AND_ISOLATION_TEST
        │   │   │   │   ├── attempt #1 → FAILED-INERT (run 35924789001)
        │   │   │   │   └── retry #2  → ACCEPTED (run 35965971283)
        │   │   │   ├── Trusted DEV validation / snapshot-tool governance track
        │   │   │   └── Stage III-A A2 fault experiment → dispatched, controller failed, journal INTENT only (run 36145190507)
        │   │   ├── B1b-3  Custody isolation review (named gate; NOT STARTED, C-7)
        │   │   ├── B1c    Routine DEV deployer authority (ACCEPTED)
        │   │   │   ├── B1c-0 read-only capture · B1c-1 authority cut · B1c-1A activation authority
        │   │   └── B1d    (undefined, C-6)
        │   ├── B2a  Accepted-memory contract + verifier (SOURCE IMPLEMENTED / TEST PROVEN)
        │   └── B2b–B2e (PROPOSED names only)
        └── 15B2b-C  First Memory (PROPOSED; not started)
Slice 16 Device / Session Sync (planned in CA-V1; not started)
Repository & delivery track (2026-09-13 → 2026-09-14)   repo foundation, ADRs, CI, PROD deploy workflow, DEV pipeline
```

## Chronological list

Dates are commit or merge dates (local time of the committer) unless stated.

| # | Date | Slice / event | Key evidence | State |
| --- | --- | --- | --- | --- |
| 0− | ≤ 2026-08-24 | Foundation phase: dual Gmail watcher, career inbox summary, meeting context collector, morning brief, follow-up tracking, Discord alerts, multi-account handling, shared redaction, read-only posture | S4 §15 "Foundation status" | PRIMARY (reported operational by S4); pre-repository |
| 0− | 2026-08-24 | LILITH OS Architecture v0.1 (identity above runtime; truth ladder; approval classes; privacy zones) | S4 | PRIMARY |
| 0 | 2026-08-25 → 09-06 | Pre-slice foundations (OS shell, Career/Memory/Automations/Meetings workspaces, Presence, Hsin VRM avatar, TTS) | commits `161c2f4` … `4ecb54b` | SOURCE IMPLEMENTED (frontend) |
| 0a | 2026-08-25 | Read-only `/memory/*` API on the VM | REPORTED (session notes) | REPORTED live |
| 0b | 2026-08-31 → 09-02 | Google OAuth coverage failure begins (Gmail/Calendar stop refreshing 31 Aug; expired/revoked tokens from 2 Sep); Morning Brief degrades honestly | J1 Entry 12 | PRIMARY; unrepaired as of 15B2a |
| 0c | 2026-09-06 | LILITH OS Project Roadmap v1.0 (phases 0–10, M1–M5, frozen systems, DEV-01) | S5 (PRIVATE HISTORICAL SOURCE); summarized publicly in Master v1.1 §P | PRIMARY |
| 1 | 2026-09-06 | Command System V1 (CommandCore contract, demo core) | `9fe4184`, `fa94852`; J1 Entries 6, 8 (tag `lilith-os-command-v1` at `fa94852`) | SOURCE IMPLEMENTED; validation PRIMARY (J1) |
| 2 | 2026-09-06 | Slice 1 — system health summary (first real read-only capability) | `88f6a91`, `a93a42d`, `f22d052`; J1 Entry 9 | SOURCE IMPLEMENTED; self-test 7/7 and live acceptance PRIMARY (J1) |
| 3 | 2026-09-06 | Slice 2 — career attention summary (playbook engine) | `a7ce18a`, `b80b04f`, `18b263b`; J1 Entry 10 | SOURCE IMPLEMENTED; 16/16 and live acceptance PRIMARY (J1) |
| 4 | 2026-09-07 | Slice 3 — durable Task Store (`/os/tasks`) | `adbbd90`, `addd4b3`, `8d6379a`; J1 Entry 11 | SOURCE IMPLEMENTED; backend, 32/32 and live acceptance PRIMARY (J1) |
| 5 | 2026-09-07 | Slice 4 — approval-gated internal draft write | `9f8af69`, `248a738`, `b4c0adb` | SOURCE IMPLEMENTED; self-test in repo |
| 6 | 2026-09-07 | Slice 5 — capability policy engine | `f393716`, `445bc6b`, `253e2eb` | SOURCE IMPLEMENTED |
| 7 | 2026-09-07 | Slice 6 — integration fabric | `94c3c88`, `778b0f7`, `1388d36` | SOURCE IMPLEMENTED |
| 8 | 2026-09-07 | Cognitive Architecture V1 (design authority) | S1 (archived PDF); `61796fb` (amended Markdown, C-10) | DESIGN RECORD (authority) |
| 9 | 2026-09-07 | Slice 7 Phase A + spec + change set + Phase B deploy | `43ceba1`, `5a7312d`, `865e375`, `8f84e62` | PRE-DEV LIVE, PASS |
| 10 | 2026-09-07 | Slice 7.1 — World Model operationalization | `6c9f365` | PRE-DEV LIVE, PASS |
| 11 | 2026-09-08 | Slice 7.2 — World-Model-first cognitive lane (Home + Telegram) | REPORTED; referenced by Slice 8/10/12/13 records | REPORTED CLOSED |
| 12 | 2026-09-08 | Slice 7.3 — deterministic draft dedup | REPORTED; "Slice 7.3" cited in Slice 10 record | REPORTED CLOSED |
| 13 | 2026-09-08 | Slice 8 — Goal/Executive | `15e5851` | PRE-DEV LIVE, PASS |
| 14 | 2026-09-08 | Slice 9 — Reasoning extraction | `2c43457` | PRE-DEV LIVE, PASS |
| 15 | 2026-09-08 | Slice 10 — Global Workspace | `eb53cf0` | PRE-DEV LIVE, PASS |
| 16 | 2026-09-08 (deploy) / 09-09 (commit) | Slice 11 — Motivation | `3965d37` | PRE-DEV LIVE, PASS |
| 17 | 2026-09-09 | Slice 12 — Planning/Replanning | `03c42c8` | PRE-DEV LIVE, PASS |
| 18 | 2026-09-09 | Slice 13 — Ethical Deliberation | `2204ec2` | PRE-DEV LIVE, PASS |
| 19 | 2026-09-09 | Slice 14 — Social Cognition + Presence contract | `6afeaaa` | PRE-DEV SHADOW, PASS |
| 20 | 2026-09-09 | Slice 15A — Learning foundations | `149d0bc` | PRE-DEV SHADOW, PASS |
| 21 | 2026-09-09 | Slice 15B1 — Canonical LTM foundations | `f56247d` | PRE-DEV, disabled, PASS |
| 22 | 2026-09-10 | Slice 15B2a — Canonical memory authority foundations | `7ef3569` | PRE-DEV, disabled, PASS |
| 22a | 2026-09-14 | Architecture & Research Master v1.0 and v1.1; Infrastructure, CI/CD & Operations v1.0, v1.1, v1.1.1 (evidence snapshot repo `56d7c7f`) | S2, M1.1 (public); S3, INF-1.1, INF-1.1.1 (PRIVATE HISTORICAL SOURCES) | PRIMARY; canonical references of that date |
| 23 | 2026-09-13 | Repository foundation (ADR-0001–0005, register, threat model, CI) | `1eee09b`; PRs #1–#6 | SOURCE |
| 24 | 2026-09-13 | Governed PROD deployment workflow (app.py only) | PR #2 (`0dca571`) | OBSERVED |
| 25 | 2026-09-14 | Isolated DEV deployment pipeline | PRs #7–#10 | OBSERVED |
| 26 | 2026-09-22 → 23 | 15B2b-A canonical runtime foundation + trusted DEV bootstrap | PRs #13–#17 | SOURCE ACCEPTED / DEV PROVEN / PROD DARK |
| 27 | 2026-09-23 | B1a synthetic owner-proof contracts | PR #18 | SOURCE / TEST |
| 28 | 2026-09-23 | B1b-1 broker foundation + trusted broker CI | PRs #19–#21 | SOURCE / TEST |
| 29 | 2026-09-23 | B1b-2a synthetic DEV boundary + shared verifier + inert OS controls | PRs #23–#26 | SOURCE / TEST |
| 30 | 2026-09-23 → 24 | B1b-2b first-install control; Stage I accepted | PRs #27–#28; owner-run install | DEV (Stage I accepted) |
| 31 | 2026-09-24 | B1b-2b Stage II harness, bootstrap exception, attempt #1 FAILED-INERT | PRs #29–#32; run 35924789001 | DEV FAILED-INERT |
| 32 | 2026-09-24 | Stage II retry controls; retry #2 ACCEPTED; accepted-lifecycle bridge | PRs #33–#36; run 35965971283 | DEV ACCEPTED (synthetic) |
| 33 | 2026-09-24 → 25 | Broker-only DEV validation, trusted transport, trusted snapshot tool, premerge validation | merge `025c5f0` (PR number not recorded), PRs #39–#52 | DEV governance (several failed releases preserved) |
| 34 | 2026-09-25 | Stage III-A A2 source chain (fault seam → dispatch entrypoint) | PRs #38, #53–#59 | SOURCE (dormant) |
| 35 | 2026-09-25 | Stage III-A A2 operations: control install (RUN 36141310248, success); first `DISPATCH_ONCE` (RUN 36143716249, failed at the dispatch step); candidate inactive install (RUN 36144155832, success); second `DISPATCH_ONCE` (RUN 36145190507, failed at the dispatch step — the consumed run) | RUN records; B1c acceptance record | DEV: controller failed; journal INTENT only |
| 36 | 2026-09-25 | Stage III consumed-run forensics (read-only) | PR #60 | SOURCE |
| 37 | 2026-09-25 → 26 | B1c routine DEV deployer authority. First deploy RUN 36172947091: attempt 1 failed closed on missing `compute.projects.get`; attempt 2 failed in the fixed helper; attempt 3 failed at the federation proof (`curl -f` on a 403). CI runs 36176288675 and 36178821872 failed during the fixes. Final RUN 36179649106 succeeded | PRs #61–#62; RUN records; record PR #63 | ACCEPTED (DEV PROVEN; PROD untouched) |
| 38 | 2026-09-26 | 15B2b-B Owner Memory Control design | PR #64 | DESIGN RECORD |
| 39 | 2026-09-26 | 15B2b-B2a accepted-memory contract + verifier | PR #65 (`b1add92`); CI RUN 36188029848 and PR RUN 36188405143 (success); post-merge DEV RUN 36188586023 (success) | SOURCE IMPLEMENTED / TEST PROVEN; post-merge routine DEV deploy succeeded (RUN) — the B2a package is not part of the DEV bundle |

## Per-slice records

Each entry lists: parent · purpose · layers · sources · implementation ·
acceptance/tests · deployment · established · **not** established ·
failures/negatives · residual debt · rollback · RQs affected (in-repo
numbering). Test counts are copied from the cited record.

### P0 — Pre-slice foundations (2026-08-25 → 2026-09-06)

- **Purpose:** OS shell and read surfaces (Career, Memory, Automations, Meetings,
  System), the Presence Engine abstraction, the Hsin VRM avatar (idle, blink,
  gaze, visemes, lip-sync, ambient motion), TTS, and the conversation relay.
- **Layers:** L17 Presence (renderer only), L01 read surfaces.
- **Evidence:** commits `161c2f4`…`4ecb54b` (OBSERVED). `/memory/*` read API and
  its exclusion of `USER.md`/`state.db` are REPORTED.
- **Established:** a presence *renderer* and read-only transport seam.
- **Not established:** any cognition in Presence; any emotional model. Avatar
  "expressions" are renderer states, not affect.
- **RQs:** RQ-043 (surface only).

### Command System V1 (2026-09-06)

- **Parent:** Cognitive Core V2 precursor. **Purpose:** freeze the UI↔Core
  contract (`CommandCore`, event reducer) before any real core existed.
- **Evidence:** `9fe4184`, `fa94852` (OBSERVED); J1 Entry 6 (TypeScript zero
  errors, build, clean diff, all task states validated in production) and
  Entry 8 (stabilization gate; tag `lilith-os-command-v1` at `fa94852`)
  (PRIMARY). J1 Entry 7 records a Turbopack stale-chunk "blank routes" false
  alarm fixed by a clean rebuild, no code change (PRIMARY).
- **Established:** demo fixtures labelled "Simulated", separable from real
  output. **Not established:** any real capability.
- **RQs:** RQ-018.

### Slice 1 — System health summary (2026-09-06) [C-1]

- **Purpose:** first real read-only capability through planner → capability
  check → executor → typed PASS/PARTIAL/FAIL verifier → evidence.
- **Layers:** L08/L10 (bounded planner), L13, L15 (verifier).
- **Evidence:** `88f6a91`, `a93a42d`, `f22d052`; `real-core.ts`,
  `verifier.ts`, `self-test.ts` (OBSERVED). J1 Entry 9 (PRIMARY): self-tests
  7/7; production acceptance; the live result "correctly reported 4 of 6
  services healthy with evidence and an overview-vs-detail discrepancy".
- **Established (in source):** transport success is not treated as task
  success. **Not established:** backend durability (history was browser
  `localStorage`).
- **Alternative meaning (CA-V1 §18):** "real observation — watcher fleet,
  `career_events`", a backend capability that predates this repository and has
  no in-repo record.
- **RQs:** RQ-021, RQ-034.

### Slice 2 — Career attention summary (2026-09-06) [C-1]

- **Purpose:** generalize Slice 1 into a playbook engine; career attention with
  explicit entity linking (unlinkable → unresolved, never fuzzy).
- **Evidence:** `a7ce18a`, `b80b04f`, `18b263b` (OBSERVED); J1 Entry 10
  (PRIMARY): self-tests 16/16; live result "7 applications needing attention"
  with application-ID-backed evidence; pipeline reconciled with no false
  discrepancy; timezone-less backend timestamps forced day-level handling.
- **Alternative meaning (CA-V1 §18):** "domain reasoning — Router V2, Hermes
  gateway". Router V2 source is **not** in this repository.
- **RQs:** RQ-021, RQ-013 (explicit linkage), RQ-024 (Router V2, REPORTED).

### Slice 3 — Durable Task Store (2026-09-07)

- **Purpose:** make the backend the source of truth for task history.
- **Layers:** L07 substrate (tasks), durable state.
- **Evidence:** `adbbd90`, `addd4b3`, `8d6379a`, `task-store.ts`, write proxies
  (OBSERVED). J1 Entry 11 (PRIMARY): backend `tasks` table on `lilith-01`'s
  SQLite, `schemaVersion=1`, monotonic revision, `expectedRevision` → 409,
  `operationId` idempotency; 32/32; history restored after reload and after
  clearing localStorage; records survived a backend restart. J1's own lesson:
  "put the backend under source control" (done later, 2026-09-13).
- **Established:** revisioned, idempotent task records (source + PRIMARY
  backend evidence). **Not established:** multi-runtime coordination.
- **RQs:** RQ-004, RQ-008, RQ-018.

### Slice 4 — Approval-gated internal write (2026-09-07)

*Primary-source note:* J1 (compiled 2026-09-07) still lists Slice 4 as
"planned only"; S1 (same date) states the design "builds on the shipped
substrate … (Slices 1–6)". Together they place Slices 4–6 on 2026-09-07,
after J1 was compiled. Test counts 48/60/67 for Slices 4–6 remain REPORTED
(session notes), except "frontend core 67/67", which later in-repo records
OBSERVE.

- **Purpose:** first real write — an **unsent** internal follow-up draft,
  approval-gated, fingerprint-frozen, idempotent, read-back verified.
- **Layers:** L10 → L12 → L13 → L15 (canonical flow D).
- **Evidence:** `9f8af69`, `248a738`, `b4c0adb`; `scripts/run-core-self-test.mjs`
  (OBSERVED). 48/48 self-test (W-A…W-P incl. unknown-commit verify-before-retry)
  and live acceptance REPORTED.
- **Established:** approval binds to a fingerprint; denial/cancel produce zero
  writes; approved-not-executed recovers idempotently. **Not established:** any
  external send (deliberately none).
- **RQs:** RQ-028, RQ-029, RQ-033, RQ-034, RQ-050.

### Slice 5 — Capability policy engine (2026-09-07)

- **Purpose:** replace a per-capability flag with typed classes
  `READ | INTERNAL_WRITE | EXTERNAL_WRITE | DESTRUCTIVE | PROHIBITED`;
  `mail.send_email` PROHIBITED; approval-expiry maintenance; second write
  `career.add_note`.
- **Evidence:** `f393716`, `445bc6b`, `253e2eb`, `policy.ts`,
  `prohibited-capabilities.ts` (OBSERVED). 60/60 REPORTED.
- **Established:** the core no longer reads permission flags; prohibition is
  checked before execution regardless of planner output.
- **Failure noted (REPORTED):** an expiry sweep recomputed "now" and never fired
  until `now` was injected.
- **RQs:** RQ-026, RQ-027, RQ-031, RQ-032, RQ-047.

### Slice 6 — Integration fabric (2026-09-07)

- **Purpose:** typed connectors with discovery and health gating; unavailable or
  unsupported fails closed with zero mutation; `google-workspace` modelled as
  unavailable (known OAuth breakage), not repaired.
- **Evidence:** `94c3c88`, `778b0f7`, `1388d36`, `connectors.ts` (OBSERVED).
  67/67 REPORTED (later regression runs cite "frontend core 67/67", OBSERVED in
  Slice 8/9 records).
- **RQs:** RQ-034, RQ-039.

### Cognitive Architecture V1 (2026-09-07)

- **Sources:** S1 (archived PDF, fingerprint MATCH) and the amended repo
  Markdown (C-10). S1 names ACT-R and Soar as inspiration and states
  "no AGI / consciousness claims".
- **Purpose:** 19-layer design authority; governing rule "planner proposes ·
  policy governs · connectors perform I/O · verifier proves"; §7a state
  durability; §10 no-simulated-suffering invariant; Slice 7–16 sequence.
- **Evidence:** [cognitive-architecture-v1.md](../architecture/cognitive-architecture-v1.md).
- **Not established:** any implementation; "no consciousness claims".

### Slice 7 — World Model + Working Memory (2026-09-07)

- **Purpose:** "spine before mind" — durable, provenance-stamped belief store;
  ephemeral reconstructible working set.
- **Layers:** L05, L03.
- **Sources:** [backend spec](../architecture/slice-7-world-model-backend-spec.md),
  [Phase B change set](../architecture/slice-7-phase-b-change-set.md),
  [deployment record](../architecture/slice-7/DEPLOYMENT-RECORD.md).
- **Tests:** 18/18 A–R. **Deployment:** PRE-DEV LIVE on `lilith-01`, appended
  block, restart-only.
- **Established:** 31 real beliefs from 8 applications; conflicts retained as
  `CONFLICTED`; stale retained; unavailable source never overwrites; working
  set reconstructed after restart (`world_working_seed=0`).
- **Not established:** a VERIFIED path in use (no Verification layer);
  `follow_up` belief (no source column).
- **Negative/limitation:** Phase B was split from Phase A because the VM was
  unreachable from the frontend environment (REPORTED).
- **Rollback:** timestamped `app.py` and DB backups.
- **RQs:** RQ-012, RQ-013, RQ-015.

### Slice 7.1 — World Model operationalization (2026-09-07)

- **Evidence:** [7.1 record](../architecture/slice-7/SLICE-7.1-RECORD.md); 9/9
  operational + 18/18 regression.
- **Established:** automatic cursor-based ingestion from `career_events`,
  idempotent, restart-safe; scheduled freshness sweep.
- **Not established:** TTL policy (career beliefs never auto-stale).
- **RQs:** RQ-008, RQ-011.

### Slice 7.2 — World-Model-first cognitive lane (2026-09-08) — REPORTED

- **No in-repo design or deployment record.** Referenced by the Slice 8, 10, 12,
  and 13 records as the belief/pending/draft lane that later lanes yield to.
- **REPORTED:** a Router V2 lane at the shared `run_sync` seam grounds belief,
  pending, and draft turns in World-Model state for Home and Telegram; the
  shadow run reproduced the original bug (the model surfacing raw database
  paths and message identifiers), which the live lane fixed; Home and Telegram
  acceptance passed.
- **RQs:** RQ-004, RQ-015, RQ-047.

### Slice 7.3 — Deterministic draft dedup (2026-09-08) — REPORTED

- **REPORTED:** exactly one unresolved draft → reuse; more than one → refuse and
  surface reconciliation; none → create. The two historical application-14
  drafts remain untouched and require a manual user decision.
- **OBSERVED consequence:** later records repeatedly show application 14
  "blocked" on two unsent drafts (Slices 8–13).
- **RQs:** RQ-008.

### Slice 8 — Goal / Executive (2026-09-08)

- **Evidence:** [design](../architecture/slice-8-goal-executive-design.md),
  [record](../architecture/slice-8/DEPLOYMENT-RECORD.md); 22/22 + 9/9.
- **Established:** durable goals, FSM, deterministic arbitration (lifecycle >
  priority > deadline > source > recency > id), derived focus reconstructed
  after restart; Home and Telegram route parity.
- **Not established:** parent/child cascade; Goals UI.
- **RQs:** RQ-018, RQ-019, RQ-020.

### Slice 9 — Reasoning extraction (2026-09-08)

- **Evidence:** [design](../architecture/slice-9-reasoning-extraction-design.md),
  [record](../architecture/slice-9/DEPLOYMENT-RECORD.md); 18/18.
- **Established:** tool-less reasoning (`enabled_toolsets=[]`, zero tool
  schemas); a fail-open short-circuit in Hermes `run.py` that still passes
  through `enforce_reply`; action precedence (reasoning yields to 7.2/8).
- **Known gap:** a reasoning turn may be answered but not persisted if history
  reconstruction fails.
- **RQs:** RQ-023, RQ-047.

### Slice 10 — Global Workspace / Attention (2026-09-08)

- **Evidence:** [design](../architecture/slice-10-global-workspace-design.md),
  [record](../architecture/slice-10/DEPLOYMENT-RECORD.md); 24/24.
- **Established:** deterministic salience-class arbitration bounding the
  reasoning input; workspace focus ≠ executive focus (executive focus never
  mutated).
- **Not established:** interruption delivery; SYSTEM_CRITICAL and
  BACKGROUND_MAINT producers (synthetic only).
- **RQs:** RQ-014, RQ-040.

### Slice 11 — Motivation / Homeostasis (2026-09-08)

- **Evidence:** [design](../architecture/slice-11-motivation-homeostasis-design.md),
  [record](../architecture/slice-11/DEPLOYMENT-RECORD.md); 32/32.
- **Established:** ordinal drives (COHERENCE, GOAL_COMPLETION; SAFETY
  synthetic); no floats, no affect keys, no emotional wording; no executive
  influence.
- **Negative finding (OBSERVED):** in realistic turns motivation contributed
  **zero** workspace slots because its sources were already raw candidates;
  its V1 effect is a trace and a bounded summary.
- **RQs:** RQ-040, RQ-041.

### Slice 12 — Planning / Replanning (2026-09-09)

- **Evidence:** [design](../architecture/slice-12-planning-design.md),
  [record](../architecture/slice-12/DEPLOYMENT-RECORD.md); 40/40.
- **Established:** proposal-only plans; grounder ≠ validator; deterministic
  template live.
- **Not established:** LLM planning live (built, not wired); post-execution
  replanning (fixture only); durable plan store.
- **Failure:** detector-precedence defect found during acceptance and fixed
  (`fix12.py`, second restart).
- **RQs:** RQ-021, RQ-022.

### Slice 13 — Ethical Deliberation (2026-09-09)

- **Evidence:** [design](../architecture/slice-13-ethical-deliberation-design.md),
  [record](../architecture/slice-13/DEPLOYMENT-RECORD.md); 54/54.
- **Established:** advisory-only (no ALLOW/DENY vocabulary);
  `SKIPPED_KNOWN_PROHIBITION` from a static policy mirror, labelled non-authoritative.
- **Not established:** the canonical "ethics subtracts" action gate (deferred);
  LTM value priors.
- **Failure:** snapshot-seed refinement for parity; a local `test_motivation`
  failure attributed to a local module-snapshot mismatch.
- **RQs:** RQ-026, RQ-030, RQ-032.

### Slice 14 — Social Cognition grounding + Presence contract (2026-09-09)

- **Evidence:** [design](../architecture/slice-14-social-cognition-presence-design.md),
  [record](../architecture/slice-14/DEPLOYMENT-RECORD.md); 49/49; Slice 8–14
  suite 226/226.
- **Established (SHADOW):** TURN-only deterministic grounding (roles, audience,
  support/humor cues); explicit prohibitions on affect, relationship state, and
  personality runtime.
- **Not established:** relationship continuity; any live consumer; any renderer
  consumer of Presence hints.
- **Recorded debt:** `STREAMED_RESPONSE_VS_POST_ENFORCEMENT_FINAL_RESPONSE_RECONCILIATION`.
- **RQs:** RQ-043, RQ-046.

### Slice 15A — Learning / consolidation foundations (2026-09-09)

- **Evidence:** [design](../architecture/slice-15a-learning-consolidation-foundations-design.md),
  [record](../architecture/slice-15a/DEPLOYMENT-RECORD.md); 56/56; 282 suite.
- **Established (SHADOW):** job/lease/cursor ledger; three `SHADOW_ELIGIBLE`
  source-event candidates; `canonicalMemoryMutation=false`.
- **Not established:** any admission; `SHADOW_ELIGIBLE` explicitly ≠ true or
  accepted.
- **RQs:** RQ-009, RQ-010.

### Slice 15B1 — Canonical LTM foundations (2026-09-09)

- **Evidence:** [design](../architecture/slice-15b1-canonical-ltm-foundations-design.md),
  [record](../architecture/slice-15b1/DEPLOYMENT-RECORD.md); 53 canonical + 335
  suite.
- **Established:** CREATE/SUPERSEDE/RESTORE mechanics (atomic, replay-safe,
  restore creates a new revision); production canonical rows **zero**.
- **Failure:** pre-commit audit found `occurredAt` in the semantic fingerprint
  and removed it.
- **Not established:** real Consent, Verifier, Rollback authority, erasure, or
  consumers.
- **RQs:** RQ-012, RQ-013, RQ-011.

### Slice 15B2a — Canonical memory authority + Privacy containment (2026-09-10)

- **Evidence:** [design](../architecture/slice-15b2a-canonical-memory-authority-privacy-containment-design.md),
  [record](../architecture/slice-15b2a/DEPLOYMENT-RECORD.md); 55 tests;
  A–DL acceptance matrix.
- **Established:** actor evidence (HMAC, nonce, expiry), payload-bound consent,
  computed (not declared) policy, single-use rollback, FORGET as hold →
  erasure, SQLite authorizers.
- **Failure:** containment could fall through with an empty registry; fixed to
  `LEGACY_CONTAINMENT_NOT_READY`.
- **Unrelated failures observed:** career-watcher and meeting-prep services
  failing on Google OAuth `invalid_grant`.
- **Not established:** any real canonical class or memory.
- **Debt:** issuance keys held as `lilith:lilith 0600` (central gap later named
  by 15B2b-B).
- **RQs:** RQ-009, RQ-011, RQ-016, RQ-028.

### Repository & delivery track (2026-09-13 → 2026-09-14)

- **Evidence:** `1eee09b`; ADR-0001–0005; PRs #1 (core API import), #2 (PROD
  workflow), #6 (quality gates), #7–#10 (DEV pipeline).
- **Established:** Git-driven deploy; PROD workflow installs **only**
  `app.py`; DEV environment.
- **Negative:** `as-is.md` and the roadmap were written as a fresh start and
  never reconciled with Slices 1–15B2a (C-2). S2/S3 (2026-09-14) note this
  drift themselves ("the repository's early AS-IS page … understates later
  slices").
- **Primary evidence (PRIVATE HISTORICAL SOURCE S3 — Infrastructure, CI/CD &
  Operations v1.0 — SHA-256 `ff7ed4dadb5ecd06c47e0a9ee87b6690fb810e34cd71dfae44e9d142c92caf90`;
  2026-09-14, repo `56d7c7f`; only facts already public elsewhere in this
  repository are repeated):** protected-main ruleset
  with four required checks and zero approvals (solo); PR → DEV → merge → PROD
  flow; an intentional DEV runtime-failure rollback test executed and verified;
  the single GitHub deployer identity held OS Admin Login, Compute Viewer and
  IAP tunnel access — the authority B1c later removed from routine DEV
  deployment. S3's own P1 target "Dedicated DEV and PROD deploy identities"
  is the item B1c realized for DEV only.

### 15B2b-A — Canonical runtime foundation (2026-09-22 → 23)

- **Evidence:** [design](../architecture/slice-15b2b-a-canonical-runtime-foundation.md),
  [acceptance](../architecture/slice-15b2b-a-acceptance-record.md), ADR-0006.
- **Established:** SOURCE ACCEPTED (PR #13), DEV PROVEN (synthetic durability
  across restart; `USER_ASSERTED` not promoted), PROD DARK (21 canonical tables
  zero rows).
- **Failure/negative:** the `workflow_run` trust boundary could not validate its
  own new controls → bootstrap PRs #14–#16 with a temporary ruleset change.
- **Not established:** owner control, real memory, production canonical package.
- **RQs:** RQ-009, RQ-015, RQ-049.

### B1a — Synthetic owner-proof contracts (2026-09-23)

- **Evidence:** [record](../architecture/slice-15b2b-b1a-owner-proof-contracts.md).
- **Established (TEST):** ES256 WebAuthn verification, digest-bound challenge
  (≤60 s), durable replay authority, `VERIFIED_PROOF_ONLY` ≠ authority.
- **Correction within the PR:** follow-up commit `bcdfbbb` bound the proof to
  the request digest and to consume-time expiry.
- **Not established:** operational Level 2; real RP/origin/enrollment.
- **RQs:** RQ-028, RQ-029.

### B1b-1 — Isolated broker software foundation (2026-09-23)

- **Evidence:** [record](../architecture/slice-15b2b-b1b1-broker-foundation.md).
- **Established (TEST):** closed request construction; conservative
  proof-to-authority crash table (A1–A5 points) with deterministic fault hooks.
- **Not established:** OS isolation; any live service.
- **RQs:** RQ-008, RQ-033.

### B1b-2a — Persistent synthetic DEV boundary (2026-09-23)

- **Evidence:** [record](../architecture/slice-15b2b-b1b2a-synthetic-dev-boundary.md).
- **Established (source):** `DEV_SYNTHETIC` mode; synthetic evidence that
  cannot deserialize as actor evidence. **Not established:** installation.

### B1b-2b — Trusted first install and runtime control (2026-09-23 → 25)

- **Evidence:** [first-install control](../architecture/slice-15b2b-b1b2b-first-install-control.md),
  [bootstrap exception](../architecture/slice-15b2b-b1b2b-trusted-control-bootstrap-exception.md),
  [Stage II control](../architecture/slice-15b2b-b1b2b-stage2-runtime-control.md),
  [failed-inert bridge](../architecture/slice-15b2b-b1b2b-failed-inert-lifecycle-bridge.md),
  [accepted Stage II](../architecture/slice15b2b-accepted-stage2-lifecycle.md).
- **Stage I:** accepted (provision only).
- **Stage II attempt #1 (run 35924789001): FAILED-INERT.** Source first pinned a
  volatile API PID (preflight stopped); then the API non-interference check
  compared a raw `ExecStart` string whose runtime annotations changed after
  `daemon-reload`, falsely reporting an API restart. Broker and socket left
  inert; history preserved.
- **Retry #2 (run 35965971283): ACCEPTED** (synthetic): 24 challenges, 2 claims,
  2 evidence rows, all row hashes pinned.
- **Governance negatives:** records describe one-time owner PR-only ruleset
  bypass procedures for PR #30, the failed-inert bridge, the accepted-lifecycle
  bridge (conditional on owner use), and the broker-only validation governance
  change, because trust-root edits could not certify themselves. Required
  checks were to stay visibly pending, never reported as passed.
- **RQs:** RQ-033, RQ-035, RQ-044.

### Trusted DEV validation and snapshot-tool track (2026-09-24 → 25)

- **Evidence:** [broker-only validation](../architecture/slice15b2b-broker-only-dev-validation.md),
  [snapshot tool](../architecture/slice15b2b-trusted-dev-snapshot-tool.md),
  [install acceptance contract](../architecture/slice15b2b-trusted-snapshot-install-acceptance-contract.md).
- **Failures (OBSERVED):** remote staging path read from contaminated SSH stdout;
  two SCP uploads stalled at zero bytes; SSH-stdin streaming stalled (run
  35986496264); causes **unproven**. Two installed snapshot-tool releases
  failed self-test (nested sudo; boot-ID format) and remain preserved as
  unaccepted history.
- **Established:** packed command-channel transport feasibility; installed
  trusted snapshot tool; premerge head binding.

### Stage III-A A2 — Fault experiment (2026-09-25)

- **Evidence:** [fault seam](../architecture/slice15b2b-stage3-a2-fault-seam.md),
  [reversible transition](../architecture/slice15b2b-stage3-a2-reversible-transition.md),
  [adapters](../architecture/slice15b2b-stage3-a2-control-adapters.md),
  [final controller](../architecture/slice15b2b-stage3-a2-final-controller.md),
  [wiring](../architecture/slice15b2b-stage3-a2-operational-wiring.md),
  [forensics](../architecture/slice15b2b-stage3-a2-consumed-run-forensics.md);
  outcome in [B1c acceptance](../architecture/slice-15b2b-b1c-acceptance-record.md#broker-and-stage-iii-preservation).
- **Hypothesis:** a real process death after proof consumption and before claim
  (A2) burns the proof without duplicate authority.
- **Runs (RUN):** control install 36141310248 succeeded; a first
  `DISPATCH_ONCE` (36143716249) failed at "Invoke only the fixed one-shot
  systemd dispatch"; the candidate was then installed inactive (36144155832);
  a second `DISPATCH_ONCE` (36145190507) failed at the same step. Why the first
  dispatch failed is not recorded in the repository.
- **Outcome:** dispatch run 36145190507 consumed the one-shot dispatch; the
  **controller failed; phase journal INTENT only**; no arm, no guard; the V2
  authorization is preserved and not consumed. **The experiment did not run.**
- **Negative (systemd):** `systemctl mask --runtime` did not mask units under
  `/etc/systemd/system` (found in isolated WSL2 testing, corrected before DEV).
- **Not established:** any live crash semantics; A1–A5 remain live-unproven.
  Must not be retried without explicit justification.
- **RQs:** RQ-033, RQ-037.

### B1c — Routine DEV deployer authority (2026-09-25 → 26)

- **Evidence:** [design/runbook](../architecture/slice15b2b-b1c-dev-deployer-authority.md),
  [acceptance](../architecture/slice-15b2b-b1c-acceptance-record.md).
- **Established:** ACCEPTED; DEV PROVEN in run 36179649106; constrained
  federation, fixed helper, 28 denials, `ACTIVATION=NOT_ACCEPTED`;
  deployment ≠ activation.
- **Failures on the path:** owner install failed closed (OS Login user not yet
  materialized, `def790c`); verifier shebang `-I -S` defect (`43e7887`);
  first deploy run 36172947091 failed in helper (inherited private cwd +
  EXIT-trap reading out-of-scope locals, `963b141`); a later attempt failed at
  federation proof because `curl -f` aborted on a correct 403 denial
  (`fbf37e0`). *(Corrected, RUN evidence.)* Run 36172947091 attempt 1 failed
  closed at "Prove the routine DEV deployer has no root, broker, or Stage III
  reach" with `Required 'compute.projects.get' permission`; the documented
  contingency custom role followed. Attempt 2 failed at "Deploy through the
  fixed root-owned DEV helper"; attempt 3 at "Prove routine DEV federation
  cannot obtain PROD or the legacy privileged identity". Validation runs
  36176288675 (`963b141`) and 36178821872 (`fbf37e0`) failed at "Validate
  routine DEV deployer authority boundary" before the test-harness fixes
  `5216381` and `bfdcc10`.
- **Open debt:** `CROSS_ENVIRONMENT_PROD_AUTHORITY_DEBT`; Level 2 not claimed.
- **RQs:** RQ-035, RQ-037, RQ-048.

### 15B2b-B — Owner Memory Control design (2026-09-26)

- **Evidence:** [design record](../architecture/slice-15b2b-b-owner-memory-control-design.md).
- **Status:** DESIGN RECORD; not accepted.
- **Contribution:** names the central authority gap (application user can mint
  evidence); logical-only owner authority context; acceptance as verifier
  output; ten unresolved owner decisions.
- **RQs:** RQ-001, RQ-009, RQ-013, RQ-015, RQ-028, RQ-048.

### 15B2b-B2a — Accepted-memory contract and verifier (2026-09-26)

- **Evidence:** [record](../architecture/slice-15b2b-b2a-accepted-memory-verifier.md),
  `services/owner-memory-control/`.
- **Status:** SOURCE IMPLEMENTED / TEST PROVEN; LIVE AUTHORITY ABSENT.
- **Established:** 43-reason closed taxonomy; 89-case tamper matrix; forbidden
  equalities (model output, row, apply, cached flag, matching value) all
  `NOT_ACCEPTED`; `truthClaim` always false.
- **Runs (RUN):** CI 36188029848 and PR check 36188405143 succeeded on
  `a827728`; after merge, validation 36188521156 and the routine DEV deploy
  36188586023 succeeded on `b1add92`. The DEV deploy installs the Core API
  bundle; the B2a package is not in it, so this is not DEV evidence for B2a.
- **Not established:** B1b-3, broker integration, real keys/memory, activation.
- **RQs:** RQ-013, RQ-015, RQ-028.

## Current position (2026-09-26)

- No real canonical memory exists in any environment.
- No owner credential is enrolled; no activation signer or grant exists.
- Stage III A2 is deferred and unproven.
- `CROSS_ENVIRONMENT_PROD_AUTHORITY_DEBT` is open.
- Next named but **unauthorized** boundaries: B1b-3, B2b–B2e, B1d, 15B2b-C.

## Primary-source corrections (2026-09-26)

What the archived sources changed in this record, and what they did not.

| Area | First pass said | Primary sources show | Source |
| --- | --- | --- | --- |
| Earliest history | Began 2026-08-25 with the repository | A foundation phase (watchers, briefs, alerts, redaction) was reported operational by 2026-08-24, and S4 already defined identity above runtimes, a truth ladder, approval classes and privacy zones | S4 |
| Command System V1, Slices 1–3 | Validation and live acceptance REPORTED | PRIMARY evidence with counts and live results | J1 Entries 6–11 |
| Slice 1/2 meaning (C-1) | Code vs repo Markdown | Both meanings are primary and same-day; M1.1 adopts the backend mapping | J1, S1, M1.1 |
| Slices 4–6 timing | 2026-09-07 from commits | Confirmed: after J1's compilation, before S1's design | J1, S1 |
| OAuth failure (N-15) | From 2026-09-10 | From 2026-08-31 / 2026-09-02 | J1 Entry 12 |
| Cognitive Architecture V1 | One document | Two versions (C-10) | S1, `61796fb` |
| Phase schemes (C-2) | Roadmap vs slices | Four schemes; M1.1 declares the older ones historical | S4, S5, M1.1 |
| Slices 7–15B2a | In-repo records only | Independently summarized by S2/M1.1 on 2026-09-14 as "VERIFIED foundations; maturity varies", canonical LTM not activated | S2, M1.1 §02 |
| Pre-B1c deployer authority | From B1c records | Recorded on 2026-09-14 (S3); dedicated DEV/PROD deploy identities were an S3 P1 target | S3 §03, §08 |
| Stage III runs | One consumed run | Two failed dispatch runs plus two successful install runs | RUN |
| B1c `compute.projects.get` | REPORTED | RUN evidence (attempt 1 log) | RUN 36172947091/1 |
| B2a CI / post-merge DEV | REPORTED | RUN evidence | RUN 36188029848, 36188586023 |

Unchanged by the primary sources: Slices 7.2 and 7.3 remain REPORTED (no
primary source names them); everything after 2026-09-14 (15B2b-A onward)
postdates every archived source and rests on in-repo records and RUN evidence;
B1b-3, B1d, B2b–B2e and 15B2b-C remain unstarted or undefined; Slice 16
(Device/Session Sync, L19) remains TARGET in S1 and M1.1.
