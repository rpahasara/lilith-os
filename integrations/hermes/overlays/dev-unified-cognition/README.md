# DEV unified cognition (PLANNED, not deployed)

This overlay is the integration path for the recovered PROD cognition on modern DEV. PROD's Working Memory and its
seven cognitive lanes (Slices 7.2 and 8–13) run on top of the DEV `f293e72-f9c2` Router V2 tree. DEV's security
and memory boundaries stay in force.

Nothing here is installed on any host, and no lane is turned on. DEV `router.yaml` keeps every lane off. Turning a
lane on, or installing this tree, needs separate owner approval.

## What changes against the f9c2 tree

| `HERMES_HOME` file | f9c2 (deployed) | This overlay |
|---|---|---|
| `lilith_router/world_context.py` | `5c1fbf98…` import stub | [governed adapter](lilith_router/world_context.py) |
| `lilith_router/_prod_world_context.py` | none | PROD `world_context.py` `46b8187e…0104`, byte-exact, copied at assembly from `home/variants/prod-lilith-01/` |
| everything else | unchanged | unchanged, including the hardened `gateway_integration.py` (`5ce4bbd4…`), the hardened `lilith_os` adapter (`8c3b0055…`) and `router.yaml` (`7bb4fbb5…`, lanes off) |

[`OVERLAY.json`](OVERLAY.json) records both files and their digests.
[`tools/assemble_dev_cognition.py`](tools/assemble_dev_cognition.py) builds the candidate tree from `MODULES.json`
plus `OVERLAY.json` and checks every byte:

```bash
python integrations/hermes/overlays/dev-unified-cognition/tools/assemble_dev_cognition.py --out /tmp/hermes-home
```

## How the integration works

The DEV gateway already contains PROD's lane orchestration. It differs from PROD's only in decision-log content: DEV
logs no message preview (F9-A D-2). The gateway calls 14 `world_context` functions, and on DEV those reached an
empty stub. The adapter exposes exactly those 14. The tests check that list against the gateway source.

Each function runs the PROD code as is. The adapter compiles the PROD file from the bytes whose SHA-256 it has just
checked. It then replaces the only three PROD functions that do I/O (the tests check that against the PROD source):

| PROD helper | Under the adapter |
|---|---|
| `_get_json` | GET to `127.0.0.1:8765` only, on an exact path allowlist: `/os/world`, `/os/tasks`, `/os/drafts`, `/os/goals`, `/os/goals/focus`, `/career/applications`, with the PROD query shapes. Never `/memory/*` or anything else. No proxy and no redirects; JSON only; 512 KiB per response; 2.5 s timeout. Read limits are in the next section |
| `_post_draft` (`POST /os/drafts`) | never sent; returns "not confirmed" |
| `_post_goal_json` (`POST /os/goals`) | never sent; returns "not confirmed" |

### Read limits

The adapter enforces its read budget per adapter call. There is no single budget for a whole turn.

| Scope | Limit | How it is held |
|---|---|---|
| One adapter call | 16 reads (`MAX_CALLS_PER_ENTRY`) | enforced; further reads return nothing |
| One gateway turn | at most 160 reads (`MAX_READS_PER_TURN`) | structural: the DEV gateway has 10 read-capable call sites and none is inside a loop (the tests check the gateway source), and each gets at most 16 |
| Measured (offline, every lane in shadow and in live, messages referencing 30 applications, 80 blocked goals) | 9 reads per call, 19 per turn | asserted exactly by the tests. The PROD bytes are digest-pinned, so a change shows up there |
| Core API refusing or timing out | 1 read, then none for 30 s | a transport failure opens a breaker; HTTP errors and malformed JSON do not open it |

A hung Core API therefore costs a turn at most one 2.5 s timeout, not one per read.

A lane's grounding text is capped at 16,000 characters. If the PROD bytes differ or fail to load, every detector
reports no intent and every builder raises inside the gateway's existing `try`. Routing then matches the stub
exactly. The adapter logs nothing.

## Compatibility decisions

| Component | Decision | Why |
|---|---|---|
| Intent detection, all lanes (7.2–13) | reuse as is | pure functions; PROD tests cover them |
| World Model, pending, goal grounding (7.2, 8) | reuse with a governed transport | reads only `lilith.db` World Model, task, draft, goal and career tables through Core API. `app.py` never imports `lilith_memory`, so canonical memory and Privacy-governed content cannot enter this way |
| Reasoning, Workspace, Motivation inputs (9–11) | reuse with a governed transport | bounded by the lane modules; read-only |
| Planning (12), Ethics (13) | reuse with a governed transport | proposal-only and advisory-only, no writes, deterministic; the LLM candidate paths are not wired |
| Durable draft creation (7.2/7.3) | **disabled** | Core API `POST /os/drafts` has no caller authentication or approval gate. Draft text is not under Privacy/FORGET governance |
| Durable goal creation (8) | **disabled** | same for `POST /os/goals` |
| PROD `router.yaml` live settings | reject as a DEV default | historical observation only |
| PROD gateway message preview in logs | reject | DEV's F9-A D-2 hardening stays |
| Router canonical LTM (`memory_store`, `canonical_ltm_enabled`) | not touched | not used by any lane; stays off |
| Owner and First Memory context (`hermes_memory_context`, root context socket) | not touched | the only governed route to canonical memory; separate planned overlay |
| Career watchers, automation, Discord/Gmail/Calendar | out of scope | not activated |

## Before any lane is turned on

1. **Release wiring.** A DEV release would install the two files above. `release/dev-f9c2/tests/test_f7_offline.py`
   checks `DEV_IMPORT_STUB` is true, so that release needs its own test revision, and a critical-file pin update
   (`pin_critical.sh`).
2. **Core API origin on DEV.** Confirm that DEV's Core API listens on `127.0.0.1:8765`, and confirm that its
   `/os/world`, `/os/tasks`, `/os/drafts`, `/os/goals` and `/career/applications` responses still match the
   shapes the tests use.
3. **Provider exposure.** Live lanes put World Model, task, draft, goal and career data into the model prompt. That
   prompt goes through DEV's provider gate, and Slice 9 live reasoning also runs a tool-less model call. Before any
   lane goes live, the owner must decide that career and World Model data may reach the configured providers.
4. **Shadow is not side-effect free.** In shadow, lanes still read Core API and append lane records to the decision
   log. The tests show those records hold no message text and no Core API content, but shadow logging still needs
   the DEV retention rules.
5. **Writes.** Before draft or goal creation can return, Core API needs an authenticated, approval-governed write
   path, and the drafts it creates must be brought under Privacy/FORGET.
6. **Rollout.** One lane at a time, `shadow` then `live`, on `lilith_os` only, with owner approval at each step.

## Rollback

On DEV, if this is ever installed, roll back like this. Restore the f9c2 stub (`5c1fbf98…`) as
`lilith_router/world_context.py`, and remove `lilith_router/_prod_world_context.py`. The tree then equals the
verified f9c2 tree byte for byte (`tests/` checks this). Setting a lane's flag to false disables that lane without
any code change. The adapter never writes, so no Core API, canonical-memory or Privacy state needs reverting.

## Tests

```bash
python -m unittest discover -s integrations/hermes/overlays/dev-unified-cognition/tests -p "test_*.py"
```

The tests use synthetic `TEST_ONLY` data and a fake Core API, with every socket blocked. No model is called. They
cover:

- byte-exact assembly;
- unchanged DEV hardening;
- with every flag off, routing and the decision log identical to the stub;
- shadow side effects;
- each live lane against the fake API;
- no writes;
- the transport allowlist, per-call budget, proxy and redirect refusal, size and content-type limits;
- reads per complete turn: the gateway call-site bound, the measured envelope, and the breaker for a hung Core API;
- unavailable and malformed API responses;
- tampered PROD bytes;
- the grounding cap;
- rollback.
