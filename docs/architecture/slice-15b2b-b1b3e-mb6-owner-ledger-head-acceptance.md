# Slice 15B2b-B1b-3e — M-B6 Owner-Derived Expected Ledger Position: Owner Acceptance (2026-10-07)

Status:

- **OWNER DECISION RECORD.** On 2026-10-07 the owner derived the expected M-B6 ledger position off-host under
  canonical control `78683b2a36dd5bd2674e9664712b13702d1aa404` (the merge of PR #164), then explicitly accepted
  and pinned it for M-B6.
- **It pins a comparison target only.** It does not authorize M-B6 execution.
  - M-B6, M-B7 and later are **NOT AUTHORIZED**.
  - Witness genesis, record 1, First Memory, authority activation and PROD are **NOT AUTHORIZED**.
  - `FRESHNESS=UNKNOWN` until a future fresh M-B6 preparation sequence.
- The derivation was off-host and read-only. No DEV, GCP or S25 contact; no K-ROOT, K-WIT or K-ACT private
  material; no host-installed copy used as an input.

```text
OWNER_LEDGER_HEAD_DERIVED = YES
OWNER_LEDGER_HEAD_ACCEPTED = YES
OWNER_LEDGER_HEAD_PINNED_FOR_MB6 = YES
M-B6 = NOT AUTHORIZED
```

```text
expected ledger head (comparison target) != ledger state != genesis commitment != witness genesis
  != authority activation != record 1 != First Memory
owner-accepted expected head != host-observed head != LEDGER_PROVISIONED accepted
```

## 1. The accepted position

| Item | Accepted value |
| --- | --- |
| canonical control | `78683b2a36dd5bd2674e9664712b13702d1aa404` |
| derivation tool | `services/owner-memory-control/tools/mb6_expected_ledger_head.py`, SHA-256 `5ecaaaaeba57c8a1afe0d76d0fa0ecaa4ef6bff35d291dc84e0fe7a205a019c8` (bytes from the canonical control) |
| Registry V1 installable (`authority-registry.v1.json`) | SHA-256 `46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e` |
| registry-root anchor (`registry-root.json`) | SHA-256 `bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687` |
| Registry V1 digest | `fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc` |
| expected ledger sequence | `1` |
| expected ledger head | `19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630` |
| GENESIS op JCS SHA-256 | `8e3bdbdf3f3730de5ad031d36eb390888fc6e0f65307d947522b0138ffcd7b60` |
| owner derivation stdout SHA-256 | `1f6b3fb93dfd7a31f410737766d98fa7825e256f3e8b11ddea331ec8bf5913a8` |

**The accepted GENESIS op** (the deterministic ledger GENESIS op derived from Registry V1; JCS bytes):

```text
{"environment":"dev","op":"GENESIS","policyVersion":"policy.dev-synthetic.v1","recoveryEpoch":{"counter":1,"random":"11f184889f333dece054f3b91a301632"},"registryVersion":1,"signingKeyIds":["test-only.dev-synthetic.actor.b1b3d.1"]}
```

The head is `sha256("LILITH_AUTHORITY_LEDGER_HEAD_V1\0" ‖ 0^32 ‖ JCS(op))`
([M-B6 remediation record](slice-15b2b-b1b3e-mb6-ledger-remediation.md) §5).

## 2. How it was derived

- **Inputs.** Owner-held local copies, located by content hash alone under the Sequence-2 evidence root. Exactly
  one file matched each input hash. Both are the owner's off-host derivation output from M-B4/M-B5, not host
  copies.
- **Tool.** The canonical bytes from a clean `git archive` export of the control commit. It was run in local WSL
  with the pinned wheels; there was no network.
- **Command.** `mb6_expected_ledger_head.py derive <authority-registry.v1.json> <registry-root.json>`: exit 0,
  empty stderr.
- **Checks performed by the tool:**
  - both inputs equal the accepted installable pins and are exact JCS;
  - `registryVerified: true` (K-ROOT pin `cb36daf1…92cf`, E0 and policy, the single K-ACT key);
  - the journal head equals the independent restatement and the pin-derived head.
- **A check outside the tool.** The head and the op hash were recomputed from the reported JCS bytes with a
  separate hash computation. They are equal.
- **Cross-check.** `MATCHES_CROSS_CHECK`: the result equals the earlier repository cross-check value
  (`19bf9091…1630`), which was `CROSS_CHECK_ONLY / NOT_OWNER_COMPUTED / NOT_ACCEPTED` until this decision.

## 3. Owner statement (substance, verbatim values)

The owner accepted the owner-derived M-B6 expected ledger position produced from the accepted owner-held
Registry V1 and registry-root inputs under canonical control `78683b2a36dd5bd2674e9664712b13702d1aa404`:

- `OWNER_LEDGER_HEAD_DERIVED = YES`; `OWNER_LEDGER_HEAD_ACCEPTED = YES`; `OWNER_LEDGER_HEAD_PINNED_FOR_MB6 = YES`;
- `EXPECTED_LEDGER_SEQUENCE = 1`;
- `EXPECTED_LEDGER_HEAD = 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630`;
- `GENESIS_OP_JCS_SHA256 = 8e3bdbdf3f3730de5ad031d36eb390888fc6e0f65307d947522b0138ffcd7b60`;
- `REGISTRY_V1_DIGEST = fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc`.

"This acceptance pins the expected M-B6 ledger result only. It does not authorize M-B6 execution, M-B7 or later,
witness genesis, Record 1, First Memory, authority activation or PROD."

## 4. What the pin is and is not

**It is** the owner-accepted comparison target for M-B6:

- the M-B6 operator's `expected` form must reproduce it in the sequence's own work directory;
- the go must name it;
- the M-B6 verifier must observe it (`ledgerHeadEqualsOwnerComputed`) for `LEDGER_COMMITTED_EXACT`.

See the [M-B6 ceremony package](slice-15b2b-b1b3e-mb6-ceremony-package.md) E-21, §8 and §9.

**It is not:**

- ledger state (no ledger exists);
- a genesis commitment, or a witness genesis or witness genesis candidate;
- `OwnerGenesisPinV1` (M-B8);
- authority activation;
- Record 1;
- First Memory;
- evidence that Registry V1 is effective, or that freshness is current.

## 5. State

```text
OWNER_LEDGER_HEAD_DERIVED = YES
OWNER_LEDGER_HEAD_ACCEPTED = YES
OWNER_LEDGER_HEAD_PINNED_FOR_MB6 = YES
EXPECTED_LEDGER_SEQUENCE = 1
EXPECTED_LEDGER_HEAD = 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630
TRUST_INSTALLED = YES
REGISTRY_INSTALLED = YES
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
M-B6 = NOT AUTHORIZED
M-B7 = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD_1 = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED
```
