# Relationship-origin correction: owner-approved canonical SUPERSEDE

Status: **SOURCE READY, DEPLOYMENT PENDING** (2026-11-08).
- Not installed anywhere.
- No live canonical memory, schema or signer has been changed.
- Each PROD step below needs its own explicit owner go, and runs on the destination host after the VM migration.

## Why

The owner's relationship-origin memory was admitted exactly as written (sha256 `047de4a8…`, 598 chars). That text
contains a human wording error: "I'm saving this" where the owner meant "I'm saying this". Canonical integrity worked.
What was missing was a governed way to **correct** an authoritative memory: this family was CREATE-only at every
layer (see the [PROD work note](../engineering/prod-work-note-2026-11-07.md) §3k).

Owner decision (2026-11-08):
- build an owner-approved SUPERSEDE using the existing revision infrastructure;
- keep the original signed revision as immutable history;
- change exactly one word;
- activate only with the owner's explicit signature;
- no FORGET and no conversation rewrite.

## What changes (source)

| Layer | Change | PR |
| --- | --- | --- |
| Family contract (`memory_action_v2`) | `VersionedFamilyV1.operations`. First Interaction stays `{CREATE}`; relationship origin is `{CREATE, SUPERSEDE}`. The family scope, consent and policy checks use it. FORGET stays Privacy-owned | A |
| L04 apply (`canonical_store._prevalidate`) | A versioned family applies only its own operations (previously CREATE-only for all) | A |
| L04 ledgers (`canonical_authority`) | `CONSENT_GRANT_V4_DDL` / `POLICY_DECISION_V4_DDL`: for this family, CREATE (no prior revision) **or** SUPERSEDE bound to a prior revision; every other byte is v3's | A |
| L18 (`learning_v2`) | `RELATIONSHIP_ORIGIN_V4_TABLE_DDL`: intent, candidate and proposal tables widened the same way; `LearningV2Store.supports_family_operation` | A |
| Schema migration | `relationship_origin_correction_migration` (v3 → v4): backup-gated, one transaction, rows byte-identical, indexes and triggers re-created exactly, fault-point rollback, idempotent; the v3 and FM-02 tooling refuse v4 | A |
| Conversation (`first_memory_conversation`) | `correct our origin: <full corrected statement>` offers ONE SUPERSEDE of the same item, bound to the ACCEPTED active revision (challenge `memoryItemId` / `expectedActiveRevisionId`). It refuses on v3 (`CORRECTION_SCHEMA_UNAVAILABLE`), with nothing to correct (`NOTHING_TO_CORRECT`) or with no change (`CORRECTION_UNCHANGED`) | A |
| Authority signer (`authority-dev/protocol.py`) | `RelationshipOriginActionV1` admits CREATE or SUPERSEDE of its one tuple (the base validator enforces the SUPERSEDE shape) | **B** (merged only at release time) |

**Already in place and reused unchanged:**
- revisions with `supersedes_revision_id`, the active-revision pointer, and `memory_apply_audit` (`prior_revision_id`);
- the expected-active-revision precondition;
- the owner challenge V2 (SUPERSEDE shape), owner evidence and the L04 V2 adapter;
- the accepted read's `memoryItemId` binding for non-CREATE operations;
- Privacy FORGET (it erases every revision of the identity).

**Why the signer change is a separate PR.** The signer-release pin tests (`test_owner_prod_signer_upgrade`,
`test_personal_memory_fm2_transition`) assert that `main`'s signer source equals the installed signer release. PR B
therefore stays a draft until the release step, exactly as FM-2 did.

## Invariants (tested)

- The original revision is never modified; the correction is a new revision of the same item.
  `supersedes_revision_id` and `prior_revision_id` record the lineage, and both admissions and audits remain.
- A correction is bound to the revision it replaces. A stale correction is refused by L04 (`PRECONDITION_FAILED`).
- Activation requires the owner's proof over the exact SUPERSEDE challenge. No consent means no row.
- CREATE behaviour is unchanged: a second origin memory is still refused, and First Interaction stays CREATE-only.
- RESTORE is not allowed for this family.
- FORGET is unchanged and erases every revision.
- The codename memory is untouched.

**Tests:**
- `services/core-api/tests/test_relationship_origin_correction.py` (8);
- `services/owner-memory-control/tests/test_relationship_origin_correction_offer.py` (4), including a full-chain proof that
  a new session recalls the corrected statement and that the installed signer wire still refuses it;
- the updated contract test in `test_relationship_origin_l04.py`.

## Destination deployment procedure (after migration; each numbered step is one owner go)

0. **Preconditions.** The migration is accepted on the destination host. Privacy is READY for this boot. A verified
   off-host backup exists. The current origin recall is exactly sha256 `047de4a8…`.
1. **Signer release.**
   - Merge PR B.
   - Build the signer release reproducibly, attested equal on Windows and WSL.
   - Add an FM-3 release contract (the `fm2_signer_upgrade` pattern: old release = installed, new = the PR B merge, a
     delta of exactly `lilith_authority_dev/protocol.py`).
   - Run the staged transition F0–F7 with `fm*_release_stages`: stop, select, start the witness then the signer; owner
     go at each mutating form.
   - Old release retained until F7.
2. **First Memory host tree release** containing PR A and PR B. Stage it beside `current`, verify the pinned host-file
   hashes, then switch.
3. **Schema v4 on the cognitive DB.**
   - Take a verified online backup (`backup.create_backup`, role `cognitive`).
   - Run `relationship_origin_correction_migration.migrate`.
   - Check that `schema_state` is 4 and that the origin recall is still exactly `047de4a8…` (unchanged text).
4. **Correction ceremony.**
   - Enable `canonical_memory.relationship_origin.create` for this window only (the same capability gates CREATE and
     correction).
   - Run one `first-memory remember` with `correct our origin: <full corrected statement>`.
   - The operator verifies, without printing the text:
     - the offer is `SUPERSEDE` with `replaces_revision_id` equal to the active revision;
     - the offered statement differs from the recalled one by **exactly one token**, `saving` → `saying`, at the same
       position, with the rest byte-identical;
     - the expected sha256 of the corrected statement is computed locally beforehand from the stored statement file.
   - The owner signs with the owner credential (WSL). Expect ADMITTED.
   - Disable the capability again, always, once this step has started.
5. **Verification.**
   - The first-memory recall equals the corrected statement by sha256.
   - 2 revisions on the item; the original still has sha `047de4a8…` as `supersedes_revision_id`.
   - Codename still recalled.
   - One fresh-session owner-DM recall on Discord shows "I'm saying this" with the rest unchanged.

## Rollback

| Point | Rollback |
| --- | --- |
| After step 1 (signer), before step 4 | The FM-style transition keeps OLD until F7; before F7, re-select OLD. After F7, a new release contract. The new signer is a superset (CREATE is unchanged), so leaving it is safe |
| After step 3 (schema v4), before step 4 | Restore the verified pre-v4 backup (role `cognitive`), or leave v4 in place. v4 only widens what may be recorded; CREATE and FORGET behaviour are unchanged |
| After step 4 (correction admitted) | History is never rewritten. To undo, run another owner-approved SUPERSEDE back to the original text (the original revision stays in history). FORGET is **not** a rollback tool for a correction |

## Privacy

No memory text appears in Git, logs or PR text. Synthetic statements only in tests. Ceremony checks compare hashes and
token positions, never printing values.
