"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Settings } from "lucide-react";
import { nav } from "./nav";
import { cn } from "@/lib/utils";
import { user } from "@/lib/data";

export function SidebarRail() {
  const pathname = usePathname();

  return (
    <aside className="z-20 flex h-full w-[84px] flex-col items-center justify-between py-5">
      {/* mark */}
      <Link href="/" className="group flex flex-col items-center gap-2">
        <div className="relative grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-violet-bright/25 to-cyan-bright/15 hairline">
          <div className="h-5 w-5 rounded-full bg-gradient-to-br from-violet-bright to-cyan-bright shadow-[0_0_16px_2px_rgba(139,92,246,0.6)] transition-transform group-hover:scale-110" />
        </div>
        <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-faint">
          Lilith
        </span>
      </Link>

      {/* nav */}
      <nav className="flex flex-col items-center gap-1">
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
              className="group relative flex w-16 flex-col items-center gap-1 py-2"
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-2xl bg-white/[0.06] hairline"
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <span
                className={cn(
                  "relative grid h-10 w-10 place-items-center rounded-xl transition-colors",
                  active
                    ? "text-violet-bright"
                    : "text-ink-faint group-hover:text-ink-muted",
                )}
              >
                <Icon className="h-[18px] w-[18px]" strokeWidth={active ? 2.2 : 1.8} />
              </span>
              <span
                className={cn(
                  "relative text-[10px] transition-colors",
                  active ? "text-ink" : "text-ink-faint group-hover:text-ink-muted",
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
          className="relative h-9 w-9 overflow-hidden rounded-full bg-gradient-to-br from-violet-deep to-cyan-deep ring-1 ring-white/15"
        >
          <span className="grid h-full w-full place-items-center text-xs font-semibold text-white">
            {user.name.charAt(0)}
          </span>
        </button>
      </div>
    </aside>
  );
}
