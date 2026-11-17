/**
 * Headless regression test for the shell's safety net and accessibility
 * basics: error boundaries exist and render, reduced motion reaches Framer
 * Motion, keyboard users can skip the chrome, the current route is announced,
 * every route has its own title, and the glass utilities ship the backdrop
 * filter they declare (and only where it is meant to be).
 *
 * Server-renders real components where it can; reads source where the thing
 * under test is a file convention or a stylesheet rule. Run by `npm run test:core`.
 */
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import WorkspaceError from "@/app/error";
import NotFound from "@/app/not-found";
import { DetailDrawer } from "@/components/ui/workspace";
import { ConnectionStatus } from "@/components/ui/connection-status";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const root = process.cwd();
const src = (...path: string[]) => readFileSync(join(root, "src", ...path), "utf8");

/** The body of one `@utility name { … }` block in the stylesheet. */
function utility(css: string, name: string): string {
  const start = css.indexOf(`@utility ${name} {`);
  if (start < 0) return "";
  return css.slice(start, css.indexOf("\n}", start));
}

export function runShellSelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `shell: ${name}`, pass, detail: pass ? undefined : detail });

  /* error boundaries ------------------------------------------------------- */
  for (const file of ["error.tsx", "not-found.tsx", "global-error.tsx"]) {
    check(`app/${file} exists`, existsSync(join(root, "src", "app", file)));
  }
  const errorHtml = renderToStaticMarkup(
    createElement(WorkspaceError, { error: Object.assign(new Error("boom"), { digest: "abc123" }), retry: () => {} }),
  );
  check("the workspace error state is an alert with a retry and a way home",
    /role="alert"/.test(errorHtml) && /Try again/.test(errorHtml) && /href="\/"/.test(errorHtml), errorHtml.slice(0, 200));
  check("the workspace error state never prints the error message", !/boom/.test(errorHtml));
  check("the workspace error state shows the reference digest", /abc123/.test(errorHtml));
  const notFoundHtml = renderToStaticMarkup(createElement(NotFound));
  check("not-found renders a heading and a way home", /<h1/.test(notFoundHtml) && /href="\/"/.test(notFoundHtml));
  const globalError = src("app", "global-error.tsx");
  check("global-error carries its own document", /<html/.test(globalError) && /<body/.test(globalError) && /retry\(\)/.test(globalError));

  /* shell ------------------------------------------------------------------ */
  const shell = src("components", "layout", "app-shell.tsx");
  check("the shell offers a skip link to the main region",
    /href="#main"/.test(shell) && /id="main"/.test(shell) && /Skip to content/.test(shell));
  check("the shell applies the reduced-motion setting to Framer Motion",
    /<MotionPreferences>/.test(shell) &&
      /reducedMotion="user"/.test(src("components", "layout", "motion-preferences.tsx")));
  check("the sidebar announces the current route",
    /aria-current=\{active \? "page" : undefined\}/.test(src("components", "layout", "sidebar-rail.tsx")));
  check("the command input has an accessible name",
    /aria-label="Ask Lilith, or give a command"/.test(src("components", "presence", "command-input.tsx")));

  /* titles ----------------------------------------------------------------- */
  check("the root layout defines a title template",
    /template: "%s · Lilith OS"/.test(src("app", "layout.tsx")));
  // /world is now a redirect to Memory → Beliefs, which carries the World Model's title.
  const titles = ["career", "memory", "automations", "meetings", "system", "memory/beliefs"].map((route) => {
    const file = join(root, "src", "app", ...route.split("/"), "layout.tsx");
    const m = existsSync(file) ? /title: (?:\{ absolute: )?"([^"]+)"/.exec(readFileSync(file, "utf8")) : null;
    return m?.[1] ?? "";
  });
  check("every workspace route has its own, distinct title",
    titles.every(Boolean) && new Set(titles).size === titles.length, titles.join(" | "));

  /* dialogs and disclosures -------------------------------------------------- */
  const drawer = renderToStaticMarkup(
    createElement(DetailDrawer, { open: true, onClose: () => {}, title: "A memory", children: "body" }),
  );
  check("the detail drawer is a labelled modal dialog",
    /role="dialog"/.test(drawer) && /aria-modal="true"/.test(drawer) && /aria-label="A memory"/.test(drawer));
  check("the detail drawer names where focus lands when it opens", /data-autofocus/.test(drawer));
  check("the detail drawer traps Tab and restores focus",
    /event\.key !== "Tab"/.test(src("components", "ui", "workspace.tsx")) &&
      /opener\?\.focus/.test(src("components", "ui", "workspace.tsx")));
  const chip = renderToStaticMarkup(
    createElement(ConnectionStatus, {
      isDemo: false,
      diagnostics: { mode: "live", transport: "proxy", endpoints: [{ path: "/x", ok: true, status: 200 }] },
    }),
  );
  check("the connection chip is a real disclosure",
    /type="button"/.test(chip) && /aria-expanded="false"/.test(chip) && /aria-controls="/.test(chip), chip.slice(0, 200));

  /* glass ------------------------------------------------------------------- */
  const css = src("app", "globals.css");
  const strong = utility(css, "glass-strong");
  check("glass-strong ships the backdrop filter in both forms",
    /-webkit-backdrop-filter: var\(--glass-backdrop\);/.test(strong) &&
      /\n\s*backdrop-filter: var\(--glass-backdrop\);/.test(strong) &&
      /--glass-backdrop: blur\(/.test(strong));
  check("glass-strong does not use a literal value the build would collapse",
    !/backdrop-filter: blur\(/.test(strong));
  for (const tier of ["glass", "glass-panel"]) {
    check(`${tier} declares no backdrop filter`, !/backdrop-filter:/.test(utility(css, tier)));
  }

  return out;
}
