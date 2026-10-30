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
| Fact-style openings (`who is`, `did the`, `what's the`) | varies | need a sign of judgement |
| Explicit knowledge questions | not considered | World Model keeps them |
| Common typos | missed | normalised for the detector only |
| Input scanned | the whole message | the first 2,000 characters |
| Lane priority | draft, goal, pending first | the same checks, unchanged |

**Goal policy:** one added rule, `Name a goal by its title. Give its goal id only if you are asked for it.` It answers the G3 finding in text only. Whether a model follows it is unproven live.

**Unchanged:** the result has the same four keys, it is pure, and it makes no read, write or provider call. No message text can leave
it. All four accepted r1 test turns keep their result.

## Measurements

| Corpus | Deployed | First candidate | **This candidate** | Independence |
|---|---|---|---|---|
| Original analytic, matched of 25 | 20 | 21 | **21** | used for tuning |
| Original casual, false of 25 | 18 | 0 | **0** | used for tuning |
| Held-out analytic, matched of 40 | 29 | 39 | **39** | seen |
| Held-out false matches, of 75 | 47 | 0 | **0** | seen |
| Red-team analytic, matched of 20 | 1 | 19 | **19** | seen, used for tuning |
| Red-team false, of 25 | 16 | 0 | **0** | seen, used for tuning |
| Validation 1 analytic, matched of 39 | 2 | 37 | **37** | scored unseen once for the first candidate; now seen |
| Validation 1 false, of 26 | 1 | 0 | **0** | as above |
| Plain look-ups about work matched, of 10 | not run | 10 | **0** | used for tuning |
| Validation 2 analytic, matched of 20 | 0 | not run | **20** | scored unseen once, 20/20; now seen |
| Validation 2 work look-ups, false of 17 | 0 | not run | **0** | scored unseen once, 1/17; that miss was then fixed |
| Validation 2 casual, false of 11 | 0 | not run | **0** | scored unseen once, 0/11; now seen |
| **Validation 3 paraphrases, matched of 13** | 0 | not run | **10** | **unseen; scored once** |
| **Validation 3 false matches, of 14** | 0 | not run | **1** | **unseen; scored once** |
| **Validation 3 negated, false of 5** | 1 | not run | **0** | **unseen; scored once** |
| **Validation 3 other lanes, false of 4** | 0 | not run | **0** | **unseen; scored once** |

**The Validation 3 rows are the only ones independent of the final rule, and only partly.** The pool was committed (`83dd428`) before the final changes, split by hash, and that half was scored once
after the rule was frozen. The same author wrote it, and it is small, so treat the numbers as better than real traffic will be. Its failures are reported and were not tuned away.

## Known failures, not hidden

- **Validation 3 misses:** `is the hiring manager stalling?`, `what's the smart play on this offer?` (the off-topic word `play`), `which of the two offers would you pick?`.
- **Validation 3 false match:** `what's a good job for a rainy day around the house?`.
- **The rule is deliberately conservative:** when unsure it stays quiet. A miss costs a shadow record; a false match costs up to 5 reads.
- **The judgement list is a list.** A work question opening `who`, `where`, `which`, `is`, `are`, `was`, `did`, `does`, `do`, `has`, `have` or `what's the` needs a word from it. Analytic questions using
  none of those words now miss. That trade is deliberate: a false match costs up to 5 reads, a miss costs an absent shadow record.
- **The off-topic list is a list.** It removes the senses it names and no others.
- **Validation 1 misses:** `what's the status of my thinking on this offer, is it good?`, `can you make sense of this feedback?`, `what's the downside of accepting?`, `does it make sense to follow up on application 33?`.
- **No work word means no match:** `what are the risks of declining?`, `which option looks strongest to you?`, `what are my choices here?`.
- **Lane priority:** `reply` and `follow up on...` can read as draft requests, so those messages go to the draft path, as designed. `why is the draft for job 9 on hold?` is the held-out miss.
- **Other languages:** not handled.
- The full lists are pinned in the `tests/*_results.json` files.

## What this supports

Good enough to **replace the deployed detector in shadow**, where a false match costs a record and, under Workspace, up to 5 reads. **It does
not support Reasoning Live:** real wording is unmeasured, and a live false match would replace a normal reply.

## To adopt it

1. Add the file to an `OVERLAY.json` entry with its digest, in a new release. It already contains the Goals hardening.
2. Pin the digest in that release's verifier (`WORLD_CONTEXT_ADAPTER_SHA256`).
3. Ship in shadow and compare records against r1.
