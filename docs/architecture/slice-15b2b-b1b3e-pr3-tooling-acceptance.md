# Slice 15B2b-B1b-3e — PR-3 Owner-Freshness Tooling Acceptance (PR-1B blocker B-1)

Status:

- **ACCEPTED** by explicit owner statement (2026-09-29). Scope: PR-3 source and tooling only
- Closes PR-1B blocker **B-1** (`pr3ToolingAccepted`) of the
  [PR-1B eligibility review](slice-15b2b-b1b3e-pr1b-eligibility-review.md)
- `LIVE_MUTATION = NONE`; no DEV contact; no owner-replica contact
- **PR-1B remains `PR1B_NOT_ELIGIBLE`**: B-2, B-3, B-4, B-5 open

```text
tooling accepted != record 1 != freshness CURRENT != acceptance enabled != PR-1B authorization
```

## 1. Owner statement (verbatim)

> I explicitly accept the LILITH 15B2b-B1b-3e PR-3 owner-freshness source and tooling as merged on main 7cef93729fcb26288173055276df54a8f092851a — services/owner-memory-control tree 9292ec47b6f586204926e4e07228676db8baff21, identical to PR-3 source commit cf22303fa40653271b9af33e9be9560347c648a3 — covering the 13 files with scope digest f7a76f37cdb849a9b41644aa8ec19bbb91e9b4ba19ff40e6ad72b4a3992cf84f, including their documented limitations.
> This acceptance satisfies PR-1B precondition pr3ToolingAccepted only.
> It does not create record 1, does not make owner freshness CURRENT, does not lift REAL_ACCEPTANCE_ENABLED, does not create any authority or custody state, and does not authorize PR-1B or First Memory.

## 2. Accepted identity

| Item | Value |
| --- | --- |
| main | `7cef93729fcb26288173055276df54a8f092851a` |
| `services/owner-memory-control` tree | `9292ec47b6f586204926e4e07228676db8baff21` (identical at `cf22303` and at `7cef937`) |
| final PR-3 source commit | `cf22303fa40653271b9af33e9be9560347c648a3` |
| PR-3 source commits | `368b36c` (foundation) · `fd0051a` (P3-2 CLI) · `7880df8` (P3-3 gate) · `c95f9d0` (P3-4 rehearsal) · `3f275ca` (P3-5 sequencing) · `0af0384` (P3-6 envelope) · `b4d4632` (P3-3A publication) · `cf22303` (Android fail-contained probe) |
| PR-3 documentation commits | `21f96be` · `69df29c` · `6238d59` |
| scope digest | `f7a76f37cdb849a9b41644aa8ec19bbb91e9b4ba19ff40e6ad72b4a3992cf84f` |

The scope digest is the SHA-256 of the file listing below: 13 lines in
`sha256sum` format (`<sha256>  <path>` + LF), sorted by path. To reproduce
it, save the block without the fences and run `sha256sum`. It verifies
against `main` with `sha256sum -c`.

```text
58b22c6d2a8dbb2b907348b806c0df32e2290ea6d6f590ccb8151a067ea232a5  services/owner-memory-control/lilith_owner_memory/create_only_publish.py
1e4ffe11b69963b2998ad3c342e2d482268ff74d8c69c510a90743aac61ee31d  services/owner-memory-control/lilith_owner_memory/owner_acceptance.py
9eab25b892010f1de966fb5c23357bf93a60ea472d02bbaf7a16fc1336b76689  services/owner-memory-control/lilith_owner_memory/owner_freshness.py
1ef8534412e39cdea2b5cdaef9a8c269a5a50aefbefd91672a1ecbf04595e8d9  services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py
bf3413311c061c2638f1a4feaa31accb819db4093c93f915ca8720be91f33088  services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py
900f37a48c5f257be0a66ddd507b3d683e390a92d4752d430c7472cca4d6f957  services/owner-memory-control/tests/test_b1b3e_pr3_owner_freshness.py
882321b61ef10cd7a3f5a2412f5876a72f0c93c2c6af57fc28aa9bc22b4dae4a  services/owner-memory-control/tests/test_b1b3e_pr3_p32_owner_freshness_tool.py
06d48dcf5789df22552492752bd22d4eaf07a5044c4ccfcaebe0bb97eb3f0fb2  services/owner-memory-control/tests/test_b1b3e_pr3_p33_storage_gate.py
7163d79009ee2a6fb3924b78584a1a0591168941c3e07f2525b714bc130d4860  services/owner-memory-control/tests/test_b1b3e_pr3_p33a_create_only_publication.py
a7db9f049df5a6ef26a3c7785c12a6337ce2f52d085ad4998080696e99b2dadd  services/owner-memory-control/tests/test_b1b3e_pr3_p34_ceremony_rehearsal.py
a431e44719b711137038d1f5ccf61be11e9bcd2341dcf1d50b057de1552750e9  services/owner-memory-control/tests/test_b1b3e_pr3_p35_pr1b_sequencing.py
9b81edf84bfbbbf4a11d68c52823007a4f6e7d9371e1447d76b685bcfec47d31  services/owner-memory-control/tests/test_b1b3e_pr3_p36_acceptance_envelope.py
9b1b69a028629cc8df2d1b4f7a2bf1f6540c9e5b130d2a4afd689f91d0277678  services/owner-memory-control/tools/android_p3_probe.py
```

**Not in scope.** The previously reviewed contracts the tooling depends on:

- `authority_contracts`;
- `recovery_contracts`;
- `rotation_contracts`;
- `witness_readiness`;
- `contracts`;
- the Core API `lilith_memory.owner_proof`.

## 3. Review basis

The review was read-only, at `7cef937`.

**Tests.** 145 PR-3 tests OK (27 + 19 + 17 + 30 + 10 + 19 + 23). The whole
owner-memory suite passed: 634 tests OK in WSL. The Android probe refuses
outside Termux private storage.

**Invariants confirmed in code.**

- **`OwnerFreshnessRecordV1`:**
  - exact fields, pinned schema, JCS, and a domain-separated digest;
  - the profile binds the environment;
  - record 1 is `ACCEPT_CURRENT` on the genesis witness;
  - `recordVersion` is a successor with a matching previous digest, and
    environment, profile, and genesis are immutable;
  - a witness is decided once, and rejection is terminal;
  - acceptance must advance the witness version, with no epoch
    regression or fork and no registry regression or digest conflict.
- **Replicas:**
  - two are required, identical record for record;
  - behind, ahead, or forked copies give `REPLICAS_DIVERGENT`, never
    resolved by length or by the latest write;
  - strict reads refuse pending files, unexpected entries, gaps,
    duplicates, and zero-byte files.
- **Freshness:**
  - authenticity (K-WIT chain) is kept separate from freshness;
  - `CURRENT`, `STALE`, `AHEAD_UNACCEPTED`, `CONFLICTING`,
    `FRESHNESS_UNKNOWN`, `REFUSED`;
  - the gate passes only for AUTHENTIC + `CURRENT` over six gated
    operations.
- **Writers:**
  - `append` requires `--confirm-digest`, re-derives the candidate, and
    writes byte-identical records only;
  - `append-envelope` rebuilds the envelope and requires identity;
  - both refuse real profiles while `REAL_ACCEPTANCE_ENABLED=False`.
- **Publication:**
  - create exactly once, never replace;
  - `RENAME_NOREPLACE_V1` (preferred) and `HARDLINK_PUBLISH_V1` are
    admitted; `DIRECT_O_EXCL_V1` is rejected;
  - the backend never enters a digest.
- **`OwnerFreshnessAcceptanceEnvelopeV1`:** unsigned (PR3-D2), chained one to
  one with records, and its `ACCEPTANCE_*` state is kept separate from
  freshness.
- **P3-5 sequencing:** linear, and not a verifier. Record 1 comes only after
  `COMMIT_WITNESS_GENESIS`. First Memory is at most "review-eligible" after
  `FULL_READINESS`.

## 4. Accepted limitations

Accepted as documented, not resolved:

1. The records and the envelope are unsigned. Their authority comes only
   from owner custody, and digest confirmation does not stop a hostile
   process running as the owner.
2. Replica A is agent-reachable. Only Replica B is the agent-unreachable
   copy, and only while it stays disconnected.
3. Freshness is relative to the owner's last checkpoint. It says nothing
   about time, and it does not survive both replicas being rolled back
   together.
4. Some settings are unknown on each device. They affect a single replica
   only:
   - laptop VSS / restore points (Replica A);
   - Termux `allowBackup` and Google app-data categories (Replica B).
5. Platform limits:
   - Termux has no `os.link`, so hard-link publication is unavailable on
     B;
   - `RENAME_NOREPLACE` on B depends on the per-architecture syscall table;
   - `cryptography` must be preinstalled in Termux;
   - Windows directory fsync is unreviewed (A is WSL ext4).
6. A staged tool copy remains in the WSL home, outside Git.
7. Stale status text still describes P3-3 as incomplete:
   - `REAL_ACCEPTANCE_BLOCK_REASON = "P3_3_STORAGE_INCOMPLETE"`;
   - the tool's comments;
   - the P3-4 `RealStateGuard`;
   - the runbook header.

   The behaviour is correct and the block stays effective. The text is
   corrected only in the reviewed B-3 change.

## 5. PR-1B blocker state after this acceptance

| # | Blocker | State |
| --- | --- | --- |
| B-1 | `PR3_TOOLING_NOT_ACCEPTED` | **CLOSED** by §1 |
| B-2 | open risks not acknowledged | open |
| B-3 | source-level real-acceptance block (plus the guard and runbook text) | open. Requires a separate reviewed change before M-B1 |
| B-4 | K-ROOT custody and the M-B8 pin-copy location | open |
| B-5 | PR-1B not authorized | open |

`evaluate_eligibility` would now report `OPEN_RISKS_NOT_ACKNOWLEDGED` and
`PR1B_NOT_AUTHORIZED`. B-3 and B-4 are review blockers outside that
function. **`PR1B_NOT_ELIGIBLE`.**

## 6. Nonclaims

This acceptance does **not**:

- create record 1 or any acceptance envelope;
- make owner freshness `CURRENT`. Real freshness remains
  `FRESHNESS_UNKNOWN`;
- lift `REAL_ACCEPTANCE_ENABLED`, or change any source, guard, or runbook;
- create K-ROOT, K-WIT, a registry, a ledger, witness state, a hold, a
  RecoveryEpoch, INITIAL_CUSTODY, or any other authority or custody state;
- accept the dependency contracts outside §2;
- authorize PR-1B, A1–A7, or First Memory.

## Explicitly not done

```text
NO DEV CONTACT
NO DEV MUTATION
NO OWNER REPLICA CONTACT
NO REAL RECORD 1
NO ACCEPTANCE ENVELOPE
REAL_ACCEPTANCE_ENABLED UNCHANGED (False)
REAL FRESHNESS REMAINS UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
