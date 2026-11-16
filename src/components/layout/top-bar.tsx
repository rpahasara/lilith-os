"use client";

import { usePathname } from "next/navigation";
import { Search } from "lucide-react";
import { nav } from "./nav";
import { Clock } from "./clock";
import { user } from "@/lib/data";
import { unavailable } from "@/components/ui/unavailable";

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
        <span className="text-[15px] font-semibold tracking-[-0.02em] text-ink">
          {titleFor(pathname)}
        </span>
        <span className="font-mono text-[11px] text-ink-faint">
          <Clock withDate />
        </span>
      </div>

      {/* center: search. Not connected yet, so it is a disabled control: no
          shortcut hint, no hover affordance, and the reason is exposed as the
          accessible description. */}
      <button
        type="button"
        aria-label="Search"
        {...unavailable("Search")}
        className="glass relative hidden h-10 max-w-[460px] flex-1 cursor-not-allowed items-center gap-3 overflow-hidden rounded-full px-4 text-left text-sm text-ink-faint opacity-60 md:flex"
      >
        <span className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-pearl/30 to-transparent" />
        <Search className="h-4 w-4 text-wine-bright/70" />
        <span className="flex-1">Search, recall, or ask Lilith…</span>
      </button>

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
            <span className="block font-mono text-[10px] text-ink-faint">
              {user.plan}
            </span>
          </span>
        </div>
      </div>
    </header>
  );
}
