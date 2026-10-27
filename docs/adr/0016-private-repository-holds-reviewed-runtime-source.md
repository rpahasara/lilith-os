# ADR-0016: The private repository holds reviewed runtime source; secrets, private state and upstream code stay out

- **Status:** Accepted
- **Date:** 2026-10-27
- **Owners:** Project owner
- **Related:** ADR-0001, ADR-0002, ADR-0005, ADR-0008, ADR-0010;
  [source consolidation record](../engineering/source-consolidation-2026-10.md);
  [VM-only source gaps](../engineering/vm-only-source-gaps.md)

> **Accepted by the owner on 2026-10-27** with the instruction that GitHub become "the complete, maintained source
> of truth for all relevant, recoverable LILITH OS source code", after `rpahasara/lilith-os` was made private. The
> decision is about source control only. It authorizes no deployment, runtime change or data movement.

## Context

- **OBSERVED.** PROD (`lilith-01`) and DEV (`lilith-dev-01`) run Hermes from upstream NousResearch/hermes-agent
  `f293e72` plus LILITH patches, with the Router V2 package, two plugins, a provider gate, a Privacy FORGET executor
  and installer scripts. Until 2026-10-27 none of that source was in this repository: ADR-0010 records that "the
  repository holds no Hermes source". It lived on the hosts, in local staging folders and in WSL build directories.
- **OBSERVED.** The local runtime-source preservation of 2026-10-27 found 1,105 unique files on the owner's PC that
  were not in Git, including the only byte-exact copy of the deployed DEV release. Some of them embed a localhost
  provider-gate client token; others are private persona and research material.
- **OBSERVED.** The full PROD Working Memory module (`world_context.py`, 91,351 bytes) and the PROD lane
  configuration exist only on the PROD host and in its disk snapshot.
- **RISK.** Source that exists only on a workstation or a VM can be lost, and a VM that depends on unexplained local
  files cannot be rebuilt or reviewed.
- **CONSTRAINT.** Making a repository private does not make it a secret store. Collaborators, automations and
  integrations can read it, and Git history is permanent. Earlier public history may already have been copied.

## Decision

1. **Reviewed LILITH-authored runtime source belongs in this repository.** That includes Hermes integration patches,
   Router V2 and its cognitive lanes, plugins, the provider gate, Privacy executors, installers, systemd units,
   non-secret configuration and templates, tests, build tooling, and the historical lineage needed to reconstruct
   deployed releases. Hermes-specific code lives under `integrations/hermes/`, which keeps Hermes replaceable
   (ADR-0001): nothing outside that directory may depend on it.
2. **Upstream third-party code is pinned, not vendored.** Hermes is recorded as an exact upstream commit plus
   LILITH's patch set and the SHA-256 of every patched file, with the upstream licence notice. Vendoring a
   third-party tree needs its own justification and licence review.
3. **Environments stay distinguishable.** PROD and DEV variants of the same file are kept side by side with their
   full digests. A DEV stub is never stored or described as the PROD implementation.
4. **One copy of each source file.** A deployed file whose exact bytes are already tracked is referenced by path and
   digest, not copied again.
5. **Never in Git, private repository or not:** credentials and tokens of any kind (including package-embedded
   localhost tokens), private keys and custody material (owner, K-PCK, K-ACT, K-WIT, signer and witness), `.env`
   files with values, live databases and conversation state, canonical or personal memory content, Privacy records,
   persona and profile runtime files (`SOUL.md`, `USER.md`), owner-origin and First Interaction content, private
   research history, and recovery passphrases. Files that mix source with a secret are committed as templates with
   a placeholder and an injection tool that reads the value from custody.
6. **Byte-exact by default.** Preserved deployed and historical files keep their bytes. Every adaptation (secret
   redaction, a Markdown newline) is listed with the original digest; the original bytes stay in owner-controlled
   encrypted backup.
7. **What cannot be preserved locally stays visible.** Source that exists only on a host is recorded as
   `VM_ONLY_SOURCE_PENDING_SEPARATE_EXPORT` with its digest and location. It is never reconstructed by guesswork.
8. **Source in Git is not a deployment.** Adding source never installs, enables or runs anything; deployment follows
   ADR-0005 and its own approvals.

## Alternatives considered

### Keep runtime source outside Git

Status quo. It leaves the running system dependent on workstation folders and VM disks, with no review history. Not
selected.

### Commit the encrypted archive or the deployed release tarballs

Recovers the exact bytes in one step, but publishes an embedded credential, large third-party binaries and private
content, and gives no reviewable source. Not selected; the archive stays in owner custody.

### Vendor the full upstream Hermes tree

About 10,000 third-party files for eight changed ones, and it hides the LILITH change set. Not selected while a pin
plus patches reproduces the bytes.

## Consequences

### Positive

- Every locally available source of the running DEV runtime, and every PROD Hermes and Router file except two, can
  be rebuilt from Git and verified by digest.
- PROD/DEV differences become reviewable diffs instead of host archaeology.

### Negative and tradeoffs

- Historical scripts name hosts, paths and workstations of their time; they are kept for provenance and are not
  runnable as is.
- Byte-exact copies keep their original whitespace and line endings, so the repository's whitespace check is
  disabled for those paths by scoped `.gitattributes`.
- Rebuilding the DEV release still needs the gate token from custody and the third-party wheels.

### Operational and migration impact

- No host changes. The PROD-only gaps close only through a separately approved, sanitized PROD source export.
- Merging source under `integrations/` into `main` is classified `DEPLOY_REQUIRED` by the existing DEV gate, like
  any non-control change; it redeploys the Core API bundle to DEV and never installs Hermes.

## Verification

- `integrations/hermes/tools/reconstruct_hermes_src.py` and `integrations/hermes/home/tools/assemble_home.py` rebuild
  and digest-check the Hermes and Router trees offline.
- A secret scan and a template check run before each change set.
