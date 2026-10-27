#!/home/lilith/.hermes/google-venv/bin/python

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from redact_sensitive import redact_sensitive

BASE = Path.home() / ".hermes" / "automation" / "productivity"

PRIMARY_TOKEN = Path.home() / ".hermes" / "google_token.json"
SECONDARY_TOKEN = Path.home() / ".hermes" / "accounts" / "secondary" / "google_token.json"

CANDIDATE_PATH = BASE / "state" / "meeting_prep_candidate.json"
FOLLOWUPS_PATH = BASE / "followups" / "followups.json"
OUTPUT_PATH = BASE / "state" / "meeting_context.json"

STOPWORDS = {
    "meeting", "call", "interview", "discussion", "sync", "catchup",
    "with", "from", "your", "about", "the", "and", "for", "this",
    "that", "devops", "engineer", "engineering"
}


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_credentials(path):
    creds = Credentials.from_authorized_user_file(str(path))

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
        path.chmod(0o600)

    return creds


def keywords_from_event(candidate):
    parts = [
        candidate.get("summary") or "",
        candidate.get("description") or "",
        candidate.get("location") or ""
    ]

    for attendee in candidate.get("attendees", []):
        parts.append(attendee.get("displayName") or "")
        parts.append(attendee.get("email") or "")

    words = re.findall(
        r"[A-Za-z0-9._+-]+",
        " ".join(parts).lower()
    )

    useful = []

    for word in words:
        word = word.strip("._+-")

        if len(word) < 4:
            continue

        if word in STOPWORDS:
            continue

        if word not in useful:
            useful.append(word)

    return useful[:12]


def search_account(token_path, account_name, keywords):
    if not token_path.exists():
        return []

    creds = load_credentials(token_path)

    service = build(
        "gmail",
        "v1",
        credentials=creds,
        cache_discovery=False
    )

    after = datetime.now(timezone.utc) - timedelta(days=60)

    # Search a few strong event terms rather than the entire mailbox.
    terms = keywords[:5]

    if not terms:
        return []

    query_terms = " OR ".join(f'"{term}"' for term in terms)
    query = f"after:{int(after.timestamp())} ({query_terms})"

    refs = (
        service.users()
        .messages()
        .list(
            userId="me",
            q=query,
            maxResults=15
        )
        .execute()
        .get("messages", [])
    )

    messages = []

    for ref in refs:
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"]
            )
            .execute()
        )

        headers = {
            h.get("name", "").lower(): h.get("value", "")
            for h in msg.get("payload", {}).get("headers", [])
        }

        messages.append({
            "account": account_name,
            "message_id": ref["id"],
            "thread_id": msg.get("threadId"),
            "from": redact_sensitive(headers.get("from", "")),
            "to": redact_sensitive(headers.get("to", "")),
            "subject": redact_sensitive(headers.get("subject", "")),
            "date": headers.get("date", ""),
            "snippet": redact_sensitive((msg.get("snippet") or "")[:600])
        })

    return messages


def relevance_score(message, keywords):
    text = (
        f"{message.get('from', '')} "
        f"{message.get('to', '')} "
        f"{message.get('subject', '')} "
        f"{message.get('snippet', '')}"
    ).lower()

    score = 0

    for keyword in keywords:
        if keyword in text:
            score += 1

    subject = message.get("subject", "").lower()

    if "interview" in subject:
        score += 3

    if "application" in subject:
        score += 2

    if "recruit" in text:
        score += 2

    return score


def main():
    candidate_payload = load_json(
        CANDIDATE_PATH,
        {"candidate": None}
    )

    candidate = candidate_payload.get("candidate")

    if not candidate:
        print("MEETING CONTEXT OK candidate=none messages=0")
        return 0

    keywords = keywords_from_event(candidate)

    primary = search_account(
        PRIMARY_TOKEN,
        "primary",
        keywords
    )

    secondary = search_account(
        SECONDARY_TOKEN,
        "secondary",
        keywords
    )

    messages = primary + secondary

    for message in messages:
        message["relevance_score"] = relevance_score(
            message,
            keywords
        )

    messages.sort(
        key=lambda item: item["relevance_score"],
        reverse=True
    )

    messages = [
        item
        for item in messages
        if item["relevance_score"] > 0
    ][:10]

    followups = load_json(
        FOLLOWUPS_PATH,
        {"items": []}
    ).get("items", [])

    relevant_followups = []

    event_text = " ".join(keywords)

    for item in followups:
        text = (
            f"{item.get('title', '')} "
            f"{item.get('reason', '')} "
            f"{item.get('resolution', '')}"
        ).lower()

        overlap = sum(
            1 for word in keywords
            if word in text
        )

        if overlap:
            copy = dict(item)
            copy["relevance_score"] = overlap
            relevant_followups.append(copy)

    relevant_followups.sort(
        key=lambda item: item["relevance_score"],
        reverse=True
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_id": candidate.get("event_id"),
        "keywords": keywords,
        "gmail_messages": messages,
        "followups": relevant_followups[:10]
    }

    tmp = OUTPUT_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    tmp.replace(OUTPUT_PATH)
    OUTPUT_PATH.chmod(0o600)

    print(
        f"MEETING CONTEXT OK "
        f"keywords={len(keywords)} "
        f"messages={len(messages)} "
        f"followups={len(relevant_followups[:10])} "
        "model_calls=0"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
