# `dev-reasoning-hardening` overlay (CANDIDATE, in no release)

A candidate governed adapter: the `dev-goals-hardening` candidate plus one replacement, `hardened_reasoning_intent`. Nothing
assembles, installs or references this directory. r1 on DEV keeps the deployed detector.

## What changes

| Rule | Deployed | Candidate |
|---|---|---|
| Evidence needed | a common word anywhere in the message | an explicit analytic request about work, in one clause |
| Trigger followed by a topic | matches | the topic must name work, or end on `this`, `that` or `it` |
| Bare `not sure`, `unknown`, `uncertain`, `assess`, `what next` | match | do not match |
| Negation before a trigger | ignored | that clause does not count; other clauses still do |
| Quoted text, and reported or transformed speech | matches | removed or refused |
| Input scanned | the whole message | the first 2,000 characters |
| Lane priority | draft, goal, pending first | the same checks, unchanged |

**Unchanged:** the result has the same four keys, it is pure, and it makes no read, write or provider call. No message text can leave
it. All four accepted r1 test turns keep their result.

## Measurements

**The first two corpora were written by the same author as the detector, so they flatter it.** The candidate was built after the
held-out corpus was committed (`4ece7cb`), but knowing what was in it. The red-team corpus was then written to break it.

| Corpus | Deployed | Candidate v1 | Candidate (final) |
|---|---|---|---|
| Original analytic, matched of 25 | 20 | 23 | **21** |
| Original casual, false of 25 | 18 | 0 | **0** |
| Held-out analytic, matched of 40 | 29 | 39 | **39** |
| Held-out casual, false of 45 | 27 | 0 | **0** |
| Held-out negated, false of 15 | 8 | 0 | **0** |
| Held-out multi-intent, matched of 8 | 8 | 8 | **8** |
| Held-out lane yields, wrong of 10 | 0 | 0 | **0** |
| Held-out adversarial, false of 15 | 12 | 0 | **0** |
| **Red-team must-match, matched of 20** | 1 | **1** | **1** |
| **Red-team must-not-match, false of 25** | 16 | **20** | **6** |

Candidate v1 was **worse than deployed** on red-team false matches. It failed because triggers such as `pros and cons` needed no work
context. The final candidate fixed that rule, using what the red-team corpus showed, so **its 6 of 25 is no longer a held-out
number.** v1's 20 of 25 is the honest held-out result for that class of attack.

## Known failures, not hidden

- **Paraphrases are missed.** 19 of 20 red-team requests fail, including `thoughts on the offer?`, `why did they reject me?`, `what went
  wrong on application 3?`, typos and shorthand. The deployed detector misses the same set. A rule list can't reach these.
- **Work words in other senses still match:** `the role of bees`, `application form at the DMV`, `offer in the shop`.
- **Four original analytic requests are missed** by the tightening: `which option looks strongest to you?`, `what are the risks of
  declining?`, `what would settle this question?`, and the `reply` case, which the draft path takes first.
- **Lane priority causes one held-out miss:** `why is the draft for job 9 on hold?` goes to the draft path, as designed.
- The full lists are pinned in [`tests/holdout_results.json`](tests/holdout_results.json) and [`tests/redteam_results.json`](tests/redteam_results.json).

## What this supports

**The candidate trades recall for precision, which is the right way round for shadow.** A miss costs nothing there. A false match costs
a record, and up to 5 Core API reads under Workspace.

**It does not support Reasoning Live.** Missing most paraphrases means a live lane would rarely fire on natural wording. Live needs
measurement on real shadow records, and probably a classifier that isn't a rule list.

## To adopt it

1. Add the file to an `OVERLAY.json` entry with its digest, in a new release. It already contains the Goals hardening.
2. Pin the digest in that release's verifier (`WORLD_CONTEXT_ADAPTER_SHA256`).
3. Ship in shadow and compare records against r1.
