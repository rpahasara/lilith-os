import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { atlasPreviewEnabled } from "@/lib/memory/atlas/preview";

// Absolute: the parent Memory layout sets a plain title, which ends the root
// layout's "%s · Lilith OS" template for the segments below it.
export const metadata: Metadata = { title: { absolute: "Cognitive Atlas Preview · Lilith OS" } };

/**
 * The off switch for the Cognitive Atlas preview. The Atlas is included in
 * every build by default; a build made with NEXT_PUBLIC_LILITH_ATLAS_PREVIEW=false
 * prerenders this route as a 404 and never sends the Atlas to the browser.
 */
export default function AtlasLayout({ children }: { children: React.ReactNode }) {
  if (!atlasPreviewEnabled()) notFound();
  // `contents`: no box of its own, so the Atlas lays out exactly as before. The
  // class pins the token values the Atlas was approved with (see globals.css).
  return <div className="atlas-token-scope contents">{children}</div>;
}
