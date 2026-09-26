# Research Source Material

Status: **RECONCILIATION RECORD** (documentation/research provenance only).
Prepared on branch `docs/research-history-reconciliation` from protected main
`b1add92209560c10204e2a05583cb4647bf627e7` on 2026-09-26. This record does not
import, rewrite, or canonicalize any source; it records what exists, what is
missing, and where missing originals should be archived once supplied.

> **Updated 2026-09-26 — primary-source pass, public edition.** Nine
> historical originals were recovered. Five public-safe originals are archived
> byte-for-byte in [originals/](originals/); four (the three Infrastructure,
> CI/CD & Operations editions and the Project Roadmap `.docx`) remain in the
> owner's private archive and are recorded by metadata and SHA-256 in the
> [historical source manifest](source-manifest.md). Sections B–F below reflect
> that; section A (in-repo sources) is unchanged.

## Why this manifest exists

The research program must be reconstructable from evidence. Several documents
named in the reconciliation brief (the "Architecture & Research Master" family)
are cited as origins of the research-question numbering, but they are **not in
this repository**. Without a manifest, later readers could not tell whether a
research claim rests on an in-repo artifact, an out-of-repo document, or a
recollection.

Hashes below are SHA-256 of the file content as stored in Git at
`b1add92` (`git show origin/main:<path> | sha256sum`), not of a working-tree
checkout, so they are line-ending independent.

## A. Source documents present in the repository

These are the canonical in-repo sources used by this reconciliation.

| Path | Role | First commit | SHA-256 at `b1add92` |
| --- | --- | --- | --- |
| [research-question-register.md](../research-question-register.md) | In-repo RQ register, RQ-001–RQ-050 | `1eee09b` (2026-09-13) | `30ae3486201d953cdfe866da5215dc06fb9d1a1acf9bc91f4c10d30b465ec4fa` |
| [method.md](../method.md) | Research method, status vocabulary, evidence levels E0–E5 | `1eee09b` | `c5669783411ecc6dc45003f4e76fa73cb3249c12721da024565e88194a89e6d5` |
| [research README](../README.md) | Program themes | `1eee09b` | `7808e0d9da83bcdec42c915513fa06cc4c0b069e65f4f6b57d11ddb7abecb5b7` |
| [cognitive-architecture-v1.md](../../architecture/cognitive-architecture-v1.md) | 19-layer design authority; Slice 1–6 mapping; Slice 7–16 sequence | `61796fb` (2026-09-07) | `28afc8a4527b360ecb3bc0a2ef8b239667a659e7facd2c61954bb54798cb1c46` |
| [principles.md](../../architecture/principles.md) | P-01–P-12 | `1eee09b` | `c1b5901336e1ad057bf548c09aeed16e1ee7f47b6ac61aafd83ae0ba01bfac83` |
| [target.md](../../architecture/target.md) | Target architecture | `1eee09b` | `216a688fb98ba084767ecf878f37d16d6cf9a02cdec7210d76a395b4cf850cfc` |
| [as-is.md](../../architecture/as-is.md) | Current-state evidence page (evidence date 2026-09-13) | `1eee09b` | `d92712a69fb64eb7067535024a28ed25815e9d5e1c495165334d8a166e48be15` |
| [roadmap.md](../../roadmap/roadmap.md) | Evidence-gated phases 0–8, autonomy levels A0–A5 | `1eee09b` | `12df77d932e6e4fa1f55a42eb1cd2001834c0f13888a4f26d7daf8053810f46f` |
| [threat-model.md](../../security/threat-model.md) | T-01–T-24, security invariants | `1eee09b` | `8c1b7df9959da9b752760d578b8b0f1c70c1eee9519ae1dd2fb7c7987ec41a48` |
| [glossary.md](../../glossary.md) | Terminology | `1eee09b` | `a2ad26feaeae111a640ed90f1f023323769ba205f03ed8bc9457847480e71968` |
| [journal README](../../journal/README.md) | Engineering-journal workflow | `1eee09b` | `2474ceb379739589c40b12bb3bf2e8037b75092927735d93bc7474baa53174e8` |
| [ADR-0006](../../adr/0006-family-neutral-canonical-memory-apply.md) | Family-neutral canonical apply | `4ba8b39` (2026-09-22) | `20892718d782dd3aba0e14c44b7f700cb7a8f8cae2c0c54942258c70c752063e` |
| [15B2b-A acceptance record](../../architecture/slice-15b2b-a-acceptance-record.md) | SOURCE ACCEPTED / DEV PROVEN / PROD DARK | `2ba5b93` (2026-09-23) | `d517eee201f26fe47e09403a43594fd4a05a7b22eccdb9f27e376dda1629a2d3` |
| [B1c acceptance record](../../architecture/slice-15b2b-b1c-acceptance-record.md) | Routine DEV deployer authority accepted | `74c37a6` (2026-09-25) | `cd59952c49ccf3bd2faeadf19c12d29570908cae0541a44aabbf198789b17f34` |
| [15B2b-B design record](../../architecture/slice-15b2b-b-owner-memory-control-design.md) | Owner Memory Control design (not accepted) | `d1d3b38` (2026-09-26) | `f899a1961634bdf9b5e9f0df0bf7a10c4161cc7007f237dc000b9ea6d0719717` |
| [B2a record](../../architecture/slice-15b2b-b2a-accepted-memory-verifier.md) | Accepted-memory verifier, TEST only | `a827728` (2026-09-26) | `250eaec50f5a9eaa6decd75f24355b801668f7c123d6a246b85a330b40f1a45e` |

All other `docs/architecture/**` slice designs, deployment records, and
per-slice artifact directories (`slice-7/` … `slice-15b2a/`) are also in-repo
sources; they are indexed by slice in the slice history record rather than
repeated here.

**Engineering journal:** `docs/journal/` contains only its README and
`entry-template.md`. **No journal entries exist in the repository.** Journal
material referenced by `as-is.md` ("Reported by earlier engineering-journal
material") is therefore out-of-repo and unverified. *(Corrected 2026-09-26: the Engineering Journal through Slice 3 is now archived in `originals/`; it is probably that material, INFERRED.)*

**Changelog:** `CHANGELOG.md` records only the documentation foundation under
"Unreleased"; it does not track slices.

## B. Historical sources: public, private and missing

Full details, hashes, dates, classification and supersession are in the
[historical source manifest](source-manifest.md).

| Source | Public status | Historic fingerprint (Master v1.1) |
| --- | --- | --- |
| S1 `LILITH_Cognitive_Architecture_V1.pdf` | ARCHIVED (PUBLIC_SAFE) | MATCH |
| S2 `LILITH_Architecture_and_Research_Master.pdf` (v1.0) | ARCHIVED (PUBLIC_SAFE) | MATCH |
| `LILITH_Architecture_and_Research_Master_v1.1.pdf` | ARCHIVED (PUBLIC_SAFE; revision) | not available |
| S4 `LILITH_OS_Architecture_v0.1.pdf` | ARCHIVED (PUBLIC_SAFE) | MATCH |
| `LILITH_Engineering_Journal_Through_Slice_3.docx` | ARCHIVED (PUBLIC_SAFE) | not available |
| S3 `LILITH_Infrastructure_CICD_and_Operations.pdf` (v1.0) | PRIVATE HISTORICAL SOURCE — PRIVATE_ARCHIVE_ONLY | MATCH |
| `LILITH_Infrastructure_CICD_and_Operations_v1.1.pdf` | PRIVATE HISTORICAL SOURCE — PRIVATE_ARCHIVE_ONLY | not available |
| `LILITH_Infrastructure_CICD_and_Operations_v1.1.1.pdf` | PRIVATE HISTORICAL SOURCE — PRIVATE_ARCHIVE_ONLY | not available |
| S5 `LILITH_OS_Project_Roadmap.docx` | PRIVATE HISTORICAL SOURCE — PUBLIC_SAFE_WITH_REDACTION (no derivative) | MATCH |

Still **missing** (no original found; content quoted inside another document is
secondary evidence only):

- *LILITH Research Question & Architecture Problem Register* — the original
  MASTER:RQ-001–100 source;
- *LILITH — Frontier Research Extensions* — the RQ-101–120 source;
- *Making LILITH Feel Human Without Making Her Suffer* — the affective source;
- the *Architecture Review Plan* conversation record, and the "S6"
  live-environment observations used by Infrastructure v1.1.1;
- any engineering journal entries after Slice 3.

A standalone RQ-121 original probably never existed: Master v1.0 states RQ-121
was synthesized in the Master task itself.

## C. Archive action taken

The five PUBLIC_SAFE originals were copied unmodified into `originals/` in a
dedicated commit. SHA-256 was computed on each source before copying and
re-checked on the stored Git blob; all matched. No conversion, transcription,
rename, edit or redacted derivative. The four private originals were never
committed to this public branch.

## D. Archival policy

Location: `docs/research/source-material/originals/`, exact filenames.

1. Originals are immutable. A later edition is added as a new file; it never
   replaces an earlier one.
2. Every recovered source — public or private — has a manifest row with
   SHA-256, size, date evidence, classification and supersession.
3. **Public-safety gate.** Before any historical binary enters this public
   repository it is scanned (text, metadata, annotations, embedded files,
   media, fonts) and classified PUBLIC_SAFE, PUBLIC_SAFE_WITH_REDACTION, or
   PRIVATE_ARCHIVE_ONLY. Only PUBLIC_SAFE originals are committed. A
   redacted derivative, if ever needed, is named
   `<name>.public-redacted.<ext>`, records source hash, derivative hash and
   redaction categories, and states that it is not the historical original.
   Manifest-only is preferred.
4. Private originals live in an owner-controlled private archive (see the
   manifest, section F); this repository keeps only their metadata and hashes.
5. Transcriptions, if ever added, sit beside a public original as
   `<name>.transcription.md`, labelled secondary.
6. `.gitattributes` marks `*.pdf` binary; Git also detects `.docx` as binary
   (stored blob hashes equal the source hashes).

## E. Owner actions required

- Place the four private originals in a private archive (manifest section F).
- Supply the missing originals listed in section B, if they still exist.
- Decide how the REPO and MASTER registers relate (see the
  [crosswalk](../rq-register-crosswalk.md) and the
  [numbering reconciliation](../rq-numbering-reconciliation.md)).

## F. First-pass record and correction (negative finding N-41)

- **What happened.** The first reconciliation pass reported every
  Master-family source as MISSING.
- **Root cause.** Its filename searches did include the owner's profile,
  OneDrive and Downloads, but both listing commands truncated their output
  (`head -80`, `head -60`); the matching files fell after the truncation point
  and were never reported. The content search also skipped binary files.
- **Impact.** The first-pass records classified MASTER:RQ-051–121 as
  "REPORTED only", declared historic hashes unverifiable, and left Slices 1–3
  evidence REPORTED.
- **Correction.** A scoped re-search found all nine originals; every affected
  record carries a dated correction note.
- **Lesson.** Truncated discovery output must never be read as exhaustive
  evidence of absence.
