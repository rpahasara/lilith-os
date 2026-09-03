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
import type { SpeakingGestureVariant } from "@/lib/hsin-speaking-motion";
import type {
  AmbientVariationName,
  AmbientIdleState,
} from "@/lib/hsin-ambient-idle";
import {
  CURRENT_AVATAR_FRAMING,
  PROPOSED_AVATAR_FRAMING,
  PROPOSED_FORWARD_GAZE,
  FRONT_FACING_CANDIDATE,
  STRONG_FRONT_FACING_CANDIDATE,
  HSIN_ARM_BONES,
  HSIN_ARM_REFERENCE_V1_DELTAS,
  HSIN_ARM_REFERENCE_V2_DELTAS,
  HSIN_ARM_REFERENCE_V3_DELTAS,
  HSIN_ARM_BASELINE_DELTAS,
  HSIN_ARM_LEFT_V1_DELTAS,
  HSIN_ARM_LEFT_V2_DELTAS,
  HSIN_ARM_FINAL_CANDIDATE_DELTAS,
  HSIN_RIGHT_HAND_RELAXED_FINGER_DELTAS,
  HSIN_RIGHT_HAND_RELAXED_FINGER_DELTAS_V2,
  HSIN_RIGHT_HAND_RELAXED_FINGER_DELTAS_V3,
  HSIN_RIGHT_HAND_ORIENT_V3,
  HSIN_RIGHT_HAND_ORIENT_V4,
  HSIN_CANONICAL_NEUTRAL,
  type ArmPoseMode,
  type ArmCalibrationOffsets,
  type ArmGeometryReport,
  type AvatarPresentationFraming,
  type ForwardGazeCalibration,
  type FrontFacingCalibration,
  type FaceExpressionState,
  type ExpressionInspectName,
  type VisemeInspectName,
  type HandInspectionView,
  type ArmIkTargets,
  type HandOrientationTargets,
  type ForearmCorrection,
  type CanonicalNeutralQuaternions,
  type NeutralCalibrationTargets,
  type PoseInspectionView,
  type PoseTestMode,
  type RelaxedPoseTuning,
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
  // Ambient Idle Phase 1 POC — dev-gated, default OFF.
  const [ambientIdleEnabled, setAmbientIdleEnabled] = useState(false);
  const [ambientTriggerSequence, setAmbientTriggerSequence] = useState(0);
  const [ambientTriggerVariation, setAmbientTriggerVariation] =
    useState<AmbientVariationName | null>(null);
  const [ambientState, setAmbientState] = useState<AmbientIdleState>({
    phase: "idle",
    variation: null,
    weight: 0,
    timeRemaining: 0,
  });
  const triggerAmbient = useCallback(
    (variation: AmbientVariationName | null) => {
      setAmbientTriggerVariation(variation);
      setAmbientTriggerSequence((current) => current + 1);
    },
    [],
  );
  // Speaking Motion Phase 1 POC — dev-gated, default OFF.
  const [speakingMotionEnabled, setSpeakingMotionEnabled] = useState(false);
  const [speakingGestureTrigger, setSpeakingGestureTrigger] = useState(0);
  // Dev A/B: V2 = visibility-tuned beat (default), V1 = original subtle beat.
  const [speakingGestureVariant, setSpeakingGestureVariant] =
    useState<SpeakingGestureVariant>("v2");
  // Arm / shoulder neutral-pose polish POC (dev-only A/B). Default CURRENT so
  // production arms are unchanged. Calibration deltas start at zero, so the
  // reference candidate is identical to current until tuned.
  const [armPoseMode, setArmPoseMode] = useState<ArmPoseMode>("current");
  // Deep-copies a preset into calibration state so slider edits never mutate the
  // exported constant.
  const cloneArmPreset = useCallback(
    (preset: ArmCalibrationOffsets): ArmCalibrationOffsets =>
      Object.fromEntries(
        HSIN_ARM_BONES.map((bone) => [
          bone,
          [...(preset[bone] ?? [0, 0, 0])],
        ]),
      ) as ArmCalibrationOffsets,
    [],
  );
  // Seeded with Reference Candidate V2 (the current review target). V1/V2 preset
  // buttons switch between them; "Reset Deltas" returns to zero (= Current).
  const [armCalibration, setArmCalibration] = useState<ArmCalibrationOffsets>(
    () =>
      Object.fromEntries(
        HSIN_ARM_BONES.map((bone) => [
          bone,
          [...(HSIN_ARM_REFERENCE_V2_DELTAS[bone] ?? [0, 0, 0])],
        ]),
      ) as ArmCalibrationOffsets,
  );
  const [armCandidateQuats, setArmCandidateQuats] = useState<
    Record<string, [number, number, number, number]>
  >({});
  const [armValuesCopied, setArmValuesCopied] = useState(false);
  // Arm geometry diagnostic (dev-only): skeleton markers, sleeve isolation, and
  // a live world-space geometry readout of the active candidate.
  const [showArmSkeleton, setShowArmSkeleton] = useState(false);
  const [armAnatomyView, setArmAnatomyView] = useState(false);
  const [armGeometry, setArmGeometry] = useState<ArmGeometryReport | null>(null);
  const [rightFingerPreset, setRightFingerPreset] = useState<
    "original" | "relaxedV1" | "relaxedV2" | "relaxedV3"
  >("original");
  const rightFingerDeltas =
    rightFingerPreset === "relaxedV1"
      ? HSIN_RIGHT_HAND_RELAXED_FINGER_DELTAS
      : rightFingerPreset === "relaxedV2"
        ? HSIN_RIGHT_HAND_RELAXED_FINGER_DELTAS_V2
        : rightFingerPreset === "relaxedV3"
          ? HSIN_RIGHT_HAND_RELAXED_FINGER_DELTAS_V3
          : null;
  const setRightHandOrient = useCallback(
    (delta: [number, number, number]) => {
      setArmCalibration((current) => ({
        ...current,
        rightHand: [...delta] as [number, number, number],
      }));
    },
    [],
  );
  // One-click combined setup for the both-sides review: Left V2 + Right V3 arm
  // chain + V4 right hand + Relaxed V3 right fingers, in Reference Candidate mode.
  const applyFinalArmCandidate = useCallback(() => {
    setArmPoseMode("referenceCandidate");
    setArmCalibration(cloneArmPreset(HSIN_ARM_FINAL_CANDIDATE_DELTAS));
    setRightFingerPreset("relaxedV3");
  }, [cloneArmPreset]);
  const setArmDelta = useCallback(
    (bone: string, axis: 0 | 1 | 2, value: number) => {
      setArmCalibration((current) => {
        const previous = current[bone as keyof ArmCalibrationOffsets] ?? [
          0, 0, 0,
        ];
        const next: [number, number, number] = [
          previous[0],
          previous[1],
          previous[2],
        ];
        next[axis] = value;
        return { ...current, [bone]: next };
      });
    },
    [],
  );
  const resetArmCalibration = useCallback(() => {
    setArmCalibration(
      Object.fromEntries(
        HSIN_ARM_BONES.map((bone) => [bone, [0, 0, 0]]),
      ) as ArmCalibrationOffsets,
    );
  }, []);
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
  const [presentationMode, setPresentationMode] = useState<"current" | "proposed">(
    "proposed",
  );
  const [proposedFraming, setProposedFraming] =
    useState<AvatarPresentationFraming>(PROPOSED_AVATAR_FRAMING);
  const [forwardGaze, setForwardGaze] =
    useState<ForwardGazeCalibration>(PROPOSED_FORWARD_GAZE);
  const [frontFacingCalibration, setFrontFacingCalibration] =
    useState<FrontFacingCalibration>(STRONG_FRONT_FACING_CANDIDATE);
  const [frontFacingMode, setFrontFacingMode] =
    useState<"current" | "candidate" | "strong">("strong");
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
        presentationFraming={
          presentationMode === "proposed"
            ? proposedFraming
            : CURRENT_AVATAR_FRAMING
        }
        forwardGaze={forwardGaze}
        frontFacingCalibration={frontFacingCalibration}
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
        ambientIdleEnabled={ambientIdleEnabled}
        ambientTriggerSequence={ambientTriggerSequence}
        ambientTriggerVariation={ambientTriggerVariation}
        onAmbientStateChange={setAmbientState}
        speakingMotionEnabled={speakingMotionEnabled}
        speakingGestureTrigger={speakingGestureTrigger}
        speakingGestureVariant={speakingGestureVariant}
        armPoseMode={armPoseMode}
        armCalibration={armCalibration}
        onArmCandidateChange={setArmCandidateQuats}
        showArmSkeleton={showArmSkeleton}
        armAnatomyView={armAnatomyView}
        onArmGeometryChange={setArmGeometry}
        rightFingerDeltas={rightFingerDeltas}
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
      <div className="space-y-2 rounded-lg border border-cyan-300/20 bg-cyan-950/20 p-2">
        <div className="grid grid-cols-2 gap-1">
          {(["current", "proposed"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setPresentationMode(mode)}
              className={`rounded px-2 py-1.5 text-[10px] uppercase tracking-wider ${presentationMode === mode ? "bg-cyan-400/25 text-cyan-100" : "bg-black/40 text-white/55"}`}
            >
              {mode}
            </button>
          ))}
        </div>
        {presentationMode === "proposed" &&
          ([
            ["scale", "Scale", 0.8, 1.4, 0.01],
            ["offsetY", "Y offset", -0.5, 0.5, 0.01],
            ["offsetX", "X offset", -0.3, 0.3, 0.01],
            ["cameraDistance", "Camera distance", 3, 5, 0.05],
            ["fov", "FOV", 25, 50, 1],
            ["targetY", "Target Y", -0.3, 0.6, 0.01],
          ] as const).map(([key, label, min, max, step]) => (
            <label
              key={key}
              className="block text-[10px] uppercase tracking-wider text-white/60"
            >
              {label} {proposedFraming[key].toFixed(2)}
              <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={proposedFraming[key]}
                onChange={(event) =>
                  setProposedFraming((current) => ({
                    ...current,
                    [key]: Number(event.target.value),
                  }))
                }
                className="mt-1 block w-full"
              />
            </label>
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
      <div className="space-y-2 rounded-lg border border-sky-300/20 bg-sky-950/20 p-2">
        <div className="text-[10px] uppercase tracking-wider text-sky-100/70">
          Forward Gaze Calibration
        </div>
        <button
          type="button"
          onClick={() => {
            setCenterEyesSequence((current) => current + 1);
            setCenterHeadSequence((current) => current + 1);
          }}
          className="w-full rounded bg-sky-400/20 px-2 py-1.5 text-[10px] uppercase tracking-wider text-sky-100"
        >
          Direct Eye Contact Test
        </button>
        {([
          ["eyeYaw", "Eye yaw", -4, 4, 0.1],
          ["eyePitch", "Eye pitch", -2, 2, 0.05],
          ["headYaw", "Head yaw", -3, 3, 0.1],
          ["headPitch", "Head pitch", -2, 2, 0.05],
        ] as const).map(([key, label, min, max, step]) => (
          <label
            key={key}
            className="block text-[10px] uppercase tracking-wider text-white/60"
          >
            {label} {forwardGaze[key].toFixed(2)}°
            <input
              type="range"
              min={min}
              max={max}
              step={step}
              value={forwardGaze[key]}
              onChange={(event) =>
                setForwardGaze((current) => ({
                  ...current,
                  [key]: Number(event.target.value),
                }))
              }
              className="mt-1 block w-full"
            />
          </label>
        ))}
      </div>
      <div className="space-y-2 rounded-lg border border-fuchsia-300/20 bg-fuchsia-950/20 p-2">
        <div className="text-[10px] uppercase tracking-wider text-fuchsia-100/70">
          Front-Facing Stance
        </div>
        <div className="grid grid-cols-3 gap-1">
          <button
            type="button"
            onClick={() => {
              setFrontFacingMode("current");
              setFrontFacingCalibration((current) => ({
                ...current,
                enabled: false,
              }));
            }}
            className={`rounded px-1 py-1.5 text-[9px] uppercase tracking-wider ${frontFacingMode === "current" ? "bg-fuchsia-400/25 text-fuchsia-100" : "bg-black/40 text-white/55"}`}
          >
            Current
          </button>
          <button
            type="button"
            onClick={() => {
              setFrontFacingMode("candidate");
              setFrontFacingCalibration(FRONT_FACING_CANDIDATE);
            }}
            className={`rounded px-1 py-1.5 text-[9px] uppercase tracking-wider ${frontFacingMode === "candidate" ? "bg-fuchsia-400/25 text-fuchsia-100" : "bg-black/40 text-white/55"}`}
          >
            Front
          </button>
          <button
            type="button"
            onClick={() => {
              setFrontFacingMode("strong");
              setFrontFacingCalibration(STRONG_FRONT_FACING_CANDIDATE);
            }}
            className={`rounded px-1 py-1.5 text-[9px] uppercase tracking-wider ${frontFacingMode === "strong" ? "bg-fuchsia-400/25 text-fuchsia-100" : "bg-black/40 text-white/55"}`}
          >
            Strong Front
          </button>
        </div>
        {frontFacingCalibration.enabled &&
          ([
            ["hipsYaw", "Hips yaw", -8, 8, 0.1],
            ["spineYaw", "Spine yaw", -8, 8, 0.1],
            ["chestYaw", "Chest yaw", -8, 8, 0.1],
            ["upperChestYaw", "Upper chest yaw", -8, 8, 0.1],
            ["leftShoulderYaw", "Left shoulder yaw", -5, 5, 0.1],
            ["leftShoulderRoll", "Left shoulder roll", -5, 5, 0.1],
            ["rightShoulderYaw", "Right shoulder yaw", -5, 5, 0.1],
            ["rightShoulderRoll", "Right shoulder roll", -5, 5, 0.1],
          ] as const).map(([key, label, min, max, step]) => (
            <label
              key={key}
              className="block text-[10px] uppercase tracking-wider text-white/60"
            >
              {label} {frontFacingCalibration[key].toFixed(1)}°
              <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={frontFacingCalibration[key]}
                onChange={(event) => {
                  setFrontFacingMode("strong");
                  setFrontFacingCalibration((current) => ({
                    ...current,
                    enabled: true,
                    [key]: Number(event.target.value),
                  }));
                }}
                className="mt-1 block w-full"
              />
            </label>
          ))}
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
        <div className="space-y-1 rounded-lg border border-emerald-300/20 bg-emerald-950/20 p-2">
          <button
            type="button"
            onClick={() => setSpeakingMotionEnabled((current) => !current)}
            className={`w-full rounded px-2 py-1.5 text-[10px] uppercase tracking-wider ${speakingMotionEnabled ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
          >
            Speaking Motion (POC) {speakingMotionEnabled ? "On" : "Off"}
          </button>
          <div className="grid grid-cols-2 gap-1">
            <button
              type="button"
              disabled={!speakingMotionEnabled}
              onClick={() => setSpeakingGestureVariant("v1")}
              className={`rounded px-2 py-1.5 text-[10px] uppercase tracking-wider disabled:opacity-30 ${speakingGestureVariant === "v1" ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
            >
              Gesture V1
            </button>
            <button
              type="button"
              disabled={!speakingMotionEnabled}
              onClick={() => setSpeakingGestureVariant("v2")}
              className={`rounded px-2 py-1.5 text-[10px] uppercase tracking-wider disabled:opacity-30 ${speakingGestureVariant === "v2" ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
            >
              Gesture V2
            </button>
          </div>
          <button
            type="button"
            disabled={!speakingMotionEnabled}
            onClick={() =>
              setSpeakingGestureTrigger((current) => current + 1)
            }
            className="w-full rounded bg-emerald-400/20 px-2 py-1.5 text-[10px] uppercase tracking-wider text-emerald-100 disabled:opacity-30"
          >
            Trigger Speaking Gesture ({speakingGestureVariant.toUpperCase()})
          </button>
          <p className="text-[9px] leading-tight text-white/40">
            Enable, then Play Timed Speech for micro-motion. Gesture also fires
            occasionally on longer speech.
          </p>
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
        <div className="space-y-1 rounded-lg border border-violet-300/20 bg-violet-950/20 p-2">
          <button
            type="button"
            onClick={() => setAmbientIdleEnabled((current) => !current)}
            className={`w-full rounded px-2 py-1.5 text-[10px] uppercase tracking-wider ${ambientIdleEnabled ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
          >
            Ambient Idle (POC) {ambientIdleEnabled ? "On" : "Off"}
          </button>
          <div className="grid grid-cols-2 gap-1">
            <button
              type="button"
              disabled={!ambientIdleEnabled}
              onClick={() => triggerAmbient("weightShiftLeft")}
              className="rounded bg-violet-400/20 px-2 py-1.5 text-[10px] uppercase tracking-wider text-violet-100 disabled:opacity-30"
            >
              Trigger Weight Shift Left
            </button>
            <button
              type="button"
              disabled={!ambientIdleEnabled}
              onClick={() => triggerAmbient("weightShiftRight")}
              className="rounded bg-violet-400/20 px-2 py-1.5 text-[10px] uppercase tracking-wider text-violet-100 disabled:opacity-30"
            >
              Trigger Weight Shift Right
            </button>
            <button
              type="button"
              disabled={!ambientIdleEnabled}
              onClick={() => triggerAmbient("gentleHeadTurnRight")}
              className="rounded bg-violet-400/20 px-2 py-1.5 text-[10px] uppercase tracking-wider text-violet-100 disabled:opacity-30"
            >
              Trigger Head Turn Right
            </button>
            <button
              type="button"
              disabled={!ambientIdleEnabled}
              onClick={() => triggerAmbient("curiousGlanceLeft")}
              className="rounded bg-violet-400/20 px-2 py-1.5 text-[10px] uppercase tracking-wider text-violet-100 disabled:opacity-30"
            >
              Trigger Glance Left
            </button>
          </div>
          <button
            type="button"
            disabled={!ambientIdleEnabled}
            onClick={() => triggerAmbient("softPostureReset")}
            className="w-full rounded bg-violet-400/20 px-2 py-1.5 text-[10px] uppercase tracking-wider text-violet-100 disabled:opacity-30"
          >
            Trigger Posture Reset
          </button>
          <button
            type="button"
            disabled={!ambientIdleEnabled}
            onClick={() => triggerAmbient(null)}
            className="w-full rounded bg-black/40 px-2 py-1.5 text-[10px] uppercase tracking-wider text-white/55 disabled:opacity-30"
          >
            Trigger Ambient (Alternate)
          </button>
          <div className="grid grid-cols-2 gap-1 pt-0.5 text-[10px] uppercase tracking-wider text-white/60">
            <div>
              Current
              <div className="text-cyan-100 normal-case">
                {ambientState.variation ?? "idle"}
              </div>
            </div>
            <div>
              Phase
              <div className="text-cyan-100 capitalize">{ambientState.phase}</div>
            </div>
          </div>
        </div>
      </div>
      {SHOW_CALIBRATION_DEBUG && (
        <div className="space-y-2 rounded-lg border border-amber-300/20 bg-amber-950/20 p-2 text-[10px] text-white/70">
          <div className="uppercase tracking-wider text-amber-200">
            Arm Neutral Polish (POC)
          </div>
          <div className="grid grid-cols-2 gap-1 rounded border border-emerald-300/30 bg-emerald-950/20 p-1">
            <button
              type="button"
              onClick={() => setArmPoseMode("current")}
              className={`rounded px-1 py-1.5 uppercase tracking-wider ${armPoseMode === "current" ? "bg-white/20 text-white" : "bg-black/40 text-white/55"}`}
            >
              Current Production
            </button>
            <button
              type="button"
              onClick={applyFinalArmCandidate}
              className="rounded bg-emerald-400/30 px-1 py-1.5 uppercase tracking-wider text-emerald-100"
            >
              Final Arm Candidate
            </button>
          </div>
          <div className="text-[9px] normal-case text-white/45">
            Final = Left V2 + Right V3 + Right Hand V4 + Relaxed V3 fingers.
          </div>
          <div className="grid grid-cols-2 gap-1">
            {(["current", "referenceCandidate"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setArmPoseMode(mode)}
                className={`rounded px-2 py-1.5 uppercase tracking-wider ${armPoseMode === mode ? "bg-amber-400/25 text-amber-100" : "bg-black/40 text-white/55"}`}
              >
                {mode === "current" ? "Current Arms" : "Reference Candidate"}
              </button>
            ))}
          </div>
          <div className="text-[9px] normal-case text-white/45">
            Candidate only differs in Natural Idle V2. Use the views below to
            validate front & side.
          </div>
          <div className="grid grid-cols-4 gap-1">
            {(
              [
                ["front", "Front"],
                ["leftThreeQuarter", "L¾"],
                ["rightThreeQuarter", "R¾"],
                ["side", "Side"],
              ] as const
            ).map(([view, label]) => (
              <button
                key={view}
                type="button"
                onClick={() => {
                  setInspectionView(view);
                  setInspectPose(true);
                }}
                className={`rounded px-1 py-1 uppercase tracking-wider ${inspectPose && inspectionView === view ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setInspectPose(false)}
            className={`w-full rounded px-2 py-1 uppercase tracking-wider ${!inspectPose ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
          >
            Presentation View
          </button>
          <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
            {HSIN_ARM_BONES.map((bone) => {
              const delta = armCalibration[bone] ?? [0, 0, 0];
              return (
                <fieldset
                  key={bone}
                  className="rounded border border-white/10 p-1"
                >
                  <legend className="pr-1 text-white/85">{bone}</legend>
                  {(
                    [
                      ["Pitch", 0],
                      ["Yaw", 1],
                      ["Roll", 2],
                    ] as const
                  ).map(([label, axis]) => (
                    <label
                      key={label}
                      className="block normal-case text-white/55"
                    >
                      {label} {delta[axis].toFixed(1)}°
                      <input
                        type="range"
                        min={-25}
                        max={25}
                        step={0.5}
                        value={delta[axis]}
                        onChange={(event) =>
                          setArmDelta(bone, axis, Number(event.target.value))
                        }
                        className="mt-0.5 block w-full"
                      />
                    </label>
                  ))}
                </fieldset>
              );
            })}
          </div>
          <div className="grid grid-cols-3 gap-1">
            <button
              type="button"
              onClick={() =>
                setArmCalibration(cloneArmPreset(HSIN_ARM_REFERENCE_V1_DELTAS))
              }
              className="rounded bg-violet-400/20 px-2 py-1.5 uppercase tracking-wider text-violet-100"
            >
              V1
            </button>
            <button
              type="button"
              onClick={() =>
                setArmCalibration(cloneArmPreset(HSIN_ARM_REFERENCE_V2_DELTAS))
              }
              className="rounded bg-amber-400/20 px-2 py-1.5 uppercase tracking-wider text-amber-100"
            >
              V2
            </button>
            <button
              type="button"
              onClick={() =>
                setArmCalibration(cloneArmPreset(HSIN_ARM_REFERENCE_V3_DELTAS))
              }
              className="rounded bg-emerald-400/25 px-2 py-1.5 uppercase tracking-wider text-emerald-100"
            >
              V3
            </button>
          </div>
          <div className="grid grid-cols-2 gap-1">
            <button
              type="button"
              onClick={() =>
                setArmCalibration(cloneArmPreset(HSIN_ARM_BASELINE_DELTAS))
              }
              className="rounded bg-black/40 px-2 py-1.5 uppercase tracking-wider text-white/70"
            >
              Baseline (V3+V4)
            </button>
            <button
              type="button"
              onClick={() =>
                setArmCalibration(cloneArmPreset(HSIN_ARM_LEFT_V1_DELTAS))
              }
              className="rounded bg-sky-400/20 px-2 py-1.5 uppercase tracking-wider text-sky-100/80"
            >
              Left V1
            </button>
          </div>
          <button
            type="button"
            onClick={() =>
              setArmCalibration(cloneArmPreset(HSIN_ARM_LEFT_V2_DELTAS))
            }
            className="w-full rounded bg-sky-400/30 px-2 py-1.5 uppercase tracking-wider text-sky-100"
          >
            Left V2
          </button>
          <div className="grid grid-cols-2 gap-1">
            <button
              type="button"
              onClick={resetArmCalibration}
              className="rounded bg-black/40 px-2 py-1.5 uppercase tracking-wider text-white/55"
            >
              Reset Deltas
            </button>
            <button
              type="button"
              onClick={() => {
                const frozen = Object.fromEntries(
                  HSIN_ARM_BONES.map((bone) => [
                    bone,
                    armCandidateQuats[bone] ?? HSIN_CANONICAL_NEUTRAL[bone],
                  ]),
                );
                navigator.clipboard
                  ?.writeText(JSON.stringify(frozen, null, 2))
                  .then(() => {
                    setArmValuesCopied(true);
                    setTimeout(() => setArmValuesCopied(false), 1500);
                  });
              }}
              className="rounded bg-amber-400/20 px-2 py-1.5 uppercase tracking-wider text-amber-100"
            >
              {armValuesCopied ? "Copied ✓" : "Copy Candidate"}
            </button>
          </div>
          <div className="grid grid-cols-2 gap-1">
            <button
              type="button"
              onClick={() => setShowArmSkeleton((current) => !current)}
              className={`rounded px-2 py-1.5 uppercase tracking-wider ${showArmSkeleton ? "bg-fuchsia-400/25 text-fuchsia-100" : "bg-black/40 text-white/55"}`}
            >
              Show Arm Skeleton {showArmSkeleton ? "On" : "Off"}
            </button>
            <button
              type="button"
              onClick={() => setArmAnatomyView((current) => !current)}
              className={`rounded px-2 py-1.5 uppercase tracking-wider ${armAnatomyView ? "bg-fuchsia-400/25 text-fuchsia-100" : "bg-black/40 text-white/55"}`}
            >
              Arm Anatomy View {armAnatomyView ? "On" : "Off"}
            </button>
          </div>
          <div className="space-y-1 rounded border border-rose-300/20 bg-rose-950/20 p-1">
            <div className="text-[9px] uppercase tracking-wider text-rose-200">
              Right hand — orientation
            </div>
            <div className="grid grid-cols-2 gap-1">
              <button
                type="button"
                onClick={() => setRightHandOrient(HSIN_RIGHT_HAND_ORIENT_V3)}
                className="rounded bg-black/40 px-2 py-1.5 uppercase tracking-wider text-white/70"
              >
                V3 Hand
              </button>
              <button
                type="button"
                onClick={() => setRightHandOrient(HSIN_RIGHT_HAND_ORIENT_V4)}
                className="rounded bg-rose-400/25 px-2 py-1.5 uppercase tracking-wider text-rose-100"
              >
                V4 Hand
              </button>
            </div>
            <div className="text-[9px] uppercase tracking-wider text-rose-200">
              Right hand — fingers
            </div>
            <div className="grid grid-cols-2 gap-1">
              {(
                [
                  ["original", "Original"],
                  ["relaxedV1", "Relaxed V1"],
                  ["relaxedV2", "Relaxed V2"],
                  ["relaxedV3", "Relaxed V3"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setRightFingerPreset(key)}
                  className={`rounded px-1 py-1.5 uppercase tracking-wider ${rightFingerPreset === key ? "bg-rose-400/25 text-rose-100" : "bg-black/40 text-white/55"}`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="text-[9px] uppercase tracking-wider text-rose-200">
              Right hand — close-up
            </div>
            <div className="grid grid-cols-3 gap-1">
              <button
                type="button"
                onClick={() => setHandInspectionView("rightFront")}
                className={`rounded px-1 py-1.5 uppercase tracking-wider ${handInspectionView === "rightFront" ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
              >
                Front
              </button>
              <button
                type="button"
                onClick={() => setHandInspectionView("rightSide")}
                className={`rounded px-1 py-1.5 uppercase tracking-wider ${handInspectionView === "rightSide" ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
              >
                Side
              </button>
              <button
                type="button"
                onClick={() => setHandInspectionView(null)}
                className={`rounded px-1 py-1.5 uppercase tracking-wider ${handInspectionView === null ? "bg-cyan-400/20 text-cyan-100" : "bg-black/40 text-white/55"}`}
              >
                Off
              </button>
            </div>
          </div>
          {showArmSkeleton && armGeometry && (
            <div className="space-y-0.5 rounded border border-white/10 p-1 normal-case text-[9px] text-white/60">
              {(["left", "right"] as const).map((side) => {
                const g = armGeometry[side];
                return (
                  <div key={side}>
                    <span className="uppercase text-white/85">{side}</span> bend{" "}
                    {g.elbowBendDeg.toFixed(1)}° · wristY{" "}
                    {g.wristHeightFromHips.toFixed(3)} · elbowX{" "}
                    {g.elbowLateralFromHips.toFixed(3)} · wristX{" "}
                    {g.wristLateralFromHips.toFixed(3)}
                  </div>
                );
              })}
              <div className="text-white/35">
                world units · wristY = height above hips (negative = below)
              </div>
            </div>
          )}
        </div>
      )}
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
