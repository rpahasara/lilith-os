# `dev-canonical-memory-context/` (cm1: installed and validated on DEV, 2026-11-04)

The canonical-memory conversation read route for the `lilith_os` console on `lilith-dev-01`. It replaces the
earlier `dev-planned-memory-context/` sketch, which was written against an older adapter and never installed.

| File | SHA-256 | What it is |
|---|---|---|
| `adapter.py` | `f8930360…` | the installed f9c2/e1 adapter (`8c3b0055…`) plus one hunk: each turn's `channel_prompt` is the canonical-memory note |
| `lilith-os-adapter-memory-context.patch` | `a796427c…` | that hunk, applied with `patch` to `8c3b0055…` it yields `f8930360…` exactly |
| `lilith_memory_context.py` | `a32c5e41…` | byte-identical copy of `services/owner-memory-control/lilith_owner_memory/hermes_memory_context.py` (also in the DEV host tree) |
| `cm1_window.sh` | see `SHA256SUMS` | the DEV window: `preflight`, `install`, `turn 1/2`, `check`, `close`, `revert` |

The root side lives with the other host-setup assets in `services/owner-memory-control/tools/hermes_context/`:
`canonical_context_service.py` and the socket-activated unit pair.

## How a turn gets canonical memory

1. The adapter receives a console turn and asks `/run/lilith-first-memory-context.sock` (root:lilith 0660) once, with
   `{"v":1,"channel":"lilith_os","sessionId":…}`, 20 s timeout.
2. systemd runs `canonical_context_service.py` as root under the installed authority release's venv. It runs the
   release's own `first-memory-context` code: the trusted host tree is checked, the host is dropped to `lilith`,
   gets only the context token, and the bridge forwards only `LOOKUP_EVIDENCE_USE`. The host recalls only ACCEPTED
   canonical memory and refuses when Privacy is not READY for this boot or a FORGET is pending.
3. The release keeps owner-personal memory back unless the Hermes Privacy floor covers it. The service adds one
   rule, owner decision **D-2**: a root-owned v2 grant that states `forgetScope: CANONICAL_RECORDS_ONLY` lets
   owner-personal memory reach `lilith_os` (never another channel). The answer then carries the same `forgetScope`.
4. The adapter renders one labelled note and sets it as `event.channel_prompt`. Hermes adds it to that turn's
   ephemeral system prompt (`gateway/run.py` `combined_ephemeral`), passes it through the Router V2 seam unchanged on
   every route, and never persists it. Any failure anywhere means no note.

## FORGET scope (D-2), stated plainly

A FORGET of a canonical memory erases its canonical records (L04 / L18) and, because the note is rebuilt from
canonical storage on every turn, stops it reaching any later turn. **It does not erase what LILITH already said in
earlier chat turns** (Hermes `state.db`), for example a reply that quoted the memory. No conversation-history
erasure is claimed. That needs the Hermes FORGET executor work for the PROD Hermes release (inventory gap G-3).

## DEV state after cm1 (2026-11-04)

- Installed: the service at `/usr/local/lib/lilith-canonical-context/`, the two units in `/etc/systemd/system/`
  (socket started, **not enabled**: a reboot removes the route until it is started again, and Privacy needs its
  per-boot unlock first anyway), the adapter and context module in `HERMES_HOME/plugins/lilith_os/`, and the v2
  grant (`ALL_LILITH_OS_SESSIONS`, expires 2026-11-07T08:30:11Z; after that personal memory stops, the codename stays).
- DEV runs the service as installed on 2026-11-04 (`187e30c9…`: grant v1/v2). The source here has since added
  the v3 grant (owner channels list, D-5); `cm1_window.sh` now pins those bytes, so a DEV re-install would carry
  them. The installed DEV grant is v2 and is unaffected.
- Provider gate back to its exact pre-install `gate.json` (`b652422f…`, budget exhausted 22/5).
- `cm1_window.sh revert` restores every pre-install byte (`critical.sha256` is compared with the saved copy).

Evidence: the cm1 phase outputs are kept in the owner's local release folder, outside the repository. The turn
replies contain the owner's personal statement and must not be committed.
