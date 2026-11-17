/**
 * Headless regression test: the shell must not show controls that do nothing.
 *
 * Server-renders the real top bar, sidebar rail and command input (Node, no
 * browser; `next/navigation` and `next/link` are stubbed by the runner) and
 * checks the markup:
 *  - every enabled <button> is one we know has a real handler;
 *  - a not-yet-built feature that is still shown is a natively `disabled`
 *    button with an accessible name and a reason (title), so mouse and
 *    keyboard cannot activate it;
 *  - controls for features that do not exist at all (Apps, Notifications,
 *    Settings) are not rendered;
 *  - no promised-but-missing shortcut, no fake account button.
 * Run by `npm run test:core`.
 */
import { createElement, type ComponentType } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { TopBar } from "@/components/layout/top-bar";
import { ShellProviders } from "@/components/layout/app-shell";
import { SidebarRail } from "@/components/layout/sidebar-rail";
import { CommandInput } from "@/components/presence/command-input";
import { REAL_SUGGESTIONS } from "@/lib/command/suggestions";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

interface ButtonInfo {
  attrs: string;
  inner: string;
  name: string;
  disabled: boolean;
  title: string | null;
}

function attr(attrs: string, key: string): string | null {
  const m = new RegExp(`\\s${key}="([^"]*)"`).exec(attrs);
  return m ? m[1] : null;
}

function buttons(html: string): ButtonInfo[] {
  const out: ButtonInfo[] = [];
  const re = /<button([^>]*)>([\s\S]*?)<\/button>/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(html)) !== null) {
    const [, attrs, inner] = m;
    const text = inner.replace(/<[^>]+>/g, "").trim();
    out.push({
      attrs,
      inner,
      name: attr(attrs, "aria-label") ?? text,
      disabled: /\sdisabled=""/.test(attrs),
      title: attr(attrs, "title"),
    });
  }
  return out;
}

function render(c: ComponentType<any>, props: Record<string, unknown> = {}) { // eslint-disable-line @typescript-eslint/no-explicit-any
  return renderToStaticMarkup(createElement(c, props));
}

/** Controls with real handlers today, per surface. */
const FUNCTIONAL: Record<string, string[]> = {
  // The launcher opens Lilith over the page (one control per breakpoint); below
  // md the fox opens the navigation sheet (P1-8).
  "top bar": ["Ask Lilith", "Open navigation"],
  "sidebar rail": [],
  // Suggestion chips fill the input; Send submits (disabled while empty).
  // Only chips backed by a real intent are offered by default.
  "command input": [...REAL_SUGGESTIONS],
};

/** Features that are not built yet and must render as disabled controls. */
const UNAVAILABLE: Record<string, string[]> = {
  "top bar": [],
  "sidebar rail": [],
  "command input": ["Voice input"],
};

export function runControlsSelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `ui-controls: ${name}`, pass, detail: pass ? undefined : detail });

  const surfaces: Record<string, string> = {
    // The top bar reads the shell's shared state, so it renders inside the real stack.
    "top bar": renderToStaticMarkup(createElement(ShellProviders, null, createElement(TopBar))),
    "sidebar rail": render(SidebarRail),
    "command input": render(CommandInput),
  };

  for (const [surface, html] of Object.entries(surfaces)) {
    const all = buttons(html);

    const stray = all.filter((b) => !b.disabled && !FUNCTIONAL[surface].includes(b.name));
    check(`${surface}: every enabled button has a real action`,
      stray.length === 0, `unexpected enabled: ${stray.map((b) => b.name || "(unnamed)").join(", ")}`);

    const unnamed = all.filter((b) => !b.name);
    check(`${surface}: every button has an accessible name`, unnamed.length === 0,
      `${unnamed.length} unnamed button(s)`);

    for (const feature of UNAVAILABLE[surface]) {
      const b = all.find((x) => x.name === feature);
      check(`${surface}: ${feature} is natively disabled with a reason`,
        !!b && b.disabled && !!b.title && /\sdata-unavailable=""/.test(b.attrs) && /\stype="button"/.test(b.attrs),
        b ? b.attrs : "button not rendered");
      check(`${surface}: ${feature} has no hover affordance`,
        !!b && !/\shover:/.test(` ${attr(b.attrs, "class") ?? ""}`), b?.attrs);
    }
  }

  const top = surfaces["top bar"];
  check("top bar: no Apps or Notifications control until those exist",
    !buttons(top).some((b) => b.name === "Apps" || b.name === "Notifications"));
  check("top bar: no unread indicator", !/bg-rose/.test(top));
  check("top bar: no advertised Ctrl K shortcut", !/Ctrl K/.test(top));
  check("top bar: account is display-only, not a button",
    !buttons(top).some((b) => /Founder|Account/.test(b.inner + b.name)) && /Founder/.test(top));

  const rail = surfaces["sidebar rail"];
  check("sidebar rail: no Settings control until settings exist",
    !buttons(rail).some((b) => b.name === "Settings"));
  check("sidebar rail: account monogram is display-only",
    !buttons(rail).some((b) => b.name === "Account") && /role="img"/.test(rail));
  check("sidebar rail: primary navigation still renders as links",
    (rail.match(/<a\s/g) ?? []).length >= 7);

  const input = surfaces["command input"];
  const send = buttons(input).find((b) => b.name === "Send");
  check("command input: Send is present and disabled while empty", !!send && send.disabled);
  check("command input: real Ctrl Space shortcut hint is kept", /Ctrl Space/.test(input));

  return out;
}
