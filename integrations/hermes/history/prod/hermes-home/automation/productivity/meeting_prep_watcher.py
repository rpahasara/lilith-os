#!/home/lilith/.hermes/google-venv/bin/python

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


BASE = Path.home() / ".hermes" / "automation" / "productivity"
TOKEN_PATH = Path.home() / ".hermes" / "google_token.json"

STATE_PATH = BASE / "state" / "meeting_prep_state.json"
CANDIDATE_PATH = BASE / "state" / "meeting_prep_candidate.json"
LOG_PATH = BASE / "logs" / "meeting_prep.log"

LOCAL_TZ = ZoneInfo("Asia/Colombo")
LOOKAHEAD_MINUTES = 90


def log(message):
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{stamp} {message}"

    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    print(line)


def load_json(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)
    path.chmod(0o600)


def load_credentials():
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        TOKEN_PATH.chmod(0o600)

    return creds


def is_noise_event(event, calendar_name):
    summary = (event.get("summary") or "").lower()
    calendar_name = (calendar_name or "").lower()

    noise_terms = [
        "holiday",
        "holidays",
        "birthday",
        "birthdays",
        "public holiday"
    ]

    combined = f"{summary} {calendar_name}"

    return any(term in combined for term in noise_terms)


def main():
    now = datetime.now(LOCAL_TZ)
    end = now + timedelta(minutes=LOOKAHEAD_MINUTES)

    state = load_json(
        STATE_PATH,
        {
            "prepared_event_ids": []
        }
    )

    prepared = set(state.get("prepared_event_ids", []))

    creds = load_credentials()
    service = build(
        "calendar",
        "v3",
        credentials=creds,
        cache_discovery=False
    )

    calendars = (
        service.calendarList()
        .list()
        .execute()
        .get("items", [])
    )

    candidates = []

    for calendar in calendars:
        calendar_id = calendar["id"]
        calendar_name = calendar.get("summary", "")

        events = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=now.astimezone(timezone.utc).isoformat(),
                timeMax=end.astimezone(timezone.utc).isoformat(),
                singleEvents=True,
                orderBy="startTime"
            )
            .execute()
            .get("items", [])
        )

        for event in events:
            event_id = event.get("id")

            if not event_id or event_id in prepared:
                continue

            # Ignore all-day events.
            if "date" in event.get("start", {}):
                continue

            if event.get("status") == "cancelled":
                continue

            if is_noise_event(event, calendar_name):
                continue

            start_raw = event.get("start", {}).get("dateTime")

            if not start_raw:
                continue

            start = datetime.fromisoformat(
                start_raw.replace("Z", "+00:00")
            ).astimezone(LOCAL_TZ)

            minutes_until = int(
                (start - now).total_seconds() / 60
            )

            if minutes_until < 0 or minutes_until > LOOKAHEAD_MINUTES:
                continue

            candidates.append({
                "event_id": event_id,
                "calendar": calendar_name,
                "summary": event.get("summary") or "(Untitled event)",
                "description": (event.get("description") or "")[:1000],
                "location": event.get("location"),
                "start": start.isoformat(),
                "minutes_until": minutes_until,
                "attendees": [
                    {
                        "email": a.get("email"),
                        "displayName": a.get("displayName")
                    }
                    for a in event.get("attendees", [])
                ]
            })

    if not candidates:
        save_json(
            CANDIDATE_PATH,
            {
                "generated_at": now.isoformat(),
                "candidate": None
            }
        )

        log("OK candidates=0 model_calls=0")
        return 0

    # Nearest upcoming meeting wins.
    candidates.sort(key=lambda x: x["minutes_until"])
    candidate = candidates[0]

    save_json(
        CANDIDATE_PATH,
        {
            "generated_at": now.isoformat(),
            "candidate": candidate
        }
    )

    log(
        f"CANDIDATE event_id={candidate['event_id']} "
        f"in={candidate['minutes_until']}min "
        f"title={candidate['summary']!r} "
        f"model_calls=0"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"ERROR {type(exc).__name__}: {exc}")
        raise SystemExit(1)
