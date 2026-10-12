# Slice 15B2b-B1b-3e — M-B12 PR-B1: PR-2 / PR-3 / Readiness-Input Prerequisite Tooling

Status:

- **REPOSITORY ONLY. TOOLING AND PROPOSALS. NOTHING RUN LIVE.** This slice adds three control- / owner-side tools
  and their synthetic tests: a PR-2 snapshot-inventory classifier (E-20), a PR-3 off-host material assembler
  (E-21, with the RR-38 B comparison used by E-18), and a PR-1 readiness input builder with a stdin envelope
  reader (OD-M11-15). No DEV or S25 contact, no plink / IAP / gcloud, no P1B-10R installation or plan retry, no
  signer start, no K-ACT load, no credential access, no HELD or custody mutation.
- **No PR-2 or PR-3 acceptance exists or is claimed.** The accepted PR-2 record
  ([inventory](slice-15b2b-b1b3e-pr2-snapshot-inventory.md), [acceptance](slice-15b2b-b1b3e-pr2-acceptance.md))
  predates K-WIT and the bootstrap state; no record declares PR-3 full material (E-21) complete. The tools produce
  a package input only from a live observation / owner-retained bytes **and** an owner acceptance or confirmation
  naming the exact digest; neither is created here.
- **The release judge is unchanged.** `pr1_acceptance.py` (`e0928854…`, pinned in `release_file_set.SHARED_HASHES`,
  installed in release `aee323e`) is not modified. Its E-19 activation-line mismatch is recorded in §8, not fixed.
- OD-M11-12, OD-M11-13, OD-M11-14 and OD-M11-15 stay **PROPOSED**. New proposals OD-M12-1 … OD-M12-5 (§10) are
  **PROPOSED**. Registry effectiveness, authority activation, First Memory and PROD stay **NOT AUTHORIZED**.

```text
inventory classified != PR-2 accepted;  candidate assembled != PR-3 full material accepted
input document != readiness;  root HOLD_RELEASE_ELIGIBILITY READY (E-17) != PR-1 package READY (E-1 … E-24)
envelope digest != owner acceptance;  package digest != authority signature;  READY is the verifier's, never a tool's
```

## 1. What is added

| File | Role | SHA-256 |
| --- | --- | --- |
| `services/owner-memory-control/tools/mb12_pr2_inventory.py` | PR-2 inventory classification; E-20 package input | `be8237972a93c04eb8b41b3a099df2e04fc1aa5840e0faa67e81c133e5c8045a` |
| `services/owner-memory-control/tools/mb12_pr3_material.py` | PR-3 `OwnerOffHostMaterialV1` candidate; E-21 package input; RR-38 B comparison | `640396badf7a74a7bccf835372f6be9bb47f2b343e2e5a79a1cce8843e05bd8a` |
| `services/owner-memory-control/tools/mb12_readiness_inputs.py` | `LILITH_PR1_VERIFIER_INPUTS` builder; stdin envelope reader | `b615e12bf1d623322b4e59810bd69a7c602a57c349fb787aae76f84f2f85ec2b` |
| `services/owner-memory-control/tests/test_b1b3e_mb12_prb1_prerequisites.py` | 27 synthetic tests | — |

All three tools live outside the release-controlled `services/authority-dev` tree and outside
`lilith_owner_memory`, so the release file set and `SHARED_HASHES` are unchanged. They are pure: no subprocess, no
socket, no file write, no host path (a source-guard test enforces this).

## 2. PR-2 / E-20: `mb12_pr2_inventory`

Input: one `LILITH_PR2_SNAPSHOT_INVENTORY` V1 document, collected elsewhere by a separately authorized read-only
PR-2 step. Fields (closed): `environment`, `evidenceClass`, `window`, `keys`, `listings`, `artefacts`,
`carriedDebts`, `privateEvidenceSha256`.

| Rule | Source | Behaviour |
| --- | --- | --- |
| complete provider listing | PR-2 record; preflight §21 row 1 | every kind (`DISK_SNAPSHOTS`, `INSTANT_SNAPSHOTS`, `IMAGES`, `MACHINE_IMAGES`, `SNAPSHOT_SCHEDULES`, `BACKUP_DR`, `BUCKETS`, `ADMIN_ACTIVITY_CREATE_CALLS`) present, `complete=true`, count = listed artefacts; otherwise the classes are `UNKNOWN_PROVENANCE` and it FAILs |
| key relationships | E-20; preflight §21 row 3 | exactly `K_ACT`, `K_WIT`, `HOST_KEY`; both ciphertexts `sealedUnder=HOST_KEY`; K-ACT / K-WIT fingerprints equal the records (B3 `dd13a1fb…`, K-WIT `5d778701…`); the host key has no public identity and is never named or read |
| artefact class | gate §5.2 / §5.6 (RR-7, RR-17) | plaintext → `EXPOSED_PRIVATE_MATERIAL`; unknown access → `UNKNOWN_PROVENANCE`; outside the accepted boundary: both halves or the secret → `EXPOSED_PRIVATE_MATERIAL`, ciphertext only → `UNKNOWN_PROVENANCE`; inside: the secret → `KNOWN_CUSTODY_DEBT`; ciphertext only → `SAFE_RETAINED_CIPHERTEXT`, unless the host secret is retained (→ `KNOWN_CUSTODY_DEBT`) or exposed (→ `EXPOSED_PRIVATE_MATERIAL`) anywhere |
| per key | gate §5.2 "a key's action follows its worst artefact" | worst class over its own ciphertexts and every artefact holding the host secret |
| E-20 judge | `pr1_acceptance._snapshot_reason` (unchanged) | every key `SAFE_RETAINED_CIPHERTEXT`, `KNOWN_CUSTODY_DEBT` or `NO_SNAPSHOTS`; every debt artefact named |
| carried debts | M-B2 completion (C-4) | `DEV_CARRIED_DEBTS = ("C-4",)` must be named; never dropped |
| freshness | OD-M12-3 | `notBefore` is an explicit argument; a window starting earlier is `INVENTORY_STALE` |

`package_input` returns the E-20 verifier form (`status=ACCEPTED`, `recordSha256`, `artefactClasses`,
`namedDebts`) only when the document is `LIVE_OBSERVATION`, the classification PASSes, and a supplied
`LILITH_PR2_INVENTORY_OWNER_ACCEPTANCE` names exactly `inventoryDigest` and is dated at or after the window end.
`recordSha256` is the inventory digest, SHA-256(`LILITH_PR2_SNAPSHOT_INVENTORY_V1\0` ‖ JCS(document)) (OD-M12-2).
A `SYNTHETIC_FIXTURE` is classified but always refused as a package input.

## 3. PR-3 / E-21 (and E-18 B): `mb12_pr3_material`

Input: the owner's retained **public** bytes (preflight §22): K-ACT publication, K-WIT publication, registry-root
anchor, Registry V1, genesis pin, authorization register, successor ceremony register. Each is parsed with the
canonical contract and compared with the accepted record:

| Value | Check | DEV record |
| --- | --- | --- |
| K-ACT publication | strict canonical bytes; file SHA-256; `publicKeySha256` = B3 | `d7647976…`, `dd13a1fb…` (M-B3, M-B11 §12) |
| K-WIT | `WitnessKeyPublicationV1`; fingerprint | `5d778701…` (M-B2) |
| K-ROOT | `TrustedRegistryRootV1` from the anchor; SHA-256(public key) | `cb36daf1…` (E-21, M-B1) |
| Registry V1 | signature verifies under that root (`verify_authority_registry`); head | `(1, fa662721…)` (M-B3) |
| genesis pin | `OwnerGenesisPinV1`; digest; file bytes = recorded on-host copy (E-12) | `ac892dc2…`, `35747736…` (Package A) |
| authorization register | `OwnerAuthorizationRegisterV1`; file bytes = recorded copy; **`authorizations` empty**; heads = `{(1, fa662721…)}` | `8d5ab875…` (Package A) |
| successor ceremony register | `SuccessorCeremonyRegisterV1`; **no entries** (no burned ordinal) | supplied by the owner; never created here |
| burned identities | `burned_identities.burned_identity` over K-ROOT, K-WIT, K-ACT, the registry digest and the genesis digest | refused if any matches |
| release provenance | `aee323e…`, manifest `1d578ca7…` | PR-1A |

The result is a `LILITH_PR3_OFFHOST_MATERIAL_CANDIDATE` with the exact `offHostMaterial` verifier fields
(`registerSha256` = SHA-256 of the authorization register bytes, the fixture precedent; `kActPublicationSha256` =
SHA-256 of the canonical publication bytes, as `pr1_acceptance` E-18 recomputes), `authorizationIds = []`,
`burnedOrdinals = []`, per-source digests, and a domain-separated candidate digest. `ownerConfirmed` and
`pr3FullMaterialAccepted` are always false. `package_input` emits `status=PRESENT` only for
`OWNER_RETAINED_PUBLIC_BYTES` with a `LILITH_PR3_MATERIAL_OWNER_CONFIRMATION` naming the exact candidate digest
(OD-M12-4). `offhost_reproduction(material, package)` is the owner-side RR-38 B comparison: every value the package
evidence shows (pin and genesis, registry head, K-WIT, K-ACT publication, release, the bound register) must equal the
material, and the package dark flags must be false; it never trusts the package's own E-18 verdict.

## 4. Readiness inputs: `mb12_readiness_inputs`

`build` produces the closed `LILITH_PR1_VERIFIER_INPUTS` document (exactly the fields
`lilith_authority_root.verifier.parse_verifier_inputs` accepts; the M-B11 `ownerInputs`) inside one
`LILITH_MB12_READINESS_INPUT_ENVELOPE` (JCS + one LF), with `inputsSha256` = SHA-256(JCS(document)) and a
provenance block. It is deterministic (byte-identical on rebuild).

| Input | Rule |
| --- | --- |
| window | `notBefore` ≤ every `observedAt` ≤ `notAfter`; otherwise `INPUT_STALE` |
| release | `releaseSha` and attested manifest = the records; reviewed runtime digests optional, hex only |
| first-preflight CURRENT | the root observation of the pinned slot (`6a61c350…`, mode `0600`, decimal identity strings), with its own `observedAt` and evidence digest; never decrypted |
| K-ACT / K-WIT publications | the exact recorded bytes (file SHA-256, B3, K-WIT fingerprint) |
| proofs | only from the producer mapped in `PROPOSED_PROOF_PRODUCERS` (§6); an unmapped name is `PROOF_PRODUCER_UNMAPPED`; `FAIL` passes through verbatim; a missing proof stays missing |
| activation | stdout must be exactly one line, exit 1, and equal the complete host line `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false`; passed **verbatim** (§8) |
| PR-2 / PR-3 | the outputs of §2 / §3 `package_input`, or `null` |

`read_envelope` (host side) reads at most 256 KiB from stdin, requires SHA-256(bytes) = the reviewed digest given
on the command line, strict JSON without duplicate keys, the canonical byte form, the exact envelope fields, the
environment, and `inputsSha256`; it returns the document for in-process use (as `mb11_signer_verifier.readiness_pair`
takes `ownerInputs`). No file is written; the installed root CLI is not used, because
`lilith_authority_root.cli._document` reads only a regular file (`read_regular`), so stdin delivery cannot reach it
without a release change (OD-M11-15). `verify-envelope` only validates; it evaluates nothing.

The build report lists `expectedNotReady` (missing proofs, absent PR-2 / PR-3, E-19) and
`knownPackageDefects`; it sets `readinessEvaluated: false`.

## 5. What the release verifier actually returns (synthetic, end to end)

Over the synthetic `Pr1Host` (environment `test`, the real `lilith_authority_root.verifier.evaluate`, HELD exact,
HEALTH captured), with only honestly buildable inputs:

| Inputs | Root E-17 readiness | Package | Failing checks |
| --- | --- | --- | --- |
| mapped proofs only; real activation line; PR-2 / PR-3 `null` | READY | NOT_READY | E-07 `PROOF_MISSING:OS_DENIAL`, E-18 `OFFHOST_MATERIAL_UNAVAILABLE`, E-19 `ACTIVATION_NOT_DARK`, E-20 `SNAPSHOT_INVENTORY_ABSENT_PR2`, E-21 `OFFHOST_REGISTER_ABSENT_PR3`, E-22 `PROOF_MISSING:SECRET_HYGIENE`, E-23 `PROOF_MISSING:PRESERVATION_SET` |
| as above + accepted PR-2 + confirmed PR-3 (tool outputs) | READY | NOT_READY | E-07, E-19, E-22, E-23 (E-18, E-20, E-21 PASS; RR-38 B reproduction empty) |

This corrects the expectation in the [M-B11 design record](slice-15b2b-b1b3e-mb11-signer-start-design.md) §4 row C
("package fails exactly E18, E20, E21"): that row used the 3-field activation constant and fixture proofs for all
seven names. With observed inputs the package also fails E-07, E-19, E-22 and E-23. Package READY is therefore not
reachable today by any honest input; it needs §8 (a release change) and the three missing producers (§6).

## 6. The seven proof names (OD-M11-14, PROPOSED mapping)

| Proof name | Package check | Proposed producer | Status |
| --- | --- | --- | --- |
| `SIGNER_DENIAL` | E-07 | `scripts/authority_custody_denial_proof.py` phase `P1B-12` (fixed `runuser … test` rows + the signer mount-namespace rows) | producer exists; **the 12 `DEFERRED_UNTIL_PHASE: P1B-12` rows and the 9 namespace rows are NOT PERFORMED** (need the running signer; no partial phase) |
| `OS_DENIAL` | E-07 | **none** | **GAP**: E-07 names "unit property + mount-namespace probe"; no tool emits an `OS_DENIAL` result, and whether it is the namespace half of the P1B-12 transcript or a separate unit-property proof is undecided |
| `DEPLOYER_DENIAL` | E-08 (`detail = maturity=P1A-9`) | `scripts/deployer_authority_boundary_proof.sh` (DR-5 on a real routine deployment) | producer exists; transcript = the DR-5 output of the bound deploy run |
| `BROKER_DENIAL` | E-09 | `scripts/authority_custody_denial_proof.py` phase `P1B-12` (the broker is an `OUTSIDER` in every row) | producer exists; the same transcript as `SIGNER_DENIAL` (its docstring binds it into E-7 and E-9); NOT PERFORMED at P1B-12 |
| `BROKER_PRESERVATION` | E-09 | `scripts/verify_broker_dev_current_incarnation.py` (`preservation`, `BROKER_PRESERVATION=PASS`) | producer exists |
| `SECRET_HYGIENE` | E-22 | **none** | **GAP**: ceremony records report scans (for example M-B2 "secret scan 0"), but no tool produces a bindable E-22 result over journal, transcript and publication scans for every PR-1B ceremony |
| `PRESERVATION_SET` | E-23 | **none** | **GAP**: the host POST preservation readers cover parts (broker, units), but no tool emits a B1b-3d §23 preservation-set result (Stage III, broker, API unit) as one transcript |

The builder enforces this table fail-closed: a proof is admitted only from its mapped producer; the three gaps are
refused, so E-07, E-22 and E-23 stay NOT_READY until a producer is implemented, reviewed and the mapping accepted.

## 7. E-25 … E-28 (OD-M11-13): retained gap

Sequencing §11 says the canonical package digest covers E-25 … E-28 (owner freshness `AUTHENTIC` + `CURRENT` at
package time, record 1 `77752db1…` and the R1 package, P3-3 storage and independence evidence, acceptance envelope
1 `95da36cd…` and `ACCEPTANCE_COMPLETE`). `pr1_acceptance.PACKAGE_CHECKS` ends at E-24 and the verifier input has
no field for them. This slice binds **none** of them (the PR-3 candidate states `E-25..E-28 owner-side bindings: NOT
BOUND`). Options for OD-M11-13 are unchanged: a release change adding the checks, or an owner amendment keeping
E-25 … E-28 as an owner-side package bound to the PR-1 package digest at M-B13.

## 8. `pr1_acceptance` has the PR #185 activation-line mismatch (recorded, not fixed)

- **Issue.** `pr1_acceptance.ACTIVATION_DARK_LINE = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT"`, and E-19 passes
  only when `activation.line == ACTIVATION_DARK_LINE`. The B1c verifier
  (`scripts/dev_deployer/lilith_activation_verify.py`, the `NOT_ACCEPTED` branch) always prints
  `ACTIVATION=NOT_ACCEPTED reason=<reason> advisoryConfigEnabled=<advisory>`; on DEV the observed line is
  `… advisoryConfigEnabled=false` in every host POST. The root verifier passes the owner-supplied line verbatim.
  So an honest input FAILs E-19 (`ACTIVATION_NOT_DARK`); only a rewritten (non-observed) line passes. This is the
  defect PR #185 fixed in `mb11_restart_boundary_install.ACTIVATION_DARK`; the fixtures
  (`services/authority-dev/tests/pr1s_fixtures.py` `verifier_inputs`) and
  `test_pr1s_runtime_wiring.py` (`ACTIVATION_DARK_LINE` constant pin) use the 3-field form, which is why no test
  caught it.
- **Not fixed here.** `pr1_acceptance.py` is pinned (`e0928854…`) and shipped in release `aee323e`; a fix is a
  release change (new release, re-pin `SHARED_HASHES`, PR-1A-style install), unrelated to this repository-only
  slice. The builder refuses to rewrite the line, and `test_known_defect_e19_rejects_the_complete_host_line` pins
  the defect so that a fix must update it.
- **Necessary tests for the fix.** The complete line with `advisoryConfigEnabled=false` (and exit 1, one line) →
  PASS; the bare 3-field form → FAIL (not an observed form); `advisoryConfigEnabled=true` → FAIL; any other reason
  or `ACTIVATION=ACCEPTED …` → FAIL; trailing space, CR, a second line → FAIL; the fixture `verifier_inputs` and the
  constant pin updated to the full line; a source-text test anchoring the printed format of
  `lilith_activation_verify.py`; the `SHARED_HASHES` re-pin; the §5 synthetic end-to-end then fails only E-07,
  E-22, E-23 (OD-M12-5).

## 9. Sequencing: root eligibility READY versus package READY (OD-M11-12)

Known distinction (M-B11 design §4, §12; preflight §19, §20, §27, §28):

| Evaluation | What it is | Can it be READY at M-B12 today? |
| --- | --- | --- |
| root `HOLD_RELEASE_ELIGIBILITY` (= package E-17) | `successor_readiness` over the complete hold observation and the captured HEALTH; READY proves the HELD binding (B1 = … = B4, B5, B6) | yes, after M-B11 (synthetic proof §5) |
| PR-1 package (E-01 … E-24) | `pr1_acceptance`: E-17 plus PR-2, PR-3, the proofs, activation, nonclaims; the RR-38 package digest | **no**: E-19 (§8), E-07 / E-22 / E-23 (§6) and, until supplied, E-18 / E-20 / E-21 |

Preflight §27 M-B12 says "eligibility READY; package digest"; §20 (OWNER-ACCEPTED) places PR-3 full material after
`HOLD_RELEASE_ELIGIBILITY`; §28 puts PR-3 full material after P1B-12 and requires E-1 … E-24 at P1B-13. Nothing here
rewrites these contracts. Proposed wording for owner review (choose one; both keep package READY required before
M-B13 acceptance and on the M-B14 re-run, RR-38):

> **OD-M11-12 (option A, PROPOSED).** In the preflight §27 M-B12 row, "eligibility READY" means: the release's root
> verifier, over one complete hold observation and the captured signer HEALTH bound to the observed InvocationID,
> returns `HOLD_RELEASE_ELIGIBILITY` READY with no reason (package check E-17 PASS), and the canonical PR-1 package
> and its digest are produced and recorded with every non-PASS check and reason verbatim. M-B12 does not require
> the package status to be READY and does not reinterpret, default or omit any check. A package digest recorded at
> M-B12 is approvable at M-B13 only if that package is READY on a current re-run. The §20 order is unchanged.

> **OD-M11-12 (option B, PROPOSED; matches the preferred direction).** In the preflight §27 M-B12 row, "eligibility
> READY" means the PR-1 package (E-01 … E-24) is READY over one complete hold observation and the captured signer
> HEALTH; E-17 READY alone is insufficient. To make this reachable, the owner amends the §20 / §28 order so that a
> fresh PR-2 inventory (E-20, accepted by digest, freshness bound OD-M12-3) and the PR-3 full material (E-21,
> confirmed by digest) are completed **before the M-B11 signer start**, and no custody event between them and
> M-B12 invalidates them. This amendment does not relax any E-check, and M-B12 stays blocked until §8 and the three
> §6 producers exist.

Recommendation: option B as the sequencing target (it avoids a signer running while PR-2 / PR-3 are still open,
matching OD-M11-6 "prepare every non-signer M-B12 input first"), but it requires a formal §20 amendment and cannot
complete before the §8 release change; option A is the only reading under which M-B12 could complete without that
change. This is an owner decision; neither is applied here.

## 10. New proposals (PROPOSED, none accepted)

| # | Proposal | Blocks |
| --- | --- | --- |
| OD-M12-1 | accept the three tools of §1 as the PR-2 / PR-3 / readiness-input tooling (pins above), with their input schemas | tooling use in any live step |
| OD-M12-2 | E-20 `recordSha256` = the domain-separated inventory digest, and the owner PR-2 acceptance names that digest | PR-2 package input |
| OD-M12-3 | the DEV PR-2 freshness bound `notBefore` (for example the M-B11 start, or the M-B12 sequence start) | PR-2 package input |
| OD-M12-4 | the PR-3 owner confirmation by candidate digest as the E-21 / E-18 owner act, with `registerSha256` = SHA-256 of the authorization register bytes | PR-3 package input |
| OD-M12-5 | the E-19 release fix of §8 (scope, new release, re-pin) | package READY (any OD-M11-12 option) |

## 11. Test results

- `services/owner-memory-control/tests/test_b1b3e_mb12_prb1_prerequisites.py`: 27 tests, OK (WSL Ubuntu-24.04,
  `PYTHONPATH=~/l1deps:…`, as for the PR-1S suites; the synthetic-host tests are POSIX-only).
- `python -m unittest discover -s services/owner-memory-control/tests`: 1563 tests, OK (15 skipped, environmental);
  `services/authority-dev/tests`: 241 tests, OK; `scripts/test_deployer_authority_boundary_proof.py`: 36 tests, OK
  (same WSL recipe, as root).
- `python scripts/validate_repository.py`: passed (249 Markdown files).

## 12. Remaining work and recommended next slice

Remaining before a live M-B12: the OD-M11-12 decision; OD-M11-13 (E-25 … E-28); OD-M11-14 and the three missing
producers (`OS_DENIAL`, `SECRET_HYGIENE`, `PRESERVATION_SET`); OD-M11-15 (stdin wiring into the W11 / M-B12 host
run, which today takes `ownerInputs` in its evidence file); the §8 release fix; a fresh live PR-2 collection and
owner acceptance; owner-retained PR-3 bytes and confirmation; the deferred P1B-12 denial rows and namespace rows
(NOT PERFORMED); and, upstream, the parked P1B-10R installation and M-B11 start.

Recommended next engineering slice (PR-B2, repository only): the three missing proof producers as fixed root
transcripts in the `authority_custody_denial_proof.py` style (closed phases, PASS / FAIL last line, transcript
SHA-256 bound by the builder), plus the stdin input path for the W11 / M-B12 host run using `read_envelope`. The §8
E-19 fix should be scoped as its own release-change slice (OD-M12-5).

## 13. State

```text
M-B12 PR-B1 PREREQUISITE TOOLING = REPOSITORY ONLY, READY FOR OWNER REVIEW
PR-2 FRESH INVENTORY = NOT COLLECTED;  PR-2 ACCEPTANCE (E-20) = NONE
PR-3 FULL MATERIAL (E-21) = NOT CLAIMED;  OWNER CONFIRMATION = NONE
E-19 RELEASE JUDGE DEFECT = RECORDED, NOT FIXED
OS_DENIAL / SECRET_HYGIENE / PRESERVATION_SET PRODUCERS = MISSING
P1B-12 DEFERRED DENIAL ROWS (12) AND SIGNER-NAMESPACE ROWS (9) = NOT PERFORMED
E-25 … E-28 = NOT BOUND
OD-M11-12 … OD-M11-15, OD-M12-1 … OD-M12-5 = PROPOSED
P1B-10R INSTALL = NOT PERFORMED;  SIGNER START / K-ACT LOAD = NOT AUTHORIZED
REGISTRY EFFECTIVE = NO;  AUTHORITY ACTIVE = NO;  FIRST MEMORY / PROD = NOT AUTHORIZED
```
