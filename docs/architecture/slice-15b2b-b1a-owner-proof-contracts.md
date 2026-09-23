# Slice 15B2b-B1a — synthetic owner-proof contracts

**Status: local implementation candidate, synthetic only.** No owner credential
is enrolled, no production RP/origin is chosen, and no proof result is wired to
ActorEvidence, Policy, Consent, Rollback, Privacy, L18, L04, an HTTP route, a
relay, or a broker service. This is not live owner authority or canonical memory.

## Boundary and dependencies

IAP plus OS Login establishes Ravindu's interactive session identity, but the
GitHub deployment service account has IAP and OS Admin Login on both VMs and
therefore can assume a local Unix identity through root. A UID alone cannot
confirm consequential memory actions. The future proof uses a private
credential held off-host and a registered public verification record. B1a
implements only a synthetic verifier and isolated durable replay ledger.

`fido2==2.2.1` provides WebAuthn parsing, RP/origin/challenge/UP/UV checks and
COSE signature verification. The accepted algorithm is ES256 (`-7`); the
implementation does not hand-code signature, authenticator-data, or COSE
verification. `rfc8785==0.1.4` supplies actual JSON Canonicalization Scheme
bytes. Both are pinned in the Core API requirements. The existing
`FrozenMemoryActionV1.action_digest` remains its unchanged, opaque V1 digest;
B1a does not reinterpret or migrate it.

## Closed challenge and proof

`OwnerMemoryChallengeV1` has exactly these JSON fields, with no extras:
`protocol`, `schemaVersion`, `ownerPrincipal`, `challengeId`, `actionDigest`,
`payloadDigest`, `operation`, `memoryClass`, `subjectNamespace`, `subjectKey`,
`purpose`, nullable `memoryItemId`, nullable `expectedActiveRevisionId`,
nullable `restoreTargetRevisionId`, nullable `restoreTargetDigest`,
`privacyNoticeVersion`, `nonce`, `issuedAt`, `expiresAt`, `rpId`. Operation is
`CREATE` (future REMEMBER), `SUPERSEDE`, `RESTORE`, or `FORGET`. A RESTORE target
digest must equal the frozen action's payload digest. The broker must
eventually generate the challenge ID and 32-byte nonce; B1a has no issuer.
Times are exact UTC `YYYY-MM-DDTHH:MM:SSZ`; lifetime is positive and at most
60 seconds. The nonce is unpadded base64url. B1a's synthetic owner and RP are
`user:synthetic-owner@example.invalid`, `owner.lilith.invalid`, and
`https://owner.lilith.invalid`. They are **TEST_ONLY / NON_PRODUCTION / NOT
VALID FOR OWNER ENROLLMENT**. The verifier rejects `.invalid` outside explicit
test mode plus `LILITH_ENV=test`, including at verification time.

Canonical challenge bytes are `rfc8785.dumps(challenge.to_dict())` (UTF-8,
RFC 8785). WebAuthn challenge bytes are exactly:

```text
SHA-256(
  ASCII("LILITH_OWNER_MEMORY_CHALLENGE_V1") || 0x00 ||
  RFC8785_UTF8(OwnerMemoryChallengeV1)
)
```

The terminal client will eventually display the action from trusted typed
fields and ask the owner to authorize these digest-bound bytes. No raw
caller-supplied JSON is signed. Four golden canonical-byte and challenge-hash
vectors live in `services/core-api/tests/owner_proof_golden.jsonl` and its test.
They cover CREATE, SUPERSEDE, RESTORE, and FORGET shapes and contain no real
memory value.

`OwnerCredentialV1` has exactly `schemaVersion`, `recordId`, `ownerPrincipal`,
`credentialId`, `publicKeyCose`, `algorithm`, `rpId`, `status`, `createdAt`,
nullable `revokedAt`, and `lastObservedSignCount`. Only `ACTIVE` and `REVOKED`
exist. It contains no private key or seed. B1a's isolated ledger permits
**only test-mode installation** of `.invalid` public fixture records; this is
not an enrollment ceremony or a production credential registry. The verifier
looks up the public record itself. A caller cannot supply a key as a
per-request substitute for registration.

The assertion envelope has only `credentialRecordId`, `credentialId`,
`clientDataJSON`, `authenticatorData`, and `signature` (bounded canonical
base64url). The verifier checks exact owner, active credential, credential ID,
RP, ES256 key, WebAuthn `webauthn.get` type, exact challenge digest and origin,
RP-ID hash, user presence, user verification, and cryptographic signature.
Unexpected envelope fields, malformed/trailing authenticator data, duplicate
or unexpected client-data JSON fields, and cross-origin assertions fail closed.
The future Hsin/Home surface may need a separately versioned origin policy;
B1a intentionally has exactly one synthetic origin.

## Durability and authority separation

The SQLite owner-control test ledger is distinct from cognitive and Privacy
databases. A challenge starts `PREPARED`; cancellation is `CANCELLED`; an
expired prepared challenge becomes `EXPIRED`; a successful assertion changes
it to `CONSUMED` in the same `BEGIN IMMEDIATE` transaction that records the
credential record ID. Consumed/cancelled/expired rows cannot verify again,
including after process restart. A fresh server clock, not a request field,
decides expiry. A non-monotonic positive sign counter produces a cloning-risk
observation; counter zero does not block modern passkeys. The durable
challenge state, not the sign counter, is the replay authority.

The only positive output is `OwnerProofVerificationResultV1` with status
`VERIFIED_PROOF_ONLY`, challenge/credential/owner references, action digest,
observed counter, and counter-risk flag. It is **not** ActorEvidence, Consent,
Policy ALLOWED, Rollback Authorization, Privacy authorization, a token, or
canonical write permission. The module has no imports or call path to those
issuers. Logging must contain only minimized references and result codes;
the dependency's INFO message containing a raw credential ID is suppressed.

Threat levels: B1a synthetically tests that model/HTTP-looking inputs cannot
forge a WebAuthn proof (Level 1). It does **not** prove operational Level 2
isolation: current `lilith` can still read keys and write databases, and the
deployer remains root-capable until B1b/B1c/B1d. An off-host private key does
not solve malicious host-root or hypervisor software tampering (Level 3).

## Delivery impact and deferred decisions

The trusted DEV bundle builder automatically includes every
`lilith_memory/*.py` module and the pinned requirements; DEV installs those
requirements and compiles the module. Its fixed test allowlist does not
include the new B1a test file or golden-vector file. Repository CI discovers
the new test file. No deployment-control change is proposed in B1a, and a PR
must not claim that DEV ran those new vectors. The current PROD workflow only
installs `app.py`; because `services/core-api/**` is in its push path filter,
**merging B1a would still trigger a PROD workflow/restart**, even though the
new module would not be installed there. The PR must not be merged in B1a.

Before live enrollment, Ravindu must choose the real RP domain, permitted
origins, authenticator(s), and recovery/revocation ceremony. B1b must replace
the test-only credential source with a separately governed public registry,
prove OS/broker isolation, and keep private credentials off both VMs. B1c
must replace broad deployer root access before claiming Level 2.
