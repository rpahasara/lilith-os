import { SidebarRail } from "./sidebar-rail";
import { TopBar } from "./top-bar";
import { StatusBar } from "./status-bar";
import { PresenceProvider } from "@/components/presence/presence-engine";
import { ConversationProvider } from "@/components/conversation/conversation-provider";
import { CommandProvider } from "@/components/command";
import { MotionPreferences } from "./motion-preferences";
import { ShellHealthProvider } from "./shell-health-provider";
import { GlobalCommandPanel, GlobalCommandProvider } from "@/components/command/global-command";

/**
 * Everything the shell shares with the pages, in dependency order. Presence,
 * the one conversation and the one command store sit above the routed pages,
 * so they survive navigation; the backend probe and the global command surface
 * read from them. Exported so the headless tests render the real stack.
 */
export function ShellProviders({ children }: { children: React.ReactNode }) {
  return (
    <PresenceProvider defaultRenderer="avatar">
      <ConversationProvider>
        <CommandProvider>
          <ShellHealthProvider>
            <GlobalCommandProvider>{children}</GlobalCommandProvider>
          </ShellHealthProvider>
        </CommandProvider>
      </ConversationProvider>
    </PresenceProvider>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ShellProviders>
        {/* Environmental wallpaper is its own layer so the filter (blur/dim)
            affects ONLY the artwork — never Lilith, glass, text, or grain. */}
        <div className="lilith-bg" aria-hidden>
          <div className="lilith-bg-image" />
          <div className="lilith-bg-scrim" />
        </div>
        {/* First stop for keyboard users: jump past the rail and top bar. */}
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:border focus:border-wine-bright/60 focus:bg-base focus:px-4 focus:py-2 focus:text-sm focus:text-ink"
        >
          Skip to content
        </a>
        <MotionPreferences>
        <div className="relative flex h-dvh w-full overflow-hidden">
          <SidebarRail />
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar />
            <main
              id="main"
              tabIndex={-1}
              className="scroll-area min-h-0 flex-1 overflow-y-auto px-4 pb-2 outline-none sm:px-7 lg:px-8 xl:overflow-hidden"
            >
              {children}
            </main>
            <StatusBar />
          </div>
        </div>
        {/* Lilith over the current workspace (never on the Command Center). */}
        <GlobalCommandPanel />
        </MotionPreferences>
    </ShellProviders>
  );
}
