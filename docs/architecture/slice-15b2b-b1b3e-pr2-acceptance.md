# Slice 15B2b-B1b-3e — PR-2 Acceptance: DEV Snapshot / Rollback Inventory

Status:

- **ACCEPTED** (owner acceptance, 2026-09-29)
- **CLASSIFICATION: `PR2_INVENTORY_COMPLETE`**
- **SCOPE: READ-ONLY INVENTORY ONLY**
- **LIVE_MUTATION = NONE**. This record is documentation only. Neither DEV nor any cloud resource was contacted to write it.
- **PR-1B NOT AUTHORIZED**; **PR-3 NOT AUTHORIZED**; **FIRST MEMORY NOT AUTHORIZED**

```text
PR-2                                     = ACCEPTED
CLASSIFICATION                           = PR2_INVENTORY_COMPLETE
WHOLE-HOST ROLLBACK RESISTANCE           = NOT ESTABLISHED
INDEPENDENTLY PERSISTED FRESHNESS STATE  = NONE
LIVE_MUTATION                            = NONE
```

This record accepts the
[PR-2 snapshot / rollback inventory](slice-15b2b-b1b3e-pr2-snapshot-inventory.md),
the gate §14 PR-2 row of the
[live-rehearsal gate](slice-15b2b-b1b3e-live-rehearsal-gate.md) (RR-17). It
follows the [PR-1A acceptance](slice-15b2b-b1b3e-pr1a-acceptance.md).

## 1. Canonical conclusion

```text
WHOLE-HOST / WHOLE-DISK ROLLBACK CAN PRESENT A SELF-CONSISTENT OLD AUTHORITY WORLD.
WHOLE-HOST ROLLBACK RESISTANCE = NOT ESTABLISHED.
INDEPENDENTLY PERSISTED FRESHNESS STATE = NONE.
```

## 2. Pinned identities

| Identity | Value |
| --- | --- |
| PR-2 evidence commit | `932a79aaa1fe6d8f69a55e029353dcbc44c373c1` |
| PR-2 starting main | `db22f09a66a91f2fe05cad3b1f11815a856c1367` |
| raw evidence `SHA256SUMS` digest (private, outside the repository) | `f967e5db574a8ec1db16aad68bcb0d7a1fbfa68091f9ef67f1c8ce2c5b07b666` |
| host observer `stableSha256` at PR-2 | `5eaec23cef9c8f53db8e6f27e84b270ad6b8567d4f21287a1ffd543550fe2778` (equal to the M-A10 POST) |
| installed authority release | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| boot | `24d1771d…` (continuous; reboot still pending) |

## 3. Accepted findings

| # | Finding | Inventory § |
| --- | --- | --- |
| F-1 | DEV has **one** 20 GB zonal `pd-balanced` boot disk with Google-managed encryption. There is no other disk, no local SSD, no regional or async replica, no LVM/md, and no swap | §3 |
| F-2 | Every current and future persistent authority and custody object maps to the same ext4 root filesystem `/dev/sda1` (`st_dev 2049`), with no mount beneath any authority path | §5 |
| F-3 | No independent persistent freshness store exists | §10 |
| F-4 | No relevant snapshot, instant snapshot, snapshot schedule / resource policy, machine image, custom image, provider backup (Backup and DR is not enabled), or on-host backup was found | §4 |
| F-5 | Provider Admin Activity audit history shows no snapshot, image, clone, attach, detach, stop, start, or suspend operation in the observed project lifetime | §4 |
| F-6 | `credential.secret` and the host-key-sealed credential blobs share **one rollback domain**. A snapshot would capture each blob and its decryption secret as one historical pair | §7 |
| F-7 | Under the present topology, the future K-ACT, K-WIT, registry, authority ledger, witness state, and custody holds would all share one rollback domain | §8, §9 |
| F-8 | Runtime credentials (`/run/credentials/<unit>`) and sockets and runtime directories under `/run` do not survive a reboot. They are rebuilt from the persistent disk state | §6 |
| F-9 | A same-host RecoveryWitness can help detect a partial or ledger-only rollback **only while the witness state survives** | §10 |
| F-10 | A whole-disk rollback rolls the witness and the ledger back **together**, and they stay consistent with each other | §9, §10 |

The security-model result stays **per property** (inventory §11):
`ROLLBACK_LEDGER_ONLY`, `ROLLBACK_WITNESS_ONLY`, `ROLLBACK_CREDENTIAL_ONLY`,
`ROLLBACK_BOOT_DISK`, `ROLLBACK_WHOLE_HOST`, and `ROLLBACK_EXTERNAL_STATE`
are not collapsed into one "rollback protected" boolean.

## 4. Hidden-assumption result (preserved)

```text
SERVICE SEPARATION       != PERSISTENCE SEPARATION
CRYPTOGRAPHIC SEPARATION != ROLLBACK SEPARATION
SIGNATURE VALIDITY       != FRESHNESS
```

The signer and the witness have separate users, units, keys, and state
directories. All of them sit on one filesystem, on one disk, under one root,
sealed by one host key. K-WIT, K-ROOT, and registry signatures authenticate
an old state exactly as well as the latest one (inventory §12).

## 5. Open risks carried forward

| ID | Risk |
| --- | --- |
| OR-1 | whole-disk authority-world rollback |
| OR-2 | root-equivalent principals (DR-3 `ubuntu`; PROD deployer project-level `osAdminLogin`), and possible host-local copies |
| OR-3 | cloud principals able to perform a future snapshot, image, or clone operation |
| OR-4 | no external freshness source |
| OR-5 | pending kernel reboot |
| OR-6 | the next boot may create `/run/lilith-*` through tmpfiles; post-reboot `P1A-9` compatibility is not yet verified |
| OR-7 | the service `PrivateTmp=` backing remains within the disk snapshot domain |
| OR-8 | any future snapshot creation can make this inventory stale |
| OR-9 | visibility outside the accessible projects is not established |

None is remediated by PR-2 or by this acceptance.

## 6. Explicit nonclaims

PR-2 and this acceptance do **not** establish:

- rollback resistance;
- independent witness freshness;
- K-WIT custody (no K-WIT exists);
- K-ROOT authority;
- registry authority (no registry exists);
- an authority ledger (none exists);
- witness genesis or witness state (none exists);
- `INITIAL_CUSTODY`;
- owner acceptance of any custody, authority, or RR-17 environment bound.
  This record accepts only the inventory;
- PR-1B readiness;
- First Memory readiness.

Also preserved: there is **no claim that K-ACT has never had a host-local
copy**. The only finding is that no provider-level snapshot, image, or clone
copy exists or has existed (OR-2).

## 7. What follows

In the accepted dependency order
([preflight §20](slice-15b2b-b1b3e-pr1-live-install-preflight.md)), PR-3
foundation comes next. **PR-3 is not authorized by this record.** PR-1B stays
blocked on PR-3 and on its own separate authorization.

```text
PR-2 ACCEPTED
PR2_INVENTORY_COMPLETE
WHOLE-HOST ROLLBACK RESISTANCE NOT ESTABLISHED
NO INDEPENDENT FRESHNESS STATE
NO K-WIT
NO REGISTRY
NO LEDGER
NO WITNESS STATE
NO INITIAL_CUSTODY
PR-1B NOT AUTHORIZED
PR-3 NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
