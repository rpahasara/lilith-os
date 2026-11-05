# `prod-canonical-memory-context/` (PREPARED for PROD `lilith-01`; not deployed)

Canonical memory for the console and the owner's private Telegram chat (owner decision D-5), through the Router V2
seam PROD already runs. No Hermes core file changes (`gateway/run.py` stays at its PROD bytes), and no adapter hunk:
the router covers every platform.

| File | What it is |
|---|---|
| `canonical_memory.py` | new `lilith_router` module: owner-channel decision, one context-service request per turn, note merge, agent rebuild when the note changes |
| `lilith_memory_context.py` | byte-identical copy of `services/owner-memory-control/lilith_owner_memory/hermes_memory_context.py` (the renderer) |
| `base/gateway_integration.py` | the deployed PROD router (`4db8bb58…`: Cutover 2 + the two Test 4 fixes; audit run 2 pin MATCH 2026-11-05), the patch base (R3c rebase from `99fe9064…`) |
| `gateway_integration.py`, `gateway_integration.patch` | that file plus 4 hunks: import, `route_turn` wrapper (note before routing, merge after), lean social reply gets the note |
| `tests/test_prod_canonical_memory.py` | channel isolation, settings, merge/rebuild, patch integrity |

## Behaviour

| Turn comes from | Channel sent to the root service | Can receive personal memory |
|---|---|---|
| Command Center (`lilith_os`) | `lilith_os` | yes, if the grant lists it |
| Telegram private chat, user id in `ownerTelegramUserIds` and equal to the chat id | `telegram_owner_dm` | yes, if the grant lists it |
| Telegram group or channel, another user, any Discord chat or DM, anything else | `public` | **never** (the service cannot grant `public`; the router also refuses to render personal memory for `public`) |

- **Off by default.** Nothing happens until root installs `lilith_router/canonical_memory.json`
  (`{"schemaVersion":1,"enabled":true,"ownerTelegramUserIds":["…"]}`, root-owned, not writable by others) and the
  owner writes a v3 grant naming the channels.
- **The note is ephemeral.** It goes into the main agent's ephemeral prompt on every route that runs the main
  agent, and the lean social prompt gets it too. Ready answers with no main-agent call (Reasoning, Planning, Ethics)
  are unchanged.
- **Changes take effect on the next turn.** When the note changes (an admission, a FORGET, an expired grant or a
  Privacy lock), the session's cached agent is rebuilt once.
- **Failures never break a turn.** Any failure means no note, and the turn proceeds as today.

## Limits (D-2)

- A FORGET erases canonical records and stops the note at once.
- It does not erase replies LILITH already sent: Telegram keeps its own copy of the chat, and Hermes keeps
  `state.db`.

## Before enabling on PROD (P2/P7/P8 of the release plan)

1. Re-read PROD read-only. The router must still be `4db8bb58…`; if it drifted, rebase the 4 hunks.
2. Run the Cutover 2 corpus harness (`c2_corpus.py`) on the patched tree with the feature **off**. Every turn must
   be byte-identical to today.
3. Run one owner console check after the grant (P7), and one owner Telegram DM check plus one Discord check (P8).
