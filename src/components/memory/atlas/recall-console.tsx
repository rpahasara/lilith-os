"use client";

import { type FormEvent, Fragment, useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight, Database, FlaskConical, Route, X } from "lucide-react";
import { REGION_BY_ID } from "@/lib/memory/atlas/regions";
import { RECALL_CUES } from "@/lib/memory/atlas/simulation";
import type { AtlasStore } from "@/lib/memory/atlas/store";
import type { RecallTrace } from "@/lib/memory/atlas/types";
import { cn } from "@/lib/utils";

export interface RecallState {
  trace: RecallTrace;
  /** index of the furthest memory reached so far. */
  step: number;
  done: boolean;
}

/**
 * Recall — a single quiet pill beneath the brain. Give it a cue and the
 * association chain lights up, both in the brain and as a strip above the pill.
 * Suggested cues appear only while the pill is hovered or focused.
 *
 * Matching is local keyword search over the synthetic set; no model runs.
 */
/** Wording per source. Real memory: following drawn links, never "recall". */
const COPY = {
  synthetic: {
    strip: "Simulated recall",
    help: "A simulation: it follows links between the synthetic memories. It does not search Lilith’s real memory.",
    miss: "No synthetic memory matches that cue — try one of these threads.",
    tag: "Simulated",
    form: "Simulated recall",
    input: "Simulated recall cue",
    placeholder: "Trace an association…",
    action: "Trace",
    unit: "memories",
  },
  real: {
    strip: "Association path",
    help: "Follows the links drawn between real records — links the source states and shared entities. It is not Lilith’s recall, and nothing is recorded.",
    miss: "No record’s title, tags or entities match that word.",
    tag: "Explore",
    form: "Explore associations",
    input: "Word to start from",
    placeholder: "Follow associations from…",
    action: "Follow",
    unit: "records",
  },
} as const;

export function RecallConsole({
  store,
  recall,
  onRecall,
  onClear,
  onSelect,
  className,
  origin = "synthetic",
  cues = RECALL_CUES,
}: {
  origin?: "synthetic" | "real";
  /** suggested starting words. */
  cues?: readonly string[];
  store: AtlasStore;
  recall: RecallState | null;
  /** returns false when the cue matched nothing. */
  onRecall: (cue: string) => boolean;
  onClear: () => void;
  onSelect: (id: string) => void;
  className?: string;
}) {
  const [cue, setCue] = useState("");
  const [miss, setMiss] = useState(false);
  const chain = useRef<HTMLOListElement>(null);
  const helpId = useId();
  const copy = COPY[origin];

  // keep the newest memory in the chain in view as the recall advances
  const step = recall?.step;
  useEffect(() => {
    chain.current?.scrollTo({ left: chain.current.scrollWidth, behavior: "smooth" });
  }, [step]);

  const run = (text: string) => {
    const value = text.trim();
    if (!value) return;
    setMiss(!onRecall(value));
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    run(cue);
  };

  return (
    <div className={cn("group/recall flex flex-col items-center gap-2", className)}>
      <AnimatePresence>
        {recall && (
          <motion.div
            key={recall.trace.id}
            initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="w-full rounded-[var(--radius-lg)] border border-white/[0.08] bg-black/40 px-4 py-2.5 backdrop-blur-xl"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="eyebrow truncate">
                <span className="text-wine-bright">{copy.strip}</span>
                <span className="mx-1.5 text-ink-faint">·</span>
                <span className="normal-case tracking-normal text-ink-muted">“{recall.trace.cue}”</span>
              </p>
              <div className="flex shrink-0 items-center gap-2.5">
                <span className="font-mono text-[10px] text-ink-faint">
                  {recall.done ? (
                    <RecallSummary store={store} trace={recall.trace} unit={copy.unit} />
                  ) : (
                    `${recall.step + 1} / ${recall.trace.nodes.length}`
                  )}
                </span>
                <button
                  type="button"
                  onClick={onClear}
                  aria-label={origin === "real" ? "Clear association path" : "Clear recall"}
                  className="grid h-6 w-6 place-items-center rounded-full bg-white/[0.06] text-ink-muted transition-colors hover:text-ink"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            </div>
            <ol ref={chain} className="scroll-area mt-2 flex items-center gap-1 overflow-x-auto pb-0.5">
              {recall.trace.nodes.slice(0, recall.step + 1).map((id, i) => {
                const node = store.node(id);
                if (!node) return null;
                const region = REGION_BY_ID[node.region];
                const via = i > 0 ? store.link(recall.trace.links[i - 1]) : null;
                return (
                  <Fragment key={id}>
                    {via && (
                      <motion.li
                        aria-hidden
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="flex shrink-0 flex-col items-center px-0.5"
                      >
                        <span className="font-mono text-[8px] uppercase tracking-[0.1em] text-ink-faint">
                          {via.basis === "explicit" ? "linked" : via.kind.replace(/^(shares|same domain) · /, "")}
                        </span>
                        <ChevronRight className="h-3 w-3 text-ink-faint" />
                      </motion.li>
                    )}
                    <motion.li
                      initial={{ opacity: 0, scale: 0.9, filter: "blur(4px)" }}
                      animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                      className="shrink-0"
                    >
                      <button
                        type="button"
                        onClick={() => onSelect(id)}
                        title={node.title}
                        className="flex max-w-[190px] items-center gap-2 rounded-full border bg-white/[0.03] py-1 pl-2 pr-3 text-left transition-colors hover:bg-white/[0.07]"
                        style={{ borderColor: `${region.color}55` }}
                      >
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{ background: region.color, boxShadow: `0 0 8px ${region.color}` }}
                        />
                        <span className="truncate text-[11px] text-ink">{node.title}</span>
                      </button>
                    </motion.li>
                  </Fragment>
                );
              })}
            </ol>
          </motion.div>
        )}
      </AnimatePresence>

      {/* revealed on hover / focus: what this is, and threads to try */}
      <div
        className={cn(
          "flex flex-col items-center gap-1.5 transition-opacity duration-300",
          miss
            ? "opacity-100"
            : "pointer-events-none opacity-0 group-focus-within/recall:pointer-events-auto group-focus-within/recall:opacity-100 group-hover/recall:pointer-events-auto group-hover/recall:opacity-100",
        )}
      >
        <p
          id={helpId}
          className={cn(
            "rounded-full bg-[rgba(10,7,12,0.6)] px-3 py-1 text-center text-[10px] leading-snug backdrop-blur-md",
            miss ? "text-amber" : "text-ink-muted",
          )}
        >
          {miss ? copy.miss : copy.help}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-1.5">
          {cues.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => {
                setCue(preset);
                run(preset);
              }}
              style={{ borderRadius: 9999 }}
              className="border border-white/[0.1] bg-[rgba(10,7,12,0.6)] px-2.5 py-1 text-[11px] text-ink-muted backdrop-blur-md transition-colors hover:border-white/25 hover:text-ink [@media(pointer:coarse)]:px-3.5 [@media(pointer:coarse)]:py-2"
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      {/* Deliberately unlike the OS search bar above: an amber "Simulated" tag,
          a trace icon and a "Trace" action — this replays associations in the
          synthetic atlas, it is not a query against real memory. */}
      <form
        onSubmit={submit}
        role="search"
        aria-label={copy.form}
        className="relative flex h-11 w-full max-w-[400px] items-center gap-2 overflow-hidden rounded-full border border-white/[0.1] bg-[rgba(12,8,13,0.5)] pl-1.5 pr-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.07),0_18px_40px_-24px_rgba(0,0,0,0.95)] backdrop-blur-xl transition-[max-width,border-color,background-color] duration-500 ease-out focus-within:max-w-[560px] focus-within:border-wine-bright/60 focus-within:bg-[rgba(12,8,13,0.7)] focus-within:shadow-[0_0_0_3px_rgba(225,132,157,0.14)]"
      >
        {origin === "real" ? (
          <span className="flex shrink-0 items-center gap-1 rounded-full border border-cyan/25 bg-cyan/10 py-1 pl-2 pr-2.5 font-mono text-[9px] uppercase tracking-[0.12em] text-cyan-bright">
            <Database className="h-2.5 w-2.5" />
            {copy.tag}
          </span>
        ) : (
          <span className="flex shrink-0 items-center gap-1 rounded-full border border-amber/25 bg-amber/10 py-1 pl-2 pr-2.5 font-mono text-[9px] uppercase tracking-[0.12em] text-amber">
            <FlaskConical className="h-2.5 w-2.5" />
            {copy.tag}
          </span>
        )}
        <input
          value={cue}
          onChange={(e) => {
            setCue(e.target.value);
            setMiss(false);
          }}
          aria-label={copy.input}
          aria-describedby={helpId}
          placeholder={copy.placeholder}
          enterKeyHint="go"
          // focus is shown by the pill itself (border + width), not a box inside it
          style={{ outline: "none" }}
          className="min-w-0 flex-1 bg-transparent text-[13px] text-ink placeholder:text-ink-faint"
        />
        <button
          type="submit"
          disabled={!cue.trim()}
          style={{ borderRadius: 9999 }}
          className="flex items-center gap-1.5 border border-wine/30 bg-gradient-to-r from-wine-deep/70 to-wine/50 px-3 py-1.5 text-[11px] font-medium text-ink transition-[border-color,box-shadow,opacity] hover:border-wine-bright/50 hover:shadow-[0_10px_30px_-14px_rgba(201,84,115,0.9)] disabled:opacity-0"
        >
          <Route className="h-3 w-3" />
          {copy.action}
        </button>
      </form>
    </div>
  );
}

function RecallSummary({ store, trace, unit }: { store: AtlasStore; trace: RecallTrace; unit: string }) {
  const domains = new Set(trace.nodes.map((id) => store.node(id)?.region));
  return (
    <>
      {trace.nodes.length} {unit} · {domains.size} domains
    </>
  );
}
