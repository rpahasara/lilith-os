/**
 * Public surface of the presence library. Import from `@/lib/presence`.
 *
 * The library is renderer-agnostic and React-agnostic (except the capability
 * hooks). React wiring lives in `@/components/presence/presence-engine`.
 */

export * from "./types";
export * from "./profiles";
export * from "./bus";
export * from "./reducer";
export * from "./map-events";
export * from "./capabilities";
export * from "./presence-types";
export * from "./presence-profiles";
export * from "./presence-director";
