# LILITH OS — UI/UX evolution proposal

**Status: PROPOSED.** An independent audit of the web application and a set of
recommendations. Nothing here has been implemented, and nothing here authorises
a redesign. Date of audit: 2026-11-16, at `446acdc` plus the Cognitive Atlas
prototype (PR #440).

## How this was done

- **Seen running** (dev server, Chromium preview, 1500×900 and 375×812): every
  route — `/`, `/career`, `/memory`, `/memory/atlas` (Brain and Timeline),
  `/automations`, `/meetings`, `/system`, `/world`.
- **Read in code**: the shell, design tokens, every page and its data layer.
- **Important limit**: the backend was unreachable during the audit. Every
  workspace page was therefore seen in its demo or unavailable state, never
  live. Judgements about live behaviour come from code, not observation.
- Not measured: frame rate on real hardware, bundle size, load time of the
  avatar, behaviour in Safari or Firefox.

---

## 1. The short version

LILITH OS currently contains two different products.

**The first** is the Command Center and the Cognitive Atlas: one subject fills
the page (the avatar, the brain), chrome is minimal, and the interface feels
like a place. This is where the ambition is visible.

**The second** is Career, Automations, Meetings and the Memory Archive: a
well-built but conventional dashboard template — a header, five metric tiles, a
tabbed list, a right rail of "insights" cards. Competently executed, and
exactly the ordinary SaaS shape the product says it is not.

The way forward is not more glass or more animation. It is three things:

1. **Make Lilith present everywhere.** Today she exists on one page. The
   navigation file says she is "present everywhere through the global command
   bar", but the command input lives only on Home, the top-bar search is a
   disabled placeholder, and the avatar unmounts when you leave. On six of
   seven pages an AI companion OS has no AI in it.
2. **Make the interface tell the truth, the same way everywhere.** The product's
   best idea is provenance — "why Lilith knows this". But the pages disagree
   about what to do when they have nothing real to show, and several controls
   claim things that are not so.
3. **Give each workspace one subject**, as Home and the Atlas have, instead of
   one template.

My main disagreement with the brief: the gap between LILITH OS and a
"JARVIS-level" interface is not visual. It is that very little on screen is
live and real. Visual ambition should follow data authority, not lead it. The
Atlas is the clearest case — it is the most impressive thing in the app and it
is entirely synthetic. Its value multiplies only when real, authorised memory
events drive it.

---

## 2. Page-by-page critique

### Command Center (`/`)

**What it is.** The Hsin avatar as hero, a greeting, a command input with four
suggestion chips, and two small cards (Today, Next) fed by the meetings
service.

**What works.** This is the best-conceived page. The avatar is the interface,
chrome is restrained, and the page has an identity no dashboard has. Keep the
composition.

**What is wrong.**

- "Presence online" is a static string. It was displayed directly above
  "Backend unreachable".
- The Idle / Listening / Thinking / Speaking chips are manual overrides of the
  presence state. They look like status and are in fact debug controls.
- Three of the four suggestion chips promise things that do not exist. Only
  "System health" maps to a real intent; "Summarise inbox" and "Compare AWS
  cost" fall through to plain chat unless a demo flag is set.
- The conversation — the core interaction of a companion — gets a strip at most
  240px tall under the avatar.
- Today and Next have a pointer cursor and hover lift but no click handler.
  "Prep with Lilith" is always disabled.
- With the meetings service down, Home is an avatar and two "unavailable"
  cards. It has nothing else to say.
- Six home cards (`activity`, `automations`, `brief`, `focus`, `memory`,
  `next-event`) are imported by nothing.
- The avatar model is about 116 MB on disk and re-initialises every time you
  return to Home. How it is compressed and cached in production was not
  verified.

**Direction.** Home should be the briefing: what changed since you were last
here, what Lilith is doing now, and what needs you (approvals, conflicts,
deadlines). The conversation should be able to expand into the page rather than
live in a strip.

### Career (`/career`)

**What it is.** Header, five metric tiles, a pipeline stage chart, an
application tracker with filter tabs, an activity timeline, and a right rail of
three cards (insights, next actions, interview prep).

**What works.** The pipeline overview is a good object: stages as a flow,
clickable to filter. Rows are informative.

**What is wrong.**

- The tile row repeats the pipeline directly beneath it (Active, Interviews,
  Offers are the same counts).
- "Add application", and the drawer's "Draft follow-up", "Update stage" and
  "Add note" are disabled. "View all" and "Prep with Lilith" have no handler.
- Rail cards have hover lift and pointer cursor but are not clickable.
- Application rows declare an entrance animation that never runs (no animating
  ancestor).
- In demo mode the page shows named real companies, an offer and a deadline,
  flagged only by a small amber chip.

### Automations (`/automations`)

**What it is.** Same template: five tiles, a grid of unit cards with status and
run-history sparklines, an execution timeline, a rail with a fleet ring and
insights.

**What works.** Unit cards are dense and legible; the run-history sparkline is
a good, honest micro-visualisation.

**What is wrong.**

- The subtitle reads "…and services — live." beside a "Demo data · backend
  offline" chip.
- The tiles (Health, Running, Active, Waiting, Failed) duplicate the fleet ring
  and the filter-tab counts.
- "Create automation", "Run now", "Pause/Resume", "Edit workflow" are all
  disabled.
- "Lilith insights" is the same component as Career's, copied.

### Meetings (`/meetings`)

**What it is.** Same template, but with a real hero (Next meeting), a schedule
with a "now" marker, and a meeting-intelligence panel with Lilith's prep brief.

**What works.** The strongest of the workspace pages. The next-meeting hero and
the prep brief are genuinely useful, and every control on the page is real.

**What is wrong.** Five tiles again, mostly restating the hero and schedule.
The schedule's "now" marker does not tick. The brief sits a full screen below
the meeting it belongs to.

### Memory — Archive (`/memory`)

**What it is.** Header, five tiles, search, a "memory model" badge row, the
Knowledge Constellation, a grid of memory shards, and a rail (recently learned,
pinned, relationships). 3.3 screens tall; 36 glass elements.

**What works.** The shard card is the best component in the app: category,
fact-versus-inference, entities, provenance and confidence in one small object.
The detail drawer's "Why Lilith knows this" is the product's signature idea.

**What is wrong.**

- The constellation shows one number per category. The category filter chips
  directly beneath it show the same numbers and drive the same filter state.
  It costs half a screen to say what a row of chips already says.
- The "memory model" row (Episodic · planned, Semantic · planned…) is roadmap
  status, not user information.
- The header tiles restate counts that the filter and rail also show.
- Search is page-local keyword matching, sitting under a disabled global search
  that promises "Search, recall, or ask Lilith…".

**On retiring the constellation: yes, but not for the reason given.** The
Atlas does not replace it today, because the Atlas shows synthetic data and the
Archive shows real data. The constellation should go because it is redundant
*within the Archive*. See P0-6 and P1-3.

### Memory — Brain and Timeline (`/memory/atlas`)

Reviewed separately in `cognitive-atlas-prototype.md`. For this audit: it is the
visual high-water mark and should set the direction for hero subjects elsewhere.
Its weakness is structural, not visual — it is synthetic, and it uses a domain
set (it has Relationships, no Work) that differs from the real memory
categories.

### System (`/system`)

**What it is.** Six static cards: runtime, integrations, privacy and
permissions, environment, performance, advanced diagnostics. No data fetching.

**What is wrong.** It is a page of statements, not a control surface. Values
such as "Avatar renderer — Enabled" are hard-coded. Internal vocabulary leaks
into the UI ("UI baseline: Home V2 approved", "Module-owned"). "Manage" is
disabled; each integration row says only "See module". The real diagnostics —
the endpoint-by-endpoint connection status — live elsewhere, in a chip on other
pages.

### World Model (`/world`)

An orphan: implemented, reachable only by URL, absent from navigation. The top
bar falls back to the title "Lilith OS". The eyebrow exposes an internal label,
"Slice 7 · World Model". Its unavailable state is, however, the most honest in
the app: it refuses to show anything it cannot verify, and says so.

### Settings

Does not exist. The sidebar gear is a disabled button.

### Shell and navigation

- The sidebar rail and its sliding active pill are good and should stay.
- Four shell controls are permanently disabled: Search, Apps, Notifications,
  Settings.
- The browser title is identical on every route.
- There is no mobile navigation: at 375px the 88px rail remains and leaves
  about 255px for content.
- There is no route-level loading, error or not-found handling.

---

## 3. Redundancy register

| Element | Where | Verdict |
| --- | --- | --- |
| Knowledge Constellation | Memory Archive | Remove. Duplicates the category filter beneath it. |
| "Memory model" badge row | Memory Archive | Remove from the page; it is roadmap status. |
| Five-tile metric rows | Career, Automations, Meetings, Memory | Remove or cut to what the page does not already show. About 20 tiles, most of them repeats. |
| "Lilith insights" panels | Career, Automations (same component, copied) | Consolidate into one shared component and one visual treatment. |
| Activity / execution timelines | Career, Automations (duplicated) | One shared component. |
| Presence state chips | Home | Remove from the user-facing UI; keep behind the debug flag. |
| "Presence online" label | Home | Replace with real state or remove. |
| Suggestion chips that are not real | Home | Show only chips backed by a real intent. |
| Apps and Notifications buttons | Top bar | Remove until they exist. |
| Settings gear | Sidebar | Remove; fold settings into System. |
| Disabled global search | Top bar | Replace with the real command line (P1-1). |
| Six unused home cards, `ModuleStub`, `Bars`, `fadeIn`, unused keyframes | Code | Delete. |
| World Model page | Unlinked route | Keep the capability; give it a home under Memory. |
| Two detail-drawer implementations | Memory vs shared | Use the shared one. |

Nothing above removes data, models, relationships, search or provenance. Every
item is presentation.

---

## 4. Proposed information architecture

```
Shell (always present)
├─ Command line        — ask, command, recall; works from every page
├─ Presence            — small, truthful indicator of what Lilith is doing
└─ Connection state    — one honest status, one place for diagnostics

Command                — the briefing: what changed, what is running, what needs you
Mind
├─ Brain               — the Cognitive Atlas (immersive)
├─ Archive             — the evidence explorer (precise)
├─ Timeline            — how memory grew
└─ Beliefs             — the World Model (currently orphaned at /world)
Work
├─ Career
└─ Meetings
Operations
├─ Automations         — what Lilith does on her own
└─ System              — health, integrations, permissions, settings
```

Changes from today: Lilith moves from one page into the shell; World Model gets
a home; Settings stops being a dead icon and becomes part of System; Apps and
Notifications leave until real. The rail keeps six destinations.

The four Mind lenses should share one selection. Choosing a memory in the
Archive offers "show in brain"; choosing a node in the Brain offers "open in
archive". That is only meaningful once the Atlas reads real memory.

---

## 5. Design system assessment

**The identity is right and should stay frozen**: the wallpaper, the wine and
rose, cyan for data, gold used rarely. Nothing below changes it.

**What is not yet a system:**

- **Type.** There is no scale. Seventeen distinct sizes are in use, and about
  286 usages are between 8px and 11px. The faint ink colour is paired with
  8–10px text 92 times, at roughly 4.6:1 on the base colour and lower over the
  wallpaper. Too much of the interface is at the edge of legibility.
- **Micro-labels.** Uppercase monospace eyebrows are used so widely (127
  `tracking-wider` usages) that they no longer mark anything as special.
- **Colour drift.** "violet" still appears about 170 times as a legacy alias,
  and the stylesheet's own header comment still says violet is the primary.
  Wine is hard-coded as raw `rgba()` in shadows in two slightly different
  values.
- **Radius.** The overrides make `rounded-xl` (28px) larger than `rounded-2xl`
  (16px).
- **Motion.** One easing curve is hard-coded 19 times; there are 15 distinct
  durations and five spring configurations outside the shared motion file.
- **Placeholders.** Five different ways of saying "not available yet".

**Glass.** Two separate problems.

*Technical.* In the dev server the `glass`, `glass-panel` and `glass-strong`
utilities render with **no backdrop blur at all** — the declaration is absent
from the served CSS. I confirmed this in the browser. In the compiled
production CSS only the `-webkit-` prefixed declaration survives, which
Chromium and Safari honour; I did not verify the rendered production result,
and as far as I know Firefox honours only the unprefixed form. So the surfaces
described in the stylesheet as translucent blurred glass are, in development,
flat dark gradients — and development and production do not look the same.

*Design.* Glass is used for everything: 44 `GlassCard` usages, 36 glass
elements on the Archive alone. When every element floats, nothing does, and
hierarchy flattens. I would use three surface tiers, each with a job:

1. **Open** — no surface. For the subject of a page: avatar, brain, pipeline,
   the day.
2. **Rows** — hairline-separated content on one shared, quiet scrim. For lists
   and evidence. Not cards inside cards.
3. **Glass** — reserved for things that genuinely float above the page: the
   command line, the dock, drawers, inspectors, menus.

This would roughly halve the number of cards and make the remaining glass mean
something.

---

## 6. Navigation, transitions and motion

**Principle.** Spend the motion budget on *state* — Lilith thinking, a memory
arriving, an automation failing — more than on *navigation*. Page changes should
be fast and quiet; state changes should be expressive.

**Worth doing**

- **One motion vocabulary.** Named durations, one easing, two springs, in the
  shared motion file; an app-wide reduced-motion setting.
- **Quiet route transition.** A 180–220ms cross-fade of the page content with
  the shell held still. React's `<ViewTransition>` is the natural tool; the
  Next docs for this version describe it as needing no configuration. It needs
  a short spike first: the docs say React 19.3 includes it and the project is
  on 19.2.8 (Next's bundled build does export it). Chromium 125+; elsewhere the
  app simply does not animate.
- **Row to detail.** A list row expanding into its drawer as one continuous
  object, rather than a drawer sliding in from nowhere.
- **Entering the mind.** Command to Memory is already a transition: the
  environment dims and the brain assembles. Make the full assembly play once
  per session and a short version after that.
- **Presence that travels.** A small presence mark in the shell that reflects
  real conversation and command state on every page, and that on Home is the
  avatar.

**Worth a spike, not a commitment**

- **State-preserving navigation.** Next can keep recent routes mounted and
  hidden instead of unmounting them, which would stop the brain re-assembling
  and keep scroll positions. It requires two config flags, changes when effects
  run, and it is unknown how the WebGL canvases behave while hidden. A cheaper
  first step is a small shared cache so pages stop refetching on every visit.

**Avoid**

- Particle or 3D transitions between ordinary pages.
- Any transition that blocks input for more than about 250ms.
- Blur-in on card entrance. The current entrance animates `filter: blur` on
  every card; it is expensive and makes text shimmer. Opacity and a few pixels
  of travel are enough.
- Parallax on the wallpaper, and sound.

---

## 7. Beyond dashboards

- **State you can trust.** One presence indicator, driven only by real events:
  idle, listening, thinking, speaking, working, waiting on you. Never a static
  label, never a manual chip.
- **One attention stream.** Today "what needs you" is scattered across insight
  panels, next-action lists, follow-ups and a dead notification bell. One
  stream — approvals, conflicts, deadlines — owned by Home, with each item
  linking to its place.
- **Context that carries.** Any object should be something you can hand to
  Lilith: a meeting, an application, a memory. Selecting one and invoking the
  command line should scope the conversation to it.
- **Explainability as the signature.** "Why Lilith knows this" already exists
  for memories. Extend the same affordance to every claim the interface makes —
  an insight, a brief, a belief — so anything Lilith asserts can be traced to
  its source.
- **The Atlas as an instrument, later.** When retrieval is observable through an
  authorised source, the brain can show which memories were actually used to
  answer a question, as it happens. Until then it must stay labelled as
  simulation.
- **Personality through restraint.** Lilith's character is better expressed in
  wording, timing and what she chooses to surface than in more ornament.

---

## 8. Technical findings

- **No route-level safety net.** There is no `error.tsx`, `loading.tsx` or
  `not-found.tsx`, and the only error boundary wraps the avatar. A render error
  in any page blanks the application.
- **Reduced motion is partial.** The global CSS rule covers CSS animation only.
  Framer Motion animations outside the avatar and the Atlas ignore the setting.
- **Accessibility gaps.** No skip link. Sidebar links carry no `aria-current`.
  The command input has no label. The shared drawer has no focus trap. The
  connection-status popover has no expanded state and no Escape handling. No
  page shows a heading while its skeleton loads.
- **False affordances.** Cards with pointer cursor and hover lift that are not
  clickable, on Home, Career and Automations. Buttons with no handler ("View
  all", "Prep with Lilith").
- **Data.** Four copies of the same 21-line data hook; no cache, so every
  navigation refetches. Backend failure silently becomes demo data.
- **Weight.** The avatar scene is 3,662 lines and its presence wrapper 2,192.
  The wallpaper is a 2.1 MB PNG blurred at runtime across the whole viewport;
  pre-blurring it into a modern format would remove both the bytes and the
  filter.
- **Responsiveness.** The layout switches once, at 1280px. There is no mobile
  shell.
- **Not a problem, noted for completeness.** The auth proxy runs on every
  request including assets. That is a deliberate security boundary and outside
  this audit.

---

## 9. Recommendations

Complexity: **S** = hours to a day, **M** = a few days, **L** = a week or more.

### P0 — consistency and usability

**P0-1. One policy for "nothing real to show".**
Now: Home and World show an honest "unavailable"; Career, Automations, Meetings
and Memory show full demo datasets with a small chip; Automations says "live"
while showing demo data.
Proposal: in production, no demo data — show the unavailable state everywhere.
Keep the demo adapters for development behind an explicit flag, with a banner
that cannot be missed.
Why: the product's credibility rests on never presenting invented content as
Lilith's. The newest feature (the Atlas) already holds a stricter line than the
older pages.
Complexity: S–M. Risk: none. **Now.**

**P0-2. Remove claims that are not true.**
"Presence online", the manual presence chips, the three suggestion chips with no
capability behind them, "— live" in the Automations subtitle, internal labels
("Slice 7", "Home V2 approved", "Module-owned").
Complexity: S. **Now.**

**P0-3. Remove false affordances and dead chrome.**
Take hover lift and pointer cursor off non-clickable cards. Remove or wire the
handler-less buttons. Remove Apps, Notifications and the Settings gear until
they exist. Keep a disabled control only where it explains a deliberate
boundary — the read-only Pin / Edit / Forget note is a good example.
Complexity: S. **Now.**

**P0-4. Fix the glass utilities.**
Find why the backdrop-filter declarations are dropped, and make development and
production render the same surface. Then decide deliberately how much blur the
design wants.
Complexity: S to diagnose. Performance: about 20 blurred layers per page once
it works — measure before keeping all of them. **Now.**

**P0-5. A safety net and the cheap accessibility fixes.**
Add route-level error and not-found handling; an app-wide reduced-motion
setting; a skip link; `aria-current`; a label on the command input; a focus trap
in the drawer; a distinct browser title per route.
Complexity: S–M. **Now.**

**P0-6. Retire the constellation and the memory-model row from the Archive.**
The category filter and counts remain. No data or model is touched.
Complexity: S. **Now.**

**P0-7. Delete dead code.**
Six unused home cards, `ModuleStub`, `Bars`, `fadeIn`, unused keyframes, the
duplicated drawer. Fix the entrance animations that never run, or remove them.
Complexity: S. **Now.**

### P1 — high-impact improvements

**P1-1. A real command line in the shell.**
Now: Lilith can be addressed only on Home; the top-bar search is disabled.
Proposal: the top-bar field becomes the command line — ask, command, recall —
on every page, using the conversation state the shell already holds. The
existing Ctrl+Space shortcut focuses it. Responses open in a panel that does not
navigate away.
Why: this single change is the difference between a set of dashboards and an
operating system with a mind in it.
Complexity: M. Accessibility: needs full keyboard handling and a live region.
**Next, before any visual work.**

**P1-2. Truthful presence in the shell.**
A small mark reflecting real state on every page; the avatar remains Home's
hero. Complexity: M. **With P1-1.**

**P1-3. Archive as an evidence explorer.**
Search first. A two-pane list and detail instead of a card grid and drawer.
Provenance and confidence as scannable columns. Facets for domain, fact versus
inference, source, confidence and time. The shard card's content is kept; its
container changes from tile to row.
Why: the Brain is for seeing the whole; the Archive should be for finding and
verifying one thing. They should complement, not compete.
Complexity: M. **After P0-6.**

**P1-4. Wire the Atlas to real memory, read-only.**
An adapter from the existing read-only memory data to the Atlas's event seam,
and a decision on the domain mapping. Until then the Atlas should not become
the default Memory view.
Complexity: M. This is a product and authority decision as much as an
engineering one. **Needs your decision first.**

**P1-5. Foundations of the design system.**
A type scale with a floor of 11px for anything meant to be read; a raised or
restricted faint ink; a named motion vocabulary; removal of the legacy violet
names; a corrected radius scale; one "not available" idiom.
Complexity: M, mostly mechanical. Cheap now, expensive in a year. **Next.**

**P1-6. Cut the tile rows and consolidate the rails.**
Remove tiles that repeat what the page shows; one shared insights component and
one shared timeline. Complexity: S–M. **Next.**

**P1-7. Quiet route transition and row-to-detail continuity.**
As described in section 6, after a short spike on `<ViewTransition>`.
Complexity: M. Must respect reduced motion. **After P1-5.**

**P1-8. A mobile shell.**
The rail becomes a bottom bar or a drawer below a breakpoint.
Complexity: M. **Next, if the phone matters to you; otherwise later.**

**P1-9. Home for the World Model and for settings.**
Link Beliefs under Memory; fold settings into System and make System show real
diagnostics. Complexity: S for the links, M for a real System page. **Next.**

### P2 — advanced experiences

**P2-1. One subject per workspace.**
Career's subject is the pipeline; Meetings' is the day as a time ribbon;
Automations' is the fleet as a living system. Each replaces the template with
an open composition, with rows beneath.
Complexity: L per page. **Later, one page at a time, Meetings first.**

**P2-2. Home as the briefing, with an attention stream.**
Complexity: L, and it depends on real sources for each item. **Later.**

**P2-3. Presence that travels and grows.**
The shell presence mark and the Home avatar as one continuous object.
Complexity: L. **Later.**

**P2-4. The Atlas as a live instrument.**
Real recall paths shown as they happen, during a conversation.
Complexity: L, and blocked on an authorised source of retrieval events.
**Later, and only with real events.**

**P2-5. State-preserving navigation.**
Complexity: M to spike, uncertain beyond that. **Spike later.**

**Not at all:** particle transitions between ordinary pages; more ambient
decoration on workspace pages; a notification centre before there is one
attention stream; any additional dependency for animation — Framer Motion, CSS
and the platform's view transitions cover everything proposed here.

---

## 10. Suggested order

1. P0-1 to P0-7 — a short, unglamorous pass that makes the application honest,
   consistent and safe.
2. P1-5 — foundations, so later work is built on a scale rather than on habits.
3. P1-1 and P1-2 — Lilith in the shell.
4. P1-3, then P1-4 once the authority decision is made.
5. P1-6, P1-7, P1-9, and P1-8 if wanted.
6. P2 work, one page at a time.

## 11. What should stay exactly as it is

- The colour identity and the atmospheric wallpaper.
- The avatar as Home's hero, and Home's restraint.
- The sidebar rail and its sliding pill.
- The shard card's content model: fact versus inference, provenance,
  confidence.
- "Why Lilith knows this."
- The honest unavailable states, and the diagnostics behind the connection
  chip.
- The read-only stance on memory, with the explanation shown.
- The Meetings prep brief.
- The Cognitive Atlas.
