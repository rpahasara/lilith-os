/**
 * Focus/free windows are DERIVED from the real gaps between timed meetings —
 * never a fabricated "productivity score". A window is open time between now (or
 * a meeting's end) and the next meeting's start, within the next 48h.
 */
import type { FocusWindow, MeetingEvent } from "./types";

const MIN_WINDOW_MIN = 20;
const HORIZON_MS = 48 * 3600_000;

function ms(iso?: string): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isFinite(t) ? t : null;
}

function endOf(e: MeetingEvent): number | null {
  const end = ms(e.end);
  if (end) return end;
  const start = ms(e.start);
  if (start && e.durationMinutes) return start + e.durationMinutes * 60_000;
  return start;
}

export function computeFocusWindows(events: MeetingEvent[], now = Date.now()): FocusWindow[] {
  const timed = events
    .filter((e) => !e.allDay && ms(e.start) != null)
    .map((e) => ({ start: ms(e.start)!, end: endOf(e) ?? ms(e.start)! }))
    .filter((e) => e.end > now) // ignore fully-past meetings
    .sort((a, b) => a.start - b.start);

  const windows: FocusWindow[] = [];
  let cursor = now;
  const horizon = now + HORIZON_MS;

  for (const ev of timed) {
    if (ev.start > cursor) {
      const gapEnd = Math.min(ev.start, horizon);
      const minutes = Math.round((gapEnd - cursor) / 60_000);
      if (minutes >= MIN_WINDOW_MIN) {
        windows.push({
          start: new Date(cursor).toISOString(),
          end: new Date(gapEnd).toISOString(),
          minutes,
          current: cursor === now,
        });
      }
    }
    cursor = Math.max(cursor, ev.end);
    if (cursor >= horizon) break;
  }

  return windows;
}
