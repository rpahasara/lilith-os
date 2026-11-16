/**
 * Atlas store — the single place memory events become visible state.
 *
 * `apply(event)` is the ONLY way the graph changes. Today the caller is the
 * synthetic simulation; later it is whatever adapter turns real LILITH memory
 * events into `AtlasEvent`s. Neither the React panels nor the WebGL scene know
 * the difference:
 *
 *   - panels read immutable snapshots through `subscribe` / `getState`
 *     (useSyncExternalStore);
 *   - the scene listens to `onEvent` and animates the change imperatively,
 *     without a React render.
 */
import type { BrainLayout } from "./brain-shape";
import { placeNode } from "./brain-shape";
import { REGION_BY_ID } from "./regions";
import { bornAt, type SyntheticGraph } from "./synthetic";
import type {
  AtlasActivity,
  AtlasEvent,
  AtlasLink,
  AtlasNode,
  AtlasState,
  Vec3,
} from "./types";

const ACTIVITY_LIMIT = 40;

/** What an applied event actually added — handed to scene listeners. */
export interface AppliedEvent {
  event: AtlasEvent;
  node?: AtlasNode;
  links: AtlasLink[];
}

export interface AtlasStore {
  getState(): AtlasState;
  subscribe(listener: () => void): () => void;
  onEvent(listener: (applied: AppliedEvent) => void): () => void;
  apply(event: AtlasEvent): void;
  node(id: string): AtlasNode | undefined;
  link(id: string): AtlasLink | undefined;
  /** links touching a node. */
  linksOf(id: string): AtlasLink[];
  /** the link between two nodes, if any. */
  between(a: string, b: string): AtlasLink | undefined;
  readonly origin: number;
  readonly now: number;
}

export function createAtlasStore(graph: SyntheticGraph, layout: BrainLayout): AtlasStore {
  let state: AtlasState = {
    nodes: graph.nodes,
    links: graph.links,
    activity: [],
    session: { learned: 0, linked: 0, reinforced: 0, recalled: 0 },
  };

  const nodes = new Map<string, AtlasNode>(graph.nodes.map((n) => [n.id, n]));
  const links = new Map<string, AtlasLink>(graph.links.map((l) => [l.id, l]));
  const adjacency = new Map<string, AtlasLink[]>();
  const pairs = new Map<string, AtlasLink>();
  const pairKey = (a: string, b: string) => (a < b ? `${a}|${b}` : `${b}|${a}`);
  const index = (l: AtlasLink) => {
    adjacency.set(l.source, [...(adjacency.get(l.source) ?? []), l]);
    adjacency.set(l.target, [...(adjacency.get(l.target) ?? []), l]);
    pairs.set(pairKey(l.source, l.target), l);
  };
  graph.links.forEach(index);

  const listeners = new Set<() => void>();
  const eventListeners = new Set<(applied: AppliedEvent) => void>();
  let serial = 0;

  const addLink = (
    input: { source: string; target: string; kind: string; strength: number },
    at: number,
  ): AtlasLink | null => {
    if (!nodes.has(input.source) || !nodes.has(input.target)) return null;
    if (input.source === input.target || pairs.has(pairKey(input.source, input.target))) return null;
    const link: AtlasLink = {
      ...input,
      id: `live-l-${++serial}`,
      createdAt: at,
      born: bornAt(at, graph.origin, graph.now),
      live: true,
    };
    links.set(link.id, link);
    index(link);
    return link;
  };

  const log = (entry: Omit<AtlasActivity, "id">): AtlasActivity[] =>
    [{ ...entry, id: `a-${++serial}` }, ...state.activity].slice(0, ACTIVITY_LIMIT);

  function apply(event: AtlasEvent) {
    const applied: AppliedEvent = { event, links: [] };
    const session = { ...state.session };

    switch (event.type) {
      case "memory.learned": {
        if (nodes.has(event.node.id)) return;
        const taken: Vec3[] = state.nodes.map((n) => n.position);
        const node: AtlasNode = {
          ...event.node,
          position: placeNode(layout, event.node.region, event.node.id, taken),
          born: bornAt(event.at, graph.origin, graph.now),
          live: true,
          reinforcements: 0,
          recalls: 0,
        };
        nodes.set(node.id, node);
        applied.node = node;
        for (const input of event.links) {
          const link = addLink(input, event.at);
          if (link) applied.links.push(link);
        }
        session.learned += 1;
        session.linked += applied.links.length;
        state = {
          nodes: [...state.nodes, node],
          links: [...state.links, ...applied.links],
          activity: log({ at: event.at, type: event.type, text: node.title, region: node.region, nodeId: node.id }),
          session,
        };
        break;
      }
      case "memory.linked": {
        const link = addLink(event.link, event.at);
        if (!link) return;
        applied.links.push(link);
        const a = nodes.get(link.source)!;
        const b = nodes.get(link.target)!;
        session.linked += 1;
        state = {
          ...state,
          links: [...state.links, link],
          activity: log({
            at: event.at,
            type: event.type,
            text: `${REGION_BY_ID[a.region].label} ↔ ${REGION_BY_ID[b.region].label} · ${link.kind.replace(/^shares · /, "")}`,
            region: a.region,
            nodeId: a.id,
          }),
          session,
        };
        break;
      }
      case "memory.reinforced": {
        const current = nodes.get(event.nodeId);
        if (!current) return;
        const node: AtlasNode = {
          ...current,
          confidence: event.confidence ?? Math.min(99, current.confidence + 1),
          reinforcements: current.reinforcements + 1,
          reinforcedAt: event.at,
        };
        nodes.set(node.id, node);
        applied.node = node;
        session.reinforced += 1;
        state = {
          ...state,
          nodes: state.nodes.map((n) => (n.id === node.id ? node : n)),
          activity: log({ at: event.at, type: event.type, text: node.title, region: node.region, nodeId: node.id }),
          session,
        };
        break;
      }
      case "memory.recalled": {
        const chain = new Set(event.chain);
        const first = nodes.get(event.chain[0]);
        if (!first) return;
        const next = state.nodes.map((n) => {
          if (!chain.has(n.id)) return n;
          const updated = { ...n, recalls: n.recalls + 1 };
          nodes.set(n.id, updated);
          return updated;
        });
        session.recalled += 1;
        state = {
          ...state,
          nodes: next,
          activity: log({
            at: event.at,
            type: event.type,
            text: `“${event.cue}” · ${event.chain.length} memories`,
            region: first.region,
            nodeId: first.id,
          }),
          session,
        };
        break;
      }
    }

    eventListeners.forEach((l) => l(applied));
    listeners.forEach((l) => l());
  }

  return {
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    onEvent(listener) {
      eventListeners.add(listener);
      return () => eventListeners.delete(listener);
    },
    apply,
    node: (id) => nodes.get(id),
    link: (id) => links.get(id),
    linksOf: (id) => adjacency.get(id) ?? [],
    between: (a, b) => pairs.get(pairKey(a, b)),
    origin: graph.origin,
    now: graph.now,
  };
}
