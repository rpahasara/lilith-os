# Slice 15B2b-B1b-3e — Rotation, Revocation, Restore, and Recovery Source Contracts

Status:

- **DESIGN ACCEPTED** ([design record](slice-15b2b-b1b3e-rotation-revocation-recovery.md),
  merged at protected main `39f801a06bb4fd37585526e568ce7c3f96abfaba`)
- **SOURCE IMPLEMENTED / TEST PROVEN** (TEST-only contracts and pure
  verifiers; synthetic keys only)
- **LIVE REHEARSAL NOT AUTHORIZED**
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**

This is the first source phase (B1b-3e-S) of the design record. It adds pure,
deterministic contracts and verifiers, all exercised only by synthetic
TEST-only tests. The phase does **not** do any of the following:

- declare any live B1b-3e completion;
- install anything;
- contact DEV or PROD;
- touch a real key, credential, registry, witness, or ledger.

It does **not** mark any of these as complete: B1b-3, Level 2 isolation,
real owner authority, First Memory, Privacy custody, or Stage III.

## 1. Location and delivery impact

| Path | Role |
| --- | --- |
| `services/owner-memory-control/lilith_owner_memory/rotation_contracts.py` | **new.** Holds all B1b-3e contracts and pure verifiers: the registry digest, the single-current-key rule, `verify_registry_succession`, both K-ROOT execution authorizations, `RecoveryWitnessV2` with its chain and head verification, the witness execution planners, the authority recovery ledger position check, the loaded-key binding, and the rotation state machine |
| `services/owner-memory-control/lilith_authority_signer/synthetic_witness_v2.py` | **new, TEST-only.** Holds the `RecoveryWitnessV2` writer (`SyntheticWitnessV2SignerV1`), the pre-witness `adopt_authorized_epoch` on the authority recovery ledger, and `observe_authority_recovery_ledger` |
| `services/owner-memory-control/tests/synthetic_b1b3e.py` | **new.** TEST_ONLY fixtures and the golden generator |
| `services/owner-memory-control/tests/test_b1b3e_rotation_recovery.py` | **new.** 84 tests |
| `services/owner-memory-control/tests/b1b3e_golden.json` | **new.** Golden vectors, SHA-256 pinned in the test |
| `docs/architecture/README.md` | one index row |

**Unchanged:**

- `authority_contracts.py`, `authority_verifier.py`, `recovery_contracts.py`,
  `recovery_admission.py`, and `synthetic_recovery_ledger.py`;
- B2a and the B1b-3b modules;
- every existing golden vector. Their SHA-256 pins are re-checked, and so are
  the authority-dev `SHARED_HASHES`;
- `services/core-api/**`, `services/memory-broker/**`,
  `services/authority-dev/**`, workflows, IAM, WIF, sudoers, and deployment
  helpers.

**Delivery.** Nothing is under `services/core-api/**`, so the PROD path filter
is not triggered. The broker file set is unchanged. The existing Core API CI
step already runs `unittest discover -s services/owner-memory-control/tests`.
No runtime package imports the new modules; a test enforces this, and it also
covers the authority-dev runtime package.

## 2. Terminology confirmed from current source

`AuthorityKeyRecordV1` (`KEY_RECORD_FIELDS`) carries `signingDomain` and
`evidenceTypes`. It has **no** `authorityDomain`. `authorityDomain` stays the
logical context field on evidence contracts only (`_COMMON_EVIDENCE_FIELDS`).
A test asserts all three facts, and no alias is introduced.

`ROUTINE` and `SUPERSEDED` verify identically in the B1b-3a verifier. A test
shows this, and the verifier is unchanged.

## 3. Reused contracts

| Reused | How |
| --- | --- |
| `AuthorityRegistryV1`, `AuthorityKeyRecordV1`, `TrustedRegistryRootV1`, `verify_authority_registry` | the authority state and its K-ROOT verification. The B1b-3e checks run on top of them |
| `registry_signing_bytes` / `REGISTRY_DOMAIN_SEPARATOR` | the registry digest is taken over exactly these bytes (§5) |
| `RecoveryEpochV1`, `compare_epochs` (`EQUAL` / `OLDER` / `NEWER` / `FORKED`), `ledger_epoch_id` | epoch encoding, ordering, and fork detection; unchanged |
| `TrustedWitnessAnchorV1`, the V1 witness reason taxonomy, `WITNESS_PROTOCOL` | reused by V2. V2 bumps `schemaVersion` to 2, so neither version parses as the other (tested) |
| V1 witness succession rules (epoch, ledger position, time) | inherited verbatim by `witness_v2_succession_reason` |
| `AuthorityLedgerStateV1`, its unchanged journal replay, and `quarantine_pre_recovery` | the authority recovery ledger. B1b-3e appends one `ADVANCE_EPOCH` record through the public `from_log` replay |
| B1b-3c readiness reason names | reused by `authority_ledger_position_reason` (a subset is asserted) |
| `RECOVERY_REASONS` | mirrored as `EPOCH_ADVANCE_REASONS`. Equality is asserted; there is no import, because the contract package never imports the signer package |
| B1b-3d L2 keygen publication and L1 `HEALTH` shapes | parsed as B3 and B4. They are cross-checked against the real authority-dev `publication()` and `DevAuthoritySignerCoreV1.health()` (§10) |

## 4. State owners

| State | Story | Owner in this phase |
| --- | --- | --- |
| Registry generations, `EpochAdvanceAuthorizationV1`, `RegistryHeadAdvanceAuthorizationV1` | 1: authority | K-ROOT. In tests, the B1b-3a synthetic root |
| `RecoveryWitnessV2` chain: epoch, registry head, ledger position, consumed authorization IDs | 2: freshness | the witness writer (TEST) |
| Authority recovery ledger (`AuthorityLedgerStateV1`) | 4: storage/observation | the authority signer boundary (TEST model only; the real `/var/lib/lilith-authority-dev/authority_ledger.db` is not touched) |
| Readiness, the loaded-key binding result, the rotation assessment | 3: issuance readiness | stateless pure verifiers |
| Memory-broker ledgers (`owner_control.db`, `synthetic_evidence.db`), L04 | — | **not touched.** A static test forbids any reference to them in the signer module's code |

No new service, identity, socket, or state owner is introduced.

## 5. Registry digest

```text
registry_digest(R) = sha256( "LILITH_AUTHORITY_REGISTRY_V1\0" || RFC8785-JCS(R minus "signature") )
```

- These are exactly the bytes K-ROOT signs.
- The digest covers the complete canonical registry content: protocol,
  schema, environment, version, epoch, policy, root key ID, `issuedAt`, and
  every key record.
- It excludes only the signature and the transport representation. Pretty
  printing and key order do not matter (tested).
- It is domain-separated by the existing registry separator, and no second
  representation is invented.
- It equals the frozen B1b-3a golden `registrySigningDigest` (tested).

## 6. New contracts and domain separators

### Domain separators

The three separators are frozen. They are distinct from all ten earlier
separators (tested):

- `LILITH_EPOCH_ADVANCE_AUTHORIZATION_V1\x00`
- `LILITH_REGISTRY_HEAD_ADVANCE_AUTHORIZATION_V1\x00`
- `LILITH_RECOVERY_WITNESS_V2\x00`

### `EpochAdvanceAuthorizationV1` (RR-2)

Fields:

- `protocol` (`LILITH_EPOCH_ADVANCE_AUTHORIZATION`) and `schemaVersion` (1);
- `authorizationId` and `nonce` (128-bit lowercase hex);
- `environment`, and `reason` (one of `EPOCH_ADVANCE_REASONS`);
- `priorRecoveryEpoch` and `successorRecoveryEpoch`;
- `targetRegistryVersion` and `targetRegistryDigest`;
- `expectedPriorWitnessVersion` and `expectedPriorWitnessDigest`;
- `registryRootKeyId`, `issuedAt`, `notAfter`, and `signature`.

Contract rules:

- the successor counter is prior + 1;
- the same counter with a different random is `EPOCH_FORKED`, never a
  succession;
- the successor random differs from the prior random;
- `notAfter > issuedAt`;
- every field except `signature` is signed;
- the signature and root are verified before any content is parsed.

### `RegistryHeadAdvanceAuthorizationV1` (RR-15)

Fields:

- `protocol` (`LILITH_REGISTRY_HEAD_ADVANCE_AUTHORIZATION`) and
  `schemaVersion` (1);
- `authorizationId`, `nonce`, `environment`;
- `reason`, one of `HEAD_ADVANCE_REASONS` (below);
- `recoveryEpoch`;
- `priorRegistryVersion` and `priorRegistryDigest`;
- `targetRegistryVersion` and `targetRegistryDigest`;
- `registryRootKeyId`, `issuedAt`, `notAfter`, and `signature`.

`HEAD_ADVANCE_REASONS` is exactly {`SUCCESSOR_ROTATION`,
`ADMINISTRATIVE_REVOCATION`, `COMPROMISE_MARKING`}. This closed set is a
choice made in this source phase; the design left it to source.

Contract rules:

- `target == prior + 1`;
- a same-version target is `SAME_VERSION_ADVANCE`;
- a gap is `TARGET_NOT_CONTIGUOUS`.

The two authorizations are distinct contracts with distinct field sets and
separators. Neither verifies as the other (tested), and there is no generic
envelope.

## 7. `RecoveryWitnessV2` (RR-4)

**Fields:**

- `protocol` (`LILITH_RECOVERY_WITNESS`), `schemaVersion` (2), `environment`;
- `witnessVersion` and `previousWitnessDigest`;
- `currentRecoveryEpoch`;
- `registryVersion` and `registryDigest`;
- `policyVersion`;
- `ledgerSequence` and `ledgerHead`;
- `consumedAuthorizationId`;
- `updatedAt`, `witnessKeyId`, and `signature`.

**Mapping from V1 (nothing silently renamed):**

- `ledgerSequence` / `ledgerHead` keep their V1 names and meaning: the
  authority recovery ledger's journal length and hash-chain head. The
  design's `authorityLedgerSequence` / `authorityLedgerHead` are these
  fields.
- V1 `minimumRegistryVersion` is replaced by the exact head
  `(registryVersion, registryDigest)`.
  - The inherited floor rule becomes
    `trusted_minimum_registry_version = registryVersion`
    (`minimum_registry_version` property; `witness_v2_authority_context`).
  - Verification against the head additionally requires the digest
    (`verify_registry_at_witness_head`).
- `consumedAuthorizationId` is new. It names the authorization whose
  execution produced this witness. It is null for the genesis witness and for
  a ledger-only advance.

**Succession rules** (`witness_v2_succession_reason`, a closed ordered set of
15 reasons):

- The environment and witness key do not change.
- The version is +1, and the chain digest links to the predecessor.
- **Epoch.** It stays equal or moves to counter + 1. `OLDER` and `FORKED`
  are regressions.
- **Registry head.**
  - It never regresses.
  - The same version with a different digest is `WITNESS_REGISTRY_FORK`.
  - The same version with the same digest is allowed as "no head change",
    subject to the other rules.
  - Versions are contiguous: `WITNESS_REGISTRY_GAP`.
  - An epoch advance always moves the head by exactly one.
- **Policy.** It changes only together with a head change.
- **Authorization.** A head or epoch change must name a consumed
  authorization. A ledger-only advance names none.
- **Ledger position and time.** The V1 rules apply unchanged. On an epoch
  advance the post-journal head must differ.

**Chain.** `verify_witness_v2_chain` verifies every document from genesis.
`witness_v2_chain_facts` then establishes three things:

- linearity;
- single use of each consumed ID (`CHAIN_AUTHORIZATION_REPLAYED`);
- the set of epoch randoms already seen.

**Execution.** The planners are pure. They produce the unsigned successor
only after every check passes, and the TEST writer signs only planner output.

- `plan_registry_head_advance` (RR-15) checks:
  1. the authorization verifies;
  2. the current head equals the authorized prior head exactly;
  3. the prior registry is the witnessed head;
  4. the authorization's epoch is the witness epoch;
  5. the target verifies under K-ROOT in that epoch;
  6. the target equals the authorization's version and digest;
  7. the target is contiguous;
  8. `verify_registry_succession(head → target)` passes;
  9. the authorization ID is unconsumed;
  10. `issuedAt ≤ updatedAt ≤ notAfter`.
- `plan_epoch_advance` (RR-2, C-4 order) checks all of the following.
  - Authorization and prior state:
    1. the authorization verifies;
    2. the expected prior witness version and digest match exactly;
    3. the prior epoch matches;
    4. the prior registry is the head.
  - Successor epoch and target registry:
    5. the successor random has never been seen in the chain;
    6. the target verifies under K-ROOT at the successor epoch;
    7. the target equals the authorization;
    8. the target is contiguous;
    9. the target is an additive successor;
    10. it has an issuance key.
  - Ledger adoption:
    11. the authority recovery ledger's last record is the `ADVANCE_EPOCH`
        adoption, naming this authorization ID, the successor epoch, the
        prior witness digest, and the target version;
    12. the post-journal head differs.
  - Replay and clock:
    13. the ID is unconsumed;
    14. the clock window holds.
- `plan_ledger_advance`: the sequence strictly advances, and nothing else
  changes.

**Replay prevention** does not rely on the clock. It rests on three things:

- the prior-witness or prior-head binding;
- the linear chain;
- the consumed-ID set.

Expiry is defence in depth only. Tests exercise replay well inside the clock
window.

`witness freshness != authority` and `witness head binding != registry
authority`. The witness key must be disjoint from the root and from every
authority key (`WITNESS_KEY_IS_AUTHORITY_KEY`). The witness signs no evidence,
registry, or authorization.

## 8. Registry succession (`verify_registry_succession`)

This is a pure function over two already-authenticated registries, with an
optional trusted prior head. The trusted head's owner is `RecoveryWitnessV2`.
Its reasons form a closed ordered set of 16.

It rejects:

- `SUCCESSION_MALFORMED`;
- `SUCCESSION_PREVIOUS_NOT_TRUSTED_HEAD`;
- a root or environment change;
- a version regression;
- a same-version fork (a different digest);
- no change (the same digest);
- a version gap;
- an `issuedAt` regression;
- an epoch that is neither equal nor counter + 1;
- a deleted historical record;
- a rewritten immutable record field: `signingDomain`, `evidenceTypes`,
  `environment`, `algorithm`, `publicKey`, `createdAt`, `notBefore`,
  `recoveryEpoch`, `policyVersion`, or `registryVersion`;
- a reopened lifecycle (resurrecting a retired or revoked key);
- a rewritten final lifecycle fact: `retiredAt`, `revokedAt`, the reason, or
  `compromisedSince`;
- a cleared compromise;
- a new record whose `registryVersion` is not the new version;
- a violation of the single-current-key scope.

**The only permitted later lifecycle change** is escalating `ROUTINE` or
`SUPERSEDED` to `COMPROMISED`, with `revokedAt` unchanged and
`compromisedSince` added.

**Honest note.** Under current contracts, `evidenceTypes` is fixed by
`signingDomain`: each domain has exactly one type. A type rewrite is therefore
always a domain rewrite, and `signingDomain` is reported first (tested).

The function verifies only the inputs it is given. It does **not** by itself
create durable fork or rollback protection.

## 9. Single current key (RR-3)

`current_issuance_keys`, `single_current_key_reason`, and
`select_current_issuance_key` enforce one rule: within one verified registry,
at most one **current issuance key** exists per `(signingDomain,
evidenceType)`. A verified registry already fixes the environment and
`recoveryEpoch`.

- **Current issuance key** means the K-ROOT-signed lifecycle is current
  (`retiredAt` and `revokedAt` are both null) in the registry's own epoch.
- `notBefore` is **not** used. A lifecycle-current key counts even before its
  `notBefore`, so two keys can never be issuance-current during an overlap
  (tested).
- `evidence.issuedAt` is never an input.
- A historical, superseded predecessor plus one current successor is
  accepted.
- Actor and Privacy are separate scopes.
- An invalid scope is `ISSUANCE_SCOPE_INVALID`.

The B1b-3a verifier is unchanged, and it still structurally accepts several
current keys. The rule is enforced at publication (succession), at witness
genesis, and in the rotation state machine.

## 10. Loaded-key / current-key binding (RR-14)

`verify_loaded_key_binding` is the pure verifier. It takes four inputs:

- **B1:** the single current key of the registry that verifies under K-ROOT
  **and** equals the fresh V2 head. The verifier reproduces this itself.
- **B2:** the root-observed hash of the unit-slot blob, with no decryption.
- **B3:** the keygen publication, in its exact L2 shape.
- **B4:** the signer `HEALTH` report, in its exact L1 shape.

It requires all of these:

- the publication fingerprint is consistent: `sha256(publicKey) ==
  publicKeySha256`;
- the key ID, `signingDomain`, `evidenceTypes`, and environment of B3 equal
  the B1 record;
- B3's `publicKey` equals B1's;
- B2 equals B3's `blobSha256`;
- the B4 credential is present;
- B4's `signingDomain` matches;
- B4's `publicKeySha256` equals B3's.

A missing input fails closed and names it (`B1_WITNESS`, `B1_REGISTRY`,
`B2_BLOB_HASH`, `B3_PUBLICATION`, `B4_HEALTH`).

A positive result reports `authorityGranted: false`. It lists B1–B3 as the
independent inputs and B4 as a signer claim. It also reports
`proofOfPossession: NOT_PERFORMED_RR14A_DEFERRED`.

A cross-check test uses the **real** authority-dev code, with synthetic bytes
only:

- `publication()` parses as B3;
- `credential._classify` on a TEST PKCS#8 key yields `sha256(raw public
  key)`, which re-confirms the RR-14a finding that `HEALTH` is derived from
  the loaded private material;
- `DevAuthoritySignerCoreV1.health()` has the same keys and passes as B4.

No real file or credential is read.

## 11. Rotation state machine (RR-10, §7.4)

The states are `P_ACTIVE → S_PROPOSED → S_PREPARED → S_AUTHORIZED →
S_PUBLISHED → S_ACTIVATED → S_CURRENT`. The predecessor reaches
`P_SUPERSEDED`: the merged design's name for the brief's "P_RETIRED". It
happens only together with `S_CURRENT`.

`evaluate_rotation` returns the highest state that the evidence
independently supports, and why the next state is not reached. Each state
requires every earlier one.

| State | Required evidence (verified here) | Not implied |
| --- | --- | --- |
| `P_ACTIVE` | the prior registry was a witnessed V2 head, and its single current key in scope is the predecessor | — |
| `S_PROPOSED` | owner intent recorded (unauthenticated intent; RR-13 deferred). Entering it also requires the local hold (`validate_rotation_transition`) | no authority |
| `S_PREPARED` | a valid successor publication (key ID, scope, environment, fingerprint) | cannot issue: the successor is unknown to the head (`KEY_UNKNOWN`, tested) |
| `S_AUTHORIZED` | **(A)** a K-ROOT-verified candidate that is contiguous and an additive successor, with the successor as the single current key matching the publication key and the predecessor `SUPERSEDED`; **and (B)** a verified `RegistryHeadAdvanceAuthorizationV1` from exactly the prior head to exactly the candidate in the same epoch, still executable (the head is still prior) or executed by the entry that consumed it. (A) alone is a staged candidate | not witness execution (`witnessExecuted: false`) |
| `S_PUBLISHED` | the chain holds the entry that consumed (B), and the current head is exactly the candidate | not issuance ready; `predecessorState` is null (nobody issues) |
| `S_ACTIVATED` | the signer `HEALTH` reports the successor fingerprint, and the authority recovery ledger observes `REGISTRY_VIEW{candidate version, [successor]}` | signer claims and observations only. `S_ACTIVATED != S_CURRENT` |
| `S_CURRENT` | (1) the head registry verifies under K-ROOT; (2) at the fresh V2 head (version and digest); (3) the single-current rule holds; the authority recovery ledger position equals the witness; (4) the loaded-key binding reproduces independently; (5) the local hold is released | `authorityGranted` stays false; only `issuanceReady` becomes true |

`validate_rotation_transition` allows only single forward steps, plus aborts
to `P_ACTIVE` from `S_PROPOSED`, `S_PREPARED`, and `S_AUTHORIZED`. An abort is
allowed only before the witness executed the head advance. `S_PUBLISHED`
onwards is forward only, so every skipped or backward edge is refused
(tested exhaustively over all 49 pairs).

Tests also cover:

- ambiguous dual-current (predecessor never revoked) is refused;
- a `ROUTINE` predecessor in a rotation is refused (RR-10: rotation uses
  `SUPERSEDED`);
- a head moved elsewhere by a competing authorization blocks
  `S_AUTHORIZED`.

**`t_cut` is registry data.** It lives in the K-ROOT-signed `revokedAt` of the
predecessor and `notBefore` of the successor, and it is used only for
historical interval verification. The TEST authority recovery ledger's
`ISSUE` records hold no `issuedAt`, so they can inform an operator but never
decide or authorize `t_cut`. `ledger evidence != registry authority`.

## 12. Authority recovery ledger (RR-5a, C-4)

`adopt_authorized_epoch` appends exactly one `ADVANCE_EPOCH` journal record to
the TEST authority recovery ledger, through the unchanged B1b-3c replay. The
record binds:

- `authorizationId`;
- `fromWitnessDigest`;
- the successor epoch;
- the target version;
- an observed `signingKeyIds`, which readiness re-derives.

It is refused when:

- the ledger rows diverge from the journal;
- the witness is not V2;
- the authorization does not verify, or is bound to another witness or
  epoch;
- the target does not match or verify.

It is **destroy/narrow-only**. The rows are identical before and after
(tested). It mints no evidence, reopens nothing, grants nothing, and makes no
key current. It has no path to the memory-broker ledgers or L04.

**Governing order (C-4, tested):**

1. ledger adoption;
2. witness execution over the post-journal `sequence/head`;
3. `quarantine_pre_recovery`;
4. the witness again, only if quarantine journalled anything;
5. independent verification.

The superseded B1b-3d §13 order is not restored, and the B1b-3d record is not
edited. The V1 `begin_recovery` path is unchanged and still used by B1b-3c.

## 13. Test coverage

`test_b1b3e_rotation_recovery.py` has **84 tests**. Coverage by area:

| Area | Coverage |
| --- | --- |
| Separators and registry digest | frozen and distinct; equals the B1b-3a golden; representation-independent; any content change changes it |
| `EpochAdvanceAuthorizationV1` | valid; tamper of every signed field; wrong separator (registry, head, witness, none); wrong root; non-test-only root; forked, non-successor, and reused-random epochs; window; nonce, ID, digest, and version validation; environment; cross-type |
| Epoch execution | stale prior witness; wrong prior epoch; wrong target and target epoch; expiry and not-yet-valid; missing adoption record (C-4); prior not the head; replay inside the clock window; a fresh authorization reusing a consumed ID; reused epoch random |
| `RegistryHeadAdvanceAuthorizationV1` | valid N→N+1; N→N; N→N+2; stale prior head; target digest mismatch; authorization epoch and target epoch mismatch; non-additive target; clock window; consumed ID with a matching head; competing authorizations (the first executed wins, the second fails the prior-head check); staged registry never the head; tamper of every field; cross-type; wrong separator and root |
| Non-adjacent authorization replay | A→B→A, A→B→C→A, and a replay across ledger-only entries: each W3 passes the pairwise `witness_v2_succession_reason`, but is rejected by the chain history (`CHAIN_AUTHORIZATION_REPLAYED`) and by the planner and writer (`AUTHORIZATION_CONSUMED`) |
| `RecoveryWitnessV2` | valid chain; V1 and V2 never parse as each other; signature tamper per field; rogue writer; authority key as witness; all 15 succession reasons; forked chain; not-from-genesis; replayed consumed ID; writer refusals; V2 context floor; head digest mismatch; downgrade |
| Registry succession | valid; every additive-history violation listed in §8; compromise escalation allowed |
| Single current key | the source terminology; one Actor plus separate Privacy; superseded predecessor plus successor; two current, including one before `notBefore`; scope mismatch; no current key; no `issuedAt` input |
| Rotation state | every state reached exactly; all 49 edges; skipped edges not forceable; hold on proposal; `S_PREPARED` cannot issue; `S_AUTHORIZED` not executed, and the abort window; `S_PUBLISHED` not ready (`BROKER_REGISTRY_VIEW_STALE`); `S_ACTIVATED != S_CURRENT`; each `S_CURRENT` condition; predecessor state; dual-current; `ROUTINE` refused; head moved elsewhere; unevaluable evidence fails closed |
| Loaded-key binding | valid; every mismatch; wrong domain, type, and environment; each input missing; B4 alone insufficient; real authority-dev cross-check |
| Restore and recovery | PREPARED voided; CONSUMED never reopens (a re-prepare refused; tampered rows → `TERMINAL_STATE_REOPENED`); stale epoch rejected; old registry rejected against V2; old ledger rejected while the witness survives; adoption destroy/narrow-only and C-4 ordered; adoption refusals; old evidence not reservable after the advance; **whole-host rollback shown undetected and unclaimed** |
| Compatibility and structure | V1 witness and reason sets unchanged; compromise still retroactive (backdated evidence `KEY_COMPROMISED`); `ROUTINE`/`SUPERSEDED` identical; all existing goldens and authority-dev `SHARED_HASHES` unchanged; the contract module is pure and holds no key; the signer module touches only the authority recovery ledger; not reachable from runtime code; public-material entry points; distinct TEST keys |
| Golden vectors | the file equals the regenerated document; its SHA-256 is pinned; every golden artifact verifies; the C-4 op order is frozen |

The existing structural scans (B1b-3b) apply automatically to the two new
package modules:

- no private-key type, private-key byte, or signer import in
  `lilith_owner_memory`;
- no OS, filesystem, database, or seed literal in `lilith_authority_signer`.

## 14. Non-claims

This phase does **not** claim, create, or authorize any of the following:

- a live rehearsal, epoch advance, rotation, revocation, or restore;
- any DEV or PROD contact;
- any real key, credential, witness, registry, or ledger;
- signer activation or witness installation;
- PROD authority, real-owner-grade custody, or a real registry root;
- First Memory;
- Privacy custody;
- Stage III;
- memory zeroization;
- proof-of-possession (RR-14a);
- re-attestation or pre-compromise survival. Compromise stays retroactive
  (C-1).

**Whole-host rollback is not detected.** A witness, registry, and authority
recovery ledger restored together pass every check here (tested), and
`wholeHostRollbackProtected` stays false.

## 15. Remaining decisions

- **Live blockers, open:**
  - RR-6: does compromise of the issuing key force an epoch advance?
  - RR-7: is retained key material a compromise?
  - RR-9: how does the witness recover from a crash between the chain
    write and the rename?
  - RR-11: the successor keygen slot and release set.
- **Deferred:**
  - RR-8: `compromisedSince` forensics;
  - RR-10a: epoch-advance predecessors keep `retiredAt` (the v5 fixture
    follows B1b-3c);
  - RR-12: the whole-host anchor;
  - RR-13: authenticated owner request;
  - RR-14a: proof-of-possession.
- **Source choices made here, recorded for review:**
  - the closed `HEAD_ADVANCE_REASONS` set;
  - V2 keeps the V1 `ledgerSequence`/`ledgerHead` names;
  - V2 replaces the V1 floor with the exact head (floor = head version);
  - the witness writer re-witnesses after quarantine only when quarantine
    journalled a record.

No conflict between current source and the merged design was found that
required stopping any part of this phase.
