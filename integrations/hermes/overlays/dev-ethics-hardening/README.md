# `dev-ethics-hardening` overlay (CANDIDATE, in no release)

Fixes E-1 to E-5 from `proposals/ethics-shadow-v0.1/DESIGN.md`. **Nothing assembles, installs or references this directory.** Ethics stays off on DEV.

Two files: `lilith_router/world_context.py`, which is the p1 adapter plus the changes below, and `lilith_router/ethics.py`, which is the deployed module with one string changed.

## Blockers

| # | Before | After | Where |
|---|---|---|---|
| E-1 Over-match | any "is it ok to" | also needs named work, a third party or personal data; quoted, reported and off-topic messages are refused | adapter |
| E-2 Weak detection | concerns dropped or never raised | see below | both |
| E-3 Overlap | risk questions ran both lanes | risk questions without the word "ethical" stay with Reasoning; conduct questions stay with Ethics, and Reasoning yields | adapter |
| E-4 Reads | 10 on a matching turn | **5 or 6**: each route once | adapter (p1 memo) |
| E-5 Identifiers | `intent.app_id` | null, on every lane | adapter (p1) |

## E-2: what was actually wrong

| Cause | Effect | Fix |
|---|---|---|
| **A real bug.** The `THIRD_PARTY_IMPACT` resolution text said "authorises", which is on the lane's own banned-word list | **That concern could never survive validation.** PROD has run this code live since 2026-09-09 | one string in `ethics.py` |
| `send my salary to the recruiter` isn't "send an email" | no action, so no privacy or consent concern | a send plus named personal data is a disclosure |
| `lie on my cover letter` names no action or person | `INSUFFICIENT_CONTEXT` | a false claim counts as reaching whoever reads it; the third party is recorded as an unresolved `employer` |
| `should I lie on my cv?` never reached the lane | missed | a conduct question on named work now matches, under the same yields |

**The four principles are unchanged.** There is no deception principle, and this doesn't add one: lying is recorded as impact on another party, under Non-maleficence. That is the honest limit of the fixed set.

## Corpus

`tests/ethics_corpus.py` was committed (`d1e78b6`) before any rule, and split by hash. The unseen half was scored once, after the rule was frozen. Its misses were **not** then fixed. One evidence word was added after that score. It can't change detection, and the concern result was already 4/4. Same author and small, so treat these as better than real traffic will be.

| Unseen half | Candidate |
|---|---|
| Should be Ethics, of 13 | **10** |
| Casual, quoted or off-topic falsely matched, of 14 | **0** |
| Reasoning questions taken, of 4 | **0** |
| Concern raised, of 4 | **4** |

**Known misses, pinned in `tests/ethics_results.json`:** `is it ethical to apply for a job I plan to leave in three months?`, `are there ethical concerns with emailing the whole team about my application?`, and `is it okay to use a friend's reference without telling them?`. A miss costs a shadow record.

**On purpose:** a bare `is this ethical?` no longer matches. The lane can't see the previous turn, so it has nothing to weigh.

## Limits

- **Deterministic rules only.** The model path stays unwired.
- **`email the recruiter's boss` gives `SKIPPED_KNOWN_PROHIBITION`,** by the existing short-circuit: the lane skips rather than weighs it.
- **Reasoning yields whenever the Ethics detector matches,** so this adapter must ship with Ethics on. A release needs a verifier rule pairing them.
- **The `THIRD_PARTY_IMPACT` fix would change PROD's advice if promoted:** concerns that never appeared there will start to. Part of the A4 lane-mode decision.

## Before a release

| Item | State |
|---|---|
| p1 accepted on DEV | not yet |
| Router, verifier pins, installer, simulation | not built; see `proposals/ethics-shadow-v0.1/RELEASE-DESIGN.md` |
| Live mode, and the model path | out of scope |

**Evidence:** `tests/test_ethics_hardening.py`, 15/15, on the real gateway, adapter and Core API with the p1 router plus Ethics in shadow, including adversarial messages and a populated store.
