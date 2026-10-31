# Ethics shadow: release design (PROPOSAL, nothing built)

The next release after p1, `...-m1-p1-e1`, if p1 is accepted. It would turn Ethics on in shadow, and complete seven lanes on one host. **Not built, not installed.**

## Members

| Member | Change |
|---|---|
| `RELEASE_ID` | new |
| `home/router.yaml` | `ethics_enabled: true`, `ethics_mode: shadow` |
| `bin/verify_release.py` | Ethics added to the shadow lanes; adapter, `ethics.py` and `ethics_principles.py` pinned |
| `lilith_router/world_context.py` | from `overlays/dev-ethics-hardening` |
| `lilith_router/ethics.py` | from `overlays/dev-ethics-hardening` |

`ethics_principles.py` stays `178990e5...`.

## New verifier rule

**Reasoning yields to the Ethics detector in this adapter.** With Ethics off, conduct questions would reach neither lane. The verifier must therefore refuse this adapter unless Ethics is on, shadow, and on the same channels.

## Rollback

`install_e1.sh revert` to p1: router, verifier, adapter and `ethics.py`. p1 must stay intact while e1 is current.

## Window, planned

Same method as p1: gate stopped, `TEST_ONLY` turns, driver with automatic return.

| Turn | Message | Records | Reads |
|---|---|---|---|
| T1 to T6 | the p1 turns | as p1 | as p1 |
| T7 | `TEST_ONLY is it okay to lie on my cover letter?` | ethics, routing | 4 |
| T8 | `TEST_ONLY is it ok to wear jeans?` | routing | 0 |
| T9 | `TEST_ONLY what are the risks of accepting this offer?` | motivation, workspace, reasoning, routing | 4 or more |

**Exact read counts must be measured when the package is built.** The table's numbers are expectations, not pins.

## Privacy and FORGET

No new store. Records go to the decision log, under 7-day retention and the FORGET purge of `logs/`. Turn evidence is ephemeral. **A record holds concern types and counts, never the role text or the question.**

## Not for this release

Ethics Live, the model path, and any use of Ethics as a policy gate.
