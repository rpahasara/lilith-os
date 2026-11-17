/**
 * Headless regression test for P1-7 (quiet route transition and row-to-detail
 * continuity): the route fade is opacity-only, short, held to the content (the
 * shell stays still) and leaves the Cognitive Atlas alone; the detail drawer
 * grows from the row that opened it only when motion is allowed, keeps its
 * dialog behaviour, and nothing new was added to the dependency list.
 *
 * Server-renders real components where it can; reads source where the thing
 * under test is a motion definition. Run by `npm run test:core`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { OWN_ENTRANCE } from "@/components/layout/route-transition";
import { DetailDrawer } from "@/components/ui/workspace";
import { DURATION } from "@/lib/motion";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const root = process.cwd();
const read = (...path: string[]) => readFileSync(join(root, ...path), "utf8");

export function runMotionP17SelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `p1-7: ${name}`, pass, detail: pass ? undefined : detail });

  /* route transition ---------------------------------------------------------- */
  const route = read("src", "components", "layout", "route-transition.tsx");
  const animated = route.slice(route.indexOf("<motion.div"), route.indexOf("</motion.div>"));
  check("the route transition animates opacity only",
    /initial=\{\{ opacity: 0 \}\}/.test(animated) && /animate=\{\{ opacity: 1 \}\}/.test(animated) &&
      !/\b(x|y|scale|filter|blur|rotate)\s*:/.test(animated), animated);
  check("it is short (the 'fast' step, about 200ms)", /DURATION\.fast/.test(animated) && DURATION.fast <= 0.22);
  check("it never waits for the old page (no exit animation, nothing blocks input)",
    !/AnimatePresence|exit=|mode=/.test(route));
  check("the Cognitive Atlas keeps its own entrance", OWN_ENTRANCE.includes("/memory/atlas"));
  const shell = read("src", "components", "layout", "app-shell.tsx");
  check("only the page content fades; the shell stays still",
    /<main[\s\S]*<RouteTransition>\{children\}<\/RouteTransition>[\s\S]*<\/main>/.test(shell) &&
      shell.indexOf("<SidebarRail") < shell.indexOf("<RouteTransition") && shell.indexOf("<StatusBar") > shell.indexOf("</main>"));

  /* row to detail ------------------------------------------------------------- */
  const drawer = read("src", "components", "ui", "workspace.tsx");
  check("the drawer grows from its row only when motion is allowed",
    /useReducedMotion\(\)/.test(drawer) && /const morph = !reduce && from !== null/.test(drawer));
  check("the growing plate is decoration (hidden from assistive tech, not clickable)",
    /aria-hidden data-drawer-plate/.test(drawer) && /pointer-events-none fixed z-50/.test(drawer));
  check("it only grows from a row on the page, never from the shell or a tiny control",
    /closest\("main"\)/.test(drawer) && /r\.width < 40/.test(drawer));
  check("without a row (or with reduced motion) the drawer fades, never slides",
    /reduce \? \{ initial: \{ opacity: 0 \}/.test(drawer));

  const closed = renderToStaticMarkup(createElement(DetailDrawer, { open: false, onClose: () => {}, title: "Invented", children: "body" }));
  check("a closed drawer renders nothing", closed === "");
  const opened = renderToStaticMarkup(createElement(DetailDrawer, { open: true, onClose: () => {}, title: "Invented detail", children: "body" }));
  check("an open drawer is still a labelled modal dialog",
    /role="dialog"/.test(opened) && /aria-modal="true"/.test(opened) && /aria-label="Invented detail"/.test(opened));

  /* no new dependencies --------------------------------------------------------- */
  const pkg = JSON.parse(read("package.json")) as { dependencies: Record<string, string> };
  const animationLibs = Object.keys(pkg.dependencies).filter((d) => /gsap|spring|motion|animat|lottie|transition/i.test(d));
  // the two that already existed: Framer Motion, and the avatar's VRM animation
  check("no new animation dependency", animationLibs.sort().join() === "@pixiv/three-vrm-animation,framer-motion", animationLibs.join());

  return out;
}
