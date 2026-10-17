# Slice 15B2b-B1b-3e — M-B12 PR-B1: PR-2 / PR-3 / Readiness-Input Prerequisite Tooling

Status:

- **REPOSITORY ONLY. TOOLING AND PROPOSALS. NOTHING RUN LIVE.** This slice adds three control- / owner-side tools
  and their synthetic tests: a PR-2 snapshot-inventory classifier (E-20), a PR-3 off-host material assembler
  (E-21, with the RR-38 B comparison used by E-18), and a PR-1 readiness input builder with a stdin envelope
  reader (OD-M11-15). No DEV or S25 contact, no plink / IAP / gcloud, no P1B-10R installation or plan retry, no
  signer start, no K-ACT load, no credential access, no HELD or custody mutation.
- **No PR-2 or PR-3 acceptance exists or is claimed, and on DEV every package input is REFUSED today.** The accepted
  PR-2 record ([inventory](slice-15b2b-b1b3e-pr2-snapshot-inventory.md),
  [acceptance](slice-15b2b-b1b3e-pr2-acceptance.md)) predates K-WIT and the bootstrap state; no record declares PR-3
  full material (E-21) complete. A caller-supplied acceptance, confirmation or proof transcript is never by itself
  evidence of an owner decision or of what ran on DEV (§2a). The DEV trust pins are empty and the freshness cutoff
  (OD-M12-3) is undecided, so the DEV forms fail closed.
- **The release judge is unchanged.** `pr1_acceptance.py` (`e0928854…`, pinned in `release_file_set.SHARED_HASHES`,
  installed in release `aee323e`) is not modified; no release, `current` pointer or witness is touched. Its E-19
  activation-line mismatch is recorded in §8, not fixed.
- OD-M11-12, OD-M11-13, OD-M11-14 and OD-M11-15 stay **PROPOSED**. New proposals OD-M12-1 … OD-M12-6 (§10) are
  **PROPOSED**. §20 / §28 are **not amended**. Registry effectiveness, authority activation, First Memory and PROD stay
  **NOT AUTHORIZED**.
- Revised after the PR #186 owner review (CHANGES REQUIRED on `64df007`): §14 lists the corrections.

```text
inventory classified != PR-2 accepted;  candidate assembled != PR-3 full material accepted
caller-made acceptance / confirmation / transcript != owner decision / DEV evidence  (§2a)
input document != readiness;  root HOLD_RELEASE_ELIGIBILITY READY (E-17) != PR-1 package READY (E-1 … E-24)
envelope digest != owner acceptance;  package digest != authority signature;  READY is the verifier's, never a tool's
```

## 1. What is added

| File | Role | SHA-256 |
| --- | --- | --- |
| `services/owner-memory-control/tools/mb12_pr2_inventory.py` | PR-2 inventory classification; E-20 package input | `24370a37c5d0b6514978c41ed43288818320140cc7332f6fdbc934189e10f5ad` |
| `services/owner-memory-control/tools/mb12_pr3_material.py` | PR-3 `OwnerOffHostMaterialV1` candidate; E-21 package input; RR-38 B comparison | `cc63183ad6fef0f604fd451db48098f762b14b0828eb1c654783f472360de73d` |
| `services/owner-memory-control/tools/mb12_readiness_inputs.py` | `LILITH_PR1_VERIFIER_INPUTS` builder; producer transcript contracts; stdin envelope reader | `1005d730b393ec5a71d89741f3eac9df7fe870f68cf3b54718da632ec72fef09` |
| `services/owner-memory-control/tests/test_b1b3e_mb12_prb1_prerequisites.py` | 42 synthetic tests (12 forgery regressions, §14) | — |

All three tools live outside the release-controlled `services/authority-dev` tree and outside
`lilith_owner_memory`, so the release file set and `SHARED_HASHES` are unchanged (a test asserts the
`pr1_acceptance.py` pin). They are pure: no subprocess, no socket, no file write, no host path (a source-guard test
enforces this). The readiness builder reads the pinned producer scripts' bytes from the repository and loads the
custody denial proof's row constants only (its `main` runs under `__main__` alone).

## 2. PR-2 / E-20: `mb12_pr2_inventory`

Input: one `LILITH_PR2_SNAPSHOT_INVENTORY` V1 document, collected elsewhere by a separately authorized read-only
PR-2 step. Fields (closed): `environment`, `evidenceClass`, `window`, `keys`, `listings`, `artefacts`,
`carriedDebts`, `privateEvidenceSha256`.

| Rule | Source | Behaviour |
| --- | --- | --- |
| complete provider listing | PR-2 record; preflight §21 row 1 | every kind (`DISK_SNAPSHOTS`, `INSTANT_SNAPSHOTS`, `IMAGES`, `MACHINE_IMAGES`, `SNAPSHOT_SCHEDULES`, `BACKUP_DR`, `BUCKETS`, `ADMIN_ACTIVITY_CREATE_CALLS`) present, `complete=true`, artefact counts = listed artefacts; otherwise the classes are `UNKNOWN_PROVENANCE` and it FAILs |
| Admin Activity create calls | gate §5.2 class 3 ("any snapshot not in the inventory") | the schema binds no call to an artefact, so **any** nonzero `ADMIN_ACTIVITY_CREATE_CALLS` count makes every key and the inventory `UNKNOWN_PROVENANCE` (`ADMIN_ACTIVITY_CREATE_CALLS_UNEXPLAINED:<n>`), even with zero listed artefacts |
| key relationships | E-20; preflight §21 row 3 | exactly `K_ACT`, `K_WIT`, `HOST_KEY`; both ciphertexts `sealedUnder=HOST_KEY`; K-ACT / K-WIT fingerprints equal the trust's identities (DEV: B3 `dd13a1fb…`, K-WIT `5d778701…`); the host key has no public identity and is never named or read |
| artefact class | gate §5.2 / §5.6 (RR-7, RR-17) | plaintext → `EXPOSED_PRIVATE_MATERIAL`; unknown access → `UNKNOWN_PROVENANCE`; outside the accepted boundary: both halves or the secret → `EXPOSED_PRIVATE_MATERIAL`, ciphertext only → `UNKNOWN_PROVENANCE`; inside: the secret → `KNOWN_CUSTODY_DEBT`; ciphertext only → `SAFE_RETAINED_CIPHERTEXT`, unless the host secret is retained (→ `KNOWN_CUSTODY_DEBT`) or exposed (→ `EXPOSED_PRIVATE_MATERIAL`) anywhere |
| empty material | no canonical "no custody material" class | an artefact with an empty `material` list is REFUSED (`INVENTORY_ARTEFACT_MATERIAL_EMPTY`) |
| per key | gate §5.2 "a key's action follows its worst artefact" | worst class over its own ciphertexts and every artefact holding the host secret |
| E-20 judge | `pr1_acceptance._snapshot_reason` (unchanged) | every key `SAFE_RETAINED_CIPHERTEXT`, `KNOWN_CUSTODY_DEBT` or `NO_SNAPSHOTS`; every debt artefact named |
| carried debts | M-B2 completion (C-4) | `DEV_CARRIED_DEBTS = ("C-4",)` must be named; never dropped |
| freshness | OD-M12-3 | the trust's `not_before` (never a caller argument); a window starting earlier is `INVENTORY_STALE` |

`package_input(document, acceptance, environment=…, trust=…)` returns the E-20 verifier form (`status=ACCEPTED`,
`recordSha256`, `artefactClasses`, `namedDebts`) only when: the document is `LIVE_OBSERVATION`; it classifies PASS
against the trust's key identities, cutoff and carried debts; a `LILITH_PR2_INVENTORY_OWNER_ACCEPTANCE` names
exactly `inventoryDigest`, is dated at or after the window end; **and** the trust's `accepted_inventories` maps that
digest to that acceptance's `acceptanceRecordSha256` (§2a). Otherwise it refuses (`TRUST_REQUIRED`,
`TRUST_MALFORMED`, `INVENTORY_STALE`, `INVENTORY_KEY_IDENTITY_MISMATCH`, `OWNER_ACCEPTANCE_NOT_ESTABLISHED`, …).
`recordSha256` is the inventory digest, SHA-256(`LILITH_PR2_SNAPSHOT_INVENTORY_V1\0` ‖ JCS(document)) (OD-M12-2).
A `SYNTHETIC_FIXTURE` is classified but always refused as a package input. `classify` alone is a report: it grants
nothing and is never a package input.

## 2a. Trust boundary (owner decisions, proof provenance, freshness)

DEV_SYNTHETIC owner acts are unsigned (PR3-D1 option A). In this repository the only established binding of an owner
decision to a value is a **reviewed, merged owner record whose accepted value is then pinned in tool source** (the
pattern of `ACCEPTED_GENESIS`, `EXPECTED_HELD_SHA256`, `ACCEPTED_CANDIDATE_DIGEST`). The tools therefore treat every
caller-supplied acceptance, confirmation or transcript as a claim, and admit it only when it matches such a pin:

| Pin (DEV value) | Establishes | Until set |
| --- | --- | --- |
| `mb12_pr2_inventory.DEV_FRESHNESS_NOT_BEFORE` (`None`) | the DEV lower freshness bound for the PR-2 window and every readiness observation (OD-M12-3) | every DEV PR-2 package input and every DEV build: `FRESHNESS_CUTOFF_UNDECIDED` |
| `mb12_pr2_inventory.DEV_ACCEPTED_INVENTORIES` (`{}`) | inventory digest → the owner PR-2 acceptance record SHA-256 | `OWNER_ACCEPTANCE_NOT_ESTABLISHED` |
| `mb12_pr3_material.DEV_ACCEPTED_CANDIDATES` (`{}`) | candidate digest → the owner PR-3 confirmation record SHA-256 | `OWNER_CONFIRMATION_NOT_ESTABLISHED` |
| `mb12_readiness_inputs.DEV_ACCEPTED_PROOF_TRANSCRIPTS` (`{}`) | proof name → the transcript SHA-256s an owner record accepted as the producer's DEV output | `PROOF_PROVENANCE_NOT_ESTABLISHED` |

The DEV trust is built only from these pins (`trust_for("dev", None)`); a caller-supplied trust for DEV is refused
(`DEV_TRUST_NOT_OVERRIDABLE`). Other environments (`test`) must pass an explicit, complete trust object
(`Pr2TrustV1`, `Pr3TrustV1`, `ReadinessTrustV1`), which is how the synthetic tests stand in for merged records.

**Missing binding (recorded, not invented).** No repository mechanism authenticates an owner acceptance, an owner
confirmation or a DEV transcript at the moment it is presented: there is no owner signature at DEV_SYNTHETIC and no
DEV-side signature on producer output. Pinning after a merged record is therefore the only binding available, and it
has a cost: a proof collected inside the M-B12 sequence must be recorded, reviewed and pinned before the package
input can be built. Whether that sequencing is acceptable, or a signed owner act / signed producer output is
required instead, is OD-M12-6.

## 3. PR-3 / E-21 (and E-18 B): `mb12_pr3_material`

Input: the owner's retained **public** bytes (preflight §22): K-ACT publication, K-WIT publication, registry-root
anchor, Registry V1, genesis pin, authorization register, successor ceremony register. Each is parsed with the
canonical contract and compared with the trust's expectations (DEV: `DEV_EXPECTED`, not overridable):

| Value | Check | DEV record |
| --- | --- | --- |
| K-ACT publication | strict canonical bytes; file SHA-256; `publicKeySha256` = B3 | `d7647976…`, `dd13a1fb…` (M-B3, M-B11 §12) |
| K-WIT | `WitnessKeyPublicationV1`; fingerprint | `5d778701…` (M-B2) |
| K-ROOT | `TrustedRegistryRootV1` from the anchor; SHA-256(public key) | `cb36daf1…` (E-21, M-B1) |
| Registry V1 | signature verifies under that root (`verify_authority_registry`); head | `(1, fa662721…)` (M-B3) |
| genesis pin | `OwnerGenesisPinV1`; digest; file bytes = recorded on-host copy (E-12) | `ac892dc2…`, `35747736…` (Package A) |
| authorization register | `OwnerAuthorizationRegisterV1`; file bytes = recorded copy; **`authorizations` empty**; heads = `{(1, fa662721…)}` | `8d5ab875…` (Package A) |
| successor ceremony register | `SuccessorCeremonyRegisterV1` (duplicate keys refused); **no entries** (no burned ordinal) | supplied by the owner; never created here |
| burned identities | `burned_identities.burned_identity` over K-ROOT, K-WIT, K-ACT, the registry digest and the genesis digest | `BURNED_REHEARSAL_IDENTITY` if any matches (tested) |
| release provenance | `aee323e…`, manifest `1d578ca7…` | PR-1A |

`assemble` returns a `LILITH_PR3_OFFHOST_MATERIAL_CANDIDATE` with the exact `offHostMaterial` verifier fields
(`registerSha256` = SHA-256 of the authorization register bytes, the fixture precedent; `kActPublicationSha256` =
SHA-256 of the canonical publication bytes, as `pr1_acceptance` E-18 recomputes), `authorizationIds = []`,
`burnedOrdinals = []`, per-source digests, and a domain-separated candidate digest; `ownerConfirmed` and
`pr3FullMaterialAccepted` are always false. `package_input(inputs, confirmation, …)` **assembles the candidate
itself** (it never accepts an assembled object) and emits `status=PRESENT` only for `OWNER_RETAINED_PUBLIC_BYTES`
with a `LILITH_PR3_MATERIAL_OWNER_CONFIRMATION` naming the exact candidate digest **and** established by the trust's
`accepted_candidates` (§2a; OD-M12-4). `offhost_reproduction(material, package)` is the owner-side RR-38 B
comparison: every value the package evidence shows (pin and genesis, registry head, K-WIT, K-ACT publication,
release, the bound register) must equal the material, and the package dark flags must be false.

## 4. Readiness inputs: `mb12_readiness_inputs`

`build(build_inputs, environment=…, trust=…)` produces the closed `LILITH_PR1_VERIFIER_INPUTS` document (exactly
the fields `lilith_authority_root.verifier.parse_verifier_inputs` accepts; the M-B11 `ownerInputs`) inside one
`LILITH_MB12_READINESS_INPUT_ENVELOPE` (JCS + one LF), with `inputsSha256` = SHA-256(JCS(document)) and a
provenance block. It is deterministic (byte-identical on rebuild).

| Input | Rule |
| --- | --- |
| window | `notBefore` ≥ the trust's freshness cutoff (`WINDOW_BEFORE_FRESHNESS_CUTOFF`; DEV: OD-M12-3, undecided → `FRESHNESS_CUTOFF_UNDECIDED`); every `observedAt` inside the window (`INPUT_STALE`) |
| release | `releaseSha` and attested manifest = the pins; reviewed runtime digests optional, hex only |
| first-preflight CURRENT | the root observation of the pinned slot (`6a61c350…`, mode `0600`, decimal identity strings), with its own `observedAt` and evidence digest; never decrypted |
| K-ACT / K-WIT publications | the exact recorded bytes (file SHA-256, B3, K-WIT fingerprint) |
| proofs | `{transcript (bytes), exitCode, observedAt, evidenceSha256}` per name; see below |
| activation | stdout exactly one line, exit 1, equal to the complete host line `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false`; passed **verbatim** (§8) |
| `pr2` | `{inventory, acceptance}` → `mb12_pr2_inventory.package_input` with the trust (refusals prefixed `PR2_`); the inventory window must also start inside the build window; or `null` |
| `pr3` | `{inputs, confirmation}` → `mb12_pr3_material.package_input` with the trust (refusals prefixed `PR3_`); or `null` |

There is no `snapshotInventory` or `offHostMaterial` build field: package objects are never accepted.

**Proof admission** (`admit_proof`). The caller supplies the producer's transcript **bytes** and exit status; the
builder never takes a result, digest, producer or detail from the caller. For each name: the producer must be mapped
(§6; unmapped → `PROOF_PRODUCER_UNMAPPED`); the producer script on disk must equal its pinned SHA-256
(`PRODUCER_SCRIPT_NOT_PINNED`); the bytes must satisfy that producer's terminal contract (`TRANSCRIPT_CONTRACT`):

| Producer | PASS contract | FAIL contract |
| --- | --- | --- |
| `scripts/authority_custody_denial_proof.py` `P1B-12` (`f4e39c81…`) | exit 0 and the bytes equal **the complete expected PASS transcript rebuilt from the script's own `ROWS` and `NAMESPACE_ROWS`** (every `DENIED:` line in order, the 9 signer-namespace lines, then `AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-12`) | exit 1, at least one `FAIL: ` line, final `AUTHORITY_CUSTODY_DENIAL_PROOF=FAIL phase=P1B-12` |
| `scripts/deployer_authority_boundary_proof.sh` DR-5 (`9b569f9b…`) | exit 0, penultimate `PR1_AUTHORITY_BOUNDARY maturity=<m>` (→ `detail`), final `AUTHORITY_BOUNDARY_PROOF=PASS maturity=<l>` | exit 1, the same two final lines with `FAIL` |
| `scripts/verify_broker_dev_current_incarnation.py preservation` (`b90ed6ef…`) | one compact sorted JSON line, `operation=READ_ONLY_BROKER_PRESERVATION`, `BROKER_PRESERVATION=PASS`, `failures=[]`, exit 0 | the same with `FAIL`, nonempty `failures`, exit 2 |

The result and `transcriptSha256` are derived from the bytes, and the digest must be in the trust's accepted
transcripts for that name (§2a; `PROOF_PROVENANCE_NOT_ESTABLISHED`). A verified FAIL passes through as FAIL. A
hand-written transcript that only ends in `PASS` fails the contract.

`read_envelope` (host side) reads at most 256 KiB from stdin, requires SHA-256(bytes) = the reviewed digest given
on the command line, strict JSON without duplicate keys, the canonical byte form (one LF, no CR, no BOM), the exact
envelope fields, the environment, and `inputsSha256`; a non-canonical number is refused, never a crash. It returns the
document for in-process use (as `mb11_signer_verifier.readiness_pair` takes `ownerInputs`); `provenance` is covered by
the envelope digest but is informational only. No file is written; the installed root CLI is not used, because
`lilith_authority_root.cli._document` reads only a regular file (`read_regular`), so stdin delivery cannot reach it
without a release change (OD-M11-15). `verify-envelope` only validates; it evaluates nothing.

## 5. What the release verifier actually returns (synthetic, end to end)

Over the synthetic `Pr1Host` (environment `test`, the real `lilith_authority_root.verifier.evaluate`, HELD exact,
HEALTH captured), with TEST trust standing in for merged pins and only honestly buildable inputs:

| Inputs | Root E-17 readiness | Package | Failing checks |
| --- | --- | --- | --- |
| the four mapped proofs (contract-verified, pinned); real activation line; PR-2 / PR-3 `null` | READY | NOT_READY | E-07 `PROOF_MISSING:OS_DENIAL`, E-18 `OFFHOST_MATERIAL_UNAVAILABLE`, E-19 `ACTIVATION_NOT_DARK`, E-20 `SNAPSHOT_INVENTORY_ABSENT_PR2`, E-21 `OFFHOST_REGISTER_ABSENT_PR3`, E-22 `PROOF_MISSING:SECRET_HYGIENE`, E-23 `PROOF_MISSING:PRESERVATION_SET` |
| as above + established PR-2 + established PR-3 | READY | NOT_READY | E-07, E-19, E-22, E-23 (E-18, E-20, E-21 PASS; RR-38 B reproduction empty) |

This corrects the expectation in the [M-B11 design record](slice-15b2b-b1b3e-mb11-signer-start-design.md) §4 row C
("package fails exactly E18, E20, E21"): that row used the 3-field activation constant and fixture proofs for all
seven names. With observed inputs the package also fails E-07, E-19, E-22 and E-23. Package READY is therefore not
reachable today by any honest input; it needs §8 (a release change), the three missing producers (§6) and the §2a
pins.

## 6. The seven proof names (OD-M11-14, PROPOSED mapping)

| Proof name | Package check | Proposed producer | Status |
| --- | --- | --- | --- |
| `SIGNER_DENIAL` | E-07 | `scripts/authority_custody_denial_proof.py` phase `P1B-12` (fixed `runuser … test` rows + the signer mount-namespace rows) | producer and exact transcript contract exist; **the 12 P1B-12 rows and the 9 namespace rows are NOT PERFORMED** (need the running signer; no partial phase); provenance pin empty |
| `OS_DENIAL` | E-07 | **none** | **GAP**: E-07 names "unit property + mount-namespace probe"; no tool emits an `OS_DENIAL` result, and whether it is the namespace half of the P1B-12 transcript or a separate unit-property proof is undecided |
| `DEPLOYER_DENIAL` | E-08 (`detail = maturity=P1A-9`) | `scripts/deployer_authority_boundary_proof.sh` (DR-5 on a real routine deployment) | producer and terminal contract exist; provenance pin empty |
| `BROKER_DENIAL` | E-09 | `scripts/authority_custody_denial_proof.py` phase `P1B-12` (the broker is an `OUTSIDER` in every row) | the same transcript as `SIGNER_DENIAL`; NOT PERFORMED |
| `BROKER_PRESERVATION` | E-09 | `scripts/verify_broker_dev_current_incarnation.py` (`preservation`) | producer and exact contract exist; provenance pin empty |
| `SECRET_HYGIENE` | E-22 | **none** | **GAP**: ceremony records report scans (for example M-B2 "secret scan 0"), but no tool produces a bindable E-22 result over journal, transcript and publication scans for every PR-1B ceremony |
| `PRESERVATION_SET` | E-23 | **none** | **GAP**: the host POST preservation readers cover parts (broker, units), but no tool emits a B1b-3d §23 preservation-set result (Stage III, broker, API unit) as one transcript |

> **Update (PR-B2).** `OS_DENIAL`, `SECRET_HYGIENE` and `PRESERVATION_SET` now have producers with exact
> transcript contracts ([PR-B2 record](slice-15b2b-b1b3e-mb12-prb2-proof-producers.md)); the gaps above are closed
> in source only. Nothing was run on DEV and every DEV provenance pin stays empty.

The DR-5 contract checks only the two final lines; the full DR-5 row set is judged by the accepted DR-5 target tools
(`mb10_dr5_target.py` / `mb11_dr5_target.py`), and binding that judgement into E-08 is part of the provenance pin.

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
  (`services/authority-dev/tests/pr1s_fixtures.py` `verifier_inputs`) and `test_pr1s_runtime_wiring.py`
  (`ACTIVATION_DARK_LINE` constant pin) use the 3-field form, which is why no test caught it.
- **Not fixed here.** `pr1_acceptance.py` is pinned (`e0928854…`) and shipped in release `aee323e`; a fix is a
  release change. The builder refuses to rewrite the line, and `test_known_defect_e19_rejects_the_complete_host_line`
  pins the defect so that a fix must update it.
- **Smallest correction (OD-M12-5).** Set `ACTIVATION_DARK_LINE = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT
  advisoryConfigEnabled=false"` and keep exact equality. **Regression tests:** that full line → PASS; the bare 3-field
  form, `advisoryConfigEnabled=true`, any other reason, `ACTIVATION=ACCEPTED …`, a trailing space, a CR and a second
  line → FAIL; update the constant pin at `test_pr1s_runtime_wiring.py` and this slice's known-defect test (the
  `pr1s_fixtures` input follows the constant); a source-text test anchoring the printed format of
  `lilith_activation_verify.py`; re-pin `SHARED_HASHES`; the §5 synthetic end-to-end then fails only E-07, E-22, E-23.
- **Release-update impact (not performed).** The witness and the signer both run from the same release tree
  (`WorkingDirectory=/opt/lilith-authority-dev/current`, `ExecStart=/opt/lilith-authority-dev/current/venv/bin/python
  …`). An RR-25 upgrade stages the new release, flips `current`, and removes `releases/aee323e`. That does not restart
  the running M-B10 witness by itself, but it leaves it running deleted code and invalidates every `aee323e` pin
  (W10 / W11 verifiers, `RELEASE_CWD`, the DR-5 targets, the restart-boundary tool), so W10_1 would need new
  phase-bound targets. Any witness restart is a new incarnation (the accepted B3 InvocationID `5136ea7a…` ends) and a
  new K-WIT load (`LoadCredentialEncrypted=recovery-witness-signing-key:…`), which is a custody event needing its own
  design and go. Custody state is outside `/opt` (CURRENT, the credstore, the hold store, the witness state and
  chain, the ledger) and the installer never touches CURRENT. A signer running across a release change would need a
  restart (another K-ACT load). So any E-19 release update belongs **before** M-B11, ideally bundled with the other
  release-side items (stdin input for OD-M11-15; E-25 … E-28 if OD-M11-13 takes the release route), as its own
  owner-authorized slice. Nothing here upgrades, deploys or changes `current`.

## 9. Sequencing: E-17 readiness versus package READY (OD-M11-12, PROPOSED)

Canonical wording reviewed: preflight §20 (OWNER-ACCEPTED) orders `INITIAL_CUSTODY / HELD -> HOLD_RELEASE_ELIGIBILITY
-> PR-3 full acceptance / register material -> explicit owner acceptance -> RELEASED`, and says "the signer's first
start (for B4) follows HELD and precedes eligibility"; its table requires PR-2 before RELEASED (E-20) and PR-3 full
material before RELEASED (E-12, E-21); §27 M-B12 passes on "eligibility READY; package digest"; §28 places PR-3 full
material after P1B-12 and requires E-1 … E-24 at P1B-13.

| Evaluation | What it is | Needs the running signer? |
| --- | --- | --- |
| root `HOLD_RELEASE_ELIGIBILITY` (= package E-17) | `successor_readiness` over the complete hold observation and the captured HEALTH; READY proves the HELD binding (B1 = … = B4, B5, B6) | **yes** (B4 HEALTH) |
| PR-1 package (E-01 … E-24) | `pr1_acceptance`: E-17 plus PR-2, PR-3, the proofs, activation, nonclaims; the RR-38 package digest | **yes**: E-03, E-06, E-17 (B4), E-07 / E-09 (the P1B-12 namespace probe needs the signer's MainPID) |

**Cycle check.** Requiring package READY before START_SIGNER is a dependency cycle: E-03, E-06 and E-17 need the
loaded K-ACT's HEALTH, and E-07 / E-09 need the running signer's mount namespace. A synthetic observation
(`test_stopped_signer_synthetic_observation_is_not_an_entry_gate`) shows that with HEALTH unavailable and fixture
inputs, exactly E-03, E-06 (`LOADED_KEY_BINDING:BINDING_INPUT_MISSING`) and E-17 (`READINESS_NOT_READY`) fail. That set
is **not** a proven real stopped-signer set: it used fixture proofs for all seven names and the 3-field activation
line; with real inputs E-07, E-09, E-19, E-22 and E-23 would also differ. It is recorded as an observation, and no
entry gate is built on it.

Option A (E-17 READY suffices for M-B12) has no cycle but lets M-B12 "pass" with the package NOT_READY. Option B
(package READY at M-B12) has no cycle only if it gates M-B12, never START_SIGNER. Recommended wording (PROPOSED; not
applied; §20 / §28 not amended):

> **OD-M11-12 (PROPOSED).**
> (a) **START_SIGNER** remains blocked until, all separately: the P1B-10R restart / reactivation boundary is installed
> and verified effective (OD-M11-11); the signer-independent M-B12 prerequisites are prepared and established by
> merged owner records — a fresh PR-2 inventory accepted by digest (E-20) under the OD-M12-3 cutoff, the PR-3 full
> material confirmed by digest (E-21), the E-19 judge correction (OD-M12-5) and producers for `OS_DENIAL`,
> `SECRET_HYGIENE` and `PRESERVATION_SET` with an accepted OD-M11-14 mapping; and the owner gives a separate start
> authorization. Pre-start checks cover only legitimate stopped-signer prerequisites; no pre-start check requires a
> signer-dependent result (E-03, E-06, E-07 / E-09 namespace rows, E-17), and no exact stopped-signer failure set is
> an entry gate until it is proven on canonical inputs and separately accepted.
> (b) **M-B12 PASS** means the PR-1 package (E-01 … E-24) is READY over one complete hold observation and the
> captured HEALTH bound to the observed InvocationID, with every input established (§2a). E-17 READY with the package
> NOT_READY is recorded verbatim as `M-B12 NOT PASSED`; it never counts as M-B12 PASS, and M-B13 does not start. No
> check is reinterpreted, defaulted or omitted.
> (c) Placing PR-2 and PR-3 full material before START_SIGNER reorders the OWNER-ACCEPTED §20 / §28 sequence (every
> "must precede" relation still holds) and needs its own owner amendment.

## 10. New proposals (PROPOSED, none accepted)

| # | Proposal | Blocks |
| --- | --- | --- |
| OD-M12-1 | accept the three tools of §1 as the PR-2 / PR-3 / readiness-input tooling (pins above), with their input schemas and transcript contracts | tooling use in any live step |
| OD-M12-2 | E-20 `recordSha256` = the domain-separated inventory digest, and the owner PR-2 acceptance names that digest | PR-2 package input |
| OD-M12-3 | the DEV freshness cutoff `DEV_FRESHNESS_NOT_BEFORE` (for example the M-B12 sequence start) | every DEV PR-2 package input and every DEV build |
| OD-M12-4 | the PR-3 owner confirmation by candidate digest as the E-21 / E-18 owner act, with `registerSha256` = SHA-256 of the authorization register bytes | PR-3 package input |
| OD-M12-5 | the E-19 release fix of §8 (scope, new release, re-pin, before M-B11) | package READY |
| OD-M12-6 | the authenticity binding of §2a: merged-record pins (current), or a signed owner act / signed producer output | every DEV package input |

## 11. Test results

- `services/owner-memory-control/tests/test_b1b3e_mb12_prb1_prerequisites.py`: 42 tests, OK (WSL Ubuntu-24.04,
  `PYTHONPATH=~/l1deps:…`, as for the PR-1S suites; the synthetic-host tests are POSIX-only).
- Full suites and `scripts/validate_repository.py`: `services/owner-memory-control/tests` 1578 tests OK (15 skipped, environmental);
  `services/authority-dev/tests` 241 OK; `scripts/test_deployer_authority_boundary_proof.py` 36 OK (same WSL
  recipe, as root); `python scripts/validate_repository.py` passed (249 Markdown files).

## 12. Remaining work and recommended next slice

Remaining before a live M-B12: OD-M11-12 and its §20 / §28 amendment; OD-M11-13 (E-25 … E-28); OD-M11-14 and the
three missing producers; OD-M11-15 (stdin wiring into the W11 / M-B12 host run); OD-M12-3 and OD-M12-6 (cutoff and
authenticity binding); the §8 release fix; a fresh live PR-2 collection and its owner record; owner-retained PR-3
bytes and their confirmation record; the deferred P1B-12 denial rows and namespace rows (NOT PERFORMED); and,
upstream, the parked P1B-10R installation and the M-B11 start.

Recommended next engineering slice (PR-B2, repository only, not started): the three missing proof producers as fixed
root transcripts in the `authority_custody_denial_proof.py` style, each with an exact transcript contract in the
builder, plus the stdin input path for the W11 / M-B12 host run using `read_envelope`. The §8 E-19 fix should be its
own release-change slice (OD-M12-5).

## 13. State

```text
M-B12 PR-B1 PREREQUISITE TOOLING = REPOSITORY ONLY, CORRECTED FOR OWNER RE-REVIEW
PR-2 FRESH INVENTORY = NOT COLLECTED;  PR-2 ACCEPTANCE (E-20) = NONE;  DEV_ACCEPTED_INVENTORIES = {}
PR-3 FULL MATERIAL (E-21) = NOT CLAIMED;  OWNER CONFIRMATION = NONE;  DEV_ACCEPTED_CANDIDATES = {}
PROOF PROVENANCE = NOT ESTABLISHED;  DEV_ACCEPTED_PROOF_TRANSCRIPTS = {}
DEV FRESHNESS CUTOFF (OD-M12-3) = UNDECIDED  ->  EVERY DEV PACKAGE INPUT / BUILD REFUSED
E-19 RELEASE JUDGE DEFECT = RECORDED, NOT FIXED;  RELEASE aee323e / current / WITNESS INCARNATION = UNCHANGED
OS_DENIAL / SECRET_HYGIENE / PRESERVATION_SET PRODUCERS = MISSING
P1B-12 DEFERRED DENIAL ROWS (12) AND SIGNER-NAMESPACE ROWS (9) = NOT PERFORMED
E-25 … E-28 = NOT BOUND
OD-M11-12 … OD-M11-15, OD-M12-1 … OD-M12-6 = PROPOSED;  §20 / §28 = NOT AMENDED
P1B-10R INSTALL = NOT PERFORMED;  SIGNER START / K-ACT LOAD = NOT AUTHORIZED
REGISTRY EFFECTIVE = NO;  AUTHORITY ACTIVE = NO;  FIRST MEMORY / PROD = NOT AUTHORIZED
```

## 14. PR #186 review corrections (reviewed head `64df007`, owner decision CHANGES REQUIRED)

Each blocker was confirmed by a synthetic probe against `64df007` (the forged input was ACCEPTED) and is now refused;
the regression test uses the same input.

| # | Finding at `64df007` | Now | Regression test |
| --- | --- | --- | --- |
| 1 | the builder accepted a hand-written `snapshotInventory` (`status=ACCEPTED`, arbitrary `recordSha256`) — the real verifier then gave E-20 PASS — and copied `offHostMaterial` without confirmation; a caller-made acceptance / confirmation was treated as an owner decision | no package-object build fields; `pr2` / `pr3` go through `package_input`; acceptance / confirmation must be established by a pin (§2a) | `test_blocker1_package_objects_are_not_build_inputs`, `test_blocker1_unestablished_acceptance_and_confirmation_are_refused`, `ForgeryPr2Tests.test_blocker1_a_caller_made_acceptance_is_not_established`, `Pr3MaterialTests.test_blocker1_a_caller_made_confirmation_is_not_established` |
| 2 | a proof was admitted on a producer-name string and an arbitrary transcript digest | transcript bytes only; pinned producer script; exact terminal contract (custody denial: the complete expected transcript); derived result and digest; provenance pin | `test_blocker2_self_asserted_proofs_are_refused`, `test_blocker2_custody_transcript_is_rebuilt_from_the_pinned_script` |
| 3 | `package_input(not_before=None)` skipped freshness; `expected_keys=None` skipped key identity | a complete trust is required (`TRUST_REQUIRED` / `TRUST_MALFORMED`); DEV trust is pinned and not overridable | `test_blocker3_not_before_and_expected_keys_are_required`, `test_blocker3_dev_trust_is_pinned_and_not_overridable` |
| 4 | `ADMIN_ACTIVITY_CREATE_CALLS` count 3 with zero artefacts classified `NO_SNAPSHOTS` and was ACCEPTED | `UNKNOWN_PROVENANCE` for every key; classification FAIL | `test_blocker4_admin_create_calls_without_artefacts_are_unknown_provenance` |
| 5 | a caller window 2016 → 2036 admitted 2017 evidence | the window's lower bound is the trust cutoff; DEV cutoff undecided → refused | `test_blocker5_caller_window_cannot_reach_before_the_cutoff`, `ForgeryPr2Tests.test_blocker5_inventory_before_the_accepted_cutoff_is_stale`, `test_dev_builds_are_refused_until_the_owner_pins_exist` |
| minor | an empty-material artefact classified `SAFE_RETAINED_CIPHERTEXT` | refused (`INVENTORY_ARTEFACT_MATERIAL_EMPTY`) | `test_minor_empty_material_is_refused` |

## 15. Addendum (2026-10-17): OD-M12-1 and OD-M12-2 accepted; one E-20 inventory collected and classified

Earlier sections keep their historical meaning. This addendum supersedes the §10 / §13 status of OD-M12-1 and
OD-M12-2 only. It is authenticated as an owner record once reviewed and merged.

**OD-M12-1 ACCEPTED (owner, 2026-10-17).** The pinned M-B12 prerequisite tooling is accepted as designed, with its
schemas, producer contracts, trust boundaries and fail-closed behaviour unchanged: `mb12_pr2_inventory.py`
(`49d46b9ca166bae853653300cdd174d2b7ddb0025e72a80123b408cbc7055008`), `mb12_pr3_material.py`
(`cac0634bd15fff548822cead4a1bc1e587b015f0f668230365886f1200cc0774`) and `mb12_readiness_inputs.py`
(`74c2af17248abc56a15f9d4695b62480a1c783835f368128228aea195f91002c`), at main `3c01e243`. This accepts no particular
PR-2 inventory, PR-3 material or readiness package.

**OD-M12-2 ACCEPTED (owner, 2026-10-17).** The E-20 inventory identity is
`recordSha256 = SHA-256("LILITH_PR2_SNAPSHOT_INVENTORY_V1\0" ‖ JCS(inventory))` (`mb12_pr2_inventory.inventory_digest`,
unchanged). The owner PR-2 acceptance must name that exact digest.

### 15.1 E-20 collection (one owner-authorized provider-only batch)

The historical PR-2 collector (`cloud_collect.sh`, `e04ff9c3…`, sealed in the 2026-09-29 PR-2 revalidation evidence,
`SHA256SUMS` `67eb9a16…`) was reused with exactly two changes: the output directory and the Admin Activity start
`2026-10-14T18:27:00Z` (OD-M12-3). An independent static preflight passed (read-only verbs only, closed stdin, no host
transport, project `lilith-agent-260823-27389`). One run, 2026-10-17T09:38:16Z–09:44:11Z: 31 read-only provider calls
(describe / list / get-iam-policy / Admin Activity read), every stderr empty, no DEV host contact. Evidence
`lilith-mb12-e20-pr2-3c01e24`, `SHA256SUMS` `1b317f81daa0831c64012e1f4d25562ea7b586dae7080d9d2da6e1bb099dd894` (provider
dumps stay in the private evidence directory).

| Kind | Source listing | Count | Complete |
| --- | --- | --- | --- |
| `DISK_SNAPSHOTS` | `compute snapshots list` | 0 | yes |
| `INSTANT_SNAPSHOTS` | `compute instant-snapshots list` | 0 | yes |
| `IMAGES` | `compute images list --no-standard-images` | 0 | yes |
| `MACHINE_IMAGES` | `compute machine-images list` | 0 | yes |
| `SNAPSHOT_SCHEDULES` | `compute resource-policies list` | 0 | yes |
| `BACKUP_DR` | enabled services (`backupdr.googleapis.com` not enabled) | 0 | yes |
| `BUCKETS` | `storage buckets list` | 0 | yes |
| `ADMIN_ACTIVITY_CREATE_CALLS` | Admin Activity since the cutoff (108 entries, all `iam.serviceAccounts.actAs`) | 0 | yes |

The whole-life compute Admin Activity listing is byte-identical to 2026-09-29 and has no snapshot, image or
machine-image create call. Of the other projects visible to the owner account, only `au4-vault` has compute enabled,
with no snapshot, image, machine image or instant snapshot.

### 15.2 Local inventory and classification (classification ≠ acceptance)

One `LILITH_PR2_SNAPSHOT_INVENTORY` V1 document (`LIVE_OBSERVATION`, `dev`) was assembled from the sealed listings only:
window `2026-10-17T09:38:16Z`–`09:44:11Z`; keys K-ACT `dd13a1fb…` and K-WIT `5d778701…` sealed under the host key (no
public identity); no artefacts (every listing is empty); carried debt `C-4` (role K-WIT, `recordSha256` = SHA-256 of
`slice-15b2b-b1b3e-mb2-kwit-completion.md` at `3c01e243`, `8ee13904c9d7c306502cf6625c064636c2fda90594a90052ac1c90f6aaf7497f`);
`privateEvidenceSha256` = the collection `SHA256SUMS` digest. The pinned `classify` under the DEV trust values gives:

```text
classification = PASS;  reasons = []
inventoryDigest = 61d9268613c13354c0184a30909a21f4cd2f8db20424bcb10f6f2e51168d46cf
keyClasses = K_ACT NO_SNAPSHOTS, K_WIT NO_SNAPSHOTS, HOST_KEY NO_SNAPSHOTS;  namedDebts = [C-4]
```

Limitations: this is a provider listing. It establishes no host-level custody state and no provenance beyond the
listed kinds, scope and Admin Activity retention (`wholeHostRollbackProtected: false`). `BACKUP_DR` is shown absent by
service enablement, not by a vault listing. Inventory files: `inventory\` (`SHA256SUMS`
`a430504f28dc5ddefc983eaa30997cb4a7b40325e4517b6031b57f4d32c43ee1`).

**Not done:** E-20 is NOT accepted. `DEV_ACCEPTED_INVENTORIES` stays `{}`. Admission needs a separate owner PR-2
acceptance naming digest `61d92686…` (dated at or after `2026-10-17T09:44:11Z`), then a merged record pinning that
digest to the acceptance record SHA-256. The inventory is fresh only up to its window end.

```text
OD-M12-1 = ACCEPTED;  OD-M12-2 = ACCEPTED;  OD-M12-3 = ACCEPTED;  OD-M12-6 = ACCEPTED (operator record §15 / §16)
E-20 INVENTORY = CLASSIFIED PASS (61d92686…), NOT OWNER-ACCEPTED;  DEV_ACCEPTED_INVENTORIES = {}
OD-M12-4 / OD-M12-7 / OD-M12-8 = PROPOSED;  E-22 = BLOCKED (JOURNAL_SECRET_SCAN=FAIL authoritative)
M-B12 = NOT PASSED;  CUSTODY = HELD;  K-ACT LOAD COUNT = 1
```
