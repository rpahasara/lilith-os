# Authority signer — Slice 15B2b-B1b-3d L1 source foundation

Status: **B1b-3d L1 SOURCE FOUNDATION IMPLEMENTED.** Not installed, not
started, no credential, no authority.

This is the source for the distinct DEV_SYNTHETIC OWNER_ACTOR authority
signer, `lilith-authority-dev.service`. It is not the memory broker, the Core
API, Hermes, or a Privacy signer. The record is
[slice-15b2b-b1b3d-l1-authority-signer-foundation.md](../../docs/architecture/slice-15b2b-b1b3d-l1-authority-signer-foundation.md);
the design is
[slice-15b2b-b1b3d-dev-synthetic-custody-design.md](../../docs/architecture/slice-15b2b-b1b3d-dev-synthetic-custody-design.md).

```text
source-controlled artifact != installed service
installed service          != credential custody
credential custody         != accepted authority
signing output             != accepted memory
accepted authority         != truth
```

| Path | Role |
| --- | --- |
| `lilith_authority_dev/profile.py` | DEV_SYNTHETIC profile, fixed OS identity and paths |
| `lilith_authority_dev/credential.py` | fail-closed inspection of the `owner-actor-signing-key` systemd credential |
| `lilith_authority_dev/evidence_minter.py` | structured-only `OwnerEvidenceV2` minter (not wired in L1) |
| `lilith_authority_dev/protocol.py` | closed owner-socket protocol: `HEALTH`, `ISSUE_OWNER_EVIDENCE` |
| `lilith_authority_dev/core.py` | dispatch; readiness is always `NOT_READY` in L1 |
| `lilith_authority_dev/server.py` | inherited-socket, root-peer-only adapter and entrypoint |
| `deploy/` | inert unit, socket, and tmpfiles material |
| `release_file_set.py` | exact source and runtime file-set contract |
| `tests/` | repository tests; TEST-only keys from the B1b-3a fixture |

Local tests need the pinned Core API requirements in an isolated
environment:

```text
python -m unittest discover -s services/authority-dev/tests -p "test_*.py"
```

Nothing here is shipped by the routine Core API deployment. The tree is
outside `services/core-api/**` (the PROD path filter) and outside
`services/memory-broker/` (the broker file set).
