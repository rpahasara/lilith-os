/**
 * Synthetic cognition — the stand-in for real memory activity.
 *
 * Three things live here, all of them simulations:
 *   1. `startSimulation` — an ambient event source that occasionally "learns" a
 *      memory, "reinforces" one, or "links" two. It only ever calls
 *      `store.apply(event)`, exactly as a real source would.
 *   2. `traceAssociations` — a spreading-activation walk used to stage a recall.
 *   3. `matchCue` — keyword matching from a typed cue to a starting memory.
 *
 * None of it touches a network, a model or the real memory system.
 */
import { LEARN_POOL, seedToInput } from "./synthetic";
import type { AtlasStore } from "./store";
import type { AtlasEvent, AtlasLinkInput, AtlasNode, RecallTrace } from "./types";

/* ------------------------------------------------------------ event source */

let liveSerial = 0;

/** Build the next "learned" event from the pool, linked into what already exists. */
export function nextLearnEvent(store: AtlasStore, cursor: number): AtlasEvent | null {
  const item = LEARN_POOL[cursor];
  if (!item) return null;
  const at = Date.now();
  const id = `live-${++liveSerial}`;
  const node = seedToInput(id, item.region, item.seed, at);
  node.importance = Math.max(node.importance, 58);

  const { nodes } = store.getState();
  const links: AtlasLinkInput[] = [];
  const used = new Set<string>();
  for (const tag of node.tags) {
    // the strongest existing memory on the same thread, preferring another domain
    let best: AtlasNode | null = null;
    let bestScore = -1;
    for (const n of nodes) {
      if (used.has(n.id) || !n.tags.includes(tag)) continue;
      const score = n.importance + (n.region !== item.region ? 30 : 0);
      if (score > bestScore) {
        bestScore = score;
        best = n;
      }
    }
    if (best) {
      used.add(best.id);
      links.push({ source: id, target: best.id, kind: `shares · ${tag}`, strength: 0.7 });
    }
    if (links.length >= 3) break;
  }
  return { type: "memory.learned", at, node, links };
}

function reinforceEvent(store: AtlasStore): AtlasEvent | null {
  const { nodes } = store.getState();
  if (!nodes.length) return null;
  const node = nodes[Math.floor(Math.random() * nodes.length)];
  return { type: "memory.reinforced", at: Date.now(), nodeId: node.id };
}

function linkEvent(store: AtlasStore): AtlasEvent | null {
  const { nodes } = store.getState();
  // find two memories on a shared thread that are not yet associated
  for (let attempt = 0; attempt < 24; attempt++) {
    const a = nodes[Math.floor(Math.random() * nodes.length)];
    const tag = a.tags[Math.floor(Math.random() * a.tags.length)];
    const candidates = nodes.filter(
      (n) => n.id !== a.id && n.region !== a.region && n.tags.includes(tag) && !store.between(a.id, n.id),
    );
    if (!candidates.length) continue;
    const b = candidates[Math.floor(Math.random() * candidates.length)];
    return {
      type: "memory.linked",
      at: Date.now(),
      link: { source: a.id, target: b.id, kind: `shares · ${tag}`, strength: 0.55 + Math.random() * 0.3 },
    };
  }
  return null;
}

export interface Simulation {
  /** begin ambient activity. `calm` (reduced motion) slows the cadence. */
  start(opts?: { calm?: boolean }): void;
  /** stop ambient activity; the store is left exactly as it is. */
  stop(): void;
  /** learn the next pooled memory immediately. Returns false when the pool is spent. */
  teach(): boolean;
  remaining(): number;
}

/**
 * The synthetic event source. It owns nothing but a timer and its place in the
 * learn pool, so it can be paused and resumed without repeating itself.
 */
export function createSimulation(store: AtlasStore): Simulation {
  let cursor = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stopped = true;
  let calm = false;

  const teach = () => {
    const event = nextLearnEvent(store, cursor);
    if (!event) return false;
    cursor += 1;
    store.apply(event);
    return true;
  };

  const tick = () => {
    if (stopped) return;
    const roll = Math.random();
    let event: AtlasEvent | null = null;
    if (roll < 0.38 && cursor < LEARN_POOL.length) {
      teach();
    } else if (roll < 0.72) {
      event = reinforceEvent(store);
    } else {
      event = linkEvent(store) ?? reinforceEvent(store);
    }
    if (event) store.apply(event);
    schedule();
  };

  const schedule = () => {
    const base = calm ? 12_000 : 5_200;
    timer = setTimeout(tick, base + Math.random() * base * 0.7);
  };

  return {
    start(opts = {}) {
      if (!stopped) return;
      stopped = false;
      calm = Boolean(opts.calm);
      timer = setTimeout(tick, calm ? 9_000 : 6_000);
    },
    stop() {
      stopped = true;
      if (timer) clearTimeout(timer);
    },
    teach,
    remaining: () => LEARN_POOL.length - cursor,
  };
}

/* ------------------------------------------------------------------ recall */

let traceSerial = 0;

/**
 * Spreading activation from a seed memory: at each hop follow the strongest
 * association not yet visited, with a preference for crossing into a new
 * domain — which is what makes a recalled chain feel like a train of thought.
 */
export function traceAssociations(
  store: AtlasStore,
  seedId: string,
  cue: string,
  maxHops = 5,
): RecallTrace | null {
  const seed = store.node(seedId);
  if (!seed) return null;
  const nodes = [seedId];
  const links: string[] = [];
  const visited = new Set(nodes);
  const regions = new Set([seed.region]);
  let current = seedId;

  for (let hop = 0; hop < maxHops; hop++) {
    let best: { id: string; link: string; score: number } | null = null;
    for (const link of store.linksOf(current)) {
      const other = link.source === current ? link.target : link.source;
      if (visited.has(other)) continue;
      const node = store.node(other);
      if (!node) continue;
      const score =
        link.strength +
        (regions.has(node.region) ? 0 : 0.45) +
        node.importance / 400 +
        (link.kind.startsWith("shares") ? 0.15 : 0);
      if (!best || score > best.score) best = { id: other, link: link.id, score };
    }
    if (!best) break;
    nodes.push(best.id);
    links.push(best.link);
    visited.add(best.id);
    regions.add(store.node(best.id)!.region);
    current = best.id;
  }

  return nodes.length > 1 ? { id: ++traceSerial, cue, nodes, links } : null;
}

const STOPWORDS = new Set(["the", "and", "for", "with", "about", "what", "who", "that", "this", "from"]);

/** Find the synthetic memory a typed cue most plausibly points at. */
export function matchCue(store: AtlasStore, cue: string): AtlasNode | null {
  const words = cue
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((w) => w.length > 2 && !STOPWORDS.has(w));
  if (!words.length) return null;
  let best: AtlasNode | null = null;
  let bestScore = 0;
  for (const node of store.getState().nodes) {
    const title = node.title.toLowerCase();
    let score = 0;
    for (const w of words) {
      if (node.tags.includes(w)) score += 3;
      if (node.entities.some((e) => e.toLowerCase().includes(w))) score += 2;
      if (title.includes(w)) score += 2;
    }
    if (!score) continue;
    score += node.importance / 100;
    if (score > bestScore) {
      bestScore = score;
      best = node;
    }
  }
  return best;
}

/** Preset cues offered in the recall console — each seeds a strong thread. */
export const RECALL_CUES = [
  "Northwind interview",
  "Aurora launch",
  "Lisbon",
  "the Nocturne",
  "sleep and winter",
  "Mira",
] as const;
