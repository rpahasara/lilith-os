# Ethics shadow: release design (CANDIDATE BUILT, NOT APPROVED, NOT INSTALLED)

The next release after p1, `f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1`. It would turn Ethics on in shadow and make seven lanes on one host. **It is based on the p1 bytes now running on DEV, and p1 is owner-accepted within its shadow-only scope. Nothing here installs it.** The sealed package is built, and installing it needs its own owner approval.

The candidate lives in `release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1/`. `gen_e1_release.py` builds it from p1, so every difference from p1 is a rule in that script.

## Members

| Member | Change | Digest |
|---|---|---|
| `RELEASE_ID` | new | `fb9a650f...` |
| `home/router.yaml` | `ethics_enabled: true`, `ethics_mode: shadow`, nothing else | `be8c08d1...` |
| `bin/verify_release.py` | Ethics added to the shadow lanes; adapter, `ethics.py` and `ethics_principles.py` pinned | template `f1086cac...` |
| `lilith_router/world_context.py` | from `overlays/dev-ethics-hardening` | `f1ee561d...` |
| `lilith_router/ethics.py` | from `overlays/dev-ethics-hardening` | `d6a1c20b...` |

`ethics_principles.py` stays `178990e5...`. DEV's installed `ethics.py` is `b6e3ce49...`, confirmed read-only on 2026-10-31, so the install base is what the installer pins.

## Pairing rule

**Reasoning yields to the Ethics detector in this adapter,** so with Ethics off, conduct questions would reach neither lane. The pairing needs no new code: one verifier pins this adapter and also requires Ethics in shadow on the same channels. p1's verifier refuses this adapter, and the e1 verifier refuses Ethics off. `test_e1_release.py` proves the pins and `sim_install_e1.sh` proves the refusal on a real verifier.

## Rollback

`install_e1.sh revert` returns to p1: router, verifier, adapter and `ethics.py`. p1 must stay intact while e1 is current.

## Window, planned

Same method as p1: gate stopped, `TEST_ONLY` turns, driver with automatic return. Read counts below were measured offline on the real gateway, adapter and Core API, on an empty store. They become pins when the package is built.

| Turn | Message | Records, in order | Reads |
|---|---|---|---|
| T1 to T6 | the p1 turns | as p1 | 5, 5, 0, 0, 6, 0 |
| T7 | `TEST_ONLY is it okay to lie on my cover letter?` | ethics `THIRD_PARTY_IMPACT`, routing | 5 |
| T8 | `TEST_ONLY is it ok to wear jeans?` | routing | 0 |
| T9 | `TEST_ONLY what are the risks of accepting this offer?` | motivation, workspace, reasoning `OPTION_GENERATION`, routing | 5 |
| T10 | `TEST_ONLY should we share my private legal records with the recruiter?` | ethics `PRIVACY_EXPOSURE` and `THIRD_PARTY_IMPACT`, cognitive, routing | 6 |

T10 is the live proof of the vocabulary fix: on the unfixed code, its privacy concern is dropped.

## Privacy and FORGET

No new store. Records go to the decision log, under 7-day retention and the FORGET purge of `logs/`. Turn evidence is ephemeral. **A record holds concern types and counts, never the role text, the quoted data or the question.**

## Evidence

| Check | Result |
|---|---|
| `test_ethics_hardening.py` | 25/25 |
| `test_e1_release.py` | 7/7 |
| `test_e1_verifier.py`, refusals on real assembled homes | 13/13 |
| `test_cross_lane.py`, seven lanes on the pinned bytes | 24/24 |
| `package/test_drive_e1.py` | 24/24 |
| `sim_install_e1.sh`, real installers, m1 to p1 to e1 and back to m1 | 36/36 |
| Window simulation, real scripts on a fake host | 47/47 |
| Real read-only P0 on DEV | `P0_E1 PASS` |
| Corpus v1, first unseen score | 10/13, 0/14 false, 0/4 from Reasoning, 4/4 concerns |
| Corpus v2, first unseen score | 11/14, 0/12 false, 0/3 from Reasoning, 5/7 concerns |
| Corpus v3, first unseen score | 5/7, 2/10 false; both false matches then fixed, so no unseen score covers that fix |

**Not proven:** e1 hasn't run on any host. The corpora have one author and are small. The window would keep stores empty, so it tests plumbing, not whether a concern is useful.

## Before approval

| Item | State |
|---|---|
| Owner accepts p1 on DEV | done, [#307](https://github.com/rpahasara/lilith-os/pull/307) |
| Sealed package and driver from `package/gen_e1pkg.py`, with fresh pins | done |
| Offline window simulation | done |
| This release merged, and its files equal to the bundle pins | **open** |
| Owner approves one run of the sealed manifest | **open** |

## Not for this release

Ethics Live, the model path, and any use of Ethics as a policy gate.
