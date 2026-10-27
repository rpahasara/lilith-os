#!/home/lilith/.hermes/google-venv/bin/python

import json
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

import sys
sys.path.insert(0, str(Path.home() / ".hermes/automation/productivity"))
from redact_sensitive import redact_sensitive

HOME = Path.home()
DB = HOME / ".hermes/lilith-os/data/lilith.db"

PRIMARY_TOKEN = HOME / ".hermes/google_token.json"
SECONDARY_TOKEN = HOME / ".hermes/accounts/secondary/google_token.json"

HERMES = HOME / ".local/bin/hermes"

LOOKBACK_DAYS = 45
MAX_MESSAGES = 100

STAGES = {
    "offer": [
        "offer letter",
        "job offer",
        "pleased to offer",
        "employment offer",
    ],
    "final_interview": [
        "final interview",
        "final round",
        "final stage",
    ],
    "interview": [
        "interview",
        "technical round",
        "technical interview",
        "interview confirmed",
        "interview scheduling",
    ],
    "assessment": [
        "assessment",
        "coding challenge",
        "technical test",
        "take home",
        "take-home",
        "hackerrank",
    ],
    "screening": [
        "screening call",
        "recruiter call",
        "introductory call",
        "initial discussion",
    ],
    "recruiter_contact": [
        "recruiter",
        "talent acquisition",
        "hiring team",
        "would like to discuss",
        "interested in your profile",
    ],
    "rejected": [
        "unfortunately",
        "not moving forward",
        "other candidates",
        "unsuccessful",
        "regret to inform",
    ],
    "applied": [
        "application received",
        "thank you for applying",
        "application submitted",
        "we received your application",
    ],
}

CAREER_TERMS = [
    "application",
    "applied",
    "recruiter",
    "recruitment",
    "talent acquisition",
    "interview",
    "assessment",
    "hiring",
    "job",
    "position",
    "role",
    "offer",
    "candidate",
]

NOISE_TERMS = [
    "job alert",
    "recommended jobs",
    "jobs you may like",
    "newsletter",
    "weekly jobs",
    "daily jobs",
]


def load_credentials(path):
    creds = Credentials.from_authorized_user_file(str(path))

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
        path.chmod(0o600)

    return creds


def header_map(msg):
    return {
        h.get("name", "").lower(): h.get("value", "")
        for h in msg.get("payload", {}).get("headers", [])
    }


def is_career_message(text):
    lower = text.lower()

    if any(term in lower for term in NOISE_TERMS):
        return False

    return any(term in lower for term in CAREER_TERMS)


def detect_stage(text):
    lower = text.lower()

    for stage in [
        "offer",
        "final_interview",
        "interview",
        "assessment",
        "screening",
        "rejected",
        "recruiter_contact",
        "applied",
    ]:
        for term in STAGES[stage]:
            if term in lower:
                return stage, 0.92

    return "discovered", 0.45


def extract_email_address(value):
    if not value:
        return None

    match = re.search(r"<([^>]+@[^>]+)>", value)
    if match:
        return match.group(1).strip().lower()

    match = re.search(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        value,
        re.I
    )

    return match.group(0).lower() if match else None


def extract_name(value):
    if not value:
        return None

    if "<" in value:
        name = value.split("<", 1)[0].strip().strip('"')
        return name or None

    return None


def company_from_sender(sender):
    email = extract_email_address(sender)

    if not email:
        return None

    domain = email.split("@", 1)[1].lower()

    generic = {
        "gmail.com",
        "outlook.com",
        "hotmail.com",
        "yahoo.com",
        "icloud.com",
    }

    if domain in generic:
        return None

    root = domain.split(".")[0]

    root = re.sub(r"[-_]+", " ", root).strip()

    return root.title() if root else None


def role_from_subject(subject):
    subject = subject or ""

    patterns = [
        r"(?i)(?:for|regarding|about)\s+(?:the\s+)?(.{3,80}?)(?:\s+(?:role|position|opportunity))?(?:$|[-|])",
        r"(?i)application\s+(?:for|to)\s+(.{3,80})",
        r"(?i)(senior\s+devops\s+engineer|devops\s+engineer|site\s+reliability\s+engineer|sre|cloud\s+engineer)",
    ]

    for pattern in patterns:
        match = re.search(pattern, subject)

        if match:
            role = match.group(1).strip(" -|:")
            if 2 < len(role) < 100:
                return role

    return None


def fetch_messages(token_path, account):
    creds = load_credentials(token_path)

    gmail = build(
        "gmail",
        "v1",
        credentials=creds,
        cache_discovery=False
    )

    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    refs = (
        gmail.users()
        .messages()
        .list(
            userId="me",
            q=f"after:{int(since.timestamp())}",
            maxResults=MAX_MESSAGES
        )
        .execute()
        .get("messages", [])
    )

    results = []

    for ref in refs:
        msg = (
            gmail.users()
            .messages()
            .get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"]
            )
            .execute()
        )

        headers = header_map(msg)

        sender = redact_sensitive(headers.get("from", ""))
        subject = redact_sensitive(headers.get("subject", ""))
        snippet = redact_sensitive((msg.get("snippet") or "")[:1000])

        combined = f"{sender} {subject} {snippet}"

        if not is_career_message(combined):
            continue

        results.append({
            "account": account,
            "message_id": ref["id"],
            "thread_id": msg.get("threadId"),
            "sender": sender,
            "subject": subject,
            "snippet": snippet,
            "date": headers.get("date", ""),
        })

    return results


def already_processed(conn, message_id):
    row = conn.execute(
        """
        SELECT 1
        FROM career_activities
        WHERE source_message_id = ?
        LIMIT 1
        """,
        (message_id,)
    ).fetchone()

    return row is not None


def ensure_company(conn, name, domain=None):
    if not name:
        return None

    conn.execute(
        """
        INSERT OR IGNORE INTO companies(name, domain)
        VALUES (?, ?)
        """,
        (name, domain)
    )

    row = conn.execute(
        "SELECT id FROM companies WHERE name = ?",
        (name,)
    ).fetchone()

    return row[0] if row else None


def ensure_person(conn, name, email, company_id=None):
    if not email:
        return None

    conn.execute(
        """
        INSERT OR IGNORE INTO people(name, email, company_id)
        VALUES (?, ?, ?)
        """,
        (name, email, company_id)
    )

    if company_id:
        conn.execute(
            """
            UPDATE people
            SET company_id = COALESCE(company_id, ?),
                name = COALESCE(name, ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE email = ?
            """,
            (company_id, name, email)
        )

    row = conn.execute(
        "SELECT id FROM people WHERE email = ?",
        (email,)
    ).fetchone()

    return row[0] if row else None


def find_application(conn, company_id, role_title):
    if company_id and role_title:
        row = conn.execute(
            """
            SELECT id, stage
            FROM job_applications
            WHERE company_id = ?
              AND lower(role_title) = lower(?)
              AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (company_id, role_title)
        ).fetchone()

        if row:
            return row

    if company_id:
        row = conn.execute(
            """
            SELECT id, stage
            FROM job_applications
            WHERE company_id = ?
              AND status = 'active'
            ORDER BY last_activity DESC
            LIMIT 1
            """,
            (company_id,)
        ).fetchone()

        if row:
            return row

    return None


def create_application(
    conn,
    company_id,
    role_title,
    stage,
    account,
    confidence,
    recruiter_id
):
    cur = conn.execute(
        """
        INSERT INTO job_applications(
            company_id,
            role_title,
            stage,
            source,
            source_account,
            confidence,
            recruiter_id
        )
        VALUES (?, ?, ?, 'gmail', ?, ?, ?)
        """,
        (
            company_id,
            role_title or "Unknown Role",
            stage,
            account,
            confidence,
            recruiter_id
        )
    )

    return cur.lastrowid


def stage_rank(stage):
    order = {
        "discovered": 0,
        "applied": 1,
        "recruiter_contact": 2,
        "screening": 3,
        "assessment": 4,
        "interview": 5,
        "final_interview": 6,
        "offer": 7,
        "rejected": 99,
        "withdrawn": 99,
        "closed": 99,
    }

    return order.get(stage, 0)


def update_application_stage(conn, app_id, current_stage, new_stage, confidence):
    should_update = (
        new_stage in {"rejected", "offer"}
        or stage_rank(new_stage) > stage_rank(current_stage)
    )

    if should_update:
        conn.execute(
            """
            UPDATE job_applications
            SET stage = ?,
                confidence = MAX(confidence, ?),
                last_activity = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_stage, confidence, app_id)
        )
    else:
        conn.execute(
            """
            UPDATE job_applications
            SET last_activity = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (app_id,)
        )


def add_activity(conn, app_id, stage, message, confidence):
    conn.execute(
        """
        INSERT INTO career_activities(
            application_id,
            activity_type,
            title,
            details,
            source,
            source_message_id,
            confidence
        )
        VALUES (?, ?, ?, ?, 'gmail', ?, ?)
        """,
        (
            app_id,
            stage,
            message["subject"],
            message["snippet"],
            message["message_id"],
            confidence
        )
    )


def add_event(conn, app_id, stage, message, confidence):
    payload = {
        "account": message["account"],
        "message_id": message["message_id"],
        "subject": message["subject"],
    }

    conn.execute(
        """
        INSERT INTO career_events(
            event_type,
            entity_type,
            entity_id,
            source,
            confidence,
            payload_json
        )
        VALUES (?, 'job_application', ?, 'gmail', ?, ?)
        """,
        (
            f"career.{stage}",
            app_id,
            confidence,
            json.dumps(payload, ensure_ascii=False)
        )
    )


def process_message(conn, message):
    if already_processed(conn, message["message_id"]):
        return "duplicate"

    text = (
        f"{message['sender']} "
        f"{message['subject']} "
        f"{message['snippet']}"
    )

    stage, confidence = detect_stage(text)

    company_name = company_from_sender(message["sender"])
    company_id = ensure_company(conn, company_name)

    recruiter_email = extract_email_address(message["sender"])
    recruiter_name = extract_name(message["sender"])

    recruiter_id = ensure_person(
        conn,
        recruiter_name,
        recruiter_email,
        company_id
    )

    role_title = role_from_subject(message["subject"])

    existing = find_application(
        conn,
        company_id,
        role_title
    )

    if existing:
        app_id, current_stage = existing
    else:
        app_id = create_application(
            conn,
            company_id,
            role_title,
            stage,
            message["account"],
            confidence,
            recruiter_id
        )
        current_stage = "discovered"

    update_application_stage(
        conn,
        app_id,
        current_stage,
        stage,
        confidence
    )

    add_activity(
        conn,
        app_id,
        stage,
        message,
        confidence
    )

    add_event(
        conn,
        app_id,
        stage,
        message,
        confidence
    )

    return "created"


def main():
    messages = []

    messages.extend(
        fetch_messages(PRIMARY_TOKEN, "primary")
    )

    messages.extend(
        fetch_messages(SECONDARY_TOKEN, "secondary")
    )

    conn = sqlite3.connect(DB)

    created = 0
    duplicates = 0

    try:
        for message in messages:
            result = process_message(conn, message)

            if result == "created":
                created += 1
            else:
                duplicates += 1

        conn.commit()
    finally:
        conn.close()

    DB.chmod(0o600)

    print(
        f"CAREER CRM OK "
        f"career_messages={len(messages)} "
        f"new_activities={created} "
        f"duplicates={duplicates} "
        f"model_calls=0"
    )


if __name__ == "__main__":
    main()
