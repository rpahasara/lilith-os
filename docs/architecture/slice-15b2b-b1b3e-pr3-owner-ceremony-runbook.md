# Slice 15B2b-B1b-3e PR-3: Owner Freshness Ceremony Runbook (Template)

**Status: TEMPLATE.** This runbook contains no real record data, paths, or
device identifiers, and it must stay that way: it is public-safe. It was
rehearsed end to end on temporary synthetic replicas in P3-4 ([design
record §26](slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md)).

**Real use ([B-3](slice-15b2b-b1b3e-b3-real-acceptance.md)).** P3-3 is complete, and real acceptance is
enabled in source (`REAL_ACCEPTANCE_ENABLED = True`); burned rehearsal
identities are refused. A real ceremony is still usable **only inside an
authorized PR-1B (B-5)**, at `APPEND_RECORD_1_REPLICA_A` after M-B9b. Until
then real freshness is `FRESHNESS_UNKNOWN`, and no real `append` or
`append-envelope` may be run. (Superseded status: while P3-3 was
`P3_3_STORAGE_INCOMPLETE`, this runbook was not usable for real acceptance.)

```text
synthetic ceremony success != real owner freshness established
candidate != acceptance;  storage != acceptance;  Git != acceptance
```

## Preconditions (all required before a real ceremony)

| # | Precondition | How checked |
| --- | --- | --- |
| P-1 | two real replicas exist, empty or identical, admitted by `init-real-replica`, with distinct devices and independent rollback paths | `compare-replicas`, `check-independence`, owner evidence |
| P-2 | at least one replica is unreachable by agents and automation (D6) | owner custody |
| P-3 | pinned trust inputs (K-WIT anchor, registry root, registries) are held by the owner | owner custody |
| P-4 | the accepted genesis pin (`OwnerGenesisPinV1`) is held by the owner | owner custody |
| P-5 | the chain export comes from the presented DEV world | the export procedure (out of scope here) |
| P-6 | the tool runs from a reviewed commit, outside any Git working tree | the owner records the commit SHA |

In the steps below, placeholders are written `<LIKE_THIS>`. Replace them
only in the owner's private notes, never in this file.

## Steps

### 1. Inspect the authentic chain

```text
python -m lilith_owner_memory.owner_freshness_tool inspect-chain \
  --trust <TRUST_INPUTS> --chain <CHAIN_EXPORT> --environment <ENV> --profile <PROFILE>
```

- **Expected:** `authenticity = AUTHENTIC`. Record the head witness
  version and digest.
- `NOT_AUTHENTIC` → **STOP**.
- Authentic does not mean current.

### 2. Classify against the owner records

```text
... classify --replica <REPLICA_A> --replica <REPLICA_B> --trust <TRUST_INPUTS> \
  --chain <CHAIN_EXPORT> --environment <ENV> --profile <PROFILE>
```

| Result | Action |
| --- | --- |
| `CURRENT` | no ceremony is needed; the gates are met |
| `AHEAD_UNACCEPTED` | an owner decision is possible: accept (step 3, `propose-accept`) or reject (`propose-reject`) |
| `STALE` (`DEV_STATE_STALE`) | **STOP.** Never accept. Recovery is PR3-D10: fresh custody, a new genesis, and a new owner lineage |
| `CONFLICTING` | **STOP**, or reject the candidate. Never accept |
| `FRESHNESS_UNKNOWN` | **STOP.** Resolve the replica state by hand first. Nothing is repaired automatically |
| `REFUSED` | **STOP.** Fix the inputs |

### 3. Generate the candidate

```text
... propose-genesis --trust ... --chain ... --pin <GENESIS_PIN> --out <NEW_CANDIDATE_FILE> ...   # record 1 only
... propose-accept  --replica <A> --replica <B> --trust ... --chain ... --pin <GENESIS_PIN> --out <NEW_CANDIDATE_FILE> ...
... propose-reject  --replica <A> --replica <B> --trust ... --chain ... --pin <GENESIS_PIN> --out <NEW_CANDIDATE_FILE> ...
```

The output file must not already exist. The candidate carries
`"accepted": false`. **A candidate is not an acceptance.**

### 4. Human review

Read the candidate file and check each of the following:

- `decision`;
- `recordVersion`: exactly one more than the replicas' last record;
- `previousRecordDigest`: the replicas' head;
- `genesisWitnessDigest`: equal to the pin;
- `witnessVersion` and `witnessDigest`: equal to step 1;
- `recoveryEpoch` and `registryVersion`/`registryDigest`: the world you
  intend to accept.

Any doubt → do not continue. Delete nothing.

### 5. Confirm the exact digest

Copy the candidate's `recordDigest` by hand into `--confirm-digest`. That
digest confirms the owner's decision for this one record only.

### 6. Append to Replica A

```text
... append --replica <REPLICA_A> --peer <REPLICA_B> --candidate <CANDIDATE_FILE> \
  --trust ... --chain ... --pin <GENESIS_PIN> --confirm-digest <RECORD_DIGEST> ...
```

- **Expected:** `RECORD_APPENDED`, `replication = PEER_PENDING`,
  `directoryFsync = PERFORMED`.
- The tool re-derives the candidate and refuses anything else.

### 7. Observe the intermediate state

Run step 2 again.

- **Expected:** `FRESHNESS_UNKNOWN`
  (`REPLICAS_DIVERGENT:replica1:PREFIX`), with every gate blocked.
- This state is **intended**. Do not act on DEV while it lasts.

### 8. Append to Replica B

Run the same `append` with `--replica <REPLICA_B> --peer <REPLICA_A>`, using
the same candidate and the same digest.

- **Expected:** `replication = REPLICAS_IDENTICAL`.
- If an offline medium is attached for this step only, disconnect it again
  afterwards.

### 9. Compare replicas

```text
... compare-replicas --replica <REPLICA_A> --replica <REPLICA_B>
```

**Expected:** `OWNER_REGISTER_VERIFIED`.

### 10. Classify CURRENT

Run step 2 again.

- **Expected:** `AUTHENTIC` + `CURRENT`. For an accept ceremony, every
  gated operation is `FRESHNESS_PRECONDITION_MET`.
- For a reject ceremony, the rejected world is `CONFLICTING`
  (`OWNER_REJECTED_LINEAGE`), and the previously accepted world stays
  `CURRENT`.
- Meeting the gate authorizes nothing by itself.

## Never

- Accept `STALE`, `CONFLICTING`, `NOT_AUTHENTIC`, or `FRESHNESS_UNKNOWN`.
- Copy records between replicas by any means other than `append`.
- Repair a replica by deleting or editing files. Stop and record the state.
- Treat a Git commit, a mirror, a file timestamp, or the witness's own
  report as acceptance.
- Run a ceremony in which an agent chooses the confirmation digest.

## Known limitation

If **both** replicas are rolled back together to the same older history,
the register can falsely report an old world as `CURRENT`. Only an
independently newer copy reveals this. Keep the replicas on independent
rollback paths (P-1), and keep the owner's own memory of the latest
accepted record.
