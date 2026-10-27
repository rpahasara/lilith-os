#!/home/lilith/.hermes/google-venv/bin/python

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path.home() / ".hermes" / "automation" / "productivity"
FOLLOWUP_DIR = BASE / "followups"
STATE_PATH = FOLLOWUP_DIR / "followups.json"
LOG_PATH = BASE / "logs" / "followup_tracker.log"

LOCAL_TZ = ZoneInfo("Asia/Colombo")


def log(message: str):
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{stamp} {message}"
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def load_state():
    if not STATE_PATH.exists():
        return {"items": []}

    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"items": []}


def save_state(state):
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)
    STATE_PATH.chmod(0o600)


def normalize(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def extract_due_info(text, reference=None):
    text = normalize(text).lower()

    if reference is None:
        reference = datetime.now(LOCAL_TZ)

    today = reference.date()

    # tomorrow
    if re.search(r"\btomorrow\b", text):
        due = today + timedelta(days=1)
        return {
            "type": "exact",
            "due_date": due.isoformat(),
            "window_start": None,
            "window_end": None,
            "confidence": "high",
            "source_phrase": "tomorrow"
        }

    # in N days / within N days
    m = re.search(r"\b(?:in|within)\s+(\d{1,3})\s+days?\b", text)
    if m:
        days = int(m.group(1))
        due = today + timedelta(days=days)
        return {
            "type": "exact",
            "due_date": due.isoformat(),
            "window_start": None,
            "window_end": None,
            "confidence": "high",
            "source_phrase": m.group(0)
        }

    # next week = Monday-Sunday of following calendar week
    if re.search(r"\bnext week\b", text):
        days_until_next_monday = 7 - today.weekday()
        start = today + timedelta(days=days_until_next_monday)
        end = start + timedelta(days=6)

        return {
            "type": "window",
            "due_date": None,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "confidence": "medium",
            "source_phrase": "next week"
        }

    # ISO date: YYYY-MM-DD
    m = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text)
    if m:
        try:
            due = datetime.strptime(m.group(0), "%Y-%m-%d").date()
            return {
                "type": "exact",
                "due_date": due.isoformat(),
                "window_start": None,
                "window_end": None,
                "confidence": "high",
                "source_phrase": m.group(0)
            }
        except ValueError:
            pass

    # "by 30 August" / "on 30 August"
    month_map = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12
    }

    months = "|".join(month_map.keys())
    m = re.search(
        rf"\b(?:by|on|before)?\s*(\d{{1,2}})\s+({months})(?:\s+(20\d{{2}}))?\b",
        text
    )

    if m:
        day = int(m.group(1))
        month = month_map[m.group(2)]
        year = int(m.group(3)) if m.group(3) else today.year

        try:
            due = datetime(year, month, day).date()

            if not m.group(3) and due < today:
                due = datetime(year + 1, month, day).date()

            return {
                "type": "exact",
                "due_date": due.isoformat(),
                "window_start": None,
                "window_end": None,
                "confidence": "high",
                "source_phrase": m.group(0).strip()
            }
        except ValueError:
            pass

    return {
        "type": "none",
        "due_date": None,
        "window_start": None,
        "window_end": None,
        "confidence": None,
        "source_phrase": None
    }


def add_followup(
    title,
    source,
    reason,
    due_date=None,
    related_message_id=None,
    status="waiting",
    source_text=None
):
    state = load_state()

    if related_message_id:
        for item in state["items"]:
            if item.get("related_message_id") == related_message_id:
                return False

    now = datetime.now(timezone.utc).isoformat()

    due_info = extract_due_info(source_text or "")

    # Explicit supplied due date wins.
    if due_date:
        due_info = {
            "type": "exact",
            "due_date": due_date,
            "window_start": None,
            "window_end": None,
            "confidence": "high",
            "source_phrase": "explicit"
        }

    item = {
        "id": f"fu-{int(datetime.now(timezone.utc).timestamp())}",
        "title": normalize(title),
        "source": source,
        "reason": normalize(reason),
        "status": status,
        "created_at": now,
        "updated_at": now,
        "due_date": due_info["due_date"],
        "due_window_start": due_info["window_start"],
        "due_window_end": due_info["window_end"],
        "due_confidence": due_info["confidence"],
        "due_source_phrase": due_info["source_phrase"],
        "related_message_id": related_message_id
    }

    state["items"].append(item)
    save_state(state)
    return True



def resolve_followup(
    followup_id,
    resolution,
    resolution_message_id=None,
    resolution_type="completed"
):
    state = load_state()

    for item in state.get("items", []):
        if item.get("id") != followup_id:
            continue

        if item.get("status") == "resolved":
            return False

        now = datetime.now(timezone.utc).isoformat()

        item["status"] = "resolved"
        item["resolved_at"] = now
        item["resolution"] = normalize(resolution)
        item["resolution_type"] = resolution_type
        item["resolution_message_id"] = resolution_message_id
        item["updated_at"] = now

        save_state(state)
        return True

    return False


def get_waiting_followups():
    state = load_state()

    return [
        item
        for item in state.get("items", [])
        if item.get("status") == "waiting"
    ]


def list_followups():
    state = load_state()

    if not state["items"]:
        print("No follow-ups.")
        return

    for item in state["items"]:
        if item.get("due_date"):
            due = item["due_date"]
        elif item.get("due_window_start") and item.get("due_window_end"):
            due = f"{item['due_window_start']}..{item['due_window_end']}"
        else:
            due = "no due date"

        print(
            f"{item['id']} | "
            f"{item['status']} | "
            f"{due} | "
            f"{item['title']}"
        )


def main():
    FOLLOWUP_DIR.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) == 1 or sys.argv[1] == "--list":
        list_followups()
        return 0

    if sys.argv[1] == "--init":
        state = load_state()
        save_state(state)
        print("FOLLOWUP TRACKER INITIALIZED")
        return 0

    if sys.argv[1] == "--add-json":
        payload = json.load(sys.stdin)

        created = add_followup(
            title=payload.get("title", "Untitled follow-up"),
            source=payload.get("source", "gmail"),
            reason=payload.get("reason", ""),
            due_date=payload.get("due_date"),
            related_message_id=payload.get("related_message_id"),
            status=payload.get("status", "waiting"),
            source_text=payload.get("source_text", "")
        )

        print("FOLLOWUP_ADDED" if created else "FOLLOWUP_EXISTS")
        return 0

    if sys.argv[1] == "--resolve-json":
        payload = json.load(sys.stdin)

        resolved = resolve_followup(
            followup_id=payload.get("followup_id"),
            resolution=payload.get("resolution", ""),
            resolution_message_id=payload.get("resolution_message_id"),
            resolution_type=payload.get("resolution_type", "completed")
        )

        print("FOLLOWUP_RESOLVED" if resolved else "FOLLOWUP_NOT_CHANGED")
        return 0

    print("Usage:")
    print("  followup_tracker.py --init")
    print("  followup_tracker.py --list")
    print("  followup_tracker.py --add-json")
    print("  followup_tracker.py --resolve-json")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"ERROR {type(exc).__name__}: {exc}")
        raise SystemExit(1)
