# LILITH OS — PROD integration work note (2026-11-07)

> **Scope:** Continuation from [Source consolidation, October 2026](source-consolidation-2026-10.md), through the 2026-11-06/07 PROD canonical-memory, deployer, learning and Social Cognition work.
>
> **Evidence discipline:** `SOURCE-VERIFIED` = PR/code on GitHub; `OPERATOR-REPORTED` = Claude's live-host run reports and owner's Telegram tests, not independently re-run by this document; `PENDING` = not confirmed complete. This note is a **handoff/work log**, not a replacement for acceptance records, audits or live probes.
>
> **Source baseline:** `main` at `6cfc3be1d4ba70e6801735a30d03dde0268d3ce9` (PR #349 merge; previously `27253c8`, PR #346). Keep this note updated after later merges.
>
> **Public-safe:** This repository was publicly accessible at the time of writing. This document deliberately excludes private memory text, identities/IDs, credentials, secrets, custody values, internal access endpoints and detailed snapshot locations.

## 1. Executive status

- **DEV → PROD source reconciliation:** `OPERATOR-REPORTED` 2026-11-06 live, file-by-file inventory found no outstanding DEV cognition source worth copying. PROD's seven cognitive lanes were already live and newer where they differed from DEV. **Do not redeploy older DEV variants over PROD.** The detailed local inventory was outside Git at the time of this note; obtain a fresh inventory before making claims about future drift.
- **Owner canonical memory:** `OPERATOR-REPORTED` two owner memories were admitted in the isolated PROD store (a project codename and a relationship-origin statement), recalled through the private Telegram owner DM, and preserved across boot/recovery. No private text is reproduced here.
- **Privacy and recovery:** `OPERATOR-REPORTED` initial hold RELEASED, Privacy READY, service auto-start and auto-unlock working after the marker-permission repair. Host-bound credentials require re-sealing during a VM move; do not assume a restored credential decrypts on a different host.
- **Routine PROD deploys:** `OPERATOR-REPORTED` constrained GitHub Actions deployment path works for Core API, router, Hermes gateway and later narrowly-scoped components, with backup/health checks/rollback. No unrestricted deployer root login.
- **Learning:** `SOURCE-VERIFIED` World Model owner-memory API, LILITH OS-first approved writes, Hermes compatibility projection, L18 owner-learning events. `OPERATOR-REPORTED` fresh-session owner Telegram learning tests passed, including exact-once durable records.
- **Social Cognition:** `SOURCE-VERIFIED` deterministic cue detection and live, optional tone guidance on owner channels (PRs #342/#344). Shared/public channels remain in shadow. `OPERATOR-REPORTED` one two-turn Telegram test showed suitable humor-with-frustration response followed by focused technical advice. A small blind offline A/B then found the playful line caused most misfires; line selection was made context-aware in #346 (see §3a). **Causal benefit is still only partially measured** (8 of 12 scenarios).
- **What is NOT complete:** L18 *active consolidation* is still shadow/partial; full contextual social reasoning and event-appraisal/functional affect are research targets, not shipped features. Full runtime replacement and restored-VM continuity remain unproven.

## 2. Git change ledger — merged work since the canonical PROD cutover

All rows below are `SOURCE-VERIFIED` merged PRs. Individual PROD outcomes are from operator reports, not inferred from merge alone.

| PR | Change | PROD/test result reported |
| --- | --- | --- |
| [#329](https://github.com/rpahasara/lilith-os/pull/329) | OWNER_PROD PR-1 eligibility tool | Prepared truthful PROD readiness/hold release; later operator run reported READY |
| [#330](https://github.com/rpahasara/lilith-os/pull/330) | Canonical context restricted to owner channels | Owner Telegram/console recall; no canonical-memory disclosure to public |
| [#331](https://github.com/rpahasara/lilith-os/pull/331) | Auto-recovery on boot and until-revoked owner grant | Boot services and Privacy auto-unlock installed |
| [#332](https://github.com/rpahasara/lilith-os/pull/332) | Correct post-reboot Privacy marker permissions | Recall repaired; no repeat reboot needed for repair test |
| [#333](https://github.com/rpahasara/lilith-os/pull/333) | Constrained PROD deploy helper/workflow | Two NOCHANGE workflow deploys; no service restart |
| [#334](https://github.com/rpahasara/lilith-os/pull/334) | Hermes owner-memory isolation and scheduled learning proposals | Nightly owner review, approval configuration, gateway deploy support |
| [#335](https://github.com/rpahasara/lilith-os/pull/335) | Deny non-owner `session_search` and `memory` tools | Initial isolation test uncovered a separate file-tool route |
| [#337](https://github.com/rpahasara/lilith-os/pull/337) | Restrict non-owner agent to conversation-tool allow-list | Fresh private-history marker test passed on Discord and Telegram |
| [#336](https://github.com/rpahasara/lilith-os/pull/336) | Track rejected proposals in nightly review | Duplicate rejected proposals suppressed; subsequently improved by L18 integration |
| [#338](https://github.com/rpahasara/lilith-os/pull/338) | Route durable facts/preferences off tool-less lean path | In-chat proposal available while ordinary banter stays fast |
| [#339](https://github.com/rpahasara/lilith-os/pull/339) | Owner-approved records in World Model, initial Hermes sync | Existing records imported with honest provenance; API-only recovery tested |
| [#340](https://github.com/rpahasara/lilith-os/pull/340) | Approval writes LILITH OS first; Hermes files are projections | Owner Telegram approval and fresh-session recall verified; failure preserves pending |
| [#341](https://github.com/rpahasara/lilith-os/pull/341) | L18 learning-event ledger | Proposed/approved/rejected/imported/superseded/retracted events; 12 historical events reported after backfill |
| [#342](https://github.com/rpahasara/lilith-os/pull/342) | Expand Social Cognition everyday cue detectors | 13/150 relevant messages detected vs 0/150 previously (operator measurement), still shadow at that step |
| [#343](https://github.com/rpahasara/lilith-os/pull/343) | Fix deployment mirror tests for generated Python caches | Router pipeline redeploy passed |
| [#344](https://github.com/rpahasara/lilith-os/pull/344) | Live owner-only Social Cognition tone note, lean + full-agent | Deployed, healthy, one natural two-turn owner DM smoke test reported successful |
| [#346](https://github.com/rpahasara/lilith-os/pull/346) | Context-aware tone-note line selection (playful gate); `git`/`force push` technical terms | Router deploy OK (3 files, backup taken); deployed selection self-check and gateway health reported OK |
| [#349](https://github.com/rpahasara/lilith-os/pull/349) | Full-agent provider fallback (Copilot Free `gpt-4.1`) via Hermes' native chain; cached agents get the router chain | Router + hermes-gateway deploys OK (backups taken); host e2e fallback for 429/401/503 with the tool run exactly once |

**Pre-PR context:** Gate 6.3b/6.4 reported initial hold released, isolated canonical store established, anchor/checkpoint/unlock ready. Gate 7.1 admitted the first PROD canonical memory; Gate 7.2/7.2r connected owner Telegram/console recall; post-boot test found and repaired the Privacy marker permissions. These gate procedures and their local evidence remain in owner-operated work folders, not reproduced here.

## 3. Useful end-to-end tests already performed (do not endlessly repeat)

1. **Canonical recall:** two separately admitted memories retrieved in owner Telegram DM; private/non-owner routing tested.
2. **Owner natural learning:** conversational facts/preferences proposed; user approved or rejected with Telegram commands; subsequent `/new` sessions recalled approved preferences. Rejection did not make a rejected fact durable.
3. **World Model first-writer:** `OPERATOR-REPORTED` one approved memory persisted to LILITH OS shortly before the Hermes projection. No tool-based history lookup was used for that fresh-session answer.
4. **Privacy test:** a private Telegram-only test marker initially leaked to Discord through `search_files` (not `session_search`); #337 restricted non-owner tools; a **new** marker then remained unavailable in Discord while owner Telegram still retrieved it. Do not repeat the marker strings here.
5. **Social tone smoke:** user joking about a laptop setback → conversational acknowledgment; next technical Git question → actionable technical advice without intrusive mood scripting. This is usability evidence, **not** a measured A/B benefit.
6. **Boot/recovery and deployment:** service recovery, Privacy repair, constrained NOCHANGE deploys and subsequent standard pipeline deployments reported healthy.

## 3a. Social Cognition defect and fix (2026-11-07)

**Observed issue** (`OPERATOR-REPORTED`, router decision logs, no message text): in the owner's two-turn Telegram test the second message — a casual Git how-to with laughter and an emoji — received the *playful* tone note. The classifier had no `git` term (`tech=0`), so the turn was treated as social and the technical-focus rule never applied. The reply was still good, but the note was not helping.

**Offline blind A/B** (`OPERATOR-REPORTED`): the lean Groq reply was replayed on the host exactly as the router builds it (same SOUL core, social policy and model; no owner profile; synthetic conversations; nothing written), with vs. without the note, two samples each, judged before un-blinding.

| Result | Scenarios |
| --- | --- |
| Note helped | Joking about a laptop freeze (laughed *and* cared); teasing banter (cheekier) |
| No difference | Sarcastic rejection (the detector misread it as playful; the model handled it anyway); a date correction |
| Note slightly hurt | Casual Git question (worst reply was a long assistant-style list); tired; a joke about force-pushing to main on Friday (the "play along" line softened her disagreement in one sample) |
| Not measured | Laughing about no sleep; laughing off a repeated rejection; affectionate greeting; cheer-me-up request (provider quota; measured after the fix, below) |

Conclusions: the model already reads social context well from the conversation; almost every misfire was the *playful* line firing on any laugh token; an extra social-reasoning inference call is **not** justified by this evidence.

**Fix** (`SOURCE-VERIFIED` #346; same owner-approved wording, no new wording, no extra inference call, lane, store or learning subsystem):
- Mood lines are dropped when the message names a technical subject or asks for help (help-request phrasing). Routing is unchanged except two narrow classifier terms: `git` (not "you git") and `force push`.
- Sarcasm markers select the approved *mixed* line (joking about something annoying). The difficulty detector also recognises sleeplessness and being rejected (not "I rejected the offer").
- A laugh that brushes off something hard from the user's previous turn gets no playful nudge. An earlier difficult subject alone never decides it; the current message must itself brush it off.
- Explicit intent (correction, comfort, humour, formality) stays authoritative.

**Tests:** 10 new context-gate tests; deploy/prod suite 70/70; historical classifier cases 18/18. **Deploy:** router via the standard pipeline at `27253c8`, smoke check OK, backup taken; an on-host self-check of the deployed code (no model call) reported the expected selections; gateway active, no new errors. **Rollback:** redeploy the previous router mirror, or set `social_cognition_mode: shadow` to stop all tone notes.

**Follow-up blind A/B, 2026-11-08** (`OPERATOR-REPORTED`; same method, with the note chosen by the deployed context-aware code; 12 calls, ~33K tokens, 40 s between calls):

| Scenario | Deployed selection | Result |
| --- | --- | --- |
| Laughing about no sleep | *mixed* | **Note helped**: both replies laughed with the user and told them to rest; without the note, one reply was harsh ("stop lying to me") and one was flippant |
| Laughing off a repeated rejection | none | Same prompt as baseline after the fix (no playful nudge) |
| Affectionate greeting | *playful* | No clear difference: one warm and one extra-cheeky reply with the note, one warm and one flat without it |
| Cheer-me-up request | *support* | No clear difference: good replies both ways; one reply with the note ran long |

No code change is needed. All 14 scenarios have now been measured.

**Remaining limitations:**
- Evaluation quota: the fast-path model has a rolling **200K tokens/day** limit. On 2026-11-07 the evaluation (~90K tokens) plus normal chat used it up, pushing live chat onto the full-agent fallback for a while. Future evaluations should use at most ~50K tokens/day.
- The selection is still deterministic. Deeper contextual social reasoning, persistent uncertain social preferences (owner-memory beliefs with L18 events) and appraisal-driven affect remain **deferred** (see §6).
- The owner-only full-agent path receives the note as an API-only prefix on the current message; that path was not A/B-measured (cost).

## 3b. Full-agent provider fallback (2026-11-08)

**Issue** (`SOURCE-VERIFIED`): the full agent (`openai-codex` / gpt-5.6-sol) had no fallback. PROD `config.yaml` has no `fallback_providers`, and a reused cached agent took only that empty chain, so a codex auth failure, outage or rate limit meant a total non-social outage. The Groq social route's own codex fallback was also lost on cached agents.

**Choice** (`OPERATOR-REPORTED` probes): Hermes' credential pool already holds `copilot`. Its plan is **GitHub Copilot Free**: 200 chat requests a month (resets on the 1st), no premium requests, overage not permitted, so it is never billed. gpt-5.6-sol and the other premium models return `model_not_supported` there. `gpt-4.1` (128K context) is free and handled a tool call correctly. Groq is unsuitable for full-agent turns: its 8K tokens-per-minute limit is below a full tool prompt.

**Fix** (`SOURCE-VERIFIED` #349; no new provider, subscription, infrastructure or lane):
- `router.yaml` `full_agent_fallback: [{provider: copilot, model: gpt-4.1}]` is sent as Hermes' `fallback_model` chain on every routed turn, after the social route's own codex fallback (social: codex, then Copilot; native: Copilot).
- `run.py` applies the router chain to a reused cached agent as well (after Hermes' own config refresh).
- Hermes decides when to switch: auth, billing, rate-limit, overload, timeout and missing-model errors. It retries only the failed model call, keeping tool results already in the history, and restores the primary on the next turn.

**Tests:** 9 new (`test_full_agent_fallback.py`, added to the deploy workflow); deploy/prod suite 79/79. **Host e2e** (`OPERATOR-REPORTED`; throwaway process, no session DB): a fake local primary issued a `todo` tool call, then failed with 429, 401 or 503. In each case Hermes switched to Copilot `gpt-4.1`, finished the reply, and **the tool ran exactly once**. About 11 of the 200 monthly Copilot requests were used for probes.

**Deploy:** router (3 files) and hermes-gateway (`run.py`) via the standard pipeline at `6cfc3be`, smoke checks OK, backups taken. Gateway and Core API active, no errors after restart; the deployed router returns the expected chains.

**Rollback:** `full_agent_fallback: []` (router component), or redeploy the previous mirror/run.py backups.

**Remaining limitations:**
- The fallback is a different, weaker model than gpt-5.6-sol. Personality comes from SOUL.md and memory, not the model, but replies on fallback may be plainer.
- Capacity is 200 model calls a month. A tool-heavy turn uses several, so this covers outages, not sustained use. A same-model second provider would need a paid plan (owner approval).
- The Copilot token exchange reports `degraded to RAW token`; free models work in that mode.
- A cached agent that is mid-cooldown on a fallback keeps it until the cooldown ends (Hermes behavior).

## 4. Feature readiness vs. remaining work

| Area | Current classification | Remaining action |
| --- | --- | --- |
| Seven cognition lanes + Working Memory | `OPERATOR-REPORTED LIVE` | Behavioral quality improvements are **new development**, not missing DEV files |
| L04 canonical memory and owner-only recall | `OPERATOR-REPORTED LIVE` | DEV canonical FORGET not yet promoted; consider separately after critical operational fixes |
| World Model owner memory + exports | `SOURCE-VERIFIED IMPLEMENTED`, `OPERATOR-REPORTED LIVE` | Prove actual replacement runtime/VM can rebuild and use the same identity knowledge |
| L18 owner learning-event ledger | `SOURCE-VERIFIED IMPLEMENTED`, `OPERATOR-REPORTED LIVE` | Do not mistake event tracking for full consolidation |
| L18 long-term memory consolidation | `SHADOW / PARTIAL` | Review existing candidate workers; measured promotion/deduplication/reconciliation is future engineering |
| Social Cognition cue + tone guidance | `SOURCE-VERIFIED LIVE FOR OWNER` (context-aware selection, #346) Offline A/B complete (14/14 scenarios); deeper contextual reasoning and appraisal **deferred research** |
| Natural owner learning | `OPERATOR-REPORTED LIVE, APPROVAL-GATED` | Selective autonomous low-risk learning **deferred**; do not disable approvals casually |
| Google OAuth and related jobs | `OPERATOR-REPORTED BROKEN` | Re-consent affected accounts, confirm scheduler jobs and functional reads |
| Primary full-agent provider fallback | `SOURCE-VERIFIED LIVE` (#349, Copilot Free `gpt-4.1`) | Optional later: same-model paid second provider (owner approval) |
| E-T4 and D1 | `OPEN KNOWN DEFECTS` | Reproduce and fix based on current code; don't invent their exact semantics |
| WhatsApp | `OPERATOR-REPORTED DISCONNECTED` | Repair only if still needed; owner Telegram is working |
| Private owner Discord DM continuity | `NOT CONFIGURED` | Verify owner identity and channel before sharing private context; server groups remain non-owner |
| Command Center/mobile access | `NOT HOSTED / OPTIONAL` | Separate UI/remote-access project |
| PROD backup/snapshot retention | `PARTIALLY COMPLETE` | Verify recoverable copies, review old snapshots and remove only proven redundant copies |
| VM migration | `NOT STARTED` | Verify actual cloud trial deadline (owner expects 2026-11-11), prepare destination, re-seal host-bound credentials, restore-test all data, then switch |

**Key caution:** The 2026-11-06 operator inventory said PROD was ahead of DEV for relevant cognition source. Apart from governed canonical FORGET, **there is no confirmed backlog of valuable DEV-only cognition code needing a wholesale port**. This is a reported deployment comparison, not independently rechecked on the hosts here.

## 5. Execution priority — finish existing work before speculative engineering

1. **Finish already-known operational gaps:** Google OAuth and dependent jobs (requires owner re-consent) and reproducible E-T4/D1 fixes (provider fallback done, §3b). Preserve working Telegram and Core API behavior.
2. **Close existing optional/incomplete integrations according to actual usage:** WhatsApp, owner-private Discord DM, canonical FORGET (DEV-derived), UI if needed. Do not conflate these with incomplete DEV→PROD cutover.
3. **Keep recovery viable:** validate destination-VM key re-sealing, protected memory/World Model/L18 backup and restore, and old snapshot retention. Plan migration separately before the owner's expected cloud-trial expiry.
4. **After existing work:** pursue measured L18 consolidation, advanced Social Cognition, other lane improvements, memory expression, optional low-risk automatic learning and under-budget alternative model research.

Avoid rewriting active subsystems, adding ceremonial gates, or scheduling repeated live user tests when offline regression tests suffice. The owner prefers one real functional example for feature validation.

## 6. Advanced affect / social cognition research note — NOT IMPLEMENTED

**Owner design intent:** Lilith should exhibit coherent, history-dependent changes in *functional* affect rather than a manually set `happy=0.8` / `sad=0.3` label. Small differences in sequences of events may change the implications of a goal, relationship or expectation, leading to different response strategies.

**Independent review input (2026-11-07):** DeepSeek proposed appraisal-based affect: evaluate an event against goal relevance, expectations, relationship/identity stakes, coping possibilities and evidence; derive a tentative action tendency; modulate attention, memory retrieval, response strategy and expression; revise from outcomes. It recommended using existing World Model, Goals, Motivation, Planning, Working Memory, L18 and Social Cognition, without adding a new lane. This is an **external proposal**, not an accepted technical decision or a claim about shipped code.

**Practical revision:** Do **not** build a next-user-message predictor merely to create a surprise score. Begin later with **observable goal/outcome changes** where evidence and expectations already exist. Compare current tone-note baseline with one event-context appraisal hypothesis on a small offline scenario set. Measure response usefulness, consistency, over-inference, latency and cost before promoting any new behavior. Store uncertainty and traceable evidence, not definitive emotion or mental-state assertions. Do not let artificial affect drive unauthorized actions or self-preservation.

**Scientific limit:** Behavioral simulation and appraisal-driven decision modulation may improve companion consistency; they do not establish subjective emotional experience or consciousness.

Research orientation (not an implementation requirement):
- Scherer, *Emotions are emergent processes: they require a dynamic computational architecture* (2009): https://doi.org/10.1098/rstb.2009.0141
- Marsella & Gratch, *EMA: A process model of appraisal dynamics* (2009): https://doi.org/10.1016/j.cogsys.2008.03.005
- Gratch & Marsella, *A domain-independent framework for modeling emotion* (2004): https://doi.org/10.1016/j.cogsys.2004.02.002

**Deferred related work:** deeper pragmatic social reasoning, persistent uncertain social preferences, reflective learning, causal efficacy testing of tone notes, alternative/less-restricted social-model evaluation, and improving natural expression of recalled memories. These are **not blockers** for closing existing operational work.

## 7. Handoff guidance and document update rule

- Before new implementation, compare this note's `PENDING` rows to current GitHub `main`, workflows and live PROD. Mark resolved items with evidence, not inference.
- For each completed change, append PR/commit, test result, deployed environment, remaining limitation and rollback/recovery note. Do not paste secrets, private memories or owner identifiers into this public repository.
- Keep `SOURCE-VERIFIED`, `OPERATOR-REPORTED`, `PENDING`, `RESEARCH` distinct.
- Update `docs/roadmap/roadmap.md` separately if its older stage labels are no longer credible; this work note intentionally does not rewrite that planning document.
- Treat source files and accepted ADRs as authoritative over this handoff summary whenever evidence conflicts.
