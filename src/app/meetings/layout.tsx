import type { Metadata } from "next";

export const metadata: Metadata = { title: "Meetings" };

export default function MeetingsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
