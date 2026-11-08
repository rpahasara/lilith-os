# 10. Registered experiments

Common method (from the measured Social Cognition A/B, work note §3a):
- offline replay on the host, using the same prompt builder as PROD;
- synthetic or owner-approved scenarios only, with no private transcript text in reports;
- **blind pairwise** owner rating, with keys held separately;
- ≥2 samples per arm;
- token and latency recorded per arm;
- runs capped at ~50K Groq tokens/day;
- results recorded as MEASURED in the work note.

Each experiment declares its kill criterion before running (AP-32 preregistration; SM-46).

**Scenario counts below are cumulative targets** (owner clarification 2026-11-08).
- Each experiment begins with a focused set of about 5–10 scenarios.
- It expands toward the stated count only when evidence warrants.
- Pass and kill criteria apply at whatever size the decision is made, reported with denominators.

| ID | Question | Arms | Primary metric | Secondary metrics | Pass (promote) | Kill | Phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **E-1** | Does the tone note help? | shadow vs live note | blind preference | over-inference count | — | — | **DONE** (MEASURED, §3a: helps on mixed / tease / no-sleep; neutral elsewhere; technical fixed by #346) |
| **E-2** | Do approved preferences improve appropriateness without over-generalizing? | no preferences vs ≤3 approved preferences | blind preference on 20 preference-relevant scenarios | over-generalization on 20 *irrelevant* scenarios; tokens | preference ↑ (≥60% pairwise wins) and over-generalization not worse than baseline | over-generalization ↑, or no preference gain | P-2 |
| **E-3** | Does a structured interpretation fix ambiguous turns better than better context? | (1) current, (2) better context with no call, (3) small-model interpretation, (4) reply-model interpretation | blind preference on 25 ambiguous scenarios (masking, sarcasm, brush-off, mixed, correction) | interpretation accuracy against owner labels; tokens per gated turn; latency | arm 3 or 4 beats arm 2 by ≥15 points of pairwise win rate, within the token budget and +1.5 s p95 | arm 2 ≥ arms 3/4, or budget exceeded | P-5b |
| **E-4** | Does deterministic appraisal change replies in a way the owner prefers? | appraisal signals off vs on (same model) | blind preference on 20 goal-relevant scenarios (setback, progress, deadline) | forced-cheer and ignored-setback counts | ≥60% wins, no increase in over-inference | no difference | P-3 |
| **E-5** | Do L16 gates reduce confident errors? | gates off vs on | rate of hallucinated personal facts on 30 recall-gap scenarios | ask-annoyance rating; latency; contradiction-acknowledged rate | errors ↓ ≥50%, annoyance ≤2/5 | no error drop | P-3 |
| **E-6** | Does correction learning stop repeats? | correction logged only vs proposed preference applied | recurrence of the corrected behaviour across 10 correction pairs (correct, then a later trigger) | "listened to me" rating; false generalization | recurrence ↓ ≥70% | no drop, or false generalization ↑ | P-2 |
| **E-7** | Are commitments honoured? | no commitment store vs store + due-check | promised follow-ups honoured or acknowledged within the window (owner log, 2 weeks) | missed and duplicate reminders | ≥90% honoured, 0 duplicates | <70% | P-4 |
| **E-8** | Does episodic recall work without fabricating? | transcript-only vs episode records | correct answers on 30 "when / what happened" questions | fabrication rate (ML-14) | accuracy ↑, fabrication ≤ baseline | fabrication ↑ | P-4 |
| **E-9** | Is bounded initiative welcome? | live, owner-only, capped | owner veto ("not now" / stop) rate | usefulness 1–5; ignored rate | veto <20%, usefulness ≥4 | veto >40% for 1 week | P-5 |
| **E-10** | Is LILITH the same across models? | Groq Qwen vs gpt-5.6-sol vs Copilot gpt-4.1 (and any future default) | blind "this is LILITH" rating on 20 identity prompts | canonical recall correctness; values consistency | ≥4/5 on each live model; recall 100% on canonical items | <3/5 on any model ⇒ restrict that model's use | P-0, then every model change |

**Reporting rule** (AP-34, SM-43).
- Report denominators, disagreements and failures, not only wins.
- A negative result is recorded in the [negative results register](../negative-results-register.md).
- Research success never activates a mechanism by itself (AP-40). Promotion is an owner decision.
