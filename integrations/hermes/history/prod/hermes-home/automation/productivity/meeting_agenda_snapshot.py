#!/home/lilith/.hermes/google-venv/bin/python
"""
LILITH Meetings — agenda snapshot (READ-ONLY).

Background writer for the Meetings workspace. Reads Google Calendar (primary +
secondary accounts) for today (local midnight) through the next 48h, normalises
and redacts each event, and writes a compact snapshot to state/agenda.json.

This is the ONLY component that talks to Google for the Meetings module — the
FastAPI service only ever reads the JSON this produces. It performs NO writes to
Google, sends no mail, and changes no calendar state.

Privacy: raw meeting descriptions are NOT persisted (only a has_description flag
and a recognised video join link). Titles/join links pass through the shared
redact_sensitive policy. Attendee emails are stored in the 0600 state file
(same as the existing candidate file) and are MASKED later by the API.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from redact_sensitive import redact_sensitive

BASE = Path.home() / ".hermes" / "automation" / "productivity"
OUTPUT_PATH = BASE / "state" / "agenda.json"
LOG_PATH = BASE / "logs" / "agenda_snapshot.log"

TOKENS = [
    ("primary", Path.home() / ".hermes" / "google_token.json"),
    ("secondary", Path.home() / ".hermes" / "accounts" / "secondary" / "google_token.json"),
]

LOCAL_TZ = ZoneInfo("Asia/Colombo")
LOOKAHEAD_HOURS = 48

NOISE_TERMS = ["holiday", "holidays", "birthday", "birthdays", "public holiday"]

VIDEO_RE = re.compile(
    r"https?://[^\s>\]\"']*"
    r"(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com|teams\.live\.com|"
    r"webex\.com|whereby\.com|meet\.jit\.si)"
    r"[^\s>\]\"']*"
)


def log(message):
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    line = "%s %s" % (stamp, message)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def load_credentials(path):
    creds = Credentials.from_authorized_user_file(str(path))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
        path.chmod(0o600)
    return creds


def is_noise(summary, calendar_name):
    combined = ("%s %s" % (summary or "", calendar_name or "")).lower()
    return any(term in combined for term in NOISE_TERMS)


def extract_join_link(event):
    link = event.get("hangoutLink")
    if link:
        return redact_sensitive(link)
    for ep in (event.get("conferenceData", {}) or {}).get("entryPoints", []) or []:
        if ep.get("entryPointType") == "video" and ep.get("uri"):
            return redact_sensitive(ep["uri"])
    blob = "%s %s" % (event.get("location", ""), event.get("description", ""))
    m = VIDEO_RE.search(blob)
    if m:
        return redact_sensitive(m.group(0))
    return None


def normalize_event(event, calendar_name):
    start_obj = event.get("start", {})
    end_obj = event.get("end", {})
    all_day = "date" in start_obj

    if all_day:
        start_iso = start_obj.get("date")
        end_iso = end_obj.get("date")
        duration = None
    else:
        start_raw = start_obj.get("dateTime")
        end_raw = end_obj.get("dateTime")
        if not start_raw:
            return None
        start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        start_iso = start_dt.astimezone(LOCAL_TZ).isoformat()
        end_iso = None
        duration = None
        if end_raw:
            end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            end_iso = end_dt.astimezone(LOCAL_TZ).isoformat()
            duration = int((end_dt - start_dt).total_seconds() / 60)

    attendees = [
        {
            "display_name": a.get("displayName"),
            "email": a.get("email"),
        }
        for a in event.get("attendees", [])
    ][:25]

    return {
        "event_id": event.get("id"),
        "calendar": calendar_name,
        "title": redact_sensitive(event.get("summary") or "(Untitled event)"),
        "start": start_iso,
        "end": end_iso,
        "duration_minutes": duration,
        "all_day": all_day,
        "status": event.get("status"),
        "attendees": attendees,
        "attendee_count": len(event.get("attendees", [])),
        "join_link": extract_join_link(event),
        "has_description": bool(event.get("description")),
        # NOTE: raw description intentionally NOT persisted.
    }


def collect_account(account_name, token_path, time_min, time_max):
    if not token_path.exists():
        return []
    creds = load_credentials(token_path)
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    calendars = service.calendarList().list().execute().get("items", [])
    out = []
    for calendar in calendars:
        calendar_id = calendar["id"]
        calendar_name = calendar.get("summary", "")
        events = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
            .get("items", [])
        )
        for event in events:
            if event.get("status") == "cancelled":
                continue
            if is_noise(event.get("summary"), calendar_name):
                continue
            norm = normalize_event(event, calendar_name)
            if norm and norm["event_id"]:
                out.append(norm)
    return out


def main():
    now_local = datetime.now(LOCAL_TZ)
    day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    time_min = day_start_local.astimezone(timezone.utc)
    time_max = (now_local + timedelta(hours=LOOKAHEAD_HOURS)).astimezone(timezone.utc)

    events = []
    seen = set()
    for account_name, token_path in TOKENS:
        try:
            for ev in collect_account(account_name, token_path, time_min, time_max):
                if ev["event_id"] in seen:
                    continue
                seen.add(ev["event_id"])
                events.append(ev)
        except Exception as exc:
            log("WARN account=%s %s: %s" % (account_name, type(exc).__name__, exc))

    events.sort(key=lambda e: str(e.get("start") or ""))

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": "Asia/Colombo",
        "window": {"start": time_min.isoformat(), "end": time_max.isoformat()},
        "events": events,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(OUTPUT_PATH)
    OUTPUT_PATH.chmod(0o600)

    log("AGENDA OK events=%d accounts=%d" % (len(events), len(TOKENS)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log("ERROR %s: %s" % (type(exc).__name__, exc))
        raise SystemExit(1)
