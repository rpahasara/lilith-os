/** Presentation-only state for placing the single loaded avatar scene. */
export type PresenceScenario =
  | "dashboard-close"
  | "scenic-full-body"
  | "peek-left"
  | "peek-right"
  | "peek-top";

export type NamedAttentionTarget = "auto" | "center" | "command" | "today" | "next";

export type AttentionTarget =
  | NamedAttentionTarget
  | { kind: "custom"; x: number; y: number };

export type PresenceExpression =
  | "neutral"
  | "soft-smile"
  | "attentive"
  | "curious";

export type PresenceTransitionMode = "smooth" | "instant";
export type PresenceVisibility = "visible" | "hidden";
export type PresencePriority = "passive" | "normal" | "notable" | "urgent";

export interface PresenceDirectorState {
  scenario: PresenceScenario;
  attentionTarget: AttentionTarget;
  expression: PresenceExpression;
  transitionMode: PresenceTransitionMode;
  visibility: PresenceVisibility;
  priority: PresencePriority;
}

export interface PresenceFraming {
  scale: number;
  offsetX: number;
  offsetY: number;
  cameraDistance: number;
  fov: number;
  targetY: number;
  centerOnFace?: boolean;
}

export type PresenceAnchor = "stage" | "left-edge" | "right-edge" | "top-edge";
export type PresenceCropMode = "dashboard-dissolve" | "full-body" | "edge-peek" | "top-peek";

export interface PresenceViewport {
  anchor: PresenceAnchor;
  cropMode: PresenceCropMode;
  className: string;
  width: string;
  maxWidth?: string;
  height?: string;
  horizontalMask: string;
  verticalMask: string;
  transformOrigin: string;
}

export interface PresencePresentationProfile {
  scenario: PresenceScenario;
  label: string;
  framing: PresenceFraming;
  viewport: PresenceViewport;
  poseLayer: "dashboard-arms" | "canonical";
}

export interface NormalizedAttentionPoint {
  x: number;
  y: number;
}
