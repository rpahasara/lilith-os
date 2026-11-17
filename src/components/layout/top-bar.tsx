"use client";

import { usePathname } from "next/navigation";
import { nav } from "./nav";
import { Clock } from "./clock";
import { user } from "@/lib/data";
import { GlobalCommandLauncher } from "@/components/command/global-command";
import { MobileNav } from "./mobile-nav";

function titleFor(pathname: string) {
  if (pathname === "/") return "Command Center";
  const item = nav.find((n) => n.href !== "/" && pathname.startsWith(n.href));
  return item?.label ?? "Lilith OS";
}

export function TopBar() {
  const pathname = usePathname();

  return (
    // Compact below md (64px, the page's own 16px gutter); from md up, as before.
    <header className="flex h-16 shrink-0 items-center justify-between gap-3 px-4 sm:px-7 md:h-[72px] md:gap-5 lg:px-8">
      {/* left: the fox menu (below md only), then context */}
      <div className="flex items-center gap-3 max-md:min-w-0">
        <MobileNav />
        <div className="flex flex-col max-md:min-w-0">
          <span className="text-lead font-semibold tracking-[-0.02em] text-ink max-md:truncate">
            {titleFor(pathname)}
          </span>
          <span className="font-mono text-micro text-ink-faint max-md:truncate">
            <Clock withDate />
          </span>
        </div>
      </div>

      {/* center: Lilith. Opens the conversation over the current workspace; on
          the Command Center it focuses the hero input. Ctrl+Space does the same. */}
      <GlobalCommandLauncher />

      {/* right: actions */}
      <div className="flex items-center gap-2">
        {/* Identity display only: there is no account menu or sign-in yet. */}
        <div className="glass flex items-center gap-2 rounded-full py-1.5 pl-1.5 pr-3">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-wine-deep to-wine-bright text-xs font-semibold text-white">
            {user.name.charAt(0)}
          </span>
          <span className="hidden text-left sm:block">
            <span className="block text-xs font-medium leading-none text-ink">
              {user.name}
            </span>
            <span className="block font-mono text-micro text-ink-faint">
              {user.plan}
            </span>
          </span>
        </div>
      </div>
    </header>
  );
}
