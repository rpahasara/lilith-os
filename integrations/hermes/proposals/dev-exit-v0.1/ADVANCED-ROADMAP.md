# After migration: advanced development roadmap (PROPOSAL)

**The aim:** one persistent companion identity that remembers what's relevant, reasons, plans and helps on her own within authorized boundaries. **None of this is a prerequisite for DEV exit.** It starts after rollout stage 8, DEV-first, with each step under the same rule: shadow, then bounded live, then owner acceptance.

## Order, by what each depends on

| Horizon | Capability | First step | Depends on | Done means |
|---|---|---|---|---|
| **1. Measure** | **Continuous evaluation and rollback** | Replayable synthetic turn sets, per-lane scores, automatic comparison to the last release | Rollout done | A lane change can't merge without a before-and-after number |
| | Context-aware conversation, personality consistency | Turn the identity prompts into a recurring check | Evaluation | Drift is measured, not noticed |
| | Provider flexibility without changing identity | Fixed identity prompts across providers; persona lives outside the provider | Evaluation | A provider swap passes the identity check |
| **2. Know** | World Model updates, uncertainty | Conversation proposes beliefs, with confidence and source; conflicts surface instead of overwriting | Evaluation, FORGET | Every belief has a source and can be erased |
| | Long-term memory consolidation | Move L18 from shadow candidates to owner-reviewed admission | L04 authority, A12 | Nothing enters canonical memory unreviewed |
| **3. Think** | Grounded multi-step reasoning | Model path behind Reasoning; every claim cites a belief | World Model | Unsupported claims are measured and fall |
| | Goal-directed planning | Plans from real goals with ordering and dependencies; proposal only | Goals creation, reasoning | The owner accepts or edits plans, and that's scored |
| **4. Continue** | Cross-session task continuity | Tasks resume with their context | Durable task store, memory | "Where were we?" works across days |
| | Safe background resumption | Timed resumption of read-only work, bounded budget, kill switch | Approval gate, evaluation | Stopped by one flag; no write without approval |
| **5. Act** | Approval-gated tool use, automation | One read-only tool, then one reversible write, through the policy engine | Everything above | Every action has a capability, a class and an audit line |

## Rules that don't relax

- **Identity stays one:** no per-provider persona, no reset.
- **Autonomy grows by capability, one at a time,** each with its own approval and rollback.
- **Anything remembered must be erasable,** and new stores join FORGET before they hold real data.
- **Multi-intent handling comes before any lane goes live on a message class:** today the first intent wins, and the second goes unanswered.
- **Real traffic is the only way to tune detectors.** Offline corpora have one author.

## Research priorities

| Priority | Question | Measure | Blocked until |
|---|---|---|---|
| 1. Grounded reasoning | Does each claim trace to a belief? | unsupported claims per reply | a model window |
| 2. World Model updates | How do beliefs change without overwriting truth? | conflicts surfaced, stale beliefs | FORGET covers conversation-derived beliefs |
| 3. Cross-session continuity | Can work resume days later? | correct resumes | task store on real data |
| 4. Goal-driven planning | Does a plan follow real goals? | owner accepts or edits | goal creation has FORGET coverage |
| 5. Multi-step cognition | Can lanes chain within one turn, with two intents? | second intent answered | precedence redesign |
| 6. Memory consolidation | What deserves keeping? | owner acceptance rate | L04 authority on PROD |
| 7. Safe action execution | One reversible action end to end | every action audited, none unapproved | policy engine on PROD |
| 8. Autonomous assistance | Bounded background work behind explicit permission | kill switch proven, budget held | 1 to 7 |

**None of this replaces a production blocker.**

## What to resist

Adding lanes before evaluation exists. Without a number, each new lane is a new way to get worse unnoticed, which is what happened with PROD's detectors.
