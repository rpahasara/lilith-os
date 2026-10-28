# Installing `f293e72-f9c2-cog1` on DEV (REVIEW ONLY, not run)

[`bin/install_cog1.sh`](bin/install_cog1.sh) is the trusted installer that the [README](README.md) lists as a
blocker. It supersedes that README's "Blocker" section. Nothing here has been run on any host. Running it needs
explicit owner approval for each gate below.

## What it does

`install_cog1.sh install <payload-dir>`:
1. **Refuses before changing anything** unless all of these hold:
   - root on `lilith-dev-01`;
   - the payload directory is root `0700` and holds exactly the six pinned files;
   - `current` is `f293e72-f9c2` and its own `verify_release.py --full` passes;
   - the installed `world_context.py` is the f9c2 stub, and no `_prod_world_context.py` exists;
   - the installed f9c2 verifier has its manifest digest;
   - the gateway is not active;
   - no FORGET intent or erasure marker exists;
   - there is enough space.
2. **Stages `releases/f293e72-f9c2-cog1`** as a copy of the f9c2 release. Its `bin/verify_release.py` is rendered on
   the host: the installer proves that the f9c2 template, with the installed token, reproduces the installed f9c2
   verifier byte for byte, then applies the same token to the cog1 template. The token is never transferred,
   printed or stored anywhere new. It then sets the cog1 `RELEASE_ID`, regenerates `RELEASE.sha256`, and makes the
   tree root-owned read-only. The f9c2 release is not modified.
3. **Installs** `_prod_world_context.py` and then the adapter as `world_context.py` (root `0644`, atomic renames),
   and switches `current` atomically.
4. **Re-pins** with the existing `pin_critical.sh`. The cog1 `verify_release.py --full` must end
   `F8_VERIFY_PASS full f293e72-f9c2-cog1`.
5. **Reverts automatically** if any step after the first change fails.

`install_cog1.sh revert <payload-dir>` has the same preconditions, with `current` = cog1. It:
1. switches `current` back;
2. restores the stub;
3. **moves** `_prod_world_context.py` to `/var/backups/hermes-gateway-dev/cog1-revert-<UTC>/`;
4. re-pins;
5. requires the f9c2 `verify_release.py --full` to pass.

The cog1 release directory is kept.

What it never does:
- start, stop or reload anything;
- change a unit, user, group, sudoers entry, credential, Core API, broker, authority, witness, Privacy or memory
  state;
- delete anything.

The tests check this statically. `rollback.sh` (stop / remove) is unchanged and still covers the whole Hermes
install.

The copied venv still runs f9c2's interpreter and editable Hermes `src` (identical, verified bytes, absolute
paths). `releases/f293e72-f9c2` must stay in place while cog1 is current; it is also the revert target.

## Payload (from Git at the installer's merge commit)

| File in the payload directory | Repository path | SHA-256 |
|---|---|---|
| `world_context.py` | `integrations/hermes/overlays/dev-unified-cognition/lilith_router/world_context.py` | `07a763e1…` |
| `_prod_world_context.py` | `integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py` | `46b8187e…` |
| `world_context.f9c2-stub.py` | `integrations/hermes/home/variants/dev-f9c2/lilith_router/world_context.py` | `5c1fbf98…` |
| `verify_release.cog1.py.tmpl` | `integrations/hermes/release/dev-f9c2-cog1/templates/bin/verify_release.py.tmpl` | `817f7cae…` |
| `verify_release.f9c2.py.tmpl` | `integrations/hermes/release/dev-f9c2/templates/bin/verify_release.py.tmpl` | `865be123…` |
| `RELEASE_ID` | `integrations/hermes/release/dev-f9c2-cog1/RELEASE_ID` | `7c5467d4…` |

None of them is secret. They reach the host through the accepted DEV operator transport, into a root `0700`
directory.

## Gate sequence on DEV (each needs its own approval)

| Gate | Operation | Expected effect | Check |
|---|---|---|---|
| D | stop `hermes-gateway-dev` | console returns 502 until restart; Core API, provider gate, FORGET path units unaffected | `systemctl show` |
| C | `install_cog1.sh install` | `COG1_INSTALLED`; `current` = cog1 | the Gate A read-only plan: release, hashes (adapter `07a763e1…`, PROD `46b8187e…`, gateway `5ce4bbd4…`, adapter.py `8c3b0055…`, router `7bb4fbb5…`), `F8_VERIFY_PASS full f293e72-f9c2-cog1`, every lane `False` |
| D | start `hermes-gateway-dev` | `ExecStartPre` cog1 verifier passes; gateway active; routing unchanged (every lane off) | service state, verifier code, `bin/smoke_console.py` with a TEST_ONLY message (needs its own approval) |

**Rollback triggers:**
- any `COG1_INSTALL_FAIL`;
- the gateway failing its `ExecStartPre`;
- any routing change while lanes are off.

**Rollback:** stop the gateway, `install_cog1.sh revert`, then start the gateway. Canonical memory, Privacy and
authority are never touched.

## Offline evidence

`tests/sim_install_cog1.sh` builds an f9c2-shaped host from this repository. It runs as root in a private mount
namespace with overlays, so the machine keeps nothing. It uses:
- the real `pin_critical.sh`;
- both real verifiers, rendered with a synthetic token;
- a `systemctl` shim.

It checks:
- refusals with no state change;
- auto-revert after an injected failure;
- install with cog1 `verify --full` passing and f9c2 untouched;
- revert to the exact f9c2 state.

`tests/test_cog1_installer.py` checks the installer's pins against the repository, and that the script never
controls services or deletes anything.

## Open follow-ups (not part of this installer)

- **IAP IAM.** IAM bindings attached directly to IAP tunnel resources were not read in the 2026-10-28 exposure
  check. It is also not confirmed whether the default compute service account's `roles/editor` carries
  `iap.tunnelInstances.accessViaIAP` (that account is not attached to the DEV VM). A read-only check of both needs
  its own approval.
- **Firewall scope.** `lilith-api-iap` has no target tag, so it covers every instance in `lilith-vpc`, PROD
  included. Narrowing it affects PROD access and is a Gate I decision.
- **f9c2 runtime test suites.** The f7, f9a and f9b suites need a built Hermes runtime and remain NOT RUN for cog1.
