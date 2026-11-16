import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { atlasPreviewEnabled } from "@/lib/memory/atlas/preview";

// Absolute: the parent Memory layout sets a plain title, which ends the root
// layout's "%s · Lilith OS" template for the segments below it.
export const metadata: Metadata = { title: { absolute: "Cognitive Atlas · Lilith OS" } };

/**
 * The gate for the Cognitive Atlas prototype. A server component, so a build
 * without the preview flag prerenders this route as a 404 and never sends the
 * Atlas to the browser.
 */
export default function AtlasLayout({ children }: { children: React.ReactNode }) {
  if (!atlasPreviewEnabled()) notFound();
  return children;
}
