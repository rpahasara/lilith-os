import { useId } from "react";
import { cn } from "@/lib/utils";

/** Compact, original fox-spirit mark for Lilith's shell and identity surfaces. */
export function FoxMark({ className }: { className?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg
      viewBox="0 0 48 48"
      role="img"
      aria-label="Lilith fox spirit mark"
      className={cn("h-7 w-7", className)}
    >
      <defs>
        <linearGradient id={`${id}-shell`} x1="8" y1="6" x2="40" y2="42" gradientUnits="userSpaceOnUse">
          <stop stopColor="#F8EEF4" />
          <stop offset="0.38" stopColor="#E68BA5" />
          <stop offset="1" stopColor="#8F2F4D" />
        </linearGradient>
        <radialGradient id={`${id}-core`} cx="0" cy="0" r="1" gradientTransform="translate(24 25) rotate(90) scale(11)">
          <stop stopColor="#FFF8E8" />
          <stop offset="0.42" stopColor="#E9B878" />
          <stop offset="1" stopColor="#C94F6D" stopOpacity="0" />
        </radialGradient>
        <filter id={`${id}-glow`} x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="2.3" />
        </filter>
      </defs>
      <path d="M9 8.5 20 15l4-3 4 3 11-6.5-3 14.2c0 8.2-5.2 14.2-12 17.2-6.8-3-12-9-12-17.2L9 8.5Z" fill={`url(#${id}-shell)`} opacity=".96" />
      <path d="m12.1 12 8.5 5.1L15 22.4 12.1 12Zm23.8 0-8.5 5.1 5.6 5.3L35.9 12Z" fill="#180D16" opacity=".88" />
      <circle cx="24" cy="25" r="10" fill="#C94F6D" opacity=".3" filter={`url(#${id}-glow)`} />
      <circle cx="24" cy="25" r="9.2" fill={`url(#${id}-core)`} />
      <path d="m17.3 23.8 4.5 2.2-4.9 1.2m13.8-3.4L26.2 26l4.9 1.2M24 27.5v4.1" fill="none" stroke="#27131F" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m21.3 32 2.7 1.6 2.7-1.6" fill="none" stroke="#FFF8EE" strokeOpacity=".72" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}
