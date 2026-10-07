# Slice 15B2b-B1b-3e — M-B4/M-B5 Installable Representations: Owner Decision (2026-10-06)

Status:

- **OWNER DESIGN DECISION RECORDED (2026-10-06), DEV_SYNTHETIC only.** It
  sets three governed derivation rules. Each turns an accepted artifact into
  the exact canonical bytes that the unchanged installer and runtime accept:
  - Registry V1 (§2), the rule first given 2026-10-06 and preserved here;
  - the K-WIT witness anchor (§3);
  - the E-21 registry-root anchor (§4).
- The rules close the byte-form gap (G-1, G-2) found by the read-only
  M-B4/M-B5 preflight. The derivation tooling, the pinned results and the
  rest of the remediation are in the
  [remediation record](slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md).
- **This decision does NOT authorize M-B4/M-B5 execution.** It authorizes
  no installation, no DEV or S25 contact, no K-ROOT or K-WIT access, and no
  effectiveness.
  - M-B4, M-B5, `INSTALL_TRUST_AND_REGISTRY`, genesis, record 1, First
    Memory and PROD remain **NOT AUTHORIZED**.
  - `FRESHNESS=UNKNOWN`.
- Append-only. Repository-only work under the owner's repository-only
  authorization of control `69dc8373ef64bbff9fd1e334a144203cff53a78f`.

```text
accepted identity != transport file != installable representation != installed bytes
derived SHA-256 = representation pin != new identity
derivation != installation != TRUST_INSTALLED != registry effective != authority
decision recorded != M-B4/M-B5 authorized
```

| Field | Value |
| --- | --- |
| Control `main` at the decision | `69dc8373ef64bbff9fd1e334a144203cff53a78f` (merge of PR #158, the [M-B3 completion record](slice-15b2b-b1b3e-mb3-registry-sign-completion.md)) |
| Preceding accepted state | M-B3 / `SIGN_REGISTRY_V1` COMPLETED / ACCEPTED; Registry V1 SIGNED / OWNER-ACCEPTED, not installed, not effective |
| Step governed | P3-5 step 4 `INSTALL_TRUST_AND_REGISTRY`, `REGISTRY_SIGNED → TRUST_INSTALLED`, mutation `M-B4+M-B5` ([sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §3; `pr1b_sequencing.STEPS`) |
| Installer (unchanged) | `services/authority-dev/ceremony/install_authority_dev.py`, SHA-256 `fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487`; stages `install-anchors` (P1B-4) and `install-registry` (P1B-5) |

## 1. Why a decision was needed

The accepted artifacts are stored in the owner tools' stdout form. The
installed release reads a different form:

| Artifact | Accepted (transport) form | Form the installer and runtime accept |
| --- | --- | --- |
| Registry V1 | signed file `3f0a59c0…6156` = RFC 8785 JCS **+ one LF** | exact JCS: `install_authority_dev._canonical_document` refuses with `INPUT_DOCUMENT_NOT_CANONICAL`; `witness_readiness.parse_document_bytes` refuses with `DOCUMENT_MALFORMED` |
| E-21 root anchor | wrapper `300a57dc…db3f` = JCS `{registryRoot, publicKeySha256}` + LF | exact JCS `TrustedRegistryRootV1` `{schemaVersion, rootKeyId, environment, algorithm, publicKey}` |
| K-WIT witness anchor | publication `9e9dd078…3472` (the M-B3 export also holds a JCS + LF anchor) | exact JCS `TrustedWitnessAnchorV1` `{schemaVersion, witnessKeyId, environment, algorithm, publicKey}` |

The M-B3 acceptance forbids modification, substitution or regeneration of
Registry V1. Changing the runtime parsers would need a new release. The
owner therefore set governed derivation rules. They change neither parser.

## 2. Registry V1 installable representation (preserved and recorded)

The owner first gave this rule on 2026-10-06 and restated it unchanged in
this authorization.

**Identity.** The accepted Registry V1 authority identity stays bound to:

- `REGISTRY_V1_DIGEST = fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc`;
- the verified K-ROOT signature (E-21 verification = PASS);
- the canonical signed fields.

`SIGNED_TRANSPORT_FILE_SHA256 = 3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156`
remains the accepted transport/export file identity.

**Rule.** For installation only, the canonical installable bytes may be
derived from that exact transport file by removing **exactly one terminal
LF byte**. This is allowed only if every fail-closed check passes:

- the source SHA-256 is exactly `3f0a59c0…6156`;
- there is exactly one terminal LF;
- no other normalization is done;
- the JSON parses strictly, with no duplicate keys and no floats;
- RFC 8785 JCS(parse(R)) == R, byte for byte;
- the Registry V1 digest is still exactly `fa662721…14fc`;
- the frozen M-B3 signed fields are unchanged;
- the E-21 signature still verifies;
- no semantic field changes.

The derived installable SHA-256 is a **representation pin**, not a new
Registry V1 identity. The original signed transport file is preserved
unchanged.

## 3. K-WIT witness anchor derivation

Accepted K-WIT identity:

- keyId `test-only.witness.dev-synthetic.b1b3d.1`;
- fingerprint `5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf`;
- public publication SHA-256 `9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472`.

The installable witness anchor MUST be derived deterministically, only from
that exact publication:

1. The input SHA-256 must equal `9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472`.
2. Parse the publication with the reviewed schema and tooling.
3. Construct exactly the witness-anchor document the installer and runtime
   expect.
4. The document must name exactly `test-only.witness.dev-synthetic.b1b3d.1`.
5. Its public key must recompute to exactly
   `5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf`.
6. `environment` must be exactly `dev`.
7. Serialize it as RFC 8785 JCS canonical bytes, with NO trailing newline
   and no extra transport bytes.
8. The output must pass the existing installer and runtime canonical-byte
   parsers without changing them.
9. Derive independently at least twice off-host and require byte-identical
   output.
10. Record the exact derived witness-anchor SHA-256.

No K-WIT private material may be read, decrypted or used. The rule does
NOT permit using an arbitrary witness-anchor export, normalizing arbitrary
whitespace, changing key identity, or regenerating K-WIT.

## 4. E-21 / K-ROOT registry-root anchor derivation

Accepted E-21 identity:

- fingerprint `cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf`;
- registry root keyId `test-only.registry-root.dev-synthetic.b1b3d.1`;
- public root wrapper SHA-256 `300a57dc01690868f7e6fa5dede4f7ca7278505e95b4fbbf0a2d505a18ffdb3f`.

The installable registry-root anchor MUST be derived deterministically,
only from that exact wrapper:

1. The input SHA-256 must equal `300a57dc01690868f7e6fa5dede4f7ca7278505e95b4fbbf0a2d505a18ffdb3f`.
2. Parse the wrapper strictly with the reviewed schema.
3. The wrapper must contain exactly the expected `registryRoot` object and
   its associated public-key check value, in the accepted format.
4. Extract ONLY the `registryRoot` object.
5. The extracted object must match exactly the installer's
   `TrustedRegistryRootV1` schema.
6. It must carry the accepted root keyId
   `test-only.registry-root.dev-synthetic.b1b3d.1`.
7. `environment` must equal `dev`.
8. `algorithm` must equal the accepted E-21 algorithm, pinned from the
   existing reviewed schema: **`Ed25519`**
   (`lilith_owner_memory.authority_contracts.ALGORITHM`). No new value is
   invented.
9. The extracted public key must recompute to exactly the E-21 fingerprint
   `cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf`.
10. The wrapper's check value (`publicKeySha256`) must be consistent with
    the extracted key under the reviewed format.
11. Serialize ONLY the extracted `TrustedRegistryRootV1` object as RFC 8785
    JCS, with NO trailing newline and no wrapper fields.
12. The output must pass the existing installer and runtime canonical-byte
    parsers without changing them.
13. Derive independently at least twice off-host and require byte-identical
    output.
14. Record the exact derived root-anchor SHA-256.

No K-ROOT private material may be opened, read, decrypted or otherwise used.
The derived root-anchor SHA is an installation representation pin; it does
NOT replace or redefine the E-21 identity.

## 5. Fail-closed rule (all three)

For Registry V1, the root anchor and the witness anchor:

ANY failure to establish any of the following means **STOP**:

- the exact accepted source identity;
- the schema;
- canonical bytes;
- key identity or fingerprint;
- the digest/signature relationship;
- deterministic output.

There is no fallback representation, no permissive normalization, no
runtime relaxation, no re-signing and no regeneration.

## 6. Results under these rules (repository-only)

The pins below come from the reviewed tooling. They were derived three
times, byte-identical: twice with the tool and once with an independent
implementation. See [remediation record](slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md)
§3.

| Installable representation | Source (pin) | Derived SHA-256 (representation pin) | Bytes |
| --- | --- | --- | --- |
| `trust/registry-root.json` | E-21 wrapper `300a57dc01690868f7e6fa5dede4f7ca7278505e95b4fbbf0a2d505a18ffdb3f` | `bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687` | 179 |
| `trust/witness-anchor.json` | K-WIT publication `9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472` | `be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a` | 176 |
| `registry/authority-registry.v1.json` | signed transport `3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156` | `46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e` | 955 |

## 7. Authority boundary

```text
OWNER DESIGN DECISION RECORDED: INSTALLABLE REPRESENTATIONS (REGISTRY V1, K-WIT ANCHOR, E-21 ROOT ANCHOR)
REGISTRY_V1_DIGEST = fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc (IDENTITY UNCHANGED)
SIGNED_TRANSPORT_FILE_SHA256 = 3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156 (PRESERVED UNCHANGED)
REGISTRY_V1_INSTALLABLE_SHA256 = 46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e (REPRESENTATION PIN)
ROOT_ANCHOR_INSTALLABLE_SHA256 = bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687 (REPRESENTATION PIN)
WITNESS_ANCHOR_INSTALLABLE_SHA256 = be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a (REPRESENTATION PIN)
E-21 publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf (IDENTITY UNCHANGED)
K-WIT publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf (IDENTITY UNCHANGED)
ANY FAILURE = STOP; NO FALLBACK; NO NORMALIZATION; NO RUNTIME RELAXATION; NO RE-SIGNING; NO REGENERATION
TRUST_INSTALLED = NO
REGISTRY_INSTALLED = NO
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
M-B4 = NOT AUTHORIZED
M-B5 = NOT AUTHORIZED
INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED
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
