/**
 * Headless regression test for P1-8 (adaptive mobile navigation): below md the
 * 88px rail is hidden and the fox in the top bar opens a navigation sheet built
 * from the same `nav` list and the same "you are here" rule; from md up the
 * rail and the top bar are what they were. The sheet is a proper modal (dialog,
 * focus trap, Escape, inert page, no background scroll, focus back to the fox),
 * closes on any navigation, never coexists with Lilith's panel, follows the
 * shared motion vocabulary, and adds no dependency.
 *
 * Server-renders the real top bar and rail; reads source for behaviour that
 * only exists in a browser. Run by `npm run test:core`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ShellProviders } from "@/components/layout/app-shell";
import { TopBar } from "@/components/layout/top-bar";
import { SidebarRail } from "@/components/layout/sidebar-rail";
import { isNavActive, nav } from "@/components/layout/nav";
import { MOBILE_NAV_ID, MOBILE_NAV_QUERY } from "@/components/layout/mobile-nav";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const root = process.cwd();
const read = (...path: string[]) => readFileSync(join(root, ...path), "utf8");

export function runMobileNavP18SelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `p1-8: ${name}`, pass, detail: pass ? undefined : detail });

  /* one source of truth -------------------------------------------------------- */
  check("the active rule: Command only on /, others by prefix",
    isNavActive("/", "/") && !isNavActive("/career", "/") && isNavActive("/memory/atlas", "/memory") &&
      !isNavActive("/meetings", "/memory") && isNavActive("/career", "/career"));
  const sheetSrc = read("src", "components", "layout", "mobile-nav.tsx");
  const railSrc = read("src", "components", "layout", "sidebar-rail.tsx");
  check("rail and sheet both use nav and isNavActive (no second list, no second rule)",
    /import \{ isNavActive, nav \} from "\.\/nav"/.test(sheetSrc) && /import \{ isNavActive, nav \} from "\.\/nav"/.test(railSrc) &&
      /nav\.map\(/.test(sheetSrc) && !/href: "\/career"/.test(sheetSrc));
  check("no navigation provider or route state of its own", !/createContext|useRouter|router\.push|history\.pushState/.test(sheetSrc));
  check("the sheet's active mark does not share the rail's layout animation", !/layoutId/.test(sheetSrc));

  /* desktop preserved ------------------------------------------------------------ */
  const rail = renderToStaticMarkup(createElement(SidebarRail));
  const aside = /<aside class="([^"]*)"/.exec(rail)?.[1] ?? "";
  check("the rail is hidden below md only, and otherwise unchanged",
    aside === "relative z-20 flex h-full max-md:hidden w-[88px] shrink-0 flex-col items-center justify-between bg-[linear-gradient(90deg,rgba(8,5,9,0.72),rgba(8,5,9,0.3)_76%,transparent)] py-5 backdrop-blur-[2px]", aside);
  check("the rail keeps its mark, its six destinations and its sliding active pill",
    /aria-label="Lilith command center"/.test(rail) && nav.every((n) => rail.includes(`href="${n.href}"`)) && /layoutId="nav-active"/.test(railSrc));

  const top = renderToStaticMarkup(createElement(ShellProviders, null, createElement(TopBar)));
  const header = /<header class="([^"]*)"/.exec(top)?.[1] ?? "";
  check("from md up the top bar keeps its 72px height, gap and gutters",
    /md:h-\[72px\]/.test(header) && /md:gap-5/.test(header) && /sm:px-7/.test(header) && /lg:px-8/.test(header), header);
  check("below md it is compact (64px, the page's 16px gutter)", /(^|\s)h-16(\s|$)/.test(header) && /(^|\s)px-4(\s|$)/.test(header), header);

  /* the fox ------------------------------------------------------------------------ */
  const fox = /<button[^>]*data-mobile-nav-trigger[^>]*>/.exec(top)?.[0] ?? "";
  check("the fox is a real button that names what it does",
    /type="button"/.test(fox) && /aria-label="Open navigation"/.test(fox) && /aria-haspopup="dialog"/.test(fox) &&
      /aria-expanded="false"/.test(fox) && new RegExp(`aria-controls="${MOBILE_NAV_ID}"`).test(fox), fox);
  check("the fox exists below md only", /md:hidden/.test(fox), fox);
  check("it is a comfortable touch target (40px tile)", /h-10 w-10/.test(fox), fox);
  check("the fox mark is the existing brand mark", /Lilith fox spirit mark/.test(top));
  check("Lilith stays reachable from the compact header", /aria-label="Ask Lilith"/.test(top) && /md:hidden/.test(top));
  check("nothing of the sheet is rendered until it opens (no SSR markup)", !top.includes(`id="${MOBILE_NAV_ID}"`));

  /* the sheet ----------------------------------------------------------------------- */
  check("it is a labelled modal dialog", /role="dialog"/.test(sheetSrc) && /aria-modal="true"/.test(sheetSrc) && /aria-label="Navigation"/.test(sheetSrc));
  check("it renders above the page (portal to body)", /createPortal\(/.test(sheetSrc) && /document\.body/.test(sheetSrc));
  check("Escape closes it", /event\.key === "Escape"/.test(sheetSrc));
  check("Tab stays inside it", /event\.key !== "Tab"/.test(sheetSrc) && /last\.focus\(\)/.test(sheetSrc) && /first\.focus\(\)/.test(sheetSrc));
  check("the page behind is inert and does not scroll", /shell\.inert = true/.test(sheetSrc) && /main\.style\.overflow = "hidden"/.test(sheetSrc));
  check("closing restores the page and returns focus to the fox", /shell\.inert = false/.test(sheetSrc) && /trigger\.current\.focus\(\)/.test(sheetSrc));
  check("the backdrop and a close control both close it", /data-mobile-nav-backdrop/.test(sheetSrc) && /onClick=\{close\}/.test(sheetSrc) && /<X /.test(sheetSrc));
  check("any path change closes it (links, Back, Forward)", /pathname !== shownPath/.test(sheetSrc) && /onClick=\{close\}/.test(sheetSrc));
  check("it never stays open beside Lilith's panel", /if \(commandOpen\) setOpen\(false\)/.test(sheetSrc));
  check("growing into the rail's range closes it", MOBILE_NAV_QUERY === "(max-width: 47.99rem)" && /matchMedia\(MOBILE_NAV_QUERY\)/.test(sheetSrc));
  check("the current workspace is marked for assistive tech and visually",
    /aria-current=\{active \? "page" : undefined\}/.test(sheetSrc) && /ring-wine\/20/.test(sheetSrc) && /bg-wine-bright/.test(sheetSrc));
  check("touch targets are at least 48px tall", /min-h-12/.test(sheetSrc));
  check("safe-area insets are respected", /env\(safe-area-inset-left\)/.test(sheetSrc) && /env\(safe-area-inset-top\)/.test(sheetSrc) && /env\(safe-area-inset-bottom\)/.test(sheetSrc));
  check("motion comes from the shared vocabulary (reduced motion handled by MotionConfig)",
    /from "@\/lib\/motion"/.test(sheetSrc) && /transition=\{spring\}/.test(sheetSrc) && !/useReducedMotion/.test(sheetSrc));
  check("no heavy backdrop blur", !/backdrop-blur/.test(sheetSrc));
  const shell = read("src", "components", "layout", "app-shell.tsx");
  check("the providers are untouched: the sheet lives inside the shell, not around it",
    /data-shell-root=""/.test(shell) && /<ShellProviders>/.test(shell) && !/MobileNav/.test(shell));

  /* the recovered width is usable: no workspace grid can outgrow the page ---------- */
  const grids = [
    ["src", "app", "career", "page.tsx"], ["src", "app", "automations", "page.tsx"], ["src", "app", "meetings", "page.tsx"],
    ["src", "components", "system", "system-workspace.tsx"], ["src", "components", "memory", "memory-explorer.tsx"],
    ["src", "components", "career", "career-skeleton.tsx"], ["src", "components", "automations", "automations-skeleton.tsx"],
    ["src", "components", "meetings", "meetings-skeleton.tsx"], ["src", "components", "memory", "memory-skeleton.tsx"],
  ];
  const loose = grids.filter((p) => /className="grid gap-4 xl:grid-cols-/.test(read(...p)) || !/className="grid grid-cols-1 gap-4 xl:grid-cols-/.test(read(...p)));
  check("every workspace grid is one minmax(0,1fr) column below xl", loose.length === 0, loose.map((p) => p.at(-1)).join());

  const systems = read("src", "components", "automations", "systems-grid.tsx");
  check("Automations filters wrap on phones instead of hiding behind a sideways scroll",
    /layoutId="systems-filter" className="max-md:flex-wrap max-md:rounded-2xl"/.test(systems));

  /* pipeline affordance + dependencies ---------------------------------------------- */
  const pipe = read("src", "components", "career", "pipeline-overview.tsx");
  check("the pipeline strip shows which edge has more stages, and nothing when it fits",
    /function useScrollEdges/.test(pipe) && /edges\.start \|\| edges\.end/.test(pipe) && /: undefined;/.test(pipe));
  const imports = [...sheetSrc.matchAll(/from "([^"]+)"/g)].map((m) => m[1]).filter((m) => !m.startsWith("@/") && !m.startsWith("."));
  check("the sheet uses only libraries already in the app",
    imports.every((m) => ["react", "react-dom", "next/link", "next/navigation", "framer-motion", "lucide-react"].includes(m)), imports.join());

  return out;
}
