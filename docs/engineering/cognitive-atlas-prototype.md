# Cognitive Atlas — UI prototype

**Status: PROPOSED (front-end prototype).** The Atlas is a visual prototype of a
"living brain" view for the Memory workspace. It runs entirely in the browser on
**synthetic data and simulated activity**. It does not read, write, or imply
anything about LILITH's real memory, and it changes no backend, authority, or
memory-system behaviour.

- Route: `/memory/atlas` (Brain view) and `/memory/atlas?view=timeline` (Timeline view)
- The existing, backend-wired Memory workspace at `/memory` is unchanged apart
  from a `Brain · Archive · Timeline` switch that links to the prototype.

## What it shows

| Behaviour | How it is produced today |
| --- | --- |
| Brain shape | An implicit volume (signed-distance field) sampled into ~29k particles; folds are creases in a noise field. No mesh, no asset. |
| Seven domains | Career, Projects, People, Knowledge, Preferences, Relationships, Personal — each a territory of the brain with its own colour. |
| Memories | 112 invented memories, each a node placed deterministically (hash of its id) inside its domain. |
| Associations | Pathways between memories that share a thread (tag) or sit together in a domain. |
| Learning | A timer "learns" a pooled memory: a node swells in, pathways draw on, the region densifies and an activation front crosses the tissue. |
| Recall | A cue is keyword-matched to a memory, then a spreading-activation walk lights an association chain hop by hop. |
| Growth | The Timeline view rewinds the brain to any point in a fictional 120-day history. |

## Layout: the brain is the interface

There is no stage, card, or frame around the brain, and no permanent panels.

- The WebGL canvas is a transparent, viewport-wide layer (`position: fixed`,
  behind the OS chrome), so the brain blends into the existing LILITH
  environment and its particles can drift behind the top bar and sidebar. A
  soft, borderless pool of shadow behind the brain keeps it legible over the
  wallpaper.
- Because that layer sits behind the page, it takes no pointer input. A
  transparent surface over the page area reports drag, zoom, hover and click to
  the scene (`surface` prop), and the scene is told which part of the viewport
  is free (`insets`) so the brain centres itself there.
- Domains are callouts: a label plus a leader line to the part of the cortex it
  names. Each frame the scene anchors the label to its region on whichever
  hemisphere faces the camera, pushes it clear of the brain's silhouette,
  separates labels that would overlap, and keeps them on the page — so a label
  stays with its region through any rotation. Selecting a label or a memory
  opens a contextual inspector; closing it returns the page to the brain.
- One control dock (bottom left) holds everything else. Always visible: pause /
  resume motion, reset view, domain labels, activity feed, visual settings.
  The overflow menu holds the domain list, the simulation switch, "learn a
  memory now", "replay assembly" and the keyboard reference. Opening a panel
  glides the brain aside. Recent activity otherwise appears as one transient
  line above the dock.
- Keyboard: Space pause / resume, R reset, L labels, A activity, D domains,
  arrows orbit, + / − zoom, Esc steps back. Touch: drag to orbit, pinch to
  zoom, tap to select.
- Visual settings (auto-orbit, pathways, glow, backdrop) and the label toggle
  are remembered per browser in `localStorage` (`lilith-os:atlas-prefs`). That
  is the only thing the Atlas stores, and it holds no memory content.
- Timeline view keeps the brain at nearly full size above a slim strip. Moving
  the marker animates the graph: memories the marker reaches flare and ring,
  their pathways draw on, their region stirs, and the label counts follow.

### Simulated, and labelled as such

Everything that looks like activity is synthetic, and the UI says so wherever
it could be mistaken for the real thing:

- the header carries a "Synthetic data" badge;
- the recall pill is tagged "Simulated", uses a "Trace" action rather than a
  search icon, and explains on focus that it does not search real memory — it
  is deliberately unlike the OS search bar above it;
- the activity feed, the transient activity line, the overflow menu's
  simulation group and the inspector footer each carry the same marking.

### Motion and fallbacks

- **Reduced motion.** The Atlas follows `prefers-reduced-motion` live. When it
  is set: no assembly animation, no sway, drift or idle activity, the
  simulation is held, camera moves are immediate rather than eased, and panel
  transitions are disabled. The dock's motion control shows it as paused and
  lets the viewer opt in.
- **No WebGL.** The same particle layout and memories are drawn once to a 2D
  canvas. Domain labels, inspectors, recall and the timeline still work;
  orbiting and picking a memory directly on the brain do not.
- **Hidden tab.** Rendering and the simulation stop while the page is hidden.

## Structure

```
src/lib/memory/atlas/
  types.ts        AtlasNode / AtlasLink / AtlasEvent — the contract
  regions.ts      the seven domains: colour, lobe, label anchor
  brain-shape.ts  the brain volume, particle sampling, node placement
  store.ts        graph state; apply(event) is the only mutation
  synthetic.ts    SYNTHETIC memories + graph builder
  simulation.ts   SYNTHETIC event source, recall walk, cue matching
  math.ts         seeded RNG, hash, noise

src/components/memory/atlas/
  cognitive-atlas.tsx   interaction state + layout (the orchestrator)
  brain-canvas.tsx      lazy WebGL host, no-WebGL still fallback
  scene/brain-scene.tsx R3F canvas: camera rig, picking, callout layout,
                        event animation
  scene/buffers.ts      growable GPU buffers (nodes, pathways, tracts), hull
  scene/shaders.ts      GLSL for every layer
  atlas-dock.tsx        the control dock, its menus, tooltips, visual settings
  atlas-labels.tsx      domain callouts and the hover card
  region-index.tsx      domain list (optional overlay)
  atlas-inspector.tsx   memory inspector + domain inspector
  cognition-feed.tsx    activity feed, transient activity line, growth log
  recall-console.tsx    simulated-recall pill + association chain
  growth-timeline.tsx   growth strip + marker

src/components/memory/memory-view-switch.tsx   Brain · Archive · Timeline
src/app/memory/atlas/page.tsx                  the route (client-only)
```

## Wiring to real memory later

The prototype was built around one seam so that this is a replacement of the
event source, not a rewrite of the view.

**The seam is `store.apply(event: AtlasEvent)`.** Nothing else changes the
graph. Panels read immutable snapshots; the scene listens to `store.onEvent`
and animates. Neither knows where an event came from.

```ts
type AtlasEvent =
  | { type: "memory.learned";    at; node: AtlasNodeInput; links: AtlasLinkInput[] }
  | { type: "memory.linked";     at; link: AtlasLinkInput }
  | { type: "memory.reinforced"; at; nodeId; confidence? }
  | { type: "memory.recalled";   at; cue; chain: string[] }
```

What a real integration replaces, in order:

1. **Initial graph** — `buildSyntheticGraph(layout)` becomes an adapter from the
   existing read-only `MemoryData` (`src/lib/memory/client.ts`): each
   `MemoryRecord` maps to an `AtlasNode` (`summary → title`, `content → detail`,
   `kind`, `tags`, `provenance`, `confidence`, `importance`, timestamps), and
   `record.related` plus `Relationship` edges map to `AtlasLink`s. Placement is
   already deterministic per id (`placeNode`), so a memory keeps its location
   across sessions.
2. **Domain mapping** — the Atlas has a `relationships` domain and no `work`
   domain, unlike `MemoryCategory`. An adapter needs an explicit rule (for
   example `work → projects`; records whose entities are two or more people →
   `relationships`). This is a product decision, not yet made.
3. **Live events** — `createSimulation(store)` is replaced by a subscriber that
   turns real memory activity into `AtlasEvent`s. No such stream exists in the
   UI contract today; polling the read-only overview's `recentActivity`
   (`learned | updated | reinforced`) and diffing is the smallest first step.
4. **Recall** — `traceAssociations` and `matchCue` are local stand-ins. A real
   recall would emit `memory.recalled` with the chain the memory system actually
   traversed; the scene already animates any chain it is given.

Constraints carried over from the Memory workspace, which a real integration
must keep:

- Live and demo data are never mixed. The Atlas should take the same
  `isDemo` flag as `/memory` and keep the "Synthetic data" badge whenever it is
  not showing live records.
- The view is read-only. There are deliberately no pin / edit / forget controls;
  any write path belongs behind the existing approval flow, not in this view.
- `unknown` kind and `unknown` provenance must be shown as unknown, never
  promoted to fact (the inspector reuses `KindTag` / `ProvenanceBadge`, which
  already do this).

## Known limits of the prototype

- Capacity is fixed at 360 nodes and 1,100 pathways (`scene/brain-scene.tsx`).
  Real memory at larger scale needs level-of-detail: cluster nodes per domain
  and expand on focus.
- Recall matching is keyword search over 112 records; it has no semantics.
- On phone-width screens the OS sidebar leaves the Atlas about 255 px, so
  domain labels drop their counts and sit close to (sometimes over) the brain.

## What has been checked (2026-11-16)

OBSERVED, in a desktop Chromium preview unless noted:

- `next build` succeeds on a clean copy of the branch (tracked files plus this
  prototype); `/memory/atlas` prerenders as a static route. `npm run
  scan:bundle` passes and `npm run test:core` passes 531/531.
- The production server (`next start` on that build) runs the Atlas under the
  production CSP with no violations: it assembles, animates at 60 fps and
  places its labels.
- Assembly, hover, select, domain focus, recall, both overlays, the dock, its
  menus and every keyboard shortcut; labels through a full rotation; timeline
  scrub and playback.
- No-WebGL fallback, with WebGL contexts forced to fail.
- Reduced motion, with the `prefers-reduced-motion` media query forced on. The
  operating-system setting itself was not toggled.
- Touch, with synthesised touch pointer events at 375 × 812: one-finger orbit,
  two-finger pinch in and out, tap to select. Not tried on a physical device.
- The Atlas code makes no network request and imports nothing from
  `lib/api` or `lib/memory/client`; it only type-imports `lib/memory/types`.

Not checked: low-end or integrated GPUs, a physical touch device, Safari and
Firefox, screen readers.
