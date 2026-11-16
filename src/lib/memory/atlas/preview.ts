/**
 * The Cognitive Atlas preview switch.
 *
 * Owner decision (2026-11-16): the Atlas ships in production as a clearly
 * labelled preview. It runs on synthetic data only (see `synthetic.ts` and
 * `simulation.ts`), reads nothing from Lilith's real memory, and says so on
 * screen. Real memory arrives later, through the authorized read-only
 * interface, as a separate and separately approved change.
 *
 * So the Atlas is included in every build, development and production alike.
 * This switch exists only to take it out again without a code change: a build
 * made with NEXT_PUBLIC_LILITH_ATLAS_PREVIEW=false has no `/memory/atlas`
 * (the route is a 404) and no Brain / Timeline switch on the Archive. The
 * value is fixed when the app is built.
 *
 * The switch decides whether the preview is included. It never connects the
 * Atlas to real memory; `preview-self-test.ts` holds that boundary.
 */
export function atlasPreviewEnabled(
  flag: string | undefined = process.env.NEXT_PUBLIC_LILITH_ATLAS_PREVIEW,
): boolean {
  return flag !== "false";
}
