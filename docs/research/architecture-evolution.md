# LILITH Architecture Evolution

Status: **RECONCILIATION RECORD** — a chronological account of how the
architecture actually changed, reconstructed from repository evidence on
2026-09-26 (protected main `b1add92`). Earlier architectures are preserved
here as historical evidence; the current design did not always exist.
Detailed per-slice evidence is in the [slice history](slice-history.md).

Labels: OBSERVED (in-repo), REPORTED (out-of-repo notes or the brief),
INFERRED.

> **Primary-source pass (2026-09-26).** Re-checked against the archived
> sources ([manifest](source-material/source-manifest.md)): S4 OS Architecture
> v0.1 (2026-08-24), S5 Project Roadmap (2026-09-06), J1 Engineering Journal
> (2026-09-07), S1 Cognitive Architecture V1 (2026-09-07), S2/M1.1 Master v1.0
> and v1.1 (2026-09-14), and the PRIVATE HISTORICAL SOURCES S3 / INF-1.1 /
> INF-1.1.1 Infrastructure v1.0–v1.1.1 (2026-09-14) and S5 Project Roadmap,
> which are not published and are cited by SHA-256 in the manifest. The first pass
> dated several concepts too late, because it only had repository evidence.
> Section 0 is new; the invariant timeline is corrected; changed statements are
> listed at the end. Newer concepts are **not** back-projected: a design in an
> older document is dated to that document, and implementation is dated to the
> slice that built it.

## 0. Before the repository: blueprint and roadmap (≤ 2026-08-24 → 2026-09-07)

- **S4, LILITH OS Architecture v0.1 (2026-08-24).** "The OS is the interface.
  LILITH is the intelligence." It already states **identity above runtimes**
  ("LILITH survives any single model, runtime, channel or cloud. Hermes is a
  reasoning runtime today — not the identity"), **model-neutral identity and
  memory**, a **truth ladder** (OBSERVED → INFERRED → USER-CONFIRMED →
  STALE/CONFLICTED, "never silently merged"; "personality may color language;
  it may never color evidence, confidence or permissions"), **approval classes**
  (AUTO / PREVIEW / APPROVE), capability tokens, a secrets vault ("credentials
  never enter prompts"), kill switch, audit ledger, working / episodic /
  semantic / procedural memory with privacy zones, an event bus with attention
  levels 0–5, and presence states that are "presentation, not simulated
  feelings". Its roadmap: Foundation → OS Core v0.1 → Career CRM v1 → Visual
  Shell → Agents+Apps → Avatar+Voice → Home+Hybrid.
- **Operational foundation before the repository.** S4 reports the foundation
  phase complete: dual Gmail watcher, career summaries, meeting context,
  morning brief, follow-up tracking, Discord alerts, redaction, read-only
  posture (PRIMARY, self-reported).
- **S5, Project Roadmap (2026-09-06)** — PRIVATE HISTORICAL SOURCE, SHA-256
  `e7e0d6494725ad7958e39641cfb11df56952df323d172639695109f724054729`; its phases and
  decisions are also summarized in the public Master v1.1 §P.2. Phases 0–10, milestones M1–M5
  (Cognitive Core V2 = M5, *after* UX and stabilization), frozen avatar
  systems, and an execution contract: "tool success must be supported by a
  returned artifact or observed external state"; "consciousness and universal
  task automation are not delivery promises". Backlog B06 names a "Brain
  Architecture V1" — the precursor of CA-V1.
- **J1, Engineering Journal (2026-09-07).** Records the path Home V2 → module
  UX → presence architecture ("the brain should request attention/expression,
  not choose bone poses") → Command System V1 → stabilization → Cognitive Core
  Slices 1–3, plus the Google OAuth failure from 31 August and the lesson "put
  the backend under source control".

## 1. The starting point (2026-08-25 → 2026-09-05)

- **A frontend over a private VM.** This repository began as a Next.js
  "LILITH OS" command center (`161c2f4`, 2026-08-25). All intelligence lived on
  a remote GCE VM reached through an IAP tunnel: the Hermes runtime, a
  single-file FastAPI `app.py`, SQLite `lilith.db`, and watcher services
  (career watcher, meeting prep). The frontend had a GET-only allow-listed
  proxy and one write channel, `POST /os/conversation` (OBSERVED in CA-V1 §0,
  §18).
- **Memory was Hermes's.** Durable "memory" was Hermes markdown files
  (`MEMORY.md`, `USER.md`) plus a full-text-searchable conversation store;
  `career_events` rows carried source and confidence (REPORTED). A read-only
  `/memory/*` projection existed (REPORTED; later classified
  `LEGACY_PROJECTION` by 15A, OBSERVED).
- **Presence was a renderer.** The orb and then the Hsin VRM avatar rendered
  states; no cognition lived there (OBSERVED commits).
- **No implemented authority model.** There was no policy engine, no verifier,
  no canonical store, and no separation between the model and actions in
  code. *(Corrected: the S4 blueprint of 2026-08-24 had already designed
  approval classes, capability tokens, a secrets vault, a kill switch and an
  audit ledger; see section 0.)*

## 2. A cognitive core in the browser (2026-09-06 → 09-07)

- Command System V1 froze a UI↔Core contract before any real core existed.
- Cognitive Core V2 ran **in the frontend**: planner → capability registry →
  executor → typed verifier (Slice 1); a shared playbook engine (Slice 2);
  backend task store (Slice 3); approval-gated unsent draft write (Slice 4);
  policy classes and a PROHIBITED tier (Slice 5); typed connectors with health
  gates (Slice 6).
- **First invariants appeared as behaviour:** transport success ≠ task
  success (Slice 1); approval binds to a fingerprint (Slice 4); policy is
  planner-independent (Slice 5); "planner proposes · policy governs ·
  connector performs I/O · verifier proves" (Slice 6).
- **Superseded within the era:** browser `localStorage` history → backend
  task store (Slice 3); per-capability permission flag → policy classes
  (Slice 5); write paths built from raw transport → connectors (Slice 6).

## 3. Design authority: Cognitive Architecture V1 (2026-09-07)

*Primary-source note:* the fingerprinted S1 PDF is a 2026-09-14 print of the
2026-09-07 artifact and lacks §7a; the repo Markdown (`61796fb`, same day)
adds §7a (see slice-history C-10). S1 names ACT-R and Soar as inspiration.

[CA-V1](../architecture/cognitive-architecture-v1.md) turned the emerging
rules into a 19-layer design with four cross-cutting authorities, "the LLM is
one reasoning component, not the whole brain", memory ≠ truth, and three
persistence regimes (§7a, which explicitly **supersedes** looser earlier
wording: World Model may checkpoint online; Working Memory is ephemeral and
reconstructible; LTM is written only by consolidation). §10 introduced the
**no-simulated-suffering** invariant for drives. It recommended building
"spine before mind" (Slice 7 first).

## 4. Cognition moves to the Router seam on the VM (2026-09-07 → 09-09)

- **Relocation.** From Slice 7.2 onward the authoritative cognitive path was
  the backend Router V2 seam where Home and Telegram converge, not the
  frontend core — because the frontend core cannot serve Telegram (REPORTED
  rationale; OBSERVED effect: Slices 8–13 accept on "Home + Telegram").
- **Pattern.** Each slice added a lane in `~/.hermes/lilith_router/` with
  per-turn flags, shadow → live rollout, strict lane precedence (action lanes
  win), fail-open behaviour, and a Home/Telegram parity check.
- **Deployment method.** Hand deployment to `lilith-01` — the host later
  treated as PROD — with timestamped backups, `ast.parse` gates, restart-only,
  never `daemon-reload` (OBSERVED in every Slice 7–15B2a record). There was no
  DEV environment.
- **Layers built:** World Model and reconstructible working set (7, 7.1),
  goals and derived focus (8), tool-less reasoning (9), deterministic
  attention (10), ordinal drives (11), proposal-only planning (12), advisory
  ethics (13), TURN-only social grounding and a Presence contract (14,
  shadow).
- **Split authority (INFERRED from Slice 12/13 records):** the authoritative
  capability registry stayed in the frontend `RealCommandCore`, while Router
  lanes used static, explicitly non-authoritative mirrors of it.

## 5. Memory is re-architected around authority (2026-09-09 → 09-10)

- **15A** created a separate learning ledger (`cognitive_memory.db`) and the
  governing sentence *Learning proposes · LTM admits and stores · Provenance
  explains · Memory is not truth.* Legacy Hermes memory was classified
  `LEGACY_EXTERNAL` / `LEGACY_UNVALIDATED` and not accessed.
- **15B1** built canonical LTM mechanics (immutable revisions, atomic apply,
  restore-as-new-revision) — disabled, zero rows.
- **15B2a** separated **authority from storage**: actor evidence, payload-bound
  consent, computed policy, single-use rollback, and a separate Privacy
  database that owns FORGET. Canonical writes stayed disabled.
- This is the point at which **storage, authority, and truth became separate
  concepts** in the architecture (memory row ≠ authorized ≠ true).

## 5b. Canonical references written (2026-09-14)

- **Master v1.0 and v1.1** formalized the identity invariant (charter,
  relationship state, autobiographical history, commitments, goals, policy,
  delegated authority, provenance) and state classes (identity-, relationship-,
  policy-critical, operational, ordinary, ephemeral). They **designed**
  relationship as a first-class entity and a functional affect architecture
  (drives → appraisal → fast affect → slow mood → expression) with an explicit
  epistemic boundary and "affect never outranks governance", and registered
  MASTER:RQ-001–121, including RQ-121 affective continuity. None of these
  relationship or affect designs was implemented; Slices 11 and 14, a few days
  earlier, had deliberately excluded affect and relationship state.
- **Master v1.1 reconciled S1 retroactively** (dispositions, not rewrites):
  "L18 is the sole LTM writer" → L18 proposes, L04 admits under consent, policy
  and privacy authority (the model 15A–15B2a had already built on
  2026-09-09/10); "online writes nothing durable" → superseded; "supersede,
  never delete" → privacy deletion takes precedence; "conscious workspace" →
  "globally available focus"; ethics advises and governance composes.
- **Infrastructure v1.0–v1.1.1** (PRIVATE HISTORICAL SOURCES; S3 SHA-256
  `ff7ed4dadb5ecd06c47e0a9ee87b6690fb810e34cd71dfae44e9d142c92caf90`) recorded the operating model at repo
  `56d7c7f`: protected main, four required checks, PR → DEV → merge → PROD,
  a verified DEV rollback test, and one GitHub deployer identity holding OS
  Admin Login on both VMs. It listed dedicated DEV/PROD deploy identities and a
  secrets broker as future targets, and a recovery inventory with explicit
  UNKNOWNs.

## 6. The repository becomes the source of truth (2026-09-13 → 09-14)

- Repository foundation (`1eee09b`): ADR-0001 (identity above runtimes),
  ADR-0002 (canonical durable state), ADR-0003 (execution ≠ verification),
  ADR-0004 (clients cannot execute capabilities), ADR-0005 (Git-driven PROD
  deployment); threat model T-01–T-14 and invariants 1–8; the in-repo research
  register RQ-001–RQ-050.
- The core API was imported (PR #1); PROD deployment became Git-driven but
  installs **only `app.py`** (PR #2); an isolated DEV pipeline was added
  (PRs #7–#10).
- **Superseded:** hand-appending to production. **Not reconciled:** `as-is.md`
  and the roadmap were written as a fresh start and did not absorb Slices
  1–15B2a (N-16).

## 7. Governed canonical runtime, dark in PROD (2026-09-22 → 09-23)

- 15B2b-A packaged the canonical runtime, adopted
  [ADR-0006](../adr/0006-family-neutral-canonical-memory-apply.md)
  (family-neutral proposal identity), added trusted exact-SHA DEV bundles, and
  proved synthetic durability on DEV while auditing PROD as dark.
- Threat model gained T-15–T-20 and invariants **#9 (only L04 may apply)** and
  **#10 (cognitive recovery cannot outrank newer Privacy suppression)**
  (`4ba8b39`).
- The three-state acceptance vocabulary (SOURCE ACCEPTED / DEV PROVEN / PROD
  DARK) first appears here.

## 8. Owner authority and broker isolation (2026-09-23 → 09-25)

- **Owner proof ≠ actor evidence.** B1a introduced a digest-bound WebAuthn
  owner proof whose only positive output is `VERIFIED_PROOF_ONLY`, explicitly
  not authority.
- **Broker isolation appears.** B1b-1 moved request construction into a
  separate memory broker with its own ledger and a conservative crash table;
  B1b-2a/2b gave it a separate OS identity, socket, and peer-credential
  checks on DEV, synthetic only. Threat model gained T-21–T-24 (`ab32f37`).
- **Trusted controls.** Pinned lifecycle profiles, history-aware retries,
  a persistent trusted snapshot tool, and premerge candidate validation were
  built — with recorded failures and owner PR-only bypass bootstraps.
- **Experiment attempt.** Stage III-A A2 built a contained one-shot crash
  experiment; the dispatch stopped at INTENT and the experiment did not run.

## 9. Deployment separated from activation (2026-09-25 → 09-26)

B1c removed routine deployer root, moved canonical activation out of the
replaceable application into an owner-signed grant checked by an isolated
verifier, and made **deployment ≠ activation** an accepted invariant alongside
model proposal ≠ authority, execution ≠ verification, memory ≠ truth.
Cross-environment PROD authority remains open debt.

## 10. Acceptance as a verifier result (2026-09-26)

The [15B2b-B design](../architecture/slice-15b2b-b-owner-memory-control-design.md)
named the remaining central gap (the application user can mint evidence),
bound owner authority to **logical** context only (no host, VM, or broker
key), and proposed that *no mutable database flag is authority*.
[B2a](../architecture/slice-15b2b-b2a-accepted-memory-verifier.md) implemented
that verifier in TEST only.

## Invariant timeline (corrected in the primary-source pass)

"First appears" is the earliest dated source that states the idea; "canonical
in" is where the repository adopted or enforced it.

| Concept / invariant | First appears | Canonical in / implemented by |
| --- | --- | --- |
| Identity above models and runtimes; Hermes is not LILITH | S4 (2026-08-24) | CA-V1 (2026-09-07); ADR-0001 and README invariant (2026-09-13); Master identity invariant (2026-09-14) |
| Model/Hermes replaceability; model-neutral identity and memory | S4 (2026-08-24) | Tool-less reasoning component, Slice 9 (2026-09-08) |
| Truth/evidence separation (truth ladder; personality never colors evidence) | S4 (2026-08-24) | Slice 7 epistemic states (2026-09-07); "memory ≠ truth" in CA-V1 §12 and 15A |
| Approval classes; exact approval before consequential action | S4 (2026-08-24) | Slices 4–5 (2026-09-07); ADR-0004 |
| Transport success ≠ task success | S5 execution contract (2026-09-06) | Slice 1 verifier (2026-09-06/07); CA-V1 §17; ADR-0003 |
| Presence is presentation, not simulated feeling | S4 (2026-08-24) | J1 Entry 4 semantic presence contract; Slice 14 Presence contract (2026-09-09) |
| 19-layer cognition | S5 backlog B06 "Brain Architecture V1" (planned, 2026-09-06) | S1 / CA-V1 (2026-09-07); Master v1.1 layer mapping (2026-09-14) |
| Planner proposes · policy governs · connectors perform · verifier proves | Slice 6 (2026-09-07) | CA-V1 (2026-09-07) |
| State durability regimes | Repo CA-V1 §7a (2026-09-07; absent from S1) | Master v1.1 disposition (2026-09-14) |
| No simulated suffering | S1 / CA-V1 §10 (2026-09-07) | Slice 11 no-affect constraints (2026-09-08) |
| Ethics may deliberate; policy governs | S1 / CA-V1 §11 | Slice 13 (2026-09-09) |
| Memory authority separated from storage (L18 proposes, L04 admits under authority) | 15A/15B1/15B2a (2026-09-09/10) | Master v1.1 disposition (2026-09-14); threat model #9, #10 (2026-09-22) |
| Relationship as a first-class entity | Master v1.0 (2026-09-14, design) | Not implemented (Slice 14 excluded relationship state) |
| Functional affect; affect never outranks governance; anti-suffering constraints | Master v1.0 §08 (2026-09-14, design) | Not implemented; MASTER:RQ-121 research |
| Clients cannot commit canonical state | ADR-0004 (2026-09-13) | Threat-model invariant #6 |
| Owner proof ≠ authority (WebAuthn, digest-bound) | B1a (2026-09-23) | No earlier source |
| Memory broker isolation (separate OS identity and ledger) | B1b-1 (2026-09-23) | B1b-2b Stage II (DEV, synthetic). Distinct from S4/Master "secrets vault/broker" for credentials |
| Deployment ≠ activation | B1c-1A (2026-09-25) | B1c acceptance. Related earlier boundary: S3 "deployment owns source delivery; it does not replace secrets, databases, memory" (2026-09-14) |
| Dedicated DEV deploy identity | S3 target (2026-09-14) | B1c (2026-09-25); PROD half still open |
| Authoritative memory acceptance = verifier output; no DB flag is authority | 15B2b-B design (2026-09-26, PROPOSED) | B2a verifier (TEST only) |

## Where current work sits (2026-09-26)

Between **design** and **first real authority** for owner-controlled memory.
Authority mechanics exist in TEST and DEV-synthetic form; no real memory,
credential, signer, or grant exists; B1b-3 custody isolation, live crash
evidence, and the cross-environment PROD debt block any real authority. The
cognitive Router lanes (7.2–14) were hand-deployed to `lilith-01` in the
pre-DEV era; their runtime source is not under `services/`, and the governed
PROD workflow installs only `app.py`, so no in-repo record shows them
re-deployed or re-verified through the governed pipeline (INFERRED). Slice 16
(sync) has not started.

## Primary-source corrections to this record

| First pass said | Corrected to | Source |
| --- | --- | --- |
| Starting point 2026-08-25, "no explicit authority model" | The 2026-08-24 blueprint already had approval classes, capability tokens, secrets vault, kill switch and audit ledger as design; none was implemented until Slices 4–6 | S4 |
| Identity above runtimes first appears in CA-V1 | First appears in S4 (2026-08-24) | S4 |
| Transport ≠ task success first appears in Slice 1 behaviour | First stated in the S5 execution contract (2026-09-06) | S5 |
| Memory ≠ truth first appears in CA-V1 §12 | The underlying truth-ladder separation appears in S4 (2026-08-24) | S4 |
| Relationship and affect concepts had no dated origin | Master v1.0 (2026-09-14) designed both; neither is implemented | S2, M1.1 |
| CA-V1 treated as one document | Two versions (S1 PDF without §7a; amended repo Markdown) | S1 |
