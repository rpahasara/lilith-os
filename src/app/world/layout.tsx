import type { Metadata } from "next";

export const metadata: Metadata = { title: "World Model" };

export default function WorldModelLayout({ children }: { children: React.ReactNode }) {
  return children;
}
