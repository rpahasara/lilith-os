# ADR-0014: Proposed cognitive sources are non-controlling and enter architecture through native acceptance

- **Status:** Accepted
- **Date:** 2026-10-05
- **Owners:** Project maintainers
- **Related:** ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0006, ADR-0007,
  ADR-0008, ADR-0009, ADR-0010, ADR-0011, ADR-0012, ADR-0013; ledger D-9,
  D-10, A-1, C-19, C-23; `docs/README.md` §Document authority;
  [contract index](../architecture/cognitive-contracts/v0.1/README.md);
  [Contract Source Review Manifest](../architecture/cognitive-contracts/source-review-manifest.md)

## Context

The [acceptance ledger](../architecture/current-architecture-acceptance-ledger-v0.1.md)
records owner decision **D-9**: "Which, if any, of the 16 proposed sources
(or which clauses) proceed to contract acceptance review, and through what
record?". It was UNRESOLVED when this ADR was drafted.

The 16 sources are the *Cognitive Architecture Contract Set v0.1*, a set of
design PDFs. Their [index](../architecture/cognitive-contracts/v0.1/README.md)
marks every one PROPOSED / NOT ACCEPTED.

### Repository evidence

- **OBSERVED.** The PDFs are not in this repository. They stay unmodified in
  the owner's private archive because each cites a private conversation
  identifier. The repository holds only the index and
  [`ORIGINALS.sha256`](../architecture/cognitive-contracts/v0.1/ORIGINALS.sha256)
  (index, "Why the PDFs are not committed").
- **OBSERVED.** No clause text from any source is in the repository. The
  ledger extracted text "to a private scratch location for searching only"
  (ledger §2.1). For cited clauses the ledger holds paraphrases. Every
  source is therefore index metadata only, plus ledger paraphrase.
- **OBSERVED.** Sources 07 (*Relationship Continuity*) and 08 (*Affect /
  Appraisal Research Protocol*) are regenerated editions. Their originals
  are unavailable, and the indexed bytes are "not certified byte-identical
  to the original". Their clause IDs are local to the regenerated editions
  (ledger §2.1).
- **OBSERVED.** The SHA-256 values identify bytes only (index, "Hash scope
  and verification"). They are not expected to verify against anything in
  this repository. No author is recorded. The cross-check against document
  16's source register matched "every register entry that could be extracted
  automatically"; the index does not record which entries, if any, could not
  be extracted.
- **OBSERVED.** Some source clause IDs collide with ledger row IDs. Source 01
  uses `ID-01`…`ID-05`, `AUTH-01`…`AUTH-03` and `AFF-01`; the ledger uses the
  same prefixes for its own rows. The ledger qualifies them in some rows
  ("I AUTH-01..03") and not in others.
- **OBSERVED.** ADR-0007 through ADR-0013 each decided their question on
  accepted ADRs and repository evidence, and each states that it does not
  adopt or rely on the corresponding source's clause text (ADR-0007 Context;
  ADR-0008 Context; ADR-0010 Context; ADR-0011 Context and "Adopt the
  proposed handoff state machine"; ADR-0012 "Independence from D-9";
  ADR-0013 "Independence from D-9").
- **OBSERVED.** ADR-0007, ADR-0009, ADR-0011, ADR-0012 and ADR-0013 each list
  acceptance of a proposed clause that draws their boundary differently as a
  revisit trigger.
- **OBSERVED.** `docs/README.md` ranks "Tested behavior and versioned
  contracts" first and accepted ADRs second. The ledger records the literal
  reading of that order as ambiguity A-1.
- **OBSERVED.** The repository has no mechanism for accepting a whole
  external source, a clause, a partial source or a source with exclusions.
  Existing precedents are adjacent only: digest-bound owner acceptance of an
  exact artifact set
  ([PR-3 tooling acceptance](../architecture/slice-15b2b-b1b3e-pr3-tooling-acceptance.md)),
  and metadata-and-hash manifests that prove a source exists without
  publishing it
  ([historical source manifest](../research/source-material/source-manifest.md)).

### What the evidence shows

No clause from any of the 16 sources can be reviewed for acceptance today,
because the text that would be reviewed is not in the repository. A hash
does not reveal wording, and a ledger paraphrase is not the source.

Two further risks would remain even with text. First, a PDF clause accepted
as a "versioned contract" could be read, under the literal `docs/README.md`
order, as outranking accepted ADRs. Second, accepting a clause that says
roughly what an accepted ADR already says would create two controlling texts
for one point. Both would reopen decisions that D-1 through D-8 have just
closed.

## Decision

A proposed cognitive-contract source is provenance and research input. It is
never controlling architecture. Its useful semantics enter LILITH
architecture only when they are restated in, and accepted through, a
project-native record. That native record is the controlling text.

```text
proposed source       ≠  controlling architecture
source exists         ≠  source accepted
source cited          ≠  source controlling
ledger paraphrase     ≠  source text
hash-pinned           ≠  reviewable
review eligibility    ≠  acceptance
equivalent clause     ≠  second authority
similarity/influence  ≠  acceptance
manifest disposition  ≠  architecture
```

### D-9 answer

- **Whole sources.** None of the 16 sources proceeds to wholesale
  acceptance. Whole-source acceptance is not the governance model.
- **Clauses ready for acceptance review now.** None. The repository holds no
  authoritative clause text for any source; a ledger paraphrase is not
  reviewable text. No clause is REVIEW_READY.
- **Conditional future queue.** A source-qualified clause may later become
  REVIEW_READY only after the integrity minimums in SG-6 are met. Until then
  it is NEEDS_SOURCE_TEXT. Candidate families found in D-9 discovery are kept
  in the manifest as queue hints only.
- **Through what record.** Two record types with different roles: a native
  acceptance record, which alone can make semantics controlling (SG-2,
  SG-3), and one non-authoritative Contract Source Review Manifest for
  provenance, integrity and triage (SG-4).

### Definitions

- **Proposed source.** Any of the 16 documents indexed in
  `docs/architecture/cognitive-contracts/v0.1/`, any later version or
  regenerated edition of them, and any similar external or design-phase
  document that has not been accepted as a native record.
- **Source-qualified clause ID.** A clause identifier prefixed by its source
  number, for example `01:ID-01` or `11:GC-16`.
- **Native record.** An accepted ADR, an accepted domain contract, an
  accepted policy, or another governance record that this repository
  explicitly accepts under its own rules.
- **Contract Source Review Manifest.** The single non-authoritative record
  that tracks provenance, integrity, triage, dependencies and disposition
  for proposed sources.
- **Review eligibility (REVIEW_READY).** A clause's eligibility to be
  considered by the owner as input to a native record. It confers nothing
  else.

### Rules

- **SG-1. Source status.** A proposed source is provenance and research
  input. It does not become controlling, in whole or in part, because:
  - its bytes are hash-pinned;
  - it carries a version number;
  - the ledger or any other record cites it;
  - the ledger paraphrases its clauses;
  - a clause resembles an accepted ADR;
  - the owner has reviewed it;
  - it appears in an index, manifest or README.
- **SG-2. Native acceptance rule.** Semantics from a proposed source become
  controlling only when a native record restates them in its own words and
  that native record is accepted under this repository's normal rules. The
  accepted native record is the controlling text. The proposed source
  remains provenance.
- **SG-3. Self-contained native records.** A native record that draws on a
  proposed source must be understandable and authoritative without access
  to that source. It may cite provenance (source number, version, digest,
  source-qualified clause ID). It must not incorporate source text by
  reference, depend on the source for its meaning, or require private
  material to be read.
- **SG-4. Manifest role.** The Contract Source Review Manifest records
  provenance, integrity metadata, triage, dependencies and disposition. It
  is not an ADR, a contract, a policy, an acceptance record, an authority
  grant or a controlling architecture source. No manifest field, status or
  value makes a source or clause accepted, and the manifest has no
  `ACCEPTED` status. When a native record accepts semantics drawn from a
  clause, the manifest may record `TRANSLATED_INTO <native record>`; the
  native record controls.
- **SG-5. Manifest statuses.** The manifest uses only these dispositions,
  each a triage label:
  - `NEEDS_SOURCE_TEXT` — no reviewable text in the repository;
  - `SOURCE_INTEGRITY_BLOCKED` — the source's provenance blocks review
    whatever text is supplied (SG-8);
  - `ALREADY_COVERED_BY_NATIVE_ARCHITECTURE` — an accepted native record
    already governs the topic (SG-10);
  - `TRANSLATED_INTO_NATIVE_RECORD` — a native record now controls the
    semantics;
  - `DEFER_DEPENDENCY` — an unresolved decision or policy must come first
    (SG-13);
  - `REJECT_REDUNDANT` — a recommendation not to review because the clause
    adds no architectural semantics; reversible, and not a rejection of the
    source;
  - `CONFLICT_RISK_REVIEW_REQUIRED` — the paraphrase suggests the clause may
    draw an accepted boundary differently;
  - `OUT_OF_SCOPE` — not a subject for source review (for example, existing
    authority and enforcement records);
  - `REVIEW_READY` — eligibility for owner review only (SG-6). It is not
    acceptance, and no entry in the initial manifest carries it.
- **SG-6. Integrity minimums for review eligibility.** A clause from a
  proposed source may become REVIEW_READY only when the repository holds,
  in readable form:
  1. the exact clause wording, verbatim or in a public-safe derivative that
     contains the exact reviewable wording;
  2. its source-qualified clause ID;
  3. a provenance statement for the source;
  4. the relationship of the text to the pinned source digest;
  5. where the text is a public-safe derivative of a private original, a
     sanitization and derivation record, the derivative's own digest, and an
     explanation of how it corresponds to the privately pinned original;
  6. enough evidence to tell original wording apart from reviewer
     paraphrase;
  7. the source's number, version and digest.

  Private conversation identifiers need not and must not be published to
  meet these minimums. A public-safe derivative is allowed.
- **SG-7. A hash is not text.** A SHA-256 proves expected identity only if
  the original content is later supplied and matches. It does not reveal
  clause wording and is never sufficient for semantic review.
- **SG-8. Regenerated editions.** Sources 07 and 08 are regenerated editions
  whose originals are unavailable. Their status is SOURCE_INTEGRITY_BLOCKED.
  Supplying the regenerated text alone does not make any of their clauses
  REVIEW_READY. Only a later, explicit owner provenance decision may treat a
  regenerated edition as a new reviewable source. This ADR does not make
  that decision.
- **SG-9. Native architecture precedence.** Accepted native architecture
  controls over proposed-source material and over the review manifest:
  - a proposed source cannot weaken an accepted ADR;
  - an equivalent source clause creates no second controlling text;
  - a weaker source clause has no effect;
  - a conflicting source clause cannot override an accepted ADR;
  - a stronger or additive source clause has no effect until it is
    translated into a new native record and that record is accepted;
  - a source revision has no architectural effect unless new native
    architecture is accepted.
- **SG-10. "Versioned contract" scope.** For the `docs/README.md` document
  authority order, an unaccepted proposed source is not a "versioned
  contract", and neither is the Contract Source Review Manifest. A domain
  contract accepted later as a native record takes its place in that order
  under the normal repository rules. This ADR does not rewrite
  `docs/README.md`; the general wording question stays recorded as A-1.
- **SG-11. Duplicate authority.** Where an accepted native record already
  governs a semantic point, the default disposition of a source clause on
  that point is ALREADY_COVERED_BY_NATIVE_ARCHITECTURE. It is not reviewed
  merely to create duplicate law. While source text is unavailable, this
  disposition rests on topic overlap with existing native architecture. It
  is not a finding of textual equivalence.
- **SG-12. Source revisions.** Every manifest entry is pinned to the source
  number, version and source digest, and to a derivative digest where one
  exists. A later version, a different file or a regenerated edition is a
  new review input. It inherits no disposition automatically.
- **SG-13. Dependencies.** A clause that meets SG-6 can still be
  DEFER_DEPENDENCY. Source review and native acceptance of source-derived
  semantics must not resolve an open owner decision, policy or conflict by
  side effect. The dependency's own record decides it first.
- **SG-14. Source-qualified identifiers.** Every source review entry uses a
  source-qualified clause ID. A bare clause ID is not used where a collision
  with another source or with a ledger row ID is possible.
- **SG-15. Provenance honesty.** Where authorship or provenance is not
  recorded, the manifest records it as UNKNOWN / not recorded. It is not
  inferred. A private conversation identifier is not authorship and is never
  published.
- **SG-16. No side effect.** None of the following accepts a proposed source
  or clause, or makes it controlling: citation; paraphrase; triage;
  inclusion in the manifest or a queue; a REVIEW_READY label; owner review;
  similarity to, or influence on, an accepted native record; indexing (D-10).

### Independence of ADR-0007 through ADR-0013

ADR-0007 through ADR-0013 were decided on accepted ADRs and repository
evidence, without accepting any proposed source. This ADR does not
retroactively reframe any of them as acceptance of `11:GC-16`, `15:E-25`,
`15:E-26`, any `04:AH-*`, `13:LS-*`, `06:PE-*` or `16:COMP-*` clause, or any
other proposed clause. Each accepted ADR remains the sole native controlling
source for its decision. Similarity or influence is not acceptance.

### Non-goals

This ADR does **not**:

- accept any of the 16 proposed sources, or any clause, in whole or in part;
- treat any ledger paraphrase as source text;
- make any clause REVIEW_READY;
- make the sources 07 and 08 provenance decision;
- create, authorize or publish a public-safe derivative, or authorize access
  to the private archive;
- publish any private conversation identifier;
- rewrite the `docs/README.md` document authority order (A-1 stays open);
- change any ledger coverage classification or total;
- change D-10, which stays RESOLVED FOR DISCOVERABILITY ONLY;
- resolve C-20, GOAL-04, EPI-11, C-22, EPI-08, C-07, C-15, G1, G2 or R1;
- create a capability, privacy / model-route, source-trust or substrate-drift
  policy;
- designate a session or presence owner, or make the identity charter
  decision (15B2b-B owner decision 2);
- change the affect deferral;
- change any code, schema, runtime, deployment or live state;
- change B-5 (WITHHELD), FRESHNESS (UNKNOWN), M-B1 or First Memory (NOT
  AUTHORIZED), or the substrate-drift policy (OPEN);
- change GOAL-06 or EPI-07, which stay CONFLICT.

## Compatibility with accepted ADRs

| ADR | Relationship | Result |
| --- | --- | --- |
| ADR-0001 | Identity and governed state exist above runtimes. SG-3 keeps controlling text native and readable rather than dependent on an external artifact | Agrees |
| ADR-0003 | Execution is not verification. SG-7 and SG-16 apply the same separation to source material: a hash or a review is not acceptance | Agrees; analogy |
| ADR-0006 | Controls canonical memory apply. Memory clauses default to ALREADY_COVERED where ADR-0006 governs the topic (SG-11) | Agrees; unchanged |
| ADR-0007 | Proposal is not acceptance, and the destination governs acceptance. SG-2 and SG-4 apply this to source material: the manifest proposes nothing into architecture by itself | Agrees; applies |
| ADR-0008 … ADR-0013 | Each decided its question without the source text and lists differently drawn clause acceptance as a revisit trigger. SG-9 and SG-11 mean an equivalent clause cannot become a second authority and a conflicting one cannot override the ADR; only a new accepted native record could change them, through the ADR's own supersession rules | Agrees; protects |

ADR-0002, ADR-0004 and ADR-0005 are not materially affected. No accepted ADR
is amended or superseded. No conflict with an accepted ADR was found.

## Interaction with unresolved items

| Item | Relationship |
| --- | --- |
| D-9 | Resolved by owner acceptance of this ADR (2026-10-05), as source governance only; no source or clause accepted |
| D-10 | Unchanged: RESOLVED FOR DISCOVERABILITY ONLY. Indexing is not acceptance (SG-16) |
| A-1 | SG-10 settles the scope question for proposed sources and the manifest only. The general `docs/README.md` wording stays open |
| C-19, C-23 | Unchanged. Resolved by ADR-0012 and ADR-0013 independently of D-9 |
| GOAL-06, EPI-07 | Unchanged: CONFLICT (implementation diverges from accepted ADRs) |
| C-20, GOAL-04, EPI-11, C-22, EPI-08, C-07, C-15 | Unchanged; dependent clause families are DEFER_DEPENDENCY |
| G1, G2, R1 | Unchanged; OPEN |
| Substrate-drift policy; B-5; FRESHNESS; M-B1; First Memory | Unchanged |

## Alternatives considered

### Whole-source acceptance (Model A)

Accept or reject each PDF as one contract. Simple, but it would accept
clauses that duplicate or may conflict with ADR-0007 through ADR-0013, along
with clauses blocked on open decisions. The text is private and two sources
are regenerated, so the controlling text would be unreadable in this
repository.

### Clause-level acceptance of source text (Model B)

Accept clauses by ID and digest. Precise, but no clause text is in the
repository, IDs collide with ledger rows, and an accepted clause would sit
beside the ADRs as a second controlling text. A paraphrase could quietly
become the working version of a clause.

### A curated manifest that accepts clauses (Model C)

A manifest with accepted, rejected and deferred clause lists. It fits
existing manifest and digest-acceptance precedents. As an *accepting* record
it still needs absent text and still creates duplicate authority. This ADR
keeps the manifest and removes its power to accept (SG-4).

### Status quo

D-9 stays open with no mechanism. Each later decision would re-argue whether
a PDF clause binds, and the literal reading of "versioned contracts" would
stay available as a route around accepted ADRs.

## Consequences

### Positive

- One controlling text per semantic point, always native and public.
- Accepted ADRs cannot be weakened or reopened by source acceptance through
  a side door.
- Source revisions, regenerated editions and private-only text have no
  architectural effect.
- Useful source semantics still have a defined path into architecture.

### Negative and tradeoffs

- Useful source wording must be restated, which can drift from the source's
  intent; SG-6 text review mitigates this when text exists.
- Nothing from the sources can be reviewed until a public-safe derivative
  process supplies text.
- The manifest needs upkeep as native records and dependencies change.

### Operational and migration impact

None. No code, schema, data, route, runtime or deployment changes.

## Security, privacy, and trust boundaries

- Private conversation identifiers stay unpublished; SG-6 needs only a
  public-safe derivative and a correspondence record.
- Closes a governance path by which unreviewable or private text could gain
  authority over accepted decisions.
- Adds no new personal data class.

## Validation

Acceptance proves no conformance. Later evidence that the rule holds:

- every native record that draws on a proposed source is readable and
  authoritative without that source;
- the manifest contains no `ACCEPTED` status and no field whose value
  confers acceptance;
- every manifest entry carries a source-qualified ID and is pinned to
  source number, version and digest;
- no entry becomes REVIEW_READY without the SG-6 evidence;
- sources 07 and 08 stay SOURCE_INTEGRITY_BLOCKED until an explicit owner
  provenance decision exists;
- no accepted ADR is cited as superseded or amended by source material.

## Revisit triggers

- An owner decision that a proposed source should be accepted directly
  rather than through native records.
- A public-safe derivative process that cannot preserve exact wording.
- An accepted change to the `docs/README.md` document authority order (A-1).
- An external standard that the project must adopt by reference rather than
  restate.

## Open follow-ups

- D-9 is resolved by owner acceptance of this ADR (2026-10-05). Acceptance
  accepts the source-governance mechanism only (SG-1 … SG-16). It accepts
  none of the 16 proposed sources, no clause from them, no ledger paraphrase
  and no conditional queue item. No clause is REVIEW_READY: the repository
  holds source metadata, version information, pinned SHA-256 values and
  ledger paraphrases only, and none of these is reviewable clause text. The
  [Contract Source Review Manifest](../architecture/cognitive-contracts/source-review-manifest.md)
  stays non-authoritative triage and provenance only; acceptance of this ADR
  does not upgrade it. Every current candidate stays NEEDS_SOURCE_TEXT or
  under a stronger blocker (SOURCE_INTEGRITY_BLOCKED, DEFER_DEPENDENCY,
  ALREADY_COVERED_BY_NATIVE_ARCHITECTURE, OUT_OF_SCOPE,
  CONFLICT_RISK_REVIEW_REQUIRED). Sources 07 and 08 stay
  SOURCE_INTEGRITY_BLOCKED; no owner provenance decision is made.
  ADR-0007 through ADR-0013 remain independently accepted native
  architecture; this ADR does not turn their influences or similarities into
  acceptance of any source 16 owner-domain clause, `06:PE-*` or source 01
  personality clause, `04:AH-*` or `12:IA-*` enforcement clause, `13:LS-*`
  clause, `04:AH-*` handoff clause, `11:GC-16`, or `15:E-25` / `15:E-26`.
  No private archive or source was accessed, no public-safe derivative was
  created, and no runtime, code, schema or live change occurred. No
  unresolved dependency is decided: C-20, GOAL-04, EPI-11, C-22, EPI-08,
  C-07, C-15, G1, G2, R1, the capability, privacy / model-route, source-trust
  and substrate-drift policies, the identity charter (owner decision 2),
  First Memory authorization, the affect deferral and session / presence
  ownership remain open. D-10 is unchanged (RESOLVED FOR DISCOVERABILITY
  ONLY). B-5 stays WITHHELD, FRESHNESS UNKNOWN, M-B1 and First Memory NOT
  AUTHORIZED, and the substrate-drift policy OPEN.
- A public-safe derivative process for any source the owner wants reviewed
  (separate track, separately authorized; index "Why the PDFs are not
  committed").
- An owner provenance decision on sources 07 and 08, if ever wanted.
- A-1: general cleanup of the `docs/README.md` precedence wording.
- Completing the record of which document 16 register entries were checked.

## Hidden-assumption review

What could make this design look correct while it is wrong?

- **The manifest is harmless because it is only triage.** A disposition such
  as ALREADY_COVERED could be read as a finding of equivalence. SG-11 states
  it is topic overlap only while text is absent.
- **Restating a clause natively is neutral.** Restatement is where meaning
  can shift. SG-6 requires the exact text before any native record is
  drafted from a clause.
- **A hash makes a private source auditable.** It makes the bytes
  identifiable, not the meaning reviewable (SG-7).
- **The ledger paraphrases are accurate enough.** They were written from
  privately extracted text that the repository cannot check; their accuracy
  is UNKNOWN.
- **No source can ever bind, so the sources do not matter.** They matter as
  provenance and input; SG-2 keeps the path open.
