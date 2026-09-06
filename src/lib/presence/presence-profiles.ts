import type {
  PresenceFraming,
  PresencePresentationProfile,
  PresenceScenario,
} from "./presence-types";

const SCENIC_FULL_BODY_FRAMING: PresenceFraming = {
  scale: 1.15,
  offsetX: -0.03,
  offsetY: -0.06,
  cameraDistance: 4.05,
  fov: 34,
  targetY: 0.32,
};

const PEEK_LEFT_FRAMING: PresenceFraming = {
  scale: 1.22,
  offsetX: -0.04,
  offsetY: -0.08,
  cameraDistance: 2.65,
  fov: 24,
  targetY: 1.1,
  centerOnFace: true,
};

const PEEK_RIGHT_FRAMING: PresenceFraming = {
  scale: 1.24,
  offsetX: 0.025,
  offsetY: -0.06,
  cameraDistance: 2.7,
  fov: 24,
  targetY: 1.08,
  centerOnFace: true,
};

const PEEK_TOP_FRAMING: PresenceFraming = {
  scale: 1.22,
  offsetX: 0,
  offsetY: -0.05,
  cameraDistance: 2.65,
  fov: 23,
  targetY: 1.1,
  centerOnFace: true,
};

/**
 * Build the V1 table around the existing approved dashboard object. Passing
 * that object in keeps dashboard framing single-source and reference-identical.
 */
export function createPresenceProfiles(
  dashboardClose: PresenceFraming,
): Record<PresenceScenario, PresencePresentationProfile> {
  return {
    "dashboard-close": {
      scenario: "dashboard-close",
      label: "Dashboard close",
      framing: dashboardClose,
      viewport: {
        anchor: "stage",
        cropMode: "dashboard-dissolve",
        className: "absolute left-1/2 top-0 h-full -translate-x-1/2",
        width: "170%",
        maxWidth: "780px",
        horizontalMask: "linear-gradient(to right, transparent 0%, #000 15%, #000 85%, transparent 100%)",
        verticalMask: "linear-gradient(to bottom, #000 0%, #000 84%, transparent 100%)",
        transformOrigin: "50% 50%",
      },
      poseLayer: "dashboard-arms",
    },
    "scenic-full-body": {
      scenario: "scenic-full-body",
      label: "Scenic full body",
      framing: SCENIC_FULL_BODY_FRAMING,
      viewport: {
        anchor: "stage",
        cropMode: "full-body",
        className: "absolute left-1/2 top-0 h-full -translate-x-1/2",
        width: "156%",
        maxWidth: "760px",
        horizontalMask: "linear-gradient(to right, transparent 0%, #000 8%, #000 92%, transparent 100%)",
        verticalMask: "linear-gradient(to bottom, #000 0%, #000 94%, transparent 100%)",
        transformOrigin: "50% 50%",
      },
      poseLayer: "canonical",
    },
    "peek-left": {
      scenario: "peek-left",
      label: "Peek left",
      framing: PEEK_LEFT_FRAMING,
      viewport: {
        anchor: "left-edge",
        cropMode: "edge-peek",
        className: "fixed -left-[168px] top-[18vh] z-30",
        width: "380px",
        height: "430px",
        horizontalMask: "linear-gradient(to right, #000 0%, #000 68%, transparent 100%)",
        verticalMask: "linear-gradient(to bottom, #000 0%, #000 86%, transparent 100%)",
        transformOrigin: "0% 50%",
      },
      poseLayer: "canonical",
    },
    "peek-right": {
      scenario: "peek-right",
      label: "Peek right",
      framing: PEEK_RIGHT_FRAMING,
      viewport: {
        anchor: "right-edge",
        cropMode: "edge-peek",
        className: "fixed -right-[160px] top-[20vh] z-30",
        width: "380px",
        height: "430px",
        horizontalMask: "linear-gradient(to left, #000 0%, #000 68%, transparent 100%)",
        verticalMask: "linear-gradient(to bottom, #000 0%, #000 86%, transparent 100%)",
        transformOrigin: "100% 50%",
      },
      poseLayer: "canonical",
    },
    "peek-top": {
      scenario: "peek-top",
      label: "Peek top",
      framing: PEEK_TOP_FRAMING,
      viewport: {
        anchor: "top-edge",
        cropMode: "top-peek",
        className: "fixed -top-[188px] left-1/2 z-30 -translate-x-1/2",
        width: "420px",
        height: "390px",
        horizontalMask: "linear-gradient(to right, transparent 0%, #000 12%, #000 88%, transparent 100%)",
        verticalMask: "linear-gradient(to bottom, #000 0%, #000 72%, transparent 100%)",
        transformOrigin: "50% 0%",
      },
      poseLayer: "canonical",
    },
  };
}

export const PRESENCE_SCENARIOS: PresenceScenario[] = [
  "dashboard-close",
  "scenic-full-body",
  "peek-left",
  "peek-right",
  "peek-top",
];
