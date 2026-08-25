import { SidebarRail } from "./sidebar-rail";
import { TopBar } from "./top-bar";
import { StatusBar } from "./status-bar";
import { PresenceProvider } from "@/components/presence/presence-engine";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <PresenceProvider defaultMode="orb">
      <div className="lilith-bg" />
      <div className="flex h-dvh w-full overflow-hidden">
        <SidebarRail />
        <div className="flex min-w-0 flex-1 flex-col border-l border-white/[0.06]">
          <TopBar />
          <main className="scroll-area min-h-0 flex-1 overflow-y-auto px-4 pb-2 sm:px-6 lg:overflow-hidden">
            {children}
          </main>
          <StatusBar />
        </div>
      </div>
    </PresenceProvider>
  );
}
