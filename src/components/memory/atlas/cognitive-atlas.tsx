"use client";

/**
 * Cognitive Atlas — a living map of Lilith's memory.
 *
 * The brain is the interface. It floats free in the Memory workspace — no
 * stage, no frame — rendered on a viewport-wide transparent layer behind the
 * OS chrome so it blends into LILITH's environment. Nothing else is permanent:
 * domains are callouts on the brain, a memory or a domain opens a contextual
 * inspector, and everything secondary sits behind one small control dock.
 *
 * Two sources, chosen explicitly and never mixed (Simulation is the default):
 *  - SIMULATION — the synthetic graph and its invented activity
 *    (lib/memory/atlas/synthetic.ts, simulation.ts), labelled as such;
 *  - REAL MEMORY — a read-only projection of the memory read model
 *    (lib/memory/atlas/real-source.ts, ./use-real-atlas.ts). Only what the
 *    backend returns; on failure an honest notice, never a stand-in.
 * Each has its own store; the brain, its interactions and its settings are
 * shared. `/memory/atlas?source=real` opens Real memory directly.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { AlertTriangle, Brain, Database, FlaskConical } from "lucide-react";
import { MemoryViewSwitch, type MemoryView } from "@/components/memory/memory-view-switch";
import { buildBrainLayout } from "@/lib/memory/atlas/brain-shape";
import { REGIONS, REGION_BY_ID } from "@/lib/memory/atlas/regions";
import { createSimulation, matchCue, traceAssociations } from "@/lib/memory/atlas/simulation";
import { createAtlasStore } from "@/lib/memory/atlas/store";
import { buildSyntheticGraph } from "@/lib/memory/atlas/synthetic";
import type { AtlasFocus, AtlasNode, RegionId } from "@/lib/memory/atlas/types";
import { FAILURE_LINE, associationTotals, associationsOf, entityMembers } from "@/lib/memory/atlas/real-source";
import { cn } from "@/lib/utils";
import { AtlasDock, BACKDROP_SHADE, DEFAULT_VISUALS, GLOW_GAIN, type AtlasVisuals } from "./atlas-dock";
import { NodeInspector, RegionInspector } from "./atlas-inspector";
import { AtlasLabels } from "./atlas-labels";
import { BrainCanvas } from "./brain-canvas";
import { CognitionFeed, GrowthLog, ThoughtTicker } from "./cognition-feed";
import { GrowthTimeline } from "./growth-timeline";
import { RecallConsole, type RecallState } from "./recall-console";
import { RegionIndex } from "./region-index";
import {
  ObservedChanges,
  RealNodeInspector,
  RealRegionInspector,
  RealStateNotice,
  RealTimelineNotice,
  SourceSwitch,
  type AtlasSource,
} from "./real-panels";
import { useRealAtlas } from "./use-real-atlas";
import type { CameraIntent, SceneAnchors, SceneApi, SceneVisuals } from "./scene/brain-scene";

type Selection = { type: "node"; id: string } | { type: "region"; id: RegionId } | null;
type AtlasView = "brain" | "timeline";
type Frame = { left: number; top: number; right: number; bottom: number; vw: number; vh: number };

const NO_FOCUS: AtlasFocus = { nodes: new Map(), links: new Set(), region: -1, dim: 0 };
/** Shown everything: later than any memory can be born. */
const NOW = 1.1;

function useMediaQuery(query: string, serverValue: boolean) {
  return useSyncExternalStore(
    (notify) => {
      const mq = window.matchMedia(query);
      mq.addEventListener("change", notify);
      return () => mq.removeEventListener("change", notify);
    },
    () => window.matchMedia(query).matches,
    () => serverValue,
  );
}

/** The page's address for a view and source. */
function atlasHref(view: AtlasView, source: AtlasSource) {
  const params = new URLSearchParams();
  if (view === "timeline") params.set("view", "timeline");
  if (source === "real") params.set("source", "real");
  const q = params.toString();
  return q ? `/memory/atlas?${q}` : "/memory/atlas";
}

const clock = (ms: number) => new Date(ms).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

function useTabHidden() {
  return useSyncExternalStore(
    (notify) => {
      document.addEventListener("visibilitychange", notify);
      return () => document.removeEventListener("visibilitychange", notify);
    },
    () => document.visibilityState === "hidden",
    () => false,
  );
}

/* viewer preferences — a per-browser convenience, never required */
const PREFS_KEY = "lilith-os:atlas-prefs";

function loadPrefs(): { visuals: AtlasVisuals; labels: boolean } {
  const fallback = { visuals: DEFAULT_VISUALS, labels: true };
  try {
    const raw = window.localStorage.getItem(PREFS_KEY);
    if (!raw) return fallback;
    const saved = JSON.parse(raw) as { visuals?: Partial<AtlasVisuals>; labels?: unknown };
    const v = saved.visuals ?? {};
    return {
      labels: typeof saved.labels === "boolean" ? saved.labels : true,
      visuals: {
        orbit: typeof v.orbit === "boolean" ? v.orbit : DEFAULT_VISUALS.orbit,
        pathways: typeof v.pathways === "boolean" ? v.pathways : DEFAULT_VISUALS.pathways,
        glow: v.glow && v.glow in GLOW_GAIN ? v.glow : DEFAULT_VISUALS.glow,
        backdrop: v.backdrop && v.backdrop in BACKDROP_SHADE ? v.backdrop : DEFAULT_VISUALS.backdrop,
      },
    };
  } catch {
    return fallback;
  }
}

export default function CognitiveAtlas() {
  const desktop = useMediaQuery("(min-width: 1280px)", true);
  const touch = useMediaQuery("(pointer: coarse)", false);
  // the OS-level "reduce motion" setting, followed live
  const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)", false);
  const hidden = useTabHidden();

  /* the brain, the synthetic graph and its event source — built once */
  const [{ layout, simStore, simulation, blank }] = useState(() => {
    const layout = buildBrainLayout();
    const simStore = createAtlasStore(buildSyntheticGraph(layout), layout);
    // what Real mode draws while it has no confirmed snapshot: no memories at all
    const blank = createAtlasStore({ nodes: [], links: [], origin: 0, now: 1 }, layout);
    return { layout, simStore, simulation: createSimulation(simStore), blank };
  });

  /* Which source the brain shows. Simulation unless chosen; never remembered. */
  const [source, setSource] = useState<AtlasSource>("simulation");
  const real = useRealAtlas(layout, source === "real", hidden);
  const isReal = source === "real";
  const store = isReal ? (real.phase === "ready" ? real.store : blank) : simStore;
  const origin = isReal ? "real" : "synthetic";
  const state = useSyncExternalStore(store.subscribe, store.getState, store.getState);

  const [view, setView] = useState<AtlasView>("brain");
  const [selection, setSelection] = useState<Selection>(null);
  /* Real memory: an entity whose records and pathways are highlighted */
  const [entityFocus, setEntityFocus] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [hotRegion, setHotRegion] = useState<RegionId | null>(null);
  const [recall, setRecall] = useState<RecallState | null>(null);
  const [scrub, setScrub] = useState(1);
  const [playing, setPlaying] = useState(false);
  const [formKey, setFormKey] = useState(0);
  const [webgl, setWebgl] = useState(true);
  /* optional overlays — closed by default; the brain has the page to itself */
  const [domainsOpen, setDomainsOpen] = useState(false);
  const [sideOpen, setSideOpen] = useState(false);
  const [menu, setMenu] = useState<"visuals" | "more" | null>(null);

  /* Motion. Unset, it follows the system: still under "reduce motion", moving
     otherwise. The dock's pause / resume is an explicit choice that overrides. */
  const [motionChoice, setMotionChoice] = useState<boolean | null>(null);
  const moving = motionChoice ?? !reducedMotion;
  const [simulating, setSimulating] = useState(true);

  const [prefs] = useState(loadPrefs);
  const [visuals, setVisuals] = useState<AtlasVisuals>(prefs.visuals);
  const [labelsOn, setLabelsOn] = useState(prefs.labels);
  useEffect(() => {
    try {
      window.localStorage.setItem(PREFS_KEY, JSON.stringify({ visuals, labels: labelsOn }));
    } catch {
      /* storage unavailable — preferences simply do not persist */
    }
  }, [visuals, labelsOn]);
  const sceneVisuals = useMemo<SceneVisuals>(
    () => ({ orbit: visuals.orbit, pathways: visuals.pathways, glow: GLOW_GAIN[visuals.glow] }),
    [visuals.orbit, visuals.pathways, visuals.glow],
  );

  /* /memory/atlas?view=timeline&source=real deep-link into a view and a source */
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("view") === "timeline") setView("timeline");
    if (params.get("source") === "real") setSource("real");
  }, []);
  const changeView = useCallback(
    (next: MemoryView) => {
      if (next === "archive") return;
      setView(next);
      setRecall(null);
      setPlaying(false);
      if (next === "brain") setScrub(1);
      window.history.replaceState(null, "", atlasHref(next, source));
    },
    [source],
  );
  const changeSource = useCallback(
    (next: AtlasSource) => {
      setSource(next);
      setSelection(null);
      setEntityFocus(null);
      setHoveredId(null);
      setRecall(null);
      setPlaying(false);
      setScrub(1);
      window.history.replaceState(null, "", atlasHref(view, next));
    },
    [view],
  );

  /* ambient synthetic activity — only while the live brain is on screen and in motion */
  const simRunning = !isReal && simulating && moving && !hidden && view === "brain";
  useEffect(() => {
    if (!simRunning) return;
    simulation.start();
    return () => simulation.stop();
  }, [simulation, simRunning]);

  /* recall: advance one association at a time */
  useEffect(() => {
    if (!recall || recall.done) return;
    const id = setTimeout(
      () =>
        setRecall((r) => {
          if (!r) return r;
          return r.step >= r.trace.nodes.length - 1 ? { ...r, done: true } : { ...r, step: r.step + 1 };
        }),
      recall.step === 0 ? 950 : 1100,
    );
    return () => clearTimeout(id);
  }, [recall]);

  const logged = useRef(0);
  useEffect(() => {
    // only the simulation records a "recall"; following real links records nothing
    if (isReal || !recall?.done || logged.current === recall.trace.id) return;
    logged.current = recall.trace.id;
    store.apply({ type: "memory.recalled", at: Date.now(), cue: recall.trace.cue, chain: recall.trace.nodes });
  }, [recall, store, isReal]);

  /* Real memory: starting words drawn from entities several records share */
  const realCues = useMemo(() => {
    if (!isReal) return [];
    const counts = new Map<string, number>();
    for (const n of state.nodes) for (const e of new Set(n.entities)) counts.set(e, (counts.get(e) ?? 0) + 1);
    return [...counts]
      .filter(([, c]) => c > 1)
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 5)
      .map(([label]) => label);
  }, [isReal, state.nodes]);

  const startRecall = useCallback(
    (seedId: string, cue: string) => {
      const trace = traceAssociations(store, seedId, cue);
      if (!trace) return false;
      setSelection(null);
      setRecall({ trace, step: 0, done: false });
      return true;
    },
    [store],
  );
  const recallCue = useCallback(
    (cue: string) => {
      const seed = matchCue(store, cue);
      return seed ? startRecall(seed.id, cue) : false;
    },
    [store, startRecall],
  );

  /* timeline playback */
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const step = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setScrub((s) => {
        const next = Math.min(1, s + dt / 16);
        if (next >= 1) setPlaying(false);
        return next;
      });
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing]);
  const togglePlay = useCallback(() => {
    setPlaying((p) => {
      if (!p) setScrub((s) => (s >= 0.999 ? 0 : s));
      return !p;
    });
  }, []);

  const selectNode = useCallback((id: string | null) => {
    setEntityFocus(null);
    setSelection(id ? { type: "node", id } : null);
  }, []);
  const selectRegion = useCallback((id: RegionId | null) => {
    setRecall(null);
    setSelection(id ? { type: "region", id } : null);
  }, []);

  const selectedNode = selection?.type === "node" ? store.node(selection.id) ?? null : null;
  const selectedRegion = selection?.type === "region" ? selection.id : null;
  const hoveredNode = hoveredId ? store.node(hoveredId) ?? null : null;
  const inspecting = Boolean(selectedNode || selectedRegion);
  // the marker sits exactly where the chart draws it; at the far right it means "now"
  // Real memory has no growth history: everything present is shown
  const asOf = !isReal && view === "timeline" && scrub < 0.999 ? scrub * 0.96 : NOW;

  /* ------------------------------------------------------------- controls */
  const api = useRef<SceneApi | null>(null);
  const toggleMotion = useCallback(() => setMotionChoice(!moving), [moving]);
  const resetView = useCallback(() => {
    setSelection(null);
    setRecall(null);
    api.current?.reset();
  }, []);
  const toggleActivity = useCallback(() => {
    // while a memory is being inspected, the control brings the feed forward
    setSideOpen((open) => !open || inspecting);
    setSelection(null);
  }, [inspecting]);

  /* keyboard: Escape steps back out; single keys drive the dock; arrows orbit */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      if (e.key === "Escape") {
        if (menu) setMenu(null);
        else if (entityFocus) setEntityFocus(null);
        else if (selection) setSelection(null);
        else if (recall) setRecall(null);
        else {
          setSideOpen(false);
          setDomainsOpen(false);
        }
        return;
      }
      const tag = target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target?.isContentEditable) return;
      const onControl = tag === "BUTTON" || tag === "A";
      switch (e.key) {
        case " ":
          if (onControl) return; // Space belongs to the focused control
          toggleMotion();
          break;
        case "r":
        case "R":
          resetView();
          break;
        case "l":
        case "L":
          setLabelsOn((on) => !on);
          break;
        case "a":
        case "A":
          toggleActivity();
          break;
        case "d":
        case "D":
          setDomainsOpen((open) => !open);
          break;
        case "ArrowLeft":
          api.current?.nudge(-0.16, 0);
          break;
        case "ArrowRight":
          api.current?.nudge(0.16, 0);
          break;
        case "ArrowUp":
          api.current?.nudge(0, 0.1);
          break;
        case "ArrowDown":
          api.current?.nudge(0, -0.1);
          break;
        case "+":
        case "=":
          api.current?.zoomBy(0.88);
          break;
        case "-":
        case "_":
          api.current?.zoomBy(1.14);
          break;
        default:
          return;
      }
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menu, entityFocus, selection, recall, toggleMotion, resetView, toggleActivity]);

  /* what the scene should emphasise */
  const focus = useMemo<AtlasFocus>(() => {
    const nodes = new Map<string, 1 | 2>();
    const links = new Set<string>();
    const neighbours = (id: string) => {
      for (const l of store.linksOf(id)) {
        const other = l.source === id ? l.target : l.source;
        if (!nodes.has(other)) nodes.set(other, 1);
      }
    };
    if (recall) {
      const reached = recall.trace.nodes.slice(0, recall.step + 1);
      reached.forEach(neighbours);
      reached.forEach((id) => nodes.set(id, 2));
      recall.trace.links.slice(0, recall.step).forEach((id) => links.add(id));
      if (selectedNode) nodes.set(selectedNode.id, 2);
      return { nodes, links, region: -1, dim: 1 };
    }
    if (isReal && selectedNode && entityFocus) {
      // every record carrying the entity, and the pathways that join them
      const members = new Set(entityMembers(entityFocus, state.nodes));
      members.forEach((id) => nodes.set(id, 1));
      nodes.set(selectedNode.id, 2);
      for (const l of state.links) {
        if (!members.has(l.source) || !members.has(l.target)) continue;
        if (l.basis === "explicit" || l.viaIds?.includes(entityFocus)) links.add(l.id);
      }
      return { nodes, links, region: -1, dim: 1 };
    }
    if (selectedNode) {
      neighbours(selectedNode.id);
      nodes.set(selectedNode.id, 2);
      store.linksOf(selectedNode.id).forEach((l) => links.add(l.id));
      if (!isReal) return { nodes, links, region: -1, dim: 1 };
      // Real memory: also the associations the simplified drawing leaves out
      const extra: NonNullable<AtlasFocus["extra"]> = [];
      for (const { id: other, via } of associationsOf(selectedNode.id, state.nodes, state.links).shared) {
        if (!nodes.has(other)) nodes.set(other, 1);
        if (store.between(selectedNode.id, other)) continue;
        extra.push({ id: `assoc:${selectedNode.id}|${other}`, source: selectedNode.id, target: other, strength: 0.34 + Math.min(3, via.length) * 0.07 });
      }
      return { nodes, links, region: -1, dim: 1, extra };
    }
    if (selectedRegion) {
      for (const n of state.nodes) if (n.region === selectedRegion) nodes.set(n.id, 1);
      for (const l of state.links) if (nodes.has(l.source) && nodes.has(l.target)) links.add(l.id);
      return { nodes, links, region: REGION_BY_ID[selectedRegion].index, dim: 1 };
    }
    if (hoveredId) {
      store.linksOf(hoveredId).forEach((l) => links.add(l.id));
      return { nodes, links, region: -1, dim: 0 };
    }
    return NO_FOCUS;
  }, [recall, selectedNode, selectedRegion, hoveredId, state, store, isReal, entityFocus]);

  /* Real memory: every association, against what the brain draws */
  const totals = useMemo(() => (isReal ? associationTotals(state.nodes, state.links) : null), [isReal, state.nodes, state.links]);

  /* where the camera should settle */
  const cameraView = useMemo<CameraIntent>(() => {
    if (selectedNode) return { key: `node:${selectedNode.id}`, kind: "node", position: selectedNode.position };
    if (recall) {
      const node = store.node(recall.trace.nodes[recall.step]);
      if (node) return { key: `trace:${recall.trace.id}:${recall.step}`, kind: "trace", position: node.position };
    }
    if (selectedRegion) {
      return { key: `region:${selectedRegion}`, kind: "region", position: REGION_BY_ID[selectedRegion].focusAt };
    }
    return { key: "home", kind: "home" };
  }, [selectedNode, selectedRegion, recall, store]);

  /* DOM pinned to brain space */
  const anchors = useRef<SceneAnchors>({ els: new Map(), positions: new Map() });
  const registrars = useRef(new Map<string, (el: HTMLElement | SVGElement | null) => void>());
  const register = useCallback((key: string) => {
    let fn = registrars.current.get(key);
    if (!fn) {
      fn = (el) => {
        if (el) anchors.current.els.set(key, el);
        else anchors.current.els.delete(key);
      };
      registrars.current.set(key, fn);
    }
    return fn;
  }, []);
  useEffect(() => {
    const positions = anchors.current.positions;
    positions.clear();
    if (hoveredNode && hoveredNode.id !== selectedNode?.id) positions.set("hover", hoveredNode.position);
  });

  // label counts follow the timeline marker, so a rewound brain reads true
  const { counts, fresh } = useMemo(() => {
    const counts = new Map<RegionId, number>();
    const fresh = new Map<RegionId, number>();
    for (const n of state.nodes) {
      if (n.born <= asOf) counts.set(n.region, (counts.get(n.region) ?? 0) + 1);
      if (n.live) fresh.set(n.region, (fresh.get(n.region) ?? 0) + 1);
    }
    return { counts, fresh };
  }, [state.nodes, asOf]);

  /* Where this page sits in the viewport. The canvas spans the whole viewport
     behind the OS chrome, so the brain has to be told which part is ours. */
  const root = useRef<HTMLDivElement>(null);
  const surface = useRef<HTMLDivElement>(null);
  const [frame, setFrame] = useState<Frame>({ left: 120, top: 76, right: 32, bottom: 56, vw: 1440, vh: 900 });

  /* On narrow screens the header wraps (title, status + source, views); how
     tall it ends up depends on the width, so it is measured, not assumed. */
  const header = useRef<HTMLElement>(null);
  const [headerH, setHeaderH] = useState(88);
  useEffect(() => {
    const el = header.current;
    if (!el) return;
    const measure = () => setHeaderH(Math.round(el.getBoundingClientRect().height));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  // where panels below the header may start, on narrow screens
  const belowHeader = headerH + 20;
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      const next: Frame = {
        left: Math.round(r.left),
        top: Math.round(r.top),
        right: Math.round(window.innerWidth - r.right),
        bottom: Math.round(window.innerHeight - r.bottom),
        vw: window.innerWidth,
        vh: window.innerHeight,
      };
      setFrame((prev) =>
        (Object.keys(next) as (keyof Frame)[]).every((k) => next[k] === prev[k]) ? prev : next,
      );
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  const rightOpen = inspecting || sideOpen;
  // an open overlay nudges the brain aside (desktop only — on narrow screens it floats over)
  const insets = useMemo(
    () => ({
      left: frame.left + (desktop && domainsOpen ? 262 : 0),
      right: frame.right + (desktop && rightOpen ? 356 : 0),
      // on narrow screens the header wraps onto further rows
      top: frame.top + (desktop ? 40 : Math.max(92, headerH + 4)),
      // the timeline is a slim strip: the brain keeps most of its size beside it
      bottom: frame.bottom + (view === "timeline" ? 150 : desktop ? 84 : 124),
    }),
    [frame, desktop, domainsOpen, rightOpen, view],
  );
  const freeW = Math.max(220, frame.vw - insets.left - insets.right);
  const freeH = Math.max(220, frame.vh - insets.top - insets.bottom);
  const pool = Math.min(freeW * 1.3, freeH * 1.95);
  const [shadeCore, shadeMid, shadeEdge] = BACKDROP_SHADE[visuals.backdrop];

  return (
    <MotionConfig reducedMotion={reducedMotion ? "always" : "never"}>
      <div ref={root} className="relative h-full min-h-[480px]">
        {/* ----------------------------------------------- the brain itself */}
        {/* A viewport-wide transparent layer behind the OS chrome: no stage, no
            frame. The only thing between the brain and the environment is a
            soft, borderless pool of shadow that keeps the particles legible. */}
        <div className="pointer-events-none fixed inset-0 -z-[1]">
          <div
            className="absolute -translate-x-1/2 -translate-y-1/2 transition-[left,top,width,height] duration-1000 ease-out"
            style={{
              left: insets.left + freeW / 2,
              top: insets.top + freeH / 2,
              width: pool,
              height: pool * 0.84,
              background: `radial-gradient(closest-side, rgba(129,42,73,0.2), transparent 60%), radial-gradient(closest-side, rgba(7,5,8,${shadeCore}) 0%, rgba(7,5,8,${shadeMid}) 44%, rgba(7,5,8,${shadeEdge}) 74%, transparent 100%)`,
            }}
          />
          <BrainCanvas
            layout={layout}
            store={store}
            focus={focus}
            selectedId={selectedNode?.id ?? null}
            hoveredId={hoveredId}
            view={cameraView}
            recall={recall}
            hotRegion={hotRegion ? REGION_BY_ID[hotRegion].index : -1}
            asOf={asOf}
            timeline={!isReal && view === "timeline"}
            calm={!moving}
            paused={hidden}
            formKey={formKey}
            visuals={sceneVisuals}
            labels={labelsOn}
            idleMemories={!isReal}
            adaptiveGlow={isReal}
            insets={insets}
            surface={surface}
            anchors={anchors}
            api={api}
            onHover={setHoveredId}
            onSelect={selectNode}
            onWebGL={setWebgl}
          />
        </div>
        {/* pointer surface: drag, zoom, hover and click all land here */}
        <div ref={surface} className="absolute inset-0 touch-none" />
        <AtlasLabels
          origin={origin}
          register={register}
          counts={counts}
          live={fresh}
          active={selectedRegion}
          quiet={Boolean(selectedNode || recall)}
          hovered={hoveredNode}
          onHoverRegion={setHotRegion}
          onSelectRegion={selectRegion}
        />

        {/* --------------------------------------------------------- header */}
        <header ref={header} className="pointer-events-none absolute inset-x-0 top-0 z-10 flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
          <div className="flex items-center gap-3">
            <span className="glass relative grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-2xl text-wine-bright">
              <span className="absolute inset-x-1 top-0 h-px bg-gradient-to-r from-transparent via-pearl/55 to-transparent" />
              <Brain className="h-[18px] w-[18px]" strokeWidth={1.75} />
            </span>
            <div>
              <h1 className="text-lg font-semibold leading-tight tracking-[-0.03em] text-ink">Cognitive Atlas</h1>
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint">
                <span className="text-ink-muted">{state.nodes.length}</span>{" "}
                {isReal ? (state.nodes.length === 1 ? "record" : "records") : "memories"} ·{" "}
                <span className="text-ink-muted">{state.links.length}</span> pathways ·{" "}
                {totals && totals.total !== state.links.length && (
                  <span title="Every pair of records the source links or that shares an entity. The brain draws a simplified set; select a record to see all of its associations.">
                    <span className="text-ink-muted">{totals.total}</span> associations ·{" "}
                  </span>
                )}
                <span className="text-ink-muted">{REGIONS.length}</span> domains
              </p>
            </div>
          </div>
          <div className="pointer-events-auto flex flex-wrap items-center gap-2">
            {isReal ? (
              real.phase === "ready" && real.stale ? (
                <span
                  className="inline-flex items-center gap-1.5 rounded-full border border-amber/25 bg-amber/10 px-2.5 py-1 text-[10px] font-medium text-amber backdrop-blur-md"
                  title={`The latest read failed: ${FAILURE_LINE[real.stale.failure]} Showing the last successful snapshot.`}
                >
                  <AlertTriangle className="h-3 w-3" />
                  Real memory · stale since {clock(real.lastGoodAt)}
                </span>
              ) : (
                <span
                  className="inline-flex items-center gap-1.5 rounded-full border border-cyan/25 bg-cyan/10 px-2.5 py-1 text-[10px] font-medium text-cyan-bright backdrop-blur-md"
                  title="Records read from Lilith's memory read model. Read-only: nothing here writes, and nothing is stored in this browser."
                >
                  <Database className="h-3 w-3" />
                  Real memory · read-only
                  {real.phase === "ready" && <span className="text-ink-faint">· read {clock(real.lastGoodAt)}</span>}
                </span>
              )
            ) : (
              <span
                className="inline-flex items-center gap-1.5 rounded-full border border-amber/25 bg-amber/10 px-2.5 py-1 text-[10px] font-medium text-amber backdrop-blur-md"
                title="This is a preview. Every memory shown here is invented; the simulation is not connected to Lilith's real memory."
              >
                <FlaskConical className="h-3 w-3" />
                Preview · Synthetic data
              </span>
            )}
            <SourceSwitch value={source} onChange={changeSource} />
            <MemoryViewSwitch active={view} onSelect={changeView} inPlace={["brain", "timeline"]} />
          </div>
        </header>

        {/* ----------------------------------------- optional: domain index */}
        <AnimatePresence>
          {domainsOpen && (
            <motion.div
              key="domains"
              initial={{ opacity: 0, x: -16, filter: "blur(6px)" }}
              animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, x: -16, filter: "blur(6px)" }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="absolute left-0 top-[64px] z-20 w-[250px]"
              style={desktop ? undefined : { top: Math.max(112, belowHeader) }}
            >
              <RegionIndex
                origin={origin}
                nodes={state.nodes}
                active={selectedRegion}
                onHover={setHotRegion}
                onSelect={selectRegion}
                onClose={() => setDomainsOpen(false)}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* ----------------- contextual inspector / optional activity panel */}
        <div
          className={cn(
            "pointer-events-none absolute right-0 top-[56px] z-20 flex w-[min(100%,344px)] flex-col",
            view === "timeline" ? "bottom-[164px]" : "bottom-[76px] max-xl:bottom-[120px]",
          )}
          style={desktop ? undefined : { top: Math.max(112, belowHeader) }}
        >
          <AnimatePresence mode="wait">
            {rightOpen && (
              <motion.div
                key={selectedNode ? "node" : selectedRegion ? "region" : "activity"}
                initial={{ opacity: 0, x: 18, filter: "blur(6px)" }}
                animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, x: 18, filter: "blur(6px)" }}
                transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
                className="pointer-events-auto flex max-h-full min-h-0 flex-col"
              >
                {isReal && real.phase === "ready" && selectedNode ? (
                  <RealNodeInspector
                    node={selectedNode}
                    store={store}
                    entities={real.entities}
                    relationships={real.relationships}
                    entitiesStale={real.entitiesStale}
                    nodes={state.nodes}
                    links={state.links}
                    focusedEntity={entityFocus}
                    onFocusEntity={(id) => setEntityFocus((current) => (current === id ? null : id))}
                    onClose={() => selectNode(null)}
                    onSelect={selectNode}
                    onExplore={(n: AtlasNode) => {
                      if (view !== "brain") changeView("brain");
                      startRecall(n.id, n.title);
                    }}
                  />
                ) : isReal && selectedRegion ? (
                  <RealRegionInspector
                    region={selectedRegion}
                    state={state}
                    store={store}
                    associations={totals?.byRegion.get(selectedRegion) ?? 0}
                    onClose={() => setSelection(null)}
                    onSelect={selectNode}
                  />
                ) : isReal ? (
                  real.phase === "ready" ? (
                    <ObservedChanges
                      state={state}
                      firstAt={real.firstAt}
                      lastGoodAt={real.lastGoodAt}
                      stale={real.stale}
                      checking={real.checking}
                      onCheck={real.check}
                      onSelect={selectNode}
                      onClose={() => setSideOpen(false)}
                      className="max-h-full"
                    />
                  ) : null
                ) : selectedNode ? (
                  <NodeInspector
                    node={selectedNode}
                    store={store}
                    onClose={() => setSelection(null)}
                    onSelect={selectNode}
                    onTrace={(n: AtlasNode) => {
                      if (view !== "brain") changeView("brain");
                      startRecall(n.id, n.title);
                    }}
                  />
                ) : selectedRegion ? (
                  <RegionInspector
                    region={selectedRegion}
                    state={state}
                    store={store}
                    onClose={() => setSelection(null)}
                    onSelect={selectNode}
                  />
                ) : view === "timeline" ? (
                  <GrowthLog
                    nodes={state.nodes}
                    asOf={asOf}
                    onSelect={selectNode}
                    onClose={() => setSideOpen(false)}
                    className="max-h-full"
                  />
                ) : (
                  <CognitionFeed
                    state={state}
                    running={simRunning}
                    onToggle={() => {
                      // resuming the simulation from the feed also resumes motion
                      if (!simRunning) setMotionChoice(true);
                      setSimulating(!simRunning);
                    }}
                    onSelect={selectNode}
                    onClose={() => setSideOpen(false)}
                    className="max-h-full"
                  />
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* ---------------------- bottom left: latest thought + control dock */}
        <div
          className={cn(
            "group/zone pointer-events-none absolute bottom-0 left-0 z-20 flex max-w-full flex-col items-start gap-2.5",
            view === "timeline" ? "max-xl:bottom-[156px]" : "max-xl:bottom-[56px]",
          )}
        >
          {view === "brain" && !sideOpen && !menu && (
            // steps back while the dock is in use, so tooltips have clear air
            <ThoughtTicker
              origin={origin}
              activity={state.activity}
              onSelect={selectNode}
              className="w-[min(100%,300px)] transition-opacity duration-200 group-has-[[role=toolbar]:hover]/zone:opacity-0 group-has-[[role=toolbar]:focus-within]/zone:opacity-0"
            />
          )}
          <AtlasDock
            className="pointer-events-auto"
            view={view}
            source={source}
            onCheck={isReal ? real.check : undefined}
            checking={real.phase === "ready" || real.phase === "unavailable" ? real.checking : real.phase === "loading"}
            motion={moving}
            heldForReducedMotion={reducedMotion && motionChoice === null}
            onMotion={toggleMotion}
            onReset={resetView}
            labels={labelsOn}
            onLabels={() => setLabelsOn((on) => !on)}
            activity={sideOpen && !inspecting}
            onActivity={toggleActivity}
            domains={domainsOpen}
            onDomains={() => setDomainsOpen((open) => !open)}
            visuals={visuals}
            onVisuals={(patch) => setVisuals((v) => ({ ...v, ...patch }))}
            simulating={simulating}
            onSimulating={() => setSimulating((on) => !on)}
            remaining={simulation.remaining()}
            onTeach={() => simulation.teach()}
            onReplay={() => {
              setMotionChoice(true);
              setFormKey((k) => k + 1);
            }}
            menu={menu}
            onMenu={setMenu}
          />
        </div>

        {/* ------------------------------------- bottom centre: recall / time */}
        <div
          className={cn(
            "absolute bottom-0 left-1/2 z-10 -translate-x-1/2",
            view === "timeline" ? "w-[min(100%,640px)]" : "pointer-events-none w-[min(100%,600px)]",
          )}
        >
          <AnimatePresence mode="wait" initial={false}>
            {view === "brain" ? (
              <motion.div
                key="recall"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 12 }}
                transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                className="flex justify-center"
              >
                <RecallConsole
                  origin={origin}
                  cues={isReal ? realCues : undefined}
                  store={store}
                  recall={recall}
                  onRecall={recallCue}
                  onClear={() => setRecall(null)}
                  onSelect={selectNode}
                  className="pointer-events-auto w-full"
                />
              </motion.div>
            ) : (
              <motion.div
                key="timeline"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 12 }}
                transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              >
                {isReal ? (
                  <RealTimelineNotice nodes={state.nodes} />
                ) : (
                  <GrowthTimeline
                    nodes={state.nodes}
                    links={state.links}
                    origin={store.origin}
                    now={store.now}
                    scrub={scrub}
                    playing={playing}
                    onScrub={(v) => {
                      setPlaying(false);
                      setScrub(v);
                    }}
                    onPlay={togglePlay}
                  />
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {isReal && real.phase !== "ready" && real.phase !== "off" && (
          <RealStateNotice
            phase={real.phase === "loading" ? "loading" : "unavailable"}
            failure={real.phase === "unavailable" ? real.failure : undefined}
            checking={real.phase === "unavailable" && real.checking}
            onRetry={real.check}
            onSimulation={() => changeSource("simulation")}
          />
        )}
        {isReal && real.phase === "ready" && state.nodes.length === 0 && (
          <RealStateNotice phase="empty" onSimulation={() => changeSource("simulation")} />
        )}

        <p className="pointer-events-none absolute bottom-1 right-0 z-10 hidden font-mono text-[9px] uppercase tracking-[0.14em] text-ink-faint/80 xl:block">
          {!webgl
            ? "Still view · WebGL is unavailable in this browser"
            : touch
              ? "Drag to orbit · pinch to zoom · tap a memory"
              : "Drag to orbit · scroll to zoom · select a memory"}
        </p>
        {!webgl && (
          <p className="pointer-events-none absolute inset-x-0 top-[72px] z-10 text-center font-mono text-[9px] uppercase tracking-[0.14em] text-ink-faint xl:hidden">
            Still view · WebGL is unavailable
          </p>
        )}
      </div>
    </MotionConfig>
  );
}
