# Acceptance: World Model shadow on DEV (`f293e72-f9c2-cog1-wm1`), 2026-10-28

**Decision:** owner-accepted as **PASS** on 2026-10-28. This covers **World Model shadow behaviour only**. It does not
authorize live cognition or any other lane.

## Runtime accepted

| Item | Value |
|---|---|
| Host | `lilith-dev-01` (boot `cb0d71da…`, unchanged throughout) |
| Release | `f293e72-f9c2-cog1-wm1`, installed 07:16Z, gateway started 07:19:50Z (PID 334256) |
| Lanes | `cognitive_enabled: true`, `cognitive_mode: shadow`, `cognitive_channels: [lilith_os]`; the other nine lanes `false` |
| Start-time gate | `F8_VERIFY_PASS pre-start f293e72-f9c2-cog1-wm1` |
| Hashes | adapter `07a763e1…`, PROD Working Memory `46b8187e…`, gateway `5ce4bbd4…`, router `4035f0a1…`, plugin adapter `8c3b0055…` |
| Rollback releases kept | `f293e72-f9c2-cog1` (every lane off) and `f293e72-f9c2`, both manifests intact |

## Evidence

The test sent 2 `TEST_ONLY` console turns at 09:10:54–09:11:05Z, in session `wm1-shadow-test-20261028`. The provider
gate was `BUDGET_EXHAUSTED`, so it refused the model calls locally.

| Criterion | Result |
|---|---|
| Positive message: one World Model shadow record (`belief=True`, synthetic `app_id`, length match) | PASS |
| Negative control: no shadow record | PASS |
| Routing records `live=False`; no other lane | PASS |
| No message text in decision records | PASS |
| Provider: no request, budget unchanged (5/5) | PASS |
| Core API: 0 `/os/*` or `/career/*` requests in the window (access logging verified: 2 lines from the current process, 98 in 7 days) | PASS |
| Gateway stable; Core API, provider gate, FORGET, broker, authority and witness unchanged | PASS |

## Unexpected artifacts, resolved

Hermes wrote two `sessions/request_dump_*.json` files (754 and 755 bytes) when the model calls were refused. They
were deleted at 09:41:29Z by an owner-approved targeted removal. The removal pinned type, owner, mode, size, inode,
device, mtime and link count, and checked the files were not open. `sessions.json` and every service were unchanged.

The following remain, synthetic and under the existing 7-day retention and FORGET: 3 decision records, the test
session's Hermes rows, and its log lines.

## Evidence folders (owner workstation; `SHA256SUMS` in each)

`lilith-dev-wm1-p0-20261028` (`b20b6b6e`), `lilith-dev-wm1-gated-stop-20261028` (`6b4189d8`),
`lilith-dev-wm1-gatee-20261028` (`8d18e60e`), `lilith-dev-wm1-gated-start-20261028` (`06b3c8b3`),
`lilith-dev-wm1-observe-20261028` (`beca3afa`), `lilith-dev-wm1-shadowtest-20261028` (`a23b1a19`),
`lilith-dev-wm1-followup-20261028` (`64bb6556`).
