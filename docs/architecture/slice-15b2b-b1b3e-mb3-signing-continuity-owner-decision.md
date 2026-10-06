# Slice 15B2b-B1b-3e — M-B3 / SIGN_REGISTRY_V1 Signing Continuity: Owner Decision (2026-10-06)

Status:

- **OWNER DECISION RECORDED (2026-10-06), DEV_SYNTHETIC only:**
  `MB3_SIGNING_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT_OFFHOST`.
- It resolves the gaps of the repository-only M-B3 preflight (§3). The
  reviewed ceremony procedure is the
  [M-B3 registry ceremony package](slice-15b2b-b1b3e-mb3-registry-ceremony-package.md).
- **This decision does NOT authorize M-B3 execution.** It authorizes no
  preparation sequence, no K-ROOT use, no signing, and no transfer.
  M-B3 / `SIGN_REGISTRY_V1`, M-B4/M-B5 `INSTALL_TRUST_AND_REGISTRY`,
  registry effectiveness, genesis, record 1, First Memory and PROD remain
  **NOT AUTHORIZED**. `FRESHNESS=UNKNOWN`.
- Append-only. Repository-only: no DEV, GCP, S25 or replica contact; no
  K-ROOT or K-WIT access; nothing signed.

```text
decision recorded != preparation sequence authorized != PREPARE != owner go != SIGN
  != REGISTRY_SIGNED != owner acceptance != installed != effective
candidate manifest != authority
prompt / flag / token != authorization
REGISTRY_SIGNED != M-B4/M-B5 authorization
```

| Field | Value |
| --- | --- |
| Control `main` at the decision | `14fbe03da8bd4e0c8d396b67bfe418bc460b44ed` (merge of PR #152, the M-B2 completion record) |
| Preceding accepted state | [M-B2 / `GENERATE_K_WIT` COMPLETED / ACCEPTED](slice-15b2b-b1b3e-mb2-kwit-completion.md); `K_WIT_CUSTODIED`; C-4 `KNOWN_CUSTODY_DEBT` |
| E-21 K-ROOT | `publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf` |
| K-WIT | `publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf`, keyId `test-only.witness.dev-synthetic.b1b3d.1`, blob `f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be` |
| Step | P3-5 step 3 `SIGN_REGISTRY_V1`, `K_WIT_CUSTODIED → REGISTRY_SIGNED` ([sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §3; `pr1b_sequencing.STEPS`) |

## 1. Owner decision (recorded)

The owner adopted:

> `MB3_SIGNING_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT_OFFHOST`
>
> The following semantics are ACCEPTED.

The fifteen accepted points are recorded in §2, in the owner's order and
without widening. The owner also stated that M-B3 / `SIGN_REGISTRY_V1`,
M-B4/M-B5 `INSTALL_TRUST_AND_REGISTRY`, registry effectiveness, genesis,
record 1, First Memory and PROD remain NOT AUTHORIZED, and that
`FRESHNESS = UNKNOWN`.

## 2. Semantics recorded

**D-1. Preparation sequence ≠ signing go.** One explicitly owner-authorized
M-B3 preparation sequence is required. Its authorization does **not**
authorize K-ROOT signing. The sequence establishes fresh / current public
evidence and prepares the exact candidate. A **separate explicit owner go**
is required immediately before the single real K-ROOT signing invocation.

**D-2. Required fresh read-only gates.** The preparation sequence must freshly
establish:

- the exact accepted control commit;
- B-5 grant usable; no applicable B-5 stop; no G-1 … G-9 invalidator;
- K-ACT CURRENT re-proof on DEV;
- the accepted K-ACT publication bytes, **obtained read-only in that fresh
  re-proof and cryptographically pinned** (not an assumed historical copy);
- K-WIT public identity / credential preservation;
- K-ROOT custody attestation on the S25;
- an acceptable boot / broker / exposure posture.

The procedure recomputes and verifies the K-ACT public-key fingerprint from
the public key. It never trusts an unverified `publicKeySha256` field.

**D-3. PR-2 / DR-5 rule.** No fresh PR-2 and no full fresh DR-5 are required
solely for M-B3: M-B3 is off-host and installs or activates nothing. After
the final accepted K-ACT / host re-proof, occurrence **or uncertainty** of
any terminator below ends the current sequence:

| # | Terminator |
| --- | --- |
| M3-T1 | a new applicable DEV deployment |
| M3-T2 | a K-ACT change |
| M3-T3 | a K-WIT change |
| M3-T4 | a reboot |
| M3-T5 | broker replacement |
| M3-T6 | a relevant IAM / topology / exposure change |
| M3-T7 | a K-ROOT custody anomaly |
| M3-T8 | public-input provenance uncertainty |
| M3-T9 | an explicit owner pause or end |
| M3-T10 | any accepted B-5 stop or invalidator |
| M3-T11 | any other relevant uncertainty |

A terminated sequence cannot reuse its final evidence. A new sequence must
re-prove the applicable gates.

**D-4. Off-host signing.** Real M-B3 signing occurs only on the owner's S25,
in local Termux. Transfer to the S25 is limited to the reviewed, pinned
package; the reviewed, pinned phone script; and the accepted public inputs.
Then: laptop unplugged; airplane mode ON; local Termux only; no ADB, no SSH,
no remote automation. K-ROOT private material never leaves Termux private
storage. The K-ROOT passphrase is entered only locally on the S25 and is
never written to a file, shell argument, environment variable, transcript,
evidence set or exported artifact.

**D-5. Registry parameters (frozen rules).**

| Parameter | Rule |
| --- | --- |
| `policyVersion` | `policy.dev-synthetic.v1` |
| `epochRandom` | exactly one 16-byte cryptographically random value, generated locally on the S25 for the candidate with Python `secrets.token_hex(16)` |
| `issuedAt` | one UTC RFC 3339 second-resolution timestamp, generated on the S25 for the candidate |

These values are candidate-specific and become permanently bound into E0 and
the K-ROOT signature.

**D-6. Two-phase phone ceremony: PREPARE, then SIGN.** PREPARE must not
access, load or decrypt K-ROOT. PREPARE verifies the package and script pins
and the public inputs; generates `epochRandom` once and `issuedAt` once;
freezes `policyVersion`; constructs the exact unsigned Registry V1 with
canonical repository logic; computes the exact signing bytes and the
expected registry digest before any K-ROOT use; writes an immutable public
candidate manifest; verifies K-ACT equality and K-WIT distinctness as far as
possible without signing; checks burned identities; and **stops**. The owner
receives the manifest values and decides whether to issue the separate
one-attempt signing go. SIGN uses the already-frozen manifest and never
regenerates `epochRandom` or `issuedAt`.

**D-7. Public candidate manifest** (`mb3-inputs.json`). Evidence and input
freezing only: **not authoritative LILITH state and not authorization**. It
binds at minimum the environment / profile, control SHA, E-21 fingerprint,
K-ACT publication file SHA-256, recomputed K-ACT fingerprint, accepted K-WIT
fingerprint and keyId, the K-WIT publication and anchor hashes,
`policyVersion`, `epochRandom`, `issuedAt`, recovery-epoch counter 1,
`registryVersion` 1, the expected registry digest, the registry-root keyId,
the signer command semantics, the ceremony-script SHA-256 and every
public-input file hash. **An archive never embeds its own SHA-256**; the
bundle SHA-256 is recorded outside the bundle and bound by the owner go.

**D-8. Owner go.** It binds at minimum: DEV_SYNTHETIC; the exact control SHA;
the reviewed bundle SHA-256; the reviewed phone-script SHA-256; the
candidate-manifest SHA-256; the K-ACT publication SHA-256; the recomputed
K-ACT fingerprint; the E-21 fingerprint; the accepted K-WIT fingerprint and
keyId; `policyVersion`; the exact `epochRandom` and `issuedAt`; the expected
registry digest; the exact S25 key path; the exact signer command; and
exactly one invocation. It authorizes exactly one real SIGN operation. **No
UI, flag, confirmation prompt or manifest is authority by itself.**

**D-9. Signing invocation.** Exactly one real invocation of the existing,
unchanged `registry-v1` signer:

```text
python services/authority-dev/ceremony/lilith_authority_owner_dev.py registry-v1 \
  <key> <kact-publication> <epochRandom> <policyVersion> <issuedAt>
```

The reviewed script invokes it once; lets `getpass` take the passphrase from
the local Termux TTY; never automates, provides or stores it; captures stdout
into S25 private storage and stderr separately; records the exit status; and
has no automatic retry.

**D-10. Go consumption.** Any `REFUSED`, wrong passphrase, unexpected
additional passphrase prompt, prompt anomaly, signer failure, nonzero exit,
unexpected output, STOP condition, or relevant uncertainty after the go
consumes the go and ends the sequence. There is no automatic or same-go
retry. A replacement needs a new M-B3 sequence, fresh applicable evidence, a
new candidate as the burn rules require, and a new explicit owner go.

**D-11. Burn / failure semantics.**

| Case | Handling |
| --- | --- |
| A. no signature produced | go consumed; sequence ends; **no** real-registry burn from the failed attempt alone |
| B. signature produced, candidate later accepted | the technical state may become `REGISTRY_SIGNED`; the exact signed bytes are preserved and are the only bytes eligible for a later M-B4/M-B5 |
| C. signature produced, but verification fails, the owner rejects it, or it is otherwise invalid | burn the known real Registry V1 digest; never install it; no silent re-sign |
| D. signed output lost after signing | burn the pre-sign frozen expected digest; never simply invoke K-ROOT again |
| E. a real signed candidate existed and its identity genuinely cannot be recovered | append an `UNKNOWN_REAL_REGISTRY_BURN` tombstone with non-secret provenance; never invent a digest |

Any canonical burn-set update is separately reviewed before a replacement.

**D-12. C-5 / discard conflict resolution.** Before owner acceptance, a
failed or rejected signed candidate may be recorded as burned and discarded.
After owner acceptance of `REGISTRY_SIGNED`, the exact accepted signed bytes
are the M-B3 artifact, and M-B4/M-B5 must install those same bytes. No silent
regeneration, re-signing or replacement is permitted. This reconciles the
live-install preflight M-B3 rollback ("discard, never installed") with P3-5
C-5 ("install the same bytes"): the first applies before acceptance, the
second after it.

**D-13. Verification twice.** (A) on the S25 before export and (B)
independently on the laptop after export. Both verify at minimum: the K-ROOT
signature; root fingerprint = E-21; the exact canonical signing bytes; the
exact expected digest; the `dev` binding; `registryVersion` 1; the E0 values;
`policyVersion`; a single current K-ACT; the exact K-ACT record equal to the
accepted publication; the recomputed K-ACT fingerprint; K-WIT absent from the
registry; K-WIT / K-ACT / K-ROOT distinctness; the canonical burned-identity
checks; the schema and field constraints. The phone displays the registry
digest to the owner before export. **The S25 signed copy is authoritative for
M-B3 custody; the laptop copy is a verified public mirror / evidence copy.**

**D-14. K-WIT.** K-WIT does not sign M-B3. The private K-WIT credential is
never decrypted or touched. The K-WIT public publication and anchor are used
only to verify distinctness, on the S25 and on the laptop.

**D-15. Terminal state and owner acceptance.** Technical success terminal
state: **`REGISTRY_SIGNED`** = a valid K-ROOT-signed Registry V1 authority
object exists off-host. It does **not** mean the registry is installed,
effective, or activated, and it authorizes none of M-B4/M-B5, genesis,
record 1, First Memory or PROD. After technical `REGISTRY_SIGNED`, **STOP**. A
separate explicit owner acceptance is required to close M-B3.

## 3. Gap reconciliation (M-B3 preflight, 2026-10-06)

The repository-only preflight classified M-B3
`NOT_READY_FOR_OWNER_MB3_DECISION` with these gaps:

| Gap | Resolution | State |
| --- | --- | --- |
| M3-A continuity and fresh evidence | D-1, D-2, D-3 | **RESOLVED** |
| M3-B frozen parameters (`policyVersion`, `epochRandom`, `issuedAt`) | D-5 | **RESOLVED** |
| M3-C K-ACT publication provenance | D-2 (fresh read-only DEV re-proof, pinned; fingerprint recomputed) | **RESOLVED** |
| M3-D reviewed S25 package, output capture, self-verification | D-4, D-6, D-9; the [ceremony package](slice-15b2b-b1b3e-mb3-registry-ceremony-package.md) | **DOCUMENTED** (becomes reviewed on merge) |
| M3-E go semantics and passphrase attempts | D-8, D-10 | **RESOLVED** |
| M3-F burn semantics for signed-but-unaccepted / lost registries | D-11 | **RESOLVED** |
| M3-G off-host digest record and authoritative copy | D-13 (S25 authoritative; laptop mirror) | **RESOLVED** |
| M3-H verification specification and tooling | D-13; the package verifier | **DOCUMENTED** |
| M3-I K-WIT distinctness venue | D-14 (S25 and laptop) | **RESOLVED** |
| M3-J owner acceptance step | D-15 | **RESOLVED** |
| M3-K discard vs C-5 wording conflict | D-12 | **RESOLVED** |

## 4. Consistency with existing contracts

No runtime, sequencer, keygen, signer, installer or workflow change is
required, and none is made.

| Point | Existing contract | Result |
| --- | --- | --- |
| signer semantics | `lilith_authority_owner_dev.py` `registry-v1` (unchanged) | the package calls it unchanged; PREPARE calls its `registry_v1` function with a non-key capture object to freeze the exact bytes |
| release file set | `services/authority-dev/release_file_set.py` fails closed on any unlisted source there | all new code is control tooling under `services/owner-memory-control/tools/`; no runtime payload changes |
| burned identities | `burned_identities.py`, `CANONICAL_COUNT == 20` | unchanged; the real-registry burn representation is separate and append-only (package §11); a real burn needs a reviewed canonical update before replacement |
| sequencer evidence | `SIGN_REGISTRY_V1` evidence: `singleCurrentKeyHolds`, `kActRecordEqualsPublication`, `kWitNotInRegistry`, `registryDigestRecordedOffHost` | each maps to a verifier token (package §9); the sequencer stays a checklist, never the verifier |
| gate | `NOT_APPLICABLE_PRE_GENESIS` | no owner-register read is required for M-B3; M-B4 is `REQUIRED_UNKNOWN_BLOCK` |
| PR-2 ordering | live-install preflight §20: PR-2 precedes registry signing | satisfied as ordering (accepted PR-2 windows precede M-B3); D-3 requires no new PR-2 |
| K-ACT exposure | live-install preflight §21 / RR-20b | covered by the fresh §24 K-ACT re-proof (D-2) and terminators M3-T2 / M3-T6 |
| custody topology | B-4 Option A1; B-5 §7 | D-4 restates it; K-ROOT never leaves Termux private storage |

## 5. State

```text
MB3_SIGNING_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT_OFFHOST
OWNER DECISION RECORDED (2026-10-06), DEV_SYNTHETIC ONLY
PREPARATION SEQUENCE != SIGNING GO
NO FRESH PR-2 AND NO FULL FRESH DR-5 REQUIRED SOLELY FOR M-B3
TERMINATORS M3-T1 … M3-T11 AFTER THE FINAL K-ACT / HOST RE-PROOF
SIGNING ONLY ON THE S25, LOCAL TERMUX, AIRPLANE MODE ON, NO ADB / SSH / AUTOMATION
policyVersion = policy.dev-synthetic.v1
epochRandom = secrets.token_hex(16), ONCE, ON THE S25
issuedAt = UTC RFC 3339 SECONDS, ONCE, ON THE S25
PREPARE NEVER ACCESSES K-ROOT; EXPECTED DIGEST FROZEN BEFORE ANY K-ROOT USE
CANDIDATE MANIFEST = EVIDENCE ONLY; NOT AUTHORITY; NOT AUTHORIZATION
ONE OWNER GO = EXACTLY ONE SIGN INVOCATION; NO RETRY
BURN CASES A … E; UNKNOWN_REAL_REGISTRY_BURN NEVER INVENTS A DIGEST
VERIFICATION ON THE S25 AND ON THE LAPTOP; S25 COPY AUTHORITATIVE
TECHNICAL TERMINAL STATE = REGISTRY_SIGNED; SEPARATE OWNER ACCEPTANCE REQUIRED
THIS DECISION DOES NOT AUTHORIZE M-B3 EXECUTION
M-B3 / SIGN_REGISTRY_V1 = NOT AUTHORIZED
M-B4/M-B5 / INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED
REGISTRY EFFECTIVENESS = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD 1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED; NO K-ROOT OR K-WIT ACCESS; NOTHING SIGNED
```
