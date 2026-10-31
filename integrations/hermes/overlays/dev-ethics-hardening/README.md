# `dev-ethics-hardening` overlay (CANDIDATE, in no release)

Fixes E-1 to E-5 from `proposals/ethics-shadow-v0.1/DESIGN.md`. **Nothing assembles, installs or references this directory.** Ethics stays off on DEV.

Two files: `lilith_router/world_context.py`, which is the p1 adapter plus the changes below, and `lilith_router/ethics.py`, which is the deployed module with the resolution string changed and the vocabulary scan narrowed.

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
| **The same failure, wider.** The vocabulary check scanned the whole concern, including the words the person typed. `share my private legal records` contains "legal", so the privacy concern was dropped. Reproduced on the unfixed code: all three test messages showed `DROPPED_PRESENT` | **A person's most sensitive data could lose its concern because of what it was called.** PROD has the same scan | the scan skips the quoted data scope only; Ethics' own words are still banned, and a test proves both directions |
| `send my salary to the recruiter` isn't "send an email" | no action, so no privacy or consent concern | a send plus named personal data is a disclosure |
| `lie on my cover letter` names no action or person | `INSUFFICIENT_CONTEXT` | a false claim counts as reaching whoever reads it; the third party is recorded as an unresolved `employer` |
| `should I lie on my cv?` never reached the lane | missed | a conduct question on named work now matches, under the same yields |
| Someone else's data, such as `my coworker's medical history` | the patterns only knew the person's own | a disclosure needs all three: another person's data, a disclosing verb, and an outside recipient. That keeps `share my screen` casual |
| `say I was laid off when I was fired`, `take credit for`, `make up a reason` | no conduct word | named false-statement shapes, still needing work as the subject |

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

## Second corpus: disclosure and false statements

`tests/ethics_corpus_v2.py` was committed (`2312505`) before these rules, split by a different hash. Only the tuning half was looked at while writing them. The unseen half was scored once, then pinned in `tests/ethics_results_v2.json`, and its misses were **not** fixed.

| Unseen half | Candidate |
|---|---|
| Should be Ethics, of 14 | **11** |
| Casual, quoted or off-topic falsely matched, of 12 | **0** |
| Reasoning questions taken, of 3 | **0** |
| Expected concern raised, of 7 | **5** |

**Known misses:** `can I sign the reference letter myself?`, `is it ok to say I managed a team when I didn't?` and `should I claim I have a competing offer to get more money?`. The last two show the limit of the subject rule: a false claim with no named job word doesn't reach the lane.

**One known overlap, from the tuning half:** `should I tell the recruiter I accept the offer?` goes to Ethics rather than Reasoning. PROD's soft path sees an outward contact, and any rule separating it from `should I tell my manager I am interviewing elsewhere?` would be guessing. It's pinned, and costs a misplaced shadow record.

**On purpose:** a bare `is this ethical?` no longer matches. The lane can't see the previous turn, so it has nothing to weigh.

## Third corpus: false claims, negation and adversarial wording

`tests/ethics_corpus_v3.py` was committed (`873280f`) before these rules, split by a third hash. The rule: a first-person claim about a credential, contradicted in the sentence or by its shape, reaches the lane without a job word, and a question about someone else's conduct doesn't.

| Unseen half, first and only score | Candidate |
|---|---|
| Should be Ethics, of 7 | **5** |
| Casual, negated, quoted or adversarial falsely matched, of 10 | **2** |

That score is frozen in `tests/ethics_results_v3_first_score.json`. **The two false matches were then fixed:** `I would never lie on my cv` and `they asked: is it ok to say I managed a team when I didn't?`. The fix has regression tests but **no unseen score**, so don't read `ethics_results_v3.json` as an estimate. Misses stay pinned: `is it ok to say I was sick when I wasn't?` and `can I write my own reference and sign it as my manager?`.

**The second corpus is no longer unseen for these rules.** Its first score is frozen in `tests/ethics_results_v2_first_score.json`. The three misses it named led to this rule, so its current 14/14 and 7/7 are not evidence of quality.

**Three corpora are enough here.** A miss costs a shadow record, and more of one author's sentences won't say anything about real wording: only real traffic will.

## Limits

- **Deterministic rules only.** The model path stays unwired.
- **`email the recruiter's boss` gives `SKIPPED_KNOWN_PROHIBITION`,** by the existing short-circuit: the lane skips rather than weighs it.
- **Reasoning yields whenever the Ethics detector matches,** so this adapter must ship with Ethics on. A release needs a verifier rule pairing them.
- **Both fixes would change PROD's advice if promoted:** concerns that never appeared there will start to. Part of the A4 lane-mode decision.

## Before a release

| Item | State |
|---|---|
| p1 accepted on DEV | installed; see the p1 acceptance record |
| Router, verifier pins, installer, simulation | not built; built in a separate release PR |
| Live mode, and the model path | out of scope |

**Evidence:** `tests/test_ethics_hardening.py`, 25/25, on the real gateway, adapter and Core API with the p1 router plus Ethics in shadow, including adversarial messages and a populated store.
