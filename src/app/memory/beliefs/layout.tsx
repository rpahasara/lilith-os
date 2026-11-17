import type { Metadata } from "next";

// Absolute: the parent Memory layout sets a plain title, which ends the root
// layout's "%s · Lilith OS" template for the segments below it.
export const metadata: Metadata = { title: { absolute: "Beliefs · Lilith OS" } };

export default function BeliefsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
