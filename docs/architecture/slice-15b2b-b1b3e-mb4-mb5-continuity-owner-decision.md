# Slice 15B2b-B1b-3e — M-B4/M-B5 `INSTALL_TRUST_AND_REGISTRY` Continuity: Owner Decision (2026-10-07)

Status:

- **OWNER DECISION RECORDED (2026-10-07), DEV_SYNTHETIC only:**
  `MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO`
  is **ACCEPTED** (§2). It was PROPOSED in the
  [remediation record](slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md)
  §8.
- It closes **G-5 in governance**. The reviewed procedure is the
  [M-B4/M-B5 ceremony package](slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md).
- The owner also accepted the three installable representation pins (§3).
- **This decision accepts continuity semantics only. It does NOT authorize
  execution.** It authorizes no preparation sequence, DEV or S25 contact,
  transfer, installer stage, verifier or removal run.
  - M-B4, M-B5 and `INSTALL_TRUST_AND_REGISTRY` remain **NOT AUTHORIZED**.
  - Genesis, record 1, First Memory and PROD remain **NOT AUTHORIZED**.
  - `FRESHNESS=UNKNOWN`.
- Append-only. Repository-only work under the owner's authorization of
  control `b0299f3966de051042b7c906b89559a179ed998d`.

```text
continuity ACCEPTED != preparation sequence authorized != M-B4 go != M-B4
  != M-B4 POST / W3 != HARD STOP != M-B5 go != M-B5 != W5 VERIFIED
  != TRUST_INSTALLED accepted != registry effective != authority active
M-B4 success != TRUST_INSTALLED;  M-B4 success != M-B5 authorization
removal before M-B6 != K-WIT burn option reopened
```

| Field | Value |
| --- | --- |
| Control `main` at the decision | `b0299f3966de051042b7c906b89559a179ed998d` (merge of PR #160, the M-B4/M-B5 [owner decision](slice-15b2b-b1b3e-mb4-mb5-installable-representation-owner-decision.md) and [remediation](slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md)) |
| Preceding accepted state | M-B3 / `SIGN_REGISTRY_V1` COMPLETED / ACCEPTED; Registry V1 SIGNED / OWNER-ACCEPTED, not installed, not effective |
| Step | P3-5 step 4 `INSTALL_TRUST_AND_REGISTRY`, `REGISTRY_SIGNED → TRUST_INSTALLED`, mutation `M-B4+M-B5`, gate `REQUIRED_UNKNOWN_BLOCK` ([sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §3, §10; `pr1b_sequencing.STEPS`) |
| Physical stages | installer `install-anchors` (P1B-4, M-B4) and `install-registry` (P1B-5, M-B5), `install_authority_dev.py` SHA-256 `fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487` |

## 1. Owner decision (recorded)

The owner accepted:

> `MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO`

The fifteen accepted points are recorded in §2 in the owner's order, without
widening. The owner also stated that the decision accepts continuity
semantics only and does not authorize execution (§5).

## 2. Semantics recorded

**C-1. One sequence.** M-B4 and M-B5 belong to one owner-attended,
evidence-bounded sequence.

**C-2. One evidence set.** The sequence uses one freshly established
evidence set.

**C-3. M-B4 go.** M-B4 requires its own separate, explicit, ONE-ATTEMPT
owner go.

**C-4. M-B4 POST.** Successful M-B4 must be followed by its required POST
and content verification.

**C-5. Hard stop.** There is a HARD STOP after M-B4.

**C-6. M-B5 go.** M-B5 requires a second separate, explicit, ONE-ATTEMPT
owner go.

**C-7. No implicit M-B5.** M-B5 is not implicitly authorized by M-B4
success.

**C-8. Broken continuity.** If any of the following happens between the
two stages, M-B5 cannot continue on old evidence, and a fresh re-proof is
required:

- relevant state changes;
- uncertainty appears;
- the sequence is paused;
- continuity is otherwise broken.

**C-9. K-WIT acknowledgement.** M-B4 authorization must explicitly
acknowledge:

- M-B4 closes the K-WIT burn/regenerate option;
- that option does not reopen merely because installed files are later
  removed before M-B6.

**C-10. Two physical stages, one transition.** M-B4 and M-B5 stay separate
physical installer stages. The accepted sequencer still models
`INSTALL_TRUST_AND_REGISTRY` as one forward transition,
`REGISTRY_SIGNED -> TRUST_INSTALLED`.

**C-11. M-B4 alone is not trust.** Successful M-B4 alone does not mean
`TRUST_INSTALLED`.

**C-12. What establishes TRUST_INSTALLED.** Successful M-B5 plus all
required content verification is what may establish `TRUST_INSTALLED`. It
is subject to separate owner acceptance.

**C-13. No TTL.** No wall-clock TTL is introduced.

**C-14. Uncertainty.** Relevant uncertainty means REVALIDATE / sequence
unusable, not PASS.

**C-15. No replay.** Historical PASS evidence may not be replayed as
current evidence.

## 3. Accepted installable representation pins

| Representation | SHA-256 |
| --- | --- |
| Registry V1 installable (`authority-registry.v1.json`) | `46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e` |
| registry-root anchor (`registry-root.json`) | `bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687` |
| witness anchor (`witness-anchor.json`) | `be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a` |

The accepted Registry V1 identity is unchanged:

| Identity | Value |
| --- | --- |
| `REGISTRY_V1_DIGEST` | `fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc` |
| `SIGNED_TRANSPORT_FILE_SHA256` | `3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156` |
| `EXPORT_SHA256` | `c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8` |
| E-21 fingerprint | `cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf` |
| K-WIT fingerprint | `5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf` |

## 4. How the semantics bind the procedure

| Point | Where the [package](slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md) enforces it |
| --- | --- |
| C-1, C-2, C-15 | §4: one sequence; the fresh evidence set E-1 … E-22 is collected inside it; no historical value counts |
| C-3, C-9 | §7: the M-B4 go template names one `install-anchors` invocation and carries the K-WIT acknowledgement verbatim |
| C-4, C-5, C-11 | §8: the M-B4 POST checkpoint (`expect W3_ANCHORS_INSTALLED_REGISTRY_ABSENT`), then HARD STOP; `TRUST_INSTALLED` is not claimed |
| C-6, C-7, C-8 | §9: the M-B5 go template names one `install-registry` invocation; the inter-stage continuity check K-1 … K-8; any break means a fresh re-proof |
| C-10, C-12 | §10: the M-B5 POST and `expect W5_INSTALLED_CONTENT_VERIFIED`; the three sequencer evidence items; then a separate owner acceptance |
| C-13, C-14 | §3: events and sequence bound validity, not a clock; unknown means REVALIDATE |

## 5. Authority boundary

```text
OWNER DECISION RECORDED: MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO (ACCEPTED)
CONTINUITY SEMANTICS ONLY; NO EXECUTION AUTHORIZED
G-5 CLOSED IN GOVERNANCE
ONE SEQUENCE; ONE FRESH EVIDENCE SET; TWO SEPARATE ONE-ATTEMPT GOS; HARD STOP AFTER M-B4
M-B4 SUCCESS != TRUST_INSTALLED; M-B4 SUCCESS != M-B5 AUTHORIZATION
M-B4 CLOSES THE K-WIT BURN/REGENERATE OPTION; REMOVAL BEFORE M-B6 DOES NOT REOPEN IT
NO WALL-CLOCK TTL; UNCERTAINTY = REVALIDATE; NO REPLAY OF HISTORICAL PASS
REGISTRY_V1_INSTALLABLE_SHA256 = 46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e
ROOT_ANCHOR_INSTALLABLE_SHA256 = bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687
WITNESS_ANCHOR_INSTALLABLE_SHA256 = be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a
M-B4 = NOT AUTHORIZED
M-B5 = NOT AUTHORIZED
INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED
TRUST_INSTALLED = NO
REGISTRY_INSTALLED = NO
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
GENESIS = NOT AUTHORIZED
RECORD_1 = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED; NO K-ROOT OR K-WIT PRIVATE MATERIAL ACCESSED
```

> **Later current state (2026-10-07, pointer only; the text above is
> preserved as written).** M-B4/M-B5 `INSTALL_TRUST_AND_REGISTRY` completed in
> preparation Sequence 2 (control `82b89a3`) and was owner-accepted
> ([completion record](slice-15b2b-b1b3e-mb4-mb5-install-trust-registry-completion.md)).
> Exactly one `install-anchors` ran: P1B-4 PASS, and W3 was confirmed after one
> read-only re-classification of a local-client POST anomaly. Exactly one
> `install-registry` ran: P1B-5 PASS, `W5_INSTALLED_CONTENT_VERIFIED`, denial
> proof P1B-5 PASS. The trust anchors and Registry V1 are installed (technical,
> owner-accepted); the registry is not effective and no authority is active.
> The K-WIT burn/regenerate option is closed. M-B6, genesis, record 1, First
> Memory and PROD remain NOT AUTHORIZED, and FRESHNESS is UNKNOWN.
