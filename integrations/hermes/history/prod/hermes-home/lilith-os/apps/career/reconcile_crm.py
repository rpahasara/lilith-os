#!/usr/bin/env python3

import re
import sqlite3
from pathlib import Path

DB = Path.home() / ".hermes/lilith-os/data/lilith.db"

TERMINAL = {"offer", "rejected", "withdrawn", "closed"}

STAGE_ORDER = {
    "discovered": 0,
    "applied": 1,
    "recruiter_contact": 2,
    "screening": 3,
    "assessment": 4,
    "interview": 5,
    "final_interview": 6,
    "offer": 7,
    "rejected": 100,
    "withdrawn": 100,
    "closed": 100,
}


def normalize_role(value):
    value = (value or "").lower()

    value = value.replace("/", " ")
    value = value.replace("-", " ")

    value = re.sub(
        r"\b(senior|sr|junior|jr)\b",
        "",
        value
    )

    value = re.sub(
        r"\b(engineer|engineering)\b",
        "",
        value
    )

    value = re.sub(r"\s+", " ", value).strip()

    aliases = {
        "devops": "devops",
        "cloud devops": "cloud devops",
        "devops cloud": "cloud devops",
        "site reliability": "sre",
        "sre": "sre",
    }

    return aliases.get(value, value)


def compatible_roles(a, b):
    if not a or not b:
        return False

    if a == "unknown role" or b == "unknown role":
        return False

    na = normalize_role(a)
    nb = normalize_role(b)

    if na == nb:
        return True

    # Treat Cloud/DevOps and DevOps as strongly related.
    if "devops" in na and "devops" in nb:
        return True

    return False


def best_stage(stages):
    terminal = [
        stage for stage in stages
        if stage in TERMINAL
    ]

    if terminal:
        return max(
            terminal,
            key=lambda s: STAGE_ORDER.get(s, 0)
        )

    return max(
        stages,
        key=lambda s: STAGE_ORDER.get(s, 0)
    )


def merge(conn, keep_id, remove_id):
    stages = [
        row[0]
        for row in conn.execute(
            """
            SELECT stage
            FROM job_applications
            WHERE id IN (?, ?)
            """,
            (keep_id, remove_id),
        )
    ]

    stage = best_stage(stages)

    conn.execute(
        """
        UPDATE career_activities
        SET application_id = ?
        WHERE application_id = ?
        """,
        (keep_id, remove_id),
    )

    conn.execute(
        """
        UPDATE career_events
        SET entity_id = ?
        WHERE entity_type = 'job_application'
          AND entity_id = ?
        """,
        (keep_id, remove_id),
    )

    conn.execute(
        """
        UPDATE job_applications
        SET stage = ?,
            last_activity = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (stage, keep_id),
    )

    conn.execute(
        "DELETE FROM job_applications WHERE id = ?",
        (remove_id,),
    )


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    apps = conn.execute(
        """
        SELECT
            ja.id,
            ja.role_title,
            ja.stage,
            ja.company_id,
            c.name AS company
        FROM job_applications ja
        LEFT JOIN companies c ON c.id = ja.company_id
        ORDER BY ja.id
        """
    ).fetchall()

    merged = 0
    consumed = set()

    for i, a in enumerate(apps):
        if a["id"] in consumed:
            continue

        for b in apps[i + 1:]:
            if b["id"] in consumed:
                continue

            # Safest automatic rule:
            # same known company + compatible role.
            if not a["company_id"] or not b["company_id"]:
                continue

            if a["company_id"] != b["company_id"]:
                continue

            if not compatible_roles(
                a["role_title"],
                b["role_title"],
            ):
                continue

            keep = a["id"]
            remove = b["id"]

            merge(conn, keep, remove)

            consumed.add(remove)
            merged += 1

            print(
                f"MERGED "
                f"{remove} -> {keep} "
                f"company={a['company']} "
                f"role={a['role_title']}"
            )

    conn.commit()
    conn.close()

    print(
        f"CAREER RECONCILIATION OK "
        f"merged={merged}"
    )


if __name__ == "__main__":
    main()
