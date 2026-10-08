# Slice 15B2b-B1b-3e — Package B Sequence 1: Owner Stop (W9 Windows Transport Limit) and Remediation R-B1 (2026-10-08)

Status:

- **`PACKAGE_B_SEQUENCE_1 = OPENED THEN STOPPED DURING OPENING EVIDENCE / TOOL_DEFECT / HISTORICAL /
  NON-REUSABLE`.** B1 was recorded on control `5ce067cf485cafed6ea2487635027955396e7844`. During opening evidence
  the W9 verifier read could not be launched on the owner's Windows workstation (`WinError 206`), **before any W9
  DEV contact**. The owner stopped the sequence (§2, verbatim).
- **No B2, no attempt marker, no witness mutation.** M-B9a and M-B9b were never authorized. The witness was never
  started; witness genesis is not committed; record 1 is absent; the signer was not started; authority is not
  active.
- **The sequence-1 freeze is RELEASED by the owner stop**; the release authorizes no deployment, merge or DEV change.
  **The control selection of `5ce067c` is CONSUMED** and is not reusable.
- **All sequence-1 evidence is HISTORICAL / NON-REUSABLE.** A later sequence collects its whole opening evidence
  again from scratch.
- **Remediation R-B1 is repository-only (§4, §5).** The verifier bundles move to stdin (Package B record §8.1), and
  a canonical owner pre-M-B9a stop is added (Package B record §10.8). Only `mb9_operator.py` changes among the
  tools; every verifier source and tool pin is unchanged.
- **Nothing is authorized by this record**: not its merge, any deploy, any DEV contact, a new Package B sequence or
  B1, M-B9a, M-B9b, witness start, witness genesis, record 1, the signer, authority activation, First Memory or PROD.
  `FRESHNESS=UNKNOWN`.

```text
B1 recorded != opening evidence complete != B2 eligible;  W9 UNKNOWN != W9 failed != witness state
owner stop (sequence 1) = an owner decision made before §10.8 existed;  §10.8 = the canonical rule from R-B1 on
transport fixed in source != transport proven live;  R-B1 merged != new control != new B1
```

## 1. Sequence 1 (historical)

| Item | Value |
| --- | --- |
| control (selected, now CONSUMED) | `5ce067cf485cafed6ea2487635027955396e7844` (PR #171 merge) |
| pre-opening preservation deploy | `37803630416`, `EQUAL` under `OWNER_INPUTS_INSTALLED_EXACT`, owner-accepted |
| owner control-selection acceptance SHA-256 | `7fa7e028c1cc36d316a175a4f6182f6a898b250f946c7bcf84e9a5f7bfeda9ba` |
| pre-opening evidence seal | `bacc0376240370d2d7dc7911d907c56492e181fb5c088242b9672d2b9cacb916` |
| B1 statement SHA-256 | `08d88e92405152f55c607e689e179ef35597801fe80674015784b77971005c2b` |
| B1 record SHA-256 (`B1_SEQUENCE_AUTHORIZATION.json`) | `6bea4e47e99c7aca55445bd7e6b8d55cec911ddce62fae45d86a886b640e7266` |
| operator (sequence 1; SUPERSEDED, must not be used) | `mb9_operator.py` SHA-256 `7f630ed3106d7d64351d0fe291004b9df651b1c937f83bd9503ec89369b862db` |
| B1 recorded | 2026-10-08T16:15:39Z (`open-sequence` → `PACKAGE_B_SEQUENCE_OPENED_READ_ONLY`) |
| `host PRE` | 2026-10-08T16:16:14Z–16:17:24Z |

**What happened.** An earlier free-form B1 did not contain the §10.1 template lines and was not recorded (the
operator's line check would have refused it); the owner then issued the canonical B1. After it was recorded:

- the Package B DR-5 targets were derived from the accepted post-M-B6 texts and equalled the record's pins (stopped
  `7f70aa3b…`, running `593c90e1…`);
- `host PRE` ran nine of its ten reads with code 0 (identity, custody, readiness, `status P1B-8`, preservation,
  observer, W5, M-B6, W8 `OWNER_INPUTS_INSTALLED_EXACT`); readiness exact including the owner witness CLI; boot id
  unchanged; `REBOOT_REQUIRED=absent`;
- the tenth, the W9 verifier, failed in the local client with `FileNotFoundError: [WinError 206] The filename or
  extension is too long`. Its bundle had been placed in one `gcloud compute ssh --command=` argument of 43688
  characters; Windows caps a command line at 32767. The W8 bundle (28062) had always fitted, which is why Package A
  never exposed the defect.

`W9 = UNKNOWN`. `DEV_W9_CONTACT = NO`. `WITNESS_MUTATION = NONE`. Cloud captures, the P1B-5 / P1B-6 / P1B-8 proofs,
P-A, Replica A, P-B, Replica B and `KNOWN_EMPTY` were not collected. The custody read also showed, for the first
time, `/run/lilith-recovery-witness` as a directory `root:lilith-authority-dev 0710`; it is recorded as an
observation only, because no W9 verdict exists for this sequence. A first copy into the laptop WSL scratch
directory `/root/mb9-seq1-20261008` failed on path quoting and was redone over stdin; that directory is laptop-local
evidence only.

## 2. Owner stop (verbatim)

The owner stop text SHA-256 (the text with its terminal LF):
`a08d3d08e72badb2652f74d8f43a27be37b889434d85d6a2dd864344c49bae2d`.

```text
OWNER ADJUDICATION
PACKAGE B SEQUENCE 1 STOP / PRE-M-B9a TOOL DEFECT

I stop Package B sequence 1 for DEV_SYNTHETIC now.

B1 was recorded on control:

5ce067cf485cafed6ea2487635027955396e7844

B1 record SHA-256:

6bea4e47e99c7aca55445bd7e6b8d55cec911ddce62fae45d86a886b640e7266

B1 statement SHA-256:

08d88e92405152f55c607e689e179ef35597801fe80674015784b77971005c2b

Package B operator:

services/owner-memory-control/tools/mb9_operator.py

SHA-256:

7f630ed3106d7d64351d0fe291004b9df651b1c937f83bd9503ec89369b862db

============================================================
SEQUENCE CLASSIFICATION
============================================================

PACKAGE_B_SEQUENCE_1 =

OPENED THEN STOPPED DURING OPENING EVIDENCE /
TOOL_DEFECT /
HISTORICAL /
NON-REUSABLE

Cause:

CLIENT_TRANSPORT_CONSTRUCTION_LIMIT_BEFORE_W9_DEV_CONTACT

The W9 verifier transport attempted to place approximately 43688 characters
into a Windows command-line argument whose platform limit is approximately
32767 characters.

The launch failed locally with WinError 206 before DEV was contacted for the
W9 read.

Therefore:

W9 =
UNKNOWN

DEV_W9_CONTACT =
NO

WITNESS_MUTATION =
NONE

B2 =
NOT AUTHORIZED

M-B9a =
NEVER AUTHORIZED

M-B9b =
NEVER AUTHORIZED

WITNESS =
NEVER STARTED

WITNESS_GENESIS =
NOT COMMITTED

RECORD 1 =
ABSENT

SIGNER =
NOT STARTED

AUTHORITY =
NOT ACTIVATED

FIRST MEMORY =
NOT AUTHORIZED

PROD =
NOT AUTHORIZED

No M-B9a marker was created or consumed.

No M-B9b marker was created or consumed.

============================================================
EVIDENCE PRESERVATION
============================================================

Preserve all evidence from this stopped sequence as historical evidence,
including:

C:\Users\edufo\lilith-packageb-seq1

and the laptop-local WSL scratch location:

/root/mb9-seq1-20261008

The failed W9 launch, partial opening evidence, B1 record and all related
state/evidence must not be rewritten as if this sequence never opened.

No evidence from this stopped sequence may be replayed as fresh eligibility
evidence for a later Package B sequence.

A future sequence must collect its complete opening evidence again from
scratch.

============================================================
FREEZE RELEASE
============================================================

The Package B deployment freeze declared by sequence 1 is released by this
owner stop.

PACKAGE_B_FREEZE_SEQUENCE_1 =

RELEASED /
OWNER DECISION /
AUTHORIZES NO DEPLOYMENT, MERGE OR DEV CHANGE BY ITSELF

This freeze release does not itself authorize any repository merge, deploy or
DEV mutation.

============================================================
CONTROL CONSUMPTION
============================================================

The Package B live-control selection:

5ce067cf485cafed6ea2487635027955396e7844

is CONSUMED by Package B sequence 1.

It is historical and NON-REUSABLE for a later Package B sequence.

A future Package B sequence requires:

1. a new merged control containing the reviewed transport remediation;
2. its merge-triggered preservation deploy;
3. fresh DR-5 preservation verification;
4. separate owner acceptance of that preservation;
5. a new Package B live-control selection;
6. a new canonical B1.

Do not treat the old control selection as merely dormant or automatically
revivable.

============================================================
REMEDIATION AUTHORIZATION
============================================================

This owner stop authorizes only preparation of a repository-only remediation
slice for the W9 client transport defect.

It authorizes:

- creating a dedicated worktree;
- creating a remediation branch;
- source edits;
- tests;
- documentation / record updates;
- local validation;
- commits;
- pushing the remediation branch;
- opening a PR.

It does NOT authorize:

- merging that PR;
- any deployment;
- any DEV contact;
- reopening Package B;
- B1 for a future sequence;
- M-B9a;
- M-B9b;
- witness start;
- witness genesis;
- Record 1;
- signer start;
- authority activation;
- First Memory;
- PROD.

============================================================
TRANSPORT REMEDIATION
============================================================

The preferred remediation is to stop transporting the W9 verifier bundle as
one command-line argument and instead transport the verifier bundle over stdin
or an equivalently reviewed channel that does not depend on the Windows
command-line length limit.

The remediation must preserve:

- exact verifier bundle integrity;
- module/tool pin verification;
- read-only W9 semantics;
- no witness socket contact by the verifier;
- existing timeout / SSH / ambiguity STOP behavior;
- no new mutation authority.

Do not reduce verifier coverage merely to make the command shorter.

Do not install/authenticate a new WSL gcloud environment as the workaround.

============================================================
NEW CANONICAL PRE-M-B9a STOP RULE
============================================================

The remediation PR must also add a canonical Package B pre-M-B9a stop rule.

The rule must cover the state where:

- B1 has been validly recorded;
- Package B freeze is active;
- opening evidence is incomplete, FAILED or UNKNOWN;
- B2 has not been issued;
- no M-B9a marker exists;
- no witness mutation has occurred.

In that state an explicit owner stop may:

- terminate the current Package B sequence;
- release that sequence's freeze;
- classify the sequence as historical / non-reusable;
- consume that sequence's selected control;
- preserve all evidence;
- authorize nothing further by implication.

The stop must never be available after M-B9a mutation begins merely as a way
to bypass the existing M-B9a classifier, removal, restart or recovery rules.

Add tests proving the exact boundary.

============================================================
REMEDIATION BRANCH
============================================================

Suggested branch:

ops/mb9-w9-stdin-transport-fix-v0.1

Do not modify the user's main checkout.

Do not perform live DEV verification while implementing the source fix.

============================================================
FUTURE ORDER
============================================================

After the remediation PR is eventually separately owner-authorized for merge,
the required order is:

remediation PR merge
→ merge-triggered DEV preservation deploy
→ fresh OWNER_INPUTS_INSTALLED_EXACT verification
→ fresh DR-5 EQUAL comparison
→ owner preservation acceptance
→ new Package B live-control selection
→ new canonical B1
→ complete opening evidence from scratch
→ B2 closing gate
→ separate owner B2 GO

No step in that future order is authorized by this stop decision.

============================================================
FIRST MEMORY
============================================================

FIRST MEMORY remains NOT AUTHORIZED.

FIRST_MEMORY_READY has NOT been reached.

When bootstrap eventually reaches FIRST_MEMORY_READY:

STOP and explicitly tell the owner before any First Memory content is
selected, drafted or written.
```

Sequence-1 evidence seal after the stop (`SHA256SUMS`, 52 entries, every file except the checkout copy):
`35e76e93f58dec7be47a2c51904af7f9613844369ebd2d4181493eab50f82af2`.

## 3. The defect

| Remote command built by operator `7f630ed3…` | Characters | Windows limit 32767 |
| --- | --- | --- |
| W9 verifier bundle (W5 + M-B6 + W8 + W9 verifiers) | 43688 | **exceeded** |
| W8 verifier bundle | 28062 | below |
| installer stream (`status`) | 27504 | below |
| witness denial proof stream | 6796 | below |

The defect is in the client transport only: the verifier, its read-only semantics, its pins and the host are not
involved, and nothing was sent.

## 4. Remediation R-B1: verifier bundles over stdin

Package B record §8.1 states the rule. In `mb9_operator.py`:

- `bundled` returns `(command, payload)`: the payload is exactly the bytes the previous command embedded (base64 of
  the gzip'd JSON `{module: source}`); the command carries `B=$(cat)`, the payload SHA-256 (exit `96` on mismatch),
  then the unchanged M-B6 loader with the per-module pins (exit `96` on mismatch);
- `ssh_stdin` has the pinned `ssh` guard, argv shape, capture and 900 s timeout and hands the payload to the client's
  stdin; `remote_bundle` is used only for the W5 + M-B6, W8 and W9 bundles (four call sites);
- nothing else changed: no verifier source or pin, no mutation command, no classifier, no owner text except the new
  §10.8 template.

| Item | SHA-256 |
| --- | --- |
| `mb9_operator.py` after R-B1 | `1a91bb2b0258cbec0028346ceede9c6e43135d556756fffe4f8696da66abbc29` |
| `mb9_operator.py` sequence 1 (superseded) | `7f630ed3106d7d64351d0fe291004b9df651b1c937f83bd9503ec89369b862db` |
| `mb9_witness_verifier.py` (unchanged) | `e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78` |

The operator SHA-256 is not a static pin in the Package B record: B1, B2 and B4 bind `<operator>` at runtime and the
operator refuses unless it equals the file at the control commit. A new sequence therefore binds the new value.

**Residual risk (stated, not hidden).** The stdin channel through `gcloud compute ssh` on Windows has not been
exercised against DEV: implementation was repository-only by owner rule. Its first live use will be the next
sequence's opening `host PRE`. Any alteration on the channel (lost, truncated, appended or CR-translated bytes)
fails closed with exit `96` before any verifier code runs (tested against the real shell and coreutils), which is a
STOP, never a false PASS.

## 5. The canonical pre-M-B9a stop (Package B record §10.8)

- **Available** only while B1 is recorded and the attempt directory is absent or empty (no B2 consumed, no M-B9a or
  M-B9b invocation). Opening evidence may be incomplete, FAILED or UNKNOWN.
- **Effect:** `B1_SEQUENCE_STOPPED.json` (create-only) with the control, the operator, the B1 record SHA-256 and the
  statement SHA-256; classification `OPENED_THEN_STOPPED_BEFORE_MB9A`; freeze `RELEASED`; control selection
  `CONSUMED`. Local only: no DEV contact.
- **After it:** `mb9a` and `mb9b` refuse `SEQUENCE_STOPPED`; a second stop refuses; the sequence cannot be reopened
  in place.
- **Never after a marker:** any file in the attempt directory makes the operator refuse
  `STOP_REFUSED_ATTEMPT_MARKER_PRESENT`; the W9 classifier, removal, restart and recovery routes govern.
- Sequence 1 was stopped by an owner decision **before** this rule existed; it is not retro-fitted with a
  `B1_SEQUENCE_STOPPED.json`.

## 6. Validation (repository only)

`test_b1b3e_mb9_w9_transport_and_stop.py`: the defect reproduced from the canonical W9 bundle; every verifier read
on stdin with its exact pinned bundle; every argv the operator builds (all `host` phases and every streamed tool)
below the Windows limit; the default runner hands the payload to stdin with the pinned capture and timeout;
timeout, SSH failure, refusal and unparseable output still STOP; stdin carries only verifier bundles while every
mutation keeps its command; the verifier and its pin unchanged; and, against the real bash and coreutils, a
synthetic bundle several times the limit delivered and loaded exactly, every channel alteration refused with `96`,
and the loader's pin refusal intact. The stop boundary: needs B1; records once; blocks `mb9a` / `mb9b`; refused
after a real `mb9a` marker and after any attempt file; binds control, B1 record and operator; authorizes nothing.

## 7. Required order (none authorized here)

```text
R-B1 PR merge (separate owner decision)
-> merge-triggered DEV deploy (preservation)
-> fresh OWNER_INPUTS_INSTALLED_EXACT verification and DR-5 EQUAL comparison
-> owner preservation acceptance
-> new Package B live-control selection
-> new canonical B1 (binding the R-B1 operator SHA-256)
-> complete opening evidence from scratch
-> B2 closing gate
-> separate owner B2 GO
```

## 8. State

```text
PACKAGE_B_SEQUENCE_1 = OPENED THEN STOPPED DURING OPENING EVIDENCE / TOOL_DEFECT / HISTORICAL / NON-REUSABLE
PACKAGE_B_SEQUENCE_1_CAUSE = CLIENT_TRANSPORT_CONSTRUCTION_LIMIT_BEFORE_W9_DEV_CONTACT
W9 (SEQUENCE 1) = UNKNOWN
DEV_W9_CONTACT = NO
WITNESS_MUTATION = NONE
PACKAGE_B_FREEZE_SEQUENCE_1 = RELEASED (OWNER DECISION; AUTHORIZES NOTHING)
PACKAGE_B_CONTROL_5ce067c = CONSUMED (NON-REUSABLE)
OPERATOR_7f630ed3 = SUPERSEDED (MUST NOT BE USED)
R-B1 = SOURCE AND TESTS READY FOR REVIEW; NOT MERGED
R-B1_STDIN_TRANSPORT = NOT YET EXERCISED LIVE
PRE_MB9A_STOP_RULE = DEFINED (PACKAGE B RECORD §10.8)
PACKAGE_B = NOT OPEN
B1 (NEW SEQUENCE) = NOT AUTHORIZED
B2 = NOT AUTHORIZED
M-B9a = NOT AUTHORIZED
M-B9b = NOT AUTHORIZED
WITNESS = NEVER STARTED
WITNESS_GENESIS = NOT COMMITTED
RECORD 1 = ABSENT
SIGNER = NOT STARTED
AUTHORITY_ACTIVATION = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
```
