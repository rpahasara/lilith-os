"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Settings } from "lucide-react";
import { nav } from "./nav";
import { cn } from "@/lib/utils";
import { user } from "@/lib/data";
import { FoxMark } from "@/components/ui/fox-mark";

export function SidebarRail() {
  const pathname = usePathname();

  return (
    <aside className="relative z-20 flex h-full w-[88px] shrink-0 flex-col items-center justify-between bg-[linear-gradient(90deg,rgba(8,5,9,0.72),rgba(8,5,9,0.3)_76%,transparent)] py-5 backdrop-blur-[2px]">
      <span className="shell-divider pointer-events-none absolute inset-y-5 right-0 w-px" />
      {/* mark */}
      <Link href="/" aria-label="Lilith command center" className="group flex flex-col items-center gap-2">
        <div className="glass relative grid h-12 w-12 place-items-center overflow-hidden rounded-2xl shadow-[0_12px_30px_-14px_rgba(201,84,115,0.8)] transition-transform duration-300 group-hover:-translate-y-0.5">
          <span className="absolute inset-0 bg-[radial-gradient(circle_at_50%_12%,rgba(255,255,255,0.12),transparent_48%)]" />
          <FoxMark className="relative h-8 w-8 drop-shadow-[0_0_10px_rgba(225,132,157,0.4)]" />
        </div>
        <span className="font-mono text-[9px] uppercase tracking-[0.24em] text-ink-muted">
          Lilith
        </span>
      </Link>

      {/* nav */}
      <nav aria-label="Primary workspaces" className="flex flex-col items-center gap-1.5">
        {nav.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className="group relative flex w-[68px] flex-col items-center gap-1 py-2.5"
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="glass absolute inset-0 rounded-2xl shadow-[0_12px_28px_-18px_rgba(201,84,115,0.9)] ring-1 ring-wine/20"
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <span
                className={cn(
                  "relative grid h-10 w-10 place-items-center rounded-xl transition-colors",
                  active
                    ? "text-wine-bright"
                    : "text-ink-faint group-hover:text-ink",
                )}
              >
                <Icon className="h-[18px] w-[18px]" strokeWidth={active ? 2.2 : 1.8} />
              </span>
              <span
                className={cn(
                  "relative text-[10px] transition-colors",
                  active ? "font-medium text-ink" : "text-ink-faint group-hover:text-ink-muted",
                )}
              >
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>

      {/* footer */}
      <div className="flex flex-col items-center gap-3">
        <button
          aria-label="Settings"
          className="grid h-10 w-10 place-items-center rounded-xl text-ink-faint transition-colors hover:bg-white/5 hover:text-ink"
        >
          <Settings className="h-[18px] w-[18px]" strokeWidth={1.8} />
        </button>
        <button
          aria-label="Account"
          className="relative h-9 w-9 overflow-hidden rounded-full bg-gradient-to-br from-wine-deep to-wine-bright ring-1 ring-white/15"
        >
          <span className="grid h-full w-full place-items-center text-xs font-semibold text-white">
            {user.name.charAt(0)}
          </span>
        </button>
      </div>
    </aside>
  );
}
