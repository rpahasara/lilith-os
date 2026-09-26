# Historical Source Manifest

Status: **RECONCILIATION RECORD — primary-source pass, public edition
(2026-09-26).** This manifest proves which historical sources existed, with
their SHA-256, without necessarily publishing them. Nine historical originals
were recovered. After a public-safety review, five are archived byte-for-byte
in [originals/](originals/); four are kept in the owner's private archive and
are recorded here by metadata and hash only. Nothing was converted, renamed,
or edited, and no redacted derivative was created.

The archive is **not complete**: several originals remain missing (section D).

## A. Public-safety classification

Every recovered file was scanned before publication: page text, PDF
metadata/XMP, annotations, links and embedded files; every XML part, media
item and embedded font inside the `.docx` packages. Scan categories: secrets,
tokens, credentials, private keys, passwords, internal IP addresses,
project/account numbers, service-account addresses, workload-identity paths,
VPC/firewall/resource names, local usernames, absolute machine paths, email
addresses, personal information, and third-party confidential information.

| Classification | Meaning |
| --- | --- |
| PUBLIC_SAFE | Archived in [originals/](originals/) unmodified. |
| PUBLIC_SAFE_WITH_REDACTION | Content is publishable only after redaction. The original stays private; a derivative named `<name>.public-redacted.<ext>` may be created later if genuinely useful. **None was created in this pass** (manifest-only is preferred). |
| PRIVATE_ARCHIVE_ONLY | Never published. Metadata and SHA-256 only. |

| Source | Classification | Scan result |
| --- | --- | --- |
| S1 Cognitive Architecture V1 (PDF) | PUBLIC_SAFE | No sensitive hits. Embedded fonts are document subsets (IBM Plex, DejaVu, Liberation) |
| S2 Architecture & Research Master v1.0 | PUBLIC_SAFE | No sensitive hits. Font subsets (Segoe UI) |
| Master v1.1 | PUBLIC_SAFE | No sensitive hits. Font subsets (Segoe UI, Consolas). Owner note: two research-question examples inherited from the original register mention personal-plan scenarios (relocation, certification cost); judged illustrative, flagged for owner awareness |
| S4 LILITH OS Architecture v0.1 | PUBLIC_SAFE | No sensitive hits; UI figures are illustrative mock values |
| J1 Engineering Journal through Slice 3 | PUBLIC_SAFE | Only `127.0.0.1` and the VM name `lilith-01`, which is already public in in-repo deployment records; no media; generator-default document properties |
| S5 LILITH OS Project Roadmap (`.docx`) | PUBLIC_SAFE_WITH_REDACTION | Contains an absolute local machine path with a local username, and embeds eight complete commercially licensed font files (Helvetica Neue family) that should not be redistributed. One embedded image is a generic diagram template. Original kept private; no derivative created |
| S3 Infrastructure, CI/CD & Operations v1.0 | PRIVATE_ARCHIVE_ONLY | OPERATIONAL_TOPOLOGY / INFRASTRUCTURE_INVENTORY: internal IP addresses, cloud identifiers, service-account addresses |
| Infrastructure, CI/CD & Operations v1.1 | PRIVATE_ARCHIVE_ONLY | OPERATIONAL_TOPOLOGY / INFRASTRUCTURE_INVENTORY: as v1.0 plus project number and workload-identity provider path |
| Infrastructure, CI/CD & Operations v1.1.1 | PRIVATE_ARCHIVE_ONLY | OPERATIONAL_TOPOLOGY / INFRASTRUCTURE_INVENTORY: as v1.1 plus VPC/subnet and firewall names and ranges |

No secret, key, token, password, or credential value was found in any file.

## B. Archived public sources

First committed on branch `docs/research-history-reconciliation-public` in
"docs(research): archive public-safe historical LILITH sources". SHA-256 was
computed on the source files before copying and re-verified on the stored Git
blobs; all matched. Source IDs S1–S5 are those used by Master v1.1, whose
"Sources and change record" also records the historic fingerprints below.

| ID | Exact filename | Title / version | Known date | Size (bytes) | SHA-256 | Historic fingerprint | Original / revision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | `LILITH_Cognitive_Architecture_V1.pdf` | "LILITH Cognitive Architecture V1 (Copy)", design report, 34 pages | Content 2026-09-07; PDF produced 2026-09-14 05:49 UTC (browser print) | 1,129,892 | `57703b6c0e2e57653ae55153d0bfba9b6db04286d3f9d2f3b85334c0998e887f` | **YES** | ORIGINAL HISTORICAL ARTIFACT (fingerprinted print of the 2026-09-07 artifact) |
| S2 | `LILITH_Architecture_and_Research_Master.pdf` | LAR-MASTER revision 1.0, 28 pages | 2026-09-14 (PDF created 10:59 +05:00) | 143,773 | `f935a466e39b799f70135d8d8d68b871baecce993f27958e2a9804e6470cbff9` | **YES** | ORIGINAL HISTORICAL ARTIFACT |
| M1.1 | `LILITH_Architecture_and_Research_Master_v1.1.pdf` | LAR-MASTER revision 1.1, 44 pages | 2026-09-14 (PDF created 11:41 +05:00) | 206,309 | `0d14d3e60e133ffa80cf7fe7dd15f629867f4e4c880622c11135e9672cc2815a` | NOT AVAILABLE | REVISION of S2 |
| S4 | `LILITH_OS_Architecture_v0.1.pdf` | "LILITH OS — Personal Intelligence Operating System — Architecture v0.1", 21 pages | "Prepared 24 AUG 2026"; PDF created 2026-08-25 00:00 +05:00 | 76,166 | `c12be53995de36f927967ea0aa6f869f67c42aa5b46a6679dcdf57959d9a0823` | **YES** | ORIGINAL HISTORICAL ARTIFACT |
| J1 | `LILITH_Engineering_Journal_Through_Slice_3.docx` | "LILITH Engineering Journal — project record through Cognitive Core V2 Vertical Slice 3", 12 entries | "Compiled 7 September 2026"; file modified 2026-09-07 09:08 UTC | 48,479 | `a9cb664c0feab7f3bed51aa40435dac34df49a3ab58152b63ef63d8c5911df2f` | NOT AVAILABLE (named, without hash, in MASTER:RQ-094) | ORIGINAL HISTORICAL ARTIFACT |

## C. Private historical sources (metadata only)

These originals exist in the owner's private archive. The public repository
records that each existed with the SHA-256 shown; their contents are not
published. Facts drawn from them appear in public documents only where the
same facts are already intentionally public in this repository (for example,
the deployer's role set is stated in the B1c acceptance record).

| ID | Exact filename | Title / version | Known date | Size (bytes) | SHA-256 | Historic fingerprint | Original / revision | Classification and reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S3 | `LILITH_Infrastructure_CICD_and_Operations.pdf` | LILITH-OPS revision 1.0, 12 pages | 2026-09-14 (PDF created 10:59 +05:00) | 78,230 | `ff7ed4dadb5ecd06c47e0a9ee87b6690fb810e34cd71dfae44e9d142c92caf90` | **YES** | ORIGINAL HISTORICAL ARTIFACT | PRIVATE_ARCHIVE_ONLY — OPERATIONAL_TOPOLOGY / INFRASTRUCTURE_INVENTORY |
| INF-1.1 | `LILITH_Infrastructure_CICD_and_Operations_v1.1.pdf` | LILITH-OPS revision 1.1, 17 pages | 2026-09-14 (PDF created 11:41 +05:00) | 120,543 | `d38d6b5ad53485f4631a76f42e3bb3cc50c3201e1d43a2be2b7808755df4ce49` | NOT AVAILABLE | REVISION of S3 | PRIVATE_ARCHIVE_ONLY — OPERATIONAL_TOPOLOGY / INFRASTRUCTURE_INVENTORY |
| INF-1.1.1 | `LILITH_Infrastructure_CICD_and_Operations_v1.1.1.pdf` | LILITH-OPS revision 1.1.1, 17 pages | 2026-09-14 (PDF created 11:48 +05:00) | 122,212 | `7777e68cfc7d6b123b7f1767fdd59daded6e56d83454d928ddea948c3aefe063` | NOT AVAILABLE | REVISION of INF-1.1 | PRIVATE_ARCHIVE_ONLY — OPERATIONAL_TOPOLOGY / INFRASTRUCTURE_INVENTORY |
| S5 | `LILITH_OS_Project_Roadmap.docx` | "LILITH OS Project Roadmap", active roadmap v1.0, sections 1–16 | Content dated 6 September 2026; file modified 2026-09-05 20:11 UTC | 511,833 | `e7e0d6494725ad7958e39641cfb11df56952df323d172639695109f724054729` | **YES** | ORIGINAL HISTORICAL ARTIFACT | PUBLIC_SAFE_WITH_REDACTION — original private (local path/username; embedded commercial fonts); no derivative |

### Citation convention for private sources

Public documents cite these sources as, for example:

> PRIVATE HISTORICAL SOURCE — LILITH Infrastructure, CI/CD & Operations v1.0 —
> SHA-256: `ff7ed4dadb5ecd06c47e0a9ee87b6690fb810e34cd71dfae44e9d142c92caf90`

or by their short IDs (**S3**, **INF-1.1**, **INF-1.1.1**, **S5**), which always
mean the private originals above. A claim resting only on a private source is
weaker public evidence than an in-repo record, test or run: readers can verify
that the source existed (by hash, if given access), not what it says.

Public-safe facts used from the private sources: the dates and titles above;
that the 2026-09-14 operations reference recorded protected-main governance,
the PR → DEV → merge → PROD flow, a verified DEV rollback test, a single GitHub
deployer identity holding the role set later documented in the B1c acceptance
record, and dedicated DEV/PROD deploy identities and a secrets broker as future
targets; and the Roadmap's phases, milestones, decisions and execution
contract. Not used publicly: any address, number, path, resource name,
topology or inventory detail.

## D. Historical roles and supersession

| Source | Historical role | Supersedes | Superseded by |
| --- | --- | --- | --- |
| S4 OS Architecture v0.1 | Original product/app/event/privacy blueprint | — | Reconciled (not replaced) by Master v1.1 §P |
| S5 Project Roadmap *(private)* | Experience roadmap phases 0–10, milestones M1–M5, frozen systems, DEV-01, decisions D01–D08 | — | Phase ordering declared HISTORICAL by Master v1.1 §P.2 |
| J1 Engineering Journal | Entries 1–12 through Cognitive Core V2 Slice 3, with failures and lessons | — | No later journal found |
| S1 Cognitive Architecture V1 | 19-layer design; Slice 1–6 backend mapping; Slice 7 recommendation | — | Some statements marked SUPERSEDED by Master v1.1 |
| S2 Master v1.0 | First canonical architecture and complete MASTER:RQ-001–121 register | — | Master v1.1 (as synthesis; does not retroactively change historical claims) |
| M1.1 Master v1.1 | Canonical reference reconciling S1–S5, all 19 layers, product model, fuller RQ text, source fingerprints | S2 (as synthesis) | Not superseded by any archived source |
| S3 Infrastructure v1.0 *(private)* | AS-IS CI/CD and operations reference | — | INF-1.1 |
| INF-1.1 *(private)* | Adds recovery inventory and rebuild sequence | S3 | INF-1.1.1 |
| INF-1.1.1 *(private)* | Adds owner-supplied live-environment facts ("S6") | INF-1.1 | — |

Notes:

- **S1 is a print copy** (PDF title ends "(Copy)", browser-produced on
  2026-09-14) and is exactly the file Master v1.1 fingerprints as S1.
- **The in-repo Markdown is a derivative, not S1.**
  [cognitive-architecture-v1.md](../../architecture/cognitive-architecture-v1.md)
  (commit `61796fb`, 2026-09-07) adds §7a, which S1 lacks. Classification:
  DERIVED / AMENDED COPY.
- **Word document metadata is not evidence.** J1 carries generator defaults
  dated 2013; S5 has no document-properties part. Dates come from content and
  file timestamps.
- Two further files were found but not archived: a PDF export of S5 (derived
  copy; SHA-256 `bf74a39b93f5b93f59ba6a6e4796ab4a057dd85541f87d4ba700e8ed78ff9b69`;
  same private status as S5) and a PNG byte-identical to
  `docs/architecture/diagrams/lilith-high-level-architecture.png`.

## E. Still missing (no original found)

Content quoted or summarized inside another document is **secondary
evidence**, not the original.

| Missing source | Evidence it existed | Search result |
| --- | --- | --- |
| *LILITH Research Question & Architecture Problem Register* (original MASTER:RQ-001–100) | Master v1.0 "Primary materials"; Master v1.1 "original attached register" | Not found |
| *LILITH — Frontier Research Extensions* (RQ-101–120 ideas; "DeepSeek extension" texts) | Master v1.0 "Primary materials"; heading "DeepSeek-inspired extensions" | Not found |
| Standalone RQ-121 source | Master v1.0: RQ-121 "synthesized from the conversation and is not part of the original attached register" | Probably never existed separately |
| *Making LILITH Feel Human Without Making Her Suffer* | Master v1.0 "Primary materials" | Not found |
| *Architecture Review Plan* task / operational record | Cited by Master v1.0 and S3 as conversation evidence | Not found (conversation) |
| "S6" live-environment observations | INF-1.1.1 | Not a document |
| Engineering journal entries after Slice 3 | — | None found; `docs/journal/` holds only a template |

Search performed (read-only, filenames only): the owner's OneDrive
"Documents/My Lilith OS" folder, then the owner's OneDrive, Documents,
Downloads and Desktop folders recursively for the titles above, excluding
dependency folders, Git internals and tool worktrees. Local credential files
were deliberately not opened, read, or archived.

## F. Private archive recommendation

Keep the four private originals (and the S5 PDF export) in one
owner-controlled location, with the hashes above as the public proof:

1. **Recommended:** a private GitHub repository (for example
   `lilith-private-archive`) holding `originals/` plus a copy of section C, so
   history, access control and integrity checks match this repository.
2. **Alternatively:** keep the existing OneDrive folder as the master copy and
   add an encrypted offline backup (for example an encrypted archive on
   separate storage).
3. In either case, re-verify SHA-256 after every copy, never commit the files
   to a public repository, and record any future relocation here.

Nothing was uploaded anywhere by this reconciliation.
