# Mobile navigation (P1-8)

Below `md` (768px) the 88px desktop rail is hidden. The fox in a compact 64px top bar opens the
navigation sheet. From `md` up the rail and the top bar are unchanged.

## How it works

- **Trigger:** `components/layout/mobile-nav.tsx`, rendered in `TopBar` (`md:hidden`). The fox is
  a button with `aria-haspopup="dialog"`, `aria-expanded` and `aria-controls`.
- **Sheet:**
  - A floating `glass-strong` panel rendered into `<body>`. It slides in from the left with the
    shared `spring`, and leaves with the `fast` step of `EASE_OUT`.
  - The backdrop is a plain dim (no blur), so it stays cheap on phones.
  - The sheet's own fox sits exactly where the header's fox is (within 1px), so the fox opens and
    closes it.
- **One source of truth:**
  - The destinations are `nav` (`components/layout/nav.ts`).
  - "You are here" is `isNavActive`, now shared by the rail and the sheet.
  - The sheet keeps no route state and adds no provider.
- **Modal behaviour:**
  - The shell (`[data-shell-root]`) is `inert` while the sheet is open, and `#main` stops
    scrolling.
  - Tab is trapped, and focus starts on the current workspace.
  - Escape, the backdrop, the close control and the sheet's fox all close it.
  - Focus returns to the fox, or to the page if the fox has gone because the viewport grew.
- **It closes itself** on any path change (a link, Back, Forward), when Lilith's panel opens
  (Ctrl+Space), and when the viewport grows into the rail's range.
- **Reduced motion:** the shell's `MotionConfig reducedMotion="user"` drops the slide, so the sheet
  only fades.
- **Safe areas:** the sheet's insets use `env(safe-area-inset-*)`. The app does not set
  `viewport-fit=cover`, so on today's phones the browser already keeps content inside the safe area
  and these resolve to the 0.5rem minimum.

## Screen space

Measured on production builds with invented data (Edge and Chrome, headless).

| Width | Content width, before → after | Rail | Header height |
|---|---|---|---|
| 320 | 200 → **288px** (+44%) | 88 → 0 | 72 → 64 |
| 375 | 255 → **343px** (+35%) | 88 → 0 | 72 → 64 |
| 390 | 270 → **358px** (+33%) | 88 → 0 | 72 → 64 |
| 768 / 1024 / 1440 | unchanged | 88 | 72 |

**What the recovered width fixed:**
- The Cognitive Atlas's 33px overflow at 320 is gone; it was measured, not assumed.
- Automations, Meetings, System and the Memory explorer used a grid with no column template below
  `xl`. Like Career before #454, its single column grew to its widest content (397px sideways on an
  empty Automations at 320). Each is now `grid-cols-1` below `xl`.
- The Automations filters wrap on phones instead of scrolling.
- The Career pipeline strip still scrolls sideways on phones by design. It now fades the edge that
  has more stages behind it; a strip that fits (desktop) is drawn exactly as before.

**Desktop and tablet:** screenshots under reduced motion are pixel-identical to the #454 base at 768,
1024 and 1440. The only differences are the Atlas's live particle field, which differs by the same
amount between two runs of the unchanged build.

## Screenshots

All data is invented, and the owner name is replaced.

- `mobile-navigation/navigation-sheet.jpg`: the sheet on Career (375), the Atlas (320) and the
  Command Center (390).
- `mobile-navigation/phone-command-career.jpg`, `mobile-navigation/phone-atlas-automations.jpg`:
  before and after at 375.
- `mobile-navigation/desktop-1440-unchanged.jpg`, `mobile-navigation/tablet-768-unchanged.jpg`:
  wider screens, unchanged.

## Not covered

- Firefox and Safari aren't installed on the verification machine.
- The sheet relies on `inert` (Firefox 112+, Safari 15.5+), `dvh` (already used by the shell),
  CSS `max()`/`env()`, and Framer Motion, which the app already uses everywhere.
