"use client";

import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import {
  VRMLoaderPlugin,
  VRMLookAtBoneApplier,
  VRMLookAtExpressionApplier,
  type VRM,
  type VRMHumanBoneName,
  type VRMPose,
} from "@pixiv/three-vrm";
import {
  createVRMAnimationClip,
  VRMAnimationLoaderPlugin,
  type VRMAnimation,
} from "@pixiv/three-vrm-animation";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { PresenceSignal } from "@/lib/presence";
import type { SpeechPlaybackSnapshot, VisemeCue } from "@/lib/hsin-lip-sync";
import {
  HsinAmbientIdle,
  type AmbientBone,
  type AmbientPhase,
  type AmbientVariationName,
  type AmbientIdleState,
} from "@/lib/hsin-ambient-idle";
import {
  HsinSpeakingMotion,
  type SpeakingMicroBone,
  type SpeakingGestureBone,
  type SpeakingGestureVariant,
} from "@/lib/hsin-speaking-motion";
import {
  HsinRareMotion,
  type RareMotionBone,
  type RareMotionOffsets,
  type RareMotionPhase,
  type RareMotionState,
  type RareTurnSide,
} from "@/lib/hsin-rare-motion";
import {
  HsinMotionOrchestrator,
  type OrchestratorMode,
  type OrchestratorReadout,
} from "@/lib/hsin-motion-orchestrator";

const AVATAR_URL = "/assets/avatars/Hsin_FINAL_EXPORT_WORKING_FIXED.vrm";
const RELAXED_IDLE_VRMA_URL = "/assets/animations/hsin-relaxed-idle.vrma";
const SHOW_CALIBRATION_DEBUG = process.env.NODE_ENV !== "production";

export type AvatarPresentationFraming = {
  scale: number;
  offsetX: number;
  offsetY: number;
  cameraDistance: number;
  fov: number;
  targetY: number;
};

export type ForwardGazeCalibration = {
  eyeYaw: number;
  eyePitch: number;
  headYaw: number;
  headPitch: number;
};
export type FrontFacingCalibration = {
  enabled: boolean;
  hipsYaw: number;
  spineYaw: number;
  chestYaw: number;
  upperChestYaw: number;
  leftShoulderYaw: number;
  leftShoulderRoll: number;
  rightShoulderYaw: number;
  rightShoulderRoll: number;
};
export const FRONT_FACING_CANDIDATE: FrontFacingCalibration = {
  enabled: true,
  hipsYaw: -2.5,
  spineYaw: -2.5,
  chestYaw: -3.5,
  upperChestYaw: -1.5,
  leftShoulderYaw: 0,
  leftShoulderRoll: 0,
  rightShoulderYaw: 0,
  rightShoulderRoll: 0,
};
export const STRONG_FRONT_FACING_CANDIDATE: FrontFacingCalibration = {
  enabled: true,
  hipsYaw: -5,
  spineYaw: -4.5,
  chestYaw: -6.5,
  upperChestYaw: -3,
  leftShoulderYaw: 0,
  leftShoulderRoll: 0,
  rightShoulderYaw: 0,
  rightShoulderRoll: 0,
};

export const PROPOSED_FORWARD_GAZE: ForwardGazeCalibration = {
  eyeYaw: -1.6,
  eyePitch: 0.15,
  headYaw: -0.7,
  headPitch: 0.1,
};

export const CURRENT_AVATAR_FRAMING: AvatarPresentationFraming = {
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  cameraDistance: 4.25,
  fov: 36,
  targetY: 0,
};

export const PROPOSED_AVATAR_FRAMING: AvatarPresentationFraming = {
  scale: 1.15,
  offsetX: -0.03,
  offsetY: -0.06,
  cameraDistance: 4.05,
  fov: 34,
  targetY: 0.32,
};

export type FaceExpressionState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking";

export type ExpressionInspectName =
  | "happy"
  | "puzzled"
  | "angry"
  | "sad"
  | "surprised"
  | "relaxed"
  | "squint"
  | "laugh"
  | "meow"
  | "openSmall"
  | "neutral";

export type VisemeInspectName = "aa" | "ih" | "ou" | "ee" | "oh";

const HSIN_VISEMES: VisemeInspectName[] = ["aa", "ih", "ou", "ee", "oh"];

const HSIN_VISEME_MAX_WEIGHTS: Record<VisemeInspectName, number> = {
  aa: 0.65,
  ih: 0.45,
  ou: 0.55,
  ee: 0.45,
  oh: 0.55,
};

const HSIN_FAKE_SPEECH_SEQUENCE: Array<VisemeInspectName | null> = [
  "aa",
  "ih",
  null,
  "ou",
  "ee",
  "oh",
  null,
  "ih",
  "aa",
  "ou",
  null,
  "ee",
];

const SPEECH_CROSSFADE_MS = 90;

function getCueWeight(cue: VisemeCue | undefined) {
  if (!cue || cue.viseme === "sil") return null;
  const viseme = cue.viseme as VisemeInspectName;
  return {
    viseme,
    weight: HSIN_VISEME_MAX_WEIGHTS[viseme] * (cue.weight ?? 1),
  };
}

function sampleTimedSpeech(
  playback: SpeechPlaybackSnapshot,
  nowMs: number,
): Record<VisemeInspectName, number> {
  const weights: Record<VisemeInspectName, number> = {
    aa: 0,
    ih: 0,
    ou: 0,
    ee: 0,
    oh: 0,
  };
  if (playback.status === "idle" || playback.cues.length === 0) return weights;

  const elapsedMs =
    playback.status === "paused"
      ? playback.pausedAtMs
      : Math.max(0, nowMs - playback.startedAtMs);
  const nextIndex = playback.cues.findIndex((cue) => cue.startMs > elapsedMs);
  const currentIndex = nextIndex === -1 ? playback.cues.length - 1 : nextIndex - 1;
  if (currentIndex < 0) return weights;

  const currentCue = playback.cues[currentIndex];
  const nextCue = nextIndex === -1 ? undefined : playback.cues[nextIndex];
  const currentShape = getCueWeight(currentCue);
  const nextShape = getCueWeight(nextCue);
  const currentEndMs = currentCue.durationMs == null
    ? (nextCue?.startMs ?? playback.endMs)
    : Math.min(currentCue.startMs + currentCue.durationMs, nextCue?.startMs ?? Infinity);

  let currentAmount = 1;
  let nextAmount = 0;
  const fadeIn = smoothStep01((elapsedMs - currentCue.startMs) / SPEECH_CROSSFADE_MS);
  currentAmount *= fadeIn;

  if (nextCue && elapsedMs >= nextCue.startMs - SPEECH_CROSSFADE_MS) {
    const blend = smoothStep01(
      (elapsedMs - (nextCue.startMs - SPEECH_CROSSFADE_MS)) /
        SPEECH_CROSSFADE_MS,
    );
    currentAmount *= 1 - blend;
    nextAmount = blend;
  } else if (elapsedMs >= currentEndMs - SPEECH_CROSSFADE_MS) {
    currentAmount *= 1 - smoothStep01(
      (elapsedMs - (currentEndMs - SPEECH_CROSSFADE_MS)) /
        SPEECH_CROSSFADE_MS,
    );
  }

  if (currentShape) weights[currentShape.viseme] += currentShape.weight * currentAmount;
  if (nextShape) weights[nextShape.viseme] += nextShape.weight * nextAmount;
  return weights;
}

const HSIN_EXPRESSION_INSPECT_NAMES: ExpressionInspectName[] = [
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

const HSIN_STATE_EXPRESSIONS: Record<
  FaceExpressionState,
  Partial<Record<"happy" | "puzzled", number>>
> = {
  idle: { happy: 0.09 },
  listening: { happy: 0.3 },
  thinking: { puzzled: 0.48 },
  speaking: { happy: 0.4 },
};

type BlinkPhase = "waiting" | "closing" | "holding" | "opening";

function randomBlinkDelay() {
  const normalDelay = THREE.MathUtils.randFloat(2.5, 6);
  return Math.random() < 0.12
    ? normalDelay + THREE.MathUtils.randFloat(2.5, 5)
    : normalDelay;
}

function smoothStep01(value: number) {
  const clamped = THREE.MathUtils.clamp(value, 0, 1);
  return clamped * clamped * (3 - 2 * clamped);
}
const HSIN_HAND_OVERRIDE_BONES = [
  "leftHand",
  "rightHand",
  "leftThumbMetacarpal",
  "leftThumbProximal",
  "leftThumbDistal",
  "leftIndexProximal",
  "leftIndexIntermediate",
  "leftIndexDistal",
  "leftMiddleProximal",
  "leftMiddleIntermediate",
  "leftMiddleDistal",
  "leftRingProximal",
  "leftRingIntermediate",
  "leftRingDistal",
  "leftLittleProximal",
  "leftLittleIntermediate",
  "leftLittleDistal",
  "rightThumbMetacarpal",
  "rightThumbProximal",
  "rightThumbDistal",
  "rightIndexProximal",
  "rightIndexIntermediate",
  "rightIndexDistal",
  "rightMiddleProximal",
  "rightMiddleIntermediate",
  "rightMiddleDistal",
  "rightRingProximal",
  "rightRingIntermediate",
  "rightRingDistal",
  "rightLittleProximal",
  "rightLittleIntermediate",
  "rightLittleDistal",
] satisfies VRMHumanBoneName[];

const HSIN_RELAXED_FINGER_DEGREES: Partial<
  Record<VRMHumanBoneName, [number, number, number]>
> = {
  leftThumbMetacarpal: [3, -14, -2],
  leftThumbProximal: [1, -3, -4],
  leftThumbDistal: [0, 0, -2],
  leftIndexProximal: [0, 0, -4],
  leftIndexIntermediate: [0, 0, -7],
  leftIndexDistal: [0, 0, -2],
  leftMiddleProximal: [0, 0, -6],
  leftMiddleIntermediate: [0, 0, -9],
  leftMiddleDistal: [0, 0, -3],
  leftRingProximal: [0, 0, -8],
  leftRingIntermediate: [0, 0, -11],
  leftRingDistal: [0, 0, -4],
  leftLittleProximal: [0, 0, -10],
  leftLittleIntermediate: [0, 0, -13],
  leftLittleDistal: [0, 0, -5],
  rightThumbMetacarpal: [3, 12, 2],
  rightThumbProximal: [1, 3, 3],
  rightThumbDistal: [0, 0, 2],
  rightIndexProximal: [0, 0, 4],
  rightIndexIntermediate: [0, 0, 7],
  rightIndexDistal: [0, 0, 2],
  rightMiddleProximal: [0, 0, 6],
  rightMiddleIntermediate: [0, 0, 9],
  rightMiddleDistal: [0, 0, 3],
  rightRingProximal: [0, 0, 8],
  rightRingIntermediate: [0, 0, 11],
  rightRingDistal: [0, 0, 4],
  rightLittleProximal: [0, 0, 10],
  rightLittleIntermediate: [0, 0, 13],
  rightLittleDistal: [0, 0, 5],
};

const DIAGNOSTIC_BONES = [
  "hips",
  "spine",
  "chest",
  "upperChest",
  "neck",
  "head",
  "leftShoulder",
  "leftUpperArm",
  "leftLowerArm",
  "leftHand",
  "rightShoulder",
  "rightUpperArm",
  "rightLowerArm",
  "rightHand",
  "leftThumbMetacarpal",
  "leftThumbProximal",
  "leftThumbDistal",
  "leftIndexProximal",
  "leftIndexIntermediate",
  "leftIndexDistal",
  "leftMiddleProximal",
  "leftMiddleIntermediate",
  "leftMiddleDistal",
  "leftRingProximal",
  "leftRingIntermediate",
  "leftRingDistal",
  "leftLittleProximal",
  "leftLittleIntermediate",
  "leftLittleDistal",
  "rightThumbMetacarpal",
  "rightThumbProximal",
  "rightThumbDistal",
  "rightIndexProximal",
  "rightIndexIntermediate",
  "rightIndexDistal",
  "rightMiddleProximal",
  "rightMiddleIntermediate",
  "rightMiddleDistal",
  "rightRingProximal",
  "rightRingIntermediate",
  "rightRingDistal",
  "rightLittleProximal",
  "rightLittleIntermediate",
  "rightLittleDistal",
  "leftUpperLeg",
  "leftLowerLeg",
  "rightUpperLeg",
  "rightLowerLeg",
] satisfies VRMHumanBoneName[];

export type PoseTestMode =
  | "authored"
  | "relaxed"
  | "vrmaIdle"
  | "naturalIdle"
  | "hsinNeutral"
  | "normalizedRest";
export type PoseInspectionView = "front" | "leftThreeQuarter" | "rightThreeQuarter" | "side";
export type HandInspectionView =
  | "leftFront"
  | "leftSide"
  | "rightFront"
  | "rightSide";
export type RelaxedPoseTuning = Partial<
  Record<VRMHumanBoneName, [number, number, number]>
>;
export type ArmIkTargets = {
  left: [number, number, number];
  right: [number, number, number];
};
export type NeutralCalibrationTargets = {
  left: { elbow: [number, number, number]; wrist: [number, number, number] };
  right: { elbow: [number, number, number]; wrist: [number, number, number] };
};
export type CanonicalNeutralQuaternions = Partial<
  Record<VRMHumanBoneName, [number, number, number, number]>
>;
export const HSIN_CANONICAL_NEUTRAL: CanonicalNeutralQuaternions = {
  leftShoulder: [0, 0, 0, 1],
  leftUpperArm: [0.4541432127634268, -0.0426923047968934, -0.785247660585315, 0.41870923199439014],
  leftLowerArm: [0.31640274953606456, -0.2644316369546037, -0.5833062520046406, 0.699799275389612],
  leftHand: [0.3204702949775492, 0.09904316316938458, -0.30887489160836107, 0.8899918781653732],
  rightShoulder: [0, 0, 0, 1],
  rightUpperArm: [0.14836292766267567, 0.006328333798608223, 0.10033261419537595, 0.9838098192310416],
  rightLowerArm: [0.8800640980894184, -0.1309145001712487, 0.05559680533923466, 0.4530536084560439],
  rightHand: [-0.3184310463714805, -0.3632447591159741, 0.19831716500713806, 0.8528336389619452],
  leftThumbMetacarpal: [0.028104056619524264, -0.12135558144911059, -0.020506064544840368, 0.9919992369803303],
  leftThumbProximal: [0.009631758520114525, -0.02585555855285681, -0.03511450401887338, 0.9990023478086718],
  leftThumbDistal: [0, 0, -0.01745240643728351, 0.9998476951563913],
  leftIndexProximal: [0, 0, -0.03489949670250097, 0.9993908270190958],
  leftIndexIntermediate: [0, 0, -0.06104853953485687, 0.9981347984218669],
  leftIndexDistal: [0, 0, -0.01745240643728351, 0.9998476951563913],
  leftMiddleProximal: [0, 0, -0.052335956242943835, 0.9986295347545738],
  leftMiddleIntermediate: [0, 0, -0.07845909572784494, 0.996917333733128],
  leftMiddleDistal: [0, 0, -0.026176948307873153, 0.9996573249755573],
  leftRingProximal: [0, 0, -0.0697564737441253, 0.9975640502598242],
  leftRingIntermediate: [0, 0, -0.09584575252022398, 0.9953961983671789],
  leftRingDistal: [0, 0, -0.03489949670250097, 0.9993908270190958],
  leftLittleProximal: [0, 0, -0.08715574274765817, 0.9961946980917455],
  leftLittleIntermediate: [0, 0, -0.11320321376790672, 0.9935718556765875],
  leftLittleDistal: [0, 0, -0.043619387365336, 0.9990482215818578],
  rightThumbMetacarpal: [0.02785323130294883, 0.10402238117315392, 0.020086672024403115, 0.9939819250509717],
  rightThumbProximal: [0.010305277576737538, 0.02559456845380277, 0.06125330397338194, 0.9977408240981595],
  rightThumbDistal: [0, 0, 0.05233595624294383, 0.9986295347545739],
  rightIndexProximal: [-0.0006090802009086826, -0.017441774902830158, 0.10451254307640284, 0.9943704248665338],
  rightIndexIntermediate: [0, 0, 0.1478094111296106, 0.9890158633619167],
  rightIndexDistal: [0, 0, 0.06104853953485687, 0.998134798421867],
  rightMiddleProximal: [-0.00022843406864775454, -0.008723545132608727, 0.13052122218260645, 0.9914071101914461],
  rightMiddleIntermediate: [0, 0, 0.17364817766693036, 0.9848077530122081],
  rightMiddleDistal: [0, 0, 0.0697564737441253, 0.9975640502598242],
  rightRingProximal: [0.0003045516968497588, 0.008721219528731424, 0.17364156567641253, 0.9847702545505929],
  rightRingIntermediate: [0, 0, 0.21643961393810285, 0.9762960071199334],
  rightRingDistal: [0, 0, 0.09584575252022398, 0.9953961983671787],
  rightLittleProximal: [0.0007612632768451532, 0.01743579561349186, 0.21640664913655128, 0.9761473125092532],
  rightLittleIntermediate: [0, 0, 0.2588190451025208, 0.9659258262890682],
  rightLittleDistal: [0, 0, 0.11320321376790672, 0.9935718556765875],
};

// --- Arm / shoulder neutral-pose polish POC (dev-only A/B) ---------------
// The eight shoulder->hand bones that are safe to retune for the reference
// neutral. Fingers are deliberately excluded and never touched by this POC.
export const HSIN_ARM_BONES: VRMHumanBoneName[] = [
  "leftShoulder",
  "leftUpperArm",
  "leftLowerArm",
  "leftHand",
  "rightShoulder",
  "rightUpperArm",
  "rightLowerArm",
  "rightHand",
];

export type ArmPoseMode = "current" | "referenceCandidate";

// Per-bone local-space Euler delta (degrees, XYZ = pitch/yaw/roll) that is
// post-multiplied onto the frozen canonical arm quaternion to author the
// reference candidate. Empty/zero => candidate is byte-identical to current.
export type ArmCalibrationOffsets = Partial<
  Record<VRMHumanBoneName, [number, number, number]>
>;

export const HSIN_ARM_CALIBRATION_ZERO: ArmCalibrationOffsets =
  Object.fromEntries(
    HSIN_ARM_BONES.map((bone) => [bone, [0, 0, 0] as [number, number, number]]),
  );

// Reference Candidate V1 — conservative local-space Euler deltas (degrees,
// XYZ = pitch/yaw/roll) authored from the two Hsin reference stills toward a
// more relaxed neutral: elbows lowered, forearms more vertical, less forearm
// twist, wrists nearer neutral. Small by design (well within the POC safety
// bounds: upperArm <=6, lowerArm <=8, hand <=8, shoulder <=3). Shoulders are
// left untouched. Signs are a reasoned first pass on Hsin's non-canonical rest
// basis and are meant to be visually reviewed / tuned via the dev sliders.
export const HSIN_ARM_REFERENCE_V1_DELTAS: ArmCalibrationOffsets = {
  leftShoulder: [0, 0, 0],
  leftUpperArm: [-2, 0, -2],
  leftLowerArm: [-3, 0, 4],
  leftHand: [-5, 0, 4],
  rightShoulder: [0, 0, 0],
  rightUpperArm: [-2, 0, 2],
  rightLowerArm: [-5, 0, -3],
  rightHand: [0, 5, -4],
};

// Reference Candidate V2 — retunes the whole shoulder->hand chain toward the
// black-background reference silhouette (arms readable as separate from the
// sleeves). Emphasis shifts to the upper/lower arms: larger frontal-plane roll
// on the upper arm to lower the elbow and open a torso->arm gap (mirrored L/R),
// more lower-arm pitch to let the forearm descend toward the thigh, and a small
// lower-arm roll to reduce twist. Hands get only secondary cleanup; shoulders
// stay untouched. Within the wider V2 exploration bounds (shoulder <=4,
// upperArm <=10, lowerArm <=12, hand <=8). Not a scalar multiple of V1.
export const HSIN_ARM_REFERENCE_V2_DELTAS: ArmCalibrationOffsets = {
  leftShoulder: [0, 0, 0],
  leftUpperArm: [-3, 0, -8],
  leftLowerArm: [-6, 0, 6],
  leftHand: [-4, 0, 3],
  rightShoulder: [0, 0, 0],
  rightUpperArm: [-3, 0, 8],
  rightLowerArm: [-8, 0, -5],
  rightHand: [0, 4, -3],
};

// Reference Candidate V3 — refines V2 from the skeleton/anatomy diagnostic: a
// touch more lower-arm pitch for a slightly more relaxed elbow bend (toward
// ~15-22deg), and a stronger RIGHT-HAND-only de-rotation to pull the splayed,
// outward-facing palm back toward the forearm line (the right hand was the
// largest remaining visible issue). Upper arms and left hand keep V2; no forearm
// re-rotation is used to fix the palm. Bone lengths unchanged (rotation only).
export const HSIN_ARM_REFERENCE_V3_DELTAS: ArmCalibrationOffsets = {
  leftShoulder: [0, 0, 0],
  leftUpperArm: [-3, 0, -8],
  leftLowerArm: [-9, 0, 6],
  leftHand: [-4, 0, 3],
  rightShoulder: [0, 0, 0],
  rightUpperArm: [-3, 0, 8],
  rightLowerArm: [-11, 0, -5],
  rightHand: [0, 12, -10],
};

// Provisional right-side baseline: V3 arm chain with the V4 right-hand
// orientation folded in ([-6,18,-14]). Left side matches V3. Used as the start
// point for the left-arm pass so the accepted right side is preserved.
export const HSIN_ARM_BASELINE_DELTAS: ArmCalibrationOffsets = {
  leftShoulder: [0, 0, 0],
  leftUpperArm: [-3, 0, -8],
  leftLowerArm: [-9, 0, 6],
  leftHand: [-4, 0, 3],
  rightShoulder: [0, 0, 0],
  rightUpperArm: [-3, 0, 8],
  rightLowerArm: [-11, 0, -5],
  rightHand: [-6, 18, -14],
};

// Left Arm V1 — retunes ONLY the left arm on top of the baseline (right side
// unchanged). Opens the left upper arm further out/down so it reads outside the
// sleeve with a lower, unburied elbow; deepens forearm descent toward the thigh;
// small extra wrist relax. Tuned independently — NOT mirrored from the right.
export const HSIN_ARM_LEFT_V1_DELTAS: ArmCalibrationOffsets = {
  leftShoulder: [0, 0, 0],
  leftUpperArm: [-4, 0, -12],
  leftLowerArm: [-12, 0, 8],
  leftHand: [-6, 0, 5],
  rightShoulder: [0, 0, 0],
  rightUpperArm: [-3, 0, 8],
  rightLowerArm: [-11, 0, -5],
  rightHand: [-6, 18, -14],
};

// Left Arm V2 — softening pass over Left V1 (right side still frozen). Eases the
// upper-arm pitch slightly (less "arranged"), deepens forearm descent while
// cutting forearm twist (roll 8->5) to reduce stiffness, and lets the hand hang
// and settle beside the thigh (more pitch, less roll) so it rests rather than
// hovers. Left side only; tuned independently from the right.
export const HSIN_ARM_LEFT_V2_DELTAS: ArmCalibrationOffsets = {
  leftShoulder: [0, 0, 0],
  leftUpperArm: [-3, 0, -12],
  leftLowerArm: [-14, 0, 5],
  leftHand: [-8, 0, 2],
  rightShoulder: [0, 0, 0],
  rightUpperArm: [-3, 0, 8],
  rightLowerArm: [-11, 0, -5],
  rightHand: [-6, 18, -14],
};

// FINAL ARM CANDIDATE — the accepted combined neutral for the full-silhouette
// review: LEFT = Left V2, RIGHT arm chain = V3, RIGHT hand = V4. Identical in
// value to HSIN_ARM_LEFT_V2_DELTAS; named separately so it is unambiguous when
// frozen into HSIN_CANONICAL_NEUTRAL later. Paired with the Relaxed V3 right
// fingers. Nothing else (torso, lengths, etc.) changes.
export const HSIN_ARM_FINAL_CANDIDATE_DELTAS: ArmCalibrationOffsets = {
  leftShoulder: [0, 0, 0],
  leftUpperArm: [-3, 0, -12],
  leftLowerArm: [-14, 0, 5],
  leftHand: [-8, 0, 2],
  rightShoulder: [0, 0, 0],
  rightUpperArm: [-3, 0, 8],
  rightLowerArm: [-11, 0, -5],
  rightHand: [-6, 18, -14],
};

// RIGHT-HAND finger bones (thumb + 4 fingers x proximal/intermediate/distal).
// Isolated to the right hand for the relaxed-fingers POC; the left hand's 15
// finger bones are never referenced here.
export const HSIN_RIGHT_FINGER_BONES: VRMHumanBoneName[] = [
  "rightThumbMetacarpal",
  "rightThumbProximal",
  "rightThumbDistal",
  "rightIndexProximal",
  "rightIndexIntermediate",
  "rightIndexDistal",
  "rightMiddleProximal",
  "rightMiddleIntermediate",
  "rightMiddleDistal",
  "rightRingProximal",
  "rightRingIntermediate",
  "rightRingDistal",
  "rightLittleProximal",
  "rightLittleIntermediate",
  "rightLittleDistal",
];

// RIGHT HAND RELAXED FINGERS (dev-only) — small additive local Euler deltas
// (degrees, XYZ) post-multiplied onto the frozen canonical right-finger
// quaternions: a gentle curl (+Z, matching the canonical flexion sign) plus a
// slight draw-together (Y) so the fingers read relaxed rather than splayed.
// Small by design; no clenched fist, no straightening, no generic humanoid
// rotations. Left fingers are untouched.
export const HSIN_RIGHT_HAND_RELAXED_FINGER_DELTAS: ArmCalibrationOffsets = {
  rightThumbMetacarpal: [0, 0, 0],
  rightThumbProximal: [0, 0, 3],
  rightThumbDistal: [0, 0, 3],
  rightIndexProximal: [0, -2, 5],
  rightIndexIntermediate: [0, 0, 7],
  rightIndexDistal: [0, 0, 4],
  rightMiddleProximal: [0, -1, 5],
  rightMiddleIntermediate: [0, 0, 7],
  rightMiddleDistal: [0, 0, 4],
  rightRingProximal: [0, 1, 5],
  rightRingIntermediate: [0, 0, 7],
  rightRingDistal: [0, 0, 4],
  rightLittleProximal: [0, 2, 6],
  rightLittleIntermediate: [0, 0, 8],
  rightLittleDistal: [0, 0, 4],
};

// RIGHT HAND RELAXED FINGERS V2 (dev-only) — stronger, coordinated group curl so
// all four fingers read as one relaxed hand shape (not single-finger twitches).
// Deeper proximal/intermediate flexion (+Z, canonical sign) increasing from
// index -> little, plus a small draw-together (Y) toward the middle. Thumb curls
// gently inward. Still no fist / claw / straight-splay. Left fingers untouched.
export const HSIN_RIGHT_HAND_RELAXED_FINGER_DELTAS_V2: ArmCalibrationOffsets = {
  rightThumbMetacarpal: [0, 0, 0],
  rightThumbProximal: [0, 0, 6],
  rightThumbDistal: [0, 0, 5],
  rightIndexProximal: [0, -3, 10],
  rightIndexIntermediate: [0, 0, 12],
  rightIndexDistal: [0, 0, 6],
  rightMiddleProximal: [0, -1, 10],
  rightMiddleIntermediate: [0, 0, 12],
  rightMiddleDistal: [0, 0, 6],
  rightRingProximal: [0, 1, 12],
  rightRingIntermediate: [0, 0, 14],
  rightRingDistal: [0, 0, 7],
  rightLittleProximal: [0, 3, 14],
  rightLittleIntermediate: [0, 0, 16],
  rightLittleDistal: [0, 0, 8],
};

// RIGHT HAND RELAXED FINGERS V3 (dev-only) — final softening pass over V2. Same
// group-curl idea but with a smoother, non-uniform progression so the hand reads
// soft rather than claw-like: index eased off, middle relaxed, ring near V2,
// little slightly stronger than ring; thumb curl reduced; Y draw-together
// softened so the fingers don't pinch. Left fingers untouched.
export const HSIN_RIGHT_HAND_RELAXED_FINGER_DELTAS_V3: ArmCalibrationOffsets = {
  rightThumbMetacarpal: [0, 0, 0],
  rightThumbProximal: [0, 0, 4],
  rightThumbDistal: [0, 0, 4],
  rightIndexProximal: [0, -2, 8],
  rightIndexIntermediate: [0, 0, 10],
  rightIndexDistal: [0, 0, 5],
  rightMiddleProximal: [0, -1, 9],
  rightMiddleIntermediate: [0, 0, 11],
  rightMiddleDistal: [0, 0, 5],
  rightRingProximal: [0, 1, 12],
  rightRingIntermediate: [0, 0, 14],
  rightRingDistal: [0, 0, 7],
  rightLittleProximal: [0, 2, 15],
  rightLittleIntermediate: [0, 0, 17],
  rightLittleDistal: [0, 0, 8],
};

// RIGHT-HAND-only orientation deltas (local Euler degrees) for the hand-focused
// comparison. V3 is the current V3-candidate right hand; V4 pushes the palm
// further back toward the forearm line (stronger de-rotation) within the wider
// hand-only bounds (pitch <=12, yaw <=20, roll <=16). Hand bone only.
export const HSIN_RIGHT_HAND_ORIENT_V3: [number, number, number] = [0, 12, -10];
export const HSIN_RIGHT_HAND_ORIENT_V4: [number, number, number] = [-6, 18, -14];

// World-space arm geometry measured after the active candidate pose is applied.
// Dev-only diagnostic (arm polish); never used by production runtime.
export type ArmJointGeometry = {
  shoulder: [number, number, number];
  elbow: [number, number, number];
  wrist: [number, number, number];
  hand: [number, number, number];
  upperArmVector: [number, number, number];
  forearmVector: [number, number, number];
  elbowBendDeg: number;
  elbowLateralFromHips: number;
  elbowDepthFromHips: number;
  wristLateralFromHips: number;
  wristDepthFromHips: number;
  wristHeightFromHips: number;
};
export type ArmGeometryReport = {
  hips: [number, number, number];
  left: ArmJointGeometry;
  right: ArmJointGeometry;
};

export type HandOrientationTargets = {
  left: [number, number, number];
  right: [number, number, number];
};
export type ForearmCorrection = {
  left: [number, number, number];
  right: [number, number, number];
};
export type ExternalHumanoidAnimationSource = {
  url: string;
  format: "vrma" | "glb" | "gltf" | "fbx" | "bvh";
};

type MaterialAssignment = {
  mesh: THREE.Mesh;
  material: THREE.Material | THREE.Material[];
};

function createBasicMaterialFallback(source: THREE.Material) {
  const mtoon = source as THREE.Material & {
    isMToonMaterial?: boolean;
    color?: THREE.Color;
    map?: THREE.Texture | null;
    alphaMap?: THREE.Texture | null;
    ignoreVertexColor?: boolean;
  };
  const fallback = new THREE.MeshBasicMaterial({
    color: mtoon.color?.clone() ?? new THREE.Color(0xffffff),
    map: mtoon.map ?? null,
    alphaMap: mtoon.alphaMap ?? null,
  });

  // Copy render-state values explicitly. The texture objects are intentionally
  // shared and never mutated, so their loader-assigned color spaces stay intact.
  fallback.name = `${source.name || "MToon"} [MeshBasic fallback]`;
  fallback.opacity = source.opacity;
  fallback.transparent = source.transparent;
  fallback.alphaTest = source.alphaTest;
  fallback.alphaHash = source.alphaHash;
  fallback.alphaToCoverage = source.alphaToCoverage;
  fallback.side = source.side;
  fallback.shadowSide = source.shadowSide;
  fallback.depthTest = source.depthTest;
  fallback.depthWrite = source.depthWrite;
  fallback.depthFunc = source.depthFunc;
  fallback.colorWrite = source.colorWrite;
  fallback.blending = source.blending;
  fallback.blendSrc = source.blendSrc;
  fallback.blendDst = source.blendDst;
  fallback.blendEquation = source.blendEquation;
  fallback.blendSrcAlpha = source.blendSrcAlpha;
  fallback.blendDstAlpha = source.blendDstAlpha;
  fallback.blendEquationAlpha = source.blendEquationAlpha;
  fallback.premultipliedAlpha = source.premultipliedAlpha;
  fallback.dithering = source.dithering;
  fallback.polygonOffset = source.polygonOffset;
  fallback.polygonOffsetFactor = source.polygonOffsetFactor;
  fallback.polygonOffsetUnits = source.polygonOffsetUnits;
  fallback.clippingPlanes = source.clippingPlanes;
  fallback.clipIntersection = source.clipIntersection;
  fallback.clipShadows = source.clipShadows;
  fallback.stencilWrite = source.stencilWrite;
  fallback.stencilWriteMask = source.stencilWriteMask;
  fallback.stencilFunc = source.stencilFunc;
  fallback.stencilRef = source.stencilRef;
  fallback.stencilFuncMask = source.stencilFuncMask;
  fallback.stencilFail = source.stencilFail;
  fallback.stencilZFail = source.stencilZFail;
  fallback.stencilZPass = source.stencilZPass;
  fallback.toneMapped = source.toneMapped;
  fallback.visible = source.visible;
  fallback.vertexColors = mtoon.ignoreVertexColor !== true;
  fallback.userData = { ...source.userData, mtoonFallbackSource: source.name };

  return fallback;
}

/**
 * First-pass VRM renderer. Presence signals continue to drive subtle whole-body
 * motion. Natural blinking is driven through the VRM expression system, while
 * gaze and other expressions remain reserved for later integration phases.
 */
function HsinAvatar({
  signal,
  presentationFraming,
  forwardGaze,
  frontFacingCalibration,
  poseMode,
  poseTuning,
  inspectPose,
  springsEnabled,
  autoBlinkEnabled,
  manualBlinkSequence,
  lookAtEnabled,
  lookAtStrength,
  centerEyesSequence,
  headAttentionEnabled,
  headAttentionStrength,
  ambientIdleEnabled,
  ambientTriggerSequence,
  ambientTriggerVariation,
  onAmbientStateChange,
  speakingMotionEnabled,
  speakingGestureTrigger,
  speakingGestureVariant,
  rareMotionEnabled,
  rareTriggerSequence,
  rareTurnSide,
  onRareStateChange,
  orchestratorEnabled,
  orchestratorFastTest,
  orchestratorRareAuto,
  onOrchestratorStateChange,
  armPoseMode,
  armCalibration,
  onArmCandidateChange,
  showArmSkeleton,
  armAnatomyView,
  onArmGeometryChange,
  rightFingerDeltas,
  centerHeadSequence,
  forcedExpressionState,
  expressionInspectEnabled,
  expressionInspectName,
  expressionInspectWeight,
  visemeInspectEnabled,
  visemeInspectName,
  visemeInspectWeight,
  fakeSpeechEnabled,
  speechPlayback,
  handInspectionView,
  revealHands,
  handOverrideEnabled,
  forearmOverrideEnabled,
  forearmCorrection,
  neutralPose,
  neutralTargets,
  onCanonicalNeutralChange,
  armIkTargets,
  handOrientationTargets,
}: {
  signal: PresenceSignal;
  presentationFraming: AvatarPresentationFraming;
  forwardGaze: ForwardGazeCalibration;
  frontFacingCalibration: FrontFacingCalibration;
  poseMode: PoseTestMode;
  poseTuning: RelaxedPoseTuning;
  inspectPose: boolean;
  springsEnabled: boolean;
  autoBlinkEnabled: boolean;
  manualBlinkSequence: number;
  lookAtEnabled: boolean;
  lookAtStrength: number;
  centerEyesSequence: number;
  headAttentionEnabled: boolean;
  headAttentionStrength: number;
  ambientIdleEnabled: boolean;
  ambientTriggerSequence: number;
  ambientTriggerVariation: AmbientVariationName | null;
  onAmbientStateChange?: (state: AmbientIdleState) => void;
  speakingMotionEnabled: boolean;
  speakingGestureTrigger: number;
  speakingGestureVariant: SpeakingGestureVariant;
  rareMotionEnabled: boolean;
  rareTriggerSequence: number;
  rareTurnSide: RareTurnSide;
  onRareStateChange?: (state: RareMotionState) => void;
  orchestratorEnabled: boolean;
  orchestratorFastTest: boolean;
  orchestratorRareAuto: boolean;
  onOrchestratorStateChange?: (state: OrchestratorReadout) => void;
  armPoseMode: ArmPoseMode;
  armCalibration: ArmCalibrationOffsets;
  onArmCandidateChange?: (
    quaternions: Record<string, [number, number, number, number]>,
  ) => void;
  showArmSkeleton: boolean;
  armAnatomyView: boolean;
  onArmGeometryChange?: (geometry: ArmGeometryReport) => void;
  rightFingerDeltas: ArmCalibrationOffsets | null;
  centerHeadSequence: number;
  forcedExpressionState: FaceExpressionState | null;
  expressionInspectEnabled: boolean;
  expressionInspectName: ExpressionInspectName;
  expressionInspectWeight: number;
  visemeInspectEnabled: boolean;
  visemeInspectName: VisemeInspectName;
  visemeInspectWeight: number;
  fakeSpeechEnabled: boolean;
  speechPlayback: SpeechPlaybackSnapshot;
  handInspectionView: HandInspectionView | null;
  revealHands: boolean;
  handOverrideEnabled: boolean;
  forearmOverrideEnabled: boolean;
  forearmCorrection: ForearmCorrection;
  neutralPose: RelaxedPoseTuning;
  neutralTargets: NeutralCalibrationTargets;
  onCanonicalNeutralChange?: (pose: CanonicalNeutralQuaternions) => void;
  armIkTargets: ArmIkTargets;
  handOrientationTargets: HandOrientationTargets;
}) {
  const { camera, gl } = useThree();
  const rig = useRef<THREE.Group>(null);
  const avatarFrame = useRef<THREE.Group>(null);
  const time = useRef(0);
  const lastPosePhase = useRef<PoseTestMode | null>(null);
  const armOverlay = useRef<THREE.LineSegments>(null);
  const leftArmTargetMarker = useRef<THREE.Mesh>(null);
  const rightArmTargetMarker = useRef<THREE.Mesh>(null);
  const leftElbowTargetMarker = useRef<THREE.Mesh>(null);
  const rightElbowTargetMarker = useRef<THREE.Mesh>(null);
  const leftActualElbowMarker = useRef<THREE.Mesh>(null);
  const rightActualElbowMarker = useRef<THREE.Mesh>(null);
  const leftActualWristMarker = useRef<THREE.Mesh>(null);
  const rightActualWristMarker = useRef<THREE.Mesh>(null);
  const handTargetMarker = useRef<THREE.Mesh>(null);
  const loggedHandView = useRef<HandInspectionView | null>(null);
  const previousSpringsEnabled = useRef(false);
  const blinkState = useRef({
    phase: "waiting" as BlinkPhase,
    elapsed: 0,
    duration: randomBlinkDelay(),
    weight: 0,
    manualSequence: manualBlinkSequence,
  });
  const lookAtPointer = useRef(new THREE.Vector2());
  const smoothedLookAtPointer = useRef(new THREE.Vector2());
  const centeredLookAtPointer = useRef(new THREE.Vector2());
  const lastCenterEyesSequence = useRef(centerEyesSequence);
  const smoothedHeadAttention = useRef(new THREE.Vector2());
  const lastCenterHeadSequence = useRef(centerHeadSequence);
  const pointerMovementVersion = useRef(0);
  const centerHeadAtPointerVersion = useRef(0);
  const stateExpressionWeights = useRef({ happy: 0, puzzled: 0 });
  const previousFaceInspectEnabled = useRef(false);
  const previousHandOverrideEnabled = useRef(handOverrideEnabled);
  const armIkSolutionKey = useRef("");
  const armIkSolution = useRef(
    new Map<VRMHumanBoneName, THREE.Quaternion>(),
  );
  const neutralSolutionKey = useRef("");
  const neutralSolution = useRef(new Map<VRMHumanBoneName, THREE.Quaternion>());
  const gltf = useLoader(GLTFLoader, AVATAR_URL, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  });
  const vrm = gltf.userData.vrm as VRM;
  const vrmaGltf = useLoader(GLTFLoader, RELAXED_IDLE_VRMA_URL, (loader) => {
    loader.register((parser) => new VRMAnimationLoaderPlugin(parser));
  });
  const vrmAnimation = (
    vrmaGltf.userData.vrmAnimations as VRMAnimation[] | undefined
  )?.[0];
  const vrmaPlayback = useMemo(() => {
    if (!vrmAnimation) return null;
    const clip = createVRMAnimationClip(vrmAnimation, vrm);
    const maskedNodeNames = new Set(
      HSIN_HAND_OVERRIDE_BONES.flatMap((boneName) => {
        const nodeName = vrm.humanoid.getNormalizedBoneNode(boneName)?.name;
        return nodeName ? [`${nodeName}.quaternion`, `${nodeName}.position`] : [];
      }),
    );
    const maskedClip = clip.clone();
    maskedClip.name = `${clip.name} [Hsin hand override]`;
    maskedClip.tracks = clip.tracks.filter(
      (track) => !maskedNodeNames.has(track.name),
    );
    const mixer = new THREE.AnimationMixer(vrm.scene);
    const action = mixer.clipAction(clip);
    const maskedAction = mixer.clipAction(maskedClip);
    action.setLoop(THREE.LoopRepeat, Infinity);
    maskedAction.setLoop(THREE.LoopRepeat, Infinity);
    console.info(
      `[Hsin hand override] tracks=${JSON.stringify({
        original: clip.tracks.length,
        masked: maskedClip.tracks.length,
        removed: clip.tracks.length - maskedClip.tracks.length,
      })}`,
    );
    return { mixer, action, maskedAction, clip, maskedClip };
  }, [vrm, vrmAnimation]);

  useEffect(() => {
    const expressionManager = vrm.expressionManager;
    console.info(
      `[Hsin blink] ${JSON.stringify({
        api: "VRMExpressionManager.setValue/getValue/update",
        blinkAvailable: expressionManager?.getExpression("blink") != null,
        mappedExpressions:
          expressionManager?.expressions.map((expression) =>
            expression.expressionName,
          ) ?? [],
      })}`,
    );
    console.info(
      `[Hsin visemes] ${JSON.stringify(
        HSIN_VISEMES.map((name) => {
          const expression = expressionManager?.getExpression(name);
          const bindTypes =
            expression?.binds.map((bind) => bind.constructor.name) ?? [];
          return {
            name,
            available: expression != null,
            isBinary: expression?.isBinary ?? null,
            bindCount: bindTypes.length,
            bindTypes,
            morphOnly:
              bindTypes.length > 0 &&
              bindTypes.every((type) => type === "VRMExpressionMorphTargetBind"),
          };
        }),
      )}`,
    );
    return () => {
      expressionManager?.setValue("blink", 0);
      expressionManager?.setValue("happy", 0);
      expressionManager?.setValue("puzzled", 0);
      HSIN_VISEMES.forEach((name) => expressionManager?.setValue(name, 0));
      expressionManager?.update();
      vrmaPlayback?.mixer.stopAllAction();
      vrmaPlayback?.mixer.uncacheRoot(vrm.scene);
    };
  }, [vrm, vrmaPlayback]);

  useEffect(() => {
    const canvas = gl.domElement;
    const handlePointerMove = (event: PointerEvent) => {
      const bounds = canvas.getBoundingClientRect();
      if (bounds.width <= 0 || bounds.height <= 0) return;
      lookAtPointer.current.set(
        THREE.MathUtils.clamp(
          ((event.clientX - bounds.left) / bounds.width) * 2 - 1,
          -1,
          1,
        ),
        THREE.MathUtils.clamp(
          1 - ((event.clientY - bounds.top) / bounds.height) * 2,
          -1,
          1,
        ),
      );
      pointerMovementVersion.current += 1;
    };
    const handlePointerLeave = () => {
      lookAtPointer.current.set(0, 0);
      pointerMovementVersion.current += 1;
    };
    canvas.addEventListener("pointermove", handlePointerMove);
    canvas.addEventListener("pointerleave", handlePointerLeave);
    return () => {
      canvas.removeEventListener("pointermove", handlePointerMove);
      canvas.removeEventListener("pointerleave", handlePointerLeave);
    };
  }, [gl]);

  useEffect(() => {
    const lookAt = vrm.lookAt;
    if (!lookAt) {
      console.warn("[Hsin LookAt] No VRM LookAt component is available");
      return;
    }
    const applier = lookAt.applier;
    const expressionDriven = applier instanceof VRMLookAtExpressionApplier;
    const rangeApplier =
      expressionDriven || applier instanceof VRMLookAtBoneApplier
        ? applier
        : null;
    const originalAutoUpdate = lookAt.autoUpdate;
    lookAt.autoUpdate = false;
    console.info(
      `[Hsin LookAt] ${JSON.stringify({
        applierType: expressionDriven ? "expression" : "bone-or-custom",
        expressionDriven,
        offsetFromHeadBone: lookAt.offsetFromHeadBone.toArray(),
        rangeMapHorizontalInner: rangeApplier?.rangeMapHorizontalInner ?? null,
        rangeMapHorizontalOuter: rangeApplier?.rangeMapHorizontalOuter ?? null,
        rangeMapVerticalDown: rangeApplier?.rangeMapVerticalDown ?? null,
        rangeMapVerticalUp: rangeApplier?.rangeMapVerticalUp ?? null,
        workflow: "manual yaw/pitch + lookAt.update(delta)",
      })}`,
    );
    return () => {
      lookAt.reset();
      lookAt.update(0);
      lookAt.autoUpdate = originalAutoUpdate;
    };
  }, [vrm]);

  const poseDiagnostic = useMemo(() => {
    const normalizedNodes = new Map<VRMHumanBoneName, THREE.Object3D>();
    const rawNodes = new Map<VRMHumanBoneName, THREE.Object3D>();
    const normalizedRest = new Map<VRMHumanBoneName, THREE.Quaternion>();
    const rawQuaternions = new Map<VRMHumanBoneName, THREE.Quaternion>();
    const rawPositions = new Map<VRMHumanBoneName, THREE.Vector3>();
    const rawScales = new Map<VRMHumanBoneName, THREE.Vector3>();

    const mappedBoneNames = Object.keys(
      vrm.humanoid.humanBones,
    ) as VRMHumanBoneName[];
    mappedBoneNames.forEach((boneName) => {
      const normalized = vrm.humanoid.getNormalizedBoneNode(boneName);
      const raw = vrm.humanoid.getRawBoneNode(boneName);
      if (normalized) {
        normalizedNodes.set(boneName, normalized);
        normalizedRest.set(boneName, normalized.quaternion.clone());
      }
      if (raw) {
        rawNodes.set(boneName, raw);
        rawQuaternions.set(boneName, raw.quaternion.clone());
        rawPositions.set(boneName, raw.position.clone());
        rawScales.set(boneName, raw.scale.clone());
      }
    });

    console.info(
      `[Hsin pose diagnostic] ${JSON.stringify({
        autoUpdateHumanBones: vrm.humanoid.autoUpdateHumanBones,
        springBoneManager: Boolean(vrm.springBoneManager),
        bones: DIAGNOSTIC_BONES.map((boneName) => ({
          boneName,
          normalized: normalizedNodes.has(boneName),
          raw: rawNodes.has(boneName),
          rawNodeName: rawNodes.get(boneName)?.name ?? null,
        })),
      })}`,
    );

    return {
      normalizedNodes,
      normalizedRest,
      rawNodes,
      rawQuaternions,
      rawPositions,
      rawScales,
    };
  }, [vrm]);

  const relaxedFingerOffsets = useMemo(() => {
    const offsets = new Map<VRMHumanBoneName, THREE.Quaternion>();
    Object.entries(HSIN_RELAXED_FINGER_DEGREES).forEach(
      ([boneName, degrees]) => {
        if (!degrees) return;
        offsets.set(
          boneName as VRMHumanBoneName,
          new THREE.Quaternion().setFromEuler(
            new THREE.Euler(
              THREE.MathUtils.degToRad(degrees[0]),
              THREE.MathUtils.degToRad(degrees[1]),
              THREE.MathUtils.degToRad(degrees[2]),
              "XYZ",
            ),
          ),
        );
      },
    );
    return offsets;
  }, []);

  const forearmCorrectionOffsets = useMemo(() => {
    const offsets = new Map<"left" | "right", THREE.Quaternion>();
    (["left", "right"] as const).forEach((side) => {
      const [pitch, yaw, roll] = forearmCorrection[side];
      offsets.set(
        side,
        new THREE.Quaternion().setFromEuler(
          new THREE.Euler(
            THREE.MathUtils.degToRad(pitch),
            THREE.MathUtils.degToRad(yaw),
            THREE.MathUtils.degToRad(roll),
            "XYZ",
          ),
        ),
      );
    });
    return offsets;
  }, [forearmCorrection]);

  const neutralPoseOffsets = useMemo(() => {
    const offsets = new Map<VRMHumanBoneName, THREE.Quaternion>();
    Object.entries(neutralPose).forEach(
      ([boneName, degrees]) => {
        if (!degrees) return;
        offsets.set(
          boneName as VRMHumanBoneName,
          new THREE.Quaternion().setFromEuler(
            new THREE.Euler(
              THREE.MathUtils.degToRad(degrees[0]),
              THREE.MathUtils.degToRad(degrees[1]),
              THREE.MathUtils.degToRad(degrees[2]),
              "XYZ",
            ),
          ),
        );
      },
    );
    return offsets;
  }, [neutralPose]);
  const naturalIdleQuaternion = useMemo(() => new THREE.Quaternion(), []);
  const naturalIdleEuler = useMemo(() => new THREE.Euler(0, 0, 0, "XYZ"), []);
  // Ambient Idle Phase 1 POC: deterministic scheduler layered additively on
  // Natural Idle V2 (dev-gated; default OFF). Pure, torso/neck/head only.
  const ambientIdle = useMemo(() => new HsinAmbientIdle(), []);
  // Dev-only FAST TEST: a second instance of the SAME scheduler with only a
  // shorter cooldown (3-6s vs 25-45s). All variation offsets and enter/hold/exit
  // animation timing are the module's own constants, so they are identical to
  // the production instance — only the between-variation wait is accelerated.
  const ambientIdleFast = useMemo(
    () => new HsinAmbientIdle({ cooldownMin: 3, cooldownMax: 6 }),
    [],
  );
  const activeAmbientWasFast = useRef(false);
  const lastAmbientPhase = useRef<AmbientPhase>("idle");
  const lastAmbientVariation = useRef<AmbientVariationName | null>(null);
  const lastAmbientTrigger = useRef(ambientTriggerSequence);
  // Speaking Motion Phase 1 POC: restrained conversational body engagement + one
  // occasional right-arm beat while SPEAKING (dev-gated; default OFF). Pure;
  // additive via the same seam. Owns chest/upperChest/neck/head + right arm only
  // while enabled AND speaking.
  const speakingMotion = useMemo(() => new HsinSpeakingMotion(), []);
  const lastSpeakingGestureTrigger = useRef(speakingGestureTrigger);
  // Rare Larger Motion Phase 1 POC: isolated scheduler for one look-aside body
  // turn (dev-gated; default OFF). Pure; additive via the same seam. Suppresses
  // ambient while active; yields to speaking motion via a fast interrupt exit.
  const rareMotion = useMemo(() => new HsinRareMotion(), []);
  const lastRareTrigger = useRef(rareTriggerSequence);
  const lastRarePhase = useRef<RareMotionPhase>("idle");
  const rareSpeechWasActive = useRef(false);
  // Motion Orchestrator Phase 1 POC: decides WHEN the existing schedulers may
  // run (dev-gated; default OFF). Pure controller — adds no animation and never
  // mutates the schedulers' data. start()/reset() on the enable-toggle edges.
  const orchestrator = useMemo(() => new HsinMotionOrchestrator(), []);
  const prevOrchestratorEnabled = useRef(orchestratorEnabled);
  const lastOrchMode = useRef<OrchestratorMode | null>(null);
  const lastOrchSecond = useRef(-1);
  // Arm neutral-pose polish POC (dev-only A/B): reused temporaries + a signature
  // so the resulting candidate quaternions are reported to the dev UI only when
  // they actually change (not every frame).
  const armDeltaQuaternion = useMemo(() => new THREE.Quaternion(), []);
  const armDeltaEuler = useMemo(() => new THREE.Euler(0, 0, 0, "XYZ"), []);
  const lastArmCandidateSignature = useRef<string>("");
  // Arm geometry-diagnostic markers (dev-only): spheres per joint + a line
  // chain, plus a throttle for the geometry readout.
  const armSkelLeftShoulder = useRef<THREE.Mesh>(null);
  const armSkelLeftElbow = useRef<THREE.Mesh>(null);
  const armSkelLeftWrist = useRef<THREE.Mesh>(null);
  const armSkelLeftHand = useRef<THREE.Mesh>(null);
  const armSkelRightShoulder = useRef<THREE.Mesh>(null);
  const armSkelRightElbow = useRef<THREE.Mesh>(null);
  const armSkelRightWrist = useRef<THREE.Mesh>(null);
  const armSkelRightHand = useRef<THREE.Mesh>(null);
  const armSkeletonLines = useRef<THREE.LineSegments>(null);
  const lastArmGeometryTime = useRef(0);

  const applyHsinRelaxedHands = () => {
    HSIN_HAND_OVERRIDE_BONES.forEach((boneName) => {
      const node = poseDiagnostic.normalizedNodes.get(boneName);
      const rest = poseDiagnostic.normalizedRest.get(boneName);
      if (!node || !rest) return;
      node.quaternion.copy(rest);
      const offset = relaxedFingerOffsets.get(boneName);
      if (offset) node.quaternion.multiply(offset);
    });
  };

  const applyRelaxedFingersOnly = () => {
    HSIN_HAND_OVERRIDE_BONES.forEach((boneName) => {
      if (boneName === "leftHand" || boneName === "rightHand") return;
      const node = poseDiagnostic.normalizedNodes.get(boneName);
      if (!node) return;
      node.quaternion.identity();
      const offset = relaxedFingerOffsets.get(boneName);
      if (offset) node.quaternion.multiply(offset);
    });
  };

  const applyCanonicalNeutral = () => {
    Object.entries(HSIN_CANONICAL_NEUTRAL).forEach(
      ([boneName, quaternion]) => {
        if (!quaternion) return;
        poseDiagnostic.normalizedNodes
          .get(boneName as VRMHumanBoneName)
          ?.quaternion.fromArray(quaternion);
      },
    );
  };

  // Dev-only: measure world-space arm geometry after the active pose is applied.
  // Uses raw humanoid bone world positions (shoulder = upperArm root, elbow =
  // lowerArm, wrist = hand, hand-tip approximated by middleProximal).
  const measureArmGeometry = (): ArmGeometryReport | null => {
    vrm.scene.updateMatrixWorld(true);
    const wp = (name: VRMHumanBoneName) =>
      vrm.humanoid.getRawBoneNode(name)?.getWorldPosition(new THREE.Vector3()) ??
      null;
    const hips = wp("hips");
    if (!hips) return null;
    const r3 = (v: THREE.Vector3): [number, number, number] => [v.x, v.y, v.z];
    const perSide = (s: "left" | "right"): ArmJointGeometry | null => {
      const shoulder = wp(`${s}UpperArm` as VRMHumanBoneName);
      const elbow = wp(`${s}LowerArm` as VRMHumanBoneName);
      const wrist = wp(`${s}Hand` as VRMHumanBoneName);
      const hand =
        wp(`${s}MiddleProximal` as VRMHumanBoneName) ?? wrist?.clone() ?? null;
      if (!shoulder || !elbow || !wrist || !hand) return null;
      const bendDeg =
        180 -
        THREE.MathUtils.radToDeg(
          shoulder.clone().sub(elbow).angleTo(wrist.clone().sub(elbow)),
        );
      return {
        shoulder: r3(shoulder),
        elbow: r3(elbow),
        wrist: r3(wrist),
        hand: r3(hand),
        upperArmVector: r3(elbow.clone().sub(shoulder)),
        forearmVector: r3(wrist.clone().sub(elbow)),
        elbowBendDeg: bendDeg,
        elbowLateralFromHips: elbow.x - hips.x,
        elbowDepthFromHips: elbow.z - hips.z,
        wristLateralFromHips: wrist.x - hips.x,
        wristDepthFromHips: wrist.z - hips.z,
        wristHeightFromHips: wrist.y - hips.y,
      };
    };
    const left = perSide("left");
    const right = perSide("right");
    if (!left || !right) return null;
    return { hips: r3(hips), left, right };
  };

  const normalizedStandingPose = useMemo<VRMPose>(() => {
    const pose: VRMPose = {};
    Object.entries(poseTuning).forEach(([boneName, degrees]) => {
      if (!degrees) return;
      pose[boneName as VRMHumanBoneName] = {
        rotation: new THREE.Quaternion()
          .setFromEuler(
            new THREE.Euler(
              THREE.MathUtils.degToRad(degrees[0]),
              THREE.MathUtils.degToRad(degrees[1]),
              THREE.MathUtils.degToRad(degrees[2]),
              "XYZ",
            ),
          )
          .toArray(),
      };
    });
    return pose;
  }, [poseTuning]);

  const getArmTargetWorld = (side: "left" | "right") => {
    const hips = vrm.humanoid.getRawBoneNode("hips");
    const target = new THREE.Vector3(...armIkTargets[side]);
    if (!hips) return target;
    rig.current?.updateWorldMatrix(true, true);
    const rigRotation = rig.current?.getWorldQuaternion(new THREE.Quaternion());
    if (rigRotation) target.applyQuaternion(rigRotation);
    return target.add(hips.getWorldPosition(new THREE.Vector3()));
  };

  const applyHandOrientations = () => {
    (["left", "right"] as const).forEach((side) => {
      const hand = vrm.humanoid.getNormalizedBoneNode(`${side}Hand`);
      const [pitch, yaw, roll] = handOrientationTargets[side];
      hand?.quaternion.setFromEuler(
        new THREE.Euler(
          THREE.MathUtils.degToRad(pitch),
          THREE.MathUtils.degToRad(yaw),
          THREE.MathUtils.degToRad(roll),
          "XYZ",
        ),
      );
    });
  };

  const solveArmToTarget = (
    side: "left" | "right",
    target: THREE.Vector3,
  ) => {
    const prefix = side === "left" ? "left" : "right";
    const handName = `${prefix}Hand` as VRMHumanBoneName;
    const jointNames = [
      `${prefix}LowerArm`,
      `${prefix}UpperArm`,
      `${prefix}Shoulder`,
    ] as VRMHumanBoneName[];
    const rawHand = vrm.humanoid.getRawBoneNode(handName);
    const normalizedHand = vrm.humanoid.getNormalizedBoneNode(handName);
    const normalizedShoulder = vrm.humanoid.getNormalizedBoneNode(
      `${prefix}Shoulder` as VRMHumanBoneName,
    );
    const normalizedUpperArm = vrm.humanoid.getNormalizedBoneNode(
      `${prefix}UpperArm` as VRMHumanBoneName,
    );
    const normalizedLowerArm = vrm.humanoid.getNormalizedBoneNode(
      `${prefix}LowerArm` as VRMHumanBoneName,
    );
    if (
      !rawHand ||
      !normalizedHand ||
      !normalizedShoulder ||
      !normalizedUpperArm ||
      !normalizedLowerArm
    ) return;

    rig.current?.updateWorldMatrix(true, true);
    const shoulderPosition = normalizedShoulder.getWorldPosition(
      new THREE.Vector3(),
    );
    const upperPosition = normalizedUpperArm.getWorldPosition(new THREE.Vector3());
    const lowerPosition = normalizedLowerArm.getWorldPosition(new THREE.Vector3());
    const handPosition = normalizedHand.getWorldPosition(new THREE.Vector3());
    const reach =
      upperPosition.distanceTo(lowerPosition) +
      lowerPosition.distanceTo(handPosition);
    const shoulderToTarget = target.clone().sub(shoulderPosition);
    const safeTarget = target.clone();
    if (shoulderToTarget.length() > reach * 0.97) {
      safeTarget.copy(shoulderPosition).add(
        shoulderToTarget.normalize().multiplyScalar(reach * 0.97),
      );
    }

    const parentWorld = new THREE.Quaternion();
    const inverseParentWorld = new THREE.Quaternion();
    const deltaWorld = new THREE.Quaternion();
    const deltaLocal = new THREE.Quaternion();
    const currentDirection = new THREE.Vector3();
    const targetDirection = new THREE.Vector3();
    const axis = new THREE.Vector3();

    // This runs only when a target/baseline changes. The larger iteration budget
    // is needed to escape Hsin's extreme authored hand-on-head arm pose.
    for (let iteration = 0; iteration < 64; iteration += 1) {
      for (const [jointIndex, jointName] of jointNames.entries()) {
        const normalizedJoint = vrm.humanoid.getNormalizedBoneNode(jointName);
        if (!normalizedJoint || !normalizedJoint.parent) continue;

        rig.current?.updateWorldMatrix(true, true);
        normalizedJoint.updateWorldMatrix(true, false);
        normalizedHand.updateWorldMatrix(true, false);
        const jointPosition = normalizedJoint.getWorldPosition(new THREE.Vector3());
        const endPosition = normalizedHand.getWorldPosition(new THREE.Vector3());
        currentDirection.copy(endPosition).sub(jointPosition).normalize();
        targetDirection.copy(safeTarget).sub(jointPosition).normalize();
        axis.crossVectors(currentDirection, targetDirection);
        if (axis.lengthSq() < 1e-10) continue;
        axis.normalize();
        const angle = Math.min(
          currentDirection.angleTo(targetDirection),
          [0.22, 0.18, 0.07][jointIndex],
        );
        deltaWorld.setFromAxisAngle(axis, angle);
        normalizedJoint.parent.getWorldQuaternion(parentWorld);
        inverseParentWorld.copy(parentWorld).invert();
        deltaLocal
          .copy(inverseParentWorld)
          .multiply(deltaWorld)
          .multiply(parentWorld);
        normalizedJoint.quaternion.premultiply(deltaLocal).normalize();
        normalizedJoint.updateWorldMatrix(false, true);
      }
    }
    vrm.humanoid.update();
  };

  const getNeutralTargetWorld = (
    side: "left" | "right",
    joint: "elbow" | "wrist",
  ) => {
    const hips = vrm.humanoid.getRawBoneNode("hips");
    const target = new THREE.Vector3(...neutralTargets[side][joint]);
    if (!hips) return target;
    rig.current?.updateWorldMatrix(true, true);
    const rigRotation = rig.current?.getWorldQuaternion(new THREE.Quaternion());
    if (rigRotation) target.applyQuaternion(rigRotation);
    return target.add(hips.getWorldPosition(new THREE.Vector3()));
  };

  const rotateNormalizedTowardWorldDirection = (
    boneName: VRMHumanBoneName,
    rawChildName: VRMHumanBoneName,
    targetDirection: THREE.Vector3,
  ) => {
    const normalized = vrm.humanoid.getNormalizedBoneNode(boneName);
    const raw = vrm.humanoid.getRawBoneNode(boneName);
    const rawChild = vrm.humanoid.getRawBoneNode(rawChildName);
    if (!normalized?.parent || !raw || !rawChild) return;
    vrm.scene.updateMatrixWorld(true);
    const currentDirection = rawChild
      .getWorldPosition(new THREE.Vector3())
      .sub(raw.getWorldPosition(new THREE.Vector3()))
      .normalize();
    const deltaWorld = new THREE.Quaternion().setFromUnitVectors(
      currentDirection,
      targetDirection.clone().normalize(),
    );
    const parentWorld = normalized.parent.getWorldQuaternion(
      new THREE.Quaternion(),
    );
    const deltaLocal = parentWorld
      .clone()
      .invert()
      .multiply(deltaWorld)
      .multiply(parentWorld);
    normalized.quaternion.premultiply(deltaLocal).normalize();
    vrm.humanoid.update();
    vrm.scene.updateMatrixWorld(true);
  };

  const orientNeutralHand = (side: "left" | "right") => {
    const handName = `${side}Hand` as VRMHumanBoneName;
    const middleName = `${side}MiddleProximal` as VRMHumanBoneName;
    const indexName = `${side}IndexProximal` as VRMHumanBoneName;
    const littleName = `${side}LittleProximal` as VRMHumanBoneName;
    const normalizedHand = vrm.humanoid.getNormalizedBoneNode(handName);
    const rawHand = vrm.humanoid.getRawBoneNode(handName);
    const rawMiddle = vrm.humanoid.getRawBoneNode(middleName);
    const rawIndex = vrm.humanoid.getRawBoneNode(indexName);
    const rawLittle = vrm.humanoid.getRawBoneNode(littleName);
    const hips = vrm.humanoid.getRawBoneNode("hips");
    const head = vrm.humanoid.getRawBoneNode("head");
    if (!normalizedHand?.parent || !rawHand || !rawMiddle || !rawIndex || !rawLittle || !hips || !head) return;

    vrm.scene.updateMatrixWorld(true);
    const handPosition = rawHand.getWorldPosition(new THREE.Vector3());
    const hipsPosition = hips.getWorldPosition(new THREE.Vector3());
    const up = head
      .getWorldPosition(new THREE.Vector3())
      .sub(hipsPosition)
      .normalize();
    const inward = hipsPosition.clone().sub(handPosition).normalize();
    const forward = new THREE.Vector3().crossVectors(up, inward).normalize();
    if (side === "right") forward.negate();
    const desiredFinger = up.clone().negate().addScaledVector(forward, 0.1).normalize();
    const desiredPalm = inward
      .clone()
      .addScaledVector(forward, side === "left" ? -0.16 : -0.1)
      .normalize();
    const desiredAcross = new THREE.Vector3()
      .crossVectors(desiredFinger, desiredPalm)
      .normalize();
    desiredPalm.crossVectors(desiredAcross, desiredFinger).normalize();

    const currentFinger = rawMiddle
      .getWorldPosition(new THREE.Vector3())
      .sub(handPosition)
      .normalize();
    const currentAcross = rawLittle
      .getWorldPosition(new THREE.Vector3())
      .sub(rawIndex.getWorldPosition(new THREE.Vector3()))
      .normalize();
    const currentPalm = new THREE.Vector3()
      .crossVectors(currentAcross, currentFinger)
      .normalize();
    if (currentPalm.dot(desiredPalm) < 0) {
      currentAcross.negate();
      currentPalm.negate();
    }

    const currentBasis = new THREE.Matrix4().makeBasis(
      currentAcross,
      currentFinger,
      currentPalm,
    );
    const desiredBasis = new THREE.Matrix4().makeBasis(
      desiredAcross,
      desiredFinger,
      desiredPalm,
    );
    const currentWorld = new THREE.Quaternion().setFromRotationMatrix(currentBasis);
    const desiredWorld = new THREE.Quaternion().setFromRotationMatrix(desiredBasis);
    const deltaWorld = desiredWorld.multiply(currentWorld.invert());
    const parentWorld = normalizedHand.parent.getWorldQuaternion(
      new THREE.Quaternion(),
    );
    normalizedHand.quaternion.premultiply(
      parentWorld.clone().invert().multiply(deltaWorld).multiply(parentWorld),
    ).normalize();
    vrm.humanoid.update();
  };

  const solveCanonicalNeutralArm = (side: "left" | "right") => {
    const upperName = `${side}UpperArm` as VRMHumanBoneName;
    const lowerName = `${side}LowerArm` as VRMHumanBoneName;
    const handName = `${side}Hand` as VRMHumanBoneName;
    const rawUpper = vrm.humanoid.getRawBoneNode(upperName);
    const rawLower = vrm.humanoid.getRawBoneNode(lowerName);
    const rawHand = vrm.humanoid.getRawBoneNode(handName);
    if (!rawUpper || !rawLower || !rawHand) return;
    vrm.scene.updateMatrixWorld(true);
    const shoulder = rawUpper.getWorldPosition(new THREE.Vector3());
    const currentElbow = rawLower.getWorldPosition(new THREE.Vector3());
    const currentWrist = rawHand.getWorldPosition(new THREE.Vector3());
    const upperLength = shoulder.distanceTo(currentElbow);
    const lowerLength = currentElbow.distanceTo(currentWrist);
    const requestedWrist = getNeutralTargetWorld(side, "wrist");
    const pole = getNeutralTargetWorld(side, "elbow");
    const direction = requestedWrist.clone().sub(shoulder);
    const requestedDistance = direction.length();
    direction.normalize();
    const flexDegrees = side === "left" ? 11 : 14;
    const flexDistance = Math.sqrt(
      upperLength ** 2 +
        lowerLength ** 2 +
        2 * upperLength * lowerLength * Math.cos(THREE.MathUtils.degToRad(flexDegrees)),
    );
    const distance = Math.min(requestedDistance, flexDistance);
    const wrist = shoulder.clone().addScaledVector(direction, distance);
    const along =
      (upperLength ** 2 - lowerLength ** 2 + distance ** 2) /
      (2 * distance);
    const height = Math.sqrt(Math.max(0, upperLength ** 2 - along ** 2));
    const poleOffset = pole.clone().sub(shoulder);
    const planeNormal = new THREE.Vector3().crossVectors(direction, poleOffset);
    if (planeNormal.lengthSq() < 1e-8) planeNormal.set(0, 0, side === "left" ? 1 : -1);
    planeNormal.normalize();
    const bendDirection = new THREE.Vector3()
      .crossVectors(planeNormal, direction)
      .normalize();
    if (bendDirection.dot(poleOffset) < 0) bendDirection.negate();
    const elbow = shoulder
      .clone()
      .addScaledVector(direction, along)
      .addScaledVector(bendDirection, height);

    rotateNormalizedTowardWorldDirection(
      upperName,
      lowerName,
      elbow.clone().sub(shoulder),
    );
    const actualElbow = rawLower.getWorldPosition(new THREE.Vector3());
    rotateNormalizedTowardWorldDirection(
      lowerName,
      handName,
      wrist.clone().sub(actualElbow),
    );
    orientNeutralHand(side);
  };

  useLayoutEffect(() => {
    const fallbacks = new Map<THREE.Material, THREE.MeshBasicMaterial>();
    const assignments: MaterialAssignment[] = [];

    vrm.scene.traverse((object) => {
      if (!(object instanceof THREE.Mesh)) return;

      const original = object.material;
      const materials = Array.isArray(original) ? original : [original];
      if (
        !materials.some(
          (material) =>
            (material as THREE.Material & { isMToonMaterial?: boolean })
              .isMToonMaterial === true,
        )
      ) {
        return;
      }

      assignments.push({ mesh: object, material: original });
      object.material = materials.map((material) => {
        if (
          (material as THREE.Material & { isMToonMaterial?: boolean })
            .isMToonMaterial !== true
        ) {
          return material;
        }
        let fallback = fallbacks.get(material);
        if (!fallback) {
          fallback = createBasicMaterialFallback(material);
          fallbacks.set(material, fallback);
        }
        return fallback;
      });
      if (!Array.isArray(original)) object.material = object.material[0];
    });

    const diagnostics = [...fallbacks].map(([source, fallback]) => ({
      material: source.name,
      sourceType: "MToonMaterial",
      fallbackType: fallback.type,
      hasBaseColorMap: Boolean(fallback.map),
      textureColorSpace: fallback.map?.colorSpace ?? "none",
      alphaTest: fallback.alphaTest,
      transparent: fallback.transparent,
      side: fallback.side === THREE.DoubleSide ? "DoubleSide" : fallback.side,
    }));
    console.table(diagnostics);
    console.info(
      `[Hsin material fallback] ${JSON.stringify(diagnostics)}`,
    );

    return () => {
      assignments.forEach(({ mesh, material }) => {
        mesh.material = material;
      });
      fallbacks.forEach((material) => material.dispose());
    };
  }, [vrm]);

  useEffect(() => {
    if (!revealHands) return;
    const hidden = new Map<THREE.Material, boolean>();
    vrm.scene.traverse((object) => {
      if (!(object instanceof THREE.Mesh)) return;
      const materials = Array.isArray(object.material)
        ? object.material
        : [object.material];
      materials.forEach((material) => {
        if (/Gathering Wives - Cloth Xin_/i.test(material.name)) {
          if (!hidden.has(material)) hidden.set(material, material.visible);
          material.visible = false;
        }
      });
    });
    return () => hidden.forEach((visible, material) => {
      material.visible = visible;
    });
  }, [revealHands, vrm]);

  // ARM ANATOMY VIEW (dev-only): reversibly hide the large red/white sleeve
  // ("Cloth") material so the bare arms are visible for skeleton calibration.
  // Reuses the proven reveal-hands hide path; restores exact visibility on OFF.
  // Does not touch the production material fallback.
  useEffect(() => {
    if (!armAnatomyView) return;
    const hidden = new Map<THREE.Material, boolean>();
    const exposed: string[] = [];
    vrm.scene.traverse((object) => {
      if (!(object instanceof THREE.Mesh)) return;
      const materials = Array.isArray(object.material)
        ? object.material
        : [object.material];
      materials.forEach((material) => {
        if (/Gathering Wives - Cloth Xin_/i.test(material.name)) {
          if (!hidden.has(material)) {
            hidden.set(material, material.visible);
            exposed.push(material.name);
          }
          material.visible = false;
        }
      });
    });
    console.info(
      `[Hsin arm anatomy view] hidden=${JSON.stringify(exposed)}`,
    );
    return () =>
      hidden.forEach((visible, material) => {
        material.visible = visible;
      });
  }, [armAnatomyView, vrm]);

  // Dev-only measurement probe: applies canonical neutral + optional arm deltas
  // and returns world-space arm geometry. CPU-side FK, so it works regardless of
  // WebGL render state. Front-facing torso yaw is intentionally omitted so it is
  // applied consistently across Current/V1/V2 comparisons.
  useEffect(() => {
    if (!SHOW_CALIBRATION_DEBUG || typeof window === "undefined") return;
    const w = window as unknown as {
      __hsinArmProbe?: (deltas?: ArmCalibrationOffsets) => ArmGeometryReport | null;
    };
    w.__hsinArmProbe = (deltas) => {
      vrm.humanoid.resetNormalizedPose();
      applyCanonicalNeutral();
      if (deltas) {
        HSIN_ARM_BONES.forEach((bone) => {
          const node = poseDiagnostic.normalizedNodes.get(bone);
          const d = deltas[bone];
          if (node && d && (d[0] || d[1] || d[2])) {
            armDeltaEuler.set(
              THREE.MathUtils.degToRad(d[0]),
              THREE.MathUtils.degToRad(d[1]),
              THREE.MathUtils.degToRad(d[2]),
              "XYZ",
            );
            node.quaternion.multiply(
              armDeltaQuaternion.setFromEuler(armDeltaEuler),
            );
          }
        });
      }
      vrm.humanoid.update();
      return measureArmGeometry();
    };
    return () => {
      delete w.__hsinArmProbe;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vrm]);

  const framing = useMemo(() => {
    const scene = vrm.scene;
    scene.updateMatrixWorld(true);

    // Normalize the imported model to a predictable full-body frame without
    // modifying the source VRM or its skeleton hierarchy.
    const bounds = new THREE.Box3().setFromObject(scene);
    const size = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const scale = size.y > 0 ? 2.75 / size.y : 1;

    console.info(
      `[Hsin pose diagnostic] framing=${JSON.stringify({
        size: size.toArray(),
        center: center.toArray(),
        scale,
      })}`,
    );

    return {
      scale,
      position: new THREE.Vector3(
        -center.x * scale,
        -center.y * scale,
        -center.z * scale,
      ),
    };
  }, [vrm]);

  useFrame((renderState, delta) => {
    if (!rig.current) return;

    const d = Math.min(delta, 0.05);
    time.current += d;
    const t = time.current;
    const handOverrideChanged =
      handOverrideEnabled !== previousHandOverrideEnabled.current;
    if (poseMode !== lastPosePhase.current || handOverrideChanged) {
      lastPosePhase.current = poseMode;
      previousHandOverrideEnabled.current = handOverrideEnabled;
      time.current = 0;
      const previousAction = handOverrideEnabled
        ? vrmaPlayback?.action
        : vrmaPlayback?.maskedAction;
      const nextAction = handOverrideEnabled
        ? vrmaPlayback?.maskedAction
        : vrmaPlayback?.action;
      const previousTime = previousAction?.time ?? 0;
      vrmaPlayback?.mixer.stopAllAction();
      vrm.humanoid.resetNormalizedPose();
      if (poseMode === "authored") {
        poseDiagnostic.rawNodes.forEach((node, boneName) => {
          node.position.copy(poseDiagnostic.rawPositions.get(boneName)!);
          node.quaternion.copy(poseDiagnostic.rawQuaternions.get(boneName)!);
          node.scale.copy(poseDiagnostic.rawScales.get(boneName)!);
        });
      } else if (poseMode === "vrmaIdle") {
        nextAction?.reset().play();
        if (handOverrideChanged && nextAction) {
          nextAction.time = previousTime % nextAction.getClip().duration;
        }
        console.info(
          `[Hsin VRMA idle] playing=${JSON.stringify({
            source: RELAXED_IDLE_VRMA_URL,
            duration: nextAction?.getClip().duration ?? null,
            tracks: nextAction?.getClip().tracks.length ?? 0,
            handOverrideEnabled,
          })}`,
        );
      } else if (poseMode === "normalizedRest") {
        vrm.humanoid.update();
        vrm.scene.updateMatrixWorld(true);
        const armBones = [
          "leftShoulder",
          "leftUpperArm",
          "leftLowerArm",
          "leftHand",
          "rightShoulder",
          "rightUpperArm",
          "rightLowerArm",
          "rightHand",
        ] as const;
        const rotations = Object.fromEntries(
          armBones.map((boneName) => {
            const node = vrm.humanoid.getNormalizedBoneNode(boneName);
            const euler = node
              ? new THREE.Euler().setFromQuaternion(node.quaternion, "XYZ")
              : null;
            return [
              boneName,
              {
                quaternion: node?.quaternion.toArray() ?? null,
                eulerDegrees: euler
                  ? [euler.x, euler.y, euler.z].map(THREE.MathUtils.radToDeg)
                  : null,
              },
            ];
          }),
        );
        const worldPositions = Object.fromEntries(
          ["head", "leftHand", "rightHand", "hips"].map((boneName) => [
            boneName,
            vrm.humanoid
              .getRawBoneNode(boneName as VRMHumanBoneName)
              ?.getWorldPosition(new THREE.Vector3())
              .toArray() ?? null,
          ]),
        );
        console.info(
          `[Hsin normalized rest test] ${JSON.stringify({ rotations, worldPositions })}`,
        );
      }
      console.info(`[Hsin pose diagnostic] phase=${poseMode}`);
    }

    if (poseMode === "vrmaIdle") {
      vrmaPlayback?.mixer.update(d);
      if (forearmOverrideEnabled) {
        (["left", "right"] as const).forEach((side) => {
          const lowerArm = vrm.humanoid.getNormalizedBoneNode(
            `${side}LowerArm` as VRMHumanBoneName,
          );
          const correction = forearmCorrectionOffsets.get(side);
          if (lowerArm && correction) lowerArm.quaternion.multiply(correction);
        });
      }
      if (handOverrideEnabled) {
        applyHsinRelaxedHands();
      }
      vrm.humanoid.update();
      vrm.nodeConstraintManager?.update();
    } else if (poseMode === "normalizedRest") {
      vrm.humanoid.resetNormalizedPose();
      vrm.humanoid.update();
    } else {
    poseDiagnostic.normalizedNodes.forEach((node, boneName) => {
      node.quaternion.copy(poseDiagnostic.normalizedRest.get(boneName)!);
    });

    if (poseMode === "hsinNeutral") {
      const solutionKey = "HSIN_CANONICAL_NEUTRAL_V1";
      if (neutralSolutionKey.current !== solutionKey) {
        vrm.humanoid.resetNormalizedPose();
        neutralSolution.current.clear();
        applyCanonicalNeutral();
        Object.keys(HSIN_CANONICAL_NEUTRAL).forEach((boneName) => {
          const normalizedBoneName = boneName as VRMHumanBoneName;
          const node = poseDiagnostic.normalizedNodes.get(normalizedBoneName);
          if (node) neutralSolution.current.set(normalizedBoneName, node.quaternion.clone());
        });
        vrm.humanoid.update();
        neutralSolutionKey.current = solutionKey;
        onCanonicalNeutralChange?.(HSIN_CANONICAL_NEUTRAL);
        console.info(
          `[HSIN_CANONICAL_NEUTRAL] ${JSON.stringify(HSIN_CANONICAL_NEUTRAL)}`,
        );
        const geometry = (["left", "right"] as const).map((side) => {
          const shoulder = vrm.humanoid
            .getRawBoneNode(`${side}UpperArm` as VRMHumanBoneName)
            ?.getWorldPosition(new THREE.Vector3());
          const elbow = vrm.humanoid
            .getRawBoneNode(`${side}LowerArm` as VRMHumanBoneName)
            ?.getWorldPosition(new THREE.Vector3());
          const wrist = vrm.humanoid
            .getRawBoneNode(`${side}Hand` as VRMHumanBoneName)
            ?.getWorldPosition(new THREE.Vector3());
          const elbowTarget = getNeutralTargetWorld(side, "elbow");
          const wristTarget = getNeutralTargetWorld(side, "wrist");
          const elbowFlexDegrees = shoulder && elbow && wrist
            ? 180 - THREE.MathUtils.radToDeg(
                shoulder.clone().sub(elbow).angleTo(wrist.clone().sub(elbow)),
              )
            : null;
          return {
            side,
            shoulder: shoulder?.toArray() ?? null,
            elbowTarget: elbowTarget.toArray(),
            actualElbow: elbow?.toArray() ?? null,
            wristTarget: wristTarget.toArray(),
            actualWrist: wrist?.toArray() ?? null,
            wristTargetDistance: wrist?.distanceTo(wristTarget) ?? null,
            elbowFlexDegrees,
          };
        });
        console.info(`[Hsin neutral geometry] ${JSON.stringify(geometry)}`);
      } else {
        neutralSolution.current.forEach((quaternion, boneName) => {
          poseDiagnostic.normalizedNodes.get(boneName)?.quaternion.copy(quaternion);
        });
      }
      vrm.humanoid.update();
      vrm.nodeConstraintManager?.update();
    }

    if (poseMode === "naturalIdle") {
      vrm.humanoid.resetNormalizedPose();
      applyCanonicalNeutral();

      // Arm neutral-pose polish POC (dev-only): when the reference candidate is
      // active, post-multiply each arm bone's frozen canonical quaternion by its
      // local Euler calibration delta. Only the 8 shoulder->hand bones; fingers
      // are never touched. Default deltas are all zero => candidate == current.
      if (armPoseMode === "referenceCandidate") {
        const resolved: Record<string, [number, number, number, number]> = {};
        HSIN_ARM_BONES.forEach((boneName) => {
          const node = poseDiagnostic.normalizedNodes.get(boneName);
          if (!node) return;
          const delta = armCalibration[boneName];
          if (delta && (delta[0] || delta[1] || delta[2])) {
            armDeltaEuler.set(
              THREE.MathUtils.degToRad(delta[0]),
              THREE.MathUtils.degToRad(delta[1]),
              THREE.MathUtils.degToRad(delta[2]),
              "XYZ",
            );
            node.quaternion.multiply(
              armDeltaQuaternion.setFromEuler(armDeltaEuler),
            );
          }
          const q = node.quaternion;
          resolved[boneName] = [q.x, q.y, q.z, q.w];
        });
        const signature = JSON.stringify(resolved);
        if (signature !== lastArmCandidateSignature.current) {
          lastArmCandidateSignature.current = signature;
          onArmCandidateChange?.(resolved);
        }
      } else if (lastArmCandidateSignature.current !== "") {
        lastArmCandidateSignature.current = "";
      }

      // RIGHT HAND RELAXED FINGERS (dev-only): post-multiply the selected finger
      // delta set (Relaxed V1/V2; null = original) onto the frozen canonical
      // RIGHT finger quaternions. Left fingers are never referenced.
      // applyCanonicalNeutral already restored all fingers to canonical this
      // frame, so this is purely additive and reversible.
      if (rightFingerDeltas) {
        HSIN_RIGHT_FINGER_BONES.forEach((boneName) => {
          const node = poseDiagnostic.normalizedNodes.get(boneName);
          if (!node) return;
          const delta = rightFingerDeltas[boneName];
          if (delta && (delta[0] || delta[1] || delta[2])) {
            armDeltaEuler.set(
              THREE.MathUtils.degToRad(delta[0]),
              THREE.MathUtils.degToRad(delta[1]),
              THREE.MathUtils.degToRad(delta[2]),
              "XYZ",
            );
            node.quaternion.multiply(
              armDeltaQuaternion.setFromEuler(armDeltaEuler),
            );
          }
        });
      }

      const addMicroMotion = (
        boneName: VRMHumanBoneName,
        x: number,
        y: number,
        z: number,
      ) => {
        const node = poseDiagnostic.normalizedNodes.get(boneName);
        if (!node) return;
        naturalIdleEuler.set(
          THREE.MathUtils.degToRad(x),
          THREE.MathUtils.degToRad(y),
          THREE.MathUtils.degToRad(z),
          "XYZ",
        );
        node.quaternion.multiply(
          naturalIdleQuaternion.setFromEuler(naturalIdleEuler),
        );
      };

      const weightShift = Math.sin(t * 0.27 + 0.35) * 0.75;
      const breath = Math.sin(t * 0.61 + 0.8);
      const slowSway = Math.sin(t * 0.19 + 1.4);
      const headDrift = Math.sin(t * 0.14 + 2.1);
      const headTilt = Math.sin(t * 0.23 + 0.55);

      if (frontFacingCalibration.enabled) {
        addMicroMotion("hips", 0, frontFacingCalibration.hipsYaw, 0);
        addMicroMotion("spine", 0, frontFacingCalibration.spineYaw, 0);
        addMicroMotion("chest", 0, frontFacingCalibration.chestYaw, 0);
        addMicroMotion(
          "upperChest",
          0,
          frontFacingCalibration.upperChestYaw,
          0,
        );
        addMicroMotion(
          "leftShoulder",
          0,
          frontFacingCalibration.leftShoulderYaw,
          frontFacingCalibration.leftShoulderRoll,
        );
        addMicroMotion(
          "rightShoulder",
          0,
          frontFacingCalibration.rightShoulderYaw,
          frontFacingCalibration.rightShoulderRoll,
        );
      }

      addMicroMotion("hips", 0, 0, weightShift);
      addMicroMotion("spine", breath * 0.48, 0, slowSway * 0.52);
      addMicroMotion("chest", breath * 0.68, slowSway * 0.16, 0);
      addMicroMotion("upperChest", breath * 0.38, 0, slowSway * 0.12);
      addMicroMotion("neck", 0, headDrift * 0.42, headTilt * 0.16);
      addMicroMotion("head", 0, headDrift * 0.78, headTilt * 0.42);

      if (centerHeadSequence !== lastCenterHeadSequence.current) {
        lastCenterHeadSequence.current = centerHeadSequence;
        centerHeadAtPointerVersion.current = pointerMovementVersion.current;
      }
      const headTargetIsCentered =
        expressionInspectEnabled ||
        visemeInspectEnabled ||
        !headAttentionEnabled ||
        centerHeadAtPointerVersion.current === pointerMovementVersion.current;
      const headTarget = headTargetIsCentered
        ? centeredLookAtPointer.current
        : lookAtPointer.current;
      const applyHeadDeadzone = (value: number) =>
        Math.abs(value) < 0.12
          ? 0
          : Math.sign(value) * ((Math.abs(value) - 0.12) / 0.88);
      smoothedHeadAttention.current.set(
        THREE.MathUtils.damp(
          smoothedHeadAttention.current.x,
          applyHeadDeadzone(headTarget.x),
          1.55,
          d,
        ),
        THREE.MathUtils.damp(
          smoothedHeadAttention.current.y,
          applyHeadDeadzone(headTarget.y),
          1.35,
          d,
        ),
      );
      const attentionYaw =
        smoothedHeadAttention.current.x * 3 * headAttentionStrength;
      const attentionPitch =
        -smoothedHeadAttention.current.y * 1.5 * headAttentionStrength;
      const attentionRoll =
        -smoothedHeadAttention.current.x * 0.65 * headAttentionStrength;
      addMicroMotion(
        "neck",
        forwardGaze.headPitch * 0.35 + attentionPitch * 0.35,
        forwardGaze.headYaw * 0.35 + attentionYaw * 0.35,
        attentionRoll * 0.25,
      );
      addMicroMotion(
        "head",
        forwardGaze.headPitch + attentionPitch,
        forwardGaze.headYaw + attentionYaw,
        attentionRoll,
      );

      // Ambient Idle Phase 1 (dev-gated, default OFF): occasional subtle pose
      // variations, layered additively on the micro-motion above via the same
      // seam. Suppressed during expression/viseme inspect so diagnostics stay
      // clean. Touches only torso/neck/head — never arms/hands/springs.
      // Ambient is suppressed by the speaking layer ONLY when that dev POC is
      // itself enabled AND Hsin is actually speaking — so with Speaking Motion
      // OFF (production default) ambient behaves exactly as before, regardless
      // of timed speech / lip-sync being active.
      const isSpeaking = speechPlayback.status !== "idle";
      const speakingLayerActive = speakingMotionEnabled && isSpeaking;

      // Motion Orchestrator (dev-gated, default OFF). Decides — this same frame —
      // whether ambient may run and whether to auto-fire a rare turn, reading the
      // schedulers' previous-frame phases. When OFF, the effective gates collapse
      // to exactly the committed props so manual/default behavior is unchanged.
      const inspectActive = expressionInspectEnabled || visemeInspectEnabled;

      // FAST TEST: with the orchestrator on and fast-test on, ambient uses the
      // accelerated-cooldown instance; otherwise the production instance. On a
      // switch, reset the instance left behind so no stale offset lingers.
      const ambientFast = orchestratorEnabled && orchestratorFastTest;
      const activeAmbient = ambientFast ? ambientIdleFast : ambientIdle;
      if (ambientFast !== activeAmbientWasFast.current) {
        activeAmbientWasFast.current = ambientFast;
        (ambientFast ? ambientIdle : ambientIdleFast).reset();
        lastAmbientPhase.current = "idle";
        lastAmbientVariation.current = null;
      }

      if (orchestratorEnabled !== prevOrchestratorEnabled.current) {
        prevOrchestratorEnabled.current = orchestratorEnabled;
        if (orchestratorEnabled) {
          orchestrator.setFast(orchestratorFastTest);
          orchestrator.setAllowRareAuto(orchestratorRareAuto);
          orchestrator.start();
        } else {
          orchestrator.reset();
          lastOrchMode.current = null;
          lastOrchSecond.current = -1;
          onOrchestratorStateChange?.(orchestrator.getState());
        }
      }
      let ambientRun = ambientIdleEnabled;
      let rareEnabled = rareMotionEnabled;
      let orchestratorRareTrigger = false;
      let orchestratorRareSide: RareTurnSide = "right";
      if (orchestratorEnabled) {
        // Keep fast-test cadence + rare-auto gate in sync (no-op unless changed).
        orchestrator.setFast(orchestratorFastTest);
        orchestrator.setAllowRareAuto(orchestratorRareAuto);
        const decision = orchestrator.update({
          dt: d,
          speaking: speakingLayerActive,
          rareActive: rareMotion.getState().phase !== "idle",
          ambientActive: activeAmbient.getState().phase !== "idle",
          inspectActive,
        });
        ambientRun = decision.ambientAllowed;
        rareEnabled = true;
        orchestratorRareTrigger = decision.rareTrigger;
        orchestratorRareSide = decision.rareSide;
        // Throttled readout: emit on mode change or once per whole second.
        const sec = Math.ceil(decision.nextRareIn);
        if (
          decision.mode !== lastOrchMode.current ||
          sec !== lastOrchSecond.current
        ) {
          lastOrchMode.current = decision.mode;
          lastOrchSecond.current = sec;
          onOrchestratorStateChange?.({
            mode: decision.mode,
            nextRareIn: decision.nextRareIn,
            graceRemaining: decision.graceRemaining,
            ambientAllowed: decision.ambientAllowed,
            lastTransition: decision.lastTransition,
          });
        }
      }

      // Rare Larger Motion (dev-gated, default OFF). Updated BEFORE ambient so
      // its active state can suppress ambient this same frame. Priority:
      // speaking > rare > ambient. Speech owns the pose — it cannot be started
      // while speaking, and if speech begins mid-turn we kick off a fast
      // interrupt exit so Hsin returns promptly (but smoothly) to neutral. The
      // offsets are applied further down (after ambient, before speaking).
      let rareOffsets: RareMotionOffsets = {};
      let rareActive = false;
      if (rareEnabled && !expressionInspectEnabled && !visemeInspectEnabled) {
        if (speakingLayerActive) {
          if (!rareSpeechWasActive.current) rareMotion.beginExit();
          // Ignore any trigger requested while speaking owns the pose.
          lastRareTrigger.current = rareTriggerSequence;
        } else {
          // Manual dev trigger (still works when orchestrator is OFF or ON).
          if (rareTriggerSequence !== lastRareTrigger.current) {
            lastRareTrigger.current = rareTriggerSequence;
            rareMotion.trigger(rareTurnSide);
          }
          // Orchestrator auto-trigger (trigger() is a no-op unless idle, so this
          // never fights a manual/in-flight turn).
          if (orchestratorRareTrigger) rareMotion.trigger(orchestratorRareSide);
        }
        rareSpeechWasActive.current = speakingLayerActive;
        rareOffsets = rareMotion.update(d);
        const rareState = rareMotion.getState();
        rareActive = rareState.phase !== "idle";
        if (rareState.phase !== lastRarePhase.current) {
          lastRarePhase.current = rareState.phase;
          onRareStateChange?.(rareState);
          console.info(
            `[Hsin rare motion] ${JSON.stringify({
              phase: rareState.phase,
              variation: rareState.variation,
              side: rareState.side,
            })}`,
          );
        }
      } else {
        lastRareTrigger.current = rareTriggerSequence;
        rareSpeechWasActive.current = false;
        if (lastRarePhase.current !== "idle") {
          rareMotion.reset();
          lastRarePhase.current = "idle";
          onRareStateChange?.(rareMotion.getState());
        }
      }

      const ambientSuppressed =
        expressionInspectEnabled ||
        visemeInspectEnabled ||
        speakingLayerActive ||
        rareActive;
      if (ambientRun && !ambientSuppressed) {
        if (ambientTriggerSequence !== lastAmbientTrigger.current) {
          lastAmbientTrigger.current = ambientTriggerSequence;
          // null variation = alternate (scheduler picks, avoiding repeat);
          // a named variation = dev "trigger this one" button.
          activeAmbient.trigger(ambientTriggerVariation ?? undefined);
        }
        const ambientOffsets = activeAmbient.update(d);
        (Object.keys(ambientOffsets) as AmbientBone[]).forEach((bone) => {
          const offset = ambientOffsets[bone];
          if (offset) {
            addMicroMotion(
              bone as VRMHumanBoneName,
              offset.x,
              offset.y,
              offset.z,
            );
          }
        });
        const ambientState = activeAmbient.getState();
        if (
          ambientState.phase !== lastAmbientPhase.current ||
          ambientState.variation !== lastAmbientVariation.current
        ) {
          lastAmbientPhase.current = ambientState.phase;
          lastAmbientVariation.current = ambientState.variation;
          onAmbientStateChange?.(ambientState);
          console.info(
            `[Hsin ambient idle] ${JSON.stringify({
              phase: ambientState.phase,
              variation: ambientState.variation,
              timeRemaining: Number(ambientState.timeRemaining.toFixed(2)),
            })}`,
          );
        }
      } else {
        lastAmbientTrigger.current = ambientTriggerSequence;
        if (
          lastAmbientPhase.current !== "idle" ||
          lastAmbientVariation.current !== null
        ) {
          activeAmbient.reset();
          lastAmbientPhase.current = "idle";
          lastAmbientVariation.current = null;
          onAmbientStateChange?.(activeAmbient.getState());
        }
      }

      // Rare Larger Motion: apply the offsets computed above, layered after
      // ambient and before speaking so Speaking Motion composes on top (higher
      // priority). Torso/neck/head only — arms/hands/legs ride the hierarchy.
      (Object.keys(rareOffsets) as RareMotionBone[]).forEach((bone) => {
        const offset = rareOffsets[bone];
        if (offset) {
          addMicroMotion(bone as VRMHumanBoneName, offset.x, offset.y, offset.z);
        }
      });

      // Speaking Motion Phase 1 (dev-gated, default OFF). Highest-priority body
      // layer: while enabled it owns chest/upperChest/neck/head (micro-motion)
      // and the right upper/lower arm + hand (one occasional beat), applied via
      // the same additive seam. Ambient is already suppressed above while this
      // layer is active, so the two never write the same bones concurrently.
      // When disabled it resets to neutral so nothing lingers.
      if (speakingMotionEnabled && !expressionInspectEnabled && !visemeInspectEnabled) {
        speakingMotion.setVariant(speakingGestureVariant);
        if (speakingGestureTrigger !== lastSpeakingGestureTrigger.current) {
          lastSpeakingGestureTrigger.current = speakingGestureTrigger;
          speakingMotion.triggerGesture();
        }
        const speakingFrame = speakingMotion.update(d, isSpeaking);
        (Object.keys(speakingFrame.micro) as SpeakingMicroBone[]).forEach(
          (bone) => {
            const offset = speakingFrame.micro[bone];
            if (offset) {
              addMicroMotion(
                bone as VRMHumanBoneName,
                offset.x,
                offset.y,
                offset.z,
              );
            }
          },
        );
        (Object.keys(speakingFrame.gesture) as SpeakingGestureBone[]).forEach(
          (bone) => {
            const offset = speakingFrame.gesture[bone];
            if (offset) {
              addMicroMotion(
                bone as VRMHumanBoneName,
                offset.x,
                offset.y,
                offset.z,
              );
            }
          },
        );
      } else {
        lastSpeakingGestureTrigger.current = speakingGestureTrigger;
        speakingMotion.reset();
      }

      vrm.humanoid.update();
      vrm.nodeConstraintManager?.update();

      const springBoneManager = vrm.springBoneManager;
      const wasSpringsEnabled = previousSpringsEnabled.current;
      if (springsEnabled && springBoneManager) {
        const isFirstEnabledFrame = !wasSpringsEnabled;
        if (isFirstEnabledFrame) {
          springBoneManager.reset();
          vrm.scene.updateMatrixWorld(true);
          springBoneManager.setInitState();
        }
        const before = isFirstEnabledFrame
          ? [...springBoneManager.joints].map((joint) => ({
              name: joint.bone.name,
              quaternion: joint.bone.quaternion.clone(),
            }))
          : [];
        springBoneManager.update(d);
        if (isFirstEnabledFrame) {
          const joints = [...springBoneManager.joints];
          const groups: Record<string, { count: number; maxDegrees: number }> = {};
          before.forEach(({ name, quaternion }, index) => {
            const joint = joints[index];
            if (!joint) return;
            const lowerName = name.toLowerCase();
            const group = /tail/.test(lowerName)
              ? "tail"
              : /hair|bang|ponytail/.test(lowerName)
                ? "hair"
                : /cloth|skirt|ribbon|sleeve|dress/.test(lowerName)
                  ? "cloth/skirt/ribbon"
                  : "other";
            const degrees = THREE.MathUtils.radToDeg(
              quaternion.angleTo(joint.bone.quaternion),
            );
            const result = (groups[group] ??= { count: 0, maxDegrees: 0 });
            result.count += 1;
            result.maxDegrees = Math.max(result.maxDegrees, degrees);
          });
          console.info(
            `[Hsin spring init test] firstFrame=${JSON.stringify(groups)}`,
          );
        }
      } else if (!springsEnabled && wasSpringsEnabled && springBoneManager) {
        springBoneManager.reset();
        vrm.scene.updateMatrixWorld(true);
        console.info(
          "[Hsin spring init test] disabled; restored captured canonical spring state",
        );
      }
      previousSpringsEnabled.current = springsEnabled;
    }

    const expressionManager = vrm.expressionManager;
    if (expressionManager?.getExpression("blink")) {
      const blink = blinkState.current;
      if (manualBlinkSequence !== blink.manualSequence) {
        blink.manualSequence = manualBlinkSequence;
        blink.phase = "closing";
        blink.elapsed = 0;
        blink.duration = THREE.MathUtils.randFloat(0.04, 0.065);
      } else if (blink.phase === "waiting") {
        if (autoBlinkEnabled) {
          blink.elapsed += d;
          if (blink.elapsed >= blink.duration) {
            blink.phase = "closing";
            blink.elapsed = 0;
            blink.duration = THREE.MathUtils.randFloat(0.04, 0.065);
          }
        } else {
          blink.elapsed = 0;
          blink.duration = randomBlinkDelay();
        }
      } else {
        blink.elapsed += d;
      }

      if (blink.phase === "closing") {
        blink.weight = smoothStep01(blink.elapsed / blink.duration);
        if (blink.elapsed >= blink.duration) {
          blink.phase = "holding";
          blink.elapsed = 0;
          blink.duration = THREE.MathUtils.randFloat(0.015, 0.03);
          blink.weight = 1;
        }
      } else if (blink.phase === "holding") {
        blink.weight = 1;
        if (blink.elapsed >= blink.duration) {
          blink.phase = "opening";
          blink.elapsed = 0;
          blink.duration = THREE.MathUtils.randFloat(0.07, 0.11);
        }
      } else if (blink.phase === "opening") {
        blink.weight = 1 - smoothStep01(blink.elapsed / blink.duration);
        if (blink.elapsed >= blink.duration) {
          blink.phase = "waiting";
          blink.elapsed = 0;
          blink.duration = randomBlinkDelay();
          blink.weight = 0;
        }
      } else {
        blink.weight = 0;
      }

      expressionManager.setValue("blink", blink.weight);
    }

    const lookAt = vrm.lookAt;
    if (lookAt) {
      if (centerEyesSequence !== lastCenterEyesSequence.current) {
        lastCenterEyesSequence.current = centerEyesSequence;
        lookAtPointer.current.set(0, 0);
      }
      const target = lookAtEnabled
        ? lookAtPointer.current
        : centeredLookAtPointer.current;
      const applyDeadzone = (value: number) =>
        Math.abs(value) < 0.08
          ? 0
          : Math.sign(value) * ((Math.abs(value) - 0.08) / 0.92);
      const targetX = applyDeadzone(target.x);
      const targetY = applyDeadzone(target.y);
      smoothedLookAtPointer.current.set(
        THREE.MathUtils.damp(
          smoothedLookAtPointer.current.x,
          targetX,
          4.2,
          d,
        ),
        THREE.MathUtils.damp(
          smoothedLookAtPointer.current.y,
          targetY,
          3.8,
          d,
        ),
      );
      lookAt.yaw =
        forwardGaze.eyeYaw +
        smoothedLookAtPointer.current.x * 12 * lookAtStrength;
      lookAt.pitch =
        forwardGaze.eyePitch -
        smoothedLookAtPointer.current.y * 8 * lookAtStrength;
      lookAt.update(d);
    }
    const stateWeights = stateExpressionWeights.current;
    if (expressionInspectEnabled) {
      stateWeights.happy = 0;
      stateWeights.puzzled = 0;
      HSIN_EXPRESSION_INSPECT_NAMES.forEach((name) =>
        expressionManager?.setValue(name, 0),
      );
      expressionManager?.setValue(
        expressionInspectName,
        expressionInspectWeight,
      );
    } else {
      HSIN_EXPRESSION_INSPECT_NAMES.forEach((name) => {
        if (name !== "happy" && name !== "puzzled") {
          expressionManager?.setValue(name, 0);
        }
      });
      const expressionState: FaceExpressionState =
        speechPlayback.status !== "idle"
          ? "speaking"
          : forcedExpressionState ??
        (signal.activity === "listening" ||
        signal.activity === "thinking" ||
        signal.activity === "speaking"
          ? signal.activity
          : "idle");
      const expressionTargets = HSIN_STATE_EXPRESSIONS[expressionState];
      stateWeights.happy = THREE.MathUtils.damp(
        stateWeights.happy,
        expressionTargets.happy ?? 0,
        7,
        d,
      );
      stateWeights.puzzled = THREE.MathUtils.damp(
        stateWeights.puzzled,
        expressionTargets.puzzled ?? 0,
        7,
        d,
      );
      expressionManager?.setValue("happy", stateWeights.happy);
      expressionManager?.setValue("puzzled", stateWeights.puzzled);
    }
    const visemeWeights: Record<VisemeInspectName, number> = {
      aa: 0,
      ih: 0,
      ou: 0,
      ee: 0,
      oh: 0,
    };
    if (visemeInspectEnabled) {
      visemeWeights[visemeInspectName] = visemeInspectWeight;
    } else if (speechPlayback.status !== "idle") {
      Object.assign(visemeWeights, sampleTimedSpeech(speechPlayback, performance.now()));
    } else if (fakeSpeechEnabled) {
      const segmentDuration = 0.14;
      const sequencePosition = renderState.clock.elapsedTime / segmentDuration;
      const sequenceIndex = Math.floor(sequencePosition);
      const outgoing =
        HSIN_FAKE_SPEECH_SEQUENCE[
          sequenceIndex % HSIN_FAKE_SPEECH_SEQUENCE.length
        ];
      const incoming =
        HSIN_FAKE_SPEECH_SEQUENCE[
          (sequenceIndex + 1) % HSIN_FAKE_SPEECH_SEQUENCE.length
        ];
      const blend = smoothStep01(sequencePosition - sequenceIndex);
      if (outgoing) {
        visemeWeights[outgoing] +=
          HSIN_VISEME_MAX_WEIGHTS[outgoing] * (1 - blend);
      }
      if (incoming) {
        visemeWeights[incoming] += HSIN_VISEME_MAX_WEIGHTS[incoming] * blend;
      }
    }
    HSIN_VISEMES.forEach((name) =>
      expressionManager?.setValue(name, visemeWeights[name]),
    );
    expressionManager?.update();

    if (poseMode === "relaxed") {
      vrm.humanoid.setNormalizedPose(normalizedStandingPose);

      if (!springsEnabled) {
        const solutionKey = JSON.stringify({
          armIkTargets,
          handOrientationTargets,
          poseTuning,
        });
        if (armIkSolutionKey.current !== solutionKey) {
          vrm.humanoid.update();
          solveArmToTarget("left", getArmTargetWorld("left"));
          solveArmToTarget("right", getArmTargetWorld("right"));
          applyHandOrientations();
          vrm.humanoid.update();
          armIkSolution.current.clear();
          (["left", "right"] as const).forEach((side) => {
            (["Shoulder", "UpperArm", "LowerArm"] as const).forEach(
              (joint) => {
                const boneName = `${side}${joint}` as VRMHumanBoneName;
                const node = vrm.humanoid.getNormalizedBoneNode(boneName);
                if (node) {
                  armIkSolution.current.set(boneName, node.quaternion.clone());
                }
              },
            );
          });
          armIkSolutionKey.current = solutionKey;
          rig.current.updateWorldMatrix(true, true);
          const solvedDistances = (["left", "right"] as const).map((side) => {
            const rawHand = vrm.humanoid.getRawBoneNode(
              `${side}Hand` as VRMHumanBoneName,
            );
            const target = getArmTargetWorld(side);
            const position = rawHand?.getWorldPosition(new THREE.Vector3());
            return {
              side,
              target: target.toArray(),
              rawHand: position?.toArray() ?? null,
              distance: position?.distanceTo(target) ?? null,
            };
          });
          console.info(
            `[Hsin arm IK] cached new target solution ${JSON.stringify(solvedDistances)}`,
          );
        } else {
          armIkSolution.current.forEach((quaternion, boneName) => {
            vrm.humanoid
              .getNormalizedBoneNode(boneName)
              ?.quaternion.copy(quaternion);
          });
          applyHandOrientations();
          vrm.humanoid.update();
        }
        vrm.nodeConstraintManager?.update();
        if (Math.floor(t * 2) !== Math.floor((t - d) * 2)) {
          rig.current.updateWorldMatrix(true, true);
          const handDistances = (["left", "right"] as const).map((side) => {
            const rawHand = vrm.humanoid.getRawBoneNode(
              `${side}Hand` as VRMHumanBoneName,
            );
            const target = getArmTargetWorld(side);
            const position = rawHand?.getWorldPosition(new THREE.Vector3());
            return {
              side,
              target: target.toArray(),
              rawHand: position?.toArray() ?? null,
              distance: position?.distanceTo(target) ?? null,
            };
          });
          console.info(`[Hsin arm IK] ${JSON.stringify(handDistances)}`);
        }
        if (previousSpringsEnabled.current) {
          vrm.springBoneManager?.reset();
          console.info("[Hsin spring diagnostic] disabled; restored spring initial state");
        }
      } else {
        const isFirstSpringFrame = !previousSpringsEnabled.current;
        const before = isFirstSpringFrame
          ? [...(vrm.springBoneManager?.joints ?? [])].map((joint) => ({
              name: joint.bone.name,
              quaternion: joint.bone.quaternion.clone(),
            }))
          : [];
        vrm.update(d);
        if (isFirstSpringFrame) {
          const groups: Record<string, { count: number; maxDegrees: number }> = {};
          before.forEach(({ name, quaternion }, index) => {
            const joint = [...(vrm.springBoneManager?.joints ?? [])][index];
            if (!joint) return;
            const lowerName = name.toLowerCase();
            const group = /tail/.test(lowerName)
              ? "tail"
              : /hair|bang|ponytail/.test(lowerName)
                ? "hair"
                : /cloth|skirt|ribbon|sleeve|dress/.test(lowerName)
                  ? "cloth/skirt/ribbon"
                  : "unclassified";
            const degrees = THREE.MathUtils.radToDeg(
              quaternion.angleTo(joint.bone.quaternion),
            );
            const result = (groups[group] ??= { count: 0, maxDegrees: 0 });
            result.count += 1;
            result.maxDegrees = Math.max(result.maxDegrees, degrees);
          });
          console.info(`[Hsin spring diagnostic] firstFrame=${JSON.stringify(groups)}`);
        }
      }
    previousSpringsEnabled.current = springsEnabled;

    if (poseMode === "relaxed") {
      leftArmTargetMarker.current?.position.copy(getArmTargetWorld("left"));
      rightArmTargetMarker.current?.position.copy(getArmTargetWorld("right"));
    } else if (poseMode === "hsinNeutral") {
      leftArmTargetMarker.current?.position.copy(getNeutralTargetWorld("left", "wrist"));
      rightArmTargetMarker.current?.position.copy(getNeutralTargetWorld("right", "wrist"));
      leftElbowTargetMarker.current?.position.copy(getNeutralTargetWorld("left", "elbow"));
      rightElbowTargetMarker.current?.position.copy(getNeutralTargetWorld("right", "elbow"));
      const updateActual = (side: "left" | "right", elbowMarker: THREE.Mesh | null, wristMarker: THREE.Mesh | null) => {
        vrm.scene.updateMatrixWorld(true);
        elbowMarker?.position.copy(
          vrm.humanoid.getRawBoneNode(`${side}LowerArm` as VRMHumanBoneName)?.getWorldPosition(new THREE.Vector3()) ?? new THREE.Vector3(),
        );
        wristMarker?.position.copy(
          vrm.humanoid.getRawBoneNode(`${side}Hand` as VRMHumanBoneName)?.getWorldPosition(new THREE.Vector3()) ?? new THREE.Vector3(),
        );
      };
      updateActual("left", leftActualElbowMarker.current, leftActualWristMarker.current);
      updateActual("right", rightActualElbowMarker.current, rightActualWristMarker.current);
    }
    }
    }

    const faceInspectEnabled = expressionInspectEnabled || visemeInspectEnabled;
    if (faceInspectEnabled) {
      rig.current.updateMatrixWorld(true);
      const rawHead = vrm.humanoid.getRawBoneNode("head");
      if (rawHead) {
        rawHead.updateWorldMatrix(true, false);
        const faceTarget = rawHead
          .getWorldPosition(new THREE.Vector3())
          .add(new THREE.Vector3(0, 0.035, 0));
        camera.position.copy(faceTarget).add(new THREE.Vector3(0, 0, 0.55));
        camera.lookAt(faceTarget);
        camera.updateProjectionMatrix();
      }
    } else if (previousFaceInspectEnabled.current) {
      camera.position.set(0, presentationFraming.targetY, presentationFraming.cameraDistance);
      camera.lookAt(new THREE.Vector3(0, presentationFraming.targetY, 0));
      if (camera instanceof THREE.PerspectiveCamera) {
        camera.fov = presentationFraming.fov;
      }
      camera.updateProjectionMatrix();
    } else if (handInspectionView) {
      rig.current.updateMatrixWorld(true);
      const isLeft = handInspectionView.startsWith("left");
      const isSide = handInspectionView.endsWith("Side");
      const handName = isLeft ? "leftHand" : "rightHand";
      const normalizedHand = vrm.humanoid.getNormalizedBoneNode(handName);
      const rawHand = vrm.humanoid.getRawBoneNode(handName);
      if (rawHand) {
        rawHand.updateWorldMatrix(true, false);
        const targetWorld = rawHand.getWorldPosition(new THREE.Vector3());
        const normalizedWorld = normalizedHand?.getWorldPosition(
          new THREE.Vector3(),
        );
        const offset = isSide
          ? new THREE.Vector3(isLeft ? -0.6 : 0.6, 0, 0)
          : new THREE.Vector3(0, 0, 0.6);
        camera.position.copy(targetWorld).add(offset);
        camera.lookAt(targetWorld);
        camera.updateProjectionMatrix();

        if (handTargetMarker.current) {
          handTargetMarker.current.position.copy(targetWorld);
          handTargetMarker.current.updateWorldMatrix(true, false);

          if (loggedHandView.current !== handInspectionView) {
            loggedHandView.current = handInspectionView;
            const markerWorld = handTargetMarker.current.getWorldPosition(
              new THREE.Vector3(),
            );
            console.info(
              `[Hsin hand inspect] ${JSON.stringify({
                view: handInspectionView,
                normalizedHandWorld: normalizedWorld?.toArray() ?? null,
                rawHandWorld: targetWorld.toArray(),
                markerWorld: markerWorld.toArray(),
                distanceRawHandToMarker: targetWorld.distanceTo(markerWorld),
                camera: camera.position.toArray(),
              })}`,
            );
          }
        }
      }
    } else {
      loggedHandView.current = null;
    }
    previousFaceInspectEnabled.current = faceInspectEnabled;

    if (inspectPose && armOverlay.current) {
      vrm.scene.updateMatrixWorld(true);
      const points: number[] = [];
      const addSegment = (from: VRMHumanBoneName, to: VRMHumanBoneName) => {
        const fromNode = poseDiagnostic.normalizedNodes.get(from);
        const toNode = poseDiagnostic.normalizedNodes.get(to);
        if (!fromNode || !toNode) return;
        const a = fromNode.getWorldPosition(new THREE.Vector3());
        const b = toNode.getWorldPosition(new THREE.Vector3());
        armOverlay.current!.parent!.worldToLocal(a);
        armOverlay.current!.parent!.worldToLocal(b);
        points.push(...a.toArray(), ...b.toArray());
      };
      addSegment("chest", "leftShoulder");
      addSegment("leftShoulder", "leftUpperArm");
      addSegment("leftUpperArm", "leftLowerArm");
      addSegment("leftLowerArm", "leftHand");
      addSegment("chest", "rightShoulder");
      addSegment("rightShoulder", "rightUpperArm");
      addSegment("rightUpperArm", "rightLowerArm");
      addSegment("rightLowerArm", "rightHand");
      armOverlay.current.geometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(points, 3),
      );
    }

    // Arm skeleton diagnostic (dev-only): spheres at shoulder/elbow/wrist/hand
    // and a line chain, driven by actual raw bone world positions of the active
    // candidate pose. Markers are direct scene children (world == local).
    if (showArmSkeleton) {
      vrm.scene.updateMatrixWorld(true);
      const wp = (name: VRMHumanBoneName) =>
        vrm.humanoid.getRawBoneNode(name)?.getWorldPosition(new THREE.Vector3()) ??
        null;
      const place = (marker: THREE.Mesh | null, p: THREE.Vector3 | null) => {
        if (!marker) return;
        if (p) {
          marker.visible = true;
          marker.position.copy(p);
        } else {
          marker.visible = false;
        }
      };
      const lSh = wp("leftUpperArm");
      const lEl = wp("leftLowerArm");
      const lWr = wp("leftHand");
      const lHa = wp("leftMiddleProximal") ?? lWr;
      const rSh = wp("rightUpperArm");
      const rEl = wp("rightLowerArm");
      const rWr = wp("rightHand");
      const rHa = wp("rightMiddleProximal") ?? rWr;
      place(armSkelLeftShoulder.current, lSh);
      place(armSkelLeftElbow.current, lEl);
      place(armSkelLeftWrist.current, lWr);
      place(armSkelLeftHand.current, lHa);
      place(armSkelRightShoulder.current, rSh);
      place(armSkelRightElbow.current, rEl);
      place(armSkelRightWrist.current, rWr);
      place(armSkelRightHand.current, rHa);
      if (armSkeletonLines.current) {
        const pts: number[] = [];
        const seg = (a: THREE.Vector3 | null, b: THREE.Vector3 | null) => {
          if (a && b) pts.push(a.x, a.y, a.z, b.x, b.y, b.z);
        };
        seg(lSh, lEl);
        seg(lEl, lWr);
        seg(lWr, lHa);
        seg(rSh, rEl);
        seg(rEl, rWr);
        seg(rWr, rHa);
        armSkeletonLines.current.geometry.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(pts, 3),
        );
      }
      if (onArmGeometryChange && t - lastArmGeometryTime.current > 0.33) {
        lastArmGeometryTime.current = t;
        const geometry = measureArmGeometry();
        if (geometry) onArmGeometryChange(geometry);
      }
    }

    if (Math.floor(t * 2) !== Math.floor((t - d) * 2)) {
      let maxPositionDrift = 0;
      let maxScaleDrift = 0;
      poseDiagnostic.rawNodes.forEach((node, boneName) => {
        maxPositionDrift = Math.max(
          maxPositionDrift,
          node.position.distanceTo(poseDiagnostic.rawPositions.get(boneName)!),
        );
        maxScaleDrift = Math.max(
          maxScaleDrift,
          node.scale.distanceTo(poseDiagnostic.rawScales.get(boneName)!),
        );
      });
      if (maxPositionDrift > 1e-5 || maxScaleDrift > 1e-5) {
        console.warn(
          `[Hsin pose diagnostic] transform drift position=${maxPositionDrift} scale=${maxScaleDrift}`,
        );
      }
    }
    if (poseMode === "naturalIdle") {
      rig.current.rotation.x = 0;
      rig.current.rotation.z = 0;
      rig.current.position.y = 0;
    } else {
      const listening = signal.activity === "listening" ? 1 : 0;
      const thinking = signal.activity === "thinking" ? 1 : 0;
      const speaking = signal.activity === "speaking" ? 1 : 0;
      const targetLean = listening * 0.035 - thinking * 0.018 + speaking * 0.012;
      const targetTilt = thinking * 0.025;
      rig.current.rotation.x = THREE.MathUtils.damp(
        rig.current.rotation.x,
        targetLean,
        3,
        d,
      );
      rig.current.rotation.z = THREE.MathUtils.damp(
        rig.current.rotation.z,
        targetTilt + Math.sin(t * 0.55) * 0.006,
        3,
        d,
      );
      rig.current.position.y = Math.sin(t * (speaking ? 1.25 : 0.8)) * 0.008;
    }
  });

  return (
    <>
      <group ref={rig}>
        <group
          ref={avatarFrame}
          scale={framing.scale * presentationFraming.scale}
          position={[
            framing.position.x * presentationFraming.scale + presentationFraming.offsetX,
            framing.position.y * presentationFraming.scale + presentationFraming.offsetY,
            framing.position.z * presentationFraming.scale,
          ]}
        >
          <primitive object={vrm.scene} />
        </group>
        {SHOW_CALIBRATION_DEBUG && inspectPose && (
          <lineSegments ref={armOverlay} renderOrder={1000}>
            <bufferGeometry />
            <lineBasicMaterial color="#22d3ee" depthTest={false} transparent opacity={0.95} />
          </lineSegments>
        )}
      </group>
      {SHOW_CALIBRATION_DEBUG &&
        (poseMode === "relaxed" || poseMode === "hsinNeutral") && (
        <>
          <mesh ref={leftArmTargetMarker} renderOrder={1002}>
            <sphereGeometry args={[0.025, 16, 16]} />
            <meshBasicMaterial color="#22c55e" depthTest={false} />
          </mesh>
          <mesh ref={rightArmTargetMarker} renderOrder={1002}>
            <sphereGeometry args={[0.025, 16, 16]} />
            <meshBasicMaterial color="#f59e0b" depthTest={false} />
          </mesh>
          {poseMode === "hsinNeutral" && (
            <>
              <mesh ref={leftElbowTargetMarker} renderOrder={1002}>
                <sphereGeometry args={[0.022, 16, 16]} />
                <meshBasicMaterial color="#86efac" depthTest={false} />
              </mesh>
              <mesh ref={rightElbowTargetMarker} renderOrder={1002}>
                <sphereGeometry args={[0.022, 16, 16]} />
                <meshBasicMaterial color="#fde68a" depthTest={false} />
              </mesh>
              <mesh ref={leftActualElbowMarker} renderOrder={1003}>
                <sphereGeometry args={[0.014, 12, 12]} />
                <meshBasicMaterial color="#06b6d4" depthTest={false} />
              </mesh>
              <mesh ref={rightActualElbowMarker} renderOrder={1003}>
                <sphereGeometry args={[0.014, 12, 12]} />
                <meshBasicMaterial color="#f97316" depthTest={false} />
              </mesh>
              <mesh ref={leftActualWristMarker} renderOrder={1003}>
                <sphereGeometry args={[0.014, 12, 12]} />
                <meshBasicMaterial color="#0891b2" depthTest={false} />
              </mesh>
              <mesh ref={rightActualWristMarker} renderOrder={1003}>
                <sphereGeometry args={[0.014, 12, 12]} />
                <meshBasicMaterial color="#ea580c" depthTest={false} />
              </mesh>
            </>
          )}
        </>
      )}
      {SHOW_CALIBRATION_DEBUG && handInspectionView && (
        <mesh ref={handTargetMarker} renderOrder={1001}>
          <sphereGeometry args={[0.012, 16, 16]} />
          <meshBasicMaterial
            color="#ff2bd6"
            depthTest={false}
            transparent
            opacity={0.9}
          />
        </mesh>
      )}
      {SHOW_CALIBRATION_DEBUG && showArmSkeleton && (
        <>
          <lineSegments ref={armSkeletonLines} renderOrder={1004}>
            <bufferGeometry />
            <lineBasicMaterial color="#f0abfc" depthTest={false} transparent opacity={0.95} />
          </lineSegments>
          <mesh ref={armSkelLeftShoulder} renderOrder={1005}>
            <sphereGeometry args={[0.02, 16, 16]} />
            <meshBasicMaterial color="#22c55e" depthTest={false} />
          </mesh>
          <mesh ref={armSkelLeftElbow} renderOrder={1005}>
            <sphereGeometry args={[0.018, 16, 16]} />
            <meshBasicMaterial color="#06b6d4" depthTest={false} />
          </mesh>
          <mesh ref={armSkelLeftWrist} renderOrder={1005}>
            <sphereGeometry args={[0.016, 16, 16]} />
            <meshBasicMaterial color="#0891b2" depthTest={false} />
          </mesh>
          <mesh ref={armSkelLeftHand} renderOrder={1005}>
            <sphereGeometry args={[0.013, 16, 16]} />
            <meshBasicMaterial color="#a3e635" depthTest={false} />
          </mesh>
          <mesh ref={armSkelRightShoulder} renderOrder={1005}>
            <sphereGeometry args={[0.02, 16, 16]} />
            <meshBasicMaterial color="#f59e0b" depthTest={false} />
          </mesh>
          <mesh ref={armSkelRightElbow} renderOrder={1005}>
            <sphereGeometry args={[0.018, 16, 16]} />
            <meshBasicMaterial color="#f97316" depthTest={false} />
          </mesh>
          <mesh ref={armSkelRightWrist} renderOrder={1005}>
            <sphereGeometry args={[0.016, 16, 16]} />
            <meshBasicMaterial color="#ea580c" depthTest={false} />
          </mesh>
          <mesh ref={armSkelRightHand} renderOrder={1005}>
            <sphereGeometry args={[0.013, 16, 16]} />
            <meshBasicMaterial color="#fbbf24" depthTest={false} />
          </mesh>
        </>
      )}
    </>
  );
}

function InspectionCamera({
  enabled,
  view,
}: {
  enabled: boolean;
  view: PoseInspectionView;
}) {
  const { camera } = useThree();

  useEffect(() => {
    const positions: Record<PoseInspectionView, THREE.Vector3> = {
      front: new THREE.Vector3(1.8, 0.35, 1.8),
      leftThreeQuarter: new THREE.Vector3(0.65, 0.35, 2.45),
      rightThreeQuarter: new THREE.Vector3(2.45, 0.35, 0.65),
      side: new THREE.Vector3(0, 0.35, 2.55),
    };
    camera.position.copy(enabled ? positions[view] : new THREE.Vector3(0, 0, 4.25));
    camera.lookAt(enabled ? new THREE.Vector3(0, 0.3, 0) : new THREE.Vector3());
    camera.updateProjectionMatrix();
  }, [camera, enabled, view]);

  return null;
}

function PresentationCamera({
  enabled,
  framing,
}: {
  enabled: boolean;
  framing: AvatarPresentationFraming;
}) {
  const { camera } = useThree();

  useEffect(() => {
    if (!enabled) return;
    camera.position.set(0, framing.targetY, framing.cameraDistance);
    camera.lookAt(new THREE.Vector3(0, framing.targetY, 0));
    if (camera instanceof THREE.PerspectiveCamera) camera.fov = framing.fov;
    camera.updateProjectionMatrix();
  }, [camera, enabled, framing]);

  return null;
}

export function AvatarScene({
  signal,
  presentationFraming = CURRENT_AVATAR_FRAMING,
  forwardGaze = PROPOSED_FORWARD_GAZE,
  frontFacingCalibration = STRONG_FRONT_FACING_CANDIDATE,
  paused = false,
  poseMode = "authored",
  poseTuning,
  inspectPose = false,
  inspectionView = "front",
  springsEnabled = false,
  autoBlinkEnabled = true,
  manualBlinkSequence = 0,
  lookAtEnabled = true,
  lookAtStrength = 0.45,
  centerEyesSequence = 0,
  headAttentionEnabled = true,
  headAttentionStrength = 1,
  ambientIdleEnabled = false,
  ambientTriggerSequence = 0,
  ambientTriggerVariation = null,
  onAmbientStateChange,
  speakingMotionEnabled = false,
  speakingGestureTrigger = 0,
  speakingGestureVariant = "v2",
  rareMotionEnabled = false,
  rareTriggerSequence = 0,
  rareTurnSide = "right",
  onRareStateChange,
  orchestratorEnabled = false,
  orchestratorFastTest = false,
  orchestratorRareAuto = false,
  onOrchestratorStateChange,
  armPoseMode = "current",
  armCalibration = HSIN_ARM_CALIBRATION_ZERO,
  onArmCandidateChange,
  showArmSkeleton = false,
  armAnatomyView = false,
  onArmGeometryChange,
  rightFingerDeltas = null,
  centerHeadSequence = 0,
  forcedExpressionState = null,
  expressionInspectEnabled = false,
  expressionInspectName = "happy",
  expressionInspectWeight = 0.5,
  visemeInspectEnabled = false,
  visemeInspectName = "aa",
  visemeInspectWeight = 0.5,
  fakeSpeechEnabled = false,
  speechPlayback,
  handInspectionView = null,
  revealHands = false,
  handOverrideEnabled = false,
  forearmOverrideEnabled = false,
  forearmCorrection,
  neutralPose,
  neutralTargets,
  onCanonicalNeutralChange,
  armIkTargets,
  handOrientationTargets,
}: {
  signal: PresenceSignal;
  presentationFraming?: AvatarPresentationFraming;
  forwardGaze?: ForwardGazeCalibration;
  frontFacingCalibration?: FrontFacingCalibration;
  paused?: boolean;
  poseMode?: PoseTestMode;
  poseTuning: RelaxedPoseTuning;
  inspectPose?: boolean;
  inspectionView?: PoseInspectionView;
  springsEnabled?: boolean;
  autoBlinkEnabled?: boolean;
  manualBlinkSequence?: number;
  lookAtEnabled?: boolean;
  lookAtStrength?: number;
  centerEyesSequence?: number;
  headAttentionEnabled?: boolean;
  headAttentionStrength?: number;
  ambientIdleEnabled?: boolean;
  ambientTriggerSequence?: number;
  ambientTriggerVariation?: AmbientVariationName | null;
  onAmbientStateChange?: (state: AmbientIdleState) => void;
  speakingMotionEnabled?: boolean;
  speakingGestureTrigger?: number;
  speakingGestureVariant?: SpeakingGestureVariant;
  rareMotionEnabled?: boolean;
  rareTriggerSequence?: number;
  rareTurnSide?: RareTurnSide;
  onRareStateChange?: (state: RareMotionState) => void;
  orchestratorEnabled?: boolean;
  orchestratorFastTest?: boolean;
  orchestratorRareAuto?: boolean;
  onOrchestratorStateChange?: (state: OrchestratorReadout) => void;
  armPoseMode?: ArmPoseMode;
  armCalibration?: ArmCalibrationOffsets;
  onArmCandidateChange?: (
    quaternions: Record<string, [number, number, number, number]>,
  ) => void;
  showArmSkeleton?: boolean;
  armAnatomyView?: boolean;
  onArmGeometryChange?: (geometry: ArmGeometryReport) => void;
  rightFingerDeltas?: ArmCalibrationOffsets | null;
  centerHeadSequence?: number;
  forcedExpressionState?: FaceExpressionState | null;
  expressionInspectEnabled?: boolean;
  expressionInspectName?: ExpressionInspectName;
  expressionInspectWeight?: number;
  visemeInspectEnabled?: boolean;
  visemeInspectName?: VisemeInspectName;
  visemeInspectWeight?: number;
  fakeSpeechEnabled?: boolean;
  speechPlayback: SpeechPlaybackSnapshot;
  handInspectionView?: HandInspectionView | null;
  revealHands?: boolean;
  handOverrideEnabled?: boolean;
  forearmOverrideEnabled?: boolean;
  forearmCorrection: ForearmCorrection;
  neutralPose: RelaxedPoseTuning;
  neutralTargets: NeutralCalibrationTargets;
  onCanonicalNeutralChange?: (pose: CanonicalNeutralQuaternions) => void;
  armIkTargets: ArmIkTargets;
  handOrientationTargets: HandOrientationTargets;
}) {
  // Same first-paint re-measure nudge the orb uses (R3F can miss late layout).
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
      camera={{ position: [0, 0, 4.25], fov: 36 }}
      dpr={[1, 2]}
      frameloop={paused ? "never" : "always"}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={1.1} />
      <directionalLight position={[-3, 4, 3]} intensity={2.2} color="#ffffff" />
      <directionalLight position={[3, 1, 2]} intensity={1.2} color="#bdefff" />
      <InspectionCamera enabled={inspectPose && !handInspectionView} view={inspectionView} />
      <PresentationCamera
        enabled={
          !inspectPose &&
          !handInspectionView &&
          !expressionInspectEnabled &&
          !visemeInspectEnabled
        }
        framing={presentationFraming}
      />
      <HsinAvatar
        signal={signal}
        presentationFraming={presentationFraming}
        forwardGaze={forwardGaze}
        frontFacingCalibration={frontFacingCalibration}
        poseMode={poseMode}
        poseTuning={poseTuning}
        inspectPose={inspectPose}
        springsEnabled={springsEnabled}
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
        onAmbientStateChange={onAmbientStateChange}
        speakingMotionEnabled={speakingMotionEnabled}
        speakingGestureTrigger={speakingGestureTrigger}
        speakingGestureVariant={speakingGestureVariant}
        rareMotionEnabled={rareMotionEnabled}
        rareTriggerSequence={rareTriggerSequence}
        rareTurnSide={rareTurnSide}
        onRareStateChange={onRareStateChange}
        orchestratorEnabled={orchestratorEnabled}
        orchestratorFastTest={orchestratorFastTest}
        orchestratorRareAuto={orchestratorRareAuto}
        onOrchestratorStateChange={onOrchestratorStateChange}
        armPoseMode={armPoseMode}
        armCalibration={armCalibration}
        onArmCandidateChange={onArmCandidateChange}
        showArmSkeleton={showArmSkeleton}
        armAnatomyView={armAnatomyView}
        onArmGeometryChange={onArmGeometryChange}
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
        revealHands={revealHands}
        handOverrideEnabled={handOverrideEnabled}
        forearmOverrideEnabled={forearmOverrideEnabled}
        forearmCorrection={forearmCorrection}
        neutralPose={neutralPose}
        neutralTargets={neutralTargets}
        onCanonicalNeutralChange={onCanonicalNeutralChange}
        armIkTargets={armIkTargets}
        handOrientationTargets={handOrientationTargets}
      />
    </Canvas>
  );
}

useLoader.preload(GLTFLoader, AVATAR_URL, (loader) => {
  loader.register((parser) => new VRMLoaderPlugin(parser));
});
