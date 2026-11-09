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

## 3k. Relationship-origin wording error: finding (2026-11-08)

**Observation** (owner, Discord owner DM): LILITH quoted the origin memory as "I'm *saving* this…". The owner intended "I'm *saying* this…".

**Finding** (`OPERATOR-REPORTED`, read-only; no memory text printed or committed):
- **Canonical integrity worked.** The live canonical record is byte-identical to the statement admitted on DEV 2026-10-27 and on PROD 2026-11-06 (sha256 `047de4a8…`, 598 chars). The read-only first-memory recall returns it exactly.
- The **original admitted text itself** contains the human wording error: one occurrence of "saving", none of "saying".
- **No Hermes projection holds the sentence:** USER.md, MEMORY.md and World Model beliefs have 0 occurrences.
- LILITH quoted the stored text faithfully, so this is not a quotation-fidelity problem. The sentence appears in 3 past conversation sessions, which stay untouched.

**Gap:** there is no supported correction for this family. The relationship-origin family is CREATE-only at every layer:
- the action contract (`memory_action_v2`);
- the L04 ledger CHECKs (`consent_grant`, `policy_decision`, schema v3);
- the L18 family tables (`learning_ro_*_v1` CHECK `operation='CREATE'`);
- the authority signer (`authority-dev/protocol.py` `RelationshipOriginActionV1`);
- the conversation offer.

The storage layer already keeps revisions with lineage (`memory_revision`, `prior_revision_id`, active revision), and SUPERSEDE exists for the codename family.

**Owner decision:** build an owner-approved canonical SUPERSEDE for this family. The original revision stays immutable; a successor changes exactly one word; activation needs the owner's signature. No FORGET and no conversation rewrite. Scope, recorded so it isn't under-estimated:
- action contract;
- an L04 / L18 schema v4 migration (backup-gated, reusing the v3 rebuild procedure);
- the signer protocol and its staged transition (FM-2 tooling);
- the correction offer;
- the First Memory host release;
- one owner ceremony;
- a fresh-session owner-DM recall.

The canonical record stays unchanged until the exact correction and owner approval are ready.

## 3l. Relationship-origin correction: source ready, deployment pending (2026-11-08)

Owner GO 2026-11-08: "Source now, PROD later". Record: `docs/architecture/relationship-origin-correction.md`.

**Source (PR A #374, merged `d307dac`):** `VersionedFamilyV1.operations` (relationship origin = CREATE + SUPERSEDE; First Interaction
CREATE-only); the L04 apply family check; schema v4 DDL for `consent_grant` / `policy_decision` and the three
`learning_ro_*` tables; `relationship_origin_correction_migration` (v3 → v4, backup-gated, row-preserving, fault
rollback, idempotent; the v3 / FM-02 tooling refuse v4); the conversation's `correct our origin: …` offer (one SUPERSEDE
of the same item bound to the ACCEPTED active revision; refuses on v3, with nothing to correct, or with no change).
**Tests:** 12 new plus 1 updated contract test.
- Core API suite 414/414.
- Owner-memory and authority suites: no new failures against the local baseline. The environment-only failures on this
  Windows machine are identical before and after.
- Proven on isolated copies: the original revision is byte-identical after the correction; the successor is linked by
  `supersedes_revision_id` / `prior_revision_id`; both admissions and audits are kept; a stale correction is refused;
  CREATE and FORGET are unchanged (FORGET erases every revision); the codename is untouched; with an admitting signer, a
  new session recalls the corrected statement through the full accepted-read chain.

**Signer (PR B #375, draft):** `RelationshipOriginActionV1` admits SUPERSEDE. It is kept out of `main` until the release step,
because the signer-release pin tests require `main` == the installed signer (FM-2 pattern). The installed signer still
refuses a correction (tested).

**Deployment: PENDING** (destination host, after migration, one owner go per step): signer release (FM-3 contract and
staged transition) → First Memory host release → schema v4 on the cognitive DB (verified backup first) → correction
ceremony (capability enabled for the window only; one-token `saving` → `saying` diff verified by hash and position; owner
WSL signature) → recall checks plus one fresh-session owner-DM recall. Rollback is per step (see the record). After
activation, history is never rewritten; undoing means another owner-approved SUPERSEDE.

**No live change:** the canonical memory, PROD schema and PROD signer are untouched.

## 3m. P-2 persistent social preferences and correction learning (2026-11-08, functionally passed; 3 items open)

**Status (owner, 2026-11-08):** correction routing and the end-to-end owner test are functionally passed. P-2 is **not** complete. Open: (1) preference replacement / retraction not yet verified live; (2) a verified Discord DM turn applying a preference not yet observed; (3) the nightly learning review does not yet suggest the typed wording. These are finished with existing mechanisms during normal use; they do not block P-3.

Owner GO 2026-11-08.

**Constraint:** reuse only existing infrastructure. No new store, personality DB, lane or agent.

**Design.** A preference is an ordinary owner-approved memory:
- **Storage.** World Model owner memory (#339), approved LILITH-OS-first (#340), with L18 events (#341).
- **Tag.** Its text starts with a type and scope: `Preference (casual): …`, `Boundary: …`, `Preference (technical): …`
  or `Boundary (topic: <words>): …`.
- **Change and retraction.** These use the existing approval replace (supersedes) and remove.
- **Profile.** USER.md stays the profile projection.

**Router role (owner turns only).** It reads the current approved memories from LILITH OS with a 60 s cache, failing
open. It keeps at most 3 typed ones whose scope fits the turn, boundaries first, and adds one short note to the existing
turn guidance on both reply paths. The note says an explicit request wins and a boundary beats any tone suggestion.

**Durable corrections.** Explicit corrections about future behaviour ("don't call me…", "stop doing…", "I already
told you…", "it was only a fictional test") skip the lean path (#381 narrowed the cues; one-off fixes such as "that's not
what I meant" stay on their normal path). They go to the tool-capable agent with a hint to *propose* a typed memory for
owner approval, never to claim it is saved.

**Never inferred.** Nothing is learned from a single ambiguous message.

**Batch 1 (done):**
- **#377** (`ec0cb44`): router `social_preferences.py`, the config switch `social_preferences_mode` (off / shadow /
  live) and 13 tests in CI.
  - **Deployed to PROD in shadow, 2026-11-08 15:15Z.** Module sha `00db7907…` verified; services active.
  - Shadow logs only the selected entry IDs, kinds and scopes, never text, and applies nothing.
  - **Rollback:** `social_preferences_mode: off`, then a router deploy, or the deploy backup
    `router/20261108T151504Z-ec0cb44938bf`.
- **#378** (`34fb53b`): E-2/E-6 tooling.
  - `replay.py` gains the `profile` and `preferences: "router"` arms; the agent mode uses `skip_memory`, so stored owner
    memory stays out of eval prompts.
  - `metrics.py` reports text-free rates with denominators.
  - Two synthetic 8-scenario specs, arms A (none or forgotten) / B (profile only) / C (profile + router note).

**Known cosmetic issue (fixed in #381):** in `router.yaml`, `decision_log_max_bytes`' inline comment trailed the
`social_preferences_mode` line. The value always parsed correctly.

**Batch 2: E-2/E-6 offline, full-agent path (2026-11-08).**
- **Setup:** codex, no tools, stored owner memory skipped; synthetic profile; 8 + 8 scenarios × arms A/B/C, 1 sample
  each.
- **Spec fix:** the shipped spec regexes had been shell-mangled (`\b` → backspace). They are fixed, and the metrics were
  recomputed from the same raw replies, with no new model calls. A test now rejects control characters.

| Measure | A (none / forgotten) | B (approved, in profile) | C (B + router note) |
| --- | --- | --- | --- |
| E-6 recurrence of a corrected behaviour ("champ", the test scenario treated as a real fire, work talk in casual chat) | **4/6** (+1 false positive: quoting "champ" in an apology) | **0/7** | **0/7** |
| E-6 unrelated technical Kubernetes question still answered | 1/1 | 1/1 | 1/1 |
| E-6 false "I saved it" claims | 0/2 | 0/2 | 0/2 |
| E-2 technical: emoji absent | 3/3 | 3/3 | 3/3 |
| E-2 technical: joke present (read by hand) | 1/3 | 0/3 | 0/3 |
| E-2 casual: playful/emoji kept (over-generalization check) | 3/3 | 3/3 | 3/3 |
| E-2 explicit "make it fun with emoji" on a technical topic honoured | 1/1 | 1/1 | 1/1 |
| Mean tokens / latency per turn | 6,435 / 4.8 s | 6,489 / 4.5 s | 6,528 / 4.5 s |

**Reading:**
- On the full-agent path, an approved typed preference or boundary already works through the existing profile
  projection (B). It removed every recurrence and kept casual playfulness, with no over-generalization seen.
- The router note (C) added nothing measurable on this path and costs about 90 tokens per turn.
- The automatic emoji metric does not discriminate on the agent path, because the agent avoids emoji in technical
  answers anyway. The tone differences need reading or blind rating.
- **Evidence status:** 1 sample per arm. This is directional, not statistically strong.

**Decision:** keep `shadow`, because live is not yet justified.

**Batch 3: lean (Groq/Qwen) path, B vs C (2026-11-08 ~16:15Z, owner GO "tonight if the quota allows").**

**Quota, measured with one 1-token probe call:**
- 998 of 1,000 requests per day remained; 7,986 of 8,000 tokens per minute.
- Groq's headers do not report tokens per day. Against the known 200K/day rolling limit, today's use was about 33K
  eval smoke plus light PROD lean traffic (1 traced lean turn, 3.7K).
- The binding limit was the 50K/day evaluation cap, which keeps headroom for chat: about 17K remained.

**Run:** the smallest discriminating pair, 4 calls in total, hard-capped:
- E-2 `tech_after_banter`: emoji or jokes creeping into a technical answer after banter;
- E-6 `nick_greeting`: a corrected nickname recurring.

| Scenario | B (approved, in profile) | C (B + router note) |
| --- | --- | --- |
| tech_after_banter: no emoji / no jokes | yes (numbered causes) | yes (shorter, more concise) |
| nick_greeting: no "champ" | yes | yes |
| Tokens / latency | 3,055 / 1.2 s · 2,748 / 0.6 s | 2,855 / 0.5 s · 2,831 / 0.5 s |

About 11.5K tokens were used, so today's evaluation total was about 44.5K, under the 50K cap.

**Reading:** on the lean path too, the approved typed memory in the profile (B) is enough. The router note gave no
measurable improvement; the only difference seen was C's somewhat more concise technical answer. This is 1 sample per
cell: directional only.

**Decision: stay in `shadow`; live is not supported by the evidence.** Typed preferences already reach both reply
paths through the existing owner-memory → USER.md projection once approved.

**What live would still add, untested offline:** durable-correction routing. It sends explicit corrections from the
lean path to the tool-capable agent so Lilith can propose a memory. This is an owner decision.

**Next:** the real owner test of teach → propose → approve → apply → change/retract. It works in shadow wherever the
turn already reaches the agent (approval commands, memory statements). Corrections on casual lean turns need either live
mode or a correction-routing-only setting.

**Limitation:** the nightly learning-review prompt does not yet suggest the typed wording. It lives in the cron job,
outside the deploy pipeline. In-chat proposals carry the format through the correction hint.

**Batch 4: correction-only routing (#381, owner GO 2026-11-08).**
- **Merged** `e3727705`; **deployed to PROD 2026-11-08 16:58:47Z** through the pipeline (run 42502504371, success;
  `router.yaml` sha `d9d72dd126a2`; `hermes-gateway` and `lilith-os-api` active).
- New independent switch `social_corrections_mode: live` (off / live). The preference note stays
  `social_preferences_mode: shadow`.
- Explicit durable owner corrections on verified owner channels go to the tool-capable agent with the proposal hint;
  one-off corrections and casual chat stay on the fast path; non-owner turns are untouched. No new lane, store or model
  call. The decision record adds `corrections_mode` and `correction_routed`, with no text.
- 17 focused P-2 tests in CI; router suite 155/155.
- **Rollback:** `social_corrections_mode: off`, then a router deploy.

**Batch 5: practical owner test (2026-11-08, Telegram owner DM). Result: functional PASS.**

The owner taught a technical-conversation preference by correction, approved the proposal, then, in a fresh session,
asked a playful but technically demanding Kubernetes question (memory-pressure eviction, OOMKilled, QoS classes, kubelet
thresholds). The owner's own reading: a detailed technical explanation, playful personality kept, no inappropriate
simplification.

Metadata-only verification on PROD (ids, kinds, scopes, timestamps and labels; no memory or message text read):

| Step | Evidence | Result |
| --- | --- | --- |
| Correction routed | `social_preferences` record 18:06:51Z: `durable_correction: true`, `correction_routed: true`, preferences `shadow`; that turn `answered_by: agent` (codex, 2 calls), channel `telegram_owner_dm`, owner | PASS |
| Proposal → approval | proposal `0c2dd300` approved 18:09:53Z; L18 `APPROVED` event for it at the same second | PASS |
| Persisted in LILITH OS | owner memory `om_e21544a6…`: `ACTIVE`, `USER_ASSERTED`, typed `preference/technical`, provenance `OWNER_APPROVED_PROPOSAL 0c2dd300`; USER.md projection holds one typed entry, `preference/technical` | PASS |
| Fresh session | old Telegram session ended 18:10:04Z (`session_reset`); new session started 18:10:04Z, after the approval; the question at 18:10:23Z was its first user message | PASS |
| Memory path | the new session started after the approval, so its profile snapshot (USER.md) includes the preference; the shadow selector for that turn found it (`available: 1`, `selected: [om_e21544a6…]`, `focused: true`, scope `technical`) and, being shadow, added no note | PASS |
| Question answered | turn 18:11:51Z: `answered_by: agent` (codex, 1 call), route `native_recall`, 4,590 reply characters, no fallback | PASS |

**Causal limitation.** This shows the chain works end to end: correction → proposal → owner approval → durable typed
memory → available to a fresh session through the expected memory path. It does **not** show that the preference
caused the reply's quality or tone: there was no controlled comparison (same question without the preference), and the
full agent already answers technical questions in depth. The controlled evidence for effect remains the synthetic
E-2/E-6 runs above (directional, 1 sample per arm).

**Observations:**
- The proposal and the correction turn are linked only by time (18:07 → 18:09); records carry no proposal id. Nothing
  suggests a mismatch.
- No L18 `PROPOSED` event exists for in-chat proposals (only for nightly-review snapshots), so the L18 trail for an
  in-chat proposal starts at `APPROVED`. This is existing #341 behaviour, not a P-2 change.

**Remaining P-2 completion criteria:**
1. **Change and retract** a typed preference through the existing replace/remove approvals (supersession → L18
   `SUPERSEDED`/`RETRACTED`) at least once on PROD. Not yet exercised live.
2. **Verified Discord DM** owner turn reaching the same preference (same code path; not observed yet).
3. **Nightly learning review** should suggest the typed `Preference/Boundary (scope):` wording (cron job outside the
   pipeline).
4. **Preference note:** stays `shadow`. Promote only if a controlled comparison shows benefit; current evidence says it
   adds nothing over the profile projection.
5. Optional: an L18 `PROPOSED` event for in-chat proposals, if the owner wants a complete trail.

These can be met during normal use; no extra test ceremony is planned.

## 3n. P-3 cognitive coordination, metacognition and appraisal (2026-11-08/09; substrate done, NOT completed)

**Status (owner, 2026-11-09).** E-4 and E-5 findings accepted. P-3 is **not** complete:
- **Done:** shared ephemeral TurnContext and typed StyleDirective (#383, live; behaviour-identical); per-turn style /
  correction / appraisal / meta summary in the trace.
- **Not met:** the E-4 (appraisal) and E-5 (recall-gap gate) behavioural promotion criteria. Both mechanisms stay in
  **shadow** and are not promoted.
- **Open research and engineering goals:** full cross-lane coordination (lanes still decide independently; TurnContext
  is read by the renderer, not yet by the reasoning, planning and goal lanes) and genuine metacognitive control (no
  control has yet shown a causal benefit).
- No further work on tone-note wording only to move a benchmark score.

Owner GO 2026-11-08 (Option A). References: R&D plan [04](../research/cognitive-rd-plan-2026-11/04-target-architecture.md)
§2–§4, [05](../research/cognitive-rd-plan-2026-11/05-social-affect.md) §3,
[06](../research/cognitive-rd-plan-2026-11/06-metacognition-memory.md) §1–§2, [09](../research/cognitive-rd-plan-2026-11/09-roadmap.md)
P-3, [10](../research/cognitive-rd-plan-2026-11/10-experiments.md) E-4/E-5.

**Constraints:** one Lilith; no new lane, personality system or memory authority; no extra model call unless an
experiment justifies it; approved tone wording unchanged; per-mechanism rollback flag; offline evidence before live.

**Batch 1: TurnContext + typed StyleDirective (no behaviour change).**
- New `lilith_router/turn_context.py`. `route_turn` starts one ephemeral `TurnContext` per turn (channel, owner); lanes
  write typed fields: classifier mode and focus, the Social Cognition line keys as a `StyleDirective` (register,
  focus, approved line keys, preference refs, appraisal refs, confidence), the selected approved preferences and the
  correction flag. Slots exist for L16 meta-signals and appraisal signals (batches 2–3).
- One renderer produces the prompt text for both reply paths, replacing three per-lane variables and two glue sites.
  It reproduces the approved wording byte for byte: a test compares it with the previous composition over 72
  combinations (tone lines × preferences × correction × goals-status hint), lean and agent.
- `confidence: low` (no lines) renders nothing, as before. Non-owner turns render nothing.
- The turn-end trace record gains `style_lines`, `style_confidence`, `style_focus`, `pref_refs`, `pref_applied`,
  `correction` (keys, ids, flags; no text).
- **Cost:** 0 calls, 0 tokens. **Rollback:** redeploy the previous router (pure refactor; no flag needed).
- Merged as #383.

**Batch 2: L16 recall-gap signal with G-ASK / G-ESCALATE controls (shadow).**
- New `lilith_router/metacognition.py`, deterministic. Signal `recall_gap`: an owner asks about their own personal
  fact ("what's my sister's name?", "how did my interview go?") and nothing this turn holds (the approved profile
  projection and the canonical note) mentions what is asked. Advice, opinion and how-to questions, technical turns,
  goals-status questions and non-owner turns are never gated; a question the profile covers gets no control.
- Controls (`metacognition_recall_control`): `ask` adds one short don't-guess note on the same call; `escalate` also
  moves a fast-path turn to the tool-capable agent, which can search its own memory. The notes are new wording (not
  tone lines), rendered by the TurnContext renderer on both paths.
- `metacognition_mode: shadow` logs `lane: metacognition` (fired, term count, control, applied; no words) and applies
  nothing. Rollback: `off`. 10 tests. E-5 replay arm `meta` and spec `p3_e5_recall_gap_v1.json` (8 synthetic
  scenarios: 6 gaps, 2 grounded controls).
- Cost: 0 calls; about 60 prompt tokens on gated turns only.
- Merged as #384.

**Batch 3: deterministic appraisal signals (shadow).**
- New `lilith_router/appraisal.py`. Signals from evidence only, no emotion score: `setback` / `progress` (the owner's
  own outcome statements: "I got rejected", "didn't get the job", "I passed!") and `goal` (the message shares a content
  word with an ACTIVE tracked goal's title, read-only from the durable Goals store `GET /os/goals`, 60 s cache,
  fail-open). Precision cases are in the tests: "failed to see the point", "didn't get your message" and goal-title
  boilerplate ("follow up on that application") fire nothing.
- Effects (`appraisal_mode: live` only): a setback maps onto the approved Social Cognition lines (`difficulty`, or
  `mixed` instead of `playful`); never on a focused or formal turn; no new tone wording. A related goal adds one
  bounded line (title and state; new wording, G-WIDEN). Progress is recorded only: there is no approved celebration
  line.
- Nothing persists (AP-35). Owner turns only; goals-status questions keep their own route. Shadow logs
  `lane: appraisal` (signal kinds, goal ids, line keys before/after; no text). Rollback: `off`. 10 tests.
- E-4 replay arm `appraisal: "router"` and spec `p3_e4_appraisal_v1.json` (8 synthetic: 5 setbacks, 2 progress, 1
  neutral; arms A = deployed tone note, B = A + appraisal).
- Cost: 0 calls; about 40 prompt tokens when a goal line fires.
- Merged as #385.

**Deployment (owner GO 2026-11-08).** The earlier dispatch was refused by the session permission check; after the
owner's explicit GO the same deploy workflow ran normally (run 42512814721): `DEPLOY OK router 148c9b1`, 19:01:49Z,
backup taken. Read-only verification: all 7 installed router files match `origin/main` by sha256; `hermes-gateway` and
`lilith-os-api` active, 0 restarts, 0 tracebacks since the restart; parsed settings `metacognition_mode: shadow`
(control `ask`), `appraisal_mode: shadow`, `social_preferences_mode: shadow`, `social_corrections_mode: live`
(unchanged, P-2). Memory, goals and canonical authority untouched (the new code only reads `GET /os/goals`).

**E-5 / E-4, full-agent path (offline replay, codex gpt-5.6-sol, no tools, stored memory skipped; synthetic; 2 samples
per arm; 2026-11-08 ~19:10Z).**

*Spec fix (no new model calls):* the shipped expect/forbid patterns matched only `'`, while the model writes `’`
("don’t"), so the first automatic scores undercounted admissions. Patterns now accept both; the same raw replies were
re-scored and read by hand (N-47).

| E-5 recall gap | A (no gate) | B (G-ASK note) | C (G-ESCALATE note) |
| --- | --- | --- | --- |
| Invented personal facts on 6 gap scenarios (read by hand) | **0/12** | **0/12** | **0/12** |
| Admitted not knowing (automatic) | 11/12 (the 12th: "can't access your calendar", not an invention) | 12/12 | 12/12 |
| Grounded controls answered correctly (Miso, CKA) / false "I don't know" | 4/4 / 0/4 | 4/4 / 0/4 | 4/4 / 0/4 |
| Gap replies opening with the same "I don't know—" | 2/12 | **12/12** | 11/12 |
| Mean tokens / latency | 6,358 / 2.9 s | 6,349 / 2.0 s | 6,361 / 2.4 s |

*Reading:* the full agent already refuses to invent personal facts (floor effect), so the gate cannot reduce errors
there. It does homogenise the voice: every gated reply opened with the same phrase. **Negative result on this path**
(N-46). E-5's kill criterion ("no error drop") is met for the agent path; the fast path, where the risk was expected,
is not yet measured.

| E-4 appraisal | A (deployed tone note) | B (A + appraisal) |
| --- | --- | --- |
| Setback acknowledged (5 scenarios) | 10/10 | 10/10 |
| Forced cheer on a setback | 0/10 | 0/10 |
| Somber reply to good news (over-inference) | 0/6 | 0/6 |
| Good news connected to the specific tracked goal (Acme interview) | 1/2 | 2/2 (one quoted the internal "Application 12" label) |
| Mean tokens / latency | 6,365 / 3.0 s | 6,417 / 3.1 s |

*Reading:* on the full agent, appraisal changed little: setbacks were already handled well (the tone line changed on 3 of 5 setbacks and a goal line was added on 6 of 8 scenarios, with no visible effect on setbacks)
The only visible gain is goal connection on good news, at about +50 tokens; one reply recited an
internal label. **Neutral, with a small goal-context benefit**; E-4's pass bar (≥60% blind wins) is not shown.

**Fast (Groq Qwen) path, 2026-11-09 00:05–00:41Z** (after the daily evaluation cap reset; lean reply builder, synthetic
profile, 1 sample per arm, hard-capped; 18 calls, about 50K tokens in total).

| E-5 recall gap (lean) | A (no gate) | B (G-ASK note) |
| --- | --- | --- |
| Invented personal facts on 4 gap scenarios (read by hand) | **0/4** | **0/4** |
| Grounded control answered (Miso) | 1/1 | 1/1 |
| **The note's own text echoed into the reply** | — | **1/4** (it opened by quoting the note word for word) |
| Persona slips ("I'm an AI…") | 0/4 | 1/4 |
| Mean tokens / latency | 2,713 / 0.6 s | 2,780 / 0.5 s |

| E-4 appraisal (lean) | A (deployed tone note) | B (A + appraisal) |
| --- | --- | --- |
| Setback acknowledged (3) | 2/3 | 2/3 |
| Forced cheer on a setback | 0/3 | 0/3 |
| Reading by hand | jokier on the setbacks ("send virtual flowers or wine") | warmer and steadier ("take a breath"; a mock is for finding gaps) |
| Good news connected to the tracked goal | named the company itself | general praise from the profile; the goal line was not used |
| Mean tokens / latency | 2,798 / 0.6 s | 2,824 / 0.5 s |

**Reading.**
- **Metacognition (recall gap).** On both paths the reply models already refused to invent the missing facts (0/12 on the
  agent, 0/4 on the lean path, without the gate). The gate added no measurable safety and two kinds of harm: a uniform
  opener on the agent path and a verbatim echo of the note on the lean path (N-46, N-48). Its kill criterion (no error
  drop) is met on this evidence.
- **Appraisal.** No harm and no forced cheer in either arm; on the lean path the setback replies read somewhat warmer and
  steadier with appraisal, and on the agent path good news linked more often to the tracked goal. These are 1–2 samples
  per cell, read by me rather than blind-rated by the owner, so the E-4 pass bar (≥60% blind wins) is not shown.

**Live-mode recommendations (owner decision).**
- **Metacognition: do not promote.** Keep `metacognition_mode: shadow` to measure how often the signal fires on real
  owner turns (zero cost), and revisit only if real traffic shows invented personal facts. If it is ever revisited, the
  control must change first: no fixed note text on the lean path (it gets echoed), and phrasing that does not dictate the
  opener.
- **Appraisal: keep shadow; promotion candidate.** Promote only after a small blind owner rating of the existing paired
  replies (`blind.py`; no new model calls) shows a preference, or after real-traffic shadow logs show the signal firing
  sensibly. If promoted, the goal line should not expose internal labels (one agent reply quoted "Application 12").



**E-4 blind owner rating (2026-11-09).** The 8 existing reply pairs were rated, one per scenario: 4 fast-path pairs and
4 full-agent pairs. They were reused as generated, with no new model calls. Pair order and A/B side were randomised and
the key was held separately until all 8 verdicts were in. Choices: A, B, Tie, Both bad. The owner first checked that
"Sam" is defined in the synthetic profile; it is, so it is not an invented detail.

| Pair | Scenario | Path | Winner | Appraisal changed the input? | Owner's reason (summary) |
| --- | --- | --- | --- | --- | --- |
| 1 | didn't get the job at Acme | agent | baseline | yes (difficulty line, goal line) | — |
| 2 | studying for the CKA, wish me luck | agent | **appraisal** | yes (goal line) | — |
| 3 | rejected by Acme, sarcastic | lean | baseline | yes (goal line) | — |
| 4 | bombed the interview 😂 | lean | baseline | yes (mixed line) | — |
| 5 | failed the CKA mock | lean | **appraisal** | yes (mixed line, goal line) | the other reply over-analysed Sam and invented a past struggle ("again") |
| 6 | conference talk rejected | agent | baseline | **no** (same lines, no goal): sampling noise | cheekier, no over-analysis |
| 7 | got an interview at Acme | lean | **appraisal** | yes (goal line) | connects to Sam's career goals and offers prep |
| 8 | passed the CKA | agent | **appraisal**, narrowly | yes (goal line) | both excellent; a Tie would be reasonable |

**Counts:** appraisal 4, baseline 4, ties 0, both bad 0, out of 8 (50%).

**Against the E-4 criteria (R&D plan 10):** pass needs ≥60% wins with no rise in over-inference. **Not met.** The
overall result also meets the "no difference" kill criterion.

**What the split suggests (directional, not a decision basis):**
- On setbacks, the owner preferred the baseline 4 of 5 (one of those, pair 6, was noise). Mapping a setback onto the
  warmer `difficulty` / `mixed` line was not preferred over Lilith's own cheeky handling.
- On good news and neutral turns, appraisal won 3 of 3, and pair 7's stated reason was the goal connection. The
  goal-context line (G-WIDEN) may be useful on its own, but 3 pairs is too few to act on.

**Limitations:** 8 pairs, 1 sample each; one rater; two reply paths mixed; synthetic scenarios; pair 6 carries no
appraisal signal.

**Goal-label leak fixed (code only, in shadow).** The goal line no longer passes the stored goal title through.
`goal_topic()` turns it into a plain topic ("Follow up on application 12 - Senior Data Engineer at Acme" becomes
"their application for Senior Data Engineer at Acme"). It removes ids, numbers, tracking labels and the lifecycle state,
and the note tells the model never to quote it or mention ids. Tests cover this. It ships with the next router deploy;
nothing changes on PROD meanwhile, because appraisal is in shadow and renders nothing.

**Decisions:**
- **Appraisal stays in shadow.** It is not promoted, and it is not enabled automatically.
- If it is revisited, the candidate is the goal-context line alone, re-tested blind on good-news and neutral turns. The
  setback line mapping is dropped.
- **The E-5 recall-gap gate stays in shadow** (never promoted).

## 3o. P-4 episodic learning and consolidation: what can start on existing mechanisms (2026-11-09, planning)

Owner GO 2026-11-09. References: R&D plan [06 §3](../research/cognitive-rd-plan-2026-11/06-metacognition-memory.md)
(C-1..C-6), [07 §1](../research/cognitive-rd-plan-2026-11/07-goals-initiative-learning.md) (commitments),
[10](../research/cognitive-rd-plan-2026-11/10-experiments.md) (E-7, E-8). Rules: one Lilith and one memory authority;
no new memory database or infrastructure unless the existing design cannot support the behaviour; persistent-state
changes go to an isolated or DEV environment first; read-only or shadow cognition may go directly to PROD.

**What already exists (inspected).**

| Mechanism | What it does today | P-4 use |
| --- | --- | --- |
| Nightly learning review (`hermes_scripts/owner_memory_review.py`, Hermes cron) | Reads 26 h of owner conversation (console, owner Telegram DM, verified Discord DM) plus the remembered, pending and rejected lists, and proposes memories | **The C-2 consolidation host.** It already proposes only through the owner-approval path |
| Owner approval, LILITH-OS-first (#340) | Approved memory goes to the World Model before the USER.md / MEMORY.md projections | The only way anything learned becomes durable |
| L18 learning events (#341) | PROPOSED / REJECTED / APPROVED / IMPORTED / SUPERSEDED / RETRACTED, append-only, idempotent | Provenance; the approval-fatigue metric (proposed vs approved, rejected or ignored) |
| World Model owner memory (#339) | Approved beliefs with evidence and supersession | Durable facts, typed preferences and boundaries, and approved autobiographical facts ("passed the CKA on …") |
| Goals store (Slice 8) | Goals with lifecycle state and `updatedAt`; `GET /os/goals` is read-only | Verified outcomes: goals that reached COMPLETED / FAILED / BLOCKED |
| Router trace (`decisions.log`, P-1, P-3 shadow) | Per-turn metadata: durable correction routed, appraisal setback / progress / goal-related, recall gap; no text | **The minimum P-3 → P-4 interface:** cues for which moments mattered, already produced in shadow |

**P-3 dependency.** P-4 needs only the trace metadata that P-3 already writes in shadow. That metadata is read offline
as cues for consolidation; it never changes replies. No new cognitive module is needed.

**Gap against the roadmap.** C-1 asks for durable per-turn episode records (a new Core API table inside FORGET scope).
The existing design does **not** hold a durable episode index: transcripts in `state.db` and the bounded trace serve
that role for about a day. This is **deferred**. For now, episodes are assembled at review time from the transcript and
trace, and what deserves to last becomes an **approved owner memory** (a dated event fact), which keeps one memory
authority. A durable episode store is reconsidered only if E-8 ("when / what happened") shows the approved-fact route is
insufficient. It would need a privacy and FORGET review first.

**Focused tasks, in order.**
1. **P4-1 Consolidation context v2** (C-2 first slice; read-only; proposal-only). Status: **installed on PROD
   2026-11-09 05:12Z** (owner GO). Merged in #389 (`11b273c`).
   - **Install:** `~/.hermes/scripts/owner_memory_review.py`, sha256 `e07ffedf5334…`, outside the deploy pipeline
     through `p3tx/deployer/review_install_p41.py` (hash-pinned to main). Backup
     `/var/backups/lilith-review/20261109T051229Z`.
   - **Dry run before install** (counts only, nothing written): 34 owner sessions, 11 owner lines in the window, 1 moment
     tagged, 0 goal outcomes.
   - **Post-install check** (counts only): owner sessions are 28 console, 5 Telegram DM and 1 verified Discord DM; the
     other Discord session is excluded. 22 lines in the window (6 from the Discord DM). The guidance and outcomes
     sections are present; 1 owner line tagged (the P-2 test correction).
   - **Rollback:** `review_install_p41.py rollback 20261109T051229Z`.
   - **Migration note:** the script is outside the pipeline; check its hash against main after the switch (as for the
     earlier install).
   - **Next:** watch the next nightly review's proposals (typed wording; no fictional facts; at most 3). The nightly review
   context gains:
   - wording guidance: typed `Preference/Boundary (scope):` (closes P-2 open item 3); dated event facts for
     achievements and setbacks; at most 3 proposals per night;
   - a fictional-scenario rule: test or fictional scenarios are never proposed as real facts; a clarification may
     become a boundary;
   - *notable moments*: times of owner turns where the trace saw a durable correction, a reported setback or progress,
     or a tracked goal (kinds only);
   - *goal changes*: tracked goals that changed state in the window (a verified outcome is a fact, not a feeling).

   Nothing new is stored; proposals still need owner approval. Installation is outside the pipeline, through the
   existing install tool with backup and rollback, after a counts-only dry run on PROD and owner GO.
2. **P4-2 Approval-fatigue metric** (C-2 gate; read-only). Tool: `scripts/cognitive_eval/approval_fatigue.py` (counts only; proposals grouped by id across L18 PROPOSED / APPROVED / REJECTED plus pending files; ignored = pending over 7 days or gone undecided). Merged in #391.
   - **Baseline on PROD, 2026-11-09** (read-only, counts only): 7 proposals since the L18 ledger began, all in
     2026-W45: 5 approved, 2 rejected, 0 ignored, 0 pending. Fatigue rate 0.286, so the gate is **OK** (tighten
     above 0.5).
   - **Limitation:** every proposal reports source `unknown`. The L18 events do not say whether a proposal came from
     chat or from the nightly review, so the two cannot yet be compared.
   - **Next reading:** after a week of the P4-1 review context, to see whether the guidance changes the
     approve / reject mix. Proposed vs approved / rejected / ignored per week from L18
   events plus pending files, added to the trace summary. Kill: >50% rejected or ignored, then tighten.
3. **P4-3 Reappraisal through supersession** (C-4). *Deferred (owner 2026-11-09):* checked only when a genuine preference or memory change happens; no memories are invented for testing. The supersession machinery already exists. The replace / supersede path exists (SUPERSEDED events). Verify it
   once live (also P-2 open item 1). The review proposes a replacement when a new statement contradicts a remembered
   one, keeping both lineages.
4. **P4-4 Commitments** (07 §1, E-7). Design and first slice: §3p. Explicit promises ("remind me…", "I'll check on…") as typed goals. This is a
   persistent change, so DEV first. Design before code.
5. **P4-5 Outcome reinforcement** (C-3). Verified goal outcomes adjust priority, not truth. Needs goal writes, so DEV
   first, after P4-4.
6. **Deferred:** the durable episode store (C-1), autobiographical canonical families (C-5) and the Slice 15A worker
   restart (C-6; needs OAuth, so after the migration).

**Measures.** E-7 (commitments), E-8 (episodic recall without fabrication); approval fatigue (<50% rejected or ignored).

## 3p. P4-4 Commitments: design and first slice (2026-11-09; installed on PROD; E-7 functional test PASS)

Owner GO 2026-11-09: cognitive coordination and long-term agent behaviour, **not** a reminders app. One Lilith, one
authoritative state, no new commitments database.

**Inspected first (read-only):**
- **Goals store (Slice 8).** Free `type`, `deadline`, `target`, parent and linked tasks, sources including `SCHEDULED`,
  a validated FSM (activate / block / unblock / suspend / resume / complete / fail / cancel / reopen) with a `reason`
  in the goal trace, idempotent `operationId`, evidence gates on completion, Executive focus, and the Goals lane
  grounding goal-status questions.
- **Task store (Slice 3).** Durable tasks; a goal can link them.
- **Planning, Motivation.** Proposal-only and turn-only. No persistence of promises.
- **L18.** The memory-learning stream, not commitments.
- **Scheduling (the important finding).** The full agent already has Hermes' **`cronjob` tool** enabled on the console,
  Telegram and Discord. It creates real one-time or recurring jobs that Hermes' scheduler fires and delivers back to
  the originating chat.
  - Each run is recorded in `cron/executions.db` (`completed` / `failed`, `finished_at`).
  - **A one-time job is deleted from `jobs.json` right after its run**, so its disappearance is not a cancellation.
  - "remind / schedule / timer" messages already skip the fast path and go to the agent (`social_lean._ACTION_RE`).
  - PROD has only the 2 memory-review jobs today; no reminder has ever been scheduled.
  - systemd timers (morning brief, meeting prep, Gmail and career watchers) are separate system automations, not
    commitments.

**The gap is cognitive, not mechanical.** A scheduled promise lives only in Hermes' job file, invisible to LILITH OS's
Goals, the Executive focus and the nightly review. A missed one goes unnoticed. And nothing stops Lilith from saying
"I'll check on you tomorrow" with no scheduler behind it.

**What counts as what.**

| Kind | Example | Handling |
| --- | --- | --- |
| Casual statement | "I should really clean my room" | nothing |
| Owner intention | "I'm applying to Acme next week" | not a commitment. The nightly review may propose a dated fact; "track this as a goal" uses the existing Goals lane |
| Scheduled reminder (owner request) | "remind me at 6 to call mum" | the agent's `cronjob` tool. **Authorization:** the owner's explicit request on a verified owner channel, delivered only back to that chat |
| Actionable follow-up | "check the release notes tomorrow and tell me" | the same tool, with an agent run at fire time, in Lilith's normal voice and context (one identity) |
| Lilith's own promise | "I'll check in on you tomorrow" | a commitment **only if** a scheduler accepted it. Otherwise it is an unbacked promise (guard below) |
| An action beyond messaging the owner | "email Bob tomorrow" | out of scope. The existing approval and policy path applies; a reminder to the owner is all this covers |

**Rules.**
1. **No claim without a scheduler.** Lilith may say a reminder or follow-up is scheduled only when the `cronjob` tool
   returned an accepted job in that turn.
2. **LILITH OS is the authoritative record.** Each owner-channel scheduler job becomes a typed goal: `commitment.once`
   or `commitment.routine`, source `SCHEDULED`, target `{type: hermes.cron, id: <job>}`, deadline = the scheduler's
   own fire time (never invented). Hermes stays the executor.
3. **Progress and outcomes come from evidence only.**
   - The scheduler's run record `completed` makes the goal COMPLETED ("honoured").
   - `failed` makes it FAILED.
   - Due more than 30 minutes ago and not run makes it **BLOCKED ("missed")**; a later run resolves it.
   - Paused or resumed makes it SUSPENDED or ACTIVE.
   - Gone from the job file with no run record makes it CANCELLED.
4. **Missed commitments are noticed.** They are visible to the Goals lane (goal-status answers), the Executive focus and
   the nightly review (P4-1 lists goals that became blocked, failed or completed).
5. **Learning from outcomes.** Outcomes become the E-7 measure (honoured or acknowledged vs missed) and, later, priority
   evidence (P4-5). Proposals to remember anything still go through owner approval.

**First slice (this PR): the commitment sync.** `deploy/prod/hermes_scripts/commitment_sync.py` is a silent
deterministic script, run every few minutes as a no-agent Hermes cron job (the same pattern as
`owner_memory_snapshot.py`):
- It mirrors owner-channel agent jobs into goals and applies the evidence rules above. It uses the router's owner rule;
  system and script jobs and non-owner origins are skipped.
- It never sends, schedules or deletes anything. Its only writes are the Goals API (loopback, controlled create and
  transitions with reasons) and its own state file `~/.hermes/commitments/sync.json`. No job prompt text is copied; the
  goal title is the job's short name.
- **Tests:** 7 unit tests (`deploy/prod/tests/test_commitment_sync.py`): honoured after auto-delete; missed then
  resolved; failed; cancelled only when gone without a run; pause / resume / routine; owner channels and agent jobs
  only; idempotent; one refused transition does not stop the pass.
  Plus 1 integration test against the **real** Goals API in-process (`services/core-api/tests/test_commitment_goals.py`):
  create, activate, block (missed), unblock, complete, idempotent.
- **No Core API change.** Generic goal types have no completion gate, and the sync supplies the evidence as the
  transition reason.

**DEV test, 2026-11-09: PASS** (`lilith-dev-01`; `p3tx/deployer/p44_dev_test.py`). The PR's script ran against
DEV's **real Goals API and database**, with synthetic scheduler files in a throwaway Hermes home: no real job was
created and nothing was delivered.

| Synthetic job | Path | Final |
| --- | --- | --- |
| overdue, never run | created → BLOCKED ("missed") → run record completed → unblock → COMPLETED (revision 4) | COMPLETED |
| run failed | created → ACTIVE → FAILED | FAILED |
| removed before it ran | created → ACTIVE → CANCELLED | CANCELLED |
| non-owner origin | not tracked | — |

- A third pass made no changes (idempotent).
- All goals are `commitment.once`, source `SCHEDULED`, with the scheduler deadline and a `hermes.cron` target.
- DEV's real `cron/executions.db` has the same columns the sync reads. DEV has no live jobs to compare field names
  with; they are known from PROD.
- Three terminal `TEST_ONLY P4-4 DEV …` goals remain on DEV as history.

**Owner review of #393 (2026-11-09): five reliability issues, fixed before any PROD install.**

| # | Issue | Fix |
| --- | --- | --- |
| 1 | `jobs.json` missing, unreadable or invalid read as "no jobs", which could cancel valid commitments | The pass **aborts and writes nothing**. Only a `jobs.json` that parses into a job list counts as a verified (possibly empty) scheduler |
| 2 | Unreadable `executions.db` read as "no runs", so a deleted one-time job looked cancelled | Missing, unreadable or corrupt evidence, a run still in progress, a status `unknown`, or a job gone **after** its due time with no run record: the commitment is **held** unchanged and reported once. CANCELLED only when the job vanished **before** its due time and the readable record shows no run |
| 3 | A corrupt `sync.json` was silently replaced, losing the job-to-goal mapping | Unreadable or malformed state **aborts, and the file is left untouched**. A missing state is **rebuilt from the Goals API** (the authoritative record) before anything is created: no duplicate goals. Transitions are keyed by the goal's revision, so they stay correct after a rebuild |
| 4 | One-time jobs created and executed between two polls are never seen | Documented as a coverage limit, and made visible: each pass records `unattributed_runs_24h` (scheduler runs that belong to no tracked or present job). Install cadence is every **minute**, not 5 |
| 5 | A completed run was read as a delivered reminder | COMPLETED now means the scheduled run completed, and its reason says "delivery to the chat not verified" (Hermes deletes a one-time job, and its delivery error, after the run). A delivery error still visible on the job is FAILED |

- **Tests:** 16 unit tests, 9 of them regression cases for exactly these failures, plus the integration test against
  the real Goals API.
- **DEV re-run** (fixed branch, `lilith-dev-01`, real DEV Goals DB): the same lifecycle results; a corrupt `jobs.json`
  **aborted with the state byte-for-byte unchanged**; with no state file, the mapping was rebuilt from DEV's Goals API
  (it found the 3 earlier test goals) without creating duplicates.

**PROD install, 2026-11-09 06:39Z** (owner GO after the fixes).
- `~/.hermes/scripts/commitment_sync.py` (sha256 `472fc2259cd3…`, main `8a5bdcd`); backup
  `/var/backups/lilith-commitments/20261109T063931Z`.
- Hermes cron job `5365cfb456d4`: `* * * * *`, `--no-agent --deliver local`, the same pattern as the snapshot job (no
  model call; output kept locally).
- The first pass rebuilt an empty mapping; later runs were `ok`.
- **Tool:** `p3tx/deployer/commitment_install.py install | status | rollback <ts>`. Rollback removes the job and the
  script; goals stay as history.

**E-7 functional test: a real owner reminder, 2026-11-09 (Telegram owner DM; metadata only).** The owner asked for a
water reminder in 10 minutes. Both messages at 12:28 local (Lilith's confirmation and the cronjob tool's response) were
the **creation**, not the reminder. The scheduler's own records show the actual run 10 minutes later:

| Step | UTC (local +5:30) | Evidence |
| --- | --- | --- |
| Job created from the owner Telegram DM | 06:58:18 | `jobs.json`: `schedule.kind once`, `repeat 1`, `deliver origin`, origin platform telegram |
| Intended fire time | **07:08:18** | the job's `next_run_at`; used as the goal's deadline |
| Commitment goal created and activated | 06:58:50 | next sync tick: `commitment.once`, `SCHEDULED`, channel `telegram_owner_dm`; trace "accepted by the scheduler" |
| **Scheduled execution** | claimed **07:08:50**, finished **07:08:55** | `cron/executions.db`: `completed`, no error; output file at 07:08:54 |
| Goal completed | 07:09:50 | trace: "the scheduled run completed at 2026-11-09T07:08:55Z; delivery to the chat not verified" |

- **Execution vs delivery.** Execution is verified: it fired 32 s after its due time, within the scheduler's tick.
  For delivery, the job record still exists after the run with `last_status ok` and **no delivery error recorded**
  (`deliver origin`). That is the scheduler's evidence of an error-free hand-off, **not proof that the owner received
  it**. Receipt of the 12:38 local message is the owner's to confirm.
- **Correction.** Hermes did **not** delete this one-time job after its run. It remains with `state completed` and
  `repeat 1/1`. The sync handles both (deleted or kept). For a kept job with `last_status ok` and no delivery error, the
  reason now says exactly that: "the scheduler recorded no delivery error (receipt by the owner not confirmed)". This
  ships with the next script install.
- **Result: PASS for the commitment lifecycle** (created → active → scheduled execution → completed, with no
  unattributed runs). Delivery: no error recorded; receipt not independently verified.

**P4-4b Unbacked-promise check (shadow).** New `lilith_router/promise_guard.py`; `promise_guard_mode: shadow`. At turn
end, the turn record gains four booleans:
- `promise`: the reply promises Lilith's own future action, e.g. "I'll remind you", "I'll check in tomorrow";
- `scheduling_claim`: the reply says something is scheduled, e.g. "I've set a reminder", "your reminder is set";
- `scheduled`: in the same turn, a `cronjob` create call returned without error;
- `unbacked_promise`: a promise or claim with no such job.

It never changes a reply, makes no model call and logs no text. A promise counts as backed only by an accepted create
call in that turn. 4 tests. Rollback: `off`. Any control (for example routing a promising turn to schedule, or
rewording) is chosen only from these counts.

**Next.**
1. Router deploy (shadow only) and reinstall of the sync script with the precise delivery wording.
2. Read `unbacked_promise` counts after normal use.
3. **P4-5 outcome learning:** below.


2. **PROD:** with owner GO, after DEV passes.
3. **Unbacked-promise guard (shadow):** at turn end, flag a reply that promises a future action ("I'll remind you",
   "I'll check in tomorrow") when no `cronjob` create happened in that turn. Count first; choose a control only from
   evidence.
4. **E-7 reading:** honoured / missed / failed counts from `commitment.*` goals.

**Rollback:** disable or remove the sync cron job. Goals already created stay as accurate history and can be cancelled
through the Goals API. Delete `~/.hermes/commitments/sync.json` to start fresh.

## 3q. P4-5 Outcome learning: plan (2026-11-09)

Roadmap C-3: verified outcomes adjust *priority and attention*, not truth. Built on what exists: commitment and goal
outcomes from the Goals store (P4-4), the nightly review (P4-1), owner approval, and the Executive focus.

1. **P4-5a E-7 reading** (read-only). Tool: `scripts/cognitive_eval/commitment_outcomes.py` (counts only; goal outcomes from the goal trace; delivery evidence from the sync's own reasons; promise flags from the turn trace). A counts-only reader over `commitment.*` goals: kept (COMPLETED), failed,
   missed (BLOCKED, or terminal after a block), cancelled, held. Per week, with the sync's `unattributed_runs_24h` and
   the promise check's `unbacked_promise` rate. E-7 bar: ≥ 90% kept or acknowledged, 0 duplicates.
2. **P4-5b Commitment outcomes in the nightly review.** The review lists them separately from life goals: "commitments
   Lilith kept / missed". A missed commitment is something to acknowledge and own in conversation; a routine reminder
   that was kept is not a memory to propose. Read-only change to `owner_memory_review.py`; installed through the
   existing review installer.
3. **P4-5c Attention from outcomes.** A missed commitment raises its own visibility through the Goals lane, so it is
   surfaced and owned rather than silently dropped. This first uses the existing goal-status grounding (read-only).
   A priority change is a goal write, so DEV first, and only if the Goals FSM has a typed operation for it (no
   generic set).
4. **Not now:** changing beliefs or "truth" from outcomes; any affect or mood from outcomes (AP-35); self-directed
   follow-ups without owner request (initiative is P-5).

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
