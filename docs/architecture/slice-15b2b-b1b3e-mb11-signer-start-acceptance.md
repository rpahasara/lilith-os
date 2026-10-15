# Slice 15B2b-B1b-3e — M-B11 START_SIGNER: Completion and Owner Acceptance (2026-10-15)

Status:

- **OWNER ACCEPTANCE RECEIPT (APPEND-ONLY).** This file records the single M-B11 signer start on DEV, its POST11
  result and the owner's acceptance. It is also the canonical M-B11 ceremony record that the E-22 secret-hygiene scope
  names (§5).
- **The [operator record](slice-15b2b-b1b3e-mb11-signer-start-operator.md) and the
  [design record](slice-15b2b-b1b3e-mb11-signer-start-design.md) are not rewritten.** Their state blocks were correct
  when written. This receipt supersedes them on the start outcome only, from 2026-10-15T05:13:15Z.
- **The `mb11-start` attempt is CONSUMED.** No second start, retry, stop, restart, enable, daemon-reload or socket
  activation is authorized by this file or by anything else.
- **Writing this record contacted no live system.** The evidence stays in the owner's local evidence directory (§6).

```text
W11_1 observed + owner-accepted  !=  hold released  !=  Registry effective  !=  authority  !=  M-B12 PASS  !=  FIRST_MEMORY_READY
hold-release ELIGIBILITY READY  !=  full readiness READY (blocked by INITIAL_CUSTODY HELD)  !=  M-B12 package READY
```

## 1. Identities

| Item | Value |
| --- | --- |
| main / control | `4e583108c3a5b9e0690819135caedc3bcb5f3ec6` (PR #199 merge), clean control clone |
| last DEV deploy | run `38677320395`, success, completed 2026-10-15T03:44:07Z (no deploy since, before the start) |
| operator | `mb11_operator.py` `1ec09faea0a7b8c4f2eb58622a8119aa513c297057e9bda1dd9a8db49bf36bcd`; host tail `mb11_start_remote.py` `04461ffe4d30d443c49e5ef2d314972fda41a0b3b8dda1765609fb64c1cad72f` |
| release | `ba943e1a188d98f4108c9eec7149c0cf1a8f68bb` (E-19 NEW, sole installed) |
| restart boundary | P1B-10R plan `2a004a4195116462d60fdff978229f9a2364427704e4d16d5dec729801106592`, `P10R_2_EFFECTIVE_EXACT` (Option A) |
| witness (unchanged) | `90b28f9d06fd48a1a1bdc3ae39474fb1` / PID `69238` / NRestarts 0 |
| owner inputs envelope | `d48347216041520f9fe5a46f12de2127b79962c490fc4987d6bccf1da8d68834` |
| MB11-GO-START | `ea6e6a00791fe3d73959ab7312e5584f491018844e7efcf81fffdc8979e27546` (1313 B, LF), consumed |

## 2. Sequence (2026-10-15, UTC)

1. 03:51:53Z post-#199 preservation: host U5 PASS (`07-U5…`, all 11 reads rc 0, identical to `06` except clocks,
   P1B-10R overlay unchanged). DR-5 EQUAL `WITNESS_RUNNING_HELD_E19` against the deploy `38677320395` log
   (compare output `c008cd9c…`, 0 failures, 0 OLD-release lines).
2. 03:54:40Z `gate` `01-GATE`: `MB11_GATE_W11_0`, reasons `[]`, observation
   `bd67ac7283b271eaffd646fad5c0e0c7ea346e4cc9b56c5f8e51ff0c0934be9d`, ledger DB
   `fae62c87608cabede09c13a9db43709c831529166894ec30ee8e1c7e577da9d3`. `render` → the go above.
3. The owner ran `mb11_operator start` once:
   - fresh gate `02-START_PRE` at 05:13:15Z: `MB11_GATE_W11_0`, reasons `[]`, observation
     `78f614dfa43e3f650713224f62a0deb7d2485c0c08bf1cff2e8f03677ae6c236`, the same ledger DB, witness and envelope;
   - marker `attempts/mb11-start.json` (`startedAt` 05:13:15Z, `invocationsPermitted` 1);
   - ONE `sudo -n /usr/bin/systemctl start lilith-authority-dev.service`: rc 0, empty stdout and stderr;
   - ONE read-only POST11 (HEALTH capture + W11): rc 0, empty stderr.
4. `START.json` (`df1affb7…`): `MB11_START_REACHED_W11_1_SIGNER_STARTED_EXACT`, `startCode` 0, `kActLoadCount` 1,
   `postRouting` `SAFE_ADOPT`, `postReasons` `[]`, `postSha256` = SHA-256(`post.out`).

## 3. POST11 (`post.out` `ff9c8ce79147d61c01c4c4bf52f97b411e06fc1a1981989ad17e722b617b36d5`)

| Fact | Observed |
| --- | --- |
| W11 phase | `W11_1_SIGNER_STARTED_EXACT`, reasons `[]` |
| K-ACT loads after the gate cursor | 1 (journal: one invocation, credentials `LOADED`) |
| signer | `lilith-authority-dev.service` active/running, InvocationID `c7ba0fb7e2d84a0eb02a04ef0e83f67a`, MainPID 84806, NRestarts 0, uid/gid 995/985, cwd `releases/ba943e1…`; `Restart=no`, drop-ins loaded |
| HEALTH | `SERVICE_AVAILABLE`, `SIGNING_NOT_AVAILABLE`, readiness `NOT_READY` with the 3 structural reasons; same incarnation before and after |
| B4 = B3 | HEALTH public key SHA-256 `dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed` = expected B3 |
| root ELIGIBILITY (hold release) | `READY`, reasons `[]`, loaded-key binding PASS |
| root FULL | `NOT_READY`, reasons exactly `CEREMONY_HOLD:CEREMONY_HOLD_HELD` (hold detail `INITIAL_CUSTODY_BOOTSTRAP`) |
| W10 | `W10_1_HELD_EXACT` (signer judged separately), HELD `c713ea1d…`, witness unchanged |
| ledger | DB SHA-256 unchanged (`fae62c87…`) |
| authority | `authorityGranted` false, `authorityActive` false, `registryEffective` false, `issuanceAuthority` `NONE` |

The package reasons POST11 reported (with the owner envelope as built: no proofs, no PR-2, no PR-3) are the M-B12
baseline:

```text
E07 SIGNER_DENIAL missing   E08 DEPLOYER_DENIAL missing   E09 BROKER_DENIAL missing
E16 CEREMONY_HOLD_HELD      E17 READINESS_NOT_READY       E18 OFFHOST_MATERIAL_UNAVAILABLE
E20 PR-2 inventory absent   E21 PR-3 register absent      E22 SECRET_HYGIENE missing   E23 PRESERVATION_SET missing
```

## 4. Owner acceptance (2026-10-15, verbatim)

> I accept the verified M-B11 signer-start and POST11 evidence: W11_1_SIGNER_STARTED_EXACT, one K-ACT load, B4=B3,
> hold-release eligibility READY, full readiness blocked only by INITIAL_CUSTODY HELD, with authority and issuance
> remaining disabled. This acceptance authorizes no additional start, custody release, authority activation, First
> Memory, or PROD operation.

The owner independently re-verified the saved POST11 evidence locally before accepting (`RECEIPT=VERIFIED`,
`ATTEMPT=CONSUMED`, `POST11_LOCAL_RECEIPT=PASS`).

## 5. Source changes: the E-22 ceremony row and the `observe` form

`mb12_secret_hygiene_proof.CEREMONIES["M-B11"]` now names this record and the DEV window
`2026-10-15T05:13:15Z` – `2026-10-15T05:13:29Z`:

- start: the marker's `startedAt`, written before the one `systemctl start`;
- end: the write time of `START.json`, after POST11 returned (05:13:28.199Z local file time), rounded up to the next
  whole second. A later end only widens the journal coverage the proof requires.

No publication: the start publishes nothing. OD-M12-7 stays PROPOSED. `prove` still FAILS on the real table with
`SCOPE_DECISION_UNRESOLVED B1B3D-L2b` and `CEREMONY_WINDOW_NOT_RECORDED M-B9b` (tested). Pin cascade (bytes only):

| Tool | Was | Now |
| --- | --- | --- |
| `mb12_secret_hygiene_proof.py` | `251fb5409eb75693316c2dba560ea0c8446fe66e4e22a15d0a744350cc3b97de` | `29a7621993f98871568a76be166e31783f198a4ae34839672569aadcd9093fee` |
| `mb12_readiness_inputs.py` (`PRODUCER_SCRIPT_SHA256`) | `d325d07f9e2ba23b1c5d98e295d415275c8aab88d0d9c50ea8081f99eb19ce2b` | `a1c68c7e054d3f7cb2d5368e8772bbeb19d977e7552a5d770c4f0461696b0435` |
| `mb11_operator.py` (`TOOL_PINS`; + the read-only `observe` form, operator record §11) | `1ec09faea0a7b8c4f2eb58622a8119aa513c297057e9bda1dd9a8db49bf36bcd` | `43c2a6bfbcf16a4035d8c8c999193ab8279acdccbcc7f22486131fd2a8f62ac4` |

The re-pinned operator is spent for `start`: its `mb11-start` marker exists. `gate`, `render`, `start` and `current`
are unchanged.

**Post-deploy preservation from now on.** With the signer running, the E-19 host U5 path no longer applies (it
requires the signer inactive), and the E-19 DR-5 target is the stopped-signer text. The reviewed path is the new
read-only `mb11_operator observe` (`MB11_OBSERVE_W11_1_EXACT`; operator record §11), then
`mb11_dr5_target compare W11_1_SIGNER_STARTED_EXACT <deploy log>` against the derived running target
(194 `ff2468f0…` / 155 `4337f769…` / 29 `f5087042…`, NOT yet accepted: OD-M11-9). The first post-start deploy,
including the merge of this record, needs that path, owner-authorized, before anything else proceeds.

## 6. Evidence (owner-local)

`C:\Users\edufo\lilith-mb11-w11-gate-4e58310`: the original `workdir` (gates `01-GATE`, `02-START_PRE`, marker,
`steps/01-START`), the go text, and `SHA256SUMS` (`cf53b17c…`, pre-start). The post-start seal
`SHA256SUMS.seal-1-start` (`887bf151430b23abac6ea8a06b78c96410604d8d042d2778a00ac9f7a2452e42`) covers every workdir file
and the pre-start manifest. `workdir-copy` is not authoritative. Preservation evidence:
`lilith-e19-pr199-host-u5-4e58310` (`123878fe…`), `lilith-e19-pr199-dr5-4e58310` (`ad799739…`).

## 7. State (from 2026-10-15T05:13:28Z)

```text
M-B11 START_SIGNER = COMPLETED, OWNER-ACCEPTED;  ATTEMPT mb11-start = CONSUMED
SIGNER = RUNNING (c7ba0fb7… / 84806);  K_ACT_LOADS = 1;  RESTART_BOUNDARY = EFFECTIVE (Restart=no)
HOLD = INITIAL_CUSTODY HELD;  HOLD-RELEASE ELIGIBILITY = READY;  FULL READINESS = NOT_READY (hold only)
M-B12 = NOT PASSED (package NOT_READY, §3);  REGISTRY_EFFECTIVE = NO;  AUTHORITY_ACTIVE = NO;  ISSUANCE = NONE
FIRST_MEMORY_READY = NOT REACHED;  PROD = NOT AUTHORIZED
```

## 8. Addendum (2026-10-15): first post-start preservation and OD-M11-9

**Status: OD-M11-9 ACCEPTED by the owner on 2026-10-15, for the running signer only (§8.3, verbatim). Nothing else is
accepted or authorized by this addendum.**

### 8.1 Preservation after the PR #200 deploy (read-only; no DEV write)

| Item | Value |
| --- | --- |
| deploy | run `38690242990`, head `0bf0b8f5c0560308f0bce139debda9078104725c` (PR #200 merge), success, completed 2026-10-15T06:09:40Z; the latest `deploy-dev` run |
| deploy log | 399908 B, SHA-256 `323ff1a8edf45b71eb67a83973b1c4faa0f4201cff55847e40efee777e95a2e3` (owner copy = a fresh `gh run view --log`, byte-identical) |
| W11 phase (independent) | owner-authorized `mb11_operator observe` (`43c2a6bf…`) once, 2026-10-15T06:34:41Z (after the deploy): `MB11_OBSERVE_W11_1_EXACT`, reasons `[]`, `kActLoadCount` 1, `OBSERVE.json` `e7fedd6dfe36ac45c986d37e88475a0a859dd353941d17ea89e39f0920e8b341`, `remote.out` = `ff9c8ce7…` (byte-identical to the accepted POST11), rc 0, stderr empty |
| still exact at that time | signer `c7ba0fb7e2d84a0eb02a04ef0e83f67a` / 84806 / NRestarts 0; HEALTH key `dd13a1fb…` = B3; witness `90b28f9d…` / 69238, W10_1, HELD `c713ea1d…`; ledger DB `fae62c87…`; boundary reasons `[]`; ELIGIBILITY READY, FULL only `CEREMONY_HOLD:CEREMONY_HOLD_HELD`; authority, registry, issuance disabled |
| DR-5 | `mb11_dr5_target.py` (`775f43e84e1e58c2c9d1e8b4f2f32dc955462d034963b74761a133003a16daf3`) `compare W11_1_SIGNER_STARTED_EXACT <log>` → `EQUAL`, target `SIGNER_RUNNING_WITNESS_RUNNING_HELD`, allowed 0, fail 0, OLD-release lines 0, unequal `[]`; output SHA-256 `2b36271ad4c8a77f0ad5b763e894c2fe99aae044dc44c2fe6fcdd96b529112d4` (owner run, independently reproduced off-host) |

Observed sets = the derived pins: result set 194 / `ff2468f09fb6721de776c857e096fe485b2399e70fa6c5d37877179c4de47509`,
DR-5 block 155 / `4337f769d984876468379caf7b1ba59dd0d503344f942e30eedb912d2bd96c64`, pre-deploy block 29 /
`f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae`.

### 8.2 The derivation contract held

The design (§8 of the design record; `mb11_dr5_target` docstring) predicted that a running signer replaces exactly one
line, `DEFERRED_UNTIL_OBJECT_EXISTS: /run/credentials/lilith-authority-dev.service (later step)`, by
`DENIED: test -w`, `-r`, `-x` of that path (+2 in the result set and DR-5 block; pre-deploy block unchanged), on the
owner-accepted `WITNESS_RUNNING_HELD_E19` base (192 / 153 / 29). The pre-start deploy `38677320395` log has the one
deferred line; the post-start deploy `38690242990` log has exactly the three `DENIED` lines, and nothing else differs
from the derived text.

Not covered: `W11_1S_STOPPED_AFTER_FIRST_LOAD` (equal to the `WITNESS_RUNNING_HELD_E19` text under a distinct name). No
stopped-after-load state has been observed and no stop is authorized (OD-M11-4).

### 8.3 Owner decision (ACCEPTED 2026-10-15)

The owner accepted OD-M11-9 "exactly as proposed in the receipt §8.3 text". The accepted text, unchanged:

> I accept OD-M11-9 for the running signer only: `SIGNER_RUNNING_WITNESS_RUNNING_HELD` (result set 194
> `ff2468f0…`, DR-5 block 155 `4337f769…`, pre-deploy block 29 `f5087042…`), derived by `mb11_dr5_target.py`
> `775f43e8…` on the accepted `WITNESS_RUNNING_HELD_E19` base, is the DR-5 baseline for phase
> `W11_1_SIGNER_STARTED_EXACT`. Basis: deploy `38690242990` (main `0bf0b8f`, log `323ff1a8…`) compared EQUAL with 0
> allowed, 0 failures and 0 OLD-release lines, and the independent observe `01-POST11` at 2026-10-15T06:34:41Z
> returned `MB11_OBSERVE_W11_1_EXACT` for signer `c7ba0fb7…` / 84806. `W11_1S_STOPPED_AFTER_FIRST_LOAD` stays derived
> and not accepted. This is a preservation baseline only: it authorizes no stop, restart, hold release, authority,
> M-B12 step, First Memory or PROD.

`mb11_dr5_target.py` is not edited: its `targetAccepted: false` output field stays a tool constant (the file is pinned
by `mb11_operator.TOOL_PINS` and `e19_completion.MB11_REPINNED_SHA256`). The acceptance lives in this record.

### 8.4 Evidence (owner-local)

`C:\Users\edufo\lilith-mb11-od-m11-9-0bf0b8f` (`SHA256SUMS` `12d76f11aca4c19800866300dbdacd0b2f4b7cd678d835190780316da5f5b0c5`):
run metadata, the re-fetched log, the reproduced compare, `PROVENANCE.md`, and the digests of `observe/01-POST11` in
the original workdir (`lilith-mb11-w11-gate-4e58310`, not modified). Routine preservation from now on:
`mb11_operator observe` + `mb11_dr5_target compare W11_1_SIGNER_STARTED_EXACT <log>`, each owner-authorized.

```text
OD-M11-9 = ACCEPTED (running signer only): W11_1 DR-5 baseline = SIGNER_RUNNING_WITNESS_RUNNING_HELD 194/155/29
W11_1S_STOPPED_AFTER_FIRST_LOAD = DERIVED, NOT ACCEPTED;  OD-M11-4 (stop) = NOT ACCEPTED
M-B12 = NOT PASSED;  HOLD = HELD;  AUTHORITY / REGISTRY / ISSUANCE = DISABLED;  FIRST_MEMORY_READY = NOT REACHED
```
