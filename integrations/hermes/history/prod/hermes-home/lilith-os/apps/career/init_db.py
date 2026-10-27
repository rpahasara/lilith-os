#!/usr/bin/env python3

import sqlite3
from pathlib import Path

DB = Path.home() / ".hermes" / "lilith-os" / "data" / "lilith.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    domain TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    company_id INTEGER,
    role TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(email),
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    role_title TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'discovered',
    source TEXT,
    source_account TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recruiter_id INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT,
    FOREIGN KEY(company_id) REFERENCES companies(id),
    FOREIGN KEY(recruiter_id) REFERENCES people(id)
);

CREATE TABLE IF NOT EXISTS career_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    activity_type TEXT NOT NULL,
    title TEXT,
    details TEXT,
    source TEXT,
    source_message_id TEXT,
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confidence REAL NOT NULL DEFAULT 0.0,
    FOREIGN KEY(application_id) REFERENCES job_applications(id)
);

CREATE TABLE IF NOT EXISTS career_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    source TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_job_app_stage
ON job_applications(stage);

CREATE INDEX IF NOT EXISTS idx_job_app_last_activity
ON job_applications(last_activity);

CREATE INDEX IF NOT EXISTS idx_career_activity_app
ON career_activities(application_id);

CREATE INDEX IF NOT EXISTS idx_career_events_type
ON career_events(event_type);
"""


def main():
    DB.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)

    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    DB.chmod(0o600)

    print(f"CAREER CRM DB OK path={DB}")


if __name__ == "__main__":
    main()
