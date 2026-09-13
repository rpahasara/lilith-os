import { SidebarRail } from "./sidebar-rail";
import { TopBar } from "./top-bar";
import { StatusBar } from "./status-bar";
import { PresenceProvider } from "@/components/presence/presence-engine";
import { ConversationProvider } from "@/components/conversation/conversation-provider";
import { CommandProvider } from "@/components/command";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <PresenceProvider defaultRenderer="avatar">
      {/* Conversation lives above the routed pages so the transcript + session
          survive navigation between workspaces. The Command System sits inside
          both so it can bridge plain chat to the backend and translate command
          lifecycle into semantic presence. */}
      <ConversationProvider>
        <CommandProvider>
        {/* Environmental wallpaper is its own layer so the filter (blur/dim)
            affects ONLY the artwork — never Lilith, glass, text, or grain. */}
        <div className="lilith-bg" aria-hidden>
          <div className="lilith-bg-image" />
          <div className="lilith-bg-scrim" />
        </div>
        <div className="relative flex h-dvh w-full overflow-hidden">
          <SidebarRail />
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar />
            <main className="scroll-area min-h-0 flex-1 overflow-y-auto px-4 pb-2 sm:px-7 lg:px-8 xl:overflow-hidden">
              {children}
            </main>
            <StatusBar />
          </div>
        </div>
        </CommandProvider>
      </ConversationProvider>
    </PresenceProvider>
  );
}
