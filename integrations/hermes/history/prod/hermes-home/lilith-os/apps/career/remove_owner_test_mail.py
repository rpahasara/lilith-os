#!/home/lilith/.hermes/google-venv/bin/python

import json
import sqlite3
from email.utils import getaddresses
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

HOME = Path.home()
DB = HOME / ".hermes/lilith-os/data/lilith.db"

TOKENS = {
    "primary": HOME / ".hermes/google_token.json",
    "secondary": HOME / ".hermes/accounts/secondary/google_token.json",
}

OWNER_EMAILS = {
    "__OWNER_PRIMARY_EMAIL__",
    "__OWNER_SECONDARY_EMAIL__",
}


def emails(value):
    return {
        email.lower().strip()
        for _, email in getaddresses([value or ""])
        if email
    }


def creds(path):
    c = Credentials.from_authorized_user_file(str(path))

    if c.expired and c.refresh_token:
        c.refresh(Request())

    return c


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

services = {}

rows = conn.execute("""
    SELECT
        ca.id AS activity_id,
        ca.application_id,
        ca.source_message_id,
        ja.source_account,
        ce.payload_json
    FROM career_activities ca
    JOIN job_applications ja
      ON ja.id = ca.application_id
    LEFT JOIN career_events ce
      ON ce.entity_type = 'job_application'
     AND ce.entity_id = ca.application_id
     AND json_extract(
            ce.payload_json,
            '$.message_id'
         ) = ca.source_message_id
    WHERE ca.source_message_id IS NOT NULL
""").fetchall()

remove_activity_ids = []

for row in rows:
    account = row["source_account"]

    if account not in TOKENS:
        continue

    if account not in services:
        services[account] = build(
            "gmail",
            "v1",
            credentials=creds(TOKENS[account]),
            cache_discovery=False,
        )

    account_order = [account] + [
        candidate
        for candidate in TOKENS
        if candidate != account
    ]

    msg = None

    for candidate_account in account_order:
        if candidate_account not in services:
            services[candidate_account] = build(
                "gmail",
                "v1",
                credentials=creds(TOKENS[candidate_account]),
                cache_discovery=False,
            )

        try:
            msg = (
                services[candidate_account]
                .users()
                .messages()
                .get(
                    userId="me",
                    id=row["source_message_id"],
                    format="metadata",
                    metadataHeaders=["From", "To", "Cc"],
                )
                .execute()
            )

            account = candidate_account
            break

        except HttpError as exc:
            if getattr(exc.resp, "status", None) == 404:
                continue
            raise

    if msg is None:
        print(
            f"SKIP missing_message={row['source_message_id']}"
        )
        continue

    headers = {
        h.get("name", "").lower(): h.get("value", "")
        for h in msg.get("payload", {}).get("headers", [])
    }

    all_addresses = (
        emails(headers.get("from"))
        | emails(headers.get("to"))
        | emails(headers.get("cc"))
    )

    if all_addresses and all_addresses <= OWNER_EMAILS:
        remove_activity_ids.append(row["activity_id"])


for activity_id in remove_activity_ids:
    row = conn.execute(
        """
        SELECT application_id, source_message_id
        FROM career_activities
        WHERE id = ?
        """,
        (activity_id,),
    ).fetchone()

    if not row:
        continue

    conn.execute(
        """
        DELETE FROM career_events
        WHERE entity_type = 'job_application'
          AND entity_id = ?
          AND json_extract(payload_json, '$.message_id') = ?
        """,
        (row["application_id"], row["source_message_id"]),
    )

    conn.execute(
        "DELETE FROM career_activities WHERE id = ?",
        (activity_id,),
    )


# Remove applications left with zero activities.
conn.execute("""
    DELETE FROM job_applications
    WHERE id NOT IN (
        SELECT DISTINCT application_id
        FROM career_activities
    )
""")

conn.commit()

remaining_apps = conn.execute(
    "SELECT COUNT(*) FROM job_applications"
).fetchone()[0]

remaining_activities = conn.execute(
    "SELECT COUNT(*) FROM career_activities"
).fetchone()[0]

conn.close()

print(
    f"OWNER TEST CLEANUP OK "
    f"removed_activities={len(remove_activity_ids)} "
    f"remaining_applications={remaining_apps} "
    f"remaining_activities={remaining_activities}"
)
