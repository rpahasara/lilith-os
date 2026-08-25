import type { RunOutcome } from "@/lib/automations/types";

const COLOR: Record<RunOutcome, string> = {
  success: "var(--green)",
  failure: "var(--rose)",
  skip: "var(--ink-faint)",
};

/** Compact bar strip of recent run outcomes (oldest → newest). */
export function RunHistory({ history }: { history?: RunOutcome[] }) {
  if (!history || history.length === 0) {
    return <span className="text-[11px] text-ink-faint">No run history</span>;
  }
  return (
    <div className="flex items-end gap-[3px]" title="Recent runs">
      {history.slice(-12).map((h, i) => (
        <span
          key={i}
          className="w-[4px] rounded-full"
          style={{
            height: h === "failure" ? "14px" : "10px",
            background: COLOR[h],
            opacity: h === "success" ? 0.55 + (i / history.length) * 0.45 : 0.9,
          }}
        />
      ))}
    </div>
  );
}
