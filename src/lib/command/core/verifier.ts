/**
 * Verifier V1 — pure. Turns retrieved system data into a typed verdict with
 * evidence and unresolved items. Never "looks okay": it checks structure,
 * freshness, completeness, and provenance, and it distinguishes *task success*
 * (we correctly retrieved + summarised the data) from *system health* (which is
 * reported honestly as findings, even inside a succeeded task).
 */
import type { CommandEvidence } from "../types";
import { isUnitUnhealthy, type OsOverview, type SystemStatus } from "./capabilities";
import type { VerifierResult } from "./types";

/** How stale the backend clock may be before we downgrade to PARTIAL (ms). */
const FRESHNESS_LIMIT_MS = 20 * 60 * 1000;

export function verifySystemHealth(input: {
  status: SystemStatus | null;
  overview: OsOverview | null;
  statusExecutionId?: string;
  overviewExecutionId?: string;
  now?: number;
}): VerifierResult {
  const { status, overview } = input;
  const now = input.now ?? Date.now();

  // Structural validity — the backbone. Without a valid unit inventory the task
  // cannot honestly succeed.
  if (!status || !Array.isArray(status.units) || status.units.length === 0) {
    return {
      verdict: "FAIL",
      summary: "Could not retrieve a valid service inventory from the control backend.",
      evidence: [],
      unresolved: ["System status was unavailable or malformed."],
      recovery: "Retry when the control backend is reachable.",
    };
  }

  const units = status.units;
  const unhealthy = units.filter(isUnitUnhealthy);
  const healthyCount = units.length - unhealthy.length;

  const evidence: CommandEvidence[] = [
    { kind: "observed_state", label: "Units checked", value: String(units.length) },
    { kind: "observed_state", label: "Healthy", value: `${healthyCount} / ${units.length}` },
  ];
  if (status.timeUtc) {
    evidence.push({ kind: "observed_state", label: "Backend clock", value: status.timeUtc });
  }
  if (input.statusExecutionId) {
    evidence.push({ kind: "external_id", label: "system.get_status", value: input.statusExecutionId });
  }
  for (const u of unhealthy) {
    evidence.push({
      kind: "error_detail",
      label: u.unit,
      value: u.serviceActive === "failed" ? "service failed" : u.result || u.active,
    });
  }

  // Freshness check.
  let stale = false;
  if (status.timeUtc) {
    const t = Date.parse(status.timeUtc);
    if (Number.isFinite(t) && now - t > FRESHNESS_LIMIT_MS) stale = true;
  }

  // Cross-check: overview's automation health vs the detailed inventory. A
  // mismatch is exactly the "200 hides a failure" case — surfaced, not trusted.
  const unresolved: string[] = [];
  if (overview) {
    const overviewUnhealthy = overview.automations.unhealthy;
    const detailUnhealthy = unhealthy.filter((u) => u.type === "timer" || u.type === "service").length;
    if (overviewUnhealthy !== detailUnhealthy) {
      evidence.push({
        kind: "observed_state",
        label: "Overview vs. detail",
        value: `overview reports ${overviewUnhealthy} unhealthy, detail shows ${detailUnhealthy}`,
      });
    }
  }

  for (const u of unhealthy) {
    unresolved.push(`${u.unit} — ${u.serviceActive === "failed" ? "service failed" : u.result || u.active}`);
  }

  // Verdict:
  //  FAIL     already handled (no valid inventory).
  //  PARTIAL  data retrieved but incomplete context (no overview) or stale.
  //  PASS     complete, fresh, valid inventory (system health findings, healthy
  //           or not, are honest content — not task partiality).
  if (!overview || stale) {
    return {
      verdict: "PARTIAL",
      summary: !overview
        ? `Retrieved ${units.length} units (${healthyCount} healthy) but could not confirm the OS overview for cross-check.`
        : `Retrieved ${units.length} units but the backend data may be stale.`,
      evidence,
      unresolved: unresolved.length ? unresolved : ["Context incomplete."],
      recovery: "Retry to refresh the missing context.",
    };
  }

  const summary =
    unhealthy.length === 0
      ? `All ${units.length} services healthy.`
      : `${healthyCount} of ${units.length} services healthy — ${unhealthy.length} need attention.`;

  return {
    verdict: "PASS",
    summary,
    evidence,
    unresolved,
  };
}
