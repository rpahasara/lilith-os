# Slice 15B2b-B1b-3e — M-B6 `PROVISION_LEDGER`: Ceremony Package and Runbook

Status:

- **CEREMONY PACKAGE (SOURCE AND DESIGN), 2026-10-07.** `MB6_PACKAGE_SOURCE_AND_DESIGN_READY_FOR_REVIEW`.
- **It implements the accepted rules:**
  - `MB6_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_GO` ([remediation record](slice-15b2b-b1b3e-mb6-ledger-remediation.md) §8, R-1);
  - `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA` (§12.2, R-2A);
  - `B5_SECTION_9_POST_MB1_STATUS = HISTORICAL_AFTER_MB1_EXERCISED` (§12.3, R-2B);
  - the separate P1B-6 proof (§13, R-3) and the W6-4 policy (§6.1, R-6);
  - the [owner-accepted expected ledger position](slice-15b2b-b1b3e-mb6-owner-ledger-head-acceptance.md).
- **Nothing here authorizes anything.** Each of these needs its own explicit owner authorization: the
  preparation sequence (§6), the go (§8), a recovery (§10), and acceptance (§12).
  - M-B6 is **NOT AUTHORIZED**.
  - M-B7 and later, genesis, record 1, First Memory and PROD remain **NOT AUTHORIZED**.
  - `FRESHNESS=UNKNOWN`.
- **The derived post-M-B6 DR-5 target (§4) is `DERIVED`, not accepted.** Its acceptance is a separate owner act
  (DR6-12).
- Repository and off-host only: no DEV, GCP or S25 contact; no K-ROOT, K-WIT or K-ACT private material.

```text
package reviewed != sequence authorized != evidence fresh != closing gate PASS != M-B6 go != M-B6
  != W6-5 != POST VERIFIED (W6-6) != LEDGER_PROVISIONED accepted != M-B7 authorized
derived DR-5 target != accepted post-M-B6 baseline;  expected head (comparison target) != ledger state
one go = exactly one `provision 1`; no automatic retry
```

## 1. Control and pinned tools

**Control rule.**

- The ceremony runs from a clean checkout of a merged `main` commit that contains this record.
- Every tool below must hash to its pin there. `mb6_operator.py pins <repo>` checks the operator's `TOOL_PINS`, and
  the operator re-checks each tool before streaming it (`git show HEAD:<path>`).
- The `mb6` form also requires the running operator to equal its own bytes at `HEAD` (`OPERATOR_NOT_AT_CONTROL`),
  and binds that SHA-256 into the go (§8).
- The pins are exact file bytes, so they do not change on merge. Any mismatch is `STOP TOOL_PIN_MISMATCH`.

| Tool (repository path) | Where it runs | SHA-256 |
| --- | --- | --- |
| `services/owner-memory-control/tools/mb6_operator.py` | owner laptop (builds every remote command) | `4a91d98421e38326858e141152180c127f5a67306eebe51a8ca8762f0504dcc5` |
| `services/owner-memory-control/tools/mb6_ledger_verifier.py` | DEV, root, release interpreter (in-memory bundle) | `6449d6ac88313da177665ab9ae7ee9beb86a3a03a22e2a02c2aecf99a79767b5` |
| `services/owner-memory-control/tools/mb6_ledger_recovery.py` | DEV, root, release interpreter (bundle; §10 only) | `8c2db24970a1e97f19e98574d712459ccfbe185ea669755235dc0b24ba71c612` |
| `services/owner-memory-control/tools/mb6_expected_ledger_head.py` | owner laptop, WSL (pinned wheels) | `5ecaaaaeba57c8a1afe0d76d0fa0ecaa4ef6bff35d291dc84e0fe7a205a019c8` |
| `services/owner-memory-control/tools/mb6_ledger_denial_proof.py` | DEV, root, `/usr/bin/python3 -I -B -` (streamed; P1B-6) | `470cb27231a0acc3cc5e0ffedb691c1e0a72c313ae80205aa928cff248b9f3c0` |
| `services/owner-memory-control/tools/mb6_dr5_target.py` | owner laptop (stdlib; §4) | `9978e3a791a829d6beace81ca0e4c6db9b1c154fbc56091f6312385d02632656` |
| `services/authority-dev/ceremony/install_authority_dev.py` | DEV, root (streamed; `status` only) | `fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487` |
| `services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py` | DEV, root, release interpreter (streamed, and in the bundle) | `78f57c01811e20a03ebb06bc114847bad440c7435e85ceb0249a488c659b2361` |
| `services/authority-dev/ceremony/observe_authority_dev_host.py` | DEV, root (streamed) | `a2f21b45e57a153f099c79a734ab05a575ac5c50f7cbc0527e562e94dd6908bf` |
| `scripts/verify_broker_dev_current_incarnation.py` | DEV, root (streamed; `preservation`) | `2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba` |
| `scripts/authority_custody_denial_proof.py` | DEV, root (streamed; P1B-5, unchanged) | `f4e39c81c24a01be5702f6a65a581fcd08f97e1c5ad4a07326883b605fef1455` |
| `services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py` (Replica A read) | owner laptop | `fd7abe2aa5e5efae41b87553efe8fe8058b437748accf866c2fa5ee71c8a7c27` |
| `services/owner-memory-control/tools/verify_mb3_registry.py` (Registry V1 custody) | owner laptop, WSL | `e710cfa623d494e243ab4a1fbaefe28e8d079e58398368f9dcabd645e06b5507` |
| `scripts/deployer_authority_boundary_proof.sh` (DR-5; runs in the deploy workflow, not by the owner) | DEV, routine deployer | `9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43` (unchanged) |

**Not used by M-B6.** The M-B4/M-B5 operator (`e380ab18…`) and its remove-before-M-B6 tool (`db0629a6…`) stay
pinned and unchanged. The remove-before-M-B6 tool is not part of this ceremony: after any M-B6 mutation it is out of
scope, and only the M-B6 recovery tool (§10) applies.

**Hash-gated streaming** is unchanged from the M-B4/M-B5 package:

- single-file tools: `… | sha256sum | cut -c1-64 | grep -qx '<pin>' || exit 96`;
- the verifier and recovery bundles: the in-memory loader refuses with exit 96 on any module pin mismatch;
- every remote command starts with `test "$(hostname)" = lilith-dev-01 || exit 97;`.

Exit 96 or 97 is a STOP. Nothing is copied to the host and no bytecode is written.

## 2. Release identity and the M-B6 code path

### 2.1 Release

The authority release on DEV stays `aee323e94412accbe321bc84eae78c5b8cf95afc` (installed in PR-1A; unchanged by
M-B4/M-B5). M-B6 runs that release's code, not the control's. Every runtime file on the M-B6 code path is
byte-identical between `aee323e` and the control (§2.2).

### 2.2 Module pins (readiness, `host` form)

`provision 1` runs `/usr/local/sbin/lilith-authority-ledger-dev`. That wrapper imports `lilith_authority_root.cli`
from `/opt/lilith-authority-dev/current`, and that import loads the modules below.

**The gap this closes.** The merged readiness probe pinned only the 18 modules the verifier bundle loads. The
installer `status` checks the release selector, the release entries and the CLI wrappers against their release
copies, but it does **not** re-hash payload files against the manifest. So the code `provision 1` executes was not
hash-pinned by any merged M-B6 read.

**The fix (this package).** The operator's read-only readiness probe now:

- also imports `lilith_authority_root.cli` (definitions only; `main` is not called);
- reports every loaded module of `lilith_authority_dev`, `lilith_authority_host`, `lilith_authority_root`,
  `lilith_owner_memory`, `lilith_memory` and `lilith_recovery_witness`;
- reports the SHA-256 of the installed wrapper.

`readinessExact` requires exactly the union of `RELEASE_MODULES` (18) and `PROVISION_MODULES` (20), and the wrapper
pin. A test runs the real probe against a release-shaped tree assembled from the repository.

**R-3 module pins** (38; `aee323e` = control):

| Module (release-relative) | SHA-256 |
| --- | --- |
| `lilith_authority_dev/__init__.py` | `e2810f0aed810c0ca1bdc7a14d60b7394cb892fb8220aeb01a59df598660206b` |
| `lilith_authority_dev/ledger.py` | `2853f2d73f8db1173207fd034d9d40cc317472bf429e85b1638e45c16d542f1a` |
| `lilith_authority_dev/profile.py` | `cf291af50ff5738ff7fdc3acc50eaf95dfb4c3c7128589b8f1927fb32652710a` |
| `lilith_authority_dev/protocol.py` | `4cd1154b4d36b4ff29083e597b77a50ecfd653bc1cc4519fb7dcc6b09353a25a` |
| `lilith_authority_host/__init__.py` | `27a314ec79fc0083f18eb70be215de10b9dc6c39119be505c5cfa690cbb7ac3a` |
| `lilith_authority_host/inputs.py` | `775d521a197372f252cd718877f74e7902b8e9f7fee79bdd843115131a0ea299` |
| `lilith_authority_host/paths.py` | `d95171b91c126da983a3ec2cc864b1875dd333b0b0d638eacf8645e93d52c55e` |
| `lilith_authority_host/store_observer.py` | `e22414fa594c5eddc139f62e2bdabe379f9e78cc78adf339ad60276990d1c27a` |
| `lilith_authority_root/__init__.py` | `b17f2c9dd955128b5028225c5444301548fd3e86fdcacb28d38c053dc5d0a33d` |
| `lilith_authority_root/cli.py` | `7175577c0bdbf52b7ad6fd56d8e5818a144d955c386ac452b768b4e5000cf10a` |
| `lilith_authority_root/clients.py` | `f6840254b0ef4abc7150077ab58612e8652472fac9caa71e778eecde3e4c328f` |
| `lilith_authority_root/genesis.py` | `fa2affd9017f275f62b6b2d9aa8eb8e17d9558d389188f09f0d778f8e4489823` |
| `lilith_authority_root/hold_store.py` | `8e62b92dd85f84df2b5e0c289260a81a0a20bb52e142e421e359c2b39e5d46ce` |
| `lilith_authority_root/ledger_tool.py` | `86b21c233012a1d03ca252b1d9a92b0cc0d60c5bc59296be55943e45e75c6fcd` |
| `lilith_authority_root/observers.py` | `5447eb67b96b5bb93f750fa6a71e63f246266e8d9bbaf6bd3ce9cdab34a349ed` |
| `lilith_authority_root/verifier.py` | `b60bf348f0e8fec9c76fc2ee2f9cde28e3033f8227acacd294ab51995740ba80` |
| `lilith_memory/__init__.py` | `2bbebd95846f1073a0b4e2ec3a2aa24378c56be4ecbb5470e5c1f1d359037e21` |
| `lilith_memory/canonical_contracts.py` | `f93d26d8a7e01d78d25f1f1d9540577cf2a55dfd4d52c4b64c87bef93ad887e0` |
| `lilith_memory/owner_proof.py` | `3a3eb7147d1e276ac261457a2340e045a0c43f6bc63eeb1a78bfc9864f80ac08` |
| `lilith_owner_memory/__init__.py` | `d1f1bf65a24315005ca4b597971dec6efa0212d4ab5836832e2a5a80fb9e62b4` |
| `lilith_owner_memory/authority_contracts.py` | `fabd8fd24f45febe83f8fd67c3fc39f277278e9145df9c55d5e03e5e8598e74f` |
| `lilith_owner_memory/authority_ledger_journal.py` | `f0d554c53948723c80f5cfbfd638d60855e92ddb562137370d12f9c7eeec49ce` |
| `lilith_owner_memory/authority_verifier.py` | `3c808267e56e9abc1ea1e848881cefd20a56fde51d9e803ac90f7f0c7517e83a` |
| `lilith_owner_memory/contracts.py` | `ff5075f1131f84348bdbc5d3fbd3410e53c7da39e265476a0b57ace6ff8ef5c7` |
| `lilith_owner_memory/pr1_acceptance.py` | `e0928854e1fcf4107458939ba9ebf1903cf7a4d0ab6808f7e89108db1444bbff` |
| `lilith_owner_memory/pr1_bootstrap.py` | `9a09a4726bb473067e84e7664dca49d51b90ced1e012564526bae07656d3d5fd` |
| `lilith_owner_memory/recovery_contracts.py` | `f4a14cff094d167a2a7925622031352955291c18244545e95c0003fb9231b95e` |
| `lilith_owner_memory/rotation_contracts.py` | `8f9df8dcd3e8a1b0cd8f03169bf7a51d4b6726cbb708cadfb3025586211996b0` |
| `lilith_owner_memory/successor_custody.py` | `29e99a7b179d58dd4f8e9cd576ed544f207145f25f89c92e97ca0e6efa65cb72` |
| `lilith_owner_memory/successor_readiness.py` | `842176d06954607aed39d8988764fc253fa8bd4c41ca49fcd5e2a4532c5ecc16` |
| `lilith_owner_memory/witness_readiness.py` | `129d4479a7c86a6ef33acfb27da4f5cd6c6a6947b89184863a50117091fe3cbd` |
| `lilith_recovery_witness/__init__.py` | `8c7a3dc1d15115616323a9ee652afde6b4a5f14afc2371dfd92ff3f845b6b3e1` |
| `lilith_recovery_witness/core.py` | `e4dcbc4bf0bae588fb1486e28ce37047faeb2755c46383ee04ed9ce9c9d5a3fd` |
| `lilith_recovery_witness/credential.py` | `7a394b561df072f5ec5ed933ab04deca450cfd84bf23f3fcf166b0c068916c18` |
| `lilith_recovery_witness/profile.py` | `7c28c05f82d399cf460bfd47b35d03985f71d8b1b423c7f6ff12f2e1874bea1d` |
| `lilith_recovery_witness/protocol.py` | `1b3f54c5a6c9298e5da08be6a8453b11e25002e396af2453f58f9ac07ed5f2e5` |
| `lilith_recovery_witness/storage.py` | `26ff45042fd90edc80c62402d39b68e2251b0725ee6579633ee2cee54f2b7898` |
| `lilith_recovery_witness/writer.py` | `ea9b619b4c867a2519f83a2c6c341a8e15d105ad5198dc38ec0609b1ae69bdca` |


| Installed wrapper | SHA-256 |
| --- | --- |
| `/usr/local/sbin/lilith-authority-ledger-dev` (= `services/authority-dev/bin/lilith-authority-ledger-dev`) | `fda779cd0dcecdc26e371082078306978f97e4f7097acae780fa6f38180fc45b` |

`sqlite3.Connection.deserialize` must be available to the release interpreter (the verifier's in-memory image).

## 3. Validity (MC-1 … MC-15)

- **Events and the sequence bound validity, not a clock** (MC-14). No TTL exists.
- **No replay** (MC-1, MC-2). Evidence from any earlier sequence counts for nothing, including:
  - M-B4/M-B5 Sequence 2;
  - the remediation slice;
  - the owner head derivation run;
  - this package's own DR-5 derivation.
  The accepted **values** they produced (pins, the accepted head, the derived target) are comparison targets, not
  fresh evidence.
- **Terminators.** Each one makes the current sequence non-reusable: REVALIDATE (MC-15). A new sequence and a fresh
  re-proof are then required. Before the marker nothing is consumed (MC-9); after it the go is consumed (MC-8).

  | # | Terminator |
  | --- | --- |
  | T-1 | a DEV deployment run starts or queues after the freeze (E-3) |
  | T-2 | boot ID, hostname or machine-id changes, or a reboot becomes pending |
  | T-3 | broker preservation other than PASS |
  | T-4 | K-ACT CURRENT or K-WIT custody facts change |
  | T-5 | installer `status`, the W5 verifier phase or the M-B6 verifier phase differs from the expected checkpoint |
  | T-6 | a cloud / IAM / topology difference from the accepted capture set, or an unexplained Admin Activity entry |
  | T-7 | `origin/main` moves, or any tool or module pin mismatches |
  | T-8 | a replica changes, or the owner register is not `KNOWN_EMPTY` |
  | T-9 | any custody-device event (G-9): phone or laptop compromise or rollback, ADB / SSH / automation on Termux |
  | T-10 | the sequence is paused, interrupted or uncertain |
  | T-11 | a DR-5 comparison other than `EQUAL` for the selected phase target (§4.3), or any `ALLOWED` |
  | T-12 | the owner-computed expected head in the work directory differs from the owner-accepted pin |

- **No B-5 §9 terminator.** B-5 §9 is historical after M-B1 (R-2B). The DR-5 terminator here is T-11 under the
  phase-bound rule.
- **Unknown fails closed.** If it is unknown whether an event is a terminator, the sequence is unusable until the
  owner records a determination. UNKNOWN = REVALIDATE = no go.

## 4. DR-5: preserved baseline and the derived post-M-B6 target

### 4.1 The accepted pre-M-B6 baseline (DR6-1; preserved, unchanged)

The accepted run is `36552218231` (`c0adb70`). Its three sets were located in local owner evidence by content hash;
51 byte-identical copies were found across the evidence roots. The raw log (`6912e0cd…`) re-extracted by
`mb6_dr5_target.py extract` reproduces all three sets exactly.

| Set | Lines | SHA-256 | Key counts |
| --- | --- | --- | --- |
| full result set | 186 | `f18692342cd62572affa54c83f9d390d21ac183e85dc8496dbadb0d5f3f49f9b` | 158 `DENIED`, 0 `ALLOWED`, 5 `DEFERRED_UNTIL_OBJECT_EXISTS`, 5 `UNOBSERVABLE_BY_DESIGN` |
| DR-5 block | 147 | `a1d98773bcd07c39b2a17f0628f75db858a3e1e6bcd19e7bcd8918c0e79f1390` | 130 `DENIED`, 0 `ALLOWED`, 5 `DEFERRED_UNTIL_OBJECT_EXISTS`, 5 `UNOBSERVABLE_BY_DESIGN` |
| pre-deploy block | 29 | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` | 28 `DENIED` |

### 4.2 The derived post-M-B6 target (DR6-2, DR6-3): DERIVED, NOT ACCEPTED

**Derivation.** `mb6_dr5_target.py derive <result-set> <dr5-block> <predeploy-block>`, off-host, over the
accepted texts. It applies exactly two substitutions, taken from the unchanged DR-5 script source:

| # | Accepted line (pre) | Target line(s) (post) | DR-5 source |
| --- | --- | --- | --- |
| S-1 | `DEFERRED_UNTIL_OBJECT_EXISTS: /var/lib/lilith-authority-dev/authority_ledger.db (/var/lib/lilith-authority-dev absent)` | `UNOBSERVABLE_BY_DESIGN: /var/lib/lilith-authority-dev/authority_ledger.db (beneath root-only /var/lib/lilith-authority-dev; checked only by root tooling)` | the `AB_PR1_UNOBSERVABLE` leaf loop |
| S-2 | `DEFERRED_UNTIL_OBJECT_EXISTS: /var/lib/lilith-authority-dev (later step)` | `DENIED: test -w /var/lib/lilith-authority-dev`, `DENIED: test -r /var/lib/lilith-authority-dev`, `DENIED: test -x /var/lib/lilith-authority-dev` (this order) | `ab_check_later_state` (`ab_deny -w`, then `-r`, `-x` for `/var/lib/*`) |

S-1 is result-set line 159 (DR-5 block line 127). S-2 is result-set line 168 (DR-5 block line 136). No other line
changes.

**No other deploy-time reader.**

- `/var/lib/lilith-authority-dev` appears in the DR-5 script only in those two code paths.
- Neither ladder nor either maturity reads it.
- `verify_broker_dev_current_incarnation.py` reports it (one JSON line, no result-set prefix). It is never judged,
  and the deploy workflow does not run it.
- The open item of the remediation record §12.2 about `CUSTODY_PATHS` is therefore closed: those lines are not in
  the deploy result set.

**The target:**

| Set | Lines | SHA-256 | Counts |
| --- | --- | --- | --- |
| full result set | **188** | `3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494` | **161** `DENIED`, **0** `ALLOWED`, 0 `FAIL`, 3 `DEFERRED_UNTIL_OBJECT_EXISTS`, 6 `UNOBSERVABLE_BY_DESIGN` |
| DR-5 block | **149** | `d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801` | **133** `DENIED`, 0 `ALLOWED`, 3 `DEFERRED_UNTIL_OBJECT_EXISTS`, 6 `UNOBSERVABLE_BY_DESIGN` |
| pre-deploy block | 29 | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` (unchanged) | 28 `DENIED` |

**Unchanged by design** (the tool checks each):

- `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`;
- `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`;
- `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=unreadable`;
- no `ALLOWED`;
- no `FAIL`.

```text
POST_MB6_DR5_TARGET_DERIVED = YES
POST_MB6_DR5_TARGET_ACCEPTED = NO   (separate owner act after a verified successful M-B6; DR6-12)
```

The tool pins this target (`POST`), so a re-derivation from the accepted texts must reproduce it or refuse
`TARGET_NOT_PINNED`. The accepted texts are owner evidence and are not committed to the repository. The tests prove
the derivation rule on synthetic baselines and bind the substitution strings to the DR-5 source.

### 4.3 Phase-bound use (DR6-4 … DR6-11)

`mb6_dr5_target.py compare <verified-host-phase> <deploy-log>`:

| Verified host phase (from the M-B6 verifier, never from the argument alone) | Target | Use |
| --- | --- | --- |
| `W6_0_NO_MB6_MUTATION` | the accepted pre-M-B6 baseline (§4.1) | E-4: every deploy before the freeze |
| `LEDGER_COMMITTED_EXACT` (W6-6, then owner-accepted) | the derived post-M-B6 target (§4.2) | F-2: the first deploy after the freeze ends (§13) |
| anything else | none: `NO_BASELINE_STOP` | a deploy there is a STOP (DR6-7); the freeze forbids it |

- `EQUAL` requires byte equality of all three sets and no `ALLOWED`.
- Any other result is `DRIFT`: unexpected, never part of the delta (DR6-4, DR6-9 … DR6-11).
- `EQUAL` is not acceptance.

## 5. Required pre-state

| Fact | Required | Proven by |
| --- | --- | --- |
| `TRUST_INSTALLED` | YES (owner-accepted M-B4/M-B5) | W5 verifier `W5_INSTALLED_CONTENT_VERIFIED` (E-13) |
| `REGISTRY_INSTALLED` | YES | E-11, E-13 |
| `REGISTRY_EFFECTIVE` | NO | M-B6 verifier `registryEffective=false` (E-25) |
| `AUTHORITY_ACTIVE` | NO | `GRANT_ABSENT` (E-24); units inactive (E-23) |
| host phase | **W6-0** (`W6_0_NO_MB6_MUTATION`) | M-B6 verifier `expect W6_0_NO_MB6_MUTATION <head>` (E-25) |
| `/var/lib/lilith-authority-dev` and the ledger | absent | E-25; observer and custody `STATE … ABSENT` (E-15) |
| `AUTHORIZATION_REGISTER_COPY_MISSING`, `GENESIS_PIN_COPY_MISSING` | exactly these host-input reasons | M-B6 verifier `hostInputReasonsExactlyW5Gaps` (E-25) |
| activation | `GRANT_ABSENT` | E-24 |
| owner register | `KNOWN_EMPTY`, freshly established from Replica A and Replica B in this sequence | E-17 … E-19 |
| installer stage | `status --expect P1B-5` PASS | E-12 |

The W6-2 pre-state (`ADOPTED_NO_MUTATION`) is **not** a starting state for this package. It is reachable only after
a reviewed W6-3 recovery, and then needs a new sequence (§10).

## 6. Fresh evidence (one owner-authorized preparation sequence)

The preparation sequence needs a **separate explicit owner authorization** (§14.1). It writes nothing to DEV. Every
item below is collected **inside** the sequence; nothing is replayed.

| # | Evidence | How (operator form or command) | PASS means |
| --- | --- | --- | --- |
| E-1 | canonical repository control | `pins <repo>` on a clean checkout | `origin/main` = HEAD = the control commit (a merged `main` containing this record); `MB6_TOOL_PINS_EXACT` |
| E-2 | latest DEV deployment and queue | GitHub run list (read-only) | the latest DEV deploy run is the control commit, or an ancestor nonmaterial by content; nothing queued or in progress |
| E-3 | deployment freeze | owner declaration, recorded with the time | **freeze declared** at the start of the live sequence; it holds per §13 |
| E-4 | fresh pre-M-B6 DR-5 | for **every** DEV deploy run after `37577178942` (the last accepted comparison) through the latest: `mb6_dr5_target.py compare W6_0_NO_MB6_MUTATION <log>` | `EQUAL` for each (186 / 158 `DENIED` / 0 `ALLOWED`; `P1A-9`, `L1c.3`, `GRANT_ABSENT`) |
| E-5 | broker preservation / incarnation | `host … PRE` → `preservation.*` | `BROKER_PRESERVATION=PASS` against the accepted incarnation (`c4b9cb38…` / `a30bd7d6…`, or a later owner-accepted re-pin) |
| E-6 | boot and machine identity | `identity.out` | machine-id `ae929170e6fa4c8ab9cc7b9547238d9d`, `lilith-dev-01`, boot `eea461c3-60f0-4b10-8ee9-556dcef19711` (last accepted at M-B4/M-B5); `REBOOT_REQUIRED=absent`. A different boot is T-2 |
| E-7 | K-ACT preservation / CURRENT | `custody.out` | credstore holds exactly one entry; blob `root:root 0600`, SHA-256 `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3`, inode and times as last accepted; publication `/root/b1b3d-l2b-publication.json` SHA-256 `d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032` (re-read now) |
| E-8 | K-WIT preservation | `custody.out` | `credentials/` lists only the K-WIT blob, `root:root 0600`, SHA-256 `f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be` (ciphertext; never decrypted), inode and times as last accepted |
| E-9 | installed registry-root exactness | W5 verifier (E-13) + `custody.out` listing | `anchorsEqualOwnerCopies` (`bc5f00a7…`); `registryVerifiesOnHost` under it |
| E-10 | installed witness-anchor exactness | W5 verifier (E-13) | `anchorsEqualOwnerCopies`; `witnessAnchorNamesKWit` |
| E-11 | installed Registry V1 exactness | W5 verifier (E-13) | the installed registry is `46b0bfc5…` and verifies on the host to digest `fa662721…14fc` |
| E-12 | installer stage | `status.*` | `install_authority_dev.py status --expect P1B-5 aee323e…` PASS |
| E-13 | W5 verification | `w5verifier.*` | `mb4_mb5_trust_install_verifier.py expect W5_INSTALLED_CONTENT_VERIFIED` exit 0 |
| E-14 | release / module exactness on the M-B6 code path | `readiness.*` | `readinessExact=true`: `releases/aee323e…`, the release interpreter executable, **all 38 module pins and the wrapper pin** (§2.2), `deserialize` available |
| E-15 | observer state | `observer.*` | differs from the accepted post-W5 observation (`76e5039ecb268a6a7f19f1d79a899c52d19eee0ba15280ee6ca0558920975943`) only in the clock; `STATE /var/lib/lilith-authority-dev ABSENT` |
| E-16 | cloud / IAM / topology | `cloud <dir> <since>` | the 11 JSON captures and the bucket list are byte-identical to the last accepted capture set; Admin Activity since `<since>` (the end of the last accepted window) holds only `iam.serviceAccounts.actAs`, each mapped to a reviewed deploy or this sequence's own IAP sessions |
| E-17 | Replica A fresh read | `owner_freshness_tool verify-replica` (laptop) | 0 records; manifest `fbdd045c…`; entries and inodes as accepted |
| E-18 | Replica B fresh read | owner-run, S25, local Termux, screen-only | canonical path, not nested; manifest `c068e533…`; 0 records; inodes as accepted; settings OFF; custody attested |
| E-19 | `KNOWN_EMPTY` | the owner's determination from E-17 + E-18 | `OWNER_REGISTER = KNOWN_EMPTY`; anything else blocks (`REQUIRED_UNKNOWN_BLOCK`) |
| E-20 | Registry V1 custody | laptop, WSL: `verify_mb3_registry.py` with the M-B3 go pins | export `c4ea3d66…64d8`; `MB3_LAPTOP_VERIFIED`; transport `3f0a59c0…6156` |
| E-21 | owner expected-head pin | `expected <repo> <authority-registry.v1.json> <registry-root.json> <workdir>` over the owner-held `46b0bfc5…` and `bc5f00a7…` | `<workdir>/expected/expected-ledger.json`: `ledgerSequence` 1, `ledgerHead` = `independentLedgerHead` = `pinDerivedLedgerHead` = the owner-accepted `19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630`; `genesisOpJcsSha256` `8e3bdbdf…7b60`. Anything else is T-12 |
| E-22 | P1B-5 denial proof | `denial <repo> <dir>` (unchanged tool) | `AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5`, 0 `ALLOWED` |
| E-23 | no later state / no M-B8 state | `custody.out`, `observer.*`, M-B6 verifier | `STATE /var/lib/lilith-recovery-witness ABSENT`; trust / registry contents as accepted; `owner/` and `holds/` empty; units inactive and not enabled; `laterStateAbsent`, `witnessGenesisPresent=false` |
| E-24 | `GRANT_ABSENT` | `custody.out` | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`, `activation_rc=1` |
| E-25 | M-B6-specific pre-state | `host … PRE` → `mb6verifier.*`; the operator result | M-B6 verifier `expect W6_0_NO_MB6_MUTATION <head>` exit 0: `trustRegistryExact`, `hostInputReasonsExactlyW5Gaps`, `genesisOpEqualsRegistryV1`, `ownerHeadIsHeadOfRegistryV1`, `laterStateAbsent`; `registryEffective=false`, `authorityGranted=false`; the operator result `MB6_HOST_PRE_PASS` with every code 0 |

**Order inside the sequence:**

1. E-1 … E-3 (the freeze starts here), then E-4.
2. E-20, then E-21 (off-host; E-21 writes the work directory's `expected`).
3. E-17 … E-19.
4. `host <repo> <workdir> <dir> PRE` (E-5 … E-15, E-23 … E-25).
5. `denial` (E-22).
6. `cloud` (E-16).
7. Owner review of E-1 … E-25: no terminator; no unknown.
8. The closing gate (§7).
9. **STOP and wait for the owner.** The sequence authorization is not the go.

## 7. Closing gate (immediately before the go)

The closing gate runs read-only, after E-1 … E-25 and immediately before the owner considers the go. Every item
must be freshly re-established; an item that is UNKNOWN is **REVALIDATE: no go**.

| # | Re-established now | PASS means |
| --- | --- | --- |
| G-1 | continuity | the same owner-attended sequence; no pause, interruption or uncertainty (T-10) |
| G-2 | no deploy after evidence closure | GitHub run list: no DEV run started or queued since E-2 (T-1) |
| G-3 | freeze active | the E-3 freeze still holds |
| G-4 | control and pins | `pins <repo>`: `origin/main` unchanged; every tool pin exact (T-7) |
| G-5 | W6-0 exact | a fresh `host … PRE` into a new evidence directory: every code 0, `readinessExact`, the M-B6 verifier `W6_0_NO_MB6_MUTATION`; identity, custody, status, W5 and observer facts identical to E-5 … E-15 (only the clock differs) |
| G-6 | expected head | `<workdir>/expected/expected-ledger.json` is unchanged and equals the owner-accepted `19bf9091…1630` (T-12) |
| G-7 | `KNOWN_EMPTY` current within this sequence | no replica event since E-17 / E-18 (T-8, T-9) |
| G-8 | cloud | a fresh `cloud` capture identical to E-16; any new Admin Activity explained (T-6) |
| G-9 | no relevant uncertainty | the owner records `NO_TERMINATOR_KNOWN` |

`MB6_CLOSING_GATE = PASS` only if G-1 … G-9 all pass. The go (§8) may be considered only after it, in the same
sequence.

## 8. The M-B6 go (DRAFT TEMPLATE; NOT ISSUED)

The operator's `mb6` form refuses before the marker unless the go file contains **every** binding line, with:

- `{control}` = the control commit;
- `{operator}` = the operator's own SHA-256 at that commit;
- `{head}` = the owner-computed head from `<workdir>/expected`;
- `{pre}` = `W6_0_NO_MB6_MUTATION`.

The lines are exactly `mb6_operator.MB6_GO_LINES`:

```text
I authorize M-B6 / PROVISION_LEDGER now for exactly one attempt within this current DEV_SYNTHETIC M-B6 sequence.
Continuity: MB6_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_GO.
The deploy freeze holds from the start of this live preparation sequence through technical POST and owner acceptance or sequence termination.
Control commit: <CONTROL>.
Operator: services/owner-memory-control/tools/mb6_operator.py SHA-256 4a91d98421e38326858e141152180c127f5a67306eebe51a8ca8762f0504dcc5.
Verifier: services/owner-memory-control/tools/mb6_ledger_verifier.py SHA-256 6449d6ac88313da177665ab9ae7ee9beb86a3a03a22e2a02c2aecf99a79767b5.
Recovery: services/owner-memory-control/tools/mb6_ledger_recovery.py SHA-256 8c2db24970a1e97f19e98574d712459ccfbe185ea669755235dc0b24ba71c612.
Ledger denial proof: services/owner-memory-control/tools/mb6_ledger_denial_proof.py SHA-256 470cb27231a0acc3cc5e0ffedb691c1e0a72c313ae80205aa928cff248b9f3c0.
Release: aee323e94412accbe321bc84eae78c5b8cf95afc.
Command: /usr/local/sbin/lilith-authority-ledger-dev provision 1, exactly one invocation.
Pre-state: W6_0_NO_MB6_MUTATION.
Owner-computed expected ledger head: 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630 (ledger sequence 1).
Registry V1 digest: fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc.
OWNER_REGISTER = KNOWN_EMPTY was freshly established in this sequence from Replica A and Replica B.
AUTHORIZATION_REGISTER_COPY_MISSING and GENESIS_PIN_COPY_MISSING remain; M-B6 does not install either copy.
This go does not accept LEDGER_PROVISIONED, and does not authorize M-B7, M-B8, genesis, record 1, First Memory or PROD.
Any REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output, or other STOP after the attempt marker consumes this go and ends the sequence. There is no automatic retry.
A partial state enters only the reviewed W6 classifier and the separately authorized recovery or adoption path.
```

This template is **not** an owner go. The owner issues the go verbatim, separately, after `MB6_CLOSING_GATE =
PASS`.

## 9. Execution and POST model

| Step | What happens | Consumption |
| --- | --- | --- |
| PRE-GO | the operator checks pins, the expected head, the go lines and the absent marker, then runs the read-only M-B6 verifier `expect W6_0_NO_MB6_MUTATION <head>`, which must return `W6_0` | refusals here consume nothing (MC-9) |
| GO CONSUMPTION | the attempt marker `<workdir>/attempts/mb6.json` is written `O_EXCL` (`invocationsPermitted: 1`) | the go is consumed from here (MC-8) |
| MUTATION | exactly one `sudo -n /usr/local/sbin/lilith-authority-ledger-dev provision 1` over ssh, behind the hostname guard | one physical invocation (MC-7) |
| TRANSCRIPT | saved and classified: `CLI_SUCCESS_EXACT` only for exit 0, empty stderr, the exact two JSON lines with `stateDirectory=CREATED` and the head | anything else is `MB6_STOP` |
| POST | `post <repo> <workdir>`: a fresh `host … POST` (the independent M-B6 verifier `expect LEDGER_COMMITTED_EXACT <head>`, installer `status --expect P1B-6`, W5 verifier `OUT_OF_SCOPE_POST_LEDGER`, readiness, broker, observer, custody) | read-only |
| W6-5 → W6-6 | the sequence classifier must return `W6_5_CLI_SUCCEEDED_POST_PENDING`. Only then, with every code 0, `readinessExact`, the three evidence items true, `registryEffective=false` and `authorityGranted=false`, is `post/POST_VERIFIED.json` written (W6-6, `ownerAccepted=false`) | read-only on DEV |
| DENIAL | `ledger-denial <repo> <dir>`: the separate P1B-6 proof; then `denial` (P1B-5) again | read-only |

**Exact technical POST expectations (W6-6):**

- `ledgerSequenceIsOne`, `ledgerHeadEqualsOwnerComputed`, `ledgerSchemaFingerprintVerified`: all true;
- exactly one journal row: sequence 1, op `GENESIS`, payload = the accepted JCS op (`8e3bdbdf…7b60`);
- `prev_head` = `0^64`;
- head = `19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630`;
- schema fingerprint = the pinned `65127a68…9cb7` (`ledger.SCHEMA_FINGERPRINT`); `integrity_check` ok; WAL header;
- meta `(1, 1, dev, DEV_SYNTHETIC)`; one exact epoch row; no challenge, evidence or use rows;
- the state directory signer-owned `0700`; the ledger `0600`; the database the only entry (`ledgerClean`);
- `laterStateAbsent`, `witnessGenesisPresent=false`;
- `hostInputReasons` = exactly `AUTHORIZATION_REGISTER_COPY_MISSING`, `GENESIS_PIN_COPY_MISSING`;
- `registryEffective=false`, `authorityActive=false`, `authorityGranted=false`;
- installer `status --expect P1B-6` PASS; broker preservation PASS; units inactive.

**P1B-6 denial expectation:** `MB6_LEDGER_DENIAL_PROOF=PASS phase=P1B-6 denied=20 allowed=0`. It is the exact
28-line transcript of the remediation record §13, including `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`. The
operator records its SHA-256.

**Observer after M-B6.** The observer digest changes by design: the state directory and the ledger are now
present. The owner compares the facts: only the state directory, the ledger and the clock differ from E-15.

## 10. Crash windows and recovery (accepted W6 model)

A partial outcome is classified only by `post` / `classify` (the independent verifier plus this sequence's
records). It may enter only the reviewed path below. Every mutating recovery needs a **separate** owner
authorization naming the plan digest (`mb6_operator.RECOVERY_LINES`).

| Phase | Meaning | Allowed path |
| --- | --- | --- |
| W6-0 | no M-B6 mutation (e.g. a refusal or transport failure before the root half ran) | none; the go is consumed if the marker exists. A new attempt needs a new sequence and a new go |
| W6-1 | state directory created, not yet chowned / chmodded | the reviewed plan / recovery path only: `REMOVE_EMPTY_STATE_DIRECTORY` → W6-0 |
| W6-2 | safe, exact, empty, signer-owned `0700` state directory | nothing to recover; re-entered only by a new sequence and a new go (`ADOPTED_NO_MUTATION`) |
| W6-3 | uncommitted ledger files | the reviewed uncommitted-ledger recovery path only: `REMOVE_UNCOMMITTED_LEDGER_FILES` → W6-2 |
| W6-4 clean | committed exact ledger, the database the only entry, CLI response lost or inexact | `REVIEWED_ADOPTION_PATH_ALLOWED` only after exact verification: `ADOPT_COMMITTED_LEDGER` (fsync only, no byte written) → `LEDGER_COMMITTED_EXACT`; never deleted |
| W6-4, data only in the WAL | committed state only in the WAL | **STOP / OWNER_ADJUDICATION_REQUIRED**: no checkpoint, no delete, no adoption, no re-provision, no retry, no inference of durability |
| W6-5 | technical success transcript, POST pending | run `post` |
| W6-6 | technical POST verified, owner acceptance pending | owner acceptance (§12) |
| `UNCLASSIFIED_STOP`, `OUT_OF_SCOPE_LATER_STATE` | anything else | STOP; owner adjudication |

There is no automatic retry in any row (MC-10). Recovery is not a retry. A new `provision 1` needs a new
sequence, a fresh re-proof and a new go.

## 11. Technical success boundary

```text
LEDGER_PROVISIONED candidate (technical, W6-6)
  sequence = 1
  head = 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630
LEDGER_PROVISIONED_OWNER_ACCEPTED = NO   (until §12)
M-B7 = NOT AUTHORIZED
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
AUTHORIZATION_REGISTER_COPY_MISSING remains
GENESIS_PIN_COPY_MISSING remains
```

## 12. Owner acceptance of a successful M-B6 (DRAFT TEMPLATE; NOT ISSUED)

```text
I accept M-B6 / PROVISION_LEDGER as technically completed for DEV_SYNTHETIC in the M-B6 sequence on control <CONTROL>, release aee323e94412accbe321bc84eae78c5b8cf95afc.
Provision: exactly one /usr/local/sbin/lilith-authority-ledger-dev provision 1; transcript CLI_SUCCESS_EXACT; attempt marker SHA-256 <MARKER_SHA256>.
Verifier: services/owner-memory-control/tools/mb6_ledger_verifier.py SHA-256 6449d6ac88313da177665ab9ae7ee9beb86a3a03a22e2a02c2aecf99a79767b5 reports LEDGER_COMMITTED_EXACT; POST_VERIFIED (W6-6), POST evidence SHA-256 <POST_SHA256>.
Ledger: sequence 1; head 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630, equal to the owner-accepted expected head; GENESIS op JCS SHA-256 8e3bdbdf3f3730de5ad031d36eb390888fc6e0f65307d947522b0138ffcd7b60; schema fingerprint 65127a68c61d4dba390e01c61d01a76fdc54e830c374cb05069b0ab0c50d9cb7; the database is the only entry.
Denial: MB6_LEDGER_DENIAL_PROOF=PASS phase=P1B-6 denied=20 allowed=0 (transcript SHA-256 <P1B6_SHA256>); AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5; GRANT_ABSENT.
DR-5: PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA applies. The post-M-B6 target 3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494 (188 lines, 161 DENIED, 0 ALLOWED) remains DERIVED and NOT ACCEPTED; its acceptance is separate, after the first post-freeze deploy compares EQUAL.
LEDGER_PROVISIONED = OWNER-ACCEPTED.
REGISTRY_EFFECTIVE = NO. AUTHORITY_ACTIVE = NO. AUTHORIZATION_REGISTER_COPY_MISSING and GENESIS_PIN_COPY_MISSING remain.
This acceptance does not authorize M-B7, M-B8, witness genesis, record 1, First Memory, authority activation or PROD.
The M-B6 deployment freeze ends with this acceptance (package §13).
```

## 13. Deployment freeze and its release

The freeze starts at E-3 (the start of the live preparation sequence). It does **not** end at technical success.

| Outcome | The freeze may end only when |
| --- | --- |
| success | the owner has issued the §12 acceptance (which includes the P1B-6 PASS), **and** the host is verified `LEDGER_COMMITTED_EXACT` at that acceptance |
| sequence terminated before the marker | the owner records the termination; the host is verified `W6_0` |
| attempt consumed, host back at `W6_0` (no mutation, or after a reviewed W6-1 recovery) | the owner records the outcome and the host is verified `W6_0` |
| W6-2 / W6-3 / W6-4 / `UNCLASSIFIED_STOP` unresolved | **never** while unresolved: a deploy there is a STOP (DR6-7). It ends only after a reviewed recovery or adoption reaches `W6_0` or `LEDGER_COMMITTED_EXACT` (with owner acceptance), or after an explicit owner adjudication of that state |

**After the freeze ends (success path):**

- **F-1.** M-B6 creates no staged files and no host copies (bundles run in memory), so there is no host cleanup.
  The local work directory is kept as evidence.
- **F-2.** The first DEV deploy after the freeze is compared with `mb6_dr5_target.py compare LEDGER_COMMITTED_EXACT
  <log>` after a fresh M-B6 verifier read confirms `LEDGER_COMMITTED_EXACT`.
- **F-3.** `EQUAL` (188 / 161 `DENIED` / 0 `ALLOWED`, `3640ca01…`) is a precondition for the separate owner
  acceptance of the post-M-B6 DR-5 baseline (DR6-12). `DRIFT` is unexpected drift, and the owner decides.
- **F-4.** Until that acceptance, `POST_MB6_DR5_TARGET_ACCEPTED = NO`. The preserved pre-M-B6 baseline remains
  historical evidence (DR6-1).

## 14. Authorization templates (each separate; none implied by another)

### 14.1 Preparation sequence (DRAFT; NOT ISSUED)

```text
I authorize one owner-attended DEV_SYNTHETIC M-B6 preparation sequence under
MB6_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_GO, on control <CONTROL>.
It collects E-1 … E-25 of the M-B6 ceremony package, read-only on DEV and GCP, and runs the closing gate.
The deployment freeze starts now and holds under package §13.
It does not authorize M-B6, the go, any recovery, M-B7 or later, genesis, record 1, First Memory or PROD.
```

### 14.2 The go

§8 (`MB6_GO_LINES`). Separate, verbatim, after the closing gate.

### 14.3 Recovery

`mb6_operator.RECOVERY_LINES`, naming the reviewed plan digest. Separate, after classification.

### 14.4 Acceptance

§12. Separate, after W6-6 and the P1B-6 PASS.

## 15. STOP rules (any one ends the sequence; no automatic retry)

- **S-1** any terminator T-1 … T-12, or any closing-gate item other than PASS;
- **S-2** any operator `STOP`, exit 96 (pin) or 97 (host guard);
- **S-3** any transcript other than `CLI_SUCCESS_EXACT` after the marker: the go is consumed; classify (§10);
- **S-4** any POST other than `MB6_POST_VERIFIED`; any P1B-5 or P1B-6 proof other than PASS; any `ALLOWED`;
- **S-5** any change to `GRANT_ABSENT`, `REGISTRY_EFFECTIVE` or `AUTHORITY_ACTIVE`;
- **S-6** UNKNOWN anywhere: REVALIDATE.

## 16. Remaining blockers before any live M-B6 preparation

| # | Blocker |
| --- | --- |
| P-1 | owner review and merge of this package (the operator, the DR-5 tool, the records and the tests); canonicalization of the merged control |
| P-2 | the owner's decision on this package (`MB6_PACKAGE_SOURCE_AND_DESIGN_READY_FOR_REVIEW`) |
| P-3 | a separate owner authorization of the preparation sequence (§14.1) |

Owner acceptance of the post-M-B6 DR-5 target is **not** a blocker to preparation. It belongs after a verified
successful M-B6 (§13).

## 17. State

```text
MB6_CEREMONY_PACKAGE = SOURCE AND DESIGN; NOT MERGED; NOT ISSUED
OWNER_LEDGER_HEAD_ACCEPTED = YES; OWNER_LEDGER_HEAD_PINNED_FOR_MB6 = YES (19bf9091…1630, sequence 1)
POST_MB6_DR5_TARGET_DERIVED = YES (188 lines, 3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494)
POST_MB6_DR5_TARGET_ACCEPTED = NO
PRE_MB6_DR5_BASELINE = PRESERVED (f18692342cd62572affa54c83f9d390d21ac183e85dc8496dbadb0d5f3f49f9b)
MB6_GO = DRAFT TEMPLATE; NOT ISSUED
MB6_ACCEPTANCE = DRAFT TEMPLATE; NOT ISSUED
TRUST_INSTALLED = YES
REGISTRY_INSTALLED = YES
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
M-B6 = NOT AUTHORIZED
M-B7 = NOT AUTHORIZED
M-B8 = NOT AUTHORIZED
M-B9a / M-B9b = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD_1 = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED
```
