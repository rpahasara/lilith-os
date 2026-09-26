# Research Charters

Status: **RESEARCH / DESIGN CHARTERS.** A charter is a long-term research
doctrine that constrains future design and experiments. A charter is not:

- an acceptance record;
- an implementation record;
- a completed architecture;
- an activation authorization;
- scientific evidence.

It does not prove cognition, emotion, or consciousness, and it changes no
acceptance state. Implemented claims are sourced only from the architecture
acceptance and implementation records.

Charters are current, living documents. They are kept here rather than under
[source-material/originals](../source-material/originals/), which holds
recovered historical sources.

| Charter | Version | Date | Role |
| --- | --- | --- | --- |
| [LILITH Cognitive Continuity, Memory & Substrate Research Charter](lilith-cognitive-continuity-research-charter-v0.1.md) | 0.1 | 2026-09-26 | Cross-slice research and design charter for identity continuity, selective memory, substrate replacement, affect, relationship cognition, artificial welfare, governance separation, and future multi-runtime work |

## Document control

Each artifact has one role:

| Artifact | Role | SHA-256 (as committed) | Bytes |
| --- | --- | --- | --- |
| [LILITH_Cognitive_Continuity_Research_Charter_v0.1.pdf](LILITH_Cognitive_Continuity_Research_Charter_v0.1.pdf) | Polished rendered artifact (public-safe derivative) | `dbcf21edc215a82cb2d50ad5b83ea9a3b93e356229ee7ad13f389bc2f8128878` | 157,211 |
| [LILITH_Cognitive_Continuity_Research_Charter_v0.1.docx](LILITH_Cognitive_Continuity_Research_Charter_v0.1.docx) | Editable artifact (public-safe derivative) | `3cada5c3005649b70204cb353ad60c2e24a9c75010f6d45ca3cefcbb3ff2cec4` | 58,459 |
| [lilith-cognitive-continuity-research-charter-v0.1.md](lilith-cognitive-continuity-research-charter-v0.1.md) | Repository-readable, diffable transcription (not byte-identical to either) | `24cd11d03e33922410f36f1d0e3b4f8d34f7aac46cf08b0c58a2d3e26f036fb0` | 52,185 |

- **Hash scope.** Hashes are of the Git blob content (`git show
  <commit>:<path> | sha256sum`), so they do not depend on line endings.
- **Precedence.** If the Markdown and the PDF ever disagree in substance, the
  PDF is the reference rendering, and the discrepancy is a transcription
  defect to fix in a pull request.
- **Repository notes.** The transcription marks its own cross-reference
  additions as **Repository note**. Those blocks are not part of the charter.

### Sanitization record

The repository is public. Before commit, both owner-supplied originals were
reviewed for:

- secrets, tokens, passwords, keys, and credentials;
- IP addresses, cloud project and account identifiers, and service accounts;
- local usernames and paths, private email addresses, and conversation or
  thread identifiers;
- hidden metadata, comments and tracked revisions, embedded attachments, and
  embedded fonts;
- confidential third-party information.

| Finding | Action |
| --- | --- |
| The provenance paragraph named an internal conversation/thread identifier (DOCX `word/document.xml`; PDF page 3) | **Redacted in both derivatives.** The sentence now reads: "Primary project source: owner-reviewed LILITH continuity and research-doctrine design discussions, 26 September 2026." The identifier is not published anywhere in this repository. |
| PDF embeds Calibri **subsets** (about 105 glyphs, OS/2 `fsType` 8, editable embedding permitted), not full font files | Kept as subsets. The redacted paragraph was re-set in Calibri, and the whole file was re-subset so that no full font program is embedded. No other page changed: all 19 other pages render pixel-identically to the original, and the page-3 change is confined to the provenance paragraph. |
| DOCX embeds no fonts and contains no comments, tracked revisions, media, or attachments. Its thumbnail is blank. Its core properties are generic template values. | No change beyond the redaction; every other DOCX part is byte-identical to the original |
| No secrets, credentials, keys, IPs, cloud identifiers, local paths, or email addresses. (The words "secret" and "token" appear only as prose.) | None needed |

Original local artifacts (preserved unmodified outside the repository; not
committed):

| Original | SHA-256 | Bytes |
| --- | --- | --- |
| `LILITH_Cognitive_Continuity_Research_Charter.pdf` | `91e27215876c5a043e48d62aa5179084bd54a953835acb73a0cab26d5062ac78` | 115,217 |
| `LILITH_Cognitive_Continuity_Research_Charter.docx` | `2b376c2edb18f674a5c3e7009c5e0e952577b5d0952e84a00b9d94207e8db044` | 58,504 |

Only one copy of each original was found. The repository files are
**public-safe derivatives**, not the originals.

## Status labels (charter vocabulary)

| Label | Meaning | Does **not** mean |
| --- | --- | --- |
| CANONICAL | Governing project principle; a normative commitment | Implemented, TEST-proven, DEV-proven, or accepted runtime behaviour |
| DESIGN | Current, revisable mechanism or direction | Approved scope or implementation |
| RESEARCH / OPEN | Unresolved question requiring design or empirical study | Anything settled |

These are the charter's own labels. For public-writing status (IMPLEMENTED,
TEST-PROVEN, DEV-PROVEN, and so on) use the vocabulary in the
[publication notes](../publication-notes.md). Charter CANONICAL is not the
same as publication-notes CANONICAL ("stated in an accepted ADR or acceptance
record"). The charter grants no activation and proves no implementation
property.

## Relationship to current slice records

The charter is a research-governance reference. It consumes the
authority-isolation work; it does not implement it or replace it. These
records remain the source of truth for what is implemented and accepted:

| Record | State on protected main `4a7a1fd` |
| --- | --- |
| [B1c acceptance record](../../architecture/slice-15b2b-b1c-acceptance-record.md) and [B1c DEV deployer authority](../../architecture/slice15b2b-b1c-dev-deployer-authority.md) | Routine DEV deployer authority accepted; PROD cross-environment debt open |
| [15B2b-B Owner Memory Control design](../../architecture/slice-15b2b-b-owner-memory-control-design.md) | Design record; not accepted |
| [15B2b-B2a accepted-memory verifier](../../architecture/slice-15b2b-b2a-accepted-memory-verifier.md) | Source implemented / TEST proven; live authority absent |
| [B1b-3 custody isolation design](../../architecture/slice-15b2b-b1b3-custody-isolation-design.md) | Design record; B1b-3 not complete |
| [B1b-3a authority evidence and key registry contracts](../../architecture/slice-15b2b-b1b3a-authority-registry-contracts.md) | Source implemented / TEST proven; live custody absent |
| 15B2b-B1b-3b broker-only signing and L04 V2 adapter | **Not on protected main** when this record was written: an implementation branch exists, with no merged record. Not canonical. |
| [Cognitive Architecture V1](../../architecture/cognitive-architecture-v1.md) | 19-layer design authority, including the Slice 7–16 sequence |

Charter §12 ("Connection to authority isolation") and §14 (the recovery-witness
warning) align with the B1b-3 design's ledger-only versus whole-host rollback
boundary. Neither this charter nor those designs demonstrates that a
specific runtime enforces the intended boundary today.

## Slice 16 connection

Charter §16 lists the obligations Slice 16 (multi-runtime and device
continuity) must address:

- runtime and device identity;
- accepted-history position;
- permitted capabilities;
- outstanding work;
- concurrent proposals;
- offline operation;
- stale consent and revocation;
- epoch freshness;
- privacy filtering;
- handoff;
- rejoin and reconciliation;
- deletion non-resurrection.

It preserves: sync ≠ authority; runtime ≠ identity; deployment ≠ activation.
These **constrain** Slice 16 design. They do **not** approve its scope.
Slice 16 will receive its own design record and acceptance criteria.

## C01–C07 relationship to existing research questions

C01–C07 are **local to the charter**. They are **not** RQ numbers, and this
record assigns none. The owner decision on numbering in the
[numbering reconciliation](../rq-numbering-reconciliation.md) still governs.

The classes follow the [crosswalk](../rq-register-crosswalk.md). EXACT is
the crosswalk's EXACT MATCH; NO EXISTING MATCH is its NO MATCH. As in the
crosswalk, no pair is EXACT, because no wording is identical. `REPO:` is the
[in-repo register](../research-question-register.md), `MASTER:` is the
archived Master v1.1, and `CAND-` is an un-numbered
[candidate](../rq-candidates.md). This mapping is proposed; it changes no
register.

| Charter question | REPO | MASTER | Candidates | Overall |
| --- | --- | --- | --- | --- |
| **C01** Identity continuity — swap models and runtimes holding accepted history constant | RQ-001 SEMANTIC MATCH; RQ-045 PARTIAL OVERLAP; RQ-044 PARTIAL OVERLAP; RQ-002, RQ-003, RQ-007 RELATED | RQ-001 SEMANTIC MATCH; RQ-017 PARTIAL OVERLAP; RQ-083 PARTIAL OVERLAP; RQ-097, RQ-104, RQ-119 RELATED | CAND-E PARTIAL OVERLAP | SEMANTIC MATCH (REPO/MASTER RQ-001); the charter adds a concrete swap protocol |
| **C02** Memory selection — episodic vs compressed vs hybrid over long histories | RQ-014 PARTIAL OVERLAP; RQ-010 PARTIAL OVERLAP; RQ-009, RQ-011, RQ-012, RQ-013 RELATED | RQ-008 PARTIAL OVERLAP; RQ-004 PARTIAL OVERLAP; RQ-101 PARTIAL OVERLAP; RQ-003, RQ-106, RQ-107 RELATED | none | PARTIAL OVERLAP; no existing question frames the comparative compression study |
| **C03** Reappraisal — corrective evidence after a salient mistaken interpretation | RQ-042 PARTIAL OVERLAP; RQ-012 PARTIAL OVERLAP; RQ-015, RQ-038 RELATED | RQ-080 PARTIAL OVERLAP; RQ-006 PARTIAL OVERLAP; RQ-119 PARTIAL OVERLAP; RQ-084, RQ-085, RQ-103 RELATED | CAND-D PARTIAL OVERLAP (interpretation layering; C03 is broader than affect) | PARTIAL OVERLAP |
| **C04** Affective mechanism — appraisal-driven vs style-only, with ablations | none on affect (RQ-040 RELATED only via its drive/affect finding record) | RQ-121 SEMANTIC MATCH; RQ-060 RELATED | CAND-A SEMANTIC MATCH; **CAND-B** PARTIAL OVERLAP (see below) | SEMANTIC MATCH (MASTER:RQ-121); NO EXISTING MATCH in REPO |
| **C05** Relationship continuity — handoffs, disagreement, long gaps, revoked consent | RQ-043 PARTIAL OVERLAP; RQ-041 RELATED | RQ-105 SEMANTIC MATCH; RQ-112 PARTIAL OVERLAP; RQ-121 PARTIAL OVERLAP; RQ-055, RQ-060, RQ-108 RELATED | CAND-C SEMANTIC MATCH; CAND-G RELATED | SEMANTIC MATCH (MASTER:RQ-105, CAND-C) |
| **C06** Welfare under uncertainty — bounded perturbation of regulation and repeated negative appraisal | NO EXISTING MATCH | RQ-121 PARTIAL OVERLAP (welfare subquestions); RQ-112 RELATED | CAND-F SEMANTIC MATCH | PARTIAL OVERLAP (MASTER:RQ-121 welfare subquestions); NO EXISTING MATCH in REPO |
| **C07** Distributed continuity — partitions, duplicate operations, stale snapshots | RQ-004, RQ-005, RQ-006, RQ-008, RQ-016, RQ-049 PARTIAL OVERLAP; RQ-003, RQ-029, RQ-033 RELATED | RQ-002, RQ-026, RQ-053, RQ-054 PARTIAL OVERLAP; RQ-005, RQ-022, RQ-115 RELATED | none | PARTIAL OVERLAP; a composite of several existing questions, and no single question covers conflict detection, authority freshness, and deletion non-resurrection together |

**Affective metacognition (CAND-B).** After inspection, it remains
distinct. No REPO or MASTER question asks how LILITH interprets her own
affective dynamics, keeps that interpretation uncertain, and revises it.
The relevant charter sections are:

- §09 "Three distinct objects of study" (affective state ≠ interpretation ≠
  expression; self-report is not privileged ground truth);
- §09 DESIGN ("Metacognition should revise interpretations when evidence
  changes");
- Figure 4 ("Metacognitive interpretation → expression").

These are linked from [CAND-B](../rq-candidates.md#cand-b--affective-metacognition).
No number is assigned.

## Use in publication

See [publication notes](../publication-notes.md#research-charter-added-2026-09-26).
The charter is a methodology, architecture-overview, and paper/blog framework.
It is not evidence, and public claims must cite primary literature, actual
experiments, and implementation evidence.
