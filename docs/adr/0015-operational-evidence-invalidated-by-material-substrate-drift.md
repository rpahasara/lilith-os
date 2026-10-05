# ADR-0015: Operational evidence is invalidated by material substrate drift, not unrelated change

- **Status:** Accepted
- **Date:** 2026-10-05
- **Owners:** Project maintainers
- **Related:** ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0006, ADR-0007,
  ADR-0009, ADR-0011; ledger D-4, AUTH-02, AUTH-05, FM-04, REC-06, COMP-G,
  C-15, C-16, EPI-08;
  [companion operational policy](../architecture/substrate-drift-and-evidence-revalidation-policy-v0.1.md);
  [Condition 3 STOP](../architecture/slice-15b2b-b1b3e-condition3-fresh-pr2-stop.md) §5 item 3;
  [B-5 re-decision (WITHHELD)](../architecture/slice-15b2b-b1b3e-b5-pr1b-authorization-withheld.md) §3

> **Accepted by the owner (2026-10-05), as architectural and governance
> acceptance only.** Together with the accepted companion policy, it resolves
> the substrate-drift policy that the D-4 owner records left OPEN. Neither
> record authorizes any live action or implementation follow-up, and neither
> changes the operational posture: B-5 WITHHELD, `FRESHNESS=UNKNOWN`,
> Condition 3 historical closure only (current satisfaction NOT ESTABLISHED),
> M-B1 NOT AUTHORIZED, First Memory NOT AUTHORIZED.

## Context

### Why a decision is required

- **OBSERVED.** The
  [Condition 3 STOP](../architecture/slice-15b2b-b1b3e-condition3-fresh-pr2-stop.md)
  (2026-10-02) found `BROKER_PRESERVATION=FAIL` while every other observation
  equalled the accepted pre-B-5 revalidation. The cause was a routine
  unattended `libssl3t64` / `openssl` upgrade on 2026-10-01. It replaced
  `libcrypto.so.3` on disk under a broker that, by design, is not restarted.
  The running process kept mapping the deleted file
  (`RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE`). No authority or state mutation
  was observed. The failure voided the B-5 grant under the
  [decision packet](../architecture/slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md)
  §9.
- **OBSERVED.** STOP §5 item 3 names a "substrate drift policy" and says the
  condition "will recur whenever a mapped library is upgraded". The owner was
  to choose; the record did not.
- **OBSERVED.** The [B-5 re-decision](../architecture/slice-15b2b-b1b3e-b5-pr1b-authorization-withheld.md)
  §3 records the policy as **OPEN**: "not required to withhold B-5. It must be
  resolved before a future B-5 re-grant can progress to eligibility." Ledger
  D-4 and AUTH-02 repeat this.
- **OBSERVED.** The later
  [Condition 3 PASS](../architecture/slice-15b2b-b1b3e-condition3-fresh-pr2-pass.md)
  set its validity window ad hoc: valid only if eligibility and M-B1 finished
  before the next `apt-daily-upgrade` run (2026-10-03T06:39Z). The window
  passed with no eligibility run. The
  [C-04 disposition](../architecture/slice-15b2b-b1b3e-condition3-c04-owner-disposition.md)
  records that historical closure lapsed and Condition 3 is not satisfied
  today.
- **OBSERVED.** No repository record defines when a substrate change is
  *material* to a piece of operational evidence. Records apply per-case
  judgments instead:
  - the STOP treated unmapped package upgrades (`libheif*`, `libxpm4`, the
    `snapd` refresh) as non-material;
  - the pre-B-5 revalidation and the Condition 3 PASS state that a routine
    deployment whose DR-5 result set equals the accepted one is not a
    topology change;
  - the reboot comparator (`scripts/compare_reboot_host_observations.py`)
    lists exactly which observed facts a reboot or a routine deployment may
    change.

### Repository precedents this ADR builds on

- **OBSERVED.** Evidence is already bound to precise substrate identifiers.
  `scripts/verify_broker_dev_current_incarnation.py` (`preservation`) pins:
  - host identity: hostname, FQDN, machine-id, GCE instance name and ID;
  - boot ID;
  - InvocationID, PID, start ticks and `NRestarts`;
  - release SHA and manifest;
  - unit, config and state file digests and ownership;
  - sandbox, account, socket, Stage III and deployer-policy facts;
  - every mapped shared library (inode, not deleted, SHA-256);
  - a canonical `baselineCandidate` digest.

  The observer's `stableSha256` and per-section digests, the DR-5 result-set
  digests and evidence `SHA256SUMS` play the same role elsewhere.
- **OBSERVED.** Process replacement ends broker acceptance. DR-1 and the
  runtime-baseline and reboot-rebaseline records state: "Any process
  replacement ends this acceptance: a restart, needrestart,
  `Restart=on-failure`, a reboot, or a fault reset." Retired incarnations are
  "never accepted by any operation".
- **OBSERVED.** The records separate a changed process from a mutated
  authority: "automatic restart ≠ unauthorized authority mutation" and
  "process replacement still requires revalidation evidence" (DR-1).
- **OBSERVED.** The open-risk acknowledgement OR-8 makes the PR-2 inventory
  point-in-time, void on topology change "or time passing before the next
  PR-1B step". P3-5 §13 requires a PR-2 revalidation immediately before
  `CHECK_ELIGIBILITY` and again before `GENERATE_K_WIT`.
- **OBSERVED.** `evaluate_eligibility`
  (`services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py`)
  takes plain booleans, including `pr2InventoryRevalidated` and
  `noUnreviewedTopologyChange`. It carries no window, digest or substrate
  identity, so it cannot tell a freshly proven `True` from a historical one.
  Only governance (the C-04 disposition) prevents a stale PASS from being
  supplied.
- **OBSERVED.** The word "freshness" carries three meanings in the repository.
  1. Owner off-host freshness (`owner_freshness.py`: `CURRENT`, `STALE`,
     `FRESHNESS_UNKNOWN`, …), the posture value `FRESHNESS=UNKNOWN`. It
     compares a witness head with the owner register and "proves nothing about
     time".
  2. "INDEPENDENTLY PERSISTED FRESHNESS STATE = NONE", about rollback
     independence (PR-2).
  3. "Fresh PR-2", meaning chronological recency combined with substrate
     equivalence.
- **OBSERVED.** Whole-host / whole-disk rollback can present a self-consistent
  old authority world. Rollback resistance is NOT ESTABLISHED (PR-2; ledger
  AUTH-05).

### Accepted architecture constraints

- **ADR-0001.** Continuity sits above replaceable substrates. A process, VM or
  runtime is not the source of identity or trust.
- **ADR-0002.** Durable records need stable identities, auditable provenance
  and tamper-evident operational evidence.
- **ADR-0003.** Verification is separate from execution. Unknown and partial
  outcomes are first-class, and a stability window is a recognized form of
  verifier independence.
- **ADR-0005.** Git is canonical. Deployment success is not inferred from
  command completion.
- **ADR-0006.** Missing or malformed state fails closed. Preservation-sensitive
  operations require freshly verified evidence.
- **ADR-0007.** OD-10: ownership grants no freshness or currentness. An
  unknown outcome stays unknown and is never resolved by recency.
- **ADR-0009.** EB-2 refuses expired or mismatched authorization. EB-11 never
  reads an unknown outcome as permitted. EB-12: authorization does not
  establish freshness or currentness.
- **ADR-0011.** CX-6 fails closed on unknown classification inputs. CX-14:
  discontinuity is represented, not masked.

## Decision

LILITH adopts a **layered substrate-drift model** for operational evidence.
Evidence stops being reusable when **material** substrate drift affects it, or
when its time validity lapses. Unrelated change does not invalidate it.

### SD-1 Four separate dimensions

Every judgment about operational evidence keeps these four dimensions
separate. None implies another.

| # | Dimension | Question |
| --- | --- | --- |
| 1 | **Time validity** | Is the evidence still within its accepted chronological validity window? |
| 2 | **Substrate equivalence** | Do the substrate dimensions relevant to the evidence remain materially equivalent to its evidence-bound baseline? |
| 3 | **Evidence currentness (usability)** | May the evidence still support a present gate or decision? |
| 4 | **Control state** | Is the underlying control actually PASS, FAIL or UNKNOWN? |

Evidence is **current** only when it satisfies every time-validity and
substrate-equivalence requirement of the gate that uses it, and no applicable
stop or revalidation rule has fired.

Consequences:

- Time expiry can make evidence non-reusable without showing a control
  failure.
- Substrate drift can make evidence non-reusable without showing a control
  failure.
- A control can fail while other evidence stays current.
- An item can be chronologically recent and substrate-invalidated, or
  substrate-equivalent and time-expired. Where a gate requires both, both
  must hold.
- **No current evidence means UNKNOWN / REVALIDATE, not FAIL.**

### SD-2 Separation from owner FRESHNESS

```text
owner FRESHNESS != evidence time validity != substrate equivalence != evidence currentness
```

This ADR does not redefine owner `FRESHNESS`. `FRESHNESS_UNKNOWN`, `CURRENT`
and the other `owner_freshness` states keep their existing owner / off-host
witness meaning. "Fresh" in phrases such as "fresh PR-2 revalidation" means
newly collected evidence. It is described in this ADR's terms (time validity
and substrate equivalence), not in owner-freshness terms.

### SD-3 Material drift

A substrate change is **material** to an evidence item when either:

- the changed dimension can affect the property the evidence purported to
  prove; or
- an accepted global invalidator (SD-5) applies.

Materiality therefore depends on the property and the evidence, except for
accepted global invalidators. It is **not** defined as "anything on the host
changed". It is **not** defined by elapsed time, which is the separate time
validity dimension.

### SD-4 Three layers

1. **Layer 1: trust-critical / global drift.** An accepted global invalidator
   makes the broad evidence set it governs not reusable, whatever narrower
   dependencies the evidence declares.
2. **Layer 2: dependency-bound material drift.** An ordinary substrate change
   makes non-reusable only the evidence whose relevant dependencies include
   the changed dimension.
3. **Layer 3: non-material drift.** A change outside an evidence item's
   relevant dependency set does not, by itself, invalidate that evidence.

Layer 3 is not a general exemption. A change counts as non-material only for
evidence whose relevant dependencies are known and do not include it.

### SD-5 Global invalidators

The global class contains only changes that existing repository stop and gate
behavior already treats as broad invalidators. The companion policy lists
them with their sources. In summary:

- host identity replacement or mismatch;
- an unreviewed rollback-domain or topology change (snapshot, image, clone,
  disk attach or change, backup / Backup and DR relationship);
- an IAM or service-account policy change relevant to the trusted boundary;
- a change to authority material, trust roots, or the reviewed verifier,
  sequencer or owner-freshness tool, where existing stop conditions apply;
- a change to burned identities, `REAL_ACCEPTANCE_ENABLED` or authority state
  covered by existing stop conditions;
- a replica continuity violation, or a prohibited nested replica;
- an unreviewed bundle affecting the trusted boundary;
- an unexplained broker start or process replacement where an existing
  ceremony treats it as STOP;
- compromise or loss of a custody device, where accepted records already treat
  it as a stop condition.

Network-exposure change and clock-trust failure are **not** global
invalidators under this ADR. The repository does not establish them as such.
Adding them, or any other global invalidator, is later policy work and needs
owner acceptance.

When a global invalidator applies, the affected operational evidence becomes
**NOT REUSABLE / REVALIDATE** until the applicable re-establishment procedure
succeeds. That does not by itself show any control failed.

### SD-6 Unknown relevance fails closed as not-reusable

```text
UNKNOWN drift relevance -> evidence not reusable (REVALIDATE; currentness not established)
UNKNOWN drift relevance -/-> control failed
not currently proven != proven false
```

Evidence is not reusable when either:

- it is unknown whether a change is material to it; or
- the evidence does not identify enough of its dependencies to decide.

This uses the ledger's existing currentness value `REVALIDATE`.

### SD-7 Evidence dependency binding

Each future operational evidence package should identify the substrate
dependencies relevant to the property it proves. The binding must be precise
enough to decide later whether a given drift affects the evidence.

This ADR defines no schema and mandates no field set. Fields will differ by
evidence class. Candidate fields include:

- evidence ID, subject or control, and the property proven;
- observation window;
- host identity, relevant digests and versions;
- boot or process incarnation, and deployment revision, where applicable;
- the declared dependency set;
- the time-validity origin and window;
- revalidation triggers;
- verifier and provenance;
- result.

The repository commit or control SHA is provenance. It is a dependency only
where the evidence explicitly binds to it.

### SD-8 Process replacement, restart and reboot

- A broker process replacement ends acceptance of that specific incarnation.
  This applies whether the replacement is a same-boot restart, needrestart,
  `Restart=on-failure`, a reboot or a fault reset.
  - Earlier broker-preservation evidence is not reusable.
  - The prior incarnation is retired.
  - A new incarnation must be re-established before broker-preservation
    evidence can be current again.
- **Process replacement ≠ authority mutation.** A restart does not by itself
  show that authority changed or that state was corrupted. An unexplained
  replacement is investigated (DR-1 precedent), and existing ceremonies treat
  it as STOP where they say so.
- This ADR creates **no carry-forward** of process-bound evidence across a
  restart. Whether a controlled restart may later be revalidated more narrowly
  than a full PR-2 window is a separate owner decision.
- A reboot invalidates the evidence that depends on the boot:
  - broker incarnation evidence;
  - P1A-9, where current records require it;
  - pre-reboot DR-5, where the existing ceremony forbids reuse.

  A reboot does not, by itself, invalidate evidence whose dependencies exclude
  the boot. The companion policy states per-evidence consequences.

### SD-9 Host identity is a binding, not a trust source

```text
same host != automatically trusted
different host != impossible continuity
```

- Current host-bound evidence binds to host identity. On a replacement VM,
  clone or rebuilt host it is not portable without re-establishment.
- ADR-0001 places continuity above substrate identity. A future accepted,
  verified migration or re-establishment contract may allow continuity onto a
  replacement host. This ADR creates no such path.

### SD-10 Rollback debt is unchanged

This ADR does not solve undetectable whole-host rollback. A self-consistent
restored snapshot may present old substrate identifiers that match the
evidence.

- If a restore or topology change is known, the affected evidence is not
  reusable.
- If a restore is undetected, it remains the existing accepted rollback and
  freshness debt.

AUTH-05, C-15, C-16, EPI-08 and related findings are not closed.

### SD-11 Composite gates

A gate built from several evidence items is current only when every required
item is current. If one required item becomes non-reusable:

- the composite cannot be claimed satisfied;
- other components that remain current are not thereby shown failed.

Applied to Condition 3:

- **Historical closure is not current satisfaction.** Current Condition 3
  satisfaction is **NOT ESTABLISHED**.
- A future Condition 3 window must bind to the then-current accepted, or
  revalidated, substrate evidence under this ADR and the companion policy.

### SD-12 Eligibility inputs must be current evidence

An eligibility boolean that represents an evidence-backed condition (for
example `pr2InventoryRevalidated` or `noUnreviewedTopologyChange`) may be
supplied as `True` only when evidence supports it that is current under:

- its applicable time-validity requirement;
- its applicable substrate-equivalence requirement;
- every relevant accepted stop and revalidation rule.

**A stale historical PASS may not be converted directly into a current
eligibility `True`.**

This is a governance requirement on whoever supplies the input. It does not
change `evaluate_eligibility`. Passing structured evidence instead of plain
booleans is later implementation work.

### SD-13 B-5 ordering and stop semantics

The ordering this ADR recognizes:

```text
substrate-drift policy accepted
  -> fresh evidence package / B-5 packet prerequisites
  -> new explicit owner B-5 decision
  -> required fresh revalidation immediately before eligibility
  -> CHECK_ELIGIBILITY
  -> separate M-B1 go statement
  -> M-B1
```

Accepting this ADR or its policy grants **none** of these steps. A future B-5
grant remains a separate, explicit owner decision.

Existing B-5 stop conditions (decision packet §9) continue to control that
grant. A stop condition may void the grant, or invalidate evidence, as the
accepted B-5 records say. That does not mean every drift event shows every
underlying control failed. This ADR does not weaken any stop condition.

### SD-14 No new evidence epoch

This ADR introduces **no** new global evidence-epoch identity. The repository
already has:

- boot IDs and InvocationIDs;
- broker candidate digests;
- observer stable and section digests;
- the retired-baseline lineage;
- DR-5 result-set digests;
- evidence `SHA256SUMS`;
- control and tool SHAs.

What is missing is dependency binding and validity / revalidation rules (SD-7,
SD-1). A future implementation may add an aggregate evidence-package ID. It
would be an index over existing identifiers, not a new trust primitive.

### SD-15 Ownership of detail

This ADR owns the principles SD-1 … SD-14. The companion
[operational policy](../architecture/substrate-drift-and-evidence-revalidation-policy-v0.1.md)
owns the concrete content:

- the global-invalidator list with sources;
- per-evidence dependency sets;
- the materiality examples;
- the portability / revalidation matrix;
- the Condition 3, B-5 and eligibility procedures.

Those tables are operational policy. They can be revised by owner-accepted
policy change without amending this ADR, provided they stay within SD-1 …
SD-14.

## Alternatives considered

### Option A: invalidate broadly on any substrate drift

All operational evidence becomes non-reusable on any observed host change.

- **Why not selected:** simple to audit, but brittle. Daily apt activity,
  timers, snap refreshes and routine deploys would force constant
  recollection. The repository already had to make reviewed exceptions for
  each of them.
- It also contradicts the STOP's own reasoning that unmapped packages are not
  material, and it does not detect rollback any better.

### Option B: dependency-bound targeted invalidation only

Only evidence whose declared dependencies changed is invalidated.

- **Why not selected alone:** low cost and good for automation, but its safety
  depends on complete dependency declarations. An undeclared dependency would
  become a silent hole.
- It would drop the broad stop behavior (B-5 §9, `HOST_MISMATCH`) that the
  repository already relies on for trust-critical change.

### Option C: layered (selected)

Global trust-critical invalidators, plus dependency-bound invalidation, plus
an explicit non-material layer and an unknown-relevance fail-closed rule.

- This is closest to existing practice: B-5 §9, the verifier, the reboot and
  routine-deploy comparator, and OR-8.
- The global layer covers gaps in dependency declarations.

### Status quo

The policy stays OPEN, and materiality is judged case by case. Validity windows
are set ad hoc. Eligibility booleans can be supplied without any rule tying
them to current evidence. The B-5 re-decision records that a future re-grant
cannot progress to eligibility in this state.

## Consequences

### Positive

- Drift no longer automatically reads as control failure. Records can say "not
  reusable / REVALIDATE" without asserting FAIL.
- Unrelated change (docs-only commits, unmapped packages, accepted volatile
  facts) no longer forces every piece of evidence to be recollected.
- Trust-critical change keeps its broad, fail-closed effect.
- Eligibility inputs gain a written currentness requirement, closing the
  governance gap behind the C-04 disposition.
- Owner `FRESHNESS` stays unambiguous.

### Negative and tradeoffs

- Dependency binding is mostly a convention until evidence contracts and
  tooling implement it. Until then, unknown relevance fails closed, which can
  force recollection.
- The global list is deliberately conservative and may miss classes such as
  network exposure until policy work adds them.
- Validity-window lengths are not set here. Each gate still needs an
  owner-accepted window where it requires one.

### Operational and migration impact

- None immediately. No code, schema, runtime, package, timer, needrestart or
  verifier constant changes.
- Historical records are not edited. They keep their original meaning and
  stay HISTORICAL / REVALIDATE.
- Follow-up evidence-contract and implementation work is listed in the
  companion policy. None is authorized here.

## Security, privacy, and trust boundaries

- No authority, credential, key or trust-root change. No new route to
  authorization: evidence that is current under this ADR still authorizes
  nothing by itself (ADR-0009 EB-12).
- The global-invalidator layer keeps trust-critical change fail-closed.
- The unknown-relevance rule (SD-6) prevents evidence with unclear relevance
  from being silently reused.
- Accepted rollback debt is unchanged and stays visible (SD-10).

## Validation

Acceptance is a documentation decision. Evidence that the decision works would
come later, from separately authorized work:

- each future operational evidence record states its property, relevant
  dependencies and time-validity origin (SD-7);
- reviews of future Condition 3 and eligibility records check every
  eligibility `True` against current evidence (SD-12);
- drift events are recorded as not reusable / REVALIDATE without a FAIL claim,
  unless a control check actually failed (SD-1, SD-6);
- regression tests for any later structured-eligibility or dependency-manifest
  implementation.

## Revisit triggers

- A verified host migration or re-establishment contract is proposed (SD-9).
- Evidence of a drift class that the global list or dependency sets missed.
- Structured eligibility evidence or dependency manifests are implemented.
- Whole-host rollback resistance or independent freshness is established
  (AUTH-05).
- An owner decision on controlled-restart revalidation, package holds,
  needrestart posture, validity windows, network exposure or clock trust.

## Non-goals

This ADR does not:

- grant B-5, establish a Condition 3 PASS, run `CHECK_ELIGIBILITY`, authorize
  or run M-B1, create K-ROOT or K-WIT, or authorize First Memory;
- contact DEV_SYNTHETIC or Replica B, or observe any live state;
- install package holds, change apt timers or needrestart, restart or reboot
  the broker or host, or re-pin verifier constants;
- modify runtime, code or schema;
- close G1, G2, C-15, C-16, EPI-08 or AUTH-05;
- resolve or redefine owner `FRESHNESS`;
- solve whole-host rollback debt;
- accept any proposed cognitive source or clause;
- decide the identity charter, or capability, model-route or source-trust
  policy;
- set validity-window durations;
- decide whether a controlled restart can avoid a full PR-2;
- normalize tool-hash types (git blob SHA vs file SHA).
