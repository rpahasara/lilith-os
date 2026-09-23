# Memory broker — Slice 15B2b-B1b-1

This is an isolated **synthetic-only software foundation**, not a running
service. It has no HTTP route, Unix socket, SSH relay, OS account, installer,
production credential, live Actor authority, or canonical-memory operation.

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

Repository CI does **not** discover these tests today, and the trusted DEV
exact-SHA Core API bundle does **not** include this package. Until a separately
reviewed trusted-control bootstrap is accepted, local success is not a claim
of required CI or DEV coverage.
