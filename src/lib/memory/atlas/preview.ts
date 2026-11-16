/**
 * The Cognitive Atlas preview gate.
 *
 * The Atlas is a prototype that runs on synthetic data only (see `synthetic.ts`
 * and `simulation.ts`); it reads nothing from Lilith's real memory. Until it is
 * wired to real memory and approved for production, it is a preview:
 *
 *   development server   on, so the prototype can be worked on.
 *   production build     off, unless the build was made with
 *                        NEXT_PUBLIC_LILITH_ATLAS_PREVIEW=true.
 *
 * When it is off, `/memory/atlas` is a 404 and the Memory Archive shows no
 * Brain / Timeline switch: a built release looks exactly as it did before the
 * prototype existed. The value is fixed when the app is built.
 */
export function atlasPreviewEnabled(
  flag: string | undefined = process.env.NEXT_PUBLIC_LILITH_ATLAS_PREVIEW,
  nodeEnv: string | undefined = process.env.NODE_ENV,
): boolean {
  return nodeEnv !== "production" || flag === "true";
}
