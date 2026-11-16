"use client";

import { usePathname } from "next/navigation";
import { nav } from "./nav";
import { Clock } from "./clock";
import { user } from "@/lib/data";
import { GlobalCommandLauncher } from "@/components/command/global-command";

function titleFor(pathname: string) {
  if (pathname === "/") return "Command Center";
  const item = nav.find((n) => n.href !== "/" && pathname.startsWith(n.href));
  return item?.label ?? "Lilith OS";
}

export function TopBar() {
  const pathname = usePathname();

  return (
    <header className="flex h-[72px] shrink-0 items-center justify-between gap-5 px-5 sm:px-7 lg:px-8">
      {/* left: context */}
      <div className="flex flex-col">
        <span className="text-lead font-semibold tracking-[-0.02em] text-ink">
          {titleFor(pathname)}
        </span>
        <span className="font-mono text-micro text-ink-faint">
          <Clock withDate />
        </span>
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
