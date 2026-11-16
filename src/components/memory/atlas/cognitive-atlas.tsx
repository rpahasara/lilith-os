"use client";

/**
 * Cognitive Atlas — a living map of Lilith's memory (PROTOTYPE).
 *
 * The brain is the interface. It floats free in the Memory workspace — no
 * stage, no frame — rendered on a viewport-wide transparent layer behind the
 * OS chrome so it blends into LILITH's environment. Nothing else is permanent:
 * domains are callouts on the brain, a memory or a domain opens a contextual
 * inspector, and everything secondary sits behind one small control dock.
 *
 * This component owns interaction state and composes those layers. All memory
 * content is synthetic (see lib/memory/atlas/synthetic.ts); the only thing that
 * mutates the graph is `store.apply(event)`, which is where real memory events
 * will arrive later.
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
import { Brain, FlaskConical } from "lucide-react";
import { MemoryViewSwitch, type MemoryView } from "@/components/memory/memory-view-switch";
import { buildBrainLayout } from "@/lib/memory/atlas/brain-shape";
import { REGIONS, REGION_BY_ID } from "@/lib/memory/atlas/regions";
import { createSimulation, matchCue, traceAssociations } from "@/lib/memory/atlas/simulation";
import { createAtlasStore } from "@/lib/memory/atlas/store";
import { buildSyntheticGraph } from "@/lib/memory/atlas/synthetic";
import type { AtlasFocus, AtlasNode, RegionId } from "@/lib/memory/atlas/types";
import { cn } from "@/lib/utils";
import { AtlasDock, BACKDROP_SHADE, DEFAULT_VISUALS, GLOW_GAIN, type AtlasVisuals } from "./atlas-dock";
import { NodeInspector, RegionInspector } from "./atlas-inspector";
import { AtlasLabels } from "./atlas-labels";
import { BrainCanvas } from "./brain-canvas";
import { CognitionFeed, GrowthLog, ThoughtTicker } from "./cognition-feed";
import { GrowthTimeline } from "./growth-timeline";
import { RecallConsole, type RecallState } from "./recall-console";
import { RegionIndex } from "./region-index";
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
  const [{ layout, store, simulation }] = useState(() => {
    const layout = buildBrainLayout();
    const store = createAtlasStore(buildSyntheticGraph(layout), layout);
    return { layout, store, simulation: createSimulation(store) };
  });
  const state = useSyncExternalStore(store.subscribe, store.getState, store.getState);

  const [view, setView] = useState<AtlasView>("brain");
  const [selection, setSelection] = useState<Selection>(null);
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

  /* /memory/atlas?view=timeline deep-links into the timeline */
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("view") === "timeline") setView("timeline");
  }, []);
  const changeView = useCallback((next: MemoryView) => {
    if (next === "archive") return;
    setView(next);
    setRecall(null);
    setPlaying(false);
    if (next === "brain") setScrub(1);
    window.history.replaceState(null, "", next === "timeline" ? "/memory/atlas?view=timeline" : "/memory/atlas");
  }, []);

  /* ambient synthetic activity — only while the live brain is on screen and in motion */
  const simRunning = simulating && moving && !hidden && view === "brain";
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
    if (!recall?.done || logged.current === recall.trace.id) return;
    logged.current = recall.trace.id;
    store.apply({ type: "memory.recalled", at: Date.now(), cue: recall.trace.cue, chain: recall.trace.nodes });
  }, [recall, store]);

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

  const selectNode = useCallback((id: string | null) => setSelection(id ? { type: "node", id } : null), []);
  const selectRegion = useCallback((id: RegionId | null) => {
    setRecall(null);
    setSelection(id ? { type: "region", id } : null);
  }, []);

  const selectedNode = selection?.type === "node" ? store.node(selection.id) ?? null : null;
  const selectedRegion = selection?.type === "region" ? selection.id : null;
  const hoveredNode = hoveredId ? store.node(hoveredId) ?? null : null;
  const inspecting = Boolean(selectedNode || selectedRegion);
  // the marker sits exactly where the chart draws it; at the far right it means "now"
  const asOf = view === "timeline" && scrub < 0.999 ? scrub * 0.96 : NOW;

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
  }, [menu, selection, recall, toggleMotion, resetView, toggleActivity]);

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
    if (selectedNode) {
      neighbours(selectedNode.id);
      nodes.set(selectedNode.id, 2);
      store.linksOf(selectedNode.id).forEach((l) => links.add(l.id));
      return { nodes, links, region: -1, dim: 1 };
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
  }, [recall, selectedNode, selectedRegion, hoveredId, state, store]);

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
      // on narrow screens the header wraps onto a second row
      top: frame.top + (desktop ? 40 : 92),
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
            timeline={view === "timeline"}
            calm={!moving}
            paused={hidden}
            formKey={formKey}
            visuals={sceneVisuals}
            labels={labelsOn}
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
        <header className="pointer-events-none absolute inset-x-0 top-0 z-10 flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
          <div className="flex items-center gap-3">
            <span className="glass relative grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-2xl text-wine-bright">
              <span className="absolute inset-x-1 top-0 h-px bg-gradient-to-r from-transparent via-pearl/55 to-transparent" />
              <Brain className="h-[18px] w-[18px]" strokeWidth={1.75} />
            </span>
            <div>
              <h1 className="text-lg font-semibold leading-tight tracking-[-0.03em] text-ink">Cognitive Atlas</h1>
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint">
                <span className="text-ink-muted">{state.nodes.length}</span> memories ·{" "}
                <span className="text-ink-muted">{state.links.length}</span> pathways ·{" "}
                <span className="text-ink-muted">{REGIONS.length}</span> domains
              </p>
            </div>
          </div>
          <div className="pointer-events-auto flex flex-wrap items-center gap-2">
            <span
              className="inline-flex items-center gap-1.5 rounded-full border border-amber/25 bg-amber/10 px-2.5 py-1 text-[10px] font-medium text-amber backdrop-blur-md"
              title="This is a preview. Every memory shown here is invented; the Atlas is not connected to Lilith's real memory."
            >
              <FlaskConical className="h-3 w-3" />
              Preview · Synthetic data
            </span>
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
              className="absolute left-0 top-[64px] z-20 w-[250px] max-xl:top-[112px]"
            >
              <RegionIndex
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
            "pointer-events-none absolute right-0 top-[56px] z-20 flex w-[min(100%,344px)] flex-col max-xl:top-[112px]",
            view === "timeline" ? "bottom-[164px]" : "bottom-[76px] max-xl:bottom-[120px]",
          )}
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
                {selectedNode ? (
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
              activity={state.activity}
              onSelect={selectNode}
              className="w-[min(100%,300px)] transition-opacity duration-200 group-has-[[role=toolbar]:hover]/zone:opacity-0 group-has-[[role=toolbar]:focus-within]/zone:opacity-0"
            />
          )}
          <AtlasDock
            className="pointer-events-auto"
            view={view}
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
              </motion.div>
            )}
          </AnimatePresence>
        </div>

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
