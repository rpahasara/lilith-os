# Design system foundations

The shared rules the LILITH OS interface is built on. They came out of P1-5 in
`ui-ux-evolution-proposal.md`. The identity (wallpaper, wine and rose, cyan for
data, the avatar, the sidebar) is unchanged; this is the scale underneath it.

Everything here is held by `src/lib/ui/foundations-self-test.ts`, which runs in
`npm run test:core`.

## Type

One scale, defined in `src/app/globals.css` and mirrored in `TYPE_SCALE`
(`src/lib/utils.ts`). Nothing meant to be read is set below 11px.

| Class | Size | Use |
| --- | --- | --- |
| `text-micro` | 11 | labels, meta, badges, timestamps |
| `text-caption` (or `text-xs`) | 12 | secondary lines |
| `text-compact` | 13 | dense rows |
| `text-body` (or `text-sm`) | 14 | running text |
| `text-lead` | 15 | inputs, emphasised lines |
| `text-lg` … `text-3xl` | 18 … 30 | headings |

These five set the size only, so text keeps the line height of where it sits.
Do not write `text-[10px]`; the test rejects one-off pixel sizes.

The class merger (`cn`) is told that these names are sizes. Without that it
would read `text-micro` as a colour and drop it next to `text-ink`.

## Ink

`--ink`, `--ink-muted`, `--ink-faint`. Faint ink is for secondary text that is
still meant to be read: 5.7:1 on the base colour. Use it for meta, not for
decoration that happens to be text.

## Colour names

`wine` is the identity, `orchid` the secondary, `cyan` is data only, `gold` is
rare. The old `violet` names were an alias for orchid and are gone.

## Radius

One rising scale: `rounded-sm` 10, `rounded-md` 14, `rounded-lg` 16,
`rounded-xl` 20, `rounded-2xl` 28, `rounded-full`. Chips and keys, fields and
tiles, bubbles and nav items, cards, panels.

## Motion

`src/lib/motion.ts` is the vocabulary: four durations (`DURATION.instant`,
`fast`, `base`, `slow`), one curve (`EASE_OUT`), two springs (`spring` for
surfaces, `springSnap` for selection), and the named transitions built from
them (`fade`, `settle`, `ease`, `meter`, `riseIn`). The same durations and curve
exist in CSS as `--duration-*` and `--ease-lilith`, and every Tailwind
`transition-*` utility uses the curve by default.

Do not write a spring or a cubic-bezier inline; the test rejects it. Spend
motion on state changing, not on decoration. Entrances are a fade and a short
rise, never a blur.

Reduced motion is handled in two places and nowhere else: `MotionConfig
reducedMotion="user"` in the shell for Framer Motion, and one media query in
the stylesheet for CSS.

## Feedback states

`src/components/ui/feedback.tsx` and `data-state.tsx`. One way to say each:

| State | Component | Role |
| --- | --- | --- |
| Loading | `LoadingRegion` around `Skeleton` | one polite status per region |
| Error | `InlineError` | alert, with the retry if there is one |
| Notice | `InlineNotice` | status |
| Not built yet | `unavailable()` on the control, plus `NotYetTag` where the label would mislead | disabled, reason as description |
| Workspace without data | `WorkspaceUnavailable` | says so; shows nothing invented |
| Simulated data (development) | `DemoBanner` | never in a production build |

## What is outside these rules, on purpose

- **The Cognitive Atlas.** It was approved as it looked before the foundations.
  Its route pins the earlier radius values, faint ink and transition curve
  (`.atlas-token-scope` in the stylesheet), and its files are not migrated.
- **The avatar and the orb.** They run their own render loops and timing.
- **The avatar calibration panels.** Developer tools with their own dense sizes.
