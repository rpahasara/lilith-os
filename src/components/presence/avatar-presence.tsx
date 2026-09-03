"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import dynamic from "next/dynamic";
import type { PresenceSignal } from "@/lib/presence";
import { hsinLipSync, type VisemeCue } from "@/lib/hsin-lip-sync";
import type {
  FaceExpressionState,
  ExpressionInspectName,
  VisemeInspectName,
  HandInspectionView,
  ArmIkTargets,
  HandOrientationTargets,
  ForearmCorrection,
  CanonicalNeutralQuaternions,
  NeutralCalibrationTargets,
  PoseInspectionView,
  PoseTestMode,
  RelaxedPoseTuning,
} from "./avatar-scene";

const SHOW_CALIBRATION_DEBUG = process.env.NODE_ENV !== "production";
const POSE_MODES: PoseTestMode[] = [
  "authored",
  "vrmaIdle",
  "naturalIdle",
  ...(SHOW_CALIBRATION_DEBUG
    ? (["hsinNeutral", "normalizedRest"] satisfies PoseTestMode[])
    : []),
];

function relaxedFingerCurl(side: "left" | "right"): RelaxedPoseTuning {
  const prefix = side === "left" ? "left" : "right";
  const bend = side === "left" ? -1 : 1;
  const thumbSpread = side === "left" ? 14 : 12;
  const thumbCurl = side === "left" ? 4 : 3;
  const finger = (
    name: "Index" | "Middle" | "Ring" | "Little",
    proximal: number,
    intermediate: number,
    distal: number,
  ) => ({
    [`${prefix}${name}Proximal`]: [0, 0, bend * proximal],
    [`${prefix}${name}Intermediate`]: [0, 0, bend * intermediate],
    [`${prefix}${name}Distal`]: [0, 0, bend * distal],
  });

  return {
    [`${prefix}ThumbMetacarpal`]: [3, bend * thumbSpread, bend * 2],
    [`${prefix}ThumbProximal`]: [1, bend * 3, bend * thumbCurl],
    [`${prefix}ThumbDistal`]: [0, 0, bend * 2],
    ...finger("Index", 4, 7, 2),
    ...finger("Middle", 6, 9, 3),
    ...finger("Ring", 8, 11, 4),
    ...finger("Little", 10, 13, 5),
  } as RelaxedPoseTuning;
}

const INITIAL_RELAXED_POSE: RelaxedPoseTuning = {
  leftShoulder: [0, 1, -5],
  leftUpperArm: [0, 0, -8],
  leftLowerArm: [0, 0, -12],
  leftHand: [1, -2, -1],
  rightShoulder: [0, -1, 4],
  rightUpperArm: [0, 0, 8],
  rightLowerArm: [0, 0, 14],
  rightHand: [1, 2, 1],
  neck: [0, 1, -1],
  head: [1, -2, 1],
  upperChest: [0, 1, 0],
  chest: [0, 1, -1],
  ...relaxedFingerCurl("left"),
  ...relaxedFingerCurl("right"),
};

const INITIAL_HSIN_NEUTRAL_POSE: RelaxedPoseTuning = {
  leftShoulder: [0, 0, -3],
  leftUpperArm: [1, -2, -72],
  leftLowerArm: [0, 0, -12],
  leftHand: [0, 0, 0],
  rightShoulder: [0, 0, 2],
  rightUpperArm: [-2, 3, 69],
  rightLowerArm: [0, 0, 14],
  rightHand: [0, 0, 0],
  chest: [0, 0, 0],
  upperChest: [0, 0, 0],
  neck: [0, 0, 0],
  head: [0, 0, 0],
  ...relaxedFingerCurl("left"),
  ...relaxedFingerCurl("right"),
};

const INITIAL_NEUTRAL_TARGETS: NeutralCalibrationTargets = {
  left: {
    elbow: [0.17, 0.04, 0.035],
    wrist: [0.135, 0.264, -0.073],
  },
  right: {
    elbow: [-0.17, 0.06, 0.05],
    wrist: [-0.215, 0.25, -0.009],
  },
};

const INITIAL_ARM_IK_TARGETS: ArmIkTargets = {
  left: [-0.16, 0.23, 0.04],
  right: [0.16, 0.28, 0.06],
};

const INITIAL_HAND_ORIENTATION_TARGETS: HandOrientationTargets = {
  left: [2, -6, -2],
  right: [-1, 8, 3],
};

const INITIAL_FOREARM_CORRECTION: ForearmCorrection = {
  left: [0, 0, -45],
  right: [0, 0, 40],
};

const TUNING_BONES = Object.keys(INITIAL_RELAXED_POSE) as Array<
  keyof RelaxedPoseTuning
>;

const EXPRESSION_INSPECT_NAMES: ExpressionInspectName[] = [
  "happy",
  "puzzled",
  "angry",
  "sad",
  "surprised",
  "relaxed",
  "squint",
  "laugh",
  "meow",
  "openSmall",
  "neutral",
];

const VISEME_INSPECT_NAMES: VisemeInspectName[] = ["aa", "ih", "ou", "ee", "oh"];

const TIMED_SPEECH_TEST_CUES: VisemeCue[] = [
  { viseme: "aa", startMs: 0, durationMs: 260 },
  { viseme: "ih", startMs: 320 },
  { viseme: "ou", startMs: 680 },
  { viseme: "sil", startMs: 1020, durationMs: 220 },
  { viseme: "ee", startMs: 1300 },
  { viseme: "oh", startMs: 1660 },
  { viseme: "aa", startMs: 2020, weight: 0.85 },
  { viseme: "sil", startMs: 2380, durationMs: 180 },
  { viseme: "ou", startMs: 2640 },
  { viseme: "ih", startMs: 3000 },
  { viseme: "ee", startMs: 3340 },
  { viseme: "oh", startMs: 3680 },
  { viseme: "sil", startMs: 4020, durationMs: 260 },
];

// Load the WebGL scene only on the client; soft glow while it boots.
const AvatarScene = dynamic(
  () => import("./avatar-scene").then((m) => m.AvatarScene),
  {
    ssr: false,
    loading: () => (
      <div className="absolute inset-0 grid place-items-center">
        <div className="h-44 w-32 rounded-full bg-gradient-to-b from-violet-bright/30 to-cyan-bright/20 blur-2xl animate-breathe" />
      </div>
    ),
  },
);

export function AvatarPresence({
  signal,
  paused = false,
}: {
  signal: PresenceSignal;
  paused?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [poseMode, setPoseMode] = useState<PoseTestMode>("naturalIdle");
  const [poseTuning, setPoseTuning] =
    useState<RelaxedPoseTuning>(INITIAL_RELAXED_POSE);
  const [inspectPose, setInspectPose] = useState(false);
  const [inspectionView, setInspectionView] =
    useState<PoseInspectionView>("front");
  const [springsEnabled, setSpringsEnabled] = useState(false);
  const [autoBlinkEnabled, setAutoBlinkEnabled] = useState(true);
  const [manualBlinkSequence, setManualBlinkSequence] = useState(0);
  const [lookAtEnabled, setLookAtEnabled] = useState(true);
  const [lookAtStrength, setLookAtStrength] = useState(0.45);
  const [centerEyesSequence, setCenterEyesSequence] = useState(0);
  const [headAttentionEnabled, setHeadAttentionEnabled] = useState(true);
  const [headAttentionStrength, setHeadAttentionStrength] = useState(1);
  const [centerHeadSequence, setCenterHeadSequence] = useState(0);
  const [forcedExpressionState, setForcedExpressionState] =
    useState<FaceExpressionState | null>(null);
  const [expressionInspectEnabled, setExpressionInspectEnabled] =
    useState(false);
  const [expressionInspectName, setExpressionInspectName] =
    useState<ExpressionInspectName>("happy");
  const [expressionInspectWeight, setExpressionInspectWeight] = useState(0.5);
  const [visemeInspectEnabled, setVisemeInspectEnabled] = useState(false);
  const [visemeInspectName, setVisemeInspectName] =
    useState<VisemeInspectName>("aa");
  const [visemeInspectWeight, setVisemeInspectWeight] = useState(0.5);
  const [fakeSpeechEnabled, setFakeSpeechEnabled] = useState(false);
  const speechPlayback = useSyncExternalStore(
    hsinLipSync.subscribe,
    hsinLipSync.getSnapshot,
    hsinLipSync.getServerSnapshot,
  );
  const [handInspectionView, setHandInspectionView] =
    useState<HandInspectionView | null>(null);
  const [revealHands, setRevealHands] = useState(true);
  const [handOverrideEnabled, setHandOverrideEnabled] = useState(true);
  const [forearmOverrideEnabled, setForearmOverrideEnabled] = useState(false);
  const [forearmCorrection, setForearmCorrection] = useState<ForearmCorrection>(
    INITIAL_FOREARM_CORRECTION,
  );
  const [neutralPose] = useState<RelaxedPoseTuning>(
    INITIAL_HSIN_NEUTRAL_POSE,
  );
  const [neutralTargets, setNeutralTargets] =
    useState<NeutralCalibrationTargets>(INITIAL_NEUTRAL_TARGETS);
  const [canonicalNeutral, setCanonicalNeutral] =
    useState<CanonicalNeutralQuaternions>({});
  const [valuesCopied, setValuesCopied] = useState(false);
  const [debugPanelCollapsed, setDebugPanelCollapsed] = useState(false);
  const [armIkTargets, setArmIkTargets] = useState<ArmIkTargets>(
    INITIAL_ARM_IK_TARGETS,
  );
  const [handOrientationTargets, setHandOrientationTargets] =
    useState<HandOrientationTargets>(INITIAL_HAND_ORIENTATION_TARGETS);
  const handleCanonicalNeutralChange = useCallback(
    (pose: CanonicalNeutralQuaternions) => {
      setCanonicalNeutral(pose);
      setValuesCopied(false);
    },
    [],
  );

  // Same container-observed re-measure the orb uses (see presence-orb).
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() =>
        window.dispatchEvent(new Event("resize")),
      );
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div ref={ref} className="relative h-full w-full">
      {/* soft backlight for depth — dimmer than the orb bloom */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-[70%] w-[55%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,rgba(139,92,246,0.22),rgba(34,211,238,0.08)_50%,transparent_72%)] blur-2xl" />
      <AvatarScene
        signal={signal}
        paused={paused}
        poseMode={poseMode}
        poseTuning={poseTuning}
        inspectPose={inspectPose}
        inspectionView={inspectionView}
        springsEnabled={
          expressionInspectEnabled || visemeInspectEnabled
            ? false
            : springsEnabled
        }
        autoBlinkEnabled={autoBlinkEnabled}
        manualBlinkSequence={manualBlinkSequence}
        lookAtEnabled={lookAtEnabled}
        lookAtStrength={lookAtStrength}
        centerEyesSequence={centerEyesSequence}
        headAttentionEnabled={headAttentionEnabled}
        headAttentionStrength={headAttentionStrength}
        centerHeadSequence={centerHeadSequence}
        forcedExpressionState={forcedExpressionState}
        expressionInspectEnabled={expressionInspectEnabled}
        expressionInspectName={expressionInspectName}
        expressionInspectWeight={expressionInspectWeight}
        visemeInspectEnabled={visemeInspectEnabled}
        visemeInspectName={visemeInspectName}
        visemeInspectWeight={visemeInspectWeight}
        fakeSpeechEnabled={fakeSpeechEnabled}
        speechPlayback={speechPlayback}
        handInspectionView={handInspectionView}
        revealHands={
          (handInspectionView !== null || poseMode === "hsinNeutral") &&
          revealHands
        }
        handOverrideEnabled={handOverrideEnabled}
        forearmOverrideEnabled={forearmOverrideEnabled}
        forearmCorrection={forearmCorrection}
        neutralPose={neutralPose}
        neutralTargets={neutralTargets}
        onCanonicalNeutralChange={handleCanonicalNeutralChange}
        armIkTargets={armIkTargets}
        handOrientationTargets={handOrientationTargets}
      />
      {SHOW_CALIBRATION_DEBUG && <aside className={`fixed right-4 top-[120px] z-[100] max-h-[calc(100vh-160px)] overflow-y-auto rounded-xl border border-white/10 bg-black/80 shadow-2xl backdrop-blur-md ${debugPanelCollapsed ? "w-11" : "w-[300px] p-2"} max-[900px]:w-11 max-[900px]:p-0`}>
        <button
          type="button"
          aria-label={debugPanelCollapsed ? "Expand debug controls" : "Collapse debug controls"}
          onClick={() => setDebugPanelCollapsed((current) => !current)}
          className="sticky top-0 ml-auto grid h-10 w-10 place-items-center rounded-lg bg-black/80 text-base text-white/75 hover:text-white"
        >
          {debugPanelCollapsed ? "◀" : "▶"}
        </button>
        <div className={`${debugPanelCollapsed ? "hidden" : "space-y-2"} max-[900px]:hidden`}>
      <div className="grid grid-cols-2 gap-1 rounded-lg border border-white/10 p-1 text-[10px] uppercase tracking-wider">
        {POSE_MODES.map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => {
              setPoseMode(mode);
              if (mode === "hsinNeutral" || mode === "normalizedRest") {
                setInspectPose(true);
                setSpringsEnabled(false);
                setForearmOverrideEnabled(false);
              }
            }}
            className={`rounded-full px-3 py-1.5 transition ${
              poseMode === mode
                ? "bg-violet-bright/30 text-white"
                : "text-white/55 hover:text-white"
            }`}
          >
            {mode === "vrmaIdle"
              ? "VRMA Diagnostic"
              : mode === "naturalIdle"
                ? "Natural Idle V2"
                : mode === "hsinNeutral"
                  ? "Hsin Neutral Calibration"
                  : mode === "normalizedRest"
                    ? "Normalized Rest Test"
                : "Authored"}
          </button>
        ))}
      </div>
      <button
        type="button"
        onClick={() => setSpringsEnabled((current) => !current)}
        className={`w-full rounded-lg border border-white/10 px-3 py-2 text-[10px] uppercase tracking-wider ${springsEnabled ? "bg-amber-400/25 text-amber-100" : "bg-emerald-400/20 text-emerald-100"}`}
      >
        Springs Test {springsEnabled ? "On" : "Off"}
      </button>
      <div className="grid grid-cols-2 gap-1">
        <button
          type="button"
          onClick={() => setAutoBlinkEnabled((current) => !current)}
          className={`rounded-lg border border-white/10 px-2 py-2 text-[10px] uppercase tracking-wider ${autoBlinkEnabled ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
        >
          Auto Blink {autoBlinkEnabled ? "On" : "Off"}
        </button>
        <button
          type="button"
          onClick={() => setManualBlinkSequence((current) => current + 1)}
          className="rounded-lg border border-white/10 bg-violet-400/20 px-2 py-2 text-[10px] uppercase tracking-wider text-violet-100"
        >
          Manual Blink Test
        </button>
      </div>
      <div className="space-y-2 rounded-lg border border-white/10 bg-black/35 p-2">
        <div className="grid grid-cols-2 gap-1">
          <button
            type="button"
            onClick={() => setLookAtEnabled((current) => !current)}
            className={`rounded px-2 py-1.5 text-[10px] uppercase tracking-wider ${lookAtEnabled ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
          >
            LookAt {lookAtEnabled ? "On" : "Off"}
          </button>
          <button
            type="button"
            onClick={() => setCenterEyesSequence((current) => current + 1)}
            className="rounded bg-violet-400/20 px-2 py-1.5 text-[10px] uppercase tracking-wider text-violet-100"
          >
            Center Eyes
          </button>
        </div>
        <label className="block text-[10px] uppercase tracking-wider text-white/60">
          LookAt strength {lookAtStrength.toFixed(2)}
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={lookAtStrength}
            onChange={(event) => setLookAtStrength(Number(event.target.value))}
            className="mt-1 block w-full"
          />
        </label>
      </div>
      <div className="space-y-1 rounded-lg border border-white/10 bg-black/35 p-2">
        <div className="text-[10px] uppercase tracking-wider text-white/50">
          State Expression
        </div>
        <div className="grid grid-cols-2 gap-1">
          {(["idle", "listening", "thinking", "speaking"] as const).map(
            (state) => (
              <button
                key={state}
                type="button"
                onClick={() => {
                  setExpressionInspectEnabled(false);
                  setForcedExpressionState(state);
                }}
                className={`rounded px-2 py-1.5 text-[10px] uppercase tracking-wider ${forcedExpressionState === state ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
              >
                Force {state}
              </button>
            ),
          )}
        </div>
        <button
          type="button"
          onClick={() => setForcedExpressionState(null)}
          className="w-full rounded bg-violet-400/20 px-2 py-1.5 text-[10px] uppercase tracking-wider text-violet-100"
        >
          Follow App State
        </button>
      </div>
      <div className="space-y-2 rounded-lg border border-fuchsia-300/20 bg-fuchsia-950/20 p-2">
        <button
          type="button"
          onClick={() => {
            setExpressionInspectEnabled((current) => {
              if (!current) {
                setHandInspectionView(null);
                setInspectPose(false);
                setSpringsEnabled(false);
                setVisemeInspectEnabled(false);
                setFakeSpeechEnabled(false);
              }
              return !current;
            });
          }}
          className={`w-full rounded px-2 py-1.5 text-[10px] uppercase tracking-wider ${expressionInspectEnabled ? "bg-fuchsia-400/25 text-fuchsia-100" : "bg-black/40 text-white/55"}`}
        >
          Expression Inspect {expressionInspectEnabled ? "On" : "Off"}
        </button>
        {expressionInspectEnabled && (
          <>
            <div className="grid grid-cols-2 gap-1">
              {EXPRESSION_INSPECT_NAMES.map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => setExpressionInspectName(name)}
                  className={`rounded px-2 py-1 text-[10px] ${expressionInspectName === name ? "bg-fuchsia-400/25 text-fuchsia-100" : "bg-black/40 text-white/55"}`}
                >
                  {name}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-4 gap-1">
              {[0.25, 0.5, 0.75, 1].map((weight) => (
                <button
                  key={weight}
                  type="button"
                  onClick={() => setExpressionInspectWeight(weight)}
                  className={`rounded px-1 py-1 text-[10px] ${expressionInspectWeight === weight ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
                >
                  {weight.toFixed(2)}
                </button>
              ))}
            </div>
            <label className="block text-[10px] uppercase tracking-wider text-white/60">
              {expressionInspectName} {expressionInspectWeight.toFixed(2)}
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={expressionInspectWeight}
                onChange={(event) =>
                  setExpressionInspectWeight(Number(event.target.value))
                }
                className="mt-1 block w-full"
              />
            </label>
          </>
        )}
      </div>
      <div className="space-y-2 rounded-lg border border-rose-300/20 bg-rose-950/20 p-2">
        <button
          type="button"
          onClick={() => {
            setVisemeInspectEnabled((current) => {
              if (!current) {
                setExpressionInspectEnabled(false);
                setFakeSpeechEnabled(false);
                setSpringsEnabled(false);
                setHandInspectionView(null);
                setInspectPose(false);
              }
              return !current;
            });
          }}
          className={`w-full rounded px-2 py-1.5 text-[10px] uppercase tracking-wider ${visemeInspectEnabled ? "bg-rose-400/25 text-rose-100" : "bg-black/40 text-white/55"}`}
        >
          Viseme Inspect {visemeInspectEnabled ? "On" : "Off"}
        </button>
        {visemeInspectEnabled && (
          <>
            <div className="grid grid-cols-3 gap-1">
              {VISEME_INSPECT_NAMES.map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => {
                    setVisemeInspectName(name);
                    if (visemeInspectWeight === 0) setVisemeInspectWeight(0.5);
                  }}
                  className={`rounded px-2 py-1 text-[10px] uppercase ${visemeInspectName === name && visemeInspectWeight > 0 ? "bg-rose-400/25 text-rose-100" : "bg-black/40 text-white/55"}`}
                >
                  {name}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setVisemeInspectWeight(0)}
                className="rounded bg-black/40 px-2 py-1 text-[10px] uppercase text-white/55"
              >
                Close
              </button>
            </div>
            <div className="grid grid-cols-4 gap-1">
              {[0.25, 0.5, 0.75, 1].map((weight) => (
                <button
                  key={weight}
                  type="button"
                  onClick={() => setVisemeInspectWeight(weight)}
                  className={`rounded px-1 py-1 text-[10px] ${visemeInspectWeight === weight ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
                >
                  {weight.toFixed(2)}
                </button>
              ))}
            </div>
            <label className="block text-[10px] uppercase tracking-wider text-white/60">
              {visemeInspectName} {visemeInspectWeight.toFixed(2)}
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={visemeInspectWeight}
                onChange={(event) =>
                  setVisemeInspectWeight(Number(event.target.value))
                }
                className="mt-1 block w-full"
              />
            </label>
          </>
        )}
        <button
          type="button"
          onClick={() => {
            setFakeSpeechEnabled((current) => {
              const next = !current;
              setVisemeInspectEnabled(false);
              setExpressionInspectEnabled(false);
              setForcedExpressionState(next ? "speaking" : null);
              return next;
            });
          }}
          className={`w-full rounded px-2 py-1.5 text-[10px] uppercase tracking-wider ${fakeSpeechEnabled ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
        >
          Fake Speech {fakeSpeechEnabled ? "On" : "Off"}
        </button>
        <div className="grid grid-cols-2 gap-1">
          <button
            type="button"
            onClick={() => {
              setFakeSpeechEnabled(false);
              setVisemeInspectEnabled(false);
              setExpressionInspectEnabled(false);
              setForcedExpressionState(null);
              hsinLipSync.startSpeech(TIMED_SPEECH_TEST_CUES);
            }}
            className={`rounded px-2 py-1.5 text-[10px] uppercase tracking-wider ${speechPlayback.status !== "idle" ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
          >
            Play Timed Speech
          </button>
          <button
            type="button"
            onClick={() => hsinLipSync.stopSpeech()}
            className="rounded bg-black/40 px-2 py-1.5 text-[10px] uppercase tracking-wider text-white/55"
          >
            Stop Speech
          </button>
        </div>
      </div>
      <div className="space-y-2 rounded-lg border border-white/10 bg-black/35 p-2">
        <div className="grid grid-cols-2 gap-1">
          <button
            type="button"
            onClick={() => setHeadAttentionEnabled((current) => !current)}
            className={`rounded px-2 py-1.5 text-[10px] uppercase tracking-wider ${headAttentionEnabled ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
          >
            Head Attention {headAttentionEnabled ? "On" : "Off"}
          </button>
          <button
            type="button"
            onClick={() => setCenterHeadSequence((current) => current + 1)}
            className="rounded bg-violet-400/20 px-2 py-1.5 text-[10px] uppercase tracking-wider text-violet-100"
          >
            Center Head
          </button>
        </div>
        <label className="block text-[10px] uppercase tracking-wider text-white/60">
          Head strength {headAttentionStrength.toFixed(2)}
          <input
            type="range"
            min={0}
            max={1.5}
            step={0.05}
            value={headAttentionStrength}
            onChange={(event) =>
              setHeadAttentionStrength(Number(event.target.value))
            }
            className="mt-1 block w-full"
          />
        </label>
      </div>
      {SHOW_CALIBRATION_DEBUG && poseMode === "hsinNeutral" && (
        <div className="space-y-1 rounded-lg border border-emerald-300/20 bg-emerald-950/20 p-2 text-[10px] text-white/70">
          <div className="uppercase tracking-wider text-emerald-200">
            Canonical arm-chain calibration
          </div>
          <div className="grid grid-cols-2 gap-1">
            {([
              ["front", "Front"],
              ["leftThreeQuarter", "Left 3/4"],
              ["rightThreeQuarter", "Right 3/4"],
              ["side", "Side"],
            ] as const).map(([view, label]) => (
              <button
                key={view}
                type="button"
                onClick={() => setInspectionView(view)}
                className={`rounded px-2 py-1 uppercase tracking-wider ${inspectionView === view ? "bg-emerald-400/25 text-emerald-100" : "bg-black/40 text-white/60"}`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="text-white/55">
            Targets are hips-relative world offsets. Large markers are targets;
            small markers are the rendered elbow/wrist positions.
          </div>
          <button
            type="button"
            onClick={() => setRevealHands((current) => !current)}
            className={`w-full rounded px-2 py-1.5 uppercase tracking-wider ${revealHands ? "bg-rose-400/25 text-rose-100" : "bg-black/40 text-white/60"}`}
          >
            Arm Cloth {revealHands ? "Hidden" : "Visible"}
          </button>
          {(["left", "right"] as const).map((side) => (
            <fieldset key={side} className="border-t border-white/10 pt-1">
              <legend className="pr-1 capitalize text-white/90">{side} arm targets</legend>
              {(["elbow", "wrist"] as const).map((joint) => (
                <div key={joint} className="mb-1">
                  <div className="capitalize text-white/75">{joint}</div>
                  {(["X", "Y", "Z"] as const).map((axis, axisIndex) => (
                    <label key={axis} className="grid grid-cols-[1rem_1fr_3.2rem] items-center gap-1">
                      <span>{axis}</span>
                      <input
                        aria-label={`${side} ${joint} target ${axis}`}
                        type="range"
                        min={-0.5}
                        max={0.5}
                        step={0.005}
                        value={neutralTargets[side][joint][axisIndex]}
                        onChange={(event) => {
                          const next = [...neutralTargets[side][joint]] as [number, number, number];
                          next[axisIndex] = Number(event.target.value);
                          setNeutralTargets((current) => ({
                            ...current,
                            [side]: { ...current[side], [joint]: next },
                          }));
                        }}
                        className="w-full accent-emerald-400"
                      />
                      <output className="text-right tabular-nums">{neutralTargets[side][joint][axisIndex].toFixed(3)}</output>
                    </label>
                  ))}
                </div>
              ))}
            </fieldset>
          ))}
          <button
            type="button"
            onClick={async () => {
              const json = JSON.stringify(canonicalNeutral, null, 2);
              console.info(`[HSIN_CANONICAL_NEUTRAL] ${json}`);
              try {
                await navigator.clipboard.writeText(json);
                setValuesCopied(true);
              } catch {
                setValuesCopied(false);
              }
            }}
            className="w-full rounded bg-emerald-400/20 px-2 py-1.5 uppercase tracking-wider text-emerald-100"
          >
            {valuesCopied ? "Values copied" : "Save / Copy values"}
          </button>
        </div>
      )}
      <button
        type="button"
        onClick={() => setHandOverrideEnabled((current) => !current)}
        className={`w-full rounded-lg border border-white/10 px-3 py-2 text-[10px] uppercase tracking-wider ${handOverrideEnabled ? "bg-fuchsia-400/25 text-fuchsia-100" : "bg-black/70 text-white/60"}`}
      >
        Hsin Hand Override {handOverrideEnabled ? "On" : "Off"}
      </button>
      <div className="space-y-1 rounded-lg border border-white/10 bg-black/70 p-2 text-[10px] text-white/70">
        <button
          type="button"
          onClick={() => setForearmOverrideEnabled((current) => !current)}
          className={`w-full rounded px-3 py-1.5 uppercase tracking-wider ${forearmOverrideEnabled ? "bg-cyan-400/25 text-cyan-100" : "text-white/60"}`}
        >
          Forearm Override {forearmOverrideEnabled ? "On" : "Off"}
        </button>
        {(["left", "right"] as const).map((side) => (
          <fieldset key={side} className="border-t border-white/10 pt-1">
            <legend className="pr-1 capitalize text-white/90">
              {side} lowerArm
            </legend>
            {(["Pitch", "Yaw", "Roll"] as const).map((axis, axisIndex) => (
              <label
                key={axis}
                className="grid grid-cols-[2.5rem_1fr_2.8rem] items-center gap-1"
              >
                <span>{axis}</span>
                <input
                  aria-label={`${side} lowerArm correction ${axis}`}
                  type="range"
                  min={-90}
                  max={90}
                  step={1}
                  value={forearmCorrection[side][axisIndex]}
                  onChange={(event) => {
                    const next = [...forearmCorrection[side]] as [
                      number,
                      number,
                      number,
                    ];
                    next[axisIndex] = Number(event.target.value);
                    setForearmCorrection((current) => ({
                      ...current,
                      [side]: next,
                    }));
                  }}
                  className="w-full accent-cyan-400"
                />
                <output className="text-right tabular-nums">
                  {forearmCorrection[side][axisIndex]}°
                </output>
              </label>
            ))}
          </fieldset>
        ))}
      </div>
      <div className="rounded-lg border border-white/10 bg-black/70 p-2 text-[10px] text-white/65">
        <button
          type="button"
          onClick={() => setPoseMode("relaxed")}
          className="w-full rounded border border-white/10 px-2 py-1.5 uppercase tracking-wider text-white/35 disabled:cursor-not-allowed"
        >
          Procedural IK POC
        </button>
        <p className="mt-1 leading-relaxed">
          Procedural IK is retained for diagnostics but is disabled by default.
        </p>
      </div>
      <div className="flex flex-col items-stretch gap-1 text-[10px] uppercase tracking-wider">
        <button
          type="button"
          onClick={() => {
            setInspectPose((current) => !current);
          }}
          className={`rounded-full border border-white/10 bg-black/70 px-3 py-1.5 backdrop-blur ${inspectPose ? "text-cyan-300" : "text-white/70"}`}
        >
          Pose Inspect {inspectPose ? "On" : "Off"}
        </button>
        <button
          type="button"
          onClick={() => {
            setHandInspectionView((current) => current ? null : "leftFront");
            setInspectPose(true);
            setSpringsEnabled(false);
            setRevealHands(true);
          }}
          className={`rounded-full border border-white/10 bg-black/70 px-3 py-1.5 backdrop-blur ${handInspectionView ? "text-fuchsia-300" : "text-white/70"}`}
        >
          Hand Inspect {handInspectionView ? "On" : "Off"}
        </button>
        {handInspectionView && (
          <div className="flex max-w-80 flex-wrap gap-1 rounded-lg border border-white/10 bg-black/70 p-1 backdrop-blur">
            {([
              ["leftFront", "Left Hand Front"],
              ["leftSide", "Left Hand Side"],
              ["rightFront", "Right Hand Front"],
              ["rightSide", "Right Hand Side"],
            ] as const).map(([view, label]) => (
              <button
                key={view}
                type="button"
                onClick={() => setHandInspectionView(view)}
                className={`rounded px-2 py-1 normal-case tracking-normal ${handInspectionView === view ? "bg-fuchsia-400/25 text-fuchsia-200" : "text-white/60"}`}
              >
                {label}
              </button>
            ))}
            <button
              type="button"
              disabled
              className="rounded bg-rose-400/25 px-2 py-1 normal-case tracking-normal text-rose-200"
            >
              Arm Cloth Hidden
            </button>
          </div>
        )}
        {inspectPose && (
          <div className="flex max-w-80 flex-wrap gap-1 rounded-lg border border-white/10 bg-black/70 p-1 backdrop-blur">
            {([
              ["front", "Front"],
              ["leftThreeQuarter", "Left 3/4"],
              ["rightThreeQuarter", "Right 3/4"],
              ["side", "Side"],
            ] as const).map(([view, label]) => (
              <button
                key={view}
                type="button"
                onClick={() => setInspectionView(view)}
                className={`rounded px-2 py-1 ${inspectionView === view ? "bg-cyan-400/25 text-cyan-200" : "text-white/60"}`}
              >
                {label}
              </button>
            ))}
          </div>
        )}
        <div className="space-y-1 rounded-lg border border-white/10 bg-black/70 p-2 normal-case tracking-normal text-white/70">
          <div className="uppercase tracking-wider text-white/90">Hand IK targets</div>
          {(["left", "right"] as const).map((side) => (
            <fieldset key={side} className="border-t border-white/10 pt-1">
              <legend className="pr-1 capitalize text-white/90">{side} hand</legend>
              {(["X", "Y", "Z"] as const).map((axis, axisIndex) => (
                <label key={axis} className="grid grid-cols-[1rem_1fr_2.8rem] items-center gap-1">
                  <span>{axis}</span>
                  <input
                    aria-label={`${side} hand target ${axis}`}
                    type="range"
                    min={axis === "Y" ? -1.2 : -0.8}
                    max={axis === "Y" ? 0.4 : 0.8}
                    step={0.01}
                    value={armIkTargets[side][axisIndex]}
                    onChange={(event) => {
                      const next = [...armIkTargets[side]] as [number, number, number];
                      next[axisIndex] = Number(event.target.value);
                      setArmIkTargets((current) => ({ ...current, [side]: next }));
                      setPoseMode("relaxed");
                    }}
                    className="w-full accent-fuchsia-400"
                  />
                  <output className="text-right tabular-nums">{armIkTargets[side][axisIndex].toFixed(2)}</output>
                </label>
              ))}
            </fieldset>
          ))}
        </div>
        <div className="space-y-1 rounded-lg border border-white/10 bg-black/70 p-2 normal-case tracking-normal text-white/70">
          <div className="uppercase tracking-wider text-white/90">Hand orientation</div>
          {(["left", "right"] as const).map((side) => (
            <fieldset key={side} className="border-t border-white/10 pt-1">
              <legend className="pr-1 capitalize text-white/90">{side} hand</legend>
              {(["Pitch", "Yaw", "Roll"] as const).map((axis, axisIndex) => (
                <label key={axis} className="grid grid-cols-[2.5rem_1fr_2.8rem] items-center gap-1">
                  <span>{axis}</span>
                  <input
                    aria-label={`${side} hand target ${axis}`}
                    type="range"
                    min={-90}
                    max={90}
                    step={1}
                    value={handOrientationTargets[side][axisIndex]}
                    onChange={(event) => {
                      const next = [...handOrientationTargets[side]] as [number, number, number];
                      next[axisIndex] = Number(event.target.value);
                      setHandOrientationTargets((current) => ({ ...current, [side]: next }));
                      setPoseMode("relaxed");
                    }}
                    className="w-full accent-cyan-400"
                  />
                  <output className="text-right tabular-nums">
                    {handOrientationTargets[side][axisIndex]}°
                  </output>
                </label>
              ))}
            </fieldset>
          ))}
        </div>
      </div>
      {!inspectPose && <details className="rounded-lg border border-white/10 bg-black/40 p-2 text-[10px] text-white/75">
        <summary className="cursor-pointer select-none uppercase tracking-wider text-white">
          Relaxed pose tuning
        </summary>
        <div className="mt-2 space-y-2">
          {TUNING_BONES.map((boneName) => (
            <fieldset key={boneName} className="border-t border-white/10 pt-1">
              <legend className="pr-1 text-white/90">{boneName}</legend>
              {(["X", "Y", "Z"] as const).map((axis, axisIndex) => (
                <label key={axis} className="grid grid-cols-[1rem_1fr_2rem] items-center gap-1">
                  <span>{axis}</span>
                  <input
                    aria-label={`${boneName} ${axis}`}
                    type="range"
                    min={-180}
                    max={180}
                    step={1}
                    value={poseTuning[boneName]?.[axisIndex] ?? 0}
                    onChange={(event) => {
                      const next = [...(poseTuning[boneName] ?? [0, 0, 0])] as [number, number, number];
                      next[axisIndex] = Number(event.target.value);
                      setPoseTuning((current) => ({ ...current, [boneName]: next }));
                      setPoseMode("relaxed");
                    }}
                    className="w-full accent-violet-400"
                  />
                  <output className="text-right tabular-nums">
                    {poseTuning[boneName]?.[axisIndex] ?? 0}
                  </output>
                </label>
              ))}
            </fieldset>
          ))}
        </div>
      </details>}
        </div>
      </aside>}
    </div>
  );
}
