# Recovery witness — Slice 15B2b-B1b-3e PR-1S

Status: **SOURCE IMPLEMENTED / TEST PROVEN. SOURCE PREPARED / NOT INSTALLED.**
No account, unit, credential, state directory, or witness exists on any
host. PR-1A is not authorized.

This is the source of the distinct DEV_SYNTHETIC `lilith-recovery-witness`
service: its own Unix identity, its own private key (K-WIT, runtime
credential `recovery-witness-signing-key`, keyId
`test-only.witness.dev-synthetic.b1b3d.1`), its own state
(`/var/lib/lilith-recovery-witness`), its own units, and its own failure
domain. It is not the authority signer. Record:
[slice-15b2b-b1b3e-pr1s-runtime-wiring.md](../../docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md).

```text
witness freshness       != authority
K-WIT credential exists != witness exists
installed code          != enabled mutation
service running         != current authority
```

K-WIT signs only `RecoveryWitnessV2` documents the pure planners produce.
There is no generic signing, OwnerEvidence, registry, authorization, or
Privacy signing path.

Track B B2 (SOURCE PREPARED / NOT INSTALLED) adds a second, separate key,
K-PAN (`kpan.dev-synthetic.01`), which signs only `PrivacyAnchorV1` strict
extensions over opaque Privacy suppression entries. It never sees Privacy
content, and K-WIT and K-PAN can never sign each other's documents.

| Path | Role |
| --- | --- |
| `lilith_recovery_witness/profile.py` | the fixed witness identity (from `pr1_bootstrap`) and sockets |
| `lilith_recovery_witness/credential.py` | K-WIT from `$CREDENTIALS_DIRECTORY` only; the one V2-only signer |
| `lilith_recovery_witness/storage.py` | the live filesystem storage port (dir-fd, `O_EXCL`, fsync, `flock`) |
| `lilith_recovery_witness/writer.py` | the durable V2 writer (pin-before-commit genesis, ledger advance, inert head/epoch execution) and recovery |
| `lilith_recovery_witness/protocol.py` | the closed two-socket protocol |
| `lilith_recovery_witness/core.py` | dispatch over fixed on-host inputs |
| `lilith_recovery_witness/server.py` | inherited-socket adapter and entrypoint (never auto-bootstraps) |
| `lilith_recovery_witness/privacy_anchor.py` | Track B B2: the K-PAN Privacy rollback anchor (owner socket only, own protocol id, own key `privacy-anchor-signing-key`, own state `/var/lib/lilith-privacy-anchor`; strict extensions only) |
| `deploy/` | the service, owner and signer sockets, tmpfiles (inert; never enabled) |
| `witness_release_file_set.py` | this tree's file set and its own manifest identity |
| `tests/` | repository tests (also run from the authority-dev suite) |

The runtime ships inside the one reviewed authority-dev release archive
(`lilith_recovery_witness/`, `assets/lilith-recovery-witness*`), with its own
manifest digest (`runtimeSha256`). It imports the shared host observers
(`lilith_authority_host`) and the pure `lilith_owner_memory` contracts of the
same release.

Local tests need the pinned Core API requirements in an isolated
environment:

```text
python -m unittest discover -s services/recovery-witness/tests -p "test_*.py"
```
