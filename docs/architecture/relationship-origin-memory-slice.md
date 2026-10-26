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
as the E-23 fixtures do for 57bff671. A pin records that the tree differs from e2324a5 in exactly the successor signer
members (below).

## Readiness slice (after #263)

**FORGET.** `privacy_forget_runner` and `privacy_forget_intent` take one closed `ForgetProfileV1`.
- First Interaction is the default and is unchanged.
- The relationship-origin profile is owned by L04 and L18_V2. It writes its own labelled
  `relationship-origin.intent`, and only one FORGET may be held at a time.
- Hold-first, durable-before-erase, Privacy authorization, replay refusal and suppression are all unchanged.
- Privacy admits `HERMES_DEV_CONVERSATION` only where the required-owner floor provisions it, so Hermes joins this
  FORGET exactly when the owner provisions that floor for the origin scope.
- The root hold executor in the Hermes gateway package must also hold and release the new intent. The patch is
  staged outside this repository with its tests; it is a Hermes package change, not part of this source.

**Hermes read route.** `lilith-authority-ledger-dev first-memory-context` is a new closed root CLI form. A
socket-activated unit (`tools/hermes_context/`) runs it once per connection.
- It runs the trusted host's `recall` with only the context token, and the bridge forwards only
  `LOOKUP_EVIDENCE_USE`.
- Owner-personal memory leaves root only when both hold:
  - a root-owned, owner-approved grant (`/etc/lilith-first-memory-dev/hermes-owner-channel.json`, at most 7 days)
    names exactly that `lilith_os` session;
  - the Privacy floor makes Hermes an erasure owner of that memory.
- Anything not READY answers UNAVAILABLE with no memories.
- The Hermes `lilith_os` adapter sets the note as the turn's `channel_prompt`. Hermes applies that at call time and
  never persists it. Codename memory is a project fact and needs neither the grant nor the floor.

**Successor signer payload** against e2324a5 (layout v3, no added member, no witness member):
`lilith_authority_dev/protocol.py` (the origin purpose) and `lilith_authority_root/cli.py` (the context form). The
FM-1 transition tooling pins OLD 57bff671, NEW e2324a5 and the E-23 incarnations. Like FM-1 after #258, the
successor's transition contract is pinned after merge, from the attested build of the merge commit.

**L04 schema v3.** `tools/relationship_origin_l04_migration.py plan|apply` is the operator path. It first requires
the canonical runtime schema, the reviewed admission-link table and known owner ledgers. It then takes a verified
backup, applies only the v3 migration, and requires every canonical row (items, revisions, admissions, active
revisions, audits, links, consent, policy, proposal references) to be byte-identical afterwards.

## Activation (each step its own owner go; no PROD)

1. Review and merge this source. The routine Core API DEV deploy follows (runtime code).
2. Build the successor release from the merge commit (A = B, attested). Then open a control-only PR with its
   transition contract (the FM-1 shape with OLD e2324a5) and run that one signer-only transition, which restarts
   the witness from NEW as FM-1 did. Re-derive the DR-5 target.
3. Install the new First Memory host tree. Run `relationship_origin_l04_migration.py apply` on the F9c2 cognitive
   DB. Keep the canonical config DISABLED.
4. Hermes package: install the executor patch, then run `install_f9c.sh --repin`, because the executor's frozen Core
   API copy must know the origin identity. Confirm Privacy READY and an empty intent directory.
5. The owner supplies the origin statement (at most 600 characters). The normalized text is shown before any offer.
6. Enable only `canonical_memory.relationship_origin.create`, run one `remember our origin: …` turn with the owner
   credential, then disable creation again.
7. Recall it from a fresh host session (`what is our origin?`).
8. Hermes (separately authorized): install the context socket units and the adapter patch. The codename then
   reaches new Hermes sessions. The origin statement reaches Hermes only after two more things: a Hermes floor for
   its scope, and an owner grant for one `lilith_os` session. No tool provisions that floor yet:
   `privacy_schema_v2.provision_hermes_owner_floor` and its database triggers cover only the First Interaction
   scope. Extending them is a separate, reviewed Privacy change.
