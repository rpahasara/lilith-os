/**
 * Headless regression test for the frontend logging policy (see
 * lib/diagnostics.ts): development diagnostics stay development-only,
 * production problem reports are sanitized, and no log call can carry
 * conversation text, voice requests, owner data or memory context.
 * Run by `npm run test:core`. The built bundle is checked separately by
 * `npm run scan:bundle` (after `npm run build`).
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { createConsoleCoreLogger } from "@/lib/command/core/logger";
import { describeError, reportProblem } from "./diagnostics";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return sourceFiles(p);
    return /\.(ts|tsx)$/.test(name) && !/self-test\.ts$/.test(name) ? [p] : [];
  });
}

/** Text of a call starting at `start` up to its balanced closing paren. */
function callText(src: string, start: number): string {
  let depth = 0;
  for (let i = src.indexOf("(", start); i < src.length; i++) {
    if (src[i] === "(") depth++;
    else if (src[i] === ")" && --depth === 0) return src.slice(start, i + 1);
  }
  return src.slice(start);
}

/** Identifiers that would mean a log carries owner/conversation/voice/memory data. */
const SENSITIVE = /\b(messages?|reply|replies|transcript|lastLilith|user\.(name|handle)|req\.text|\.text\b|memory|memories|sessionId|session|apiKey|token|credential|password)\b/i;

export function runDiagnosticsSelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `diagnostics: ${name}`, pass, detail: pass ? undefined : detail });

  /* ------------------------------------------------ sanitized problem reports */
  const big = Object.assign(new Error("context lost\n  while   rendering " + "x".repeat(400)), {
    name: "WebGLError",
    payload: { conversation: "private words", owner: "someone" },
  });
  const described = describeError(big);
  check("errors are reduced to one truncated 'Name: message' line",
    described.startsWith("WebGLError: context lost while rendering") && described.length <= 160 && !/\n/.test(described),
    described);
  check("non-Error throwables never echo their content",
    describeError("private words") === "non-Error thrown" && describeError({ owner: "x" }) === "non-Error (object)");

  const lines: string[] = [];
  reportProblem("presence", "renderer failed, falling back to static", big, (l) => lines.push(l));
  reportProblem("Hsin", "WebGL context lost — awaiting restoration", undefined, (l) => lines.push(l));
  check("problem reports are single strings with no payload, stack or attached data",
    lines.length === 2 && lines.every((l) => typeof l === "string" && !/private words|someone|\bat\s/.test(l)) &&
    lines[0].startsWith("[presence] renderer failed") && lines[1] === "[Hsin] WebGL context lost — awaiting restoration",
    JSON.stringify(lines));

  /* ------------------------------------------------ command-core logger */
  const captured: { level: string; args: unknown[] }[] = [];
  const sink = {
    info: (...args: unknown[]) => captured.push({ level: "info", args }),
    warn: (...args: unknown[]) => captured.push({ level: "warn", args }),
  };
  const prod = createConsoleCoreLogger(false, sink);
  prod.log("task.created", "t1", { intent: "career.followup", writes: true });
  prod.log("approval.requested", "t1", { capId: "draft.create" });
  prod.log("persist.degraded", "t1", { phase: "create", error: "backend said: secret detail" });
  check("production core logger is silent for lifecycle traces and field-less for problems",
    captured.length === 1 && captured[0].level === "warn" && captured[0].args.length === 1 &&
    captured[0].args[0] === "[core persist.degraded] task=t1", JSON.stringify(captured));
  captured.length = 0;
  createConsoleCoreLogger(true, sink).log("plan.created", "t2", { steps: 3 });
  check("development core logger keeps full traces",
    captured.length === 1 && captured[0].level === "info" && captured[0].args[0] === "[core plan.created] task=t2");

  /* ------------------------------------------------ source policy */
  const root = join(process.cwd(), "src");
  const files = sourceFiles(root);
  const ungated: string[] = [];
  const sensitive: string[] = [];
  const badFlags: string[] = [];
  for (const file of files) {
    const rel = relative(process.cwd(), file).split(sep).join("/");
    const src = readFileSync(file, "utf8");
    for (const m of src.matchAll(/\bconsole\.(log|info|debug|table|trace|warn|error)\s*\(/g)) {
      const at = m.index ?? 0;
      const lineStart = src.lastIndexOf("\n", at) + 1;
      const before = src.slice(lineStart, at);
      const isSink = rel === "src/lib/diagnostics.ts";
      if (!isSink && !/if \(DEV_DIAGNOSTICS\)\s*$/.test(before)) {
        ungated.push(`${rel}:${src.slice(0, at).split("\n").length}`);
      }
      if (SENSITIVE.test(callText(src, at))) sensitive.push(`${rel}:${src.slice(0, at).split("\n").length}`);
    }
    for (const m of src.matchAll(/\breportProblem\s*\(/g)) {
      const at = m.index ?? 0;
      if (rel !== "src/lib/diagnostics.ts" && SENSITIVE.test(callText(src, at))) {
        sensitive.push(`${rel}:${src.slice(0, at).split("\n").length}`);
      }
    }
    for (const m of src.matchAll(/const DEV_DIAGNOSTICS\s*=\s*([^;]+);/g)) {
      if (m[1].trim() !== 'process.env.NODE_ENV !== "production"') badFlags.push(`${rel}: ${m[1].trim()}`);
    }
  }
  check("every console call outside the sanitized sink is development-gated", ungated.length === 0, ungated.join(", "));
  check("no log call references conversation, voice, owner, memory or credential data",
    sensitive.length === 0, sensitive.join(", "));
  check("DEV_DIAGNOSTICS is always the build-time NODE_ENV check (cannot be forced on in production)",
    badFlags.length === 0, badFlags.join(", "));

  return out;
}
