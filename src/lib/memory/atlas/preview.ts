/**
 * The Cognitive Atlas preview switch.
 *
 * Owner decision (2026-11-16): the Atlas ships in production as a clearly
 * labelled preview, opening on the synthetic simulation (see `synthetic.ts`
 * and `simulation.ts`), which says so on screen. Real memory (P1-4) is a
 * second, explicitly chosen source: a read-only projection of the authorized
 * memory read model (`real-source.ts`). Simulation stays the default.
 *
 * So the Atlas is included in every build, development and production alike.
 * This switch exists only to take it out again without a code change: a build
 * made with NEXT_PUBLIC_LILITH_ATLAS_PREVIEW=false has no `/memory/atlas`
 * (the route is a 404) and no Brain / Timeline switch on the Archive. The
 * value is fixed when the app is built.
 *
 * The switch decides whether the preview is included. `preview-self-test.ts`
 * holds the boundary that only `real-source.ts` reads the backend.
 */
export function atlasPreviewEnabled(
  flag: string | undefined = process.env.NEXT_PUBLIC_LILITH_ATLAS_PREVIEW,
): boolean {
  return flag !== "false";
}
