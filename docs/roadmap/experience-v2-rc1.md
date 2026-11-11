# LILITH Experience V2: release candidate 1 and rollback plan

Status: **RELEASE CANDIDATE, not merged, not deployed.** Prepared 2026-11-11.
Roadmap reference: #420 (`docs/roadmap/experience-v2-plan.md`).

Boundaries:
- Nothing here is merged or deployed without separate owner authorization.
- PROD/DEV, the Core API, Hermes, canonical memory, authority and model providers are unchanged.
- Timeline stays shadow, and P-5 stays disabled.

## 1. Contents (dependency order)

The branch `integration/xv2-rc1` is `main` at `cda3d85` plus these merges, in this order:

| # | PR | Head | Change |
|---|---|---|---|
| 1 | #419 | `442e77f` | Status capsule shows measured backend state and API round-trip (no hard-coded "Online/48ms") |
| 2 | #421 | `f8e2cf2` | Unbuilt controls (Search, Apps, Notifications, Settings, Mic) natively disabled; fake unread dot removed; account display-only |
| 3 | #422 | `9592d70` | TODAY/NEXT come from the live read-only meetings data or say "unavailable"; no fabricated meetings, scores or countdowns. **Includes the owner-timezone fix** (day boundaries and times in `overview.timezone`, browser fallback) |
| 4 | #423 | `d887137` | Conversation Stop (browser-only, truthful notice), stale-reply safety, Retry without duplicates, elapsed feedback, single live-region announcements |
| 5 | #424 | `9df5fcd` | Owner-facing voice toggle on the single `voiceSettings` store and the existing ElevenLabs path; no history replay; off stops audio and visemes |
| 6 | #425 | `ba18640` | Dev-only Hsin and command-core diagnostics dropped from production; sanitized operational warnings |
| 7 | RC | — | Test runner reconciled; `scan:bundle -- --demo` also checks for fabricated home data |

**Conflicts resolved:** only `scripts/run-core-self-test.mjs`, regenerated from `main` with every test module and the union of build options:
- `jsx`;
- the `createRequire` banner;
- the `next/navigation` and `next/link` stubs.

`command-input.tsx` (#421 Mic and #423 Stop) and `presence-hero.tsx` (#423 Stop and announcer, #424 reply gating, voice settle and toggle) merged automatically. Both were reviewed by hand.

**Diff against `main`:** 37 files, +2,846 / −287. These are frontend, test and docs only:
- no `services/`, `integrations/`, workflow, Core API or Hermes files;
- no new dependencies;
- no new environment variables or credentials.

## 2. Verification of the combined branch

| Check | Result |
|---|---|
| `npm run test:core` (complete combined suite) | **249/249** |
| `tsc --noEmit` | clean |
| `npm run build` | clean |
| `npm run scan:bundle -- --demo` (client bundle) | **PASS**: 0 dev-only diagnostics, 0 fabricated home-data strings. The control build of `main` has **26** (21 + 5). |
| Production-build runtime console during the full flow | No conversation text, no `[core …]` traces, no Hsin dumps. Only browser 503 network lines and two third-party library deprecation warnings. |

**Combined interaction check:** run on the production build (`next start`) at 1440×900, with in-page fake conversation and TTS endpoints that honour `AbortSignal`. Hsin's state was read from `data-presence-activity`.

| Scenario | Observed |
|---|---|
| First load (no backend) | Capsule "Demo data"; TODAY/NEXT "unavailable"; 5 unbuilt controls disabled; voice off; no fabricated content |
| Waiting for a reply | Hsin `thinking` |
| Voice off, reply arrives | Canned speaking beat; **0 TTS calls** |
| Voice turned on | Nothing replayed (0 calls) |
| Voice on, new reply | 1 TTS call; real playback; Hsin `speaking`, then `idle` when the audio ended |
| Stop while waiting | Request aborted; Hsin `idle`; input re-enabled; truthful browser-only notice |
| Late reply from the stopped turn | Not shown, **not spoken** |
| Ask again | No duplicate user bubble; the new answer is spoken once |
| Voice off mid-speech | Audio stopped; Hsin `idle` |
| New message while speaking | Speech interrupted at once; Hsin `thinking` |
| Real network error, then Retry | `role="alert"`; Hsin `idle`; Retry recovered with no duplicate bubble |
| Navigate to Meetings and back | Transcript kept; voice kept; **0 replays** |
| Mobile 375×812 | No page-level horizontal scroll; Stop, voice toggle and cards within the viewport; stop notice wraps |

The individual PRs were also verified separately on desktop and mobile, as recorded in each PR. #423 and #424 were checked together on a local merge, and the combined suite there passed 162/162.

## 3. Known issues (not regressions; not fixed in RC1)

1. **Hsin WebGL context loss in a hidden or background tab.** The GPU context is reclaimed, and Hsin's existing remount logic recovers it. Her visual rendering could not be screenshot while the preview pane was hidden. Her behaviour was verified through `data-presence-activity`, and she rendered in the visible mobile and earlier desktop previews.
2. **Mobile overflow from the avatar layer.** The avatar canvas layer is 434 px, wider than `<main>` (287 px, with the 88 px rail) on a 375 px phone, so `<main>` can scroll sideways. This is pre-existing and untouched by RC1. It belongs to the mobile UI milestone, together with the always-visible rail.
3. **113 MB VRM.** First load is slow on real networks. This is the Hsin optimization milestone.
4. **TTS cancellation is browser-side only.** A provider call the server has already started is not cancelled. Forwarding the abort upstream is a follow-up.
5. **Still static:** the "Presence online" eyebrow and the `user.plan` "Founder" label. Six unused fake home cards remain in `src/components/home/`. These are cleanup items.
6. **Third-party console warnings:** three.js `THREE.Clock` deprecation and three-vrm `VRMLookAtQuaternionProxy`.

## 4. Merge plan (requires separate authorization)

### Blocking consideration: merging to `main` triggers a DEV deployment
`.github/workflows/deploy-dev.yml` ("Deploy LILITH Core API to DEV") runs after every successful `Repository validation` on `main`. Its classifier (`scripts/classify_dev_deployment.py`) exempts only an exact list of control and broker paths, and accepts no directory globs. Run locally on this RC's diff it returns:

```
MODE=DEPLOY_REQUIRED
```

So merging RC1, any of #419 to #425, or #420's docs would make the fixed DEV helper deploy an exact-SHA bundle and restart `lilith-os-api-dev.service`. The Core API code would be unchanged, so it is a same-code redeploy and restart, but it is still a DEV restart. Before merging, the owner chooses one of:

- **(a) Accept the DEV redeploy** as part of the merge authorization (same Core API code; health-checked by the workflow), or
- **(b) First change the classifier** so frontend-only diffs are `CONTROL_ONLY_NO_DEPLOY`. This is a security-sensitive change to a deliberately fail-closed control, so it needs its own reviewed PR and its own authorization. It is not part of this RC.

### Recommended: one merge of the RC
1. The owner authorizes the merge, including choice (a) or (b) above.
2. Re-run CI on the RC PR at its final head. Confirm `main` has not moved, or rebase and re-run the full checklist in §5.
3. Merge **once** with a merge commit, keeping the six PR merges visible.
4. Close #419 and #421 to #425 as *superseded by the RC*. Their reviews and evidence stay linked.
5. Follow the merge-sequencing rule: do not merge anything else until this merge's `main` runs, including the DEV deployment evaluation, have fully succeeded.

**Alternative: sequential individual merges**, in the order #419 → #421 → #422 → #423 → #424 → #425:
- each needs a runner rebase;
- each waits for its `main` runs to finish;
- each triggers its own DEV deployment evaluation.

This allows a per-PR revert, but it costs six DEV redeploys and six rebases.

## 5. Pre-merge and post-merge checklist

Run on the exact merge candidate:
1. `npm ci`
2. `npm run test:core` (expect 249/249, or more if `main` moved)
3. `npx tsc --noEmit`
4. `npm run build`
5. `npm run scan:bundle -- --demo` (expect PASS)
6. Manual smoke on `next start`, desktop and phone:
   - load Home;
   - send a turn and Stop it;
   - Ask again;
   - turn voice on, then send, and the reply is spoken;
   - turn voice off mid-speech;
   - open Meetings and come back;
   - check the console for anything other than known third-party warnings.

## 6. Rollback plan

**What is affected:** only the Next.js frontend, which is not deployed by any pipeline today. The owner runs it locally behind the IAP tunnel. There are no backend, database, memory or authority changes, and no data migrations.

**Browser state introduced:** a new localStorage key, `lilith-os:voice` (`"on"`/`"off"`). Older code ignores it. The existing `lilith-os:messages` and `lilith-os:session-id` formats are unchanged.

**Rollback steps:**
1. **Local frontend (immediate):**
   - check out the pre-merge `main` SHA (recorded at merge time; `cda3d85` today);
   - `npm ci && npm run build && npm start`.

   Optionally remove `lilith-os:voice` from the browser.
2. **Repository:** revert the single RC merge commit with `git revert -m 1 <rc-merge-sha>` in one PR.
   - Run CI on it.
   - The revert's diff also classifies as `DEPLOY_REQUIRED`, so the same DEV-redeploy decision from §4 applies.
3. **Partial rollback:** if only one feature misbehaves (for example voice), revert that PR's files in a follow-up PR rather than the whole RC. Each feature is isolated in its own modules:

   | PR | Files |
   |---|---|
   | #419 | `lib/system/*`, `status-bar.tsx` |
   | #421 | `ui/unavailable.ts`, `top-bar.tsx`, `sidebar-rail.tsx`, the Mic in `command-input.tsx` |
   | #422 | `lib/home/*`, `today-card.tsx`, `next-card.tsx`, `page.tsx` |
   | #423 | `lib/conversation/turn-runner.ts`, `conversation-provider.tsx`, `conversation-view.tsx`, Stop in `command-input.tsx` and `presence-hero.tsx` |
   | #424 | `lib/voice/*`, `voice-toggle.tsx`, `presence-hero.tsx` |
   | #425 | `lib/diagnostics.ts`, guarded console lines |

**Rollback triggers:**
- a test, build or scan failure on `main`;
- Hsin's presence stuck in `speaking`/`thinking`;
- any reply spoken that the owner did not just request;
- duplicate or lost conversation turns;
- any conversation text appearing in the production console.

## 7. Next milestones (after RC1 is merged)
1. **Private web preview under our domain:** Cloudflare Tunnel + Access, plus the app-level Access-JWT check and Origin checks (plan H1–H3 in #420). The DEV-deploy classifier decision in §4 applies to those merges too.
2. **Hsin avatar optimization:** compress the VRM from 113 MB to 20 MB or less, with progressive presence (S1–S2).
3. **Mobile UI:** bottom navigation, the avatar-layer overflow, conversation dock (X1–X2).
