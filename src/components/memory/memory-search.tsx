"use client";

import { type ComponentType, useEffect, useRef, useState } from "react";
import { Search, X, Sparkles, MessagesSquare, BookMarked } from "lucide-react";
import type { SearchScope } from "@/lib/memory/types";
import { cn } from "@/lib/utils";

const PLACEHOLDERS = [
  "What does Lilith know about LILITH OS?",
  "What have I said about Singapore?",
  "What do you remember about least privilege?",
  "Ask Lilith what she knows…",
];

const SUGGESTIONS = ["LILITH OS", "Singapore", "Anthropic", "least privilege", "offer"];

export function MemorySearch({
  query,
  onQuery,
  scope,
  onScope,
  resultCount,
}: {
  query: string;
  onQuery: (q: string) => void;
  scope: SearchScope;
  onScope: (s: SearchScope) => void;
  resultCount: number;
}) {
  const [ph, setPh] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // gently cycle the placeholder while empty, to hint at what's possible
  useEffect(() => {
    if (query) return;
    const t = setInterval(() => setPh((p) => (p + 1) % PLACEHOLDERS.length), 3800);
    return () => clearInterval(t);
  }, [query]);

  return (
    <div className="glass-strong relative overflow-hidden rounded-[var(--radius-lg)] p-4">
      {/* faint aurora wash to make search feel like the cognitive entry point */}
      <span className="pointer-events-none absolute -right-10 -top-16 h-40 w-40 rounded-full bg-violet-bright/10 blur-3xl" />
      <span className="pointer-events-none absolute -left-10 -bottom-16 h-40 w-40 rounded-full bg-cyan-bright/10 blur-3xl" />

      <div className="relative flex items-center gap-3 rounded-[var(--radius-md)] border border-white/[0.08] bg-white/[0.03] px-4 py-3 focus-within:border-violet-bright/40">
        <Search className="h-4 w-4 shrink-0 text-ink-faint" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          placeholder={PLACEHOLDERS[ph]}
          className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
          aria-label="Search Lilith's memory"
        />
        {query && (
          <button
            onClick={() => {
              onQuery("");
              inputRef.current?.focus();
            }}
            className="grid h-5 w-5 place-items-center rounded-full bg-white/[0.06] text-ink-faint hover:text-ink"
            aria-label="Clear search"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>

      <div className="relative mt-3 flex flex-wrap items-center justify-between gap-3">
        {/* scope toggle */}
        <div className="flex items-center gap-1 rounded-full border border-white/[0.06] bg-white/[0.02] p-1">
          <ScopeButton
            active={scope === "memory"}
            onClick={() => onScope("memory")}
            icon={BookMarked}
            label="Curated memory"
          />
          <ScopeButton
            active={scope === "conversation"}
            onClick={() => onScope("conversation")}
            icon={MessagesSquare}
            label="Conversation"
            soon
          />
        </div>

        {/* suggestions / status */}
        <div className="flex flex-wrap items-center gap-1.5">
          {query ? (
            <span className="font-mono text-[10px] text-ink-faint">
              {resultCount} {resultCount === 1 ? "match" : "matches"}
            </span>
          ) : (
            SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => onQuery(s)}
                className="rounded-full bg-white/[0.04] px-2.5 py-1 text-[11px] text-ink-muted transition-colors hover:bg-white/[0.08] hover:text-ink"
              >
                {s}
              </button>
            ))
          )}
        </div>
      </div>

      <p className="relative mt-3 flex items-center gap-1.5 text-[10px] text-ink-faint">
        <Sparkles className="h-3 w-3 text-violet-bright/70" />
        Keyword recall today · semantic search and conversation recall arrive with the memory backend.
      </p>
    </div>
  );
}

function ScopeButton({
  active,
  onClick,
  icon: Icon,
  label,
  soon,
}: {
  active: boolean;
  onClick: () => void;
  icon: ComponentType<{ className?: string }>;
  label: string;
  soon?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={soon}
      title={soon ? "Conversation recall arrives with the memory backend" : undefined}
      className={cn(
        "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors",
        active ? "bg-white/10 text-ink" : "text-ink-faint",
        soon ? "cursor-not-allowed opacity-50" : "hover:text-ink-muted",
      )}
    >
      <Icon className="h-3 w-3" />
      {label}
      {soon && <span className="font-mono text-[9px] uppercase tracking-wider">soon</span>}
    </button>
  );
}
