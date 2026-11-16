import type { Metadata } from "next";

export const metadata: Metadata = { title: "System" };

export default function SystemLayout({ children }: { children: React.ReactNode }) {
  return children;
}
