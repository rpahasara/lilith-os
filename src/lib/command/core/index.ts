/**
 * Public surface of the Cognitive Core (Vertical Slice 1). Import from
 * `@/lib/command/core`.
 */
export * from "./types";
export * from "./intents";
export * from "./planner";
export * from "./verifier";
export * from "./capabilities";
export * from "./career-capabilities";
export * from "./career-write";
export * from "./career-analysis";
export * from "./context";
export * from "./task-store";
export type { TaskPlaybook, PlaybookContext, StepResult } from "./playbook";
export { realTransport } from "./transport";
export { consoleCoreLogger, silentCoreLogger } from "./logger";
export { RealCommandCore } from "./real-core";
export { runCoreSelfTest, type SelfTestResult } from "./self-test";
