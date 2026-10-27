#!/usr/bin/env python3

import sqlite3
from pathlib import Path

DB = Path.home() / ".hermes/lilith-os/data/lilith.db"

def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT
            ja.id,
            COALESCE(c.name, 'Unknown') AS company,
            ja.role_title,
            ja.stage,
            ja.source_account,
            ja.confidence,
            ja.last_activity,
            COUNT(ca.id) AS activities
        FROM job_applications ja
        LEFT JOIN companies c
            ON c.id = ja.company_id
        LEFT JOIN career_activities ca
            ON ca.application_id = ja.id
        GROUP BY ja.id
        ORDER BY ja.last_activity DESC
    """).fetchall()

    print()
    print("LILITH CAREER CRM")
    print("=" * 118)

    if not rows:
        print("No applications found.")
        return

    print(
        f"{'ID':<4} "
        f"{'COMPANY':<22} "
        f"{'ROLE':<34} "
        f"{'STAGE':<20} "
        f"{'INBOX':<10} "
        f"{'CONF':<6} "
        f"{'ACT':<4}"
    )
    print("-" * 118)

    for r in rows:
        company = (r["company"] or "")[:21]
        role = (r["role_title"] or "")[:33]

        print(
            f"{r['id']:<4} "
            f"{company:<22} "
            f"{role:<34} "
            f"{r['stage']:<20} "
            f"{r['source_account'] or '-':<10} "
            f"{r['confidence']:<6.2f} "
            f"{r['activities']:<4}"
        )

    print("-" * 118)
    print(f"Applications: {len(rows)}")

    stages = conn.execute("""
        SELECT stage, COUNT(*) AS count
        FROM job_applications
        GROUP BY stage
        ORDER BY count DESC
    """).fetchall()

    print()
    print("PIPELINE")
    print("=" * 35)

    for r in stages:
        print(f"{r['stage']:<22} {r['count']}")

    conn.close()

if __name__ == "__main__":
    main()
