"use client";

import { usePathname } from "next/navigation";
import { Bell, Search, LayoutGrid } from "lucide-react";
import { nav } from "./nav";
import { Clock } from "./clock";
import { user } from "@/lib/data";

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

      {/* center: search */}
      <button className="glass group relative hidden h-10 max-w-[460px] flex-1 items-center gap-3 overflow-hidden rounded-full px-4 text-left text-sm text-ink-faint transition-all hover:border-wine/25 hover:text-ink-muted md:flex">
        <span className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-pearl/30 to-transparent" />
        <Search className="h-4 w-4 text-wine-bright/70 transition-colors group-hover:text-wine-bright" />
        <span className="flex-1">Search, recall, or ask Lilith…</span>
        <kbd className="rounded-md border border-white/10 bg-black/15 px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
          Ctrl K
        </kbd>
      </button>

      {/* right: actions */}
      <div className="flex items-center gap-2">
        <IconBtn label="Apps">
          <LayoutGrid className="h-[18px] w-[18px]" />
        </IconBtn>
        <IconBtn label="Notifications">
          <Bell className="h-[18px] w-[18px]" />
          <span className="absolute right-2.5 top-2.5 h-1.5 w-1.5 rounded-full bg-rose" />
        </IconBtn>
        <button className="glass flex items-center gap-2 rounded-full py-1.5 pl-1.5 pr-3 transition-colors hover:border-wine/25">
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
        </button>
      </div>
    </header>
  );
}

function IconBtn({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <button
      aria-label={label}
      className="glass relative grid h-10 w-10 place-items-center rounded-full text-ink-muted transition-colors hover:border-wine/25 hover:text-ink"
    >
      {children}
    </button>
  );
}
