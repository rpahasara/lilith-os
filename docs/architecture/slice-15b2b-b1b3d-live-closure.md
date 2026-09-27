# Slice 15B2b-B1b-3d — DEV_SYNTHETIC Custody Preparation Live Closure

Status: CLOSED  
Environment: DEV_SYNTHETIC  
Closure date: 2026-09-27  
Authority class: synthetic OWNER_ACTOR custody only  
Next slice: B1b-3e — rotation, revocation, restore, and recovery semantics

## 1. Purpose

This record closes the live B1b-3d custody-preparation ladder.

B1b-3d established that a DEV_SYNTHETIC OWNER_ACTOR signing key can be
generated on the DEV host, encrypted into the host-bound systemd credential
mechanism, retained outside the routine deployer's authority boundary, and
preserved across a normal routine DEV deployment without activating authority.

This closure does not establish real-owner-grade custody, accepted authority,
activation, memory acceptance, truth, identity, or production readiness.

The governing separations remain:

- credential custody != accepted authority
- installed service != active service
- model proposal != authority
- deployment != activation
- storage != acceptance
- memory != truth
- runtime != identity

## 2. Closed live ladder

The following live transitions are complete:

| Step | Result |
| --- | --- |
| L0 | PASS |
| L1a | PASS |
| S-1 | PASS, later consumed |
| L1b.1 | PASS |
| S-2 | PASS |
| L1b.2 | PASS |
| L1c.1 | PASS |
| L1c.2 | PASS |
| L1c.3 | PASS |
| L2a | PASS |
| L2b.1 | PASS |
| L2b.2 | PASS |

No further B1b-3d mutation is authorized by this record.

## 3. Pinned artifacts and control generations

Authority release:

`RELEASE_SHA=9ac7de22bf977385ceb954624677e33f0bae062b`

Protected-main control generation used for the final routine-deployer proof:

`CONTROL_SHA=293a4c3f3c225dd57113d207133eacb8ffa236cb`

Accepted broker release:

`817a83e44cec8965479fd97fc30b7a0b3ae49ab2`

Accepted broker baseline candidate SHA-256:

`3549585487ad46ead96a0cb1af30a15be0c4ac17575663816e8e11dc80a7eee5`

Accepted broker runtime incarnation:

`42af2691b8d24ee5a92a286197c5444c`

K-ACT identifier:

`test-only.dev-synthetic.actor.b1b3d.1`

Signing domain:

`OWNER_ACTOR`

Algorithm:

`Ed25519`

## 4. K-ACT custody result

The DEV_SYNTHETIC OWNER_ACTOR key ceremony completed successfully.

Credential blob:

`/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred`

Observed contract:

- owner: `root:root`
- mode: `0600`
- credential store: `root:root 0700`
- host credential key: `/var/lib/systemd/credential.secret`
- host credential key mode: `root:root 0400`

Credential blob SHA-256:

`6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3`

The root-run L2b.2 installer status returned:

- `result=PASS`
- `stage=L2b.2`
- `failures=[]`
- both host prerequisites `PRESENT_SECURE`

The publication JSON's `blobSha256` matched the installer's
`credentialBlobSha256`.

The publication contained only public verification material and custody
metadata.

## 5. Leakage checks

The L2b.2 closure included:

- publication private-key-pattern scan: PASS
- journal private-key-pattern scan around the ceremony: PASS

No private-key pattern was observed in either scan.

The ceremony requirement that swap be absent was satisfied before key
generation.

The following remain explicitly NOT_PROVEN:

- private-key memory zeroization
- remanence elimination
- plaintext absence from RAM during the ceremony
- protection from privileged host memory inspection
- whole-host or snapshot rollback protection

These are not reinterpreted as proven by successful key generation.

## 6. Signer and activation state

At closure:

- `lilith-authority-dev.service` is loaded but inactive
- `lilith-authority-dev.socket` is loaded but inactive
- neither unit is enabled
- no signer runtime directory exists
- no signer state directory exists
- `/etc/lilith-authority-dev` is absent
- `/run/credentials/lilith-authority-dev.service` is absent
- recovery-witness runtime and state paths are absent
- K-WIT is absent

Activation remains deliberately dark:

`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`

Therefore:

credential custody != signer activation  
signer installation != signing availability  
activation darkness remains preserved

## 7. DR-5 routine deployer boundary

The final post-K-ACT routine deployment used protected-main candidate:

`293a4c3f3c225dd57113d207133eacb8ffa236cb`

The deployment workflow completed successfully.

The live routine deployer identity was:

`sa_112096412008414111981`

The authority-boundary proof established, non-vacuously, that the routine
deployer could not:

- `sudo -u lilith-authority-dev`
- start, stop, restart, reload, enable, disable, mask, unmask, edit, or
  otherwise control the authority service or socket
- invoke `lilith-authority-keygen-dev`
- write the authority release tree
- write the installed authority unit, socket, tmpfiles file, or keygen CLI
- read or write `/var/lib/systemd/credential.secret`
- read, write, or traverse `/etc/credstore.encrypted`

The K-ACT blob itself was reported:

`UNOBSERVABLE_BY_DESIGN`

This is intentional. The deployer cannot traverse the credential store, so
blob existence and custody consistency remain the responsibility of the
root-run installer status rather than the deployer proof.

The final boundary verdict was:

`AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`

The deployer-observed maturity ending at L1c.3 is intentional and does not
conflict with root-observed custody maturity L2b.2.

DR-5 is therefore CLOSED for B1b-3d.

## 8. Routine-deployment preservation

After the live DR-5 proof passed, the normal DEV deployment completed
successfully for candidate:

`293a4c3f3c225dd57113d207133eacb8ffa236cb`

After that routine deployment:

- root-run `status --expect L2b.2` remained PASS
- the K-ACT credential blob remained present with the same SHA-256
- both host prerequisites remained PRESENT_SECURE
- authority units remained inactive
- broker preservation remained PASS
- activation remained `GRANT_ABSENT`

This establishes that the B1b-3d custody state survived the normal routine
DEV deployment path without becoming part of the routine deployer's
authority.

## 9. Broker preservation

The post-deployment broker preservation verifier returned:

`BROKER_PRESERVATION=PASS`

with:

- accepted baseline candidate unchanged
- accepted runtime incarnation unchanged
- `failures=[]`
- release equivalence preserved
- config equivalence preserved
- identity boundary equivalence preserved
- socket boundary equivalence preserved
- Stage III untouched

The verifier correctly continued to report:

`authorityCustodyJudgment=NOT_PERFORMED`

and:

`authorityMaturity=NOT_ESTABLISHED_BY_PRESERVATION`

This is not a gap.

The broker preservation verifier owns broker-preservation evidence only.
Exact authority state is owned by the root-run authority installer status,
and routine-deployer denial is owned by DR-5.

## 10. Negative-result handling

An attempted rerun of historical workflow run `36267577821` failed before
classification and before cloud authentication because its original
validated SHA was:

`9ac7de22bf977385ceb954624677e33f0bae062b`

while protected main had advanced to:

`293a4c3f3c225dd57113d207133eacb8ffa236cb`

The protected-main provenance check failed closed.

No DEV mutation or DR-5 execution occurred in that failed replay.

The old run was not retried again.

A current-main run was used instead.

## 11. Residual open risks and non-claims

### DR-3 — OPEN

The `ubuntu` host account remains root-equivalent through `sudo` and `lxd`.

B1b-3d proves the routine deployer boundary, not denial against host root or
root-equivalent operators.

### Whole-host rollback — OPEN

Host-bound systemd credentials do not, by themselves, solve whole-host or
snapshot rollback.

### Zeroization — NOT_PROVEN

The keygen reduced avoidable persistence paths but did not prove memory
zeroization or remanence elimination.

### Real owner custody — NOT ESTABLISHED

This is DEV_SYNTHETIC custody only.

### Accepted authority — NOT ESTABLISHED

No AuthorityKeyRecordV1 registry admission, activation grant, authority
state, signer readiness, or accepted signing capability is established by
this closure.

### First Memory — NOT AUTHORIZED

No First Memory ceremony or accepted-memory transition is authorized by
B1b-3d closure.

## 12. Closure decision

B1b-3d has satisfied its live acceptance purpose:

1. exact DEV_SYNTHETIC K-ACT custody exists;
2. the private key was converted to a host-bound encrypted credential;
3. public and ciphertext evidence are consistent;
4. leakage scans passed;
5. the routine deployer has no authority-custody reach;
6. the custody state survived a real routine DEV deployment;
7. broker preservation remained intact;
8. activation remained dark.

Therefore:

`B1b-3d DEV_SYNTHETIC custody preparation = CLOSED`

`DR-5 = CLOSED`

`DR-3 = OPEN`

The next authorized design slice is:

`B1b-3e — rotation, revocation, restore, and recovery semantics`

B1b-3e begins as source/design work only. No new live mutation is authorized
by this closure record.
