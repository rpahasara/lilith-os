/**
 * Atlas store — the single place memory events become visible state.
 *
 * `apply(event)` is the ONLY way the graph changes. Two kinds of caller, never
 * in the same store:
 *   - the synthetic simulation (`memory.*` events), and
 *   - the real-memory reconciler (`record.*` / `link.*` events), which reports
 *     only what differs between two successful snapshots of the read model.
 *
 * Neither the React panels nor the WebGL scene know which is which:
 *   - panels read immutable snapshots through `subscribe` / `getState`
 *     (useSyncExternalStore);
 *   - the scene listens to `onEvent` and animates the change imperatively,
 *     without a React render.
 *
 * A withdrawn record is removed from every index the store keeps: the node
 * map, the link map, adjacency, pair lookup and the activity log. Nothing of
 * it is retained.
 */
import type { BrainLayout } from "./brain-shape";
import { placeNode } from "./brain-shape";
import { REGION_BY_ID } from "./regions";
import { bornAt } from "./math";
import type {
  AtlasActivity,
  AtlasEvent,
  AtlasLink,
  AtlasLinkInput,
  AtlasNode,
  AtlasState,
  Vec3,
} from "./types";

const ACTIVITY_LIMIT = 40;

/** What a store is built from. */
export interface AtlasGraph {
  nodes: AtlasNode[];
  links: AtlasLink[];
  /** start of the growth timeline (epoch ms). */
  origin: number;
  now: number;
}

/** What an applied event actually changed — handed to scene listeners. */
export interface AppliedEvent {
  event: AtlasEvent;
  node?: AtlasNode;
  links: AtlasLink[];
  /** ids taken out of the graph by this event. */
  removed?: { nodes: string[]; links: string[] };
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

const NO_CHANGES = { observed: 0, changed: 0, withdrawn: 0, links: 0 };

export function createAtlasStore(graph: AtlasGraph, layout: BrainLayout): AtlasStore {
  let state: AtlasState = {
    nodes: graph.nodes,
    links: graph.links,
    activity: [],
    session: { learned: 0, linked: 0, reinforced: 0, recalled: 0 },
    changes: NO_CHANGES,
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
  const unindex = (l: AtlasLink) => {
    for (const end of [l.source, l.target]) {
      const rest = (adjacency.get(end) ?? []).filter((x) => x.id !== l.id);
      if (rest.length) adjacency.set(end, rest);
      else adjacency.delete(end);
    }
    if (pairs.get(pairKey(l.source, l.target))?.id === l.id) pairs.delete(pairKey(l.source, l.target));
    links.delete(l.id);
  };
  graph.links.forEach(index);

  const listeners = new Set<() => void>();
  const eventListeners = new Set<(applied: AppliedEvent) => void>();
  let serial = 0;

  const addLink = (input: AtlasLinkInput, at: number): AtlasLink | null => {
    if (!nodes.has(input.source) || !nodes.has(input.target)) return null;
    if (input.source === input.target || pairs.has(pairKey(input.source, input.target))) return null;
    if (input.id && links.has(input.id)) return null;
    const link: AtlasLink = {
      basis: "synthetic",
      ...input,
      id: input.id ?? `live-l-${++serial}`,
      createdAt: at,
      born: bornAt(at, graph.origin, graph.now),
      live: true,
    };
    links.set(link.id, link);
    index(link);
    return link;
  };

  const log = (entry: Omit<AtlasActivity, "id">, activity = state.activity): AtlasActivity[] =>
    [{ ...entry, id: `a-${++serial}` }, ...activity].slice(0, ACTIVITY_LIMIT);

  function apply(event: AtlasEvent) {
    const applied: AppliedEvent = { event, links: [] };
    const session = { ...state.session };
    const changes = { ...state.changes };

    switch (event.type) {
      case "memory.learned":
      case "record.observed": {
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
        if (event.type === "memory.learned") {
          session.learned += 1;
          session.linked += applied.links.length;
        } else {
          changes.observed += 1;
          changes.links += applied.links.length;
        }
        state = {
          nodes: [...state.nodes, node],
          links: [...state.links, ...applied.links],
          activity: log({ at: event.at, type: event.type, text: node.title, region: node.region, nodeId: node.id }),
          session,
          changes,
        };
        break;
      }
      case "record.changed": {
        const current = nodes.get(event.node.id);
        if (!current) return;
        // same place in the brain; what the source says now
        const node: AtlasNode = { ...current, ...event.node, region: current.region === event.node.region ? current.region : event.node.region };
        if (node.region !== current.region) {
          node.position = placeNode(layout, node.region, node.id, state.nodes.filter((n) => n.id !== node.id).map((n) => n.position));
        }
        nodes.set(node.id, node);
        applied.node = node;
        changes.changed += 1;
        state = {
          ...state,
          nodes: state.nodes.map((n) => (n.id === node.id ? node : n)),
          activity: log({ at: event.at, type: event.type, text: node.title, region: node.region, nodeId: node.id }),
          changes,
        };
        break;
      }
      case "record.withdrawn": {
        const current = nodes.get(event.nodeId);
        if (!current) return;
        const gone = [...(adjacency.get(current.id) ?? [])];
        gone.forEach(unindex);
        adjacency.delete(current.id);
        nodes.delete(current.id);
        const goneIds = new Set(gone.map((l) => l.id));
        applied.removed = { nodes: [current.id], links: [...goneIds] };
        changes.withdrawn += 1;
        // Nothing of the record stays behind: earlier activity about it goes,
        // and the entry for its withdrawal names no content.
        const kept = state.activity.filter((a) => a.nodeId !== current.id);
        state = {
          ...state,
          nodes: state.nodes.filter((n) => n.id !== current.id),
          links: state.links.filter((l) => !goneIds.has(l.id)),
          activity: log({ at: event.at, type: event.type, text: "A record is no longer in the read model", region: current.region }, kept),
          changes,
        };
        break;
      }
      case "memory.linked":
      case "link.observed": {
        const link = addLink(event.link, event.at);
        if (!link) return;
        applied.links.push(link);
        const a = nodes.get(link.source)!;
        const b = nodes.get(link.target)!;
        if (event.type === "memory.linked") session.linked += 1;
        else changes.links += 1;
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
          changes,
        };
        break;
      }
      case "link.withdrawn": {
        const link = links.get(event.linkId);
        if (!link) return;
        unindex(link);
        applied.removed = { nodes: [], links: [link.id] };
        changes.links += 1;
        const a = nodes.get(link.source);
        state = {
          ...state,
          links: state.links.filter((l) => l.id !== link.id),
          activity: a
            ? log({ at: event.at, type: event.type, text: `${a.title} · ${link.kind}`, region: a.region, nodeId: a.id })
            : state.activity,
          changes,
        };
        break;
      }
      case "memory.reinforced": {
        const current = nodes.get(event.nodeId);
        if (!current) return;
        const node: AtlasNode = {
          ...current,
          confidence: event.confidence ?? Math.min(99, (current.confidence ?? 0) + 1),
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
