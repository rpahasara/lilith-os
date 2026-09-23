# Memory broker — Slice 15B2b-B1b-1 and B1b-2a candidate

This is a **synthetic-only software foundation**, not a running service. B1b-2a
adds a persistent DEV-only configuration, non-canonical synthetic evidence
store, inherited-socket server adapter, and proposed systemd assets. Nothing
is installed or provisioned on a VM in B1b-2a. There is no HTTP route, live
SSH/Windows relay, production credential, live Actor authority, or canonical
memory operation.

The package imports the governed `lilith_memory` contracts from
`services/core-api/lilith_memory` as a library; it never imports or starts
`services/core-api/app.py`. Its only fixture is
`fixture.b1b1.synthetic-codename.v1` with a deliberately non-production memory
class and `.invalid` RP. The logical owner is `owner.ravindu.v1`; the synthetic
access identity is not a real enrollment.

For local focused tests, install the existing pinned Core API requirements in
an isolated Python environment, then run:

```text
python -m unittest discover -s services/memory-broker/tests -p test_*.py
```

Tests use temporary owner-control and cognitive databases. The fixed test
private scalar is in the existing B1a test fixture only, never this package.
The owner-control test initializer requires `LILITH_ENV=test` and an OS temp
directory. Production-mode startup only validates a governed existing ledger;
this substage provides no production initializer.

`dev_core.py` is a separate runtime, requiring `LILITH_ENV=dev` and a closed
root-owned configuration pinned to `lilith-dev-01`, its machine ID, the exact
release SHA, the fixed public synthetic credential fingerprint, both schema
fingerprints, and explicit absence of canonical/Privacy/key custody. The
public-only credential fixture is under `deploy/`; its private test scalar is
not shipped. Explicit provisioning and ordinary startup are separate.

`dev_proof.py` is a broker-local DEV synthetic verification boundary, not a
change to the Core API B1a `.invalid` RP guard. Its verification and durable
consumption semantics must be parity-tested against B1a. `dev_core.py` links
consumed proof to a `synthetic_claim_v1` and separate
`synthetic_evidence_v1`, never to `ActorEvidenceRefV1`. It imports no
`canonical_authority` and requires no cognitive/Privacy DB or authority key.
The original B1b-1 `core.py` remains test-only and must be excluded from an
operational release.

`server.py` accepts only one systemd-passed AF_UNIX listener FD; it cannot
bind a socket. It checks kernel `SO_PEERCRED` before framing and exposes only
HEALTH, PREPARE_SYNTHETIC, CONFIRM_SYNTHETIC, and CANCEL. ACCESS_CONTEXT is not
exposed. The proposed service, socket, tmpfiles rule, and configuration schema
are inert source files under `deploy/`.

Existing trusted DEV controls still validate the B1b-1 exact-SHA artifact
transiently and do not install this runtime. A separately governed control
bootstrap must freeze the release file set and install/rollback policy before
any DEV OS change. B1b-2b installation and service persistence remain subject
to later owner authorization.
