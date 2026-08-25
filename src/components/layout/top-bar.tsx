"use client";

import { usePathname } from "next/navigation";
import { Bell, Plus, Search, LayoutGrid } from "lucide-react";
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
    <header className="flex h-16 shrink-0 items-center justify-between gap-4 px-6">
      {/* left: context */}
      <div className="flex flex-col">
        <span className="text-[15px] font-semibold tracking-tight text-ink">
          {titleFor(pathname)}
        </span>
        <span className="font-mono text-[11px] text-ink-faint">
          <Clock withDate />
        </span>
      </div>

      {/* center: search */}
      <button className="group hidden max-w-md flex-1 items-center gap-3 rounded-full glass px-4 py-2 text-left text-sm text-ink-faint transition-colors hover:border-white/15 md:flex">
        <Search className="h-4 w-4" />
        <span className="flex-1">Search or ask Lilith anything…</span>
        <kbd className="rounded-md border border-white/10 px-1.5 py-0.5 font-mono text-[10px]">
          ⌘K
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
        <button className="flex items-center gap-2 rounded-full glass py-1.5 pl-1.5 pr-3 transition-colors hover:border-white/15">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-violet-deep to-cyan-deep text-xs font-semibold text-white">
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
      className="relative grid h-10 w-10 place-items-center rounded-full glass text-ink-muted transition-colors hover:border-white/15 hover:text-ink"
    >
      {children}
    </button>
  );
}
