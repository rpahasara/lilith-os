/**
 * Headless regression test for the design-system foundations: one type scale
 * with an 11px floor, one rising radius scale, one motion vocabulary, no legacy
 * colour names, readable faint ink, and the Cognitive Atlas pinned to the token
 * values it was approved with.
 *
 * Reads source and the stylesheet; renders the shared feedback components.
 * Run by `npm run test:core`.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join, sep } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { InlineError, InlineNotice, LoadingRegion, NotYetTag, Skeleton } from "@/components/ui/feedback";
import { DURATION, EASE_OUT, riseIn, spring, springSnap } from "@/lib/motion";
import { TYPE_SCALE, cn } from "@/lib/utils";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const root = process.cwd();
const rel = (file: string) => file.slice(root.length + 1).split(sep).join("/");

function sources(): string[] {
  const out: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(entry.name) && !/self-test\.ts$/.test(entry.name)) out.push(full);
    }
  };
  walk(join(root, "src"));
  return out;
}

/** The Atlas keeps its own approved values; these files are not migrated. */
const isAtlas = (file: string) => /src\/(components|lib)\/memory\/atlas\//.test(file) || /memory-view-switch\.tsx$/.test(file);
/** Avatar calibration panels: developer tools with their own dense sizes. */
const isCalibration = (file: string) => /presence\/avatar-(presence|scene)\.tsx$/.test(file);
/** Render loops with their own timing, outside the UI motion vocabulary. */
const ownsMotion = (file: string) =>
  isAtlas(file) || /src\/lib\/(motion|presence|voice)\b/.test(file) || /presence\/(avatar-|orb-scene)/.test(file);

function luminance(hex: string): number {
  const c = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
function contrast(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

export function runFoundationsSelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `foundations: ${name}`, pass, detail: pass ? undefined : detail });

  const css = readFileSync(join(root, "src", "app", "globals.css"), "utf8");
  const rootBlock = css.slice(css.indexOf(":root {"), css.indexOf("\n}", css.indexOf(":root {")));
  const token = (name: string, from = rootBlock) => new RegExp(`--${name}:\\s*([^;]+);`).exec(from)?.[1].trim() ?? "";
  const files = sources().map((file) => ({ file: rel(file), text: readFileSync(file, "utf8") }));

  /* type ------------------------------------------------------------------------ */
  const sizes = TYPE_SCALE.map((name) => parseFloat(token(`text-${name}`, css)) * 16);
  check("the type scale is defined, rising, and starts at 11px",
    sizes.length === 5 && sizes[0] === 11 && sizes.every((s, i) => i === 0 || s > sizes[i - 1]), sizes.join(", "));
  const arbitrary = files.filter((f) => !isAtlas(f.file) && !isCalibration(f.file) && /\btext-\[[0-9.]+px\]/.test(f.text));
  check("no one-off pixel text sizes outside the Atlas and the calibration panels",
    arbitrary.length === 0, arbitrary.map((f) => f.file).join(", "));
  check("the class merger keeps a size and a colour together",
    cn("text-micro", "text-ink") === "text-micro text-ink" && cn("text-ink-faint", "text-lead") === "text-ink-faint text-lead");
  check("the class merger still resolves two sizes to the last one", cn("text-micro", "text-lead") === "text-lead");

  /* ink --------------------------------------------------------------------------- */
  const faint = contrast(token("ink-faint"), token("base"));
  check("faint ink reads at 5.5:1 or better on the base colour", faint >= 5.5, faint.toFixed(2));
  check("ink steps stay in order: faint below muted below ink",
    contrast(token("ink-faint"), token("base")) < contrast(token("ink-muted"), token("base")) &&
      contrast(token("ink-muted"), token("base")) < contrast(token("ink"), token("base")));

  /* colour names --------------------------------------------------------------------- */
  const violet = files.filter((f) => !isAtlas(f.file) && /\bviolet(?!-\d)/.test(f.text));
  check("the legacy violet names are gone from the code", violet.length === 0, violet.map((f) => f.file).join(", "));
  check("the legacy violet tokens are gone from the stylesheet", !/--(color-)?violet/.test(css));
  check("orchid carries all three steps", ["orchid", "orchid-bright", "orchid-deep"].every((n) => token(n) !== ""));

  /* radius ------------------------------------------------------------------------------ */
  const radii = ["sm", "md", "lg", "xl", "2xl"].map((n) => parseFloat(token(`radius-${n}`)));
  check("the radius scale rises from sm to 2xl", radii.every((r, i) => Number.isFinite(r) && (i === 0 || r > radii[i - 1])), radii.join(", "));

  /* motion -------------------------------------------------------------------------------- */
  check("four named durations, rising", [DURATION.instant, DURATION.fast, DURATION.base, DURATION.slow].every((d, i, a) => i === 0 || d > a[i - 1]));
  check("the CSS durations and curve match the shared motion file",
    token("duration-instant") === `${DURATION.instant * 1000}ms` && token("duration-fast") === `${DURATION.fast * 1000}ms` &&
      token("duration-base") === `${DURATION.base * 1000}ms` && token("duration-slow") === `${DURATION.slow * 1000}ms` &&
      token("ease-lilith") === `cubic-bezier(${EASE_OUT.join(", ")})`,
    [token("duration-fast"), token("ease-lilith")].join(" | "));
  check("transition utilities default to the house curve", /--default-transition-timing-function:\s*var\(--ease-lilith\)/.test(css));
  const stray = files.filter((f) => !ownsMotion(f.file) && (/stiffness:\s*\d/.test(f.text) || /ease:\s*\[/.test(f.text)));
  check("no hand-written springs or easing curves outside the motion file", stray.length === 0, stray.map((f) => f.file).join(", "));
  check("two springs: surfaces and selection",
    (spring as { stiffness?: number }).stiffness === 320 && (springSnap as { stiffness?: number }).stiffness === 400);
  check("panel entrances do not animate blur", !JSON.stringify(riseIn).includes("blur"));
  check("reduced motion stills CSS animations and transitions",
    /@media \(prefers-reduced-motion: reduce\)[\s\S]*animation-duration: 0\.001ms !important[\s\S]*transition-duration: 0\.001ms !important/.test(css));

  /* the Atlas keeps what it was approved with ---------------------------------------------- */
  const scope = css.slice(css.indexOf(".atlas-token-scope {"), css.indexOf("}", css.indexOf(".atlas-token-scope {")));
  check("the Atlas route pins its approved radii, faint ink and curve",
    token("radius-lg", scope) === "1.25rem" && token("radius-xl", scope) === "1.75rem" && token("radius-2xl", scope) === "1rem" &&
      token("ink-faint", scope) === "#817587" && token("ease-lilith", scope) === "cubic-bezier(0.4, 0, 0.2, 1)", scope);
  check("the Atlas route applies that scope without adding a box",
    /className="atlas-token-scope contents"/.test(readFileSync(join(root, "src", "app", "memory", "atlas", "layout.tsx"), "utf8")));

  /* feedback states ---------------------------------------------------------------------------- */
  const loading = renderToStaticMarkup(createElement(LoadingRegion, { label: "Career", children: createElement(Skeleton, { className: "h-4" }) }));
  check("loading is one polite status with a name", /role="status"/.test(loading) && /aria-busy="true"/.test(loading) && /Loading Career/.test(loading));
  check("skeleton blocks are hidden from assistive technology", /aria-hidden="true"/.test(loading));
  const error = renderToStaticMarkup(createElement(InlineError, { message: "It failed.", onAction: () => {} }));
  check("an error is an alert with its retry", /role="alert"/.test(error) && /It failed\./.test(error) && /Retry/.test(error));
  check("an error without a retry offers no button",
    !/<button/.test(renderToStaticMarkup(createElement(InlineError, { message: "It failed." }))));
  const notice = renderToStaticMarkup(createElement(InlineNotice, { message: "Stopped.", onAction: () => {}, actionLabel: "Ask again" }));
  check("a notice is a status, not an alert", /role="status"/.test(notice) && !/role="alert"/.test(notice) && /Ask again/.test(notice));
  check("the not-yet tag reads 'Not yet'", /Not yet/.test(renderToStaticMarkup(createElement(NotYetTag))));

  return out;
}
