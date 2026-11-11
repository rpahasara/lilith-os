// Headless test stub for `next/navigation` (no App Router context in Node).
export function usePathname(): string {
  return (globalThis as { __lilithTestPathname?: string }).__lilithTestPathname ?? "/";
}
