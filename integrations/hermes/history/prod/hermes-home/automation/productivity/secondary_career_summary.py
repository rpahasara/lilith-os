#!/home/lilith/.hermes/google-venv/bin/python

import json
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from redact_sensitive import redact_sensitive


BASE = Path.home() / ".hermes" / "automation" / "productivity"
TOKEN_PATH = Path.home() / ".hermes" / "accounts" / "secondary" / "google_token.json"
OUTPUT_PATH = BASE / "state" / "secondary_career_summary.json"


CAREER_TERMS = [
    "recruiter",
    "recruitment",
    "talent acquisition",
    "human resources",
    "interview",
    "assessment",
    "application",
    "shortlisted",
    "selected",
    "offer",
    "next round",
    "next step",
    "hiring",
    "inmail",
    "sent you a message",
    "replied to your message",
    "availability",
    "schedule a call"
]


NOISE_TERMS = [
    "job alert",
    "recommended jobs",
    "jobs you may be interested in",
    "newsletter",
    "weekly digest",
    "daily digest",
    "promotion"
]


def get_header(headers, name):
    name = name.lower()
    for item in headers:
        if item.get("name", "").lower() == name:
            return item.get("value", "")
    return ""


def load_credentials():
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        TOKEN_PATH.chmod(0o600)

    return creds


def main():
    creds = load_credentials()

    service = build(
        "gmail",
        "v1",
        credentials=creds,
        cache_discovery=False
    )

    after = datetime.now(timezone.utc) - timedelta(hours=26)
    query = f"after:{int(after.timestamp())}"

    refs = (
        service.users()
        .messages()
        .list(
            userId="me",
            q=query,
            maxResults=50
        )
        .execute()
        .get("messages", [])
    )

    items = []

    for ref in refs:
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            )
            .execute()
        )

        headers = msg.get("payload", {}).get("headers", [])

        sender = get_header(headers, "From")
        subject = get_header(headers, "Subject")
        date = get_header(headers, "Date")
        snippet = (msg.get("snippet") or "").strip()

        combined = f"{sender} {subject} {snippet}".lower()

        if any(term in combined for term in NOISE_TERMS):
            continue

        if not any(term in combined for term in CAREER_TERMS):
            continue

        name, email = parseaddr(sender)

        items.append({
            "message_id": ref["id"],
            "sender_name": name,
            "sender_email": email,
            "subject": subject,
            "date": date,
            "snippet": snippet[:500]
        })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account": "secondary",
        "career_messages": items
    }

    tmp = OUTPUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(OUTPUT_PATH)
    OUTPUT_PATH.chmod(0o600)

    print(f"SECONDARY SUMMARY OK messages={len(items)}")


if __name__ == "__main__":
    main()
