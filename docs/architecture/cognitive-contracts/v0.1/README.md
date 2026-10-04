# LILITH Cognitive Architecture Contract Set v0.1

Status: **PROPOSED / NOT ACCEPTED.** Every document in this set is a proposed
semantic and governance contract. None is accepted, implemented, or
authoritative.

Package completeness / acceptance: **NOT_ESTABLISHED.** This directory holds
metadata and an index only. It is not the architecture package itself.

This directory records the **Cognitive Architecture Contract Set v0.1**: 16
design PDFs written after a full audit of LILITH's architecture and vision.
They formalize semantic and governance gaps that had been spread across many
earlier documents.

**The PDFs themselves are not in this repository.** They are kept unmodified
in the owner's private archive, pending a separate public-safe derivative
process. This directory holds only this README and a byte-identity list of the
16 private originals ([ORIGINALS.sha256](ORIGINALS.sha256)). See
[Why the PDFs are not committed](#why-the-pdfs-are-not-committed).

## What this set is not

The presence of this directory, or its merge into Git, does **not** imply:

- contract acceptance;
- implementation;
- mechanism conformance;
- behavioural evidence;
- currentness or freshness;
- operational authorization;
- activation.

All documents in this set are PROPOSED / NOT ACCEPTED and do not constitute
authorization for any live operation. That includes First Memory, M-B1,
PR-1B, authority transitions, model or runtime swaps, memory or personality
mutation, autonomous action, Hsin activation, and deployment changes. These
documents are **not an authorization source** for
any ceremony, host, cloud, broker, authority, witness, or production change.

## Relationship to the existing repository

| Source | Role |
| --- | --- |
| Existing repository (ADRs, architecture and slice records, acceptance and evidence records, research register, code, tests) | Implementation, research, governance and evidence history; actual implementation and acceptance status must be established from the controlling records and evidence. |
| This contract set | **Design and semantic contract sources** for later reconciliation against that history |

The set does not replace the repository's architecture. It must be reconciled
with it.

### Precedence

These PDFs **do not automatically supersede** existing accepted governance,
ADRs, repository contracts, canonical schemas, acceptance records, evidence
records, or authority and currentness decisions.

The repository-wide [document authority order](../../../README.md#document-authority)
still applies, and in it a later date alone does not make a document
authoritative. Any conflict between a PDF and an existing record must be
**explicitly reconciled** through an ADR or a corrective pull request. A
conflict must never be settled silently by choosing the newer PDF.

Within the set, the Composition Contract's **owner-domain principle** guides
later reconciliation:

- each canonical domain has controlling semantics;
- other domains may read or produce evidence and proposals only where
  permitted;
- no domain may silently accept or write another domain's canonical state;
- the destination domain's governance owns acceptance and application.

## Start here: the composition document

Document 16, **LILITH Integrated Cognitive Architecture & Composition
Contract v0.1**, is the composition and index document for the set. It
consolidates the other fifteen, assigns domain ownership, and maps their
gates.

Document 16 describes the design-PDF phase as concluded. That is the
document's own proposed position, not an accepted state, and it makes no
claim that this repository holds a complete package. It proposes these next
phases, in order:

1. repository packaging (this directory currently records metadata and an
   index only; the PDFs remain private pending public-safe derivatives);
2. an Architecture & Acceptance Ledger;
3. repository/design reconciliation;
4. gap review;
5. implementation slice planning;
6. evidence and conformance work.

## Inventory

Status for all 16 documents: **PROPOSED / NOT ACCEPTED**. Version: **0.1**.
Bytes, pages, and SHA-256 were measured on the private originals during
packaging on 2026-10-04.

| # | Title | Exact filename | Pages | Bytes | SHA-256 | Role / purpose | Source note |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| 01 | LILITH Identity Invariant Specification v0.1 | `LILITH-Identity-Invariant-Specification-v0.1.pdf` | 16 | 121,397 | `3e07a2c05157b0129a26532603b20a68f806df520d291fc76d974210767d00f7` | Identity continuity through accepted history across replaceable models, runtimes, and devices | Direct design artifact |
| 02 | LILITH First Memory Semantic & Acceptance Specification v0.1 | `LILITH-First-Memory-Semantic-and-Acceptance-Specification-v0.1.pdf` | 20 | 130,455 | `d9e1d38f8c2c5a16ad4057468e679bac73901c7c83c1722a7e3fd62ffa43b47a` | Semantics and acceptance criteria for the first autobiographical landmark | Direct design artifact |
| 03 | LILITH Continuity Benchmark & Evaluation Protocol v0.1 | `LILITH-Continuity-Benchmark-and-Evaluation-Protocol-v0.1.pdf` | 26 | 144,376 | `9996bcf0a7f362218e9ca943a38732e97a5ca70191d09918fd068d18e865ab95` | Evaluation protocol for identity and continuity claims | Direct design artifact |
| 04 | LILITH Model / Runtime Adapter & Handoff Specification v0.1 | `LILITH-Model-Runtime-Adapter-and-Handoff-Specification-v0.1.pdf` | 29 | 150,173 | `0e4e6bae3b0177cc5e35f9c29a4b4ba66b8988aa330638d9fe03fc93848380a1` | Governed continuity across replaceable cognitive substrates | Direct design artifact |
| 05 | LILITH Memory Lifecycle & Reappraisal Specification v0.1 | `LILITH-Memory-Lifecycle-and-Reappraisal-Specification-v0.1.pdf` | 31 | 175,246 | `44c0952df8409e639f2dab689d1708641dbba27de9850b1b47fc5a3120b2db27` | Correction, reinterpretation, selective recall, and lawful erasure of memory | Direct design artifact |
| 06 | LILITH Personality Evolution Specification v0.1 | `LILITH-Personality-Evolution-Specification-v0.1.pdf` | 35 | 173,616 | `ffab7feb8cb29d6bb8c665ffe6eabfa26d7f6914d7292e2611db8776515083ae` | Personality development through accepted continuity, without a frozen personality | Direct design artifact |
| 07 | LILITH Relationship Continuity Specification v0.1 | `LILITH-Relationship-Continuity-Specification-v0.1.pdf` | 28 | 63,528 | `0c21de4a50073cfbea1265807bc4db7348d5a10a3d752ec8696e5e3070d61cce` | Relationship state, consent, and boundaries across time and handoffs | **Regenerated edition; original unavailable; not certified byte-identical to the original** |
| 08 | LILITH Affect / Appraisal Research Protocol v0.1 | `LILITH-Affect-Appraisal-Research-Protocol-v0.1.pdf` | 30 | 67,658 | `e1a670820694da18b77ed5e8c6c725eb9a20926aaa8e9bfbb1248e5dc436e632` | Research protocol for appraisal-driven affect; no persistent affect authorized | **Regenerated edition; original unavailable; not certified byte-identical to the original** |
| 09 | LILITH Cognitive Recovery, Migration & Multi-Device Continuity Specification v0.1 | `LILITH-Cognitive-Recovery-Migration-and-Multi-Device-Continuity-Specification-v0.1.pdf` | 48 | 131,683 | `bfdf6aff8434dae45e3a4bd7b011ed9bf10eaa25832ffaa6da6167d2044e1933` | Preserving accepted cognition across replacement, restore, and reconnect | Direct design artifact |
| 10 | LILITH Hsin Semantic Integration & Session Presence Specification v0.1 | `LILITH-Hsin-Semantic-Integration-and-Session-Presence-Specification-v0.1.pdf` | 45 | 195,536 | `edb0e2470ec8c77d85641933790f0bc61af0d8d6490140ba5888491a2bf76155` | Presence as a governed projection across voice, avatar, display, and devices | Direct design artifact |
| 11 | LILITH Goal, Commitment & Intention Continuity Specification v0.1 | `LILITH-Goal-Commitment-and-Intention-Continuity-Specification-v0.1.pdf` | 49 | 191,691 | `ce8389147bb3581d4599297c6898c65a3195b4e1543406120ee363f1aabd022b` | Goals, commitments, and intentions as governed accepted state | Direct design artifact |
| 12 | LILITH Initiative, Interruption & Autonomous Action Specification v0.1 | `LILITH-Initiative-Interruption-and-Autonomous-Action-Specification-v0.1.pdf` | 50 | 183,437 | `8aaf1ea910898305d9ec93288164a59f10494c1685be96c346b5b96df173a79b` | Separating a reason to act from permission to act or interrupt | Direct design artifact |
| 13 | LILITH Learning, Skill Acquisition & Competence Development Specification v0.1 | `LILITH-Learning-Skill-Acquisition-and-Competence-Development-Specification-v0.1.pdf` | 50 | 163,673 | `99b023fe69d4d7bf2e6acc587b53c07f49da51c6b5fbbdf209b0178f830a60da` | Evidence-based learning and competence, where evidence does not create authority | Direct design artifact |
| 14 | LILITH Self-Model, Metacognition & Capability Awareness Specification v0.1 | `LILITH-Self-Model-Metacognition-and-Capability-Awareness-Specification-v0.1.pdf` | 52 | 191,439 | `51984caab58cf3208e1004fd45401ea7462c01df7a7b5a83b6d3df496b8b84db` | Calibrated self-beliefs; capability awareness is not a capability grant | Direct design artifact |
| 15 | LILITH Epistemic Integrity, Belief State & Uncertainty Governance Specification v0.1 | `LILITH-Epistemic-Integrity-Belief-State-and-Uncertainty-Governance-Specification-v0.1.pdf` | 55 | 195,709 | `ac653b8ff30847c73e0eda3ea47f5f8e6993314c82898651a2096b8fa4a47d6e` | What is believed, why, and what remains uncertain; acceptance records a representation, not reality | Direct design artifact |
| 16 | LILITH Integrated Cognitive Architecture & Composition Contract v0.1 | `LILITH-Integrated-Cognitive-Architecture-and-Composition-Contract-v0.1.pdf` | 69 | 224,509 | `69dfd5fa998111fff4e2ddf96e35afb140b9de81bb07007c5674986c1ec6ce3f` | Composition, domain-ownership, and gate map for the set | **Final composition and consolidation document for this design-PDF phase** |

The role and purpose column is a packaging summary of each document's own
first-page statement. It is not a normative restatement.

## Hash scope and verification

- **What a hash proves.** SHA-256 identifies bytes only. A matching hash does
  not establish truth, acceptance, currentness, or canonical status.
- **What was hashed.** The hashes are of the private original PDF files, read
  as raw bytes. No PDF was modified, renamed, re-encoded, or redacted.
- **How to verify.** [ORIGINALS.sha256](ORIGINALS.sha256) uses the standard
  `sha256sum` format. It identifies the 16 unchanged private originals and is
  **not expected to verify against anything in this directory**. Run the
  check from the private archive directory that holds them:

  ```bash
  sha256sum -c /path/to/docs/architecture/cognitive-contracts/v0.1/ORIGINALS.sha256
  ```
- **Cross-check against document 16.** The Composition Contract's own
  component source register lists exact filenames and SHA-256 values for its
  sources. During packaging, every register entry that could be extracted
  automatically matched the local bytes, and none disagreed.
- **Collection.** All 16 originals were collected on 2026-10-04: 15 in the
  first pass, and the Learning specification (13) supplied by the owner later
  that day. Its bytes match the hash recorded for it in document 16.

## Why the PDFs are not committed

All 16 PDFs cite, in their source sections, the identifier of a private
external chat conversation that served as design context. Under the
repository's earlier sanitization practice (see the
[research charters README](../../../research/charters/README.md#sanitization-record)),
conversation and thread identifiers are not published in this repository.

The owner decided the following for this package:

- The original PDFs stay **unchanged in the owner's private archive**, with the
  SHA-256 values above.
- **No redacted copy was created.** Redaction would change the bytes and break
  the cross-hashes inside the documents. In particular, document 16's source
  register pins the original bytes of the other fifteen.
- Publishing these PDFs, or any derivative of them, in this repository needs a
  **separate public-safe derivative process** with its own review and
  sanitization record.

This follows the manifest-only pattern in
[source-material/source-manifest.md](../../../research/source-material/source-manifest.md):
the repository proves which sources exist without publishing them.

The packaging scan found no secrets, credentials, keys, IP addresses, cloud
identifiers, local paths, email addresses, embedded files, annotations, or XMP
metadata. Pattern hits such as "sk-specific" and "private key" were ordinary
prose. The only finding was the conversation identifier.

## Audit debt carried forward (not resolved by this set)

The architecture audit that led to this set found the gaps below. **This set
does not fix them**, and its presence must not be read as resolving them.

| ID | Finding | Status |
| --- | --- | --- |
| G1 | Capability-policy overrides may weaken defaults, despite the stated "tighten only" intent. | OPEN |
| G2 | The legacy draft-write path does not itself prove server-side approval authorization against alternate callers. | OPEN |
| — | Epistemic and presentation concern: unknown values may become fact-looking UI or output records. | OPEN |

## Future ledger review questions

These came from an external review of the PDFs made without repository
access. They are **questions for the later Architecture & Acceptance Ledger
and reconciliation phase only**. They are not specifications, they are not in
scope for implementation, and no new contract documents should be written for
them.

| ID | Question |
| --- | --- |
| HX-01 Natural Expression Projection | Does the existing repository translate governed state into natural human expression, without letting governance jargon, excessive qualification, or robotic disclaimers leak into ordinary conversation? |
| HX-02 One-Voice Model Routing | Does the current Router / SOUL / Adapter / Hsin architecture preserve one recognizable LILITH voice and personality across several replaceable reasoning models, and across text, voice, avatar, and robot surfaces? |
| HX-03 Conversational Fast Path | Can low-risk, ephemeral conversation stay responsive while durable writes and external effects use heavier governance and verification paths? |

## Later reconciliation discipline

The ledger and reconciliation work will keep these evidence categories
separate, and will not flatten them into a single "implemented" status:

- DESIGN
- CODE
- LOCAL TEST
- REPO RECORD
- INFERENCE
- NOT FOUND

For each requirement, it will ask whether the requirement is:

- already implemented;
- partially implemented;
- only conceptual;
- contradicted by accepted governance;
- already covered by a stronger existing mechanism;
- missing;
- in need of evidence rather than code;
- intentionally deferred.

## Architecture-wide distinctions the set preserves

These distinctions are summarized here for navigation. The controlling text is
in the PDFs, mainly document 16.

- proposal ≠ authority
- execution ≠ verification
- memory ≠ truth
- belief ≠ truth
- storage ≠ acceptance
- deployment ≠ activation
- sync ≠ authority
- historical validity ≠ currentness
- import ≠ activation
- emotion ≠ authority
- skill ≠ authority
- goal ≠ permission
- initiative ≠ action authority
- presence ≠ identity
- archive ≠ active memory
- working context ≠ identity
- source claim ≠ truth
- observation ≠ fact
- accepted belief ≠ true proposition
- capability awareness ≠ capability grant
- self-description ≠ self-knowledge

None of these is LILITH: the model, Hermes or another runtime, a device, Hsin
embodiment, a database, or a voice or avatar. Model, runtime, device, and
expression are each distinct from identity, and identity and governed
continuity must survive the replacement of any of them.

## Operational effect

None. Packaging this set changed no ceremony, authority, witness, broker,
host, cloud, phone, deployment, policy, schema, or runtime state. It is not
evidence of the current state of any of them.
