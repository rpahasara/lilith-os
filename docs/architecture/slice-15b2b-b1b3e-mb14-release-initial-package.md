# Slice 15B2b-B1b-3e: M-B14 `release-initial` ceremony package (DEV_SYNTHETIC)

**Status:** PACKAGE PREPARED FOR OWNER REVIEW. Repository only. Nothing here ran against DEV.
M-B14 is **not authorized**: the earlier authorization ended with the 2026-10-19 STOP and does not carry over.
`CUSTODY = HELD`, `AUTHORITY = DARK`, `REGISTRY V1 = NOT EFFECTIVE`, `FIRST MEMORY = NONE`.

```text
package prepared != owner review != M-B14 authorization != RELEASED != FULL_READINESS (M-B15) != authority
```

## 1. Why this package exists

On 2026-10-19 the owner authorized M-B14. Execution stopped before any DEV contact
(off-host record `C:\Users\edufo\lilith-mb14-stop-0457b03\STOP.md`, `7fc6ad93…`), for these reasons:

- M-B14 had no reviewed operator. The M-B13 record says it is "not prepared".
- The release CLI reads its input document from a host path, and no reviewed delivery existed.
- Nothing derived the expected RELEASED bytes before execution.
- No post-release judge existed.

This package closes those gaps. It changes nothing in the accepted protocol, the hold store, the release CLI or the
installed release `129f2be`.

| Gap | Closed by |
| --- | --- |
| reviewed operator, one go, one marker, fail closed | `tools/mb14_operator.py` (§4) |
| input-document delivery on DEV | fixed root-only staging inside the single invocation (§3) |
| expected RELEASED bytes before execution | `expected_released` / `EXPECTED.json` (§2) |
| independent post-release verification; HELD evidence off-host | `post` read-back (§5) |
| ceremony vs HELD-bytes wording | §6 (reconciliation, no protocol change) |
| which pins survive the release | §7 |

## 2. Expected records (derived before execution)

The writer is `HoldStoreV1.release_initial` (`services/authority-dev/lilith_authority_root/hold_store.py`). It works
under the exclusive store lock:

1. It re-runs the package in `HOLD_RELEASE_ELIGIBILITY` mode and refuses unless the result equals the approved digest
   (`pr1_acceptance.release_decision`).
2. It refuses unless the witness head is still on the genesis registry.
3. It writes **one** `CeremonyHoldV1` with the same fields as the HELD record, except:
   - state `RELEASED`;
   - reason `OWNER_RELEASE_AFTER_ELIGIBILITY`;
   - `observedWitnessDigest` = the witness head.
4. It publishes under the same name (`_publish`: scratch in the parent, fsync, rename into `holds`, fsync both
   directories).

The operator derives the expected record two independent ways and requires them to agree:

- **Stdlib:** from the M-B10 pinned HELD (`mb10_held_verifier.pinned_expected_held`, pinned `73a8fe9a…`).
- **Release contract:** `successor_custody.CeremonyHoldV1`, `hold_record_bytes` and `hold_record_name`, with the
  step checked by the writer's own rule (`hold_store_transition_reason`).

It also requires both listing digests to equal the contract's (`pr1_acceptance.hold_listing_digest`). The HELD
listing must equal the digest the live M-B12 package reported. Any difference is a STOP before a go can be rendered.

| | HELD (now, M-B10) | RELEASED (expected after M-B14) |
| --- | --- | --- |
| name | `1ee1b7d5797b9c39b941befbbe4a5917b7fe510fa48a0f487f801246f80071d6.json` | the same name (replaced in place) |
| ceremony | `dev.initial-custody.test-only.dev-synthetic.actor.b1b3d.1`, `INITIAL_CUSTODY` | the same |
| state / reason | `HELD` / `INITIAL_CUSTODY_BOOTSTRAP` | `RELEASED` / `OWNER_RELEASE_AFTER_ELIGIBILITY` |
| predecessor / successor | `null` / `test-only.dev-synthetic.actor.b1b3d.1` | the same |
| `observedWitnessDigest` | genesis `ac892dc2…65e4` | witness head = genesis `ac892dc2…65e4` (chain length 1) |
| bytes (RFC 8785) | 421, SHA-256 `c713ea1d2e0b016e59eb55ddc1a125561495ed4cc0a2c24764f36c8355d0216d` | 431, SHA-256 `bb7576f4437fb61dd31adafe50ac56eba467c7f98b329b7149942e630f1ef003` |
| hold listing digest | `ee7aaa61c2e52d1aa8bb2c2a5c086e1d85a4b432df20cbb78a60f88495df6a82` (= the M-B12 evidence) | `c4cb131983b450d1e931d1121e5b125a98c2dc1625934db0ff0a5f3f661e195c` |

The RELEASED digest and listing are pinned in the operator (`EXPECTED_RELEASED_SHA256`,
`EXPECTED_RELEASED_LISTING`). The derivation must reproduce them.

## 3. Input-document delivery (bounded)

The CLI form is `lilith-authority-hold-dev release-initial <approvedPackageDigest> <inputs.json>`. It reads the
document with `read_regular`: a regular file, `O_NOFOLLOW`, at most 256 KiB. So a pipe, `/dev/stdin` or a symlink is
refused, and the document must be a real file.

It cannot go beside the hold store: the hold parent must contain only `holds`, or the writer refuses with
`HOLD_PARENT_UNEXPECTED_ENTRY`.

| Property | Value |
| --- | --- |
| document | the verifier input document `owner_inputs(envelope)` from the accepted envelope `3128a0a8…`, exactly as the `package` form passes it, as sorted compact ASCII JSON plus LF |
| path | `/run/lilith-mb14-release-initial/inputs.json` (tmpfs; outside every custody, witness, credential, preservation-set and DR-5 path) |
| mode | directory created new as root `0700`; file root `0600` (`umask 077`) |
| transport | the pinned direct-plink stdin route, base64; payload SHA-256 checked first (exit 96) |
| preconditions | the directory must not exist (exit 95); the written file must hash to the prepared document (exit 93, then removed) |
| lifetime | created, used by exactly one CLI invocation and removed **within the same remote invocation**; the CLI exit code is returned |
| residue | the read-back reports the path. If present, only `unstage` (its own owner statement and marker, digest-checked) removes it |

## 4. Operator and owner acts

The operator is `services/owner-memory-control/tools/mb14_operator.py`. It subclasses the pinned E-22 operator
(`7a04d456…`) and reuses, unchanged: its transports, go check, marker, record helpers, owner-inputs reader and
read-only `package` form.

| Form | DEV | Effect |
| --- | --- | --- |
| `pins` | none | clean control; every pinned tool exact; this operator at control |
| `prepare <envelope>` | none | new workdir: `envelope.out`, `inputs.json`, `EXPECTED.json`, `PREPARED.json` |
| `pre` | read-only | `hold observe` = expected HELD; staging path absent; signer `efbc0784…` / 128648; ONE `package` re-run = `eab79d56…`, mode `HOLD_RELEASE_ELIGIBILITY`, reasons `[]`, witness CONSISTENT, chain 1, head = genesis, package hold = HELD with listing `ee7aaa61…` |
| `render GO` | none | the canonical go text, bound to the control, operator, `PRE.json`, input digest, expected HELD and RELEASED |
| `release <go>` | **one write** | go = the canonical text; a fresh read-only gate (HELD exact, staging absent, signer exact); marker `mb14` (`O_EXCL`, before the invocation); ONE remote invocation (§3); then `post` |
| `post` | read-only | the independent read-back (§5) |
| `render ACCEPT` / `accept` | none | the owner's verbatim acceptance; adds the adoption line when the writer's response was not received exactly |
| `render UNSTAGE` / `unstage` | one removal | only after a read-back found the staged document |

Owner acts, each its own text and none implied by another:

- **GO** authorizes the one write and acknowledges the point of no return.
- **ACCEPT** accepts M-B14 and authorizes nothing further.
- **UNSTAGE** permits only removing the staged document.

**Fail closed.** Every outcome after the marker consumes the go: REFUSED, a non-zero exit, a traceback, a timeout,
SSH loss or unexpected output. There is no retry and no second invocation path. The read-back decides:

| `release` result | Read-back | Meaning / next |
| --- | --- | --- |
| `MB14_RELEASED_EXACT` | `RELEASED_EXACT`, staging absent, signer unchanged; the CLI returned exactly the expected record | owner `ACCEPT` |
| `MB14_RELEASED_ADOPTION_REQUIRED` | `RELEASED_EXACT`, but the CLI response was not received exactly | owner `ACCEPT` with the adoption line |
| `MB14_STOP:…NOT_WRITTEN` | exactly the HELD record | go consumed; nothing written; a new go needs a new owner decision |
| `MB14_STOP:…RELEASED_STAGING_RESIDUE` | RELEASED exact, staging document left | owner `UNSTAGE`, then `post` |
| `MB14_STOP:…STOP_C19` | unobservable (for example the writer's scratch in the parent), malformed, misbound, extra entries, or a changed signer | **C-19 MANUAL_RECOVERY_REQUIRED**: the root observer decides HELD vs RELEASED; never recreate; ambiguous = STOP; owner review |

## 5. Independent post-release verification

`post` runs three read-only invocations, each with its own transcript:

1. The release's own complete root observer (`lilith-authority-hold-dev observe`, shared lock).
2. The staging path.
3. `systemctl show` for the signer and witness.

The operator does not trust the writer's response. It decodes the observer's wire snapshot and compares it, byte for
byte, with `EXPECTED.json`. It recomputes the listing digest and requires it to equal both the observer's and the
expected digest. Only one entry, with exactly the expected RELEASED bytes, is `RELEASED_EXACT`.

**HELD evidence off-host.** After the release the HELD bytes exist on no host. They are retained in:

- the M-B10 evidence;
- the M-B12 / M-B13 records (listing `ee7aaa61…`);
- this workdir: `EXPECTED.json` holds the full HELD bytes, and `pre/*/observe.out` holds the observed HELD snapshot.

The workdir is sealed with `SHA256SUMS` as the off-host execution record.

## 6. Reconciliation: retaining the ceremony vs retaining HELD bytes

The records use these phrasings:

- RR-40: HELD is "never deleted, recreated or re-bound".
- Preflight §27: "forward only; never deleted or recreated".
- Sequencing: "Once HELD exists it is never deleted, recreated, or re-bound".

Read with the accepted contract (`hold_transition_reason` and `hold_store_transition_reason`), these mean:

- the **ceremony's record** never leaves the store ("no record may disappear: absence is never a release");
- a ceremony is never recreated from missing or re-bound to another witness or key;
- `HELD -> RELEASED` is the one permitted forward step **of that record**, under its fixed name;
- RELEASED never returns to HELD.

They do not mean that the HELD **bytes** stay on the host. One record per ceremony, replaced in place, is the
accepted design (Source Prep B design §10.6 `CeremonyHoldV1`; `successor_custody.hold_record_name`: "one name per
ceremony"; `hold_store._publish`). This package keeps it and does not make the
store append-only. HELD bytes are retained off-host only (§5). No accepted text changes. This section is the
clarification.

## 7. Evidence pins across the release

**Stay valid.** These do not observe the hold-store content, so the release does not change them:

- K-ACT CURRENT `6a61c350…`, publication `d7647976…`, HEALTH key `dd13a1fb…`
- K-WIT `5d778701…` / blob `f8759370…`; anchors `bc5f00a7…` / `be360da2…`
- registry `46b0bfc5…` (digest `fa662721…`, not effective); ledger head `19bf…1630`
- witness genesis `ac892dc2…`, `chain/1.json` `252c3220…`
- release `129f2be` / manifest `fc7dbf08…`; signer `efbc0784…` / 128648; witness `8cbfbed2…` / 127192
- proof transcripts E-08 `7fe21378…`, E-23 `9d7599c7…`, OS_DENIAL, BROKER_PRESERVATION, the E-22 adjudication
- activation dark
- the E-22 DR-5 target 194 / 155 / 29. DR-5 only sees `holds` as a root-only directory it cannot read.

The P1B-10 hold denial proof checks the name and modes only. The name and the `0600` mode are unchanged, so it is
expected to pass, but a fresh run must prove it.

**Become historical (by design, consumed by M-B14):**

- the package digest `eab79d56…` and HOLD listing `ee7aaa61…` (`HOLD_RELEASE_ELIGIBILITY` over a RELEASED store is
  not READY);
- the HELD record `c713ea1d…`;
- every judge that requires HELD:
  - `mb10_held_verifier` `W10_1_HELD_EXACT` (it reports a RELEASED record as `W10_HOLD_SET_UNEXPECTED`, a HALT);
  - the W11 verifier and the M-B11 / E-22 `status` / `v0` / `post` forms built on it;
  - E-19 `PRESERVED_PINS` (`heldSha256`).

After the release these report HALT or mismatch. That is expected and is not drift.

**Must be newly established after M-B14:**

1. The RELEASED record `bb7576f4…` / listing `c4cb1319…`: by this package's read-back and the owner's acceptance.
2. A post-RELEASED read-only host judge (a W14 phase) for later verification and M-B15. Not in this package.
3. FULL_READINESS (M-B15), a separate milestone.
4. DR-5 EQUAL (expected unchanged) on the first deploy after M-B14.

## 8. Owner decisions still open

1. **Review and merge** this package (the control for a later sequence). No push, PR or merge without separate
   approval.
2. **Accept §6** as the reading of RR-40 (ceremony retained; HELD bytes off-host only).
3. **Accept the staging path and handling (§3)**, a transient root-only file under `/run`.
4. **Freeze for the sequence.** Between `pre` and `release` there must be no merge, deploy, restart or upgrade.
   Unlike M-B10 there is no D1 opening form here. The `pre` re-run plus the fresh gate inside `release` are the
   freshness boundary. Any merge after `pre` means a new `pre` (and DR-5 for its deploy).
5. **A fresh M-B14 authorization** (the `GO` text) after review.
6. **Whether M-B15 needs the W14 judge** (§7 item 2) before it can be prepared.

## 9. Tests

`services/owner-memory-control/tests/test_b1b3e_mb14_release_initial.py` (18 tests) covers:

- derivation (stdlib = contract = pins; writer rule; listings);
- the read-back judge over the real snapshot wire form;
- the real staging command in a local shell (paths substituted, `sudo -n` removed): staging, exactly one CLI call,
  removal, exit-code propagation, refusals 95 / 96;
- the operator flow: exact, refused, response lost (adoption), misbound (C-19), staging residue (UNSTAGE), a changed
  go or gate never consuming the attempt;
- pins.

The WSL baseline is the full owner-memory-control suite.
