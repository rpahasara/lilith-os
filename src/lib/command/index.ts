/**
 * Public surface of the LILITH Command System. Import from `@/lib/command`.
 *
 * The library is React-free: the store + surfaces live in
 * `@/components/command`. Everything here is types, the UI↔Core contract, the
 * pure reducer, and the V1 demo adapter.
 */

export * from "./types";
export * from "./events";
export * from "./reducer";
export * from "./presence";
export * from "./fixtures";
export { DemoCommandCore } from "./demo-core";
