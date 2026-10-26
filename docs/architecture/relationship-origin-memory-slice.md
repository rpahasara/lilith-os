# Relationship-origin memory: source slice (LOCAL, not activated)

**Status:** source and offline proof only, 2026-10-26. No DEV or PROD change, no memory written, no provider call.
The memory's content is the owner's own words and is supplied and approved by the owner at activation. Nothing in
this slice proposes, paraphrases or infers LILITH's history or personality.

## What it adds

One governed canonical-memory family next to the project codename. It is not a codename in disguise and does not
reuse the FORGOTTEN First Interaction identity.

| | Value |
| --- | --- |
| Tuple | `OWNER_PROVIDED_RELATIONSHIP_ORIGIN` / `lilith.core.relationship` / `origin.owner-statement` |
| Purpose | `LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL` |
| Capability | `canonical_memory.relationship_origin.create` (CREATE only; FORGET stays Privacy-owned) |
| Value schema | `OwnerRelationshipOriginV1` = `{"statement": …}`: NFC and trimmed, never rewritten, one paragraph, at most 600 characters, commas allowed, control/format/separator characters refused |
| Epistemic basis | `USER_ASSERTED` (the owner's statement; not a transcript and not an inference) |
| Sensitivity | `OWNER_PERSONAL`: shown only on the owner's own trusted channel |
| Directive | `remember our origin: <statement>`; recall `what is our origin?` (closed grammar, never inferred from dialogue) |

## Reused unchanged

The owner WebAuthn challenge and B2a verifier, governed `ISSUE_OWNER_EVIDENCE`, the durable signer ledger and
witness, the evidence-use transport (reserve, confirm, abandon, lookup), the L04 V2 adapter and admission link, the
accepted-memory read facade, Privacy holds and restore suppression, the Track B freshness gate, and the
root bridge forms (`first-memory remember|recall`). `canonical_contracts.py` is byte-identical (`f93d26d8`).

## Source changes

- `memory_action_v2.py`: the versioned families become a closed table (`VersionedFamilyV1`: First Interaction and
  relationship origin). The FM-02 First Interaction behaviour, names and digests are unchanged.
- `learning_v2.py`: one per-family L18 DDL generator. Its First Interaction output is byte-identical to the FM-02
  DDL, so the pinned v2 fingerprints are unchanged. It adds the five `learning_ro_*` tables and the statement
  normalizer. Store methods dispatch by family.
- `canonical_authority.py`, `relationship_origin_migration.py`: owner-ledger **schema v3**, explicit and
  backup-gated, from v1 (DEV today) or v2. It rebuilds `consent_grant`, `policy_decision` and `learning_proposal_ref`
  with paired CHECKs and keeps every row. From v1 it also adds the FM-02 tables, which stay empty and suppressed.
- `canonical_store.py`, `memory_v2.py`: family dispatch for apply and for Privacy erasure, restore residue and the
  identity inventory.
- `config.py`: the root-owned canonical config may now *name* the origin capability. It never names the First
  Interaction capability.
- **Signer:** `protocol.py` alone changes. It holds its own closed allowlist `SIGNER_PURPOSES` = {codename,
  relationship origin} and a self-contained `RelationshipOriginActionV1`: CREATE of the one tuple, every other field
  checked by the unchanged base validator. A test pins it equal to `memory_action_v2`. The release member set,
  layout v3 and every `SHARED_HASHES` pin are unchanged. No new operation, key, authority or bridge form.
- `first_memory_conversation.py`, `tools/first_memory_dev_host.py`: the closed origin kind, per-kind creation gating
  (the origin needs its own capability), and `recall_authorized`.
- `hermes_memory_context.py`: the read-only Hermes context contract `LilithCanonicalMemoryContextV1`. The memory
  side is reached through the unchanged `recall` bridge form with an exact context token. The conversation side
  renders one labelled note that is kept separate from chat history and leaves `OWNER_PERSONAL` out unless the
  channel is the owner's. Any refusal (Privacy not READY included) yields no note.

Tests: the FM-1 transition fixtures now build the e2324a5 payload from its git bytes (`installed_layout.build_fm1`),
as the E-23 fixtures do for 57bff671. A pin records that the tree differs from e2324a5 in exactly one signer member,
`lilith_authority_dev/protocol.py`.

## Activation still needs (each a separate owner go)

1. A reviewed **signer release** from the merge commit, then a signer-only transition like FM-1. The installed
   `e2324a5` signer refuses this purpose (`INVALID_ACTION`). The DR-5 target names the signer release path, so it
   must be re-derived.
2. The **host tree** update (`/opt/lilith-first-memory-dev/current`) and **schema v3** on the F9c2 cognitive DB,
   after a verified backup.
3. A governed **FORGET path for this identity**. The erasure owners and Privacy already handle it (tested), but the
   operator runner and its durable intent are First Interaction-only.
4. The owner's exact statement, then one `remember` turn under a single-use go with the origin capability enabled,
   then disabled again.
5. **Hermes**: a platform-adapter hook that calls `render_context_note` on a context payload obtained through the
   root bridge. The Hermes gateway runs unprivileged and cannot invoke the root bridge itself, so this needs an
   owner decision on the read route. No provider call is needed to prove the note; the Groq budget stays untouched.
