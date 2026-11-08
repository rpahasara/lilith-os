# LILITH OS — PROD integration work note (2026-11-07)

> **Scope:** Continuation from [Source consolidation, October 2026](source-consolidation-2026-10.md), through the 2026-11-06/07 PROD canonical-memory, deployer, learning and Social Cognition work.
>
> **Evidence discipline:** `SOURCE-VERIFIED` = PR/code on GitHub; `OPERATOR-REPORTED` = Claude's live-host run reports and owner's Telegram tests, not independently re-run by this document; `PENDING` = not confirmed complete. This note is a **handoff/work log**, not a replacement for acceptance records, audits or live probes.
>
> **Source baseline:** `main` at `28dbe12e76de6a4a9336bbf17b7166ed10633c66` (PR #355 merge; previously `c09e01d`, PR #351). Keep this note updated after later merges.
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
| [#351](https://github.com/rpahasara/lilith-os/pull/351) | E-T4 self-status hint on the current message (owner-only goal read); D1 stored reply = delivered reply | Router + hermes-gateway deploys OK (backups taken); gateway/API healthy, new code loaded |

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

## 3c. E-T4 and D1 (2026-11-08)

**E-T4** (`OPERATOR-REPORTED`, Cutover 2 acceptance 2026-11-04): "what am I working toward right now?" took the `native_self_status` route and read the tracked goals, but twice the model led with a casual weekend plan from the previous turn. Two system-prompt wording fixes did not change that.
- **Fix** (`SOURCE-VERIFIED` #351): the same instruction, shortened, now also rides on the **current message** as an API-only turn hint, the mechanism the tone note uses (never stored). It applies on owner turns only, and replaces the tone note on that turn. Reading the tracked goals on this route is now also owner-only; before this, any live channel could receive the owner's goal lines.
- **Check** (`OPERATOR-REPORTED`): a synthetic run on gpt-5.6-sol (2 samples per variant, synthetic history and goals, no owner data, no tools) did **not** reproduce the original failure: both variants led with the goals. With the hint the answers were fuller and added the long-term goals.
- **Status: `OWNER-CONFIRMED PASS` (2026-11-08).** In a real owner Telegram test after a casual conversation, LILITH correctly put the owner's tracked goals first. **E-T4 is closed** (the Cutover 2 acceptance exception E-T4 is resolved).

**D1** (`SOURCE-VERIFIED`, foundation audit 2026-11-02): when the social guard replaced a reply, `state.db` kept the rejected original. Its `codex_message_items` would also resend that text on the next turn.
- **Fix** (#351): `run.py` calls `record_delivered_reply` only when the guard changed the reply.
  - It updates exactly one row: the session's latest active assistant row without tool calls, whose cleaned text matches the rejected reply.
  - It writes the delivered text into that row and clears its replay columns (`api_content`, `codex_*`, `reasoning*`). The existing FTS update triggers re-index the row.
  - It uses Hermes' own `_execute_write` and never raises. If no row matches, nothing changes.
- Not live-reproduced: guard rewrites are rare and can't be triggered on demand.

**Tests:** 10 new (`test_et4_d1.py`, added to the deploy workflow); deploy/prod suite 89/89. **Deploy:** router and hermes-gateway at `c09e01d`, smoke checks OK, backups taken. **Rollback:** redeploy the previous backups.

## 3d. Google OAuth diagnosis (2026-11-08, owner step pending)

**Evidence** (`OPERATOR-REPORTED`, read-only; metadata only, no token values):
- Both tokens (primary `~/.hermes/google_token.json`, secondary `accounts/secondary/google_token.json`) fail refresh with `invalid_grant`. Their last refresh was 2026-08-31.
- Every 15 minutes, `lilith-career-watcher` and `lilith-meeting-prep` fail (units `failed`; 94 failures each on the last day), and `lilith-agenda-snapshot` and `lilith-gmail-watcher` log a `RefreshError` per account.
- The morning brief runs degraded.
- Both accounts use one *installed* OAuth client (redirect `http://localhost`) in the GCP project `lilith-agent-260823-27389`, with scopes for Calendar, `gmail.modify`, `gmail.readonly` and `gmail.send`.

**Cause (strong inference):** the OAuth client files date from 2026-08-24 and both refresh tokens died on 2026-08-31, exactly 7 days later. That matches Google's 7-day refresh-token expiry for consent screens in **Testing** status. Re-consent alone would fail again within a week.

**Recovery (owner steps):**
1. Google Cloud console, project `lilith-agent-260823-27389`: OAuth consent screen, Audience, **Publish app** (Testing to In production). For personal use the app stays unverified; Google shows an "unverified app" warning on consent.
2. Re-consent each account with `p3tx/deployer/oauth_reconsent.py <primary|secondary>` (local operator tool). It runs Google's loopback flow on the VM behind an IAP SSH port-forward, so the authorization code goes from the browser straight to the VM. The new token is verified with one Gmail profile read before it replaces the old one (kept as `.invalid-<ts>`, 0600).
3. Confirm the next timer runs succeed and the two failed units clear.

**Owner progress (2026-11-08):** publishing was blocked because the Branding page is incomplete (homepage, privacy-policy URL and authorized domains empty).

**Owner decision (2026-11-08): OAuth recovery DEFERRED to the migration.**
- No Google OAuth change in the current trial project, to avoid configuring and authorizing twice.
- During migration, create a **durable OAuth client in the destination project**, publish it (In production, with Branding complete), and authorize **both Google accounts once**.
- Keep that client independent of future VM changes where possible: a project not tied to one VM, tokens restored with the data.
- Until then, the Google-dependent jobs (career watcher, meeting prep, agenda snapshot, Gmail watcher, morning brief Google parts) stay degraded as they have been since 2026-08-31.
- The recovery tooling above (`oauth_reconsent.py`) is reused against the new client.

**Migration note:** the OAuth client lives in the trial project (trial expiry owner-confirmed 2026-11-18). Plan its future together with the VM migration (Gmail/Calendar APIs need no billing, but the project must survive the trial).

## 3e. L18 consolidation and canonical FORGET — what can be finished now (2026-11-08)

**L18 shadow consolidation** (`SOURCE-VERIFIED` code; `OPERATOR-REPORTED` PROD counts):
- `learning_worker.py` (Slice 15A) is a manually invoked, bounded worker. It reads one source, `career_events`, and writes shadow candidates and assessments to `cognitive_memory.db`, with no prompt or retrieval consumer.
- On PROD it has run once (September test batch: 1 job, 3 candidates, 3 assessments). There are 0 `memory_consolidation` traces in the router log, and `memory_item` is 0.
- Its only source is stale: `career_events` = 11, the latest from **2026-08-31**, because the career watcher has been broken by the OAuth failure since then.
- **Completable now:** nothing useful before OAuth is restored. After that, the existing worker can run on a schedule in SHADOW. A unit/timer is outside the deploy pipeline's components, so it needs one owner-approved install. Promotion, deduplication and reconciliation into memory remain **future engineering** (no redesign today).
- The L18 *learning-event ledger* (#341; 12 events) is live and separate.

**Canonical FORGET** (`SOURCE-VERIFIED` code and plans; `OPERATOR-REPORTED` PROD presence):
- The governed FORGET path is already on PROD in the First Memory host tree: `privacy_forget_runner`, `privacy_forget_intent` (hold-first) and the owner tool `relationship_origin_forget_dev.py` (`status | forget --owner-approval REF | resume`).
- Per the accepted PROD plan, its scope is **canonical records only** (D-2) under the interim V1 HMAC authorization (D-6). It covers exactly two closed profiles: First Interaction (synthetic) and **Relationship Origin**, with owners L04 and L18_V2.
- **Completable now without new engineering:** an owner-directed FORGET of the relationship-origin memory. It needs an owner go, owner-device checkpoint (K-PCK) and witness anchoring. The gateway is stopped while it runs, so LILITH is offline briefly.
- **Not covered:** the project-codename canonical memory admitted at Gate 7.1 has no FORGET profile (a new closed profile would be new engineering).
- **Not covered:** erasure of Hermes conversation copies (`state.db`, Telegram) is out of scope by D-2. The DEV-only Hermes erasure executor (F9c2) has no PROD equivalent.
- Nothing was run or changed in this inspection.

## 3f. Snapshot inventory and other existing items (2026-11-08)

**Snapshots** (`OPERATOR-REPORTED`, read-only `gcloud`):
- **33 snapshots**, about **22.5 GB** incremental storage.
- 7 are daily auto snapshots of `lilith-01` (policy `lilith-01-daily`, 18:00 UTC, 30-day retention).
- 26 are manual gate, cutover and fix snapshots from 2026-10-27 to 2026-11-06. The largest is `lilith-01-preserve-20261027`, 5.7 GB.
- `lilith-dev-01` has one manual snapshot (2026-10-27) and no schedule.

**Decision:**
- No deletions now. Snapshots are incremental, so removing the small gate snapshots saves little.
- All snapshots live in the trial project, so they are **not** a migration backup. The migration needs an off-project, portable backup (data, keys handled per the custody rules, tokens) and a verified restore on the destination before switching.
- Retention cleanup happens with the old project's retirement.

**Other existing items re-checked:**
- **Natural-learning gap** ("rejected within one 10-minute snapshot window can be re-proposed"): closed by #340/#341. A rejection now writes an L18 `REJECTED` event, with `memory-review/rejected.jsonl` as fallback, at the moment of rejection, and the nightly review reads both.
- **WhatsApp** and the **private owner Discord DM** need owner decisions: whether WhatsApp is still wanted, and which Discord DM identity counts as the owner. They are left as they are.

## 3g. Private Discord owner DM, documentation cleanup, review index (2026-11-08)

**Schedule (owner, 2026-11-08):** the VM migration moves to **2026-11-14**; the trial still expires 2026-11-18.

**Discord owner DM** (`SOURCE-VERIFIED` #355; router deployed at `28dbe12`, 5 files, smoke OK, backup taken):
- A Discord DM is an owner channel, `discord_owner_dm`, only when all of these hold:
  - it has no guild or thread and is not from a bot;
  - its (user id, DM channel id) pair is listed in the root-owned `canonical_memory.json` `ownerDiscordDms`.
- Display names, roles and server membership prove nothing. Server channels, threads, groups and other users stay `public`.
- **Reuse:** an owner turn takes the existing path. Canonical memory comes through the owner grant (label added at activation); Hermes profile memory and full tools through `owner_memory=True`; Social Cognition owner mode is unchanged; live and cognitive lanes match the label in `router.yaml`, so no Discord id is in the repository. No new store, personality or contract.
- **One-time challenge** (`owner_link.py`):
  1. Send `link owner` in the Discord DM.
  2. A one-time code goes to the verified owner Telegram DM.
  3. Type the code back in that same Discord DM.
  4. The verified pair is recorded as evidence only. The code is kept as a salted hash and expires after 10 minutes (5 tries; at most 3 requests per hour).
- **Activation:** `p3tx/deployer/discord_owner_activate.py` (operator) copies the verified pair into `canonical_memory.json` and adds `discord_owner_dm` to the owner grant. It keeps backups and needs no restart; rollback is by timestamp.
- **Tests:** 14 new; deploy/prod suite 103/103.
- **Post-deploy check** (`OPERATOR-REPORTED`): existing settings load, Telegram is still the owner channel, an unverified Discord DM is `public`, and the grant lists only `lilith_os` and `telegram_owner_dm`.
- **Status: `ACTIVE` (2026-11-08).** The owner completed the challenge in the Discord DM; the first attempt, in the #lilith-home server channel, was correctly ignored. Activation installed the verified pair and the grant label (backup `20261108T081312Z`, no restart).
- **Host check** (`OPERATOR-REPORTED`, labels and counts only): the verified DM resolves to `discord_owner_dm`, and the same account in the server channel resolves to `public`. The context service grants the DM label (`ownerChannel` true, 2 canonical memories).
- **Live tests** (owner-reported done; router log metadata): the DM recall turn was routed **live** (`groq_lean`). Live switching for that DM comes only from the `discord_owner_dm` label, so the turn ran as an owner turn. The server-channel isolation turns stayed on the server channel's own route, with no owner label. No tracebacks.
  - Reply text was not read (privacy). Correctness of the recall is owner-reported.
- **Nightly learning review:** includes the verified Discord DM since 2026-11-08 (see §3h).

**Documentation cleanup:**
- **#311:** not merged. Its scripts embed operator account and infrastructure details, including a personal email. Its 16 historical records were preserved redacted in #356 (merged).
- **#296:** clean, unique proposals (cognition dependencies, goal erasure). **Merged 2026-11-08** with the owner's go. Inert: nothing references its code or config (the drop-in is an uninstalled sample).
- **#311:** **closed unmerged** 2026-11-08 (owner decision) with a pointer to #356.
- **#357:** outdated status claims corrected. AS-IS, the roadmap, `development.md` and the README now say there is an active PROD deployment. Dated updates carry SOURCE-VERIFIED / OPERATOR-REPORTED labels, and the original text is kept as history.

**Review index:** [docs/research/deepseek-review-index-2026-11.md](../research/deepseek-review-index-2026-11.md) indexes the 19-layer architecture, the Master v1.1 affect design (drives, appraisal, fast affect, slow mood, expression), the research questions, implemented lanes and deferred proposals for an independent DeepSeek review. Read-only; no new roadmap until that review is back.

## 3h. Advanced cognition planning (2026-11-08, documentation only)

- The DeepSeek independent review was received.
- PR #360 adds the R&D planning package `docs/research/cognitive-rd-plan-2026-11/` for owner review:
  - AS-IS maturity and gaps against the 19 layers;
  - DeepSeek reconciliation, including factual corrections;
  - a two-loop runtime view with a shared TurnContext;
  - workstreams for social and relationship continuity, appraisal, metacognition, consolidation, goals and initiative, and identity;
  - a phased roadmap with token-budget costs and ten registered experiments.
- It authorizes nothing. P-0 is the 2026-11-14 migration.
- **Planning package merged** as #360 (owner-approved *as a documentation proposal*; no implementation until after the migration and OAuth recovery). Clarifications:
  - P-1 scenario suites are cumulative targets that start small;
  - external literature stays unverified until R-0.
- **Nightly learning review includes the verified Discord owner DM** (`SOURCE-VERIFIED` #362; owner GO 2026-11-08).
  - `owner_memory_review.py` adds only Discord sessions whose (user id, DM channel id) pair is in the root-owned `canonical_memory.json` `ownerDiscordDms` with `chat_type` dm, the router's own owner rule.
  - Server channels, threads, other DMs and other users are excluded; malformed pairs fail closed.
  - Proposals, owner approval, LILITH-OS-first recording and L18 events are unchanged. There is no new store.
  - Identical lines from two channels appear once, and the remembered / pending / rejected lists stop repeat proposals.
  - **Install** (outside the deploy pipeline): one file at `~/.hermes/scripts/owner_memory_review.py`, hash `8c9bc4fe`, backup `/var/backups/lilith-review/20261108T093502Z`.
  - **Verification** (`OPERATOR-REPORTED`, counts only): 1 verified pair; owner sessions are 28 console, 4 Telegram DM and 1 Discord DM. 6 lines in the window come from the Discord DM; the server-channel session is excluded; the context header names the verified Discord DM.
  - **Rollback:** `p3tx/deployer/review_discord_install.py rollback 20261108T093502Z`.
- **Migration implications (2026-11-14).** The new VM must carry all of these unchanged, or the Discord DM silently loses owner status and leaves the review:
  - **(1)** root-owned `lilith_router/canonical_memory.json`, including `ownerDiscordDms`;
  - **(2)** the owner grant `/etc/lilith-first-memory-dev/hermes-owner-channel.json`, including `discord_owner_dm`;
  - **(3)** `~/.hermes/scripts/owner_memory_review.py`, which is outside the pipeline, so its hash must be checked against main;
  - **(4)** `~/.hermes/owner-link/verified.json`, kept as evidence;
  - **(5)** `state.db`, for session history.
  The Discord user and DM channel ids don't change with the host, so no re-verification is needed. Re-run the counts-only check after the switch.

## 3i. R-0 and P-1 preparation (2026-11-08, documentation only)

- **R-0 complete** (#364): the DeepSeek review's 13 citations were checked against primary listings.
  - 6 are verified as described, 4 are verified with a narrower scope, 3 are preprints, and none are missing.
  - Results, corrections and applicability are in `docs/research/cognitive-rd-plan-2026-11/12-r0-citation-verification.md`.
  - No design decision changed.
- **P-1 prepared** (`13-p1-implementation-tasks.md`): tasks T-1..T-6, all after the migration.
  - T-1 turn id on every decision-log record; T-2 one turn-end record (model, fallback, guard, latency, tokens);
  - T-3 a read-only summarizer; T-4 the eval harness moved into Git with small focused scenario sets;
  - T-5 an owner blind-rating scorer; T-6 log retention.
  - No PROD change was made.
- **Findings** (`OPERATOR-REPORTED`, metadata only):
  - `decisions.log` has 433 records over 73 days, **no rotation**, and per-lane records that cannot be correlated.
  - **247 legacy records hold a `preview` field of up to 60 characters of message text**, from both owner and public channels, the latest about 5 days old. That code was replaced at Cutover 2, and the current router writes no text.
  - **Owner decision needed** (T-6b): drop the field during the migration rather than carry it into the off-project backup.

## 3j. P-1 implementation: trace, retention and offline evaluation (2026-11-08)

Owner GO 2026-11-08: implement P-1 now; migration stays separate and needs explicit authorization.

| Task | PR | Deployed | What |
| --- | --- | --- | --- |
| T-1 turn id | #366 | router `218da29` | `turn_id` (16 hex) on every decision-log record through one `_append_log` writer; `turn_trace_enabled` flag |
| T-2 turn-end record | #367 | router + hermes-gateway `456158d` | one `lane: turn` record: route, mode, answered_by, provider/model, fallback, api_calls, per-turn tokens, guard_changed, d1_recorded, reply length, duration |
| T-6 retention | #369 | router `1890d10` | `decisions.log` rotates to `.1` at `decision_log_max_bytes` (2 MB) |
| T-3/T-4/T-5 tools | #368, #370 | (operator tools) | `scripts/cognitive_eval/`: `trace_summary.py`, `replay.py`, `blind.py`, the 14-scenario synthetic set |

**Rules held:**
- No extra model call for tracing.
- No message text or reasoning in any record (tests assert it; the summarizer prints only allow-listed labels).
- LILITH's behaviour is unchanged.
- Rollback: `turn_trace_enabled: false`, or the deploy backups.
- Tests: 26 new in `test_p1_trace.py` plus 6 tool tests in CI; deploy/prod suite 138/138.

**Measured** (`OPERATOR-REPORTED`):
- **Legacy scrub** (owner decision): `scrub_legacy_preview.py` removed **284** `preview` message-snippet fields (247 in the live log, 37 in the 2026-08-26 `.bak`). Every record and all other metadata were kept; 0 remain. Conversation history and canonical memory were not touched.
- **Harness smoke on PROD:** 6 scenarios × 2 arms (baseline vs deployed tone note), 12/12 calls succeeded, **33,357 tokens** (2,623–3,177 per lean call, the same as the §3a A/B), inside the 40K run budget.
  - The run exposed a tool bug: latency included the TPM back-off sleep (~22 s per call). Fixed in #370 before any latency was reported.
  - The blind sheet is kept by the operator for the owner's rating; no quality result is claimed yet.
- **Live trace verified** (owner Telegram messages, 2026-11-08; `trace_summary.py`, aggregates only):
  - 3 turns; `turn_id` coverage 100% (14 of 14 records); 0 legacy-preview records.
  - Answered by: 1 lean (`groq/qwen3.8-27b`) and 2 agent (`openai-codex/gpt-5.6-sol`). No fallback, guard rewrite or D1 correction.
  - Tokens per turn: **lean ≈ 3.7K; agent ≈ 39K**, almost all prompt (system, tools and history). Agent turns cost about 10× a lean turn, which matters for P-3 G-ESCALATE.
  - Turn duration: lean 5.7 s; agent p50 9.5 s and slowest 23.7 s (n = 2; indicative only).
  - 4–5 lane records per turn, all joined by `turn_id`.

**Smallest useful P-2** (proposed, not started):
- **(a) Correction routing.** Owner corrections ("don't call me…", "stop …", "I told you…") stay on the tool-less lean path today, so no memory proposal can follow. Adding correction phrasing to the existing durable-statement detector (`social_lean._MEMORY_STATEMENT_RE`, #338) routes them to the full agent. There the existing in-chat proposal → owner approval → LILITH OS → L18 flow handles them. No new store or lane; flag-gated.
- **(b) E-6 first, 6–8 cue → trigger scenarios.** Compare a correction left only in history against the same correction as an approved profile line (≤30K tokens), plus live recurrence from the trace.

## 4. Feature readiness vs. remaining work

| Area | Current classification | Remaining action |
| --- | --- | --- |
| Seven cognition lanes + Working Memory | `OPERATOR-REPORTED LIVE` | Behavioral quality improvements are **new development**, not missing DEV files |
| L04 canonical memory and owner-only recall | `OPERATOR-REPORTED LIVE` | Relationship-origin FORGET available on owner request (§3e); codename memory has no FORGET profile |
| World Model owner memory + exports | `SOURCE-VERIFIED IMPLEMENTED`, `OPERATOR-REPORTED LIVE` | Prove actual replacement runtime/VM can rebuild and use the same identity knowledge |
| L18 owner learning-event ledger | `SOURCE-VERIFIED IMPLEMENTED`, `OPERATOR-REPORTED LIVE` | Do not mistake event tracking for full consolidation |
| L18 long-term memory consolidation | `SHADOW / PARTIAL` (source stale since 08-31) | After OAuth: schedule the existing shadow worker; promotion/dedup/reconciliation is future engineering (§3e) |
| Social Cognition cue + tone guidance | `SOURCE-VERIFIED LIVE FOR OWNER` (context-aware selection, #346) | Offline A/B complete (14/14 scenarios); deeper contextual reasoning and appraisal **deferred research** |
| Natural owner learning | `OPERATOR-REPORTED LIVE, APPROVAL-GATED` | Selective autonomous low-risk learning **deferred**; do not disable approvals casually |
| Google OAuth and related jobs | `OPERATOR-REPORTED BROKEN` (cause: Testing-status 7-day tokens); **deferred to migration** (owner, 2026-11-08) | New durable client in the destination project, published, both accounts authorized once (§3d) |
| Primary full-agent provider fallback | `SOURCE-VERIFIED LIVE` (#349, Copilot Free `gpt-4.1`) | Optional later: same-model paid second provider (owner approval) |
| E-T4 and D1 | E-T4 `OWNER-CONFIRMED PASS` (2026-11-08); D1 `DEPLOYED` (#351) | None (D1 not live-reproducible; guard rewrites are rare) |
| WhatsApp | `OPERATOR-REPORTED DISCONNECTED` | Repair only if still needed; owner Telegram is working |
| Private owner Discord DM continuity | `ACTIVE` (#355; activated 2026-11-08) | Optional: include Discord DM sessions in the nightly learning review (§3g) |
| Command Center/mobile access | `NOT HOSTED / OPTIONAL` | Separate UI/remote-access project |
| PROD backup/snapshot retention | `PARTIALLY COMPLETE`; inventory 2026-11-08 (§3f) | Off-project portable backup + restore verification during migration; no snapshot deletion before then |
| VM migration | `NOT STARTED` (planned from 2026-11-09) | GCP trial expiry **owner-confirmed 2026-11-18**. Prepare destination, re-seal host-bound credentials, backup + restore verification of all data, durable OAuth client + one-time authorization of both accounts, then switch |

**Key caution:** The 2026-11-06 operator inventory said PROD was ahead of DEV for relevant cognition source. Apart from governed canonical FORGET, **there is no confirmed backlog of valuable DEV-only cognition code needing a wholesale port**. This is a reported deployment comparison, not independently rechecked on the hosts here.

## 5. Execution priority — finish existing work before speculative engineering

1. **Finish already-known operational gaps:** Google OAuth and dependent jobs (requires owner re-consent) and reproducible E-T4/D1 fixes (provider fallback done, §3b). Preserve working Telegram and Core API behavior.
2. **Close existing optional/incomplete integrations according to actual usage:** WhatsApp, owner-private Discord DM, canonical FORGET (DEV-derived), UI if needed. Do not conflate these with incomplete DEV→PROD cutover.
3. **Keep recovery viable:** validate destination-VM key re-sealing, protected memory/World Model/L18 backup and restore, and old snapshot retention. Plan migration separately before the cloud-trial expiry (owner-confirmed **2026-11-18**; earlier provisional date 2026-11-11 superseded).
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
