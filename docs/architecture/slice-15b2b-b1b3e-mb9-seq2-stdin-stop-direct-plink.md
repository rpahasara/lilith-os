# Slice 15B2b-B1b-3e — Package B Sequence 2: Owner Stop (Verifier Stdin Integrity Refusal), Diagnostics R-B2 … R-B4 and Remediation R-B5 (2026-10-08 / 2026-10-09)

Status:

- **`PACKAGE_B_SEQUENCE_2 = OPENED THEN STOPPED BEFORE M-B9a / HISTORICAL / NON-REUSABLE`.** B1 was recorded on
  control `103efe50d42ea8f016d671d8ee5f052b9ce961ae` (the R-B1 merge). During opening evidence the first live use
  of the R-B1 stdin transport returned the integrity refusal (exit 96) for all three verifier bundles. The owner
  stopped the sequence with the canonical pre-M-B9a stop (§2, verbatim; Package B record §10.8).
- **No B2, no attempt marker, no witness mutation.** M-B9a and M-B9b were never authorized or attempted. The
  witness was never started; witness genesis is not committed; record 1 is absent; the signer was not started;
  authority is not active.
- **The sequence-2 freeze is RELEASED by the stop**; the release authorizes no deployment, merge or DEV change.
  **The control selection of `103efe5` is CONSUMED** and is not reusable. All sequence-2 evidence is HISTORICAL /
  NON-REUSABLE.
- **Owner-authorized diagnostics R-B2 … R-B4 (§4)** found the cause: on the owner's Windows workstation `gcloud
  compute ssh` hands its SSH client the two bytes `y\n` instead of the caller's stdin, and the same SSH client,
  launched directly over the same IAP tunnel, carries stdin exactly.
- **Remediation R-B5 is repository-only (§5).** The three read-only verifier bundles (M-B6, W8, W9) now ride the
  stdin of a directly launched, hash-pinned PuTTY `plink` with a pinned key, OS Login user, host alias and host key
  (Package B record §8.2). Every other form and every mutation keeps the reviewed `gcloud compute ssh` command.
  Only `mb9_operator.py` changes among the tools; every verifier source and tool pin is unchanged.
- **R-B4 proved the raw byte route only. The full verifier wrapper has NOT been exercised live over direct plink.**
  Its first live use belongs to a future fresh Package B opening sequence.
- **Nothing is authorized by this record**: not its merge, any deploy, any DEV contact, a new Package B sequence or
  B1, B2, M-B9a, M-B9b, witness start, witness genesis, record 1, the signer, authority activation, First Memory or
  PROD. `FRESHNESS=UNKNOWN`.

```text
transport fixed in source != transport proven live;  raw stdin EXACT (R-B4) != verifier wrapper proven
gcloud compute ssh stdin (Windows) = "y\n", never the caller's bytes;  direct plink = the caller's bytes (R-B4)
R-B5 merged != new control != new B1;  sequence 2 evidence != eligibility evidence for any later sequence
```

## 1. Sequence 2 (historical)

| Item | Value |
| --- | --- |
| control (selected, now CONSUMED) | `103efe50d42ea8f016d671d8ee5f052b9ce961ae` (PR #172 merge, R-B1) |
| post-R-B1 preservation deploy | `37813766810`, `EQUAL` under `OWNER_INPUTS_INSTALLED_EXACT` (`3640ca01…`, `d05aa017…`, `f5087042…`), owner-accepted |
| owner preservation / control-selection acceptance SHA-256 | `98466cc306e135700c340724189bbcc0eed2056fab98b32c8c400a4300fd741f` |
| preservation evidence seal | `048f46e81fe78fa4ca0e0b941afe92c8f7d0fd1228f2bc53172658a4667e9c2f` |
| B1 statement SHA-256 | `a841b70ebef4ad9a5fbdfbde047bab5ed3e741c972d9f8c9eee49189790735f7` |
| B1 record SHA-256 (`B1_SEQUENCE_AUTHORIZATION.json`) | `3a9bd61ba39103b899fc18fbdbd0f305105c96cc7a5dca1f71aff035792313c1` |
| operator (sequence 2; SUPERSEDED by R-B5, must not be used) | `mb9_operator.py` SHA-256 `1a91bb2b0258cbec0028346ceede9c6e43135d556756fffe4f8696da66abbc29` |
| B1 recorded | 2026-10-08T17:27:26Z (`open-sequence` → `PACKAGE_B_SEQUENCE_OPENED_READ_ONLY`) |
| opening evidence collected | pins `MB9_TOOL_PINS_EXACT`; boundary (main = control, last deploy `37813766810`, queue empty); cloud 13/13 captured (non-audit captures byte-equal to Package A; audit `actAs` only); `host PRE` 17:29:25–17:30:36Z |
| `host PRE` | `MB9_HOST_PRE_NOT_PASS`: identity, custody, readiness, status, preservation, observer, W5 exit 0 and without drift (boot `eea461c3…` unchanged, `REBOOT_REQUIRED` absent, `readinessExact`, no `/tmp` residue); **M-B6, W8 and W9 verifier reads exit 96 with empty stdout and stderr** |
| not collected | P1B-5 / P1B-6 / P1B-8, candidate reproduction, P-A, Replica A, P-B, Replica B, `KNOWN_EMPTY`, DR-5 target derivation |
| owner stop | 2026-10-08T17:44:18Z, canonical §10.8 text (§2), `stop-sequence` → `PACKAGE_B_SEQUENCE_STOPPED_BEFORE_MB9A` |
| stop record SHA-256 (`B1_SEQUENCE_STOPPED.json`) | `6e2edcaba87c48f47309a33bb04955e6e11e0e84399480dc08835eb937aff465` |
| evidence seal | `dfdba43b817b354ebb181e3947e9797f211def4bb40288222871fc4764f26649` (local, outside the repository) |

Exit 96 is the remote digest gate (`B=$(cat)` hashed against the digest in the command) or the M-B6 loader's pin
gate; with empty output the two cannot be told apart. Both refuse before decoding and before `sudo`, so **no
verifier ran on DEV**. W9 was classified `UNKNOWN` (`UNCLASSIFIED_STOP` / `STOP_OWNER_ADJUDICATION`), never absence
or success.

## 2. Owner stop (verbatim)

SHA-256 `0b1912420f0b50a6a7c05f46d69dca93cfcb392442d71adb2bb97aa9647e2b46` (byte-identical to the rendered §10.8
template; it passed the operator's verbatim line check):

```text
I stop this Package B sequence now, before M-B9a, for this current DEV_SYNTHETIC sequence only.
Control commit: 103efe50d42ea8f016d671d8ee5f052b9ce961ae. B1 record SHA-256: 3a9bd61ba39103b899fc18fbdbd0f305105c96cc7a5dca1f71aff035792313c1.
Operator: services/owner-memory-control/tools/mb9_operator.py SHA-256 1a91bb2b0258cbec0028346ceede9c6e43135d556756fffe4f8696da66abbc29.
No B2 was issued, no M-B9a or M-B9b attempt marker exists, and no witness mutation was made by this sequence.
This sequence is OPENED THEN STOPPED BEFORE M-B9a / HISTORICAL / NON-REUSABLE; its evidence is preserved and must not be replayed into a later sequence.
The Package B deployment freeze of this sequence is RELEASED by this stop; the release authorizes no deployment, merge or DEV change.
The selected Package B live control 103efe50d42ea8f016d671d8ee5f052b9ce961ae is CONSUMED by this sequence and is not reusable.
This stop authorizes nothing further. A new sequence needs a new merged control, a fresh preservation deploy, a new owner control selection and a new canonical B1.
```

## 3. Transport history (append-only)

| Step | Finding |
| --- | --- |
| R-B1 (sequence 1, [record](slice-15b2b-b1b3e-mb9-seq1-w9-transport-stop.md)) | The W9 bundle inside one `gcloud --command` argument (43688 characters) exceeded the Windows command-line limit (32767; `WinError 206`) before any W9 DEV contact. R-B1 moved the bundles to the remote command's stdin. |
| sequence 2 (§1) | The first live stdin use: all three bundles refused with exit 96 and empty output. |
| R-B2 diagnostic | Over the same `gcloud compute ssh` route, a no-sudo `python3` reader received exactly `79 0a` (`y\n`, SHA-256 `3bb2abb69ebb27fbfe63c7639624c6ec5e331b841a5bc8c3ebc10b9285e90877`) for payloads of 1024, 19273 and 42273 bytes: `WINDOWS_GCLOUD_STDIN_RAW_TRANSPORT = NOT_EXACT`. |
| R-B2 feasibility | A compressed command-line transport cannot fit W9: raw LZMA2 (extreme) + base85 is 32295 characters and the rendered gcloud command 34009 (> 32767): `R_B2_COMPRESSED_COMMAND_TRANSPORT = INFEASIBLE_FOR_W9`. |
| R-B3 discovery (local only) | The installed Cloud SDK 581.0.0 source establishes the producer: with the PuTTY suite on Windows and `ssh/putty_force_connect` (default True), `SSHCommand.Run` passes `in_str='y\n'` with `-legacy-stdio-prompts`, and `execution_utils` writes it to the client's stdin pipe and closes it; the caller's stdin never reaches the client: `GCLOUD_Y_NEWLINE_SOURCE = PROVEN_PUTTY_FORCE_CONNECT_STDIN_INJECTION`. A `--flags-file` cannot help: the client receives the remote command inline (`GCLOUD_FLAGS_FILE = NOT_SUFFICIENT`). |
| R-B4 probe | After one read-only OS Login profile read, the SDK's own `plink.exe`, launched directly with `-batch -noagent`, the pinned host key, the existing key and the SDK-built IAP `-proxycmd`, delivered 1024, 19273 and 42273 bytes with exact counts and SHA-256, exit 0, empty stderr, no prompt: `DIRECT_PLINK_STDIN_RAW_TRANSPORT = EXACT_FOR_PROBE_SET`. This proves the raw byte route only. |

Local evidence seals (outside the repository): R-B2 diagnostic `161f8559ff66dfc00820e02f9ce8dbd65966ed61b8c7e580916e86a72ef4ba76`,
R-B2 feasibility `528dd099d1db4401c35cbb883343d28532ab923e86c6a995456d16bffb0932fb`, R-B3
`e70e0c677a24d47308a0574fa8bee8d856ae9d9280cdbecf4ecac205d020316f`, R-B4
`0bf4ad2e7862bc2bcca3b011ee264bcecfe53feed5d36a85045b90935bf041bd`. None of the diagnostics changed an SSH key, OS
Login, metadata, IAM or DEV state, used sudo or created a remote file.

## 4. Bindings established by R-B4

| Binding | Value |
| --- | --- |
| OS Login POSIX user (the only account, primary) | `ravindupahasara2_gmail_com` (uid / gid `476420618`, home `/home/ravindupahasara2_gmail_com`) |
| key | the existing `~/.ssh/google_compute_engine.ppk`; public blob SHA-256 `e830598a20880490d8b1644d48a448e600503367d3ab130d051e67d2a6e1a12e` (= `google_compute_engine.pub`), already in the OS Login profile; nothing imported |
| host alias | `compute.7687007163730582258` (the alias `gcloud` uses for `lilith-dev-01`) |
| host key | ed25519 `SHA256:XfNINpbMvAzlla6rma0q+whKd6UT12C4Fhc0mpOrEXU` (the single cached PuTTY entry for that alias) |
| client | Cloud SDK 581.0.0 `bin/sdk/plink.exe` (PuTTY release 0.83), SHA-256 `7308e9d356f14aa1f08cab1af363f71a077bf35dcb49e50b363418044758cd1e` |
| tunnel | `-proxycmd`: the operator's gcloud prefix + `compute start-iap-tunnel lilith-dev-01 %port --listen-on-stdin --project=lilith-agent-260823-27389 --zone=asia-southeast1-b --verbosity=warning`, escaped exactly as the SDK escapes it |
| hostname guard | `test "$(hostname)" = lilith-dev-01 \|\| exit 97` |

## 5. Remediation R-B5: the read-only verifier client is direct plink

The Package B record §8.2 is the rule. In `mb9_operator.py`:

- `remote_bundle` (the only path of the M-B6, W8 and W9 verifier bundles) calls `plink_stdin`; `ssh_stdin` (the
  `gcloud compute ssh` stdin channel) is removed, so no fallback to it exists.
- `plink_argv` builds `[<LILITH_MB9_PLINK>, -ssh, -T, -batch, -noagent, -hostkey <pin>, -i <ppk>, -proxycmd <IAP>,
  ravindupahasara2_gmail_com@compute.7687007163730582258, <guarded command>]`. Before any launch it requires
  `LILITH_MB9_PLINK` to be set and its file to hash to the client pin, and the PPK's public blob to hash to the key
  pin. `-legacy-stdio-prompts` is never passed and no code writes anything but the bundle to the client's stdin.
- The remote command is the R-B1 command unchanged: the hostname guard, `B=$(cat)`, the bundle SHA-256 gate (exit
  96), then the unchanged M-B6 loader with every module pin (exit 96). No remote file, no new sudo.
- A plink exit 0 with anything on stderr becomes `TRANSPORT_STDERR_EXIT` (95): never a PASS.
- The W5 verifier, identity, custody, readiness, status, preservation, observer, denial proofs and every mutation
  (`witness-state`, the two starts, `bootstrap`, removal, restart, health, read, chain export) keep the reviewed
  `gcloud compute ssh` command byte for byte.

| Failure | Result |
| --- | --- |
| `LILITH_MB9_PLINK` unset, unreadable or not the pinned client | STOP `PLINK_UNSET` / `PLINK_UNAVAILABLE` / `PLINK_PIN_MISMATCH` before launch |
| PPK missing, malformed or not the pinned key | STOP `PPK_UNAVAILABLE` / `PPK_MALFORMED` / `PPK_KEY_MISMATCH` before launch |
| non-ASCII or control character in the tunnel command | STOP `PROXYCMD_BAD_CHARACTER` before launch |
| host-key mismatch, prompt, authentication, IAP or SSH failure | plink exits non-zero under `-batch` → verifier failure (`VERIFIER_FAILED` / `NOT_PASS`, UNKNOWN) |
| timeout (900 s) | raised, never retried or absorbed |
| digest or module pin mismatch | exit 96 → verifier failure |
| hostname guard | exit 97 → verifier failure |
| stderr on a clean exit | exit 95 → verifier failure |
| malformed verifier output | `VERIFIER_FAILED` (unchanged) |

Operator prerequisites on the owner's workstation: `LILITH_MB9_PLINK` = the path of the Cloud SDK `plink.exe`
(pinned above); the existing `~/.ssh/google_compute_engine.ppk`; `LILITH_MB6_GCLOUD` as before. R-B4 proved the
tunnel with the backslash form of the SDK paths (`C:\\Users\\…\\python.exe`, `…\\lib\\gcloud.py` in the JSON);
using that form keeps the tunnel command byte-identical to the proven one.

| Tool | SHA-256 |
| --- | --- |
| `mb9_operator.py` after R-B1 (sequence 2; superseded) | `1a91bb2b0258cbec0028346ceede9c6e43135d556756fffe4f8696da66abbc29` |
| `mb9_operator.py` after R-B5 | `066fc8213b40c392e3e2bfd609da4a7f2a4e0b6f05da011daee9add3caf13973` |

## 6. Validation (repository only)

| Check | Result |
| --- | --- |
| Package B suites, Windows (`test_b1b3e_mb9_direct_plink_transport`, `_package`, `_w9_transport_and_stop`) | 107 run, OK (20 skipped: POSIX-only) |
| Package B suites, WSL Ubuntu 24.04, root / non-root | 107 OK / 107 OK (15 skipped) |
| full `services/owner-memory-control/tests`, WSL root / non-root | 1293 OK (15 skipped) / 1293 OK (29 skipped); the base `103efe5`: 1274 / 1274 OK |
| full `services/authority-dev/tests`, WSL root / non-root | 241 OK / 241 OK (= the base) |
| full suites, Windows | the same 17 (owner-memory-control) and 8 (authority-dev) environmental import errors as the base `103efe5`; no new failure |
| fake-plink integration (a real child process; bundle > 2 × 32767 bytes on stdin, argv < 4000 characters) | OK on Windows and WSL; the end-to-end gate case (POSIX bash) OK in WSL |
| `scripts/validate_repository.py`, `compileall`, `git diff --check` | PASS |
| tunnel command for the R-B4 gcloud prefix | byte-equal to the one R-B4 proved |
| every Operator method and owner text except the bundle client | byte-identical to R-B1 (`1a91bb2b…`) |

No live system was contacted during implementation or validation.

## 7. Required order (none authorized here)

```text
R-B5 PR merge (separate owner decision)
-> merge-triggered DEV deploy (preservation)
-> fresh OWNER_INPUTS_INSTALLED_EXACT verification and DR-5 EQUAL comparison
-> owner preservation acceptance
-> new Package B live-control selection
-> new canonical B1 (binding the R-B5 operator SHA-256)
-> complete opening evidence from scratch
-> first live direct-plink M-B6 / W8 / W9 verifier reads
-> B2 closing gate
-> separate owner B2 GO
```

## 8. State

```text
PACKAGE_B_SEQUENCE_1 = STOPPED / HISTORICAL / NON-REUSABLE
PACKAGE_B_SEQUENCE_2 = OPENED THEN STOPPED BEFORE M-B9a / HISTORICAL / NON-REUSABLE
PACKAGE_B_SEQUENCE_2_CAUSE = VERIFIER_STDIN_INTEGRITY_REFUSAL (EXIT 96) ON THE FIRST LIVE STDIN USE
W9 (SEQUENCE 2) = UNKNOWN
WITNESS_MUTATION = NONE
PACKAGE_B_FREEZE_SEQUENCE_2 = RELEASED (CANONICAL STOP; AUTHORIZES NOTHING)
PACKAGE_B_CONTROL_5ce067c = CONSUMED (NON-REUSABLE)
PACKAGE_B_CONTROL_103efe5 = CONSUMED (NON-REUSABLE)
OPERATOR_1a91bb2b = SUPERSEDED (MUST NOT BE USED)
WINDOWS_GCLOUD_STDIN_RAW_TRANSPORT = NOT_EXACT
GCLOUD_Y_NEWLINE_SOURCE = PROVEN_PUTTY_FORCE_CONNECT_STDIN_INJECTION
R_B2_COMPRESSED_COMMAND_TRANSPORT = INFEASIBLE_FOR_W9
GCLOUD_FLAGS_FILE = NOT_SUFFICIENT
DIRECT_PLINK_STDIN_RAW_TRANSPORT = EXACT_FOR_PROBE_SET
R-B5 = SOURCE AND TESTS READY FOR REVIEW; NOT MERGED
R-B5_DIRECT_PLINK_VERIFIER_TRANSPORT = NOT YET EXERCISED LIVE
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

At `FIRST_MEMORY_READY` the process stops and the owner is told before any First Memory content is selected,
drafted or written.
