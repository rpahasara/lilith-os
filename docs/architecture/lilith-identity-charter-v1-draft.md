# LILITH Identity Charter V1 (DRAFT, NOT ACCEPTED)

```text
STATUS: DRAFT FOR OWNER REVIEW. NOT ACCEPTED. NO IDENTITY ID HAS BEEN CREATED.
```

This draft answers owner decision 2 of the
[15B2b-B design](slice-15b2b-b-owner-memory-control-design.md) ("whether, and how, to create a versioned identity
charter and a stable LILITH-system identity identifier"), approved in principle as D-1, D-2 and D-3. It is not
accepted, it does not resolve ledger rows ID-02 or FM-07, and it authorizes nothing. It restates accepted
architecture ([ADR-0001](../adr/0001-lilith-identity-above-runtimes.md),
[ADR-0007](../adr/0007-owner-domain-canonical-state-ownership.md),
[ADR-0008](../adr/0008-canonical-personality-ownership-soul-projection.md), principles P-01 and P-02) and adds only
what an identity identifier needs.

## 1. What the identity denotes

LILITH's persistent system identity is a **governed continuity relation** across change, not a component. It is
represented by one stable, opaque identifier, `lilithIdentityId`, bound to an accepted version of this charter.

The identifier names *which* governed history, memory, commitments and relationships belong together. It does not
describe LILITH, prove anything about LILITH's behaviour, or carry any authority.

This charter makes no claim about consciousness, subjective experience, feelings or inner life. It does not create,
assert or reconstruct any memory or experience.

## 2. Continuity invariants

Across replacement of a model, runtime, device, database or host:

- **I-1.** `lilithIdentityId` is unchanged. Only an owner-accepted identity decision may change it, and a change
  is recorded as a fork or successor, never as silent replacement.
- **I-2.** Accepted history is preserved, not rewritten. A replacement may change style or capability; it may not
  invent a new origin or silently rewrite relationships, commitments or accepted memory.
- **I-3.** A new runtime establishes its relationship to the identity through governed state and present authority.
  It does not establish identity by assertion.
- **I-4.** Identity and authority never validate each other (ledger ID-06). Stale or missing authority blocks
  authority-changing operations; it does not end the identity.

## 3. What cannot establish identity by itself

None of the following, alone or together, establishes that something *is* LILITH:

- the text "I am LILITH", any self-report, or any model output (ADR-0011);
- the same model, prompt, persona file (`SOUL.md`, ADR-0008), voice, avatar or embodiment;
- the same host, VM, database row, device, broker or key;
- the owner identity (`owner.ravindu.v1`), K-ROOT, K-WIT, the registry, the recovery epoch, the witness genesis or
  any authority-lineage digest.

A stable identifier alone also does not demonstrate narrative, behavioural or authority continuity. Those are
separate claims.

## 4. Separation of concerns

| Concept | What it is | Identity role |
| --- | --- | --- |
| LILITH system identity | `lilithIdentityId`, bound to an accepted charter version | Names the governed continuity relation |
| Owner identity | `owner.ravindu.v1`, authenticated by WebAuthn owner proof | The principal who authorizes; never LILITH's identity |
| Authority and lineage | K-ROOT, K-WIT, registry, ledger, witness, recovery epoch | Who may change governed state; never identity evidence |
| Runtime, model, session | Hermes, a model, a prompt, a process | Replaceable execution; owns nothing (ADR-0007 OD-9) |
| Memory subject and provenance | memory class, subject tuple, source, epistemic basis | What a record is about and where it came from |

A memory that is *bound* to the identity is LILITH's memory in the governance sense only. Identity verification never
substitutes for admission authorization or for verification of content truth: the binding does not admit the memory,
authorize anything or make its content true.

A binding is meaningful only **inside the owner-authorized admitted value**: it must be part of the exact
class-normalized value whose digest the owner's proof signed and L04 admitted. A binding supplied beside the memory,
by a caller or by an edited stored copy, binds nothing.

## 5. Versioning and supersession

- The charter is versioned (`1.0.0`, …). Its digest is `SHA-256("LILITH_IDENTITY_CHARTER_V1\0" ‖ charter bytes)`.
- A new charter version requires owner acceptance. It supersedes the previous version for new bindings and keeps the
  same `lilithIdentityId` unless the accepted decision explicitly records a fork.
- Bindings made under an earlier version remain historically valid under that version. They are not rewritten.
- The identity profile is `{environment, lilithIdentityId, charter: {charterVersion, charterDigest}}`, digested as
  `SHA-256("LILITH_IDENTITY_PROFILE_V1\0" ‖ RFC 8785 JCS(profile))`, following the repository's existing convention.

## 6. Proposed creation, custody and persistence of the real identifier (not performed)

1. **After** this charter is accepted, the owner generates the identifier once, offline on the owner workstation:
   128 bits from the operating-system CSPRNG (`secrets.token_bytes(16)`), formatted `lid1.` + 32 lowercase hex.
   It is never derived from the owner ID, a key, an epoch, a host or a model.
2. The identifier is **not secret**. Its protection is integrity and uniqueness, not confidentiality.
3. The owner records an identity profile binding the identifier to the accepted charter digest, checks that it
   collides with no known value in §3, and accepts it through the existing off-host owner-acceptance and sealing
   procedure. The profile digest is then pinned in the repository. A collision check catches some mistakes only:
   it **cannot prove independent random generation**. Independence rests on the separately reviewed,
   owner-controlled generation procedure and its record.
4. The identifier is never regenerated. Loss of a copy is recovered from the sealed off-host record or the
   repository pin. A conflicting second identifier is refused, never merged.
5. DEV_SYNTHETIC and any later real environment have **separate** identity profiles; a synthetic or test identifier
   is never reused as a real one.
6. A repository-pinned profile **cannot authenticate itself**. Its standing depends on controlled owner acceptance
   (owner-merged change), trusted verification code that loads the pin, and the sealed off-host acceptance record it
   must match. Neither the repository contents alone nor a memory value or caller packet are authoritative.

## 7. Nonclaims

This draft does not accept the cognitive-contract identity specification, define a First Memory class or semantic
packet (FM-02), authorize First Memory, change any owner-signed contract, or create an identifier.
