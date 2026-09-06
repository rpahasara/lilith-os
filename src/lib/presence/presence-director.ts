import type {
  AttentionTarget,
  NormalizedAttentionPoint,
  PresenceDirectorState,
  PresenceExpression,
  PresenceScenario,
  PresenceTransitionMode,
  PresenceVisibility,
} from "./presence-types";

const DEFAULT_STATE: PresenceDirectorState = {
  scenario: "dashboard-close",
  attentionTarget: "auto",
  expression: "neutral",
  transitionMode: "smooth",
  visibility: "visible",
  priority: "normal",
};

type Listener = () => void;

class PresenceDirector {
  private state = DEFAULT_STATE;
  private listeners = new Set<Listener>();

  getSnapshot = () => this.state;
  getServerSnapshot = () => DEFAULT_STATE;
  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  private update(patch: Partial<PresenceDirectorState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((listener) => listener());
  }

  setScenario(scenario: PresenceScenario) { this.update({ scenario }); }
  setAttentionTarget(attentionTarget: AttentionTarget) { this.update({ attentionTarget }); }
  setExpression(expression: PresenceExpression) { this.update({ expression }); }
  setTransitionMode(transitionMode: PresenceTransitionMode) { this.update({ transitionMode }); }
  setVisibility(visibility: PresenceVisibility) { this.update({ visibility }); }
  reset() { this.state = DEFAULT_STATE; this.listeners.forEach((listener) => listener()); }
}

export const lilithPresenceDirector = new PresenceDirector();

const NAMED_ATTENTION: Record<Exclude<AttentionTarget, object>, NormalizedAttentionPoint> = {
  auto: { x: 0, y: 0 },
  center: { x: 0, y: 0 },
  command: { x: 0, y: -0.72 },
  today: { x: -0.72, y: 0.18 },
  next: { x: 0.72, y: -0.02 },
};

export function resolveAttentionPoint(
  target: AttentionTarget,
  scenario: PresenceScenario,
): NormalizedAttentionPoint | null {
  if (typeof target === "object") {
    return { x: Math.max(-1, Math.min(1, target.x)), y: Math.max(-1, Math.min(1, target.y)) };
  }
  if (target === "auto") {
    if (scenario === "peek-left") return { x: 0.72, y: 0 };
    if (scenario === "peek-right") return { x: -0.72, y: 0 };
    if (scenario === "peek-top") return { x: 0, y: -0.58 };
    return null;
  }
  return NAMED_ATTENTION[target];
}

/** `null` preserves the current signal-driven expression behavior. */
export function expressionStateForRequest(
  expression: PresenceExpression,
): "listening" | "thinking" | null {
  if (expression === "soft-smile" || expression === "attentive") return "listening";
  if (expression === "curious") return "thinking";
  return null;
}
