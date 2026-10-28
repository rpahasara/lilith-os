# DEV release candidate `f293e72-f9c2-cog1` (CANDIDATE, not installed)

This candidate is the installed DEV release [`f293e72-f9c2`](../dev-f9c2/README.md) with the unified-cognition
overlay from PR #278 ([`overlays/dev-unified-cognition`](../../overlays/dev-unified-cognition/README.md)). Every
cognitive lane stays off.

Nothing here has been installed on any host. No workflow can install it: the DEV workflow deploys only the Core API
bundle, and a classifier test forbids any workflow from referencing `integrations/`. The f9c2 release files are
unchanged, and its tests still assert the import stub.

## What changes against f9c2

[`RELEASE-DELTA.json`](RELEASE-DELTA.json) lists the four package members that change. Every other member of the
f9c2 package (`MANIFEST.sha256`, package SHA-256 `4b0b0110…`) is byte-identical, including:
- `home/router.yaml` (every lane off);
- the hardened `gateway_integration.py` and `lilith_os` adapter;
- `src/` (patched Hermes);
- the provider gate;
- the FORGET executor and the restore guard;
- the systemd units.

| Member | f9c2 | cog1 |
|---|---|---|
| `RELEASE_ID` | `f293e72-f9c2` | `f293e72-f9c2-cog1` |
| `home/lilith_router/world_context.py` | `5c1fbf98…` import stub | `07a763e1…` governed adapter |
| `home/lilith_router/_prod_world_context.py` | none | `46b8187e…0104`, recovered PROD Working Memory, byte-exact |
| `bin/verify_release.py` | from the f9c2 template (`865be123…`) | from [`templates/bin/verify_release.py.tmpl`](templates/bin/verify_release.py.tmpl) (`817f7cae…`) |

### Why the release verifier has to change

Every gateway start runs `verify_release.py --pre-start` from `ExecStartPre`. The f9c2 verifier refuses to start
unless `world_context.py` is the import stub (`WORLD_CONTEXT_NOT_THE_F7_STUB`). So placing the #278 files on an
f9c2 host would stop the gateway at its next start.

The cog1 verifier changes only that check. It now requires the adapter at `07a763e1…` and the PROD module at
`46b8187e…`. All other checks are identical, including:
- every lane off (`LANES_OFF`);
- no cognitive channels;
- the critical-file pins;
- the provider-gate pins.

The tests check this two ways. They diff the two templates. They also run both verifiers against the same fixture
hosts and get the same failures apart from the `world_context` check.

Turning any lane on, even in shadow, still fails this verifier at the next start. Lane activation therefore needs a
reviewed verifier revision of its own (Gate E).

## Building it

| Part | How | Reproducible from Git |
|---|---|---|
| `home/` code tree | `python integrations/hermes/overlays/dev-unified-cognition/tools/assemble_dev_cognition.py --out <dir>/home` (MODULES.json + OVERLAY.json, every byte checked) | yes; the tests check it against the f9c2 manifest plus the delta |
| `bin/verify_release.py` | replace `__LILITH_GATE_CLIENT_TOKEN__` in the cog1 template with the custody token. First prove that token with `integrations/hermes/tools/render_dev_f9c2_templates.py`, which must end `DEV_F9C2_TEMPLATES=PASS` | template yes; the token only at the authorized install stage |
| `RELEASE_ID` | this directory | yes |
| everything else | the f9c2 release bytes | `src/` yes (`reconstruct_hermes_src.py`). The interpreter, `uv`, wheels and the build backend are not in Git; take them from the installed f9c2 release directory, or from the f9c2 package in the owner archive |

Dependencies are unchanged. The adapter uses only the Python standard library and the lane modules already in the
tree.

## Compatibility with DEV (from source and records)

- **Core API origin.** The f9c2 release's accepted sandbox probe expects "Core API 127.0.0.1:8765 (permitted
  loopback)" to be open from the gateway sandbox (`bin/sandbox_probe.sh` P9). `bin/smoke_console.py` uses the same
  origin.
- **Core API code.** `services/core-api` has not changed since the last DEV Core API deployment (`d82f7da`,
  2026-10-26). The compatibility test runs exactly that `app.py`, on a throwaway synthetic database, behind the
  adapter. Results:
  - every lane read returns 200 JSON from a real route;
  - World Model, pending, goal, planning and ethics grounding all build;
  - the draft request reuses the existing unsent draft (Slice 7.3 de-dup), and goal creation is refused;
  - with every lane live, no table changes.
- **Shadow is not write-free on the Core API side.** `GET /os/goals/focus` records a `goal_trace` arbitration row
  whenever the focus winner differs from the last recorded one (`_record_focus_trace` in `app.py`). This is existing
  Core API behaviour, and the Command Center and PROD trigger it too. With lanes in shadow, the test sees at most one
  such row and no other table change. The #278 README describes reads as GET only; that is true of the adapter, and
  this is the one server-side effect a GET can have.
- **Provider data.** Shadow lanes make no model call. Live lanes put the following into the prompt:
  - World Model beliefs (entity, predicate, value, provenance source ids);
  - task titles and states;
  - draft ids, kinds, targets and subjects;
  - goal titles, states and blocked reasons.

  Slice 9 sends a bounded version of the same data to the gateway model. `/career/applications` is read only on the
  refused draft and goal paths, and only `role_title` and `company` are used. Recruiter name and contact never
  reach a prompt (tested).
- **FORGET.** The executor snapshots `lilith_router` when an erasure starts and requires it unchanged at the FILES
  phase. Install and rollback must therefore not run while a FORGET is pending, as `install_f9c.sh` and
  `rollback.sh` already require.
- **Critical pins.** `bin/pin_critical.sh` already hashes every file under `HERMES_HOME/lilith_router`, so both new
  files are pinned by the existing script.

## Blocker: no trusted install procedure for this change

The f9c2 release has two installers:
- `bin/install.sh`, first install only, which refuses when any release path exists;
- `bin/install_f9c.sh`, which adds the FORGET executor.

No reviewed procedure replaces files in an installed release. A manual root copy is not acceptable.

Proposed, as separate work for approval (not implemented here): a narrow `install_cog1.sh` built from the
`install_f9c.sh` pattern.
1. **Preconditions:**
   - root on `lilith-dev-01`;
   - `current` is exactly `f293e72-f9c2` and `verify_release.py --full` passes;
   - no FORGET pending;
   - C-3 reload preconditions;
   - the gateway stopped (Gate D).
2. **Stage the release.** Create `releases/f293e72-f9c2-cog1` as a copy of the f9c2 release directory, with the
   rendered cog1 `bin/verify_release.py` and `RELEASE_ID`. Regenerate its `RELEASE.sha256` and make it root-owned
   read-only.
3. **Install the code.** Install the two `lilith_router` files root `0644`, then atomically switch `current`.
4. **Re-pin and verify.** Run `bin/pin_critical.sh`. `verify_release.py --full` must end `F8_VERIFY_PASS`, and the
   protected-service state must be unchanged.
5. **Start.** Starting the gateway is a separate approved step.

The f9c2 release directory is left in place for rollback.

## Rollback (not executed)

1. Stop the gateway (`rollback.sh stop`). Rollback refuses while a FORGET is pending.
2. Switch `current` back to `releases/f293e72-f9c2`.
3. Restore `lilith_router/world_context.py` to the f9c2 stub (`5c1fbf98…`, from the f9c2 release `home/` or
   `integrations/hermes/home/variants/dev-f9c2/`). Remove `lilith_router/_prod_world_context.py`.
4. Run `bin/pin_critical.sh`. The f9c2 `verify_release.py --full` must pass.
5. Start the gateway (approved step).

No Core API, canonical-memory, Privacy, authority or witness state is touched. The adapter never writes, so nothing
needs reverting. The tests show the rolled-back `home/` tree equals the f9c2 manifest byte for byte, and the f9c2
verifier accepts it.

## Tests

```bash
python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1/tests -p "test_*.py"
python -m unittest discover -s integrations/hermes/overlays/dev-unified-cognition/tests -p "test_*.py"
```

`test_cog1_core_api_compat.py` needs the Core API's `fastapi`, plus `httpx` for `TestClient`. It skips without them
and reports NOT RUN.

The f9c2 `tests/test_f7_offline.py` belongs to f9c2 and still asserts the stub. Run against a cog1 home, two of its
checks do not apply:
- `DEV_IMPORT_STUB`;
- `test_enabling_a_lane_with_the_stub_fails_open`.

The cog1 contract above replaces them. The f7, f9a and f9b suites need a built Hermes runtime and were not run here.
