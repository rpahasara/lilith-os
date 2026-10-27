#!/home/lilith/.hermes/google-venv/bin/python

import json
import re
import sqlite3
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

HOME = Path.home()
DB = HOME / ".hermes/lilith-os/data/lilith.db"

TOKENS = {
    "primary": HOME / ".hermes/google_token.json",
    "secondary": HOME / ".hermes/accounts/secondary/google_token.json",
}

OWN_EMAILS = {
    "primary": "__OWNER_PRIMARY_EMAIL__",
    "secondary": "__OWNER_SECONDARY_EMAIL__",
}


def load_credentials(path):
    creds = Credentials.from_authorized_user_file(str(path))

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
        path.chmod(0o600)

    return creds


def extract_email(value):
    value = value or ""

    m = re.search(r"<([^<>]+@[^<>]+)>", value)
    if m:
        return m.group(1).strip().lower()

    m = re.search(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        value,
        re.I,
    )

    return m.group(0).lower() if m else None


def extract_name(value):
    value = value or ""

    if "<" not in value:
        return None

    name = value.split("<", 1)[0].strip().strip('"')
    return name or None


def get_account(conn, activity):
    rows = conn.execute(
        """
        SELECT payload_json
        FROM career_events
        WHERE entity_id = ?
          AND entity_type = 'job_application'
        """,
        (activity["application_id"],),
    ).fetchall()

    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except Exception:
            continue

        if payload.get("message_id") == activity["source_message_id"]:
            account = payload.get("account")
            if account in TOKENS:
                return account

    return activity["source_account"]


def ensure_person(conn, name, email):
    if not email:
        return None

    row = conn.execute(
        """
        SELECT id
        FROM people
        WHERE lower(email) = lower(?)
        LIMIT 1
        """,
        (email,),
    ).fetchone()

    if row:
        conn.execute(
            """
            UPDATE people
            SET name = COALESCE(name, ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name, row["id"]),
        )

        return row["id"]

    cur = conn.execute(
        """
        INSERT INTO people(name, email)
        VALUES (?, ?)
        """,
        (name, email),
    )

    return cur.lastrowid


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    services = {}

    activities = conn.execute(
        """
        SELECT
            ca.id,
            ca.application_id,
            ca.source_message_id,
            ja.source_account
        FROM career_activities ca
        JOIN job_applications ja
          ON ja.id = ca.application_id
        WHERE ca.source_message_id IS NOT NULL
        ORDER BY ca.id
        """
    ).fetchall()

    repaired = 0
    skipped = 0

    # Remember the latest valid external counterparty per application.
    app_counterparty = {}

    for activity in activities:
        account = get_account(conn, activity)

        if account not in TOKENS:
            skipped += 1
            continue

        if account not in services:
            creds = load_credentials(TOKENS[account])
            services[account] = build(
                "gmail",
                "v1",
                credentials=creds,
                cache_discovery=False,
            )

        msg = (
            services[account]
            .users()
            .messages()
            .get(
                userId="me",
                id=activity["source_message_id"],
                format="metadata",
                metadataHeaders=["From", "To"],
            )
            .execute()
        )

        headers = {
            h.get("name", "").lower(): h.get("value", "")
            for h in msg.get("payload", {}).get("headers", [])
        }

        sender_raw = headers.get("from", "")
        recipient_raw = headers.get("to", "")

        sender = extract_email(sender_raw)
        recipient = extract_email(recipient_raw)
        own = OWN_EMAILS[account]

        external_email = None
        external_name = None
        direction = "unknown"

        if sender and sender != own:
            direction = "incoming"
            external_email = sender
            external_name = extract_name(sender_raw)

        elif sender == own and recipient and recipient != own:
            direction = "outgoing"
            external_email = recipient
            external_name = extract_name(recipient_raw)

        if not external_email:
            skipped += 1
            continue

        person_id = ensure_person(
            conn,
            external_name,
            external_email,
        )

        app_counterparty[activity["application_id"]] = {
            "person_id": person_id,
            "email": external_email,
            "name": external_name,
            "direction": direction,
        }

        repaired += 1

    for app_id, party in app_counterparty.items():
        conn.execute(
            """
            UPDATE job_applications
            SET recruiter_id = ?
            WHERE id = ?
            """,
            (party["person_id"], app_id),
        )

    conn.commit()
    conn.close()

    DB.chmod(0o600)

    print(
        f"COUNTERPARTY REPAIR OK "
        f"activities={len(activities)} "
        f"repaired={repaired} "
        f"applications={len(app_counterparty)} "
        f"skipped={skipped}"
    )


if __name__ == "__main__":
    main()
