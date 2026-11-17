# Cognitive Atlas — Real Memory (P1-4)

The Atlas has two sources, chosen explicitly in its header and never mixed:

| | Simulation (default) | Real memory |
|---|---|---|
| Data | Synthetic graph + invented activity (`synthetic.ts`, `simulation.ts`) | Read-only projection of the memory read model (`real-source.ts`) |
| Label | "Preview · Synthetic data", "Simulated" tags | "Real memory · read-only", "snapshot" tags |
| Activity | Learning, linking, reinforcement, recall — all invented | Differences between successive snapshots — nothing else |
| Timeline | Synthetic growth history | None: the records carry no learning history |
| Store | Its own `AtlasStore` | Its own `AtlasStore`, dropped when the mode is left |

`/memory/atlas?source=real` opens Real memory directly. The choice is not
remembered; every visit opens on the simulation. The brain, its interactions
and the visual settings are shared by both.

## Data source

There is no memory event stream, and nothing new was added to the backend.
Real memory reads the same two GET endpoints the Memory Archive reads, through
the same same-origin proxy and the same normalisers:

- `GET /memory/records` → records
- `GET /memory/entities` → entities and entity-to-entity relationships

No demo or sample data is ever used in Real mode (`getMemoryData`'s demo
fallback is not on this path). No Core API schema change was needed.

## Mapping

### Categories → regions

The brain's seven regions are fixed (they are the approved visual); the memory
model has seven categories. Six map by name. The remaining pair do not line up:

| Category | Region | Notes |
|---|---|---|
| career | Career | |
| **work** | **Career** | Category stays `work`. The region is named **"Career · Work"** in Real mode, the inspector says "Category Work · drawn in the Career · Work field", and the region panel lists both categories with counts. |
| projects | Projects | Work is never placed here. |
| people | People | |
| knowledge | Knowledge | |
| preferences | Preferences | |
| personal | Personal | |
| — | **Relationships** | No category maps here. In Real mode it is empty (0) and says so. |

Why Work goes to the Career field: Career is the frontal field of roles and the
decisions that shape them, and "how you work" is closest to it; Projects is
about specific things being built. Adding an eighth region or re-purposing
Relationships would change the approved visual and invent a classification the
source does not make. The source classification is preserved on every node
(`AtlasNode.category`), so nothing downstream reads Work as Career.

Relationships stays empty rather than borrowing People records: a person is not
a relationship, and filling the region would be a visual claim the data does
not make.

### Records → nodes

Only what the source states is carried. Absent fields stay absent:

| Field | From | When absent |
|---|---|---|
| title / detail | `summary` / `content` | "Untitled record" |
| kind | `kind` (today always `unknown`) | shown as Unknown |
| confidence | `confidence` (career events only) | "—" / "not stated" |
| importance | `importance` (today always null) | "—" / "not stated" |
| createdAt | `created_at` | "not stated" (curated files have none) |
| updatedAt | `updated_at` (for files: modification time) | "not stated" |
| provenance | `provenance.{kind,label,at,source_account}` | at / account omitted |

Node size and brightness use `renderWeight(node)` — the stated importance, or a
neutral drawing default (`DEFAULT_RENDER_WEIGHT`). The default is a rendering
parameter, never shown or read back as importance.

Real nodes have no growth position (`born = 0`), no reinforcements, no recalls
and no "learned" time. The inspector shows record dates under "Record dates",
with a note that an update can be a file change and is not when Lilith learned
anything.

### Links

Two kinds of memory-to-memory pathway, kept apart in data and on screen:

- **explicit** (`explicit:a|b`) — the source lists the records as `related`.
  Inspector: "Linked by the source".
- **shared-entity** (`shared:a|b`) — derived here: both records carry the same
  entity. The link names the shared entities (`via`). Inspector: "Share an
  entity · derived here". A pair with an explicit link is not also drawn as
  shared. An entity carried by more than 24 records draws no pathways (dense
  and uninformative); it is still listed on each record.

Pathway brightness for real links is a drawing weight, not a measured strength,
and is not shown as a value.

**Entity-to-entity relationships** (`/memory/entities` → `relationships`, e.g.
"works at") are not memory links and are never drawn as pathways. They are
shown in the node inspector under each entity, labelled as relationships
between entities.

## Change over time

Real mode reads the records when it opens, then every 60 s while the page is
visible, and on "Check now". Each successful read is compared with the graph by
record id and a fingerprint of the stated fields:

| Difference | Event | Shown as |
|---|---|---|
| record not seen before | `record.observed` | "Newly observed" |
| stated fields differ | `record.changed` | "Changed" (stays in place unless its region changed) |
| record absent | `record.withdrawn` | "No longer in the read model" |
| link appears / disappears | `link.observed` / `link.withdrawn` | "Association observed" / "Association gone" |

The panel says a difference is not proof that Lilith learned or forgot
anything. The first read builds the graph whole (nothing is animated as
"new" just because it was already there).

### Failures never delete

A read is accepted only when `/memory/records` answers 2xx with a records
array. Network errors, 401/403, 5xx, 503 (not configured) and malformed bodies
are failed checks: nothing is removed, the header turns to "stale since HH:MM",
and the Observed changes panel names the failure. With no successful read yet,
Real mode shows "Real memory is unavailable" and draws no memories — no sample
or simulated records take their place. Records without an id are left out (and
counted) because they cannot be followed between reads. If only the entities
endpoint fails, the previous entity index is kept.

### Removal

When a successful snapshot no longer contains a record, it is removed from the
store's node map, link map, adjacency and pair indexes, from the activity log
(earlier entries about it are purged; the withdrawal entry names no content),
and from the GPU buffers (slot hidden and forgotten by id). Selection and hover
fall away because the id no longer resolves.

## Privacy

- Nothing about real records is written to `localStorage`, `sessionStorage`,
  IndexedDB or caches. The only persisted Atlas data is the visual preferences
  key (`lilith-os:atlas-prefs`: visuals + labels).
- Real data lives in the Real-mode hook's memory and is dropped when the mode
  is left or the page unmounts.
- Test fixtures are invented and shaped like the contract; no real memory,
  API response or screenshot of real data is committed.

## Exploration, not recall

The bottom console becomes "Explore associations" in Real mode: it matches a
word against record titles, tags and entities locally and follows drawn links.
It is labelled as not being Lilith's recall, and records nothing (no
`memory.recalled`, no recall counts). Suggested words are entities shared by
more than one record. Idle ambient motion stays at the level of whole regions;
individual real records are not pulsed at random.

## Boundaries

Unchanged: canonical memory authority, memory writes and learning pipelines,
Privacy/FORGET/consent, broker and witness, Core API schemas, DEV/PROD
infrastructure, production authentication. `preview-self-test.ts` enforces that
`real-source.ts` is the only Atlas file that reaches the backend;
`real-self-test.ts` covers mapping, missing metadata, links, reconciliation,
removal, failures, privacy and the simulation staying intact.

## Limitations

- Change detection is by polling; a change is seen up to 60 s late.
- The read model has no learning history, so Real mode has no timeline.
- Fingerprints compare stated fields only; a backend change that alters no
  field is invisible (correctly).
- Removed GPU slots are not reused; buffers are sized with headroom (160 nodes,
  600 pathways beyond the first snapshot). A very long session with heavy churn
  could exhaust it; reopening the mode rebuilds.
- Real mode follows the existing Memory authorization (same proxy and session
  as the Archive). Merging this makes Real mode reachable, opt-in, wherever the
  Atlas preview is enabled; Simulation remains the default.
