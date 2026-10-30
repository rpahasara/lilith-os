# `dev-reasoning-hardening` overlay (CANDIDATE, in no release)

A candidate governed adapter: the `dev-goals-hardening` candidate plus one replacement, `hardened_reasoning_intent`. Nothing
assembles, installs or references this directory. r1 on DEV keeps the deployed detector.

## What changes

| Rule | Deployed | Candidate |
|---|---|---|
| Main test | a common word anywhere in the message | a question or request, in one clause, aimed at a named piece of work; or an explicit analytic cue about work |
| Paraphrases | missed | matched by the shape of the clause and its topic, not by a phrase list |
| Bare `not sure`, `unknown`, `assess`, `what next` | match | do not match |
| Other senses of work words | match | removed by an off-topic list (`film`, `shop`, `role of`, `application form`…) |
| Negation before the trigger or topic | ignored | that clause does not count; other clauses still do |
| Quoted text, and reported or transformed speech | matches | removed or refused |
| Plain look-ups (`what time`, `how many`, `show me`) | varies | refused, for the forms listed |
| Explicit knowledge questions | not considered | World Model keeps them |
| Common typos | missed | normalised for the detector only |
| Input scanned | the whole message | the first 2,000 characters |
| Lane priority | draft, goal, pending first | the same checks, unchanged |

**Unchanged:** the result has the same four keys, it is pure, and it makes no read, write or provider call. No message text can leave
it. All four accepted r1 test turns keep their result.

## Measurements

| Corpus | Deployed | Previous candidate | This candidate | Independence |
|---|---|---|---|---|
| Original analytic, matched of 25 | 20 | 21 | **21** | used for tuning |
| Original casual, false of 25 | 18 | 0 | **0** | used for tuning |
| Held-out analytic, matched of 40 | 29 | 39 | **39** | seen before this candidate |
| Held-out false matches, of 75 | 47 | 0 | **0** | seen |
| Red-team analytic, matched of 20 | 1 | 1 | **19** | seen, used for tuning |
| Red-team false, of 25 | 16 | 6 | **0** | seen, used for tuning |
| **Validation analytic, matched of 39** | 2 | not run | **37** | **unseen; scored once** |
| **Validation false, of 26** | 1 | not run | **0** | **unseen; scored once** |
| Plain look-ups about work matched, of 10 | not run | not run | **10** | written after, to attack it |

**Only the validation row is independent of tuning,** and only partly. The pool (`bedfec8`) was committed first, then split by hash, and that half was
never read until its one run. The same author wrote it, and its negatives use everyday topics also covered by the off-topic list, so
treat 0 of 26 as optimistic. It is small: the 95% range on 37 of 39 is roughly 83% to 99%.

## Known failures, not hidden

- **Plain look-ups about work match.** `who is the recruiter?` wants a fact, and the rule can't tell. This is the main cost of the broad rule, and
  it will also inflate Workspace reads. Real records will show how common it is.
- **The off-topic list is a list.** It removes the senses it names and no others.
- **Validation misses:** `can you make sense of this feedback?` and `what's the downside of accepting?`.
- **No work word means no match:** `what are the risks of declining?`, `which option looks strongest to you?`, `what are my choices here?`.
- **Lane priority:** `reply` and `follow up on…` can read as draft requests, so those messages go to the draft path, as designed.
- **Other languages:** not handled.
- The full lists are pinned in the `tests/*_results.json` files.

## What this supports

Good enough to **replace the deployed detector in shadow**, where a false match costs a record and, under Workspace, up to 5 reads. **It does
not support Reasoning Live:** real wording is unmeasured, and a live false match would replace a normal reply.

## To adopt it

1. Add the file to an `OVERLAY.json` entry with its digest, in a new release. It already contains the Goals hardening.
2. Pin the digest in that release's verifier (`WORLD_CONTEXT_ADAPTER_SHA256`).
3. Ship in shadow and compare records against r1.
