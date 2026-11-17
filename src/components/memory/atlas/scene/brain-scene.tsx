"use client";

/**
 * The living brain — one R3F canvas, six additive layers:
 *
 *   cortex    ~29k particles sampled from the brain volume (assembly, folds,
 *             region glow, activation waves, growth)
 *   tracts    faint projection fibres fanning from the stem into every lobe
 *   pathways  associations between memories, each carrying a packet of light
 *   nodes     the memories themselves
 *   trace     the bright chain drawn by a recall
 *   stage     core heartbeat, platform rings, selection reticle
 *
 * React renders this tree once. Everything that moves is driven from the frame
 * loop through uniforms and in-place attribute writes; store events animate
 * without a React render. The same loop lays out the DOM that floats in brain
 * space: the domain callouts and the hover card.
 */
import { type RefObject, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { BrainLayout } from "@/lib/memory/atlas/brain-shape";
import { REGIONS, REGION_BY_ID, REGION_RGB, hexToRgb } from "@/lib/memory/atlas/regions";
import type { AppliedEvent, AtlasStore } from "@/lib/memory/atlas/store";
import type { AtlasFocus, AtlasLink, RecallTrace, Vec3 } from "@/lib/memory/atlas/types";
import {
  ALWAYS,
  NodeBuffers,
  PathBuffers,
  addLink,
  buildCortexGeometry,
  buildHull,
  buildRingGeometry,
  buildTracts,
  linkControl,
} from "./buffers";
import * as GLSL from "./shaders";

/** Where the camera should settle. `key` identifies the intent for effects. */
export interface CameraIntent {
  key: string;
  kind: "home" | "node" | "region" | "trace";
  position?: Vec3;
}

/**
 * DOM the scene keeps pinned to brain space. Elements register under a key:
 *   region:<id>  a domain callout        line:<id> / dot:<id>  its leader
 *   hover        the card for the memory under the pointer (needs a position)
 */
export interface SceneAnchors {
  els: Map<string, HTMLElement | SVGElement>;
  positions: Map<string, Vec3>;
}

/** Viewer-adjustable look. None of these change the brain's geometry. */
export interface SceneVisuals {
  /** slow automatic sway around the profile view. */
  orbit: boolean;
  /** ambient association pathways (focused ones always show). */
  pathways: boolean;
  /** overall light, 1 = as designed. */
  glow: number;
}

/** Imperative camera controls for the dock and keyboard. */
export interface SceneApi {
  nudge(dTheta: number, dPhi: number): void;
  zoomBy(factor: number): void;
  reset(): void;
}

export interface BrainSceneProps {
  layout: BrainLayout;
  store: AtlasStore;
  focus: AtlasFocus;
  selectedId: string | null;
  hoveredId: string | null;
  view: CameraIntent;
  recall: { trace: RecallTrace; step: number } | null;
  /** region index lit by hovering a domain, or -1. */
  hotRegion: number;
  /** position on the growth timeline; anything born later is hidden. */
  asOf: number;
  /** timeline mode: whatever the marker has just reached flares and draws on. */
  timeline: boolean;
  /** motion off (paused, or the system asks for reduced motion): no assembly,
   *  sway, drift or idle activity, and the camera moves without easing. */
  calm: boolean;
  paused: boolean;
  /** bump to replay the assembly. */
  formKey: number;
  visuals: SceneVisuals;
  /** show the domain callouts. */
  labels: boolean;
  /** idle stirring may pulse individual memories. Off for real memory: a
   *  random pulse on a real record would look like activity that did not
   *  happen, so idle motion stays at the level of whole regions. */
  idleMemories?: boolean;
  /** dim ambient memory pathways as they get denser, so many overlapping
   *  additive lines never wash the brain out. Focused pathways keep full
   *  strength. Off for the simulation, which is drawn as designed. */
  adaptiveGlow?: boolean;
  /** px of the canvas (the whole viewport) that the OS chrome and any open
   *  overlays cover — the brain centres itself in what is left. */
  insets: { left: number; right: number; top: number; bottom: number };
  /** the element that receives pointer input. The canvas itself sits behind the
   *  OS chrome as a pure backdrop, so it cannot take events directly. */
  surface: RefObject<HTMLElement | null>;
  anchors: RefObject<SceneAnchors>;
  api: RefObject<SceneApi | null>;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
}

/** Most hidden associations one focus can draw at once. */
const OVERLAY_CAPACITY = 1024;
/** Pathway count up to which ambient memory pathways keep full strength
 *  (about the simulation's own density); beyond it they dim with the square
 *  root of the count, never below DENSITY_FLOOR. */
const DENSITY_REF = 300;
const DENSITY_FLOOR = 0.28;

const FOV = 36;
const TAN = Math.tan(THREE.MathUtils.degToRad(FOV / 2));
const HOME: Vec3 = [-0.05, -0.14, 0];
/** The canonical view: left profile, turned slightly toward the viewer. */
const HOME_ORBIT = Math.PI + 0.3;
const HOME_PHI = 0.13;
const SWAY = 0.46;
const HEART: Vec3 = [-0.2, -0.28, 0];
/** Shortest signed turn from one angle to another. */
const turnTo = (from: number, to: number) =>
  THREE.MathUtils.euclideanModulo(to - from + Math.PI, Math.PI * 2) - Math.PI;

function additive(
  vertexShader: string,
  fragmentShader: string,
  uniforms: Record<string, THREE.IUniform>,
) {
  return new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms,
    transparent: true,
    depthTest: false,
    depthWrite: false,
    blending: THREE.CustomBlending,
    blendEquation: THREE.AddEquation,
    blendSrc: THREE.OneFactor,
    blendDst: THREE.OneFactor,
    blendSrcAlpha: THREE.OneFactor,
    blendDstAlpha: THREE.OneFactor,
  });
}

/** One domain callout while it is being laid out on screen. */
interface Callout {
  x: number;
  y: number;
  /** half extents of the label, px */
  w: number;
  h: number;
  /** where its leader starts: the region itself, on screen */
  ax: number;
  ay: number;
  facing: number;
  placed: boolean;
  /** smoothed position actually drawn */
  sx: number;
  sy: number;
}

function Brain(props: BrainSceneProps) {
  const { layout, store } = props;
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  const live = useRef(props);
  live.current = props;

  /* ---------------------------------------------------------- GPU resources */
  // bumped when live arrivals fill the node or pathway buffers: the buffers
  // are then rebuilt from the store, sized to what it holds now
  const [generation, setGeneration] = useState(0);
  const world = useMemo(() => {
    const u = {
      uTime: { value: 0 },
      uFlow: { value: 0 },
      uForm: { value: 0 },
      uAsOf: { value: 1.1 },
      uTimeline: { value: 0 },
      uDim: { value: 0 },
      uCortexDim: { value: 0 },
      uMotion: { value: 1 },
      uBreath: { value: 0 },
      uScale: { value: 1000 },
      uGain: { value: 1 },
      uPathGain: { value: 1 },
      uFocusDist: { value: 7 },
      uRegionFocus: { value: -1 },
      uRegionGlow: { value: new Float32Array(8) },
      uWave: { value: [0, 1, 2, 3].map(() => new THREE.Vector4(0, 0, 0, ALWAYS)) },
      uWaveGain: { value: new Float32Array(4) },
    };
    const memGain = { value: 1 };
    const cortex = buildCortexGeometry(layout);
    const initial = store.getState();
    // room for what the store already holds plus later arrivals (slots of
    // removed items are not reused)
    const nodes = new NodeBuffers(Math.max(360, initial.nodes.length + 160));
    const paths = new PathBuffers(Math.max(1100, initial.links.length + 600));
    // associations drawn only while focused (filled from focus.extra)
    const overlay = new PathBuffers(OVERLAY_CAPACITY);
    const tracts = buildTracts(layout);
    const rings = buildRingGeometry();
    const hull = buildHull(layout);

    const state = store.getState();
    for (const n of state.nodes) nodes.add(n, ALWAYS);
    for (const l of state.links) {
      const a = store.node(l.source);
      const b = store.node(l.target);
      if (a && b) addLink(paths, l, a, b, ALWAYS);
    }

    const reticle = new THREE.BufferGeometry();
    reticle.setAttribute("position", new THREE.BufferAttribute(new Float32Array(6), 3));
    reticle.setAttribute("aSize", new THREE.BufferAttribute(new Float32Array(2), 1));
    reticle.setAttribute("aKind", new THREE.BufferAttribute(new Float32Array(2), 1));
    reticle.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 8);

    const heart = new THREE.BufferGeometry();
    heart.setAttribute("position", new THREE.BufferAttribute(new Float32Array(HEART), 3));
    heart.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 8);

    const wine = new THREE.Vector3(...hexToRgb(REGION_BY_ID.personal.color));
    const materials = {
      cortex: additive(GLSL.CORTEX_VERT, GLSL.CORTEX_FRAG, u),
      nodes: additive(GLSL.NODE_VERT, GLSL.NODE_FRAG, u),
      paths: additive(GLSL.PATH_VERT, GLSL.PATH_FRAG, u),
      packets: additive(GLSL.PACKET_VERT, GLSL.PACKET_FRAG, u),
      reticle: additive(GLSL.RETICLE_VERT, GLSL.RETICLE_FRAG, u),
      heart: additive(GLSL.GLOW_VERT, GLSL.GLOW_FRAG, { ...u, uColor: { value: wine } }),
      rings: additive(GLSL.RING_VERT, GLSL.RING_FRAG, {
        ...u,
        uColor: { value: new THREE.Vector3(0.88, 0.52, 0.62) },
      }),
      // memory pathways: same shaders, their own ambient gain (tracts keep uPathGain)
      memPaths: additive(GLSL.PATH_VERT, GLSL.PATH_FRAG, { ...u, uPathGain: memGain }),
      memPackets: additive(GLSL.PACKET_VERT, GLSL.PACKET_FRAG, { ...u, uPathGain: memGain }),
    };
    return { u, memGain, cortex, nodes, paths, overlay, tracts, rings, reticle, heart, hull, materials };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- generation only signals a rebuild
  }, [layout, store, generation]);

  useEffect(
    () => () => {
      const { cortex, nodes, paths, overlay, tracts, rings, reticle, heart, materials } = world;
      for (const g of [cortex.geometry, nodes.geometry, paths.lines, paths.packets, overlay.lines, overlay.packets, tracts.lines, tracts.packets, rings, reticle, heart]) {
        g.dispose();
      }
      Object.values(materials).forEach((m) => m.dispose());
    },
    [world],
  );

  /* ------------------------------------------------------------------- rig */
  const rig = useRef({
    orbit: HOME_ORBIT,
    theta: Math.PI + 1.5,
    phi: 0.3,
    dPhi: HOME_PHI,
    radius: 16,
    fit: 7,
    // where the brain sits on the canvas, in px from centre — damped, so
    // opening an overlay glides the brain aside instead of snapping it
    offX: 0,
    offY: 0,
    dOffX: 0,
    dOffY: 0,
    placed: false,
    scale: 1,
    zoom: 1,
    /** sway amplitude the current camera intent asks for … */
    sway: SWAY,
    /** … and what is applied after motion / auto-orbit settings */
    swayNow: SWAY,
    phase: 0,
    target: new THREE.Vector3(...HOME),
    dTarget: new THREE.Vector3(...HOME),
    form: 0,
    pointer: null as { x: number; y: number } | null,
    down: null as { x: number; y: number; moved: boolean } | null,
    /** every pointer currently down, for pinch */
    touches: new Map<number, { x: number; y: number }>(),
    pinch: null as { dist: number; zoom: number } | null,
    /** a pinch just ended: the lifting fingers are not a tap */
    quiet: false,
    hover: null as string | null,
    glow: new Float32Array(8),
    impulse: new Float32Array(8),
    wave: 0,
    nextThought: 5,
    frame: 0,
    seenAsOf: 2,
    labelFade: 0,
    callouts: REGIONS.map<Callout>(() => ({ x: 0, y: 0, w: 40, h: 12, ax: 0, ay: 0, facing: 1, placed: false, sx: 0, sy: 0 })),
    hullX: new Float32Array(world.hull.length / 3),
    hullY: new Float32Array(world.hull.length / 3),
  });

  const fireWave = (at: Vec3, gain: number) => {
    const r = rig.current;
    const slot = r.wave++ % 4;
    world.u.uWave.value[slot].set(at[0], at[1], at[2], world.u.uTime.value);
    world.u.uWaveGain.value[slot] = gain;
  };

  /* camera controls for the dock and keyboard */
  useEffect(() => {
    const r = rig.current;
    const api = props.api;
    api.current = {
      nudge(dTheta, dPhi) {
        r.orbit += dTheta;
        r.dPhi = THREE.MathUtils.clamp(r.dPhi + dPhi, -0.55, 0.95);
      },
      zoomBy(factor) {
        r.zoom = THREE.MathUtils.clamp(r.zoom * factor, 0.42, 1.5);
      },
      reset() {
        r.zoom = 1;
        r.dPhi = HOME_PHI;
        r.orbit += turnTo(r.orbit, HOME_ORBIT);
        r.phase = 0;
      },
    };
    return () => {
      api.current = null;
    };
  }, [props.api]);

  /* fit the brain to whatever the chrome and open overlays leave free */
  useEffect(() => {
    const { left, right, top, bottom } = props.insets;
    const freeW = Math.max(220, size.width - left - right);
    const freeH = Math.max(220, size.height - top - bottom);
    const fit = Math.max((3.9 * size.height) / (2 * TAN * freeW), (2.8 * size.height) / (2 * TAN * freeH));
    const r = rig.current;
    r.fit = THREE.MathUtils.clamp(fit, 3.4, 16);
    r.dOffX = (right - left) / 2;
    r.dOffY = (bottom - top) / 2;
    if (!r.placed) {
      r.placed = true;
      r.offX = r.dOffX;
      r.offY = r.dOffY;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size.width, size.height, props.insets.left, props.insets.right, props.insets.top, props.insets.bottom]);

  /* camera intent */
  useEffect(() => {
    const r = rig.current;
    const { view } = live.current;
    const p = view.position;
    if (view.kind === "home" || !p) {
      r.dTarget.set(...HOME);
      r.scale = 1;
      r.sway = SWAY;
      r.dPhi = HOME_PHI;
      // settle back into the profile, by the shortest way round
      r.orbit += turnTo(r.orbit, HOME_ORBIT);
      r.phase = 0;
      return;
    }
    if (view.kind === "node") {
      r.dTarget.set(p[0] * 0.55, p[1] * 0.55, p[2] * 0.55);
      r.scale = 0.74;
      r.sway = 0.12;
      r.dPhi = THREE.MathUtils.clamp(p[1] * 0.3, -0.12, 0.5);
      if (Math.abs(p[2]) > 0.12) {
        // swing to the hemisphere the memory lives in, by the shortest way round
        r.orbit += turnTo(r.orbit, Math.atan2(p[0] * 0.3, p[2]));
        r.phase = 0;
      }
    } else if (view.kind === "region") {
      r.dTarget.set(p[0] * 0.5, p[1] * 0.5, 0);
      r.scale = 0.88;
      r.sway = 0.34;
      r.dPhi = HOME_PHI;
    } else {
      r.dTarget.set(p[0] * 0.3, p[1] * 0.3, p[2] * 0.3);
      r.scale = 0.92;
      r.sway = 0.3;
    }
  }, [props.view.key]);

  /* replay the assembly */
  useEffect(() => {
    const r = rig.current;
    const still = live.current.calm;
    r.form = still ? 1 : 0;
    r.radius = still ? r.fit : r.fit * 2.1;
    r.theta = r.orbit + (still ? 0 : 1.1);
  }, [props.formKey]);

  /* focus → per-vertex emphasis */
  const overlayLines = useRef<THREE.LineSegments>(null);
  const overlayPackets = useRef<THREE.Points>(null);
  useEffect(() => {
    world.nodes.setStates(props.focus.nodes);
    world.paths.setStates(props.focus.links);
    // associations the simplified drawing leaves out, shown while focused
    const { overlay } = world;
    overlay.clear();
    const lit = new Set<string>();
    const t = world.u.uTime.value;
    for (const extra of props.focus.extra ?? []) {
      const a = store.node(extra.source);
      const b = store.node(extra.target);
      if (!a || !b || overlay.count >= overlay.capacity) continue;
      const link: AtlasLink = { ...extra, basis: "shared-entity", kind: "", born: 0, live: false };
      addLink(overlay, link, a, b, t);
      lit.add(extra.id);
    }
    overlay.setStates(lit);
    // drawn only when there is something to show (the simulation never has)
    if (overlayLines.current) overlayLines.current.visible = overlay.count > 0;
    if (overlayPackets.current) overlayPackets.current.visible = overlay.count > 0;
  }, [props.focus, world, store]);

  /* selection + hover reticle */
  useEffect(() => {
    const position = world.reticle.getAttribute("position") as THREE.BufferAttribute;
    const aSize = world.reticle.getAttribute("aSize") as THREE.BufferAttribute;
    const aKind = world.reticle.getAttribute("aKind") as THREE.BufferAttribute;
    const slots: [string | null, number][] = [
      [props.selectedId, 2],
      [props.hoveredId !== props.selectedId ? props.hoveredId : null, 1],
    ];
    slots.forEach(([id, kind], slot) => {
      const i = id ? world.nodes.index.get(id) : undefined;
      if (i === undefined) {
        aKind.array[slot] = 0;
        return;
      }
      position.array.set(world.nodes.positions.subarray(i * 3, i * 3 + 3), slot * 3);
      aSize.array[slot] = world.nodes.sizes[i] * (kind === 2 ? 4.4 : 3.4);
      aKind.array[slot] = kind;
    });
    position.needsUpdate = aSize.needsUpdate = aKind.needsUpdate = true;
  }, [props.selectedId, props.hoveredId, world]);

  /* store events → animation */
  useEffect(() => {
    const onEvent = ({ event, node, links, removed }: AppliedEvent) => {
      const t = world.u.uTime.value;
      const r = rig.current;
      if (event.type === "memory.learned" && node) {
        const region = REGION_BY_ID[node.region].index;
        world.nodes.add(node, t);
        world.nodes.pulse(node.id, t + 0.5);
        world.cortex.densify(region, node.position, 46, t);
        r.impulse[region] += 0.9;
        fireWave(node.position, 1);
        links.forEach((l, i) => {
          const other = store.node(l.target === node.id ? l.source : l.target);
          if (!other) return;
          const start = t + 0.9 + i * 0.5;
          addLink(world.paths, l, node, other, start);
          world.nodes.pulse(other.id, start + 1.0);
        });
      } else if (event.type === "memory.linked") {
        for (const l of links) {
          const a = store.node(l.source);
          const b = store.node(l.target);
          if (!a || !b) continue;
          addLink(world.paths, l, a, b, t);
          world.nodes.pulse(a.id, t);
          world.nodes.pulse(b.id, t + 1.0);
          r.impulse[REGION_BY_ID[a.region].index] += 0.35;
          r.impulse[REGION_BY_ID[b.region].index] += 0.35;
        }
      } else if (event.type === "memory.reinforced" && node) {
        world.nodes.pulse(node.id, t);
        r.impulse[REGION_BY_ID[node.region].index] += 0.3;
        fireWave(node.position, 0.5);
      } else if (event.type === "record.observed" && node) {
        // a record seen for the first time in this session's snapshots
        world.nodes.add(node, t);
        world.nodes.pulse(node.id, t + 0.5);
        r.impulse[REGION_BY_ID[node.region].index] += 0.6;
        fireWave(node.position, 0.7);
      } else if (event.type === "record.changed" && node) {
        const before = world.nodes.positions.subarray(
          (world.nodes.index.get(node.id) ?? 0) * 3,
          (world.nodes.index.get(node.id) ?? 0) * 3 + 3,
        );
        const moved = before[0] !== node.position[0] || before[1] !== node.position[1] || before[2] !== node.position[2];
        world.nodes.update(node);
        if (moved) {
          // its pathways follow it to the new region
          for (const l of store.linksOf(node.id)) {
            const a = store.node(l.source);
            const b = store.node(l.target);
            world.paths.remove(l.id);
            if (a && b) addLink(world.paths, l, a, b, t);
          }
        }
        world.nodes.pulse(node.id, t);
        r.impulse[REGION_BY_ID[node.region].index] += 0.25;
      } else if (event.type === "link.observed") {
        for (const l of links) {
          const a = store.node(l.source);
          const b = store.node(l.target);
          if (!a || !b) continue;
          addLink(world.paths, l, a, b, t);
          world.nodes.pulse(a.id, t);
          world.nodes.pulse(b.id, t + 1.0);
        }
      }
      if (removed) {
        // withdrawn: out of the scene and out of every index it kept
        for (const id of removed.links) world.paths.remove(id);
        for (const id of removed.nodes) {
          const i = world.nodes.index.get(id);
          if (i !== undefined) fireWave([world.nodes.positions[i * 3], world.nodes.positions[i * 3 + 1], world.nodes.positions[i * 3 + 2]], 0.3);
          world.nodes.remove(id);
        }
      }
      // a new node may be part of the current focus
      world.nodes.setStates(live.current.focus.nodes);
      world.paths.setStates(live.current.focus.links);
      // Full buffers would silently drop what arrives next (the header would
      // count pathways the brain does not draw): rebuild them from the store.
      if (world.nodes.count >= world.nodes.capacity || world.paths.count >= world.paths.capacity) {
        setGeneration((g) => g + 1);
      }
    };
    return store.onEvent(onEvent);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store, world]);

  /* recall: each hop flares its memory and sends a front through the tissue */
  const recallId = props.recall?.trace.id;
  const recallStep = props.recall?.step ?? -1;
  useEffect(() => {
    const recall = live.current.recall;
    if (!recall || recall.step < 0) return;
    const node = store.node(recall.trace.nodes[recall.step]);
    if (!node) return;
    const t = world.u.uTime.value;
    world.nodes.pulse(node.id, t + (recall.step === 0 ? 0 : 0.6));
    rig.current.impulse[REGION_BY_ID[node.region].index] += 0.7;
    fireWave(node.position, 0.9);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recallId, recallStep, store, world]);

  const scratch = useMemo(() => new THREE.Vector3(), []);

  /** Nearest visible memory to the pointer, in screen space. */
  const pick = (reach = 18): string | null => {
    const r = rig.current;
    if (!r.pointer) return null;
    const { nodes, u } = world;
    let best = -1;
    let bestD = reach;
    for (let i = 0; i < nodes.count; i++) {
      if (nodes.born[i] > u.uAsOf.value) continue;
      scratch.fromArray(nodes.positions, i * 3).project(camera);
      if (scratch.z > 1) continue;
      const x = (scratch.x * 0.5 + 0.5) * size.width;
      const y = (-scratch.y * 0.5 + 0.5) * size.height;
      // nearer memories win ties
      const d = Math.hypot(x - r.pointer.x, y - r.pointer.y) + scratch.z * 4;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    }
    return best >= 0 ? nodes.ids[best] : null;
  };

  /* pointer: drag to orbit, wheel or pinch to zoom, hover / tap to pick */
  useEffect(() => {
    const el = live.current.surface.current ?? gl.domElement;
    const canvas = gl.domElement;
    const r = rig.current;
    // pointer positions are kept in canvas space, whatever element reports them
    const local = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };
    const spread = () => {
      const [a, b] = [...r.touches.values()];
      return Math.hypot(a.x - b.x, a.y - b.y);
    };
    const onDown = (e: PointerEvent) => {
      const p = local(e);
      r.touches.set(e.pointerId, p);
      try {
        el.setPointerCapture(e.pointerId);
      } catch {
        /* the pointer is already gone — the gesture still works without capture */
      }
      if (r.touches.size === 2) {
        // second finger: this is a pinch, not a drag or a tap
        r.pinch = { dist: Math.max(spread(), 1), zoom: r.zoom };
        r.down = null;
        r.quiet = true;
        return;
      }
      r.down = { ...p, moved: false };
    };
    const onMove = (e: PointerEvent) => {
      const p = local(e);
      if (r.touches.has(e.pointerId)) r.touches.set(e.pointerId, p);
      if (r.pinch && r.touches.size === 2) {
        // fingers apart → closer
        r.zoom = THREE.MathUtils.clamp((r.pinch.zoom * r.pinch.dist) / Math.max(spread(), 1), 0.42, 1.5);
        return;
      }
      if (r.down) {
        const dx = p.x - r.down.x;
        const dy = p.y - r.down.y;
        if (r.down.moved || Math.hypot(dx, dy) > (e.pointerType === "touch" ? 8 : 4)) {
          r.down = { ...p, moved: true };
          r.orbit -= dx * 0.0055;
          r.dPhi = THREE.MathUtils.clamp(r.dPhi + dy * 0.004, -0.55, 0.95);
        }
      }
      // a finger has no hover: it only points while it is down
      if (e.pointerType !== "touch" || r.down) r.pointer = p;
    };
    const onUp = (e: PointerEvent) => {
      const wasDrag = r.down?.moved;
      const tapped = r.down && !wasDrag;
      r.touches.delete(e.pointerId);
      if (r.touches.size < 2) r.pinch = null;
      r.down = null;
      if (el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId);
      if (r.quiet) {
        if (r.touches.size === 0) r.quiet = false;
        return;
      }
      if (tapped && e.type === "pointerup") {
        r.pointer = local(e);
        live.current.onSelect(pick(e.pointerType === "touch" ? 30 : 18));
      }
      if (e.pointerType === "touch") r.pointer = null;
    };
    const onLeave = () => {
      if (r.down) return;
      r.pointer = null;
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      r.zoom = THREE.MathUtils.clamp(r.zoom * Math.exp(e.deltaY * 0.0011), 0.42, 1.5);
    };
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
    el.addEventListener("pointerleave", onLeave);
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
      el.removeEventListener("pointerleave", onLeave);
      el.removeEventListener("wheel", onWheel);
      el.style.cursor = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gl]);

  /**
   * Domain callouts. Each label belongs to a point on the cortex: the region's
   * anchor on whichever hemisphere faces the camera. The label is pushed out
   * along the line from the brain's centre through that anchor until it clears
   * the silhouette, labels that would overlap are separated, everything is kept
   * inside the free area, and a leader line ties each label back to its region.
   */
  const layoutCallouts = (dt: number, appear: number) => {
    const p = live.current;
    const r = rig.current;
    const anchors = p.anchors.current;
    if (!anchors) return;
    const w = size.width;
    const h = size.height;
    const toScreen = () => {
      scratch.project(camera);
      return [(scratch.x * 0.5 + 0.5) * w, (-scratch.y * 0.5 + 0.5) * h] as const;
    };

    r.labelFade = THREE.MathUtils.damp(r.labelFade, p.labels ? 1 : 0, 7, dt);
    const visible = appear * r.labelFade;

    scratch.set(HOME[0], HOME[1], HOME[2]);
    const [cx, cy] = toScreen();
    const count = world.hull.length / 3;
    for (let i = 0; i < count; i++) {
      scratch.fromArray(world.hull, i * 3);
      const [x, y] = toScreen();
      r.hullX[i] = x - cx;
      r.hullY[i] = y - cy;
    }

    // which hemisphere faces us: -1 … 1, passing through 0 when seen head-on
    const facing = THREE.MathUtils.clamp(((camera.position.z - r.target.z) / r.radius) * 3, -1, 1);
    const bounds = {
      l: p.insets.left + 6,
      r: w - p.insets.right - 6,
      t: p.insets.top + 4,
      b: h - p.insets.bottom - 4,
    };

    REGIONS.forEach((region, i) => {
      const c = r.callouts[i];
      const el = anchors.els.get(`region:${region.id}`) as HTMLElement | undefined;
      if (el && r.frame % 20 === 1) {
        c.w = el.offsetWidth / 2 || c.w;
        c.h = el.offsetHeight / 2 || c.h;
      }
      // head-on, labels split left and right by `side` rather than stacking on the midline
      const hemi = THREE.MathUtils.clamp(facing + (1 - Math.abs(facing)) * region.side * 0.9, -1, 1);
      scratch.set(region.anchor[0], region.anchor[1], region.anchor[2] * hemi);
      const depth = scratch.distanceTo(camera.position);
      [c.ax, c.ay] = toScreen();
      c.facing = THREE.MathUtils.clamp(1.25 - (depth - r.radius) * 0.5, 0.45, 1);

      let dx = c.ax - cx;
      let dy = c.ay - cy;
      const len = Math.hypot(dx, dy);
      if (len < 10) {
        dx = 0;
        dy = -1;
      } else {
        dx /= len;
        dy /= len;
      }
      // how far the silhouette reaches in this direction
      let reach = len;
      for (let k = 0; k < count; k++) reach = Math.max(reach, r.hullX[k] * dx + r.hullY[k] * dy);
      const clear = reach + 20 + Math.abs(dx) * c.w + Math.abs(dy) * c.h;
      c.x = cx + dx * clear;
      c.y = cy + dy * clear;
    });

    // separate overlapping labels, then keep them all on the page
    for (let pass = 0; pass < 6; pass++) {
      for (let i = 0; i < r.callouts.length; i++) {
        for (let j = i + 1; j < r.callouts.length; j++) {
          const a = r.callouts[i];
          const b = r.callouts[j];
          const ox = a.w + b.w + 10 - Math.abs(a.x - b.x);
          const oy = a.h + b.h + 8 - Math.abs(a.y - b.y);
          if (ox <= 0 || oy <= 0) continue;
          if (oy < ox) {
            const push = (oy / 2) * (a.y < b.y || (a.y === b.y && i < j) ? -1 : 1);
            a.y += push;
            b.y -= push;
          } else {
            const push = (ox / 2) * (a.x < b.x || (a.x === b.x && i < j) ? -1 : 1);
            a.x += push;
            b.x -= push;
          }
        }
      }
      for (const c of r.callouts) {
        c.x = THREE.MathUtils.clamp(c.x, bounds.l + c.w, Math.max(bounds.l + c.w, bounds.r - c.w));
        c.y = THREE.MathUtils.clamp(c.y, bounds.t + c.h, Math.max(bounds.t + c.h, bounds.b - c.h));
      }
    }

    REGIONS.forEach((region, i) => {
      const c = r.callouts[i];
      if (!c.placed) {
        c.placed = true;
        c.sx = c.x;
        c.sy = c.y;
      } else {
        // ease toward the target so labels glide rather than jitter
        const k = p.calm ? 1 : 1 - Math.exp(-9 * dt);
        c.sx += (c.x - c.sx) * k;
        c.sy += (c.y - c.sy) * k;
      }
      const el = anchors.els.get(`region:${region.id}`) as HTMLElement | undefined;
      if (el) {
        el.style.transform = `translate3d(${c.sx.toFixed(1)}px, ${c.sy.toFixed(1)}px, 0)`;
        el.style.opacity = (visible * c.facing).toFixed(3);
        el.style.visibility = visible > 0.02 ? "visible" : "hidden";
      }
      // leader: from the region to the nearest edge of its label
      const ex = THREE.MathUtils.clamp(c.ax, c.sx - c.w, c.sx + c.w);
      const ey = THREE.MathUtils.clamp(c.ay, c.sy - c.h, c.sy + c.h);
      const gap = Math.hypot(ex - c.ax, ey - c.ay);
      const lead = visible * c.facing * THREE.MathUtils.smoothstep(gap, 6, 22);
      const line = anchors.els.get(`line:${region.id}`);
      if (line) {
        line.setAttribute("x1", c.ax.toFixed(1));
        line.setAttribute("y1", c.ay.toFixed(1));
        line.setAttribute("x2", ex.toFixed(1));
        line.setAttribute("y2", ey.toFixed(1));
        line.style.opacity = (lead * 0.55).toFixed(3);
      }
      const dot = anchors.els.get(`dot:${region.id}`);
      if (dot) {
        dot.setAttribute("cx", c.ax.toFixed(1));
        dot.setAttribute("cy", c.ay.toFixed(1));
        dot.style.opacity = (lead * 0.9).toFixed(3);
      }
    });
  };

  /* ------------------------------------------------------------ frame loop */
  useFrame((_, rawDelta) => {
    const dt = Math.min(rawDelta, 0.05);
    const r = rig.current;
    const p = live.current;
    const { u } = world;
    const damp = THREE.MathUtils.damp;
    const still = p.calm;
    const cursorEl = p.surface.current ?? gl.domElement;
    r.frame++;

    u.uTime.value += dt;
    if (!still) u.uFlow.value += dt;
    const t = u.uTime.value;

    // assembly
    r.form = still ? 1 : Math.min(1, r.form + dt / 4.6);
    u.uForm.value = r.form;
    u.uMotion.value = damp(u.uMotion.value, still ? 0 : 1, 4, dt);
    u.uBreath.value = 0.006 * Math.sin(u.uFlow.value * 0.8) * u.uMotion.value;
    u.uAsOf.value = damp(u.uAsOf.value, p.asOf, 7, dt);
    u.uTimeline.value = p.timeline ? 1 : 0;
    u.uGain.value = damp(u.uGain.value, p.visuals.glow, 5, dt);
    u.uPathGain.value = damp(u.uPathGain.value, p.visuals.pathways ? 1 : 0, 5, dt);
    const drawnLinks = store.getState().links.length;
    const density = p.adaptiveGlow
      ? Math.max(DENSITY_FLOOR, Math.min(1, Math.sqrt(DENSITY_REF / Math.max(1, drawnLinks))))
      : 1;
    world.memGain.value = damp(world.memGain.value, (p.visuals.pathways ? 1 : 0) * density, 5, dt);

    // focus
    u.uDim.value = damp(u.uDim.value, p.focus.dim, 4.5, dt);
    u.uCortexDim.value = damp(u.uCortexDim.value, p.focus.region < 0 ? p.focus.dim : 0, 4.5, dt);
    if (p.focus.region >= 0) u.uRegionFocus.value = p.focus.region;
    else if (p.focus.dim > 0 || u.uDim.value < 0.03) u.uRegionFocus.value = -1;

    // timeline: every memory the marker has just reached stirs its region
    const asOf = u.uAsOf.value;
    if (p.timeline && asOf > r.seenAsOf + 1e-4) {
      let fronts = 0;
      for (let i = 0; i < world.nodes.count; i++) {
        const born = world.nodes.born[i];
        if (born <= r.seenAsOf || born > asOf) continue;
        const node = store.node(world.nodes.ids[i]);
        if (!node) continue;
        const region = REGION_BY_ID[node.region].index;
        r.impulse[region] = Math.min(r.impulse[region] + 0.3, 1.2);
        if (!still && fronts++ < 1) fireWave(node.position, 0.4);
      }
    }
    r.seenAsOf = asOf;

    // region glow = steady highlight + decaying impulses from events
    for (let i = 0; i < 7; i++) {
      const base = Math.max(p.hotRegion === i ? 0.34 : 0, p.focus.region === i ? 0.14 : 0);
      r.glow[i] = damp(r.glow[i], base, 5, dt);
      r.impulse[i] *= Math.exp(-dt * 1.15);
      u.uRegionGlow.value[i] = r.glow[i] + Math.min(r.impulse[i], 1.4);
    }

    // idle thought: now and then a memory stirs on its own
    if (!still && r.form >= 1 && t > r.nextThought && world.nodes.count) {
      r.nextThought = t + 1.4 + Math.random() * 2.6;
      const i = Math.floor(Math.random() * world.nodes.count);
      if (p.idleMemories === false) {
        r.impulse[Math.floor(Math.random() * 7)] += 0.12;
      } else if (world.nodes.born[i] <= asOf) {
        const node = store.node(world.nodes.ids[i]);
        if (node) {
          world.nodes.pulse(node.id, t);
          r.impulse[REGION_BY_ID[node.region].index] += 0.16;
          if (Math.random() < 0.4) fireWave(node.position, 0.32);
        }
      }
    }

    // camera — eased while in motion, immediate when motion is off
    const ease = still ? 14 : 1;
    const swaying = !still && p.visuals.orbit;
    if (swaying && !r.down) r.phase += dt * 0.085;
    r.swayNow = damp(r.swayNow, swaying ? r.sway : 0, 3, dt);
    r.theta = damp(r.theta, r.orbit + r.swayNow * Math.sin(r.phase), 2.4 * ease, dt);
    r.phi = damp(r.phi, r.dPhi, 2.4 * ease, dt);
    r.radius = damp(r.radius, r.fit * r.scale * r.zoom, 1.9 * ease, dt);
    r.offX = damp(r.offX, r.dOffX, 3.2 * ease, dt);
    r.offY = damp(r.offY, r.dOffY, 3.2 * ease, dt);
    r.target.lerp(r.dTarget, 1 - Math.exp(-2.2 * ease * dt));
    camera.setViewOffset(size.width, size.height, r.offX, r.offY, size.width, size.height);
    const cp = Math.cos(r.phi);
    camera.position.set(
      r.target.x + r.radius * Math.sin(r.theta) * cp,
      r.target.y + r.radius * Math.sin(r.phi),
      r.target.z + r.radius * Math.cos(r.theta) * cp,
    );
    camera.lookAt(r.target);
    camera.updateMatrixWorld();
    u.uFocusDist.value = r.radius;
    u.uScale.value = gl.domElement.height / (2 * TAN);

    // hover
    if (r.down?.moved || r.pinch) {
      cursorEl.style.cursor = "grabbing";
    } else if (r.frame % 2 === 0) {
      const hit = r.pointer ? pick() : null;
      if (hit !== r.hover) {
        r.hover = hit;
        p.onHover(hit);
      }
      cursorEl.style.cursor = hit ? "pointer" : "grab";
    }

    // DOM in brain space: domain callouts, then anything pinned to a point
    const appear = THREE.MathUtils.smoothstep(r.form, 0.82, 1);
    layoutCallouts(dt, appear);
    const anchors = p.anchors.current;
    if (anchors) {
      anchors.positions.forEach((at, key) => {
        const el = anchors.els.get(key) as HTMLElement | undefined;
        if (!el) return;
        scratch.set(at[0], at[1], at[2]).multiplyScalar(1 + u.uBreath.value).project(camera);
        const x = (scratch.x * 0.5 + 0.5) * size.width;
        const y = (-scratch.y * 0.5 + 0.5) * size.height;
        el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
        el.style.opacity = appear.toFixed(3);
      });
      const hover = anchors.els.get("hover") as HTMLElement | undefined;
      if (hover && !anchors.positions.has("hover")) hover.style.opacity = "0";
    }
  });

  const { materials } = world;
  return (
    <group>
      <points geometry={world.rings} material={materials.rings} frustumCulled={false} />
      <points geometry={world.heart} material={materials.heart} frustumCulled={false} />
      <lineSegments geometry={world.tracts.lines} material={materials.paths} frustumCulled={false} />
      <points geometry={world.tracts.packets} material={materials.packets} frustumCulled={false} />
      <points geometry={world.cortex.geometry} material={materials.cortex} frustumCulled={false} />
      <lineSegments geometry={world.paths.lines} material={materials.memPaths} frustumCulled={false} />
      <points geometry={world.paths.packets} material={materials.memPackets} frustumCulled={false} />
      <lineSegments ref={overlayLines} visible={false} geometry={world.overlay.lines} material={materials.memPaths} frustumCulled={false} />
      <points ref={overlayPackets} visible={false} geometry={world.overlay.packets} material={materials.memPackets} frustumCulled={false} />
      {props.recall &&
        props.recall.trace.links.slice(0, Math.max(0, props.recall.step)).map((linkId, i) => (
          <TraceSegment
            key={`${props.recall!.trace.id}-${linkId}`}
            store={store}
            from={props.recall!.trace.nodes[i]}
            to={props.recall!.trace.nodes[i + 1]}
            uniforms={world.u}
          />
        ))}
      <points geometry={world.nodes.geometry} material={materials.nodes} frustumCulled={false} />
      <points geometry={world.reticle} material={materials.reticle} frustumCulled={false} />
    </group>
  );
}

/** One hop of a recall: a thin bright tube with a soft sheath, drawn on from its source. */
function TraceSegment({
  store,
  from,
  to,
  uniforms,
}: {
  store: AtlasStore;
  from: string;
  to: string;
  uniforms: { uTime: THREE.IUniform<number>; uFlow: THREE.IUniform<number>; uBreath: THREE.IUniform<number> };
}) {
  const built = useMemo(() => {
    const a = store.node(from);
    const b = store.node(to);
    if (!a || !b) return null;
    const curve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(...a.position),
      new THREE.Vector3(...linkControl(a.position, b.position)),
      new THREE.Vector3(...b.position),
    );
    const make = (radius: number, gain: number) => {
      const material = additive(GLSL.TRACE_VERT, GLSL.TRACE_FRAG, {
        uTime: uniforms.uTime,
        uFlow: uniforms.uFlow,
        uBreath: uniforms.uBreath,
        uStart: { value: uniforms.uTime.value },
        uGain: { value: gain },
        uColorA: { value: new THREE.Vector3(...REGION_RGB[REGION_BY_ID[a.region].index]) },
        uColorB: { value: new THREE.Vector3(...REGION_RGB[REGION_BY_ID[b.region].index]) },
      });
      material.side = THREE.DoubleSide;
      return { geometry: new THREE.TubeGeometry(curve, 30, radius, 6, false), material };
    };
    return [make(0.0065, 1), make(0.028, 0.13)];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store, from, to]);

  useEffect(
    () => () => {
      built?.forEach((m) => {
        m.geometry.dispose();
        m.material.dispose();
      });
    },
    [built],
  );

  if (!built) return null;
  return (
    <>
      {built.map((m, i) => (
        <mesh key={i} geometry={m.geometry} material={m.material} frustumCulled={false} />
      ))}
    </>
  );
}

export function BrainScene(props: BrainSceneProps) {
  // R3F's own ResizeObserver can miss late layout shifts and leave the canvas
  // at 300x150 (see presence/orb-scene.tsx) — nudge a re-measure once mounted.
  useEffect(() => {
    const fire = () => window.dispatchEvent(new Event("resize"));
    const raf = requestAnimationFrame(fire);
    const timers = [setTimeout(fire, 150), setTimeout(fire, 400)];
    return () => {
      cancelAnimationFrame(raf);
      timers.forEach(clearTimeout);
    };
  }, []);

  return (
    <Canvas
      camera={{ fov: FOV, near: 0.1, far: 80, position: [0, 0, 16] }}
      dpr={[1, 1.75]}
      frameloop={props.paused ? "never" : "always"}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ background: "transparent", pointerEvents: "none" }}
    >
      <Brain {...props} />
    </Canvas>
  );
}
