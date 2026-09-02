"use client";

import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import {
  VRMLoaderPlugin,
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

const AVATAR_URL = "/assets/avatars/Hsin_FINAL_EXPORT_WORKING_FIXED.vrm";
const RELAXED_IDLE_VRMA_URL = "/assets/animations/hsin-relaxed-idle.vrma";
const SHOW_CALIBRATION_DEBUG = process.env.NODE_ENV !== "production";
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
  leftUpperArm: [0.46008867595713404, -0.10919560299218388, -0.7345722710784305, 0.4866192650377313],
  leftLowerArm: [0.40729593027403904, -0.3232519079154474, -0.5781911406869105, 0.628739400739605],
  leftHand: [0.37961383389756165, 0.08173997048984835, -0.3308682189071233, 0.8600803079103376],
  rightShoulder: [0, 0, 0, 1],
  rightUpperArm: [0.1733831295720082, 0.01748003896988334, 0.0310141588666062, 0.9842107805583236],
  rightLowerArm: [0.912644066417831, -0.16118115248821804, 0.0911740866053977, 0.3644018798614617],
  rightHand: [-0.2685427777613197, -0.4272972001976144, 0.37631632414628446, 0.7769735538591662],
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
  rightThumbProximal: [0.009405762322721644, 0.02593862593505052, 0.026395337515045917, 0.99927073682621],
  rightThumbDistal: [0, 0, 0.01745240643728351, 0.9998476951563913],
  rightIndexProximal: [0, 0, 0.03489949670250097, 0.9993908270190958],
  rightIndexIntermediate: [0, 0, 0.06104853953485687, 0.9981347984218669],
  rightIndexDistal: [0, 0, 0.01745240643728351, 0.9998476951563913],
  rightMiddleProximal: [0, 0, 0.052335956242943835, 0.9986295347545738],
  rightMiddleIntermediate: [0, 0, 0.07845909572784494, 0.996917333733128],
  rightMiddleDistal: [0, 0, 0.026176948307873153, 0.9996573249755573],
  rightRingProximal: [0, 0, 0.0697564737441253, 0.9975640502598242],
  rightRingIntermediate: [0, 0, 0.09584575252022398, 0.9953961983671789],
  rightRingDistal: [0, 0, 0.03489949670250097, 0.9993908270190958],
  rightLittleProximal: [0, 0, 0.08715574274765817, 0.9961946980917455],
  rightLittleIntermediate: [0, 0, 0.11320321376790672, 0.9935718556765875],
  rightLittleDistal: [0, 0, 0.043619387365336, 0.9990482215818578],
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
 * motion, while expressions, gaze, blinking, springs, and optimization remain
 * intentionally disabled for the next integration phases.
 */
function HsinAvatar({
  signal,
  poseMode,
  poseTuning,
  inspectPose,
  springsEnabled,
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
  poseMode: PoseTestMode;
  poseTuning: RelaxedPoseTuning;
  inspectPose: boolean;
  springsEnabled: boolean;
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
  const { camera } = useThree();
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
    return () => {
      vrmaPlayback?.mixer.stopAllAction();
      vrmaPlayback?.mixer.uncacheRoot(vrm.scene);
    };
  }, [vrm, vrmaPlayback]);

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

  useFrame((_, delta) => {
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

      addMicroMotion("hips", 0, 0, weightShift);
      addMicroMotion("spine", breath * 0.48, 0, slowSway * 0.52);
      addMicroMotion("chest", breath * 0.68, slowSway * 0.16, 0);
      addMicroMotion("upperChest", breath * 0.38, 0, slowSway * 0.12);
      addMicroMotion("neck", 0, headDrift * 0.42, headTilt * 0.16);
      addMicroMotion("head", 0, headDrift * 0.78, headTilt * 0.42);

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

    if (handInspectionView) {
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
        <group ref={avatarFrame} scale={framing.scale} position={framing.position}>
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

export function AvatarScene({
  signal,
  paused = false,
  poseMode = "authored",
  poseTuning,
  inspectPose = false,
  inspectionView = "front",
  springsEnabled = false,
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
  paused?: boolean;
  poseMode?: PoseTestMode;
  poseTuning: RelaxedPoseTuning;
  inspectPose?: boolean;
  inspectionView?: PoseInspectionView;
  springsEnabled?: boolean;
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
      <HsinAvatar
        signal={signal}
        poseMode={poseMode}
        poseTuning={poseTuning}
        inspectPose={inspectPose}
        springsEnabled={springsEnabled}
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
