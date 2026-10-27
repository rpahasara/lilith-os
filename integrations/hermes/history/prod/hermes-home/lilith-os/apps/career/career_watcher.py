#!/usr/bin/env python3

import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()

PRODUCTIVITY = HOME / ".hermes/automation/productivity"

import sys
sys.path.insert(0, str(PRODUCTIVITY))

from discord_notifier import send_discord

DB = HOME / ".hermes/lilith-os/data/lilith.db"

EXTRACTOR = (
    HOME
    / ".hermes/lilith-os/apps/career/career_extractor_v2.py"
)

RESOLVER = (
    HOME
    / ".hermes/lilith-os/apps/career/entity_resolver.py"
)


def run(cmd):
    proc = subprocess.run(
        [str(x) for x in cmd],
        capture_output=True,
        text=True,
        timeout=900,
    )

    output = (proc.stdout or "").strip()
    error = (proc.stderr or "").strip()

    if output:
        print(output)

    if proc.returncode != 0:
        if error:
            print(error)

        raise SystemExit(proc.returncode)

    return output


def get_metric(output, name):
    match = re.search(
        rf"\b{name}=(\d+)\b",
        output
    )

    return int(match.group(1)) if match else 0


def parse_stage_changes(output):
    pattern = re.compile(
        r"CAREER_STAGE_CHANGE "
        r"application_id=(\d+) "
        r"previous=([^\s]+) "
        r"stage=([^\s]+) "
        r"source=([^\s]+) "
        r"confidence=([0-9.]+)"
    )

    changes = []

    for match in pattern.finditer(output):
        changes.append({
            "application_id": int(match.group(1)),
            "previous_stage": (
                None
                if match.group(2) == "none"
                else match.group(2)
            ),
            "new_stage": match.group(3),
            "source": match.group(4),
            "confidence": float(match.group(5)),
        })

    return changes


def application_summary(conn, application_id):
    row = conn.execute(
        """
        SELECT
            ja.id,
            COALESCE(c.name, 'Unknown') AS company,
            ja.role_title,
            ja.stage,
            ja.source_account
        FROM job_applications ja
        LEFT JOIN companies c
          ON c.id = ja.company_id
        WHERE ja.id = ?
        """,
        (application_id,),
    ).fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "company": row[1],
        "role": row[2],
        "stage": row[3],
        "source_account": row[4],
    }


def audit_stage_changes(changes):
    if not changes:
        return 0

    conn = sqlite3.connect(DB)

    written = 0

    try:
        for change in changes:
            app = application_summary(
                conn,
                change["application_id"]
            )

            if not app:
                continue

            metadata = {
                "source": change["source"],
                "source_account": app["source_account"],
                "external_action": False,
                "notification_pending": True,
            }

            before = {
                "stage": change["previous_stage"],
            }

            after = {
                "stage": change["new_stage"],
                "company": app["company"],
                "role": app["role"],
            }

            conn.execute(
                """
                INSERT INTO os_audit_log(
                    app,
                    action,
                    entity_type,
                    entity_id,
                    actor,
                    confidence,
                    reason,
                    before_json,
                    after_json,
                    reversible,
                    metadata_json
                )
                VALUES(
                    'career',
                    'stage_change',
                    'job_application',
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    1,
                    ?
                )
                """,
                (
                    str(change["application_id"]),
                    (
                        "python"
                        if change["source"] == "python"
                        else "lilith"
                    ),
                    change["confidence"],
                    (
                        f"Career stage changed from "
                        f"{change['previous_stage'] or 'new'} "
                        f"to {change['new_stage']}"
                    ),
                    json.dumps(
                        before,
                        ensure_ascii=False
                    ),
                    json.dumps(
                        after,
                        ensure_ascii=False
                    ),
                    json.dumps(
                        metadata,
                        ensure_ascii=False
                    ),
                )
            )

            written += 1

        conn.commit()

    finally:
        conn.close()

    DB.chmod(0o600)

    return written


def notify_stage_changes(changes):
    if not changes:
        return 0

    conn = sqlite3.connect(DB)

    sent = 0

    try:
        for change in changes:
            app = application_summary(
                conn,
                change["application_id"]
            )

            if not app:
                continue

            previous = (
                change["previous_stage"]
                or "new"
            )

            company = app["company"]
            role = app["role"]

            message = (
                "😈 **LILITH Career**\n\n"
                f"**{company} — {role}**\n"
                f"`{previous}` → **{change['new_stage']}**\n\n"
                f"Confidence: {change['confidence']:.0%}\n"
                "Career CRM updated automatically."
            )

            try:
                send_discord(message)
                sent += 1

                conn.execute(
                    """
                    UPDATE os_audit_log
                    SET metadata_json = json_set(
                        COALESCE(metadata_json, '{}'),
                        '$.notification_pending',
                        0,
                        '$.notification_sent',
                        1
                    )
                    WHERE app = 'career'
                      AND action = 'stage_change'
                      AND entity_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        str(change["application_id"]),
                    )
                )

            except Exception as exc:
                print(
                    "CAREER DISCORD ERROR "
                    f"application_id={change['application_id']} "
                    f"{type(exc).__name__}: {exc}"
                )

        conn.commit()

    finally:
        conn.close()

    return sent


def main():
    print(
        datetime.now(timezone.utc).isoformat(),
        "CAREER WATCH START"
    )

    extractor_output = run([EXTRACTOR])

    stage_changes = parse_stage_changes(
        extractor_output
    )

    audited = audit_stage_changes(
        stage_changes
    )

    print(
        f"CAREER AUDIT "
        f"stage_changes={len(stage_changes)} "
        f"entries_written={audited}"
    )

    notifications = notify_stage_changes(
        stage_changes
    )

    print(
        f"CAREER NOTIFY "
        f"stage_changes={len(stage_changes)} "
        f"discord_sent={notifications}"
    )

    new_career = get_metric(
        extractor_output,
        "career"
    )

    if new_career > 0:
        print(
            f"CAREER CHANGED "
            f"new_career={new_career} "
            "resolver=run"
        )

        run([
            RESOLVER,
            "--apply",
        ])

    else:
        print(
            "CAREER UNCHANGED "
            "resolver=skipped "
            "model_calls=0"
        )

    print(
        datetime.now(timezone.utc).isoformat(),
        "CAREER WATCH OK"
    )


if __name__ == "__main__":
    main()
