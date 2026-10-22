import html
import json
import re
import sqlite3
import subprocess
import os as _os
from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException

HOME = Path(_os.getenv("LILITH_HOME", Path.home()))
HERMES_HOME = Path(
    _os.getenv("HERMES_HOME", HOME / ".hermes")
)
LILITH_DATA_DIR = Path(
    _os.getenv("LILITH_DATA_DIR", HERMES_HOME / "lilith-os" / "data")
)
DB = Path(
    _os.getenv("LILITH_DB_PATH", LILITH_DATA_DIR / "lilith.db")
)

app = FastAPI(
    title="LILITH OS API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "lilith-os-api",
        "version": "0.1.0",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "database": DB.exists(),
    }


@app.get("/career/applications")
def career_applications():
    conn = db()

    try:
        rows = conn.execute("""
            SELECT
                ja.id,
                COALESCE(c.name, 'Unknown') AS company,
                ja.role_title AS role,
                ja.stage,
                ja.source_account,
                ja.confidence,
                ja.first_seen,
                ja.last_activity,
                COUNT(ca.id) AS activities,
                p.name AS recruiter_name,
                p.email AS recruiter_contact,
                (
                    SELECT title
                    FROM career_activities x
                    WHERE x.application_id = ja.id
                    ORDER BY x.occurred_at DESC, x.id DESC
                    LIMIT 1
                ) AS last_activity_summary
            FROM job_applications ja
            LEFT JOIN companies c
              ON c.id = ja.company_id
            LEFT JOIN people p
              ON p.id = ja.recruiter_id
            LEFT JOIN career_activities ca
              ON ca.application_id = ja.id
            GROUP BY ja.id
            ORDER BY ja.last_activity DESC
        """).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            # Contact linked to this application (recruiter_id -> people). This is
            # raw CRM contact data, NOT a guaranteed human recruiter: it may be a
            # noreply/self address. Surfaced as-is; not reinterpreted.
            name = d.pop("recruiter_name", None)
            contact = d.pop("recruiter_contact", None)
            d["recruiter"] = (
                {"name": name, "contact": contact}
                if (name or contact)
                else None
            )
            result.append(d)

        return result

    finally:
        conn.close()


@app.get("/career/pipeline")
def career_pipeline():
    conn = db()

    try:
        rows = conn.execute("""
            SELECT
                stage,
                COUNT(*) AS count
            FROM job_applications
            GROUP BY stage
            ORDER BY count DESC
        """).fetchall()

        return {
            row["stage"]: row["count"]
            for row in rows
        }

    finally:
        conn.close()


@app.get("/career/activity")
def career_activity(limit: int = 50):
    limit = max(1, min(limit, 200))

    conn = db()

    try:
        rows = conn.execute("""
            SELECT
                ca.id,
                ca.application_id,
                ca.activity_type,
                ca.title,
                ca.occurred_at,
                ca.confidence,
                COALESCE(c.name, 'Unknown') AS company,
                ja.role_title AS role
            FROM career_activities ca
            JOIN job_applications ja
              ON ja.id = ca.application_id
            LEFT JOIN companies c
              ON c.id = ja.company_id
            ORDER BY ca.occurred_at DESC, ca.id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


@app.get("/audit/recent")
def audit_recent(limit: int = 50):
    limit = max(1, min(limit, 200))

    conn = db()

    try:
        rows = conn.execute("""
            SELECT
                id,
                timestamp,
                app,
                action,
                entity_type,
                entity_id,
                actor,
                confidence,
                reason,
                reversible
            FROM os_audit_log
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        # os_audit_log is the primary source. When it is empty, fall back to the
        # real career_events rows (no fabrication) mapped into the audit shape.
        if not rows:
            rows = conn.execute("""
                SELECT
                    id,
                    created_at AS timestamp,
                    'career' AS app,
                    event_type AS action,
                    entity_type,
                    entity_id,
                    source AS actor,
                    confidence,
                    payload_json AS reason,
                    1 AS reversible
                FROM career_events
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def _systemctl_show(unit, props):
    proc = subprocess.run(
        ["systemctl", "show", unit, "--no-pager"]
        + ["--property=%s" % p for p in props],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return proc


def _kv(stdout):
    values = {}
    for line in stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values.setdefault(key, value)  # keep first occurrence
    return values


def _iso(ts):
    """Parse a systemd timestamp string to ISO 8601 (UTC). None if absent."""
    ts = (ts or "").strip()
    if not ts or ts.lower().startswith("n/a"):
        return None
    m = re.search(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", ts)
    if not m:
        return None
    try:
        dt = datetime.strptime(
            "%s %s" % (m.group(1), m.group(2)), "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def _schedule(stdout):
    """Human cadence straight from systemd timer properties (no inference)."""
    m = re.search(r"OnCalendar=([^;}\n]+)", stdout)
    if m:
        return m.group(1).strip()
    m = re.search(r"OnUnitActiveUSec=([^;}\n]+)", stdout)
    if m:
        return "every %s" % m.group(1).strip()
    m = re.search(r"OnBootUSec=([^;}\n]+)", stdout)
    if m:
        return "boot + %s" % m.group(1).strip()
    return None


def _int_or_none(v):
    v = (v or "").strip()
    return int(v) if v.isdigit() else None


def systemctl_state(unit):
    is_timer = unit.endswith(".timer")
    props = [
        "ActiveState", "SubState", "Result", "NRestarts",
        "ExecMainStartTimestamp", "ExecMainExitTimestamp", "ExecMainStatus",
    ]
    if is_timer:
        props += [
            "LastTriggerUSec", "NextElapseUSecRealtime",
            "TimersCalendar", "TimersMonotonic", "Unit",
        ]

    proc = _systemctl_show(unit, props)
    if proc.returncode != 0:
        return {"unit": unit, "available": False, "type": "timer" if is_timer else "service"}

    v = _kv(proc.stdout)

    state = {
        "unit": unit,
        "available": True,
        "type": "timer" if is_timer else "service",
        "active": v.get("ActiveState"),
        "sub": v.get("SubState"),
        "result": v.get("Result"),
        "n_restarts": _int_or_none(v.get("NRestarts")),
        "last_run": _iso(v.get("ExecMainStartTimestamp")),
        "last_run_end": _iso(v.get("ExecMainExitTimestamp")),
        "next_run": None,
        "schedule": None,
    }

    if is_timer:
        # schedule + next fire come from the timer itself...
        state["schedule"] = _schedule(proc.stdout)
        state["next_run"] = _iso(v.get("NextElapseUSecRealtime"))
        state["last_run"] = _iso(v.get("LastTriggerUSec")) or state["last_run"]
        # ...but the run RESULT lives on the paired .service (dead between runs).
        paired = v.get("Unit")
        if paired and paired.endswith(".service"):
            sp = _systemctl_show(paired, [
                "Result", "NRestarts", "ExecMainStartTimestamp",
                "ExecMainExitTimestamp", "ExecMainStatus",
                "ActiveState", "SubState",
            ])
            if sp.returncode == 0:
                sv = _kv(sp.stdout)
                state["result"] = sv.get("Result") or state["result"]
                nr = _int_or_none(sv.get("NRestarts"))
                if nr is not None:
                    state["n_restarts"] = nr
                state["last_run"] = _iso(sv.get("ExecMainStartTimestamp")) or state["last_run"]
                state["last_run_end"] = _iso(sv.get("ExecMainExitTimestamp")) or state["last_run_end"]
                state["service_active"] = sv.get("ActiveState")
                state["service_sub"] = sv.get("SubState")

    return state


@app.get("/system/status")
def system_status():
    units = [
        "hermes-gateway.service",
        "lilith-gmail-watcher.timer",
        "lilith-meeting-prep.timer",
        "lilith-morning-brief.timer",
        "lilith-career-watcher.timer",
        "lilith-os-api.service",
    ]

    return {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "services": [
            systemctl_state(unit)
            for unit in units
        ],
    }


@app.get("/os/overview")
def os_overview():
    conn = db()

    try:
        total_apps = conn.execute(
            "SELECT COUNT(*) FROM job_applications"
        ).fetchone()[0]

        pipeline_rows = conn.execute("""
            SELECT stage, COUNT(*) AS count
            FROM job_applications
            GROUP BY stage
        """).fetchall()

        pipeline = {
            row["stage"]: row["count"]
            for row in pipeline_rows
        }

        recent_audit = conn.execute("""
            SELECT
                id,
                timestamp,
                app,
                action,
                entity_type,
                entity_id,
                actor,
                confidence,
                reason
            FROM os_audit_log
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()

        # Primary is os_audit_log; fall back to real career_events when empty.
        if not recent_audit:
            recent_audit = conn.execute("""
                SELECT
                    id,
                    created_at AS timestamp,
                    'career' AS app,
                    event_type AS action,
                    entity_type,
                    entity_id,
                    source AS actor,
                    confidence,
                    payload_json AS reason
                FROM career_events
                ORDER BY id DESC
                LIMIT 10
            """).fetchall()

    finally:
        conn.close()

    units = [
        "hermes-gateway.service",
        "lilith-gmail-watcher.timer",
        "lilith-meeting-prep.timer",
        "lilith-morning-brief.timer",
        "lilith-career-watcher.timer",
        "lilith-os-api.service",
    ]

    services = [
        systemctl_state(unit)
        for unit in units
    ]

    healthy = sum(
        1
        for service in services
        if (
            service.get("available")
            and service.get("active") == "active"
        )
    )

    unhealthy = len(services) - healthy

    return {
        "lilith": {
            "status": (
                "online"
                if unhealthy == 0
                else "degraded"
            ),
            "os_version": "0.1.0",
            "time_utc": datetime.now(
                timezone.utc
            ).isoformat(),
        },

        "career": {
            "applications": total_apps,
            "pipeline": pipeline,
        },

        "automations": {
            "total": len(services),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "services": services,
        },

        "recent_activity": [
            dict(row)
            for row in recent_audit
        ],
    }


# =========================================================================
# Memory (read-only) — LILITH's persistent cognitive memory.
#
# Sources (real data only):
#   * career_activities (+ job_applications, companies) as career memories.
#   * Hermes curated memory files under ~/.hermes/memories/ EXCLUDING USER.md
#     (sensitive) and empty scaffolds.
#   * people / companies / job_applications as entities + their real FK edges.
#
# NOT exposed in V1: USER.md raw content, and ~/.hermes/state.db conversation
# history / FTS. All routes are GET-only. Absent confidence/importance/
# last_accessed are returned as null — never fabricated.
# =========================================================================

MEM = HERMES_HOME / "memories"

# curated-memory directory -> frontend category
_MEM_DIR_CATEGORY = {
    "projects": "projects",
    "decisions": "work",
    "relationships": "people",
    "tasks": "work",
}

# zero-width / invisible padding chars that pollute scraped email bodies
_ZW = dict.fromkeys(map(ord, "͏​‌‍﻿"), None)


def _iso_dt(s):
    """DB timestamp 'YYYY-MM-DD HH:MM:SS' -> ISO 8601 UTC. None if absent."""
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    if "T" in s:
        return s
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ ](\d{2}:\d{2}:\d{2})", s)
    if m:
        return "%sT%s+00:00" % (m.group(1), m.group(2))
    return s


def _clean(text, limit=240):
    """Unescape HTML, strip zero-width/padding chars, collapse whitespace."""
    if not text:
        return ""
    t = html.unescape(str(text)).translate(_ZW)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > limit:
        t = t[: limit - 1].rstrip() + "…"
    return t


def _pct(conf):
    """0..1 (or 0..100) confidence -> 0..100 int, or None when unknown (<=0)."""
    if conf is None:
        return None
    try:
        c = float(conf)
    except (TypeError, ValueError):
        return None
    if c <= 0:
        return None
    return round(c * 100) if c <= 1 else round(c)


def _career_memory_records(conn):
    """career_activities carry real human titles/details — the richest career
    memory. (career_events is the underlying applied-signal table and would
    duplicate these 1:1 by message id, so it is not re-emitted here.)"""
    rows = conn.execute("""
        SELECT
            ca.id, ca.application_id, ca.activity_type, ca.title, ca.details,
            ca.source, ca.occurred_at, ca.confidence,
            ja.role_title, ja.company_id, ja.stage,
            c.name AS company_name
        FROM career_activities ca
        JOIN job_applications ja ON ja.id = ca.application_id
        LEFT JOIN companies c ON c.id = ja.company_id
        ORDER BY ca.occurred_at DESC, ca.id DESC
    """).fetchall()

    records = []
    for r in rows:
        entities = [{
            "id": "application_%s" % r["application_id"],
            "type": "application",
            "label": r["role_title"] or "Application",
        }]
        if r["company_id"] is not None:
            entities.append({
                "id": "company_%s" % r["company_id"],
                "type": "company",
                "label": r["company_name"] or "Company",
            })
        summary = _clean(r["title"], 140) or "Career activity"
        content = _clean(r["details"], 320) or summary
        at = _iso_dt(r["occurred_at"])
        records.append({
            "id": "career_activity_%s" % r["id"],
            "summary": summary,
            "content": content,
            "category": "career",
            "entity_type": "application",
            "entities": entities,
            # EPI-01 / P-07: email-derived connector activity is a candidate observation, not a stated fact.
            "kind": "unknown",
            "confidence": _pct(r["confidence"]),
            "importance": None,
            "pinned": False,
            "tags": [r["activity_type"]] if r["activity_type"] else [],
            "provenance": {
                "kind": "career_event",
                "source_account": r["source"],
                "label": "Career activity: %s" % (r["activity_type"] or "event"),
                "at": at,
            },
            "created_at": at,
            "updated_at": at,
            "last_accessed": None,
            "related": [],
        })
    return records


def _curated_memory_records():
    """Hermes curated markdown memories. USER.md is excluded (sensitive); empty
    scaffolds are skipped. File-backed entries have no confidence/importance and
    only a file-mtime timestamp (labelled as such)."""
    records = []
    if not MEM.exists():
        return records
    for path in sorted(MEM.rglob("*.md")):
        if path.name == "USER.md":
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not raw.strip():
            continue
        rel = path.relative_to(MEM).as_posix()
        parent = path.parent.name if path.parent != MEM else ""
        category = _MEM_DIR_CATEGORY.get(parent, "knowledge")
        mtime = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
        entries = [e.strip() for e in raw.split("§")] if "§" in raw else [raw.strip()]
        entries = [e for e in entries if e]
        slug = re.sub(r"[^a-z0-9]+", "-", rel.lower())
        for i, entry in enumerate(entries):
            first = entry.lstrip("# ").splitlines()[0].strip()
            records.append({
                "id": "curated_%s_%d" % (slug, i),
                "summary": _clean(first, 140),
                "content": _clean(entry, 1000),
                "category": category,
                "entity_type": None,
                "entities": [],
                # EPI-01 / P-07: curated markdown states no per-entry epistemic basis.
                "kind": "unknown",
                "confidence": None,
                "importance": None,
                "pinned": False,
                "tags": [],
                "provenance": {
                    "kind": "curated_memory",
                    "source_account": "hermes · memories",
                    "label": "%s (timestamp: file mtime)" % rel,
                    "at": mtime,
                },
                "created_at": None,
                "updated_at": mtime,
                "last_accessed": None,
                "related": [],
            })
    return records


def _all_memory_records(conn):
    records = _career_memory_records(conn) + _curated_memory_records()
    records.sort(
        key=lambda r: (r.get("updated_at") or r.get("created_at") or ""),
        reverse=True,
    )
    return records


def _memory_entities(conn, records):
    counts = {}
    for r in records:
        for e in r["entities"]:
            counts[e["id"]] = counts.get(e["id"], 0) + 1

    entities = []

    for p in conn.execute(
        "SELECT id, name, email, company_id, role FROM people"
    ).fetchall():
        eid = "person_%s" % p["id"]
        label = p["name"] or p["email"] or "Person %s" % p["id"]
        entities.append({
            "id": eid, "type": "person", "label": label,
            "subtitle": p["role"] or (p["email"] if p["name"] else None),
            "memory_count": counts.get(eid, 0),
        })

    for c in conn.execute("SELECT id, name, domain FROM companies").fetchall():
        eid = "company_%s" % c["id"]
        entities.append({
            "id": eid, "type": "company",
            "label": c["name"] or "Company %s" % c["id"],
            "subtitle": c["domain"], "memory_count": counts.get(eid, 0),
        })

    for a in conn.execute(
        "SELECT id, role_title, stage FROM job_applications"
    ).fetchall():
        eid = "application_%s" % a["id"]
        entities.append({
            "id": eid, "type": "application",
            "label": a["role_title"] or "Application %s" % a["id"],
            "subtitle": a["stage"], "memory_count": counts.get(eid, 0),
        })

    proj_dir = MEM / "projects"
    if proj_dir.exists():
        for path in sorted(proj_dir.glob("*.md")):
            if path.name in ("README.md", "USER.md"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", path.stem.lower())
            eid = "project_%s" % slug
            first = text.lstrip("# ").splitlines()[0].strip()
            entities.append({
                "id": eid, "type": "project", "label": _clean(first, 80),
                "subtitle": "Curated project", "memory_count": counts.get(eid, 0),
            })

    return entities


def _memory_relationships(conn):
    rels = []
    for p in conn.execute(
        "SELECT id, company_id FROM people WHERE company_id IS NOT NULL"
    ).fetchall():
        rels.append({
            "id": "rel_pc_%s" % p["id"],
            "from": "person_%s" % p["id"],
            "to": "company_%s" % p["company_id"],
            "kind": "works at",
        })
    for a in conn.execute(
        "SELECT id, company_id, recruiter_id FROM job_applications"
    ).fetchall():
        if a["company_id"] is not None:
            rels.append({
                "id": "rel_ac_%s" % a["id"],
                "from": "application_%s" % a["id"],
                "to": "company_%s" % a["company_id"],
                "kind": "at",
            })
        if a["recruiter_id"] is not None:
            rels.append({
                "id": "rel_ap_%s" % a["id"],
                "from": "application_%s" % a["id"],
                "to": "person_%s" % a["recruiter_id"],
                "kind": "contact",
            })
    return rels


@app.get("/memory/records")
def memory_records():
    conn = db()
    try:
        return {"records": _all_memory_records(conn)}
    finally:
        conn.close()


@app.get("/memory/entities")
def memory_entities():
    conn = db()
    try:
        records = _all_memory_records(conn)
        entities = _memory_entities(conn, records)
        ids = {e["id"] for e in entities}
        rels = [
            r for r in _memory_relationships(conn)
            if r["from"] in ids and r["to"] in ids
        ]
        return {"entities": entities, "relationships": rels}
    finally:
        conn.close()


@app.get("/memory/entity/{entity_id}")
def memory_entity(entity_id: str):
    conn = db()
    try:
        records = _all_memory_records(conn)
        entities = _memory_entities(conn, records)
        by_id = {e["id"]: e for e in entities}
        entity = by_id.get(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="entity not found")
        rels = [
            r for r in _memory_relationships(conn)
            if r["from"] == entity_id or r["to"] == entity_id
        ]
        related_ids = {
            (r["to"] if r["from"] == entity_id else r["from"]) for r in rels
        }
        refs = [
            r for r in records
            if any(e["id"] == entity_id for e in r["entities"])
        ]
        return {
            "entity": entity,
            "relationships": rels,
            "related_entities": [by_id[i] for i in related_ids if i in by_id],
            "records": refs,
        }
    finally:
        conn.close()


@app.get("/memory/search")
def memory_search(q: str = ""):
    conn = db()
    try:
        records = _all_memory_records(conn)
    finally:
        conn.close()
    query = (q or "").strip().lower()
    if not query:
        return {"query": q, "records": []}
    out = []
    for r in records:
        hay = " ".join([
            r["summary"], r["content"], r["category"],
            " ".join(r["tags"]),
            " ".join(e["label"] for e in r["entities"]),
            r["provenance"]["label"],
        ]).lower()
        if query in hay:
            out.append(r)
    return {"query": q, "records": out}


@app.get("/memory/overview")
def memory_overview():
    conn = db()
    try:
        records = _all_memory_records(conn)
        entities = _memory_entities(conn, records)
    finally:
        conn.close()

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    def _ts(r):
        return r.get("created_at") or r.get("updated_at")

    def _recent(r):
        t = _ts(r)
        if not t:
            return False
        try:
            return datetime.fromisoformat(t) >= week_ago
        except ValueError:
            return False

    confs = [r["confidence"] for r in records if r["confidence"] is not None]
    categories = {r["category"] for r in records}

    recent_activity = [
        {
            "id": r["id"],
            "at": _ts(r),
            "text": r["summary"],
            "category": r["category"],
            "kind": "learned",
        }
        for r in records[:6]
    ]

    return {
        "total": len(records),
        "recently_learned": sum(1 for r in records if _recent(r)),
        "pinned": sum(1 for r in records if r["pinned"]),
        "categories": len(categories),
        "entities": len(entities),
        "avg_confidence": round(sum(confs) / len(confs)) if confs else 0,
        "recent_activity": recent_activity,
    }


# =========================================================================
# Meetings (read-only) — LILITH's meeting intelligence.
#
# Data comes ONLY from local state JSON that the background meeting-prep chain
# and the agenda-snapshot timer already produce under
# ~/.hermes/automation/productivity/. This API NEVER touches Google/Gmail or
# OAuth tokens — the snapshot writer (a background systemd timer) is the sole
# calendar reader. Attendee emails are masked; raw meeting descriptions and raw
# Gmail snippets are never returned. GET-only.
# =========================================================================

PROD = HERMES_HOME / "automation" / "productivity"
_AGENDA_PATH = PROD / "state/agenda.json"
_CANDIDATE_PATH = PROD / "state/meeting_prep_candidate.json"
_MCONTEXT_PATH = PROD / "state/meeting_context.json"
_PREP_STATE_PATH = PROD / "state/meeting_prep_state.json"
_FOLLOWUPS_PATH = PROD / "followups/followups.json"
_BRIEFS_DIR = PROD / "state/meeting_prep_briefs"

# Re-use the production redactor as defence-in-depth on any text we return.
try:
    import sys as _sys
    if str(PROD) not in _sys.path:
        _sys.path.insert(0, str(PROD))
    from redact_sensitive import redact_sensitive as _redact  # type: ignore
except Exception:
    def _redact(v):
        return "" if v is None else (v if isinstance(v, str) else str(v))

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _mask_email(email):
    if not email or "@" not in str(email):
        return None
    local, _, dom = str(email).partition("@")
    local = local.strip()
    if not local:
        return None
    masked = (local[0] + "***" + local[-1]) if len(local) > 2 else (local[:1] + "***")
    return masked + "@" + dom


def _email_domain(email):
    return str(email).split("@")[-1] if email and "@" in str(email) else None


def _mask_emails_in_text(text):
    if not text:
        return text
    return _EMAIL_RE.sub(lambda m: _mask_email(m.group(0)) or "***", str(text))


def _safe(text):
    """Redact secrets AND mask any email address — for every free-text field a
    meetings endpoint returns (subjects, follow-up text, briefs, keywords)."""
    return _mask_emails_in_text(_redact(text if text is not None else ""))


def _now_utc():
    return datetime.now(timezone.utc)


def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _prepared_ids():
    return set(_load_json(_PREP_STATE_PATH, {}).get("prepared_event_ids", []))


def _candidate_event_id():
    cand = (_load_json(_CANDIDATE_PATH, {}) or {}).get("candidate") or {}
    return cand.get("event_id")


def _context_event_id():
    return (_load_json(_MCONTEXT_PATH, {}) or {}).get("event_id")


def _brief_exists(event_id):
    return bool(event_id) and (_BRIEFS_DIR / ("%s.json" % event_id)).exists()


def _event_status(ev, prepared, ctx_id, cand_id, now):
    ended_at = _parse_iso(ev.get("end") or ev.get("start"))
    if ended_at and ended_at < now:
        return "completed"
    eid = ev.get("event_id")
    if eid in prepared:
        return "delivered"
    if eid and eid == ctx_id:
        return "context_gathered"
    if eid and eid == cand_id:
        return "detected"
    return "scheduled"


def _norm_event(ev, prepared, ctx_id, cand_id, now):
    eid = ev.get("event_id")
    start = _parse_iso(ev.get("start"))
    minutes_until = (
        int((start - now).total_seconds() / 60) if start else None
    )
    return {
        "id": eid,
        # defence-in-depth: a Google primary calendar's name is the owner's email
        "title": _mask_emails_in_text(ev.get("title") or "(Untitled event)"),
        "calendar": _mask_emails_in_text(ev.get("calendar")),
        "start": ev.get("start"),
        "end": ev.get("end"),
        "duration_minutes": ev.get("duration_minutes"),
        "all_day": bool(ev.get("all_day")),
        "minutes_until": minutes_until,
        "join_link": ev.get("join_link"),
        "has_description": bool(ev.get("has_description")),
        "attendees": [
            {
                "display_name": a.get("display_name") or a.get("displayName"),
                "email_masked": _mask_email(a.get("email")),
                "domain": _email_domain(a.get("email")),
            }
            for a in ev.get("attendees", [])
        ],
        "attendee_count": ev.get("attendee_count")
        if ev.get("attendee_count") is not None
        else len(ev.get("attendees", [])),
        "prep_status": _event_status(ev, prepared, ctx_id, cand_id, now),
        "prepared": eid in prepared,
        "brief_available": _brief_exists(eid),
        "context_available": bool(eid) and eid == ctx_id,
    }


def _agenda_events():
    agenda = _load_json(_AGENDA_PATH, {}) or {}
    events = [e for e in agenda.get("events", []) if e.get("status") != "cancelled"]
    events.sort(key=lambda e: str(e.get("start") or ""))
    return agenda, events


@app.get("/meetings/upcoming")
def meetings_upcoming():
    agenda, events = _agenda_events()
    now = _now_utc()
    prepared, ctx_id, cand_id = _prepared_ids(), _context_event_id(), _candidate_event_id()
    return {
        "generated_at": agenda.get("generated_at"),
        "timezone": agenda.get("timezone"),
        "window": agenda.get("window"),
        "events": [_norm_event(e, prepared, ctx_id, cand_id, now) for e in events],
    }


@app.get("/meetings/next")
def meetings_next():
    agenda, events = _agenda_events()
    now = _now_utc()
    prepared, ctx_id, cand_id = _prepared_ids(), _context_event_id(), _candidate_event_id()

    for e in events:
        if e.get("all_day"):
            continue
        end = _parse_iso(e.get("end") or e.get("start"))
        if end and end >= now:
            return {"next": _norm_event(e, prepared, ctx_id, cand_id, now)}

    # Fallback: the watcher's nearest-90-min candidate, if agenda is empty/stale.
    cand = (_load_json(_CANDIDATE_PATH, {}) or {}).get("candidate")
    if cand:
        ev = {
            "event_id": cand.get("event_id"),
            "calendar": cand.get("calendar"),
            "title": _redact(cand.get("summary") or "(Untitled event)"),
            "start": cand.get("start"),
            "end": None,
            "duration_minutes": None,
            "all_day": False,
            "join_link": None,
            "has_description": bool(cand.get("description")),
            "attendees": cand.get("attendees", []),
        }
        return {"next": _norm_event(ev, prepared, ctx_id, cand_id, now)}

    return {"next": None}


@app.get("/meetings/context")
def meetings_context():
    ctx = _load_json(_MCONTEXT_PATH, {}) or {}
    messages = []
    for m in ctx.get("gmail_messages", []):
        messages.append({
            "account": m.get("account"),
            "subject": _safe(m.get("subject") or ""),
            "from": _safe(m.get("from") or ""),
            "date": m.get("date"),
            "relevance_score": m.get("relevance_score"),
        })
    followups = [_norm_followup(f) for f in ctx.get("followups", [])]
    return {
        "event_id": ctx.get("event_id"),
        "generated_at": ctx.get("generated_at"),
        "keywords": [_mask_emails_in_text(k) for k in ctx.get("keywords", [])],
        "messages": messages,
        "message_count": len(messages),
        "followups": followups,
    }


def _norm_followup(f):
    if f.get("due_date"):
        due = f.get("due_date")
        due_kind = "date"
    elif f.get("due_window_start") and f.get("due_window_end"):
        due = "%s .. %s" % (f.get("due_window_start"), f.get("due_window_end"))
        due_kind = "window"
    else:
        due = None
        due_kind = "none"
    return {
        "id": f.get("id"),
        "title": _safe(f.get("title") or ""),
        "source": f.get("source"),
        "reason": _safe(f.get("reason") or ""),
        "status": f.get("status"),
        "due": due,
        "due_kind": due_kind,
        "due_confidence": f.get("due_confidence"),
        "created_at": f.get("created_at"),
        "updated_at": f.get("updated_at"),
        "resolved_at": f.get("resolved_at"),
        "resolution": _safe(f.get("resolution") or "") if f.get("resolution") else None,
    }


@app.get("/meetings/followups")
def meetings_followups():
    items = (_load_json(_FOLLOWUPS_PATH, {}) or {}).get("items", [])
    norm = [_norm_followup(f) for f in items]
    return {
        "total": len(norm),
        "pending": sum(1 for f in norm if f["status"] == "waiting"),
        "followups": norm,
    }


@app.get("/meetings/overview")
def meetings_overview():
    agenda, events = _agenda_events()
    now = _now_utc()
    prepared = _prepared_ids()
    ctx = _load_json(_MCONTEXT_PATH, {}) or {}
    followups = (_load_json(_FOLLOWUPS_PATH, {}) or {}).get("items", [])

    upcoming = [
        e for e in events
        if not e.get("all_day")
        and (_parse_iso(e.get("end") or e.get("start")) or now) >= now
    ]
    today_str = now.astimezone(timezone.utc).date().isoformat()
    today_total = sum(
        1 for e in events
        if str(e.get("start") or "").startswith(today_str)
    )

    nxt = None
    if upcoming:
        ev = _norm_event(upcoming[0], prepared, ctx.get("event_id"), _candidate_event_id(), now)
        nxt = {
            "id": ev["id"], "title": ev["title"], "start": ev["start"],
            "minutes_until": ev["minutes_until"], "prep_status": ev["prep_status"],
        }

    return {
        "generated_at": agenda.get("generated_at"),
        "timezone": agenda.get("timezone"),
        "counts": {
            "upcoming_total": len(upcoming),
            "today_total": today_total,
            "prepared": len(prepared),
            "followups_total": len(followups),
            "followups_pending": sum(1 for f in followups if f.get("status") == "waiting"),
            "context_messages": len(ctx.get("gmail_messages", [])),
        },
        "next": nxt,
        "prep_timer": systemctl_state("lilith-meeting-prep.timer"),
        "agenda_snapshot": systemctl_state("lilith-agenda-snapshot.timer"),
    }


@app.get("/meetings/{event_id}/prep")
def meetings_prep(event_id: str):
    path = _BRIEFS_DIR / ("%s.json" % event_id)
    data = _load_json(path, None)
    if not data:
        raise HTTPException(status_code=404, detail="no prep brief for this event")
    return {
        "event_id": data.get("event_id", event_id),
        "generated_at": data.get("generated_at"),
        "brief": _safe(data.get("brief") or ""),
        "source_counts": data.get("source_counts", {}),
    }


# ─────────────────────────────────────────────────────────────────────────
# LILITH OS conversation seam (added 2026-08-27)
#
# Narrowly-scoped conversation relay: forwards ONE operator message to the
# trusted, localhost-only LILITH OS console adapter (the `lilith_os` gateway
# platform on 127.0.0.1:$LILITH_OS_PORT), which routes it through the normal
# gateway MessageEvent path + Conversation Router V2 and returns LILITH's reply
# synchronously. This endpoint only relays text — it never exposes provider
# keys, model/provider names, raw DB, or memory files. It does NOT provide
# command execution or agent internals.
# ─────────────────────────────────────────────────────────────────────────
import urllib.request as _urlreq
import urllib.error as _urlerr
import hashlib as _hashlib
import hmac as _hmac
import threading as _threading
from fastapi import Body as _Body
from fastapi import Header as _Header


def _hermes_env(key: str, default: str = "") -> str:
    """Read a value from ~/.hermes/.env (the single source of truth shared with
    the gateway), falling back to this process's environment. Values are used
    only to reach the local console; never returned to the client."""
    try:
        for line in (HERMES_HOME / ".env").read_text().splitlines():
            line = line.strip()
            if line.startswith(key + "="):
                return line[len(key) + 1:].strip().strip('"').strip("'")
    except Exception:
        pass
    return _os.getenv(key, default)


# F2 First Interaction evidence capture. Inactive unless LILITH_FI_EVIDENCE_CAPTURE=1. The capture credential is
# read from this process's environment only (never ~/.hermes/.env, which the console's own tools can read) and is
# sent by the server-side Next proxy, never by the browser. Only sessions minted by the capture store are captured;
# every other session is relayed exactly as before. Like the PROD API as a whole, capture never imports the canonical
# memory runtime: it only records and seals exact bytes. Verifying them is the First Interaction candidate gate's job
# (conversation_evidence in the canonical runtime package, which reads `fi_conversation_evidence` read-only).
# The capture credential is SERVICE authentication (the Next server proxy to this API), NOT owner authentication: it
# proves which service sent a turn, never who typed it. Nothing captured here is an owner identity, an authentic First
# Memory or an acceptance; the owner is authenticated only later, by the owner proof and V2 evidence over the exact
# episode value at admission.
_CAPTURE_PREFIX = "fi-capture-"
_CAPTURE_PAYLOAD_KEYS = frozenset({"message", "session"})
_TRANSCRIPT_SCHEMA = "lilith.fm02.transcript.v1"
_capture_locks: dict = {}
_capture_locks_guard = _threading.Lock()
_CAPTURE_TABLES = ("fi_capture_session", "fi_capture_turn", "fi_capture_fault", "fi_conversation_evidence")
_CAPTURE_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS fi_capture_session (
        session_id TEXT PRIMARY KEY, opened_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS fi_capture_turn (
        session_id TEXT NOT NULL REFERENCES fi_capture_session(session_id),
        turn_index INTEGER NOT NULL CHECK(turn_index>=0),
        speaker TEXT NOT NULL CHECK(speaker IN ('OWNER','LILITH')),
        at TEXT NOT NULL, text TEXT NOT NULL,
        PRIMARY KEY(session_id, turn_index))""",
    """CREATE TABLE IF NOT EXISTS fi_capture_fault (
        session_id TEXT NOT NULL REFERENCES fi_capture_session(session_id), at TEXT NOT NULL, reason TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS fi_conversation_evidence (
        evidence_ref TEXT PRIMARY KEY,
        session_id TEXT NOT NULL UNIQUE REFERENCES fi_capture_session(session_id),
        transcript BLOB NOT NULL, sha256 TEXT NOT NULL CHECK(length(sha256)=64),
        turn_count INTEGER NOT NULL CHECK(turn_count>=2),
        started_at TEXT NOT NULL, ended_at TEXT NOT NULL, sealed_at TEXT NOT NULL)""",
    *(f"""CREATE TRIGGER IF NOT EXISTS {t}_no_update BEFORE UPDATE ON {t}
          BEGIN SELECT RAISE(ABORT,'conversation evidence is immutable'); END""" for t in _CAPTURE_TABLES),
    *(f"""CREATE TRIGGER IF NOT EXISTS {t}_no_delete BEFORE DELETE ON {t}
          BEGIN SELECT RAISE(ABORT,'conversation evidence erasure requires Privacy authority'); END"""
      for t in _CAPTURE_TABLES),
    """CREATE TRIGGER IF NOT EXISTS fi_capture_turn_after_seal BEFORE INSERT ON fi_capture_turn
        WHEN EXISTS (SELECT 1 FROM fi_conversation_evidence WHERE session_id=NEW.session_id)
        BEGIN SELECT RAISE(ABORT,'capture session is sealed'); END""",
)


class CaptureRefused(ValueError):
    """Closed capture refusal; `code` never carries dialogue text."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _capture_stamp(moment):
    """Fixed-width UTC (six fraction digits), so stamps order as text and fit the transcript schema."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _capture_transcript_bytes(conversation_ref, turns):
    """Deterministic UTF-8 transcript bytes; dialogue text is kept exactly (no ASCII escaping, no trimming)."""
    doc = {"schema": _TRANSCRIPT_SCHEMA, "conversationRef": conversation_ref,
           "turns": [{"index": i, "speaker": s, "at": at, "text": text} for i, (s, at, text) in enumerate(turns)]}
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class ConversationCaptureStore:
    """Append-only capture sessions, turns, faults and sealed transcripts in their own SQLite file. Speaker, order,
    time and text come from the relay itself; a relay fault makes a session unsealable, because the console may have
    kept a turn the transcript does not have. Sealing stores exact bytes and never repairs text."""

    def __init__(self, path, *, now_fn=lambda: datetime.now(timezone.utc)):
        self.path = Path(path)
        self.now_fn = now_fn

    def _connect(self):
        created = not self.path.exists()
        conn = sqlite3.connect(str(self.path), timeout=5.0, isolation_level=None)
        if created and _os.name != "nt":
            _os.chmod(self.path, 0o600)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        for statement in _CAPTURE_SCHEMA:
            conn.execute(statement)
        return conn

    @staticmethod
    def _state(conn, session_id):
        if conn.execute("SELECT 1 FROM fi_capture_session WHERE session_id=?", (session_id,)).fetchone() is None:
            return None
        sealed = conn.execute("SELECT 1 FROM fi_conversation_evidence WHERE session_id=?", (session_id,)).fetchone()
        return "SEALED" if sealed else "OPEN"

    @staticmethod
    def _faulted(conn, session_id):
        return conn.execute("SELECT 1 FROM fi_capture_fault WHERE session_id=?", (session_id,)).fetchone() is not None

    def open_session(self):
        import uuid as _uuid

        session_id = _CAPTURE_PREFIX + _uuid.uuid4().hex
        conn = self._connect()
        try:
            conn.execute("INSERT INTO fi_capture_session VALUES (?,?)", (session_id, _capture_stamp(self.now_fn())))
        finally:
            conn.close()
        return session_id

    def require_capturable(self, session_id):
        """Refuse before a turn is relayed: unknown, sealed or faulted sessions take no turns."""
        conn = self._connect()
        try:
            state = self._state(conn, session_id)
            if state is None:
                raise CaptureRefused("CAPTURE_SESSION_UNKNOWN")
            if state == "SEALED":
                raise CaptureRefused("CAPTURE_SESSION_SEALED")
            if self._faulted(conn, session_id):
                raise CaptureRefused("CAPTURE_INCOMPLETE")
        finally:
            conn.close()

    def record_exchange(self, session_id, *, owner_text, owner_at, lilith_text, lilith_at):
        """Append one OWNER turn and its LILITH reply; returns the OWNER turn index."""
        if not all(isinstance(v, str) for v in (owner_text, owner_at, lilith_text, lilith_at)):
            raise CaptureRefused("CAPTURE_TURN_MALFORMED")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if self._state(conn, session_id) != "OPEN" or self._faulted(conn, session_id):
                raise CaptureRefused("CAPTURE_SESSION_NOT_OPEN")
            last = conn.execute("SELECT turn_index, at FROM fi_capture_turn WHERE session_id=? "
                                "ORDER BY turn_index DESC LIMIT 1", (session_id,)).fetchone()
            ordered = [owner_at, lilith_at] if last is None else [last[1], owner_at, lilith_at]
            if ordered != sorted(ordered):
                raise CaptureRefused("CAPTURE_ORDER_INVALID")
            index = 0 if last is None else int(last[0]) + 1
            conn.execute("INSERT INTO fi_capture_turn VALUES (?,?,?,?,?)",
                         (session_id, index, "OWNER", owner_at, owner_text))
            conn.execute("INSERT INTO fi_capture_turn VALUES (?,?,?,?,?)",
                         (session_id, index + 1, "LILITH", lilith_at, lilith_text))
            conn.execute("COMMIT")
            return index
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def record_fault(self, session_id, reason):
        conn = self._connect()
        try:
            if self._state(conn, session_id) == "OPEN":
                conn.execute("INSERT INTO fi_capture_fault VALUES (?,?,?)",
                             (session_id, _capture_stamp(self.now_fn()), str(reason)[:64]))
        finally:
            conn.close()

    def seal(self, session_id):
        import uuid as _uuid

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            state = self._state(conn, session_id)
            if state is None:
                raise CaptureRefused("CAPTURE_SESSION_UNKNOWN")
            if state == "SEALED":
                raise CaptureRefused("CAPTURE_SESSION_SEALED")
            if self._faulted(conn, session_id):
                raise CaptureRefused("CAPTURE_INCOMPLETE")
            turns = [(str(r[0]), str(r[1]), str(r[2])) for r in conn.execute(
                "SELECT speaker, at, text FROM fi_capture_turn WHERE session_id=? ORDER BY turn_index", (session_id,))]
            if len(turns) < 2:
                raise CaptureRefused("CAPTURE_TOO_SHORT")
            data = _capture_transcript_bytes(session_id, turns)
            evidence_ref = "evidence.conv." + _uuid.uuid4().hex
            conn.execute("INSERT INTO fi_conversation_evidence VALUES (?,?,?,?,?,?,?,?)",
                         (evidence_ref, session_id, data, _hashlib.sha256(data).hexdigest(), len(turns),
                          turns[0][1], turns[-1][1], _capture_stamp(self.now_fn())))
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return self.evidence(session_id)

    def evidence(self, session_id):
        conn = self._connect()
        try:
            row = conn.execute("SELECT evidence_ref, session_id, sha256, turn_count, started_at, ended_at, sealed_at, "
                               "transcript FROM fi_conversation_evidence WHERE session_id=?", (session_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return {"evidenceRef": row[0], "conversationRef": row[1], "transcriptSchema": _TRANSCRIPT_SCHEMA,
                "sha256": row[2], "turnCount": int(row[3]), "startedAt": row[4], "endedAt": row[5],
                "sealedAt": row[6], "firstMemoryAccepted": False}

    def sealed_transcript(self, session_id):
        conn = self._connect()
        try:
            row = conn.execute("SELECT transcript, sha256 FROM fi_conversation_evidence WHERE session_id=?",
                               (session_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        data = bytes(row[0])
        if _hashlib.sha256(data).hexdigest() != row[1]:
            raise CaptureRefused("EVIDENCE_CORRUPT")
        return data


def _capture_enabled() -> bool:
    return _os.getenv("LILITH_FI_EVIDENCE_CAPTURE", "") == "1"


def _capture_store():
    path = Path(_os.getenv("LILITH_FI_EVIDENCE_DB", str(LILITH_DATA_DIR / "conversation-evidence.db")))
    return ConversationCaptureStore(path)


def _require_capture_auth(credential) -> None:
    if not _capture_enabled():
        raise HTTPException(status_code=403, detail="CAPTURE_INACTIVE")
    expected = _os.getenv("LILITH_OS_OWNER_CAPTURE_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="CAPTURE_CREDENTIAL_UNCONFIGURED")
    if not isinstance(credential, str) or not _hmac.compare_digest(
        credential.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="CAPTURE_NOT_AUTHENTICATED")


def _capture_lock(session: str):
    with _capture_locks_guard:
        return _capture_locks.setdefault(session, _threading.Lock())


def _capture_refusal(exc) -> HTTPException:
    status = 404 if exc.code in {"CAPTURE_SESSION_UNKNOWN", "EVIDENCE_UNKNOWN"} else 409
    return HTTPException(status_code=status, detail=exc.code)


@app.post("/os/conversation")
def os_conversation(
    payload: dict = _Body(default=None),
    x_lilith_os_owner_capture: str = _Header(default=None),
):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    message = str(payload.get("message") or payload.get("text") or "").strip()
    session = str(
        payload.get("session") or payload.get("session_id") or "lilith-os"
    ).strip() or "lilith-os"
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if session.startswith(_CAPTURE_PREFIX):
        return _captured_conversation(payload, message, session, x_lilith_os_owner_capture)
    return _relay_conversation(message, session)


def _captured_conversation(payload, message, session, credential):
    """One OWNER turn and its LILITH reply, recorded exactly as relayed. Refused before relaying unless the request
    is authenticated, carries only {message, session} and the session is an open capture session."""
    _require_capture_auth(credential)
    if set(payload) != _CAPTURE_PAYLOAD_KEYS or payload.get("message") != message:
        raise HTTPException(status_code=400, detail="CAPTURE_PAYLOAD_INVALID")
    store = _capture_store()
    with _capture_lock(session):
        try:
            store.require_capturable(session)
        except CaptureRefused as exc:
            raise _capture_refusal(exc)
        owner_at = _capture_stamp(datetime.now(timezone.utc))
        try:
            relayed = _relay_conversation(message, session)
        except HTTPException as exc:
            # The console may still have kept this turn: the session can no longer be sealed.
            store.record_fault(session, f"RELAY_{exc.status_code}")
            raise
        lilith_at = _capture_stamp(datetime.now(timezone.utc))
        reply = relayed["reply"]
        try:
            store.record_exchange(session, owner_text=message, owner_at=owner_at,
                                  lilith_text=reply if isinstance(reply, str) else "", lilith_at=lilith_at)
        except CaptureRefused as exc:
            store.record_fault(session, exc.code)
            raise _capture_refusal(exc)
    return {**relayed, "session": session, "capture": {"state": "OPEN", "captured": True}}


@app.post("/os/conversation/evidence")
def os_conversation_evidence(
    payload: dict = _Body(default=None),
    x_lilith_os_owner_capture: str = _Header(default=None),
):
    """Open a capture session, seal it, or read its sealed transcript. Authenticated; never accepts memory."""
    _require_capture_auth(x_lilith_os_owner_capture)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    action = payload.get("action")
    store = _capture_store()
    try:
        if action == "open" and set(payload) == {"action"}:
            return {"session": store.open_session(), "state": "OPEN", "firstMemoryAccepted": False}
        session = payload.get("session")
        if set(payload) != {"action", "session"} or not isinstance(session, str):
            raise HTTPException(status_code=400, detail="EVIDENCE_REQUEST_INVALID")
        if action == "seal":
            with _capture_lock(session):
                return store.seal(session)
        if action == "transcript":
            data = store.sealed_transcript(session)
            if data is None:
                raise HTTPException(status_code=404, detail="EVIDENCE_UNKNOWN")
            return {**store.evidence(session), "transcript": data.decode("utf-8")}
    except CaptureRefused as exc:
        raise _capture_refusal(exc)
    raise HTTPException(status_code=400, detail="EVIDENCE_REQUEST_INVALID")


def _relay_conversation(message, session):
    port = _hermes_env("LILITH_OS_PORT", "9901")
    token = _hermes_env("LILITH_OS_TOKEN", "")
    url = f"http://127.0.0.1:{port}/"
    body = json.dumps({"message": message, "session": session}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-LILITH-OS-Token"] = token

    req = _urlreq.Request(url, data=body, headers=headers, method="POST")
    try:
        with _urlreq.urlopen(req, timeout=175) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
    except _urlerr.HTTPError as exc:
        detail = "conversation error"
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", detail)
        except Exception:
            pass
        code = 504 if getattr(exc, "code", 0) == 504 else 502
        raise HTTPException(status_code=code, detail=detail)
    except Exception:
        raise HTTPException(
            status_code=502, detail="LILITH conversation console unreachable"
        )

    return {
        "reply": data.get("reply", ""),
        "session": data.get("session", session),
        "state": data.get("state"),
    }


# ─────────────────────────────────────────────────────────────────────────
# LILITH OS durable Task Store  (Cognitive Core V2 — Vertical Slice 3)
#
# Backend-authoritative persistence for RealCommandCore task records. Storage
# is the existing SQLite lilith.db: a dedicated `tasks` table holding the
# canonical (already client-minimized) CoreTaskRecord as JSON, plus indexed
# columns, a monotonic `revision` for optimistic concurrency, and
# `last_operation_id` for idempotent replay. Read-only career/system/meeting
# /memory endpoints above are untouched. No secrets are stored or logged —
# the client persists only summarized context + evidence references.
# ─────────────────────────────────────────────────────────────────────────

TASK_SCHEMA_VERSION = 1

_TASK_STATUSES = {
    "created", "assembling_context", "planning", "capability_check", "running",
    "verifying", "cancel_requested", "succeeded", "partial", "failed",
    "cancelled", "blocked", "waiting_for_approval",
}
_TERMINAL_STATUSES = {"succeeded", "partial", "failed", "cancelled"}
_APPROVAL_STATES = {"not_required", "required", "approved", "denied", "expired"}
_MAX_RECORD_BYTES = 256 * 1024
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _task_log(op, **fields):
    """Structured, secret-free observability line (captured by journald)."""
    try:
        print("lilith.tasks " + json.dumps({"op": op, **fields},
                                            separators=(",", ":")), flush=True)
    except Exception:
        pass


def _tasks_db():
    """Open the shared DB and ensure the tasks schema exists (idempotent)."""
    conn = db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id           TEXT PRIMARY KEY,
            schema_version    INTEGER NOT NULL,
            revision          INTEGER NOT NULL,
            source            TEXT NOT NULL,
            kind              TEXT,
            status            TEXT NOT NULL,
            title             TEXT,
            created_at        INTEGER NOT NULL,
            updated_at        INTEGER NOT NULL,
            ended_at          INTEGER,
            last_operation_id TEXT,
            record_json       TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_kind ON tasks(kind)")
    conn.commit()
    return conn


def _row_to_task(row):
    rec = json.loads(row["record_json"])
    # Columns are authoritative for these two fields (guard against blob drift).
    rec["revision"] = row["revision"]
    rec["schemaVersion"] = row["schema_version"]
    return rec


def _validate_record(rec):
    if not isinstance(rec, dict):
        raise HTTPException(status_code=400, detail="record must be a JSON object")
    tid = rec.get("taskId")
    if not isinstance(tid, str) or not _TASK_ID_RE.match(tid):
        raise HTTPException(status_code=400, detail="invalid taskId")
    sv = rec.get("schemaVersion", TASK_SCHEMA_VERSION)
    if not isinstance(sv, int) or sv < 1:
        raise HTTPException(status_code=422, detail="invalid schemaVersion")
    if sv > TASK_SCHEMA_VERSION:
        # Unknown newer version must fail safely, never be silently accepted.
        raise HTTPException(status_code=422,
                            detail="unsupported schemaVersion %s" % sv)
    status = rec.get("status")
    if status not in _TASK_STATUSES:
        raise HTTPException(status_code=422, detail="invalid status")
    if rec.get("approvalState", "not_required") not in _APPROVAL_STATES:
        raise HTTPException(status_code=422, detail="invalid approvalState")
    for k in ("createdAt", "updatedAt"):
        if not isinstance(rec.get(k), (int, float)):
            raise HTTPException(status_code=422, detail="invalid %s" % k)
    return tid, sv, status


def _serialize(rec, revision, sv):
    rec["revision"] = revision
    rec["schemaVersion"] = sv
    blob = json.dumps(rec, separators=(",", ":"))
    if len(blob.encode("utf-8")) > _MAX_RECORD_BYTES:
        raise HTTPException(status_code=413, detail="record too large")
    return blob


def _transition_ok(old_status, old_attempt, new_status, new_attempt):
    """Reject terminal→active regressions unless it is an explicit new attempt
    (a retry bumps attemptCount, which is the only legal path back to active)."""
    if old_status in _TERMINAL_STATUSES and new_status not in _TERMINAL_STATUSES:
        return new_attempt > old_attempt
    return True


@app.post("/os/tasks")
def create_task(payload: dict = _Body(default=None)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    record = payload.get("record", payload)
    operation_id = payload.get("operationId")
    tid, sv, status = _validate_record(record)
    conn = _tasks_db()
    try:
        existing = conn.execute(
            "SELECT * FROM tasks WHERE task_id=?", (tid,)).fetchone()
        if existing is not None:
            # Idempotent create: return the existing row, never a duplicate.
            _task_log("create.idempotent", taskId=tid, revision=existing["revision"])
            return {"task": _row_to_task(existing),
                    "revision": existing["revision"], "created": False}
        blob = _serialize(record, 1, sv)
        conn.execute(
            "INSERT INTO tasks (task_id, schema_version, revision, source, kind, "
            "status, title, created_at, updated_at, ended_at, last_operation_id, "
            "record_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, sv, 1, record.get("source", "core"), record.get("scope"),
             status, record.get("title"), int(record["createdAt"]),
             int(record["updatedAt"]), record.get("endedAt"), operation_id, blob),
        )
        conn.commit()
        stored = conn.execute(
            "SELECT * FROM tasks WHERE task_id=?", (tid,)).fetchone()
        _task_log("create", taskId=tid, revision=1, status=status)
        return {"task": _row_to_task(stored), "revision": 1, "created": True}
    finally:
        conn.close()


@app.get("/os/tasks")
def list_tasks(limit: int = 50, status: str = None, kind: str = None):
    limit = max(1, min(int(limit or 50), 200))
    q = "SELECT * FROM tasks"
    clauses, args = [], []
    if status:
        clauses.append("status=?"); args.append(status)
    if kind:
        clauses.append("kind=?"); args.append(kind)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    conn = _tasks_db()
    try:
        rows = conn.execute(q, args).fetchall()
        return {"tasks": [_row_to_task(r) for r in rows], "count": len(rows),
                "schemaVersion": TASK_SCHEMA_VERSION}
    finally:
        conn.close()


@app.get("/os/tasks/{task_id}")
def get_task(task_id: str):
    if not _TASK_ID_RE.match(task_id or ""):
        raise HTTPException(status_code=400, detail="invalid taskId")
    conn = _tasks_db()
    try:
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="task not found")
        return {"task": _row_to_task(row), "revision": row["revision"]}
    finally:
        conn.close()


@app.patch("/os/tasks/{task_id}")
def update_task(task_id: str, payload: dict = _Body(default=None)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    record = payload.get("record", payload)
    expected_revision = payload.get("expectedRevision")
    operation_id = payload.get("operationId")
    if not _TASK_ID_RE.match(task_id or ""):
        raise HTTPException(status_code=400, detail="invalid taskId")
    if not isinstance(record, dict):
        raise HTTPException(status_code=400, detail="record must be a JSON object")
    if record.get("taskId") not in (None, task_id):
        raise HTTPException(status_code=400, detail="taskId mismatch")
    record["taskId"] = task_id
    tid, sv, status = _validate_record(record)
    conn = _tasks_db()
    try:
        existing = conn.execute(
            "SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="task not found")
        # Idempotent replay: the same operationId already applied → no-op.
        if operation_id and existing["last_operation_id"] == operation_id:
            _task_log("update.replay", taskId=task_id, revision=existing["revision"],
                      operationId=operation_id)
            return {"task": _row_to_task(existing),
                    "revision": existing["revision"], "applied": False}
        if expected_revision is not None and expected_revision != existing["revision"]:
            _task_log("update.conflict", taskId=task_id,
                      expected=expected_revision, actual=existing["revision"])
            raise HTTPException(status_code=409, detail={
                "error": "revision_conflict",
                "current": _row_to_task(existing),
                "revision": existing["revision"]})
        old_rec = json.loads(existing["record_json"])
        old_attempt = int(old_rec.get("attemptCount") or 0)
        new_attempt = int(record.get("attemptCount") or 0)
        if not _transition_ok(existing["status"], old_attempt, status, new_attempt):
            _task_log("update.illegal_transition", taskId=task_id,
                      **{"from": existing["status"], "to": status})
            raise HTTPException(status_code=409, detail={
                "error": "illegal_transition",
                "from": existing["status"], "to": status})
        new_rev = existing["revision"] + 1
        blob = _serialize(record, new_rev, sv)
        # Atomic optimistic-concurrency guard: the UPDATE only lands if the
        # revision is still the one we read, so a concurrent writer loses.
        guard = expected_revision if expected_revision is not None else existing["revision"]
        cur = conn.execute(
            "UPDATE tasks SET schema_version=?, revision=?, kind=?, status=?, "
            "title=?, updated_at=?, ended_at=?, last_operation_id=?, record_json=? "
            "WHERE task_id=? AND revision=?",
            (sv, new_rev, record.get("scope"), status, record.get("title"),
             int(record["updatedAt"]), record.get("endedAt"),
             operation_id or existing["last_operation_id"], blob, task_id, guard),
        )
        if cur.rowcount == 0:
            conn.rollback()
            fresh = conn.execute(
                "SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            _task_log("update.conflict.race", taskId=task_id, actual=fresh["revision"])
            raise HTTPException(status_code=409, detail={
                "error": "revision_conflict",
                "current": _row_to_task(fresh), "revision": fresh["revision"]})
        conn.commit()
        stored = conn.execute(
            "SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        _task_log("update", taskId=task_id, revision=new_rev, status=status)
        return {"task": _row_to_task(stored), "revision": new_rev, "applied": True}
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────
# Follow-up drafts — Cognitive Core V2 Slice 4 (approval-gated internal write)
# An UNSENT internal draft record only. Nothing is emailed or sent anywhere.
# Reversible (soft-discard). Idempotent create keyed by idempotency_key.
# ──────────────────────────────────────────────────────────────────────────

import hashlib as _hashlib

DRAFT_SCHEMA_VERSION = 1
_DRAFT_KINDS = {"career_followup", "career_note"}
_DRAFT_STATUSES = {"created", "discarded"}
_DRAFT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_MAX_DRAFT_BYTES = 64 * 1024


def _draft_log(op, **fields):
    """Structured, secret-free observability line (captured by journald)."""
    try:
        print("lilith.drafts " + json.dumps({"op": op, **fields},
                                             separators=(",", ":")), flush=True)
    except Exception:
        pass


def _drafts_db():
    """Open the shared DB and ensure the drafts schema exists (idempotent)."""
    conn = db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS drafts (
            draft_id        TEXT PRIMARY KEY,
            schema_version  INTEGER NOT NULL,
            kind            TEXT NOT NULL,
            status          TEXT NOT NULL,
            target_type     TEXT NOT NULL,
            target_id       TEXT NOT NULL,
            subject         TEXT,
            body            TEXT NOT NULL,
            content_hash    TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            task_id         TEXT,
            step_id         TEXT,
            created_at      INTEGER NOT NULL,
            updated_at      INTEGER NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_drafts_target ON drafts(target_type, target_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_drafts_task ON drafts(task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_drafts_created ON drafts(created_at)")
    conn.commit()
    return conn


def _content_hash(subject, body):
    canonical = (subject or "") + "\n\n" + (body or "")
    return _hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _row_to_draft(row):
    return {
        "draftId": row["draft_id"],
        "schemaVersion": row["schema_version"],
        "kind": row["kind"],
        "status": row["status"],
        "target": {"type": row["target_type"], "id": row["target_id"]},
        "subject": row["subject"],
        "body": row["body"],
        "contentHash": row["content_hash"],
        "idempotencyKey": row["idempotency_key"],
        "taskId": row["task_id"],
        "stepId": row["step_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


@app.post("/os/drafts")
def create_draft(payload: dict = _Body(default=None)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    draft_id = payload.get("draftId")
    idem = payload.get("idempotencyKey")
    kind = payload.get("kind", "career_followup")
    target = payload.get("target") or {}
    target_type = (target.get("type") if isinstance(target, dict) else None) or "application"
    target_id = target.get("id") if isinstance(target, dict) else None
    subject = payload.get("subject")
    body = payload.get("body")
    task_id = payload.get("taskId")
    step_id = payload.get("stepId")
    sv = payload.get("schemaVersion", DRAFT_SCHEMA_VERSION)
    if not isinstance(sv, int) or sv < 1:
        raise HTTPException(status_code=422, detail="invalid schemaVersion")
    if sv > DRAFT_SCHEMA_VERSION:
        raise HTTPException(status_code=422, detail="unsupported schemaVersion %s" % sv)
    if not isinstance(draft_id, str) or not _DRAFT_ID_RE.match(draft_id):
        raise HTTPException(status_code=400, detail="invalid draftId")
    if not isinstance(idem, str) or not _IDEMPOTENCY_RE.match(idem):
        raise HTTPException(status_code=400, detail="invalid idempotencyKey")
    if kind not in _DRAFT_KINDS:
        raise HTTPException(status_code=422, detail="invalid kind")
    if not isinstance(target_id, (str, int)) or str(target_id) == "":
        raise HTTPException(status_code=400, detail="invalid target id")
    target_id = str(target_id)
    if not isinstance(body, str) or not body.strip():
        raise HTTPException(status_code=400, detail="body required")
    if subject is not None and not isinstance(subject, str):
        raise HTTPException(status_code=400, detail="invalid subject")
    if len(body.encode("utf-8")) > _MAX_DRAFT_BYTES:
        raise HTTPException(status_code=413, detail="draft too large")
    chash = _content_hash(subject, body)
    now = int(_now_utc().timestamp() * 1000)
    conn = _drafts_db()
    try:
        # Idempotent create: dedupe on idempotency_key first — retry and
        # duplicate-approval both return the SAME row, never a second draft.
        existing = conn.execute(
            "SELECT * FROM drafts WHERE idempotency_key=?", (idem,)).fetchone()
        if existing is not None:
            _draft_log("create.idempotent", draftId=existing["draft_id"], idem=idem)
            return {"draft": _row_to_draft(existing), "created": False}
        # A different payload reusing an existing draftId is a hard conflict.
        clash = conn.execute(
            "SELECT draft_id FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
        if clash is not None:
            raise HTTPException(status_code=409, detail={"error": "draft_id_exists"})
        conn.execute(
            "INSERT INTO drafts (draft_id, schema_version, kind, status, target_type, "
            "target_id, subject, body, content_hash, idempotency_key, task_id, step_id, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (draft_id, sv, kind, "created", target_type, target_id, subject, body,
             chash, idem, task_id, step_id, now, now),
        )
        conn.commit()
        stored = conn.execute(
            "SELECT * FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
        _draft_log("create", draftId=draft_id, target=target_id, idem=idem,
                   hash=chash[:12])
        return {"draft": _row_to_draft(stored), "created": True}
    finally:
        conn.close()


@app.get("/os/drafts")
def list_drafts(limit: int = 50, target_id: str = None, task_id: str = None,
                idempotency_key: str = None):
    limit = max(1, min(int(limit or 50), 200))
    q = "SELECT * FROM drafts"
    clauses, args = [], []
    if target_id:
        clauses.append("target_id=?"); args.append(str(target_id))
    if task_id:
        clauses.append("task_id=?"); args.append(task_id)
    if idempotency_key:
        clauses.append("idempotency_key=?"); args.append(idempotency_key)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    conn = _drafts_db()
    try:
        rows = conn.execute(q, args).fetchall()
        return {"drafts": [_row_to_draft(r) for r in rows], "count": len(rows),
                "schemaVersion": DRAFT_SCHEMA_VERSION}
    finally:
        conn.close()


@app.get("/os/drafts/{draft_id}")
def get_draft(draft_id: str):
    if not _DRAFT_ID_RE.match(draft_id or ""):
        raise HTTPException(status_code=400, detail="invalid draftId")
    conn = _drafts_db()
    try:
        row = conn.execute(
            "SELECT * FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="draft not found")
        return {"draft": _row_to_draft(row)}
    finally:
        conn.close()


@app.delete("/os/drafts/{draft_id}")
def discard_draft(draft_id: str):
    # Reversibility: soft-discard keeps the audit row but flips status.
    if not _DRAFT_ID_RE.match(draft_id or ""):
        raise HTTPException(status_code=400, detail="invalid draftId")
    now = int(_now_utc().timestamp() * 1000)
    conn = _drafts_db()
    try:
        row = conn.execute(
            "SELECT * FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="draft not found")
        conn.execute(
            "UPDATE drafts SET status='discarded', updated_at=? WHERE draft_id=?",
            (now, draft_id))
        conn.commit()
        stored = conn.execute(
            "SELECT * FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
        _draft_log("discard", draftId=draft_id)
        return {"draft": _row_to_draft(stored)}
    finally:
        conn.close()


# ============================================================================
# BEGIN SLICE 7 — WORLD MODEL + WORKING MEMORY (Phase B)  [additive; append-only]
# Uses existing module globals: app, DB, db, sqlite3, json, datetime, timezone,
# HTTPException. No changes to Slice 1-6 code above this marker.
# ============================================================================

WORLD_SCHEMA_VERSION = 1

_WORLD_EPISTEMIC = ("OBSERVED", "USER_ASSERTED", "INFERRED", "VERIFIED")
_EPI_RANK = {"INFERRED": 1, "OBSERVED": 2, "USER_ASSERTED": 2, "VERIFIED": 3}
_EPI_BASE = {"VERIFIED": 0.98, "OBSERVED": 0.80, "USER_ASSERTED": 0.80, "INFERRED": 0.45}
_EPI_WEIGHT = {"VERIFIED": 1.0, "OBSERVED": 0.7, "USER_ASSERTED": 0.7, "INFERRED": 0.4}
_LIFECYCLE_WEIGHT = {"ACTIVE": 1.0, "CONFLICTED": 0.6, "STALE": 0.4, "SUPERSEDED": 0.0}
_ACTIVE_CONFIDENCE_FLOOR = 0.15
_DEFAULT_WORKING_CAPACITY = 12
_world_schema_ready = False


def _wm_now():
    return datetime.now(timezone.utc).isoformat()


def _world_key(entity_type, entity_id, predicate):
    return "%s:%s:%s" % (entity_type, entity_id, predicate)


def _ensure_world_schema(conn):
    """Idempotent inline bootstrap — production has no migration runner."""
    global _world_schema_ready
    if _world_schema_ready:
        return
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS world_belief (
          key TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
          predicate TEXT NOT NULL, value_json TEXT NOT NULL,
          lifecycle_state TEXT NOT NULL, epistemic_state TEXT NOT NULL,
          confidence REAL NOT NULL, confidence_tier TEXT NOT NULL, confidence_basis TEXT NOT NULL,
          observed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          expires_at TEXT, revision INTEGER NOT NULL DEFAULT 1);
        CREATE INDEX IF NOT EXISTS ix_world_belief_entity ON world_belief(entity_type, entity_id);
        CREATE INDEX IF NOT EXISTS ix_world_belief_lifecycle ON world_belief(lifecycle_state);
        CREATE TABLE IF NOT EXISTS world_belief_evidence (
          id INTEGER PRIMARY KEY AUTOINCREMENT, belief_key TEXT NOT NULL,
          source_class TEXT NOT NULL, source_id TEXT, source_type TEXT, correlation_id TEXT,
          value_json TEXT NOT NULL, epistemic_state TEXT NOT NULL, confidence REAL NOT NULL,
          observed_at TEXT, ingested_at TEXT NOT NULL, origin_ref TEXT, content_hash TEXT,
          note TEXT, superseded INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS ix_world_evidence_key ON world_belief_evidence(belief_key, ingested_at);
        CREATE TABLE IF NOT EXISTS world_belief_conflict (
          belief_key TEXT NOT NULL, conflict_ref TEXT NOT NULL, detected_at TEXT NOT NULL,
          reason TEXT NOT NULL, resolved_at TEXT, PRIMARY KEY (belief_key, conflict_ref));
        CREATE TABLE IF NOT EXISTS world_belief_trace (
          id INTEGER PRIMARY KEY AUTOINCREMENT, correlation_id TEXT NOT NULL,
          belief_key TEXT NOT NULL, at TEXT NOT NULL, prev_lifecycle TEXT,
          new_lifecycle TEXT NOT NULL, prev_epistemic TEXT, new_epistemic TEXT NOT NULL,
          confidence REAL NOT NULL, confidence_basis TEXT NOT NULL, source_class TEXT NOT NULL,
          reconciliation_reason TEXT NOT NULL, superseded_keys TEXT, conflict_keys TEXT);
        CREATE INDEX IF NOT EXISTS ix_world_trace_key ON world_belief_trace(belief_key, at);
        CREATE INDEX IF NOT EXISTS ix_world_trace_corr ON world_belief_trace(correlation_id);
        CREATE TABLE IF NOT EXISTS world_working_seed (
          session_id TEXT PRIMARY KEY, task_id TEXT, focus_json TEXT,
          capacity INTEGER NOT NULL DEFAULT 12, updated_at TEXT NOT NULL);
        """
    )
    conn.commit()
    _world_schema_ready = True


def _world_ro_conn():
    """Read-only connection (mode=ro + busy_timeout) — safe under rollback journal."""
    conn = sqlite3.connect("file:" + str(DB) + "?mode=ro", uri=True, timeout=2.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=2000")
    except sqlite3.OperationalError:
        pass
    return conn


def _world_confidence(epistemic, corroborations, lifecycle):
    """Explainable, rule-derived confidence (spec S7). Returns (value, tier, basis)."""
    base = _EPI_BASE.get(epistemic, 0.45)
    basis = epistemic.lower()
    adj = 0.0
    if corroborations > 0:
        adj += min(0.15, 0.05 * corroborations)
        basis = "%s+%dcorrob" % (epistemic.lower(), corroborations)
    if lifecycle == "CONFLICTED":
        adj -= 0.20
        basis = "conflicted_penalty"
    elif lifecycle == "STALE":
        adj -= 0.15
        basis = "stale_penalty"
    val = max(0.0, min(1.0, base + adj))
    tier = ("high" if val >= 0.80 else "medium" if val >= 0.55
            else "low" if val >= _ACTIVE_CONFIDENCE_FLOOR else "unknown")
    return round(val, 4), tier, basis


def _world_trace(conn, corr, key, at, prev_life, new_life, prev_epi, new_epi,
                 conf, basis, source_class, reason, superseded=None, conflict=None):
    conn.execute(
        "INSERT INTO world_belief_trace (correlation_id, belief_key, at, prev_lifecycle,"
        " new_lifecycle, prev_epistemic, new_epistemic, confidence, confidence_basis,"
        " source_class, reconciliation_reason, superseded_keys, conflict_keys)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (corr, key, at, prev_life, new_life, prev_epi, new_epi, conf, basis,
         source_class, reason, json.dumps(superseded or []), json.dumps(conflict or [])),
    )


def _world_reconcile(conn, entity_type, entity_id, predicate, value, epistemic,
                     source_class, source_id=None, source_type=None,
                     correlation_id=None, observed_at=None, origin_ref=None,
                     note=None, expires_at=None):
    """Deterministic reconciliation R0-R8. INTERNAL ONLY (no HTTP surface)."""
    if epistemic not in _WORLD_EPISTEMIC:
        raise ValueError("bad epistemic state")
    _ensure_world_schema(conn)
    key = _world_key(entity_type, str(entity_id), predicate)
    now = _wm_now()
    corr = correlation_id or ("wm_" + now)
    vjson = json.dumps(value, sort_keys=True, ensure_ascii=False)

    conn.execute(
        "INSERT INTO world_belief_evidence (belief_key, source_class, source_id, source_type,"
        " correlation_id, value_json, epistemic_state, confidence, observed_at, ingested_at,"
        " origin_ref, note, superseded) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
        (key, source_class, source_id, source_type, corr, vjson, epistemic,
         _EPI_BASE.get(epistemic, 0.45), observed_at, now, origin_ref, note),
    )
    row = conn.execute("SELECT * FROM world_belief WHERE key=?", (key,)).fetchone()

    # R0 — no current belief
    if row is None:
        conf, tier, basis = _world_confidence(epistemic, 0, "ACTIVE")
        conn.execute(
            "INSERT INTO world_belief (key, entity_type, entity_id, predicate, value_json,"
            " lifecycle_state, epistemic_state, confidence, confidence_tier, confidence_basis,"
            " observed_at, created_at, updated_at, expires_at, revision)"
            " VALUES (?,?,?,?,?, 'ACTIVE', ?,?,?,?,?,?,?,?, 1)",
            (key, entity_type, str(entity_id), predicate, vjson, epistemic, conf, tier,
             basis, observed_at, now, now, expires_at),
        )
        _world_trace(conn, corr, key, now, None, "ACTIVE", None, epistemic, conf, basis,
                     source_class, "first_evidence")
        conn.commit()
        return {"key": key, "action": "created", "revision": 1, "reason": "first_evidence"}

    cur_life, cur_epi, cur_val, rev = (row["lifecycle_state"], row["epistemic_state"],
                                       row["value_json"], row["revision"])
    new_rank, cur_rank = _EPI_RANK[epistemic], _EPI_RANK.get(cur_epi, 1)

    # R1 — identical value: idempotent corroboration
    if vjson == cur_val:
        corrob = conn.execute(
            "SELECT COUNT(*) c FROM world_belief_evidence WHERE belief_key=? AND value_json=?",
            (key, vjson)).fetchone()["c"] - 1
        life = "ACTIVE" if cur_life in ("STALE", "CONFLICTED") else cur_life
        eff_epi = epistemic if new_rank >= cur_rank else cur_epi
        conf, tier, basis = _world_confidence(eff_epi, corrob, life)
        conn.execute("UPDATE world_belief SET lifecycle_state=?, epistemic_state=?, confidence=?,"
                     " confidence_tier=?, confidence_basis=?, updated_at=? WHERE key=?",
                     (life, eff_epi, conf, tier, basis, now, key))
        if life != cur_life:
            conn.execute("UPDATE world_belief_conflict SET resolved_at=? WHERE belief_key=?"
                         " AND resolved_at IS NULL", (now, key))
        _world_trace(conn, corr, key, now, cur_life, life, cur_epi, eff_epi, conf, basis,
                     source_class, "idempotent_corroboration")
        conn.commit()
        return {"key": key, "action": "updated" if life != cur_life else "noop",
                "revision": rev, "reason": "idempotent_corroboration"}

    # R2 — new higher authority supersedes
    if new_rank > cur_rank:
        conn.execute("UPDATE world_belief_evidence SET superseded=1 WHERE belief_key=? AND id <"
                     " (SELECT MAX(id) FROM world_belief_evidence WHERE belief_key=?)", (key, key))
        rev += 1
        conf, tier, basis = _world_confidence(epistemic, 0, "ACTIVE")
        reason = ("verified_outranks_%s" % cur_epi.lower() if epistemic == "VERIFIED"
                  else "higher_authority_supersedes")
        conn.execute("UPDATE world_belief SET value_json=?, lifecycle_state='ACTIVE',"
                     " epistemic_state=?, confidence=?, confidence_tier=?, confidence_basis=?,"
                     " observed_at=?, updated_at=?, expires_at=?, revision=? WHERE key=?",
                     (vjson, epistemic, conf, tier, basis, observed_at, now, expires_at, rev, key))
        conn.execute("UPDATE world_belief_conflict SET resolved_at=? WHERE belief_key=?"
                     " AND resolved_at IS NULL", (now, key))
        _world_trace(conn, corr, key, now, cur_life, "ACTIVE", cur_epi, epistemic, conf, basis,
                     source_class, reason, superseded=[key])
        conn.commit()
        return {"key": key, "action": "superseded", "revision": rev, "reason": reason}

    # R5 — new lower authority, disagreeing: current stands; keep evidence (superseded)
    if new_rank < cur_rank:
        conn.execute("UPDATE world_belief_evidence SET superseded=1 WHERE belief_key=? AND"
                     " value_json=?", (key, vjson))
        _world_trace(conn, corr, key, now, cur_life, cur_life, cur_epi, cur_epi,
                     row["confidence"], row["confidence_basis"], source_class,
                     "lower_authority_ignored_kept")
        conn.commit()
        return {"key": key, "action": "noop", "revision": rev, "reason": "lower_authority_ignored_kept"}

    # equal authority, differing value
    # R3 — newer comparable observation supersedes (recency ONLY at equal authority)
    if observed_at and (row["observed_at"] is None or observed_at > row["observed_at"]):
        rev += 1
        conf, tier, basis = _world_confidence(epistemic, 0, "ACTIVE")
        conn.execute("UPDATE world_belief SET value_json=?, lifecycle_state='ACTIVE',"
                     " epistemic_state=?, confidence=?, confidence_tier=?, confidence_basis=?,"
                     " observed_at=?, updated_at=?, revision=? WHERE key=?",
                     (vjson, epistemic, conf, tier, basis, observed_at, now, rev, key))
        _world_trace(conn, corr, key, now, cur_life, "ACTIVE", cur_epi, epistemic, conf, basis,
                     source_class, "newer_comparable_supersedes", superseded=[key])
        conn.commit()
        return {"key": key, "action": "superseded", "revision": rev, "reason": "newer_comparable_supersedes"}

    # R4 — equal authority, disagreeing, not clearly newer -> CONFLICTED (retain both)
    rev += 1
    conf, tier, basis = _world_confidence(cur_epi, 0, "CONFLICTED")
    conn.execute("UPDATE world_belief SET lifecycle_state='CONFLICTED', confidence=?,"
                 " confidence_tier=?, confidence_basis=?, updated_at=?, revision=? WHERE key=?",
                 (conf, tier, basis, now, rev, key))
    conn.execute("INSERT OR IGNORE INTO world_belief_conflict (belief_key, conflict_ref,"
                 " detected_at, reason) VALUES (?,?,?, 'equal_authority_disagree')",
                 (key, "evidence:" + now, now))
    _world_trace(conn, corr, key, now, cur_life, "CONFLICTED", cur_epi, cur_epi, conf, basis,
                 source_class, "equal_authority_disagree", conflict=[key])
    conn.commit()
    return {"key": key, "action": "conflicted", "revision": rev, "reason": "equal_authority_disagree"}


# ---- Controlled ingestion boundary (INTERNAL functions; NO generic setBelief) ----
# R7 (source unavailable) and R8 (unknown) are enforced HERE: never call reconcile
# with a None/empty value from a failed/absent source.

def submit_observation(entity_type, entity_id, predicate, value,
                       source_class="LIVE_CONNECTOR", conn=None, **kw):
    if value is None:  # R7 — emptiness is never evidence of a value
        return {"key": _world_key(entity_type, str(entity_id), predicate),
                "action": "noop", "reason": "source_unavailable_noop"}
    own = conn is None
    conn = conn or db()
    try:
        return _world_reconcile(conn, entity_type, entity_id, predicate, value, "OBSERVED",
                                source_class, **kw)
    finally:
        if own:
            conn.close()


def submit_user_assertion(entity_type, entity_id, predicate, value, conn=None, **kw):
    own = conn is None
    conn = conn or db()
    try:
        return _world_reconcile(conn, entity_type, entity_id, predicate, value,
                                "USER_ASSERTED", "USER", **kw)
    finally:
        if own:
            conn.close()


def submit_inference_candidate(entity_type, entity_id, predicate, value, basis=None,
                               conn=None, **kw):
    own = conn is None
    conn = conn or db()
    kw.setdefault("note", basis or "inference")
    try:
        return _world_reconcile(conn, entity_type, entity_id, predicate, value, "INFERRED",
                                "INFERENCE", **kw)
    finally:
        if own:
            conn.close()


def apply_verified_delta(entity_type, entity_id, predicate, value, verification_ref=None,
                         mirror_audit=False, conn=None, **kw):
    own = conn is None
    conn = conn or db()
    kw.setdefault("origin_ref", verification_ref)
    try:
        res = _world_reconcile(conn, entity_type, entity_id, predicate, value, "VERIFIED",
                               "VERIFICATION", **kw)
        if mirror_audit:  # optional convenience mirror; world trace stays authoritative
            conn.execute(
                "INSERT INTO os_audit_log (app, action, entity_type, entity_id, actor,"
                " confidence, reason, before_json, after_json, reversible)"
                " VALUES ('world-model','belief.verified',?,?, 'verification', 0.98, ?, NULL, ?, 0)",
                (entity_type, str(entity_id), res.get("reason"), json.dumps(value)))
            conn.commit()
        return res
    finally:
        if own:
            conn.close()


def world_freshness_sweep(now=None):
    """R6 — mark ACTIVE beliefs past expires_at as STALE (value retained)."""
    now = now or _wm_now()
    conn = db()
    try:
        _ensure_world_schema(conn)
        rows = conn.execute("SELECT key, epistemic_state FROM world_belief WHERE"
                            " expires_at IS NOT NULL AND expires_at < ? AND lifecycle_state='ACTIVE'",
                            (now,)).fetchall()
        for r in rows:
            conf, tier, basis = _world_confidence(r["epistemic_state"], 0, "STALE")
            conn.execute("UPDATE world_belief SET lifecycle_state='STALE', confidence=?,"
                         " confidence_tier=?, confidence_basis=?, updated_at=? WHERE key=?",
                         (conf, tier, basis, now, r["key"]))
            _world_trace(conn, "sweep_" + now, r["key"], now, "ACTIVE", "STALE",
                         r["epistemic_state"], r["epistemic_state"], conf, basis, "SYSTEM",
                         "freshness_expired")
        conn.commit()
        return {"staled": len(rows)}
    finally:
        conn.close()


def world_ingest_career(limit=200):
    """First live domain. Reads job_applications (+companies). NULL fields skipped
    (R7/R8 — never ingest emptiness). follow_up is NOT emitted here (no column)."""
    conn = db()
    try:
        _ensure_world_schema(conn)
        apps = conn.execute(
            "SELECT ja.id, ja.role_title, ja.stage, ja.status, ja.last_activity,"
            " ja.source_account, c.name AS company FROM job_applications ja"
            " LEFT JOIN companies c ON c.id = ja.company_id LIMIT ?", (limit,)).fetchall()
        n = 0
        for a in apps:
            eid = a["id"]
            prov = dict(source_type="career.application", source_id="career-store",
                        origin_ref="job_applications/%s" % eid, observed_at=a["last_activity"],
                        note=("acct:%s" % a["source_account"]) if a["source_account"] else None)
            for pred, val in (("status", a["stage"]), ("role", a["role_title"]),
                              ("company", a["company"]), ("last_activity", a["last_activity"])):
                if val is not None:
                    submit_observation("career.application", eid, pred, val, conn=conn, **prov)
                    n += 1
        return {"applications": len(apps), "observations": n}
    finally:
        conn.close()


# ---- Working Memory reconstruction (mirrors src/lib/world/working-memory.ts) ----

def _wm_recency(iso, now_ts):
    if not iso:
        return 0.0
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0
    return 0.5 ** (max(0.0, (now_ts - t) / 86400.0) / 14.0)


def _wm_score(b, focus_entities, focus_predicates, now_ts):
    if b["lifecycle_state"] == "SUPERSEDED" or b["confidence"] < _ACTIVE_CONFIDENCE_FLOOR:
        return 0.0
    rel = 0.0
    if (b["entity_type"], str(b["entity_id"])) in focus_entities:
        rel += 1.0
    if b["predicate"] in focus_predicates:
        rel += 0.5
    return (3.0 * rel + 1.5 * _EPI_WEIGHT.get(b["epistemic_state"], 0.4)
            + 1.2 * b["confidence"] + 0.8 * _wm_recency(b["updated_at"] or b["observed_at"], now_ts)
            + 0.5 * _LIFECYCLE_WEIGHT.get(b["lifecycle_state"], 0.4))


def build_working_set(session_id, focus_entities=None, focus_predicates=None,
                      capacity=_DEFAULT_WORKING_CAPACITY, task_id=None):
    """Ephemeral, reconstructible. Reads durable beliefs read-only; no WM persistence."""
    fe = set((et, str(eid)) for et, eid in (focus_entities or []))
    fp = set(focus_predicates or [])
    now = _wm_now()
    now_ts = datetime.now(timezone.utc).timestamp()
    conn = _world_ro_conn()
    try:
        rows = conn.execute("SELECT * FROM world_belief WHERE lifecycle_state != 'SUPERSEDED'").fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    scored = [(r, _wm_score(r, fe, fp, now_ts)) for r in rows]
    scored = sorted([s for s in scored if s[1] > 0], key=lambda s: (-s[1], s[0]["key"]))
    active = scored[:max(0, int(capacity))]
    return {"sessionId": session_id, "taskId": task_id,
            "activeBeliefIds": [r["key"] for r, _ in active],
            "activeEntities": [{"entityType": r["entity_type"], "entityId": r["entity_id"]}
                               for r, _ in active],
            "capacity": int(capacity), "createdAt": now, "updatedAt": now}


# ---- Read API (GET only; snake_case wire matching src/lib/world/client.ts) ----

def _world_ensure_once():
    global _world_schema_ready
    if not _world_schema_ready:
        c = db()
        try:
            _ensure_world_schema(c)
        finally:
            c.close()


def _belief_to_wire(r, conn):
    ev = conn.execute("SELECT source_class, source_id, source_type, correlation_id, observed_at,"
                      " confidence, origin_ref, note FROM world_belief_evidence WHERE belief_key=?"
                      " AND superseded=0 ORDER BY id DESC", (r["key"],)).fetchall()
    contradicted = [c["conflict_ref"] for c in conn.execute(
        "SELECT conflict_ref FROM world_belief_conflict WHERE belief_key=? AND resolved_at IS NULL",
        (r["key"],)).fetchall()]
    return {
        "key": r["key"], "entity_type": r["entity_type"], "entity_id": r["entity_id"],
        "predicate": r["predicate"], "value": json.loads(r["value_json"]),
        "lifecycle_state": r["lifecycle_state"], "epistemic_state": r["epistemic_state"],
        "confidence": {"value": r["confidence"], "tier": r["confidence_tier"], "basis": r["confidence_basis"]},
        "provenance": [{"source_class": e["source_class"], "source_id": e["source_id"],
                        "source_type": e["source_type"], "correlation_id": e["correlation_id"],
                        "observed_at": e["observed_at"], "confidence": e["confidence"],
                        "origin_ref": e["origin_ref"], "note": e["note"]} for e in ev],
        "observed_at": r["observed_at"], "created_at": r["created_at"], "updated_at": r["updated_at"],
        "expires_at": r["expires_at"], "revision": r["revision"],
        "supersedes": [], "contradicted_by": contradicted,
    }


@app.get("/os/world")
def os_world(entity_type: str = None, entity_id: str = None,
             include_superseded: int = 0, limit: int = 200):
    _world_ensure_once()
    conn = _world_ro_conn()
    try:
        q, args = "SELECT * FROM world_belief WHERE 1=1", []
        if not include_superseded:
            q += " AND lifecycle_state != 'SUPERSEDED'"
        if entity_type:
            q += " AND entity_type=?"; args.append(entity_type)
        if entity_id:
            q += " AND entity_id=?"; args.append(str(entity_id))
        q += " ORDER BY entity_type, entity_id, predicate LIMIT ?"; args.append(int(limit))
        rows = conn.execute(q, args).fetchall()
        beliefs = [_belief_to_wire(r, conn) for r in rows]
        by_life, by_epi = {}, {}
        for r in conn.execute("SELECT lifecycle_state, epistemic_state, COUNT(*) c FROM world_belief"
                              " GROUP BY lifecycle_state, epistemic_state").fetchall():
            by_life[r["lifecycle_state"]] = by_life.get(r["lifecycle_state"], 0) + r["c"]
            by_epi[r["epistemic_state"]] = by_epi.get(r["epistemic_state"], 0) + r["c"]
        last = conn.execute("SELECT MAX(updated_at) m FROM world_belief").fetchone()["m"]
        meta = {"total": sum(by_life.values()), "by_lifecycle": by_life, "by_epistemic": by_epi,
                "conflicted": by_life.get("CONFLICTED", 0), "stale": by_life.get("STALE", 0),
                "last_reconciled_at": last}
        return {"beliefs": beliefs, "meta": meta}
    finally:
        conn.close()


@app.get("/os/world/{key}")
def os_world_key(key: str):
    _world_ensure_once()
    conn = _world_ro_conn()
    try:
        r = conn.execute("SELECT * FROM world_belief WHERE key=?", (key,)).fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="no belief for key")  # honest UNKNOWN
        return _belief_to_wire(r, conn)
    finally:
        conn.close()

# ============================================================================
# END SLICE 7 — WORLD MODEL + WORKING MEMORY (Phase B)
# ============================================================================


# ============================================================================
# BEGIN SLICE 7.1 — WORLD MODEL OPERATIONALIZATION  [additive; append-only]
# Automatic event-driven ingestion from career_events + scheduled freshness.
# Reuses Slice 7 primitives (submit_observation, world_freshness_sweep,
# _ensure_world_schema, _world_key, _wm_now, db, DB, json). No Slice 1-6 changes;
# no new HTTP mutation surface; no schema change to existing tables (adds one
# additive world_* table: world_ingest_cursor). NOT Goal/Executive/Workspace/
# Motivation/Ethics/Reasoning — pure maintenance of the existing belief store.
# ============================================================================

def _ensure_world_ingest_schema(conn):
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS world_ingest_cursor ("
        " name TEXT PRIMARY KEY, last_id INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);"
    )
    conn.commit()


def _world_cursor_get(conn, name):
    r = conn.execute("SELECT last_id FROM world_ingest_cursor WHERE name=?", (name,)).fetchone()
    return r["last_id"] if r else 0


def _world_cursor_set(conn, name, last_id):
    conn.execute(
        "INSERT INTO world_ingest_cursor (name, last_id, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(name) DO UPDATE SET last_id=excluded.last_id, updated_at=excluded.updated_at",
        (name, int(last_id), _wm_now()))


def _world_ingest_one(conn, entity_type, entity_id, predicate, value, prov):
    """Idempotent single-observation ingest. Skips when identical evidence for the
    same (belief_key, origin_ref, value) already exists (defence-in-depth beyond
    the cursor), and skips None values (unavailable field never overwrites).
    Returns True iff an observation was actually submitted."""
    if value is None:
        return False
    key = _world_key(entity_type, str(entity_id), predicate)
    origin = prov.get("origin_ref")
    vj = json.dumps(value, sort_keys=True, ensure_ascii=False)
    if origin:
        dup = conn.execute(
            "SELECT 1 FROM world_belief_evidence WHERE belief_key=? AND origin_ref=? AND value_json=? LIMIT 1",
            (key, origin, vj)).fetchone()
        if dup:
            return False
    submit_observation(entity_type, entity_id, predicate, value, conn=conn, **prov)
    return True


def world_ingest_from_events(limit=1000):
    """Event-driven World Model ingestion. Consumes NEW career_events (id > cursor)
    and refreshes the affected application beliefs from job_applications (the
    watcher's reconciled current state), then advances the cursor. Idempotent and
    restart-safe: the cursor marks progress; per-evidence dedup guarantees no
    duplicate evidence even if the same events are reprocessed after a crash before
    the cursor advanced. Never fabricates predicates; a missing application or NULL
    field is skipped, never written as an empty value."""
    conn = db()
    try:
        _ensure_world_schema(conn)
        _ensure_world_ingest_schema(conn)
        last = _world_cursor_get(conn, "career_events")
        events = conn.execute(
            "SELECT id, entity_type, entity_id, source, confidence, created_at "
            "FROM career_events WHERE id > ? ORDER BY id LIMIT ?", (last, limit)).fetchall()
        if not events:
            return {"new_events": 0, "beliefs_touched": 0, "cursor": last}
        max_id = last
        latest_evt = {}  # application id -> (event_id, source, confidence, created_at)
        for e in events:
            if e["id"] > max_id:
                max_id = e["id"]
            et = (e["entity_type"] or "").lower()
            if et in ("job_application", "application", "job_applications") and e["entity_id"] is not None:
                latest_evt[e["entity_id"]] = (e["id"], e["source"], e["confidence"], e["created_at"])
        touched = 0
        for aid, (evid, src, conf, cat) in latest_evt.items():
            row = conn.execute(
                "SELECT ja.id, ja.role_title, ja.stage, ja.last_activity, ja.source_account, "
                "c.name AS company FROM job_applications ja LEFT JOIN companies c ON c.id = ja.company_id "
                "WHERE ja.id=?", (aid,)).fetchone()
            if row is None:
                continue  # event referenced an application not present -> skip (no fabrication)
            prov = dict(source_type="career.application", source_id="career-events",
                        origin_ref="career_events/%s" % evid,
                        observed_at=cat or row["last_activity"],
                        correlation_id="evt_%s" % evid,
                        note=("acct" if row["source_account"] else None))
            for pred, val in (("status", row["stage"]), ("role", row["role_title"]),
                              ("company", row["company"]), ("last_activity", row["last_activity"])):
                if _world_ingest_one(conn, "career.application", aid, pred, val, prov):
                    touched += 1
        _world_cursor_set(conn, "career_events", max_id)
        conn.commit()
        return {"new_events": len(events), "beliefs_touched": touched, "cursor": max_id}
    finally:
        conn.close()


def _world_maint_tick():
    """One maintenance tick: event ingestion + freshness sweep. Each guarded so a
    failure in one step neither aborts the other nor corrupts the store."""
    out = {}
    try:
        out["ingest"] = world_ingest_from_events()
    except Exception as e:
        out["ingest_error"] = repr(e)
    try:
        out["sweep"] = world_freshness_sweep()
    except Exception as e:
        out["sweep_error"] = repr(e)
    return out


def _world_maintenance_loop():
    import os, time
    try:
        interval = max(15, int(_os.environ.get("WORLD_MAINT_INTERVAL_SEC", "120")))
    except Exception:
        interval = 120
    while True:
        res = _world_maint_tick()
        try:
            print("[world-maint] " + json.dumps(res), flush=True)
        except Exception:
            pass
        time.sleep(interval)


_world_maint_thread = None


@app.on_event("startup")
def _world_maint_start():
    """Start the in-process maintenance scheduler when the ASGI app starts (under
    uvicorn). Not started on a bare `import app`, so tests/one-offs never spawn it.
    Smallest production-compatible scheduler: a daemon thread inside the existing
    single-worker uvicorn process — no systemd/cron changes, restart-safe, and
    failures are visible in the service journal."""
    global _world_maint_thread
    if _world_maint_thread is not None:
        return
    import threading
    _world_maint_thread = threading.Thread(target=_world_maintenance_loop, name="world-maint", daemon=True)
    _world_maint_thread.start()
    print("[world-maint] scheduler started", flush=True)

# ============================================================================
# END SLICE 7.1 — WORLD MODEL OPERATIONALIZATION
# ============================================================================


# ============================================================================
# BEGIN SLICE 8 — GOAL / EXECUTIVE SYSTEM V1  [additive; append-only]
# Uses existing module globals: app, db, DB, sqlite3, json, re, datetime,
# timezone, HTTPException, _Body, _world_ro_conn (Slice 7). No changes to
# Slice 1-7.1 code above this marker.
#
# Executive decides WHAT should be pursued now. Planning (HOW) is out of scope.
# Goal != Task: the `tasks` table (Slice 3) is the execution substrate and is
# NOT touched here; a Goal is a durable continuity object that LINKS tasks/drafts
# and owns lifecycle + focus. Focus is DERIVED (never stored). Arbitration is
# deterministic (typed ranks; no LLM, no opaque scores).
#
# WORLD MODEL OWNERSHIP BOUNDARY (strict): this block READS beliefs only, via the
# read-only connection helper `_world_ro_conn()`. It NEVER calls, imports, or
# references any World Model belief-write or reconciliation helper. A conformance
# test asserts those mutation symbols are absent from this block. The Executive
# also invokes no external integration or tool, and performs no external send.
# ============================================================================

GOAL_SCHEMA_VERSION = 1

_GOAL_LIFECYCLE = (
    "PENDING", "ACTIVE", "BLOCKED", "SUSPENDED", "COMPLETED", "CANCELLED", "FAILED",
)
_GOAL_TERMINAL = frozenset(("COMPLETED", "CANCELLED", "FAILED"))
_GOAL_NONTERMINAL = frozenset(("PENDING", "ACTIVE", "BLOCKED", "SUSPENDED"))
_GOAL_SOURCES = ("USER_REQUESTED", "TASK_DERIVED", "SYSTEM_MAINTENANCE", "SCHEDULED")
_GOAL_PRIORITIES = ("URGENT", "HIGH", "NORMAL", "LOW")
_GOAL_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_GOAL_OP_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_MAX_GOAL_BYTES = 64 * 1024

# action -> (allowed_from_states, target_state, timestamp_column)
# Explicit, validated FSM. Terminal -> active never happens implicitly; the only
# terminal exit is `reopen` and it lands in PENDING (never directly ACTIVE).
_GOAL_ACTIONS = {
    "activate": (frozenset(("PENDING",)), "ACTIVE", "started_at"),
    "block":    (frozenset(("PENDING", "ACTIVE")), "BLOCKED", "blocked_at"),
    "unblock":  (frozenset(("BLOCKED",)), "ACTIVE", "started_at"),
    "suspend":  (frozenset(("ACTIVE",)), "SUSPENDED", "suspended_at"),
    "resume":   (frozenset(("SUSPENDED",)), "ACTIVE", "started_at"),
    "complete": (frozenset(("ACTIVE",)), "COMPLETED", "completed_at"),
    "fail":     (frozenset(("ACTIVE", "BLOCKED")), "FAILED", "failed_at"),
    "cancel":   (frozenset(("PENDING", "ACTIVE", "BLOCKED", "SUSPENDED")), "CANCELLED", "cancelled_at"),
    "reopen":   (frozenset(("COMPLETED", "CANCELLED", "FAILED")), "PENDING", None),
}

# Arbitration rank tables (lower = preferred). Deterministic + explainable.
_GOAL_LIFE_RANK = {"ACTIVE": 0, "PENDING": 1}
_GOAL_PRIO_RANK = {p: i for i, p in enumerate(_GOAL_PRIORITIES)}
_GOAL_SOURCE_RANK = {
    "USER_REQUESTED": 0, "TASK_DERIVED": 1, "SCHEDULED": 2, "SYSTEM_MAINTENANCE": 3,
}
# Ordered arbitration rules (index = precedence). Used for explainable traces.
_GOAL_ARB_RULES = ("lifecycle", "priority", "deadline", "source", "recency", "id")

_goal_schema_ready = False


def _goal_now():
    return datetime.now(timezone.utc).isoformat()


def _goal_log(op, **fields):
    """Structured, secret-free observability line (captured by journald)."""
    try:
        print("lilith.goals " + json.dumps({"op": op, **fields},
                                            separators=(",", ":")), flush=True)
    except Exception:
        pass


def _goals_db():
    """Open the shared DB and ensure the goal schema exists (idempotent inline
    bootstrap — production has no migration runner; mirrors tasks/drafts)."""
    global _goal_schema_ready
    conn = db()
    if not _goal_schema_ready:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS goal (
                goal_id           TEXT PRIMARY KEY,
                schema_version    INTEGER NOT NULL,
                type              TEXT NOT NULL,
                title             TEXT NOT NULL,
                description       TEXT,
                source            TEXT NOT NULL,
                owner             TEXT NOT NULL,
                lifecycle_state   TEXT NOT NULL,
                priority          TEXT NOT NULL,
                parent_goal_id    TEXT,
                linked_task_ids   TEXT NOT NULL DEFAULT '[]',
                target_json       TEXT,
                target_key        TEXT NOT NULL DEFAULT '',
                deadline          TEXT,
                blocked_reason    TEXT,
                blocked_by_json   TEXT,
                resume_conditions TEXT,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL,
                started_at        TEXT,
                blocked_at        TEXT,
                suspended_at      TEXT,
                completed_at      TEXT,
                cancelled_at      TEXT,
                failed_at         TEXT,
                provenance_json   TEXT,
                revision          INTEGER NOT NULL DEFAULT 1,
                last_operation_id TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_goal_lifecycle ON goal(lifecycle_state);
            CREATE INDEX IF NOT EXISTS idx_goal_parent ON goal(parent_goal_id);
            CREATE INDEX IF NOT EXISTS idx_goal_type ON goal(type);
            CREATE INDEX IF NOT EXISTS idx_goal_dedup ON goal(type, owner, target_key);
            CREATE TABLE IF NOT EXISTS goal_trace (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                correlation_id TEXT NOT NULL,
                goal_id        TEXT,
                at             TEXT NOT NULL,
                kind           TEXT NOT NULL,
                prior_state    TEXT,
                new_state      TEXT,
                action         TEXT,
                reason         TEXT NOT NULL,
                source         TEXT,
                arbitration_winner        TEXT,
                arbitration_alternatives_json TEXT,
                priority_inputs_json      TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_goal_trace_goal ON goal_trace(goal_id, at);
            CREATE INDEX IF NOT EXISTS idx_goal_trace_corr ON goal_trace(correlation_id);
            """
        )
        conn.commit()
        _goal_schema_ready = True
    return conn


def _goal_target_key(target):
    """Canonical dedup key for a typed target (sorted-keys JSON, '' when none)."""
    if not target or not isinstance(target, dict):
        return ""
    return json.dumps(target, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _goal_trace_insert(conn, correlation_id, goal_id, kind, reason,
                       prior_state=None, new_state=None, action=None, source=None,
                       arb_winner=None, arb_alternatives=None, priority_inputs=None):
    conn.execute(
        "INSERT INTO goal_trace (correlation_id, goal_id, at, kind, prior_state,"
        " new_state, action, reason, source, arbitration_winner,"
        " arbitration_alternatives_json, priority_inputs_json)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (correlation_id or ("g_" + _goal_now()), goal_id, _goal_now(), kind,
         prior_state, new_state, action, reason, source, arb_winner,
         json.dumps(arb_alternatives) if arb_alternatives is not None else None,
         json.dumps(priority_inputs) if priority_inputs is not None else None),
    )


def _row_to_goal(row):
    return {
        "goalId": row["goal_id"],
        "schemaVersion": row["schema_version"],
        "type": row["type"],
        "title": row["title"],
        "description": row["description"],
        "source": row["source"],
        "owner": row["owner"],
        "lifecycleState": row["lifecycle_state"],
        "priority": row["priority"],
        "parentGoalId": row["parent_goal_id"],
        "linkedTaskIds": json.loads(row["linked_task_ids"] or "[]"),
        "target": json.loads(row["target_json"]) if row["target_json"] else None,
        "deadline": row["deadline"],
        "blockedReason": row["blocked_reason"],
        "blockedBy": json.loads(row["blocked_by_json"]) if row["blocked_by_json"] else None,
        "resumeConditions": row["resume_conditions"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "startedAt": row["started_at"],
        "blockedAt": row["blocked_at"],
        "suspendedAt": row["suspended_at"],
        "completedAt": row["completed_at"],
        "cancelledAt": row["cancelled_at"],
        "failedAt": row["failed_at"],
        "provenance": json.loads(row["provenance_json"]) if row["provenance_json"] else None,
        "revision": row["revision"],
    }


def _goal_by_id(conn, goal_id):
    return conn.execute("SELECT * FROM goal WHERE goal_id=?", (goal_id,)).fetchone()


# ── World Model READ boundary (strict, read-only) ───────────────────────────
# The Executive may READ belief state to inform decisions. This helper uses the
# Slice-7 read-only connection (mode=ro) and only ever runs SELECT statements, so
# it is structurally incapable of mutating a belief. It must remain the ONLY way
# the Executive touches the World Model.

def _exec_read_beliefs(entity_type=None, entity_id=None):
    """Return current beliefs (read-only) for optional entity focus. Never writes."""
    try:
        conn = _world_ro_conn()
    except Exception:
        return []
    try:
        q = "SELECT key, entity_type, entity_id, predicate, value_json,"           " lifecycle_state, epistemic_state, confidence FROM world_belief"           " WHERE lifecycle_state != 'SUPERSEDED'"
        args = []
        if entity_type:
            q += " AND entity_type=?"; args.append(str(entity_type))
        if entity_id:
            q += " AND entity_id=?"; args.append(str(entity_id))
        rows = conn.execute(q, args).fetchall()
        out = []
        for r in rows:
            out.append({
                "key": r["key"], "entity_type": r["entity_type"],
                "entity_id": r["entity_id"], "predicate": r["predicate"],
                "value": json.loads(r["value_json"]),
                "lifecycle_state": r["lifecycle_state"],
                "epistemic_state": r["epistemic_state"],
                "confidence": r["confidence"],
            })
        return out
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _exec_world_conflicted(entity_type, entity_id):
    """True when any belief for this entity is CONFLICTED — the Executive must
    then block/escalate rather than silently progress (design §6)."""
    for b in _exec_read_beliefs(entity_type, entity_id):
        if b.get("lifecycle_state") == "CONFLICTED":
            return True
    return False


def _exec_unresolved_followups(conn, app_id):
    """Read-only: created (UNSENT) career_followup drafts for an application.
    Reuses the durable drafts substrate (Slice 4). Real blocker evidence for the
    application-14 duplicate-draft case."""
    try:
        rows = conn.execute(
            "SELECT draft_id FROM drafts WHERE target_type='application' AND"
            " target_id=? AND kind='career_followup' AND status='created'"
            " ORDER BY created_at", (str(app_id),)).fetchall()
        return [r["draft_id"] for r in rows]
    except sqlite3.OperationalError:
        return []


# ── Controlled create (with deterministic USER_REQUESTED de-dup) ────────────

def _goal_validate_create(payload):
    gtype = payload.get("type")
    title = payload.get("title")
    source = payload.get("source", "USER_REQUESTED")
    owner = payload.get("owner", "user")
    priority = payload.get("priority", "NORMAL")
    if not isinstance(gtype, str) or not gtype.strip():
        raise HTTPException(status_code=400, detail="type required")
    if not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=400, detail="title required")
    if source not in _GOAL_SOURCES:
        raise HTTPException(status_code=422, detail="invalid source")
    if priority not in _GOAL_PRIORITIES:
        raise HTTPException(status_code=422, detail="invalid priority")
    if not isinstance(owner, str) or not owner.strip():
        raise HTTPException(status_code=400, detail="owner required")
    sv = payload.get("schemaVersion", GOAL_SCHEMA_VERSION)
    if not isinstance(sv, int) or sv < 1:
        raise HTTPException(status_code=422, detail="invalid schemaVersion")
    if sv > GOAL_SCHEMA_VERSION:
        raise HTTPException(status_code=422, detail="unsupported schemaVersion %s" % sv)
    return gtype, title, source, owner, priority, sv


def _create_goal_impl(conn, payload):
    """Internal controlled create. Returns (goal_dict, created_bool). Applies the
    deterministic (type,target,owner) de-dup for USER_REQUESTED goals."""
    gtype, title, source, owner, priority, sv = _goal_validate_create(payload)
    operation_id = payload.get("operationId")
    target = payload.get("target")
    target_key = _goal_target_key(target)
    now = _goal_now()

    # Idempotent replay by operation_id (exact retry -> same row).
    if operation_id:
        prev = conn.execute(
            "SELECT * FROM goal WHERE last_operation_id=?", (operation_id,)).fetchone()
        if prev is not None:
            return _row_to_goal(prev), False

    # Deterministic semantic de-dup for USER_REQUESTED goals (design §4):
    # exact (type,target_key,owner) match among NON-TERMINAL goals.
    if source == "USER_REQUESTED":
        rows = conn.execute(
            "SELECT * FROM goal WHERE type=? AND owner=? AND target_key=? AND"
            " lifecycle_state IN ('PENDING','ACTIVE','BLOCKED','SUSPENDED')"
            " ORDER BY created_at", (gtype, owner, target_key)).fetchall()
        if len(rows) == 1:
            _goal_log("create.reused", goalId=rows[0]["goal_id"], type=gtype)
            return _row_to_goal(rows[0]), False
        if len(rows) > 1:
            ids = [r["goal_id"] for r in rows]
            _goal_log("create.reconciliation_required", type=gtype, count=len(ids))
            raise HTTPException(status_code=409, detail={
                "error": "reconciliation_required",
                "reason": "multiple equivalent non-terminal goals exist",
                "goalIds": ids})

    import uuid as _uuid
    goal_id = payload.get("goalId") or ("g." + _uuid.uuid4().hex)
    if not _GOAL_ID_RE.match(goal_id):
        raise HTTPException(status_code=400, detail="invalid goalId")
    corr = payload.get("correlationId") or ("g_" + now)
    provenance = {
        "source": source,
        "sourceChannel": payload.get("sourceChannel"),
        "correlationId": corr,
        "createdVia": payload.get("createdVia", "api"),
    }
    deadline = payload.get("deadline")  # only if genuinely provided; never invented
    conn.execute(
        "INSERT INTO goal (goal_id, schema_version, type, title, description, source,"
        " owner, lifecycle_state, priority, parent_goal_id, linked_task_ids,"
        " target_json, target_key, deadline, created_at, updated_at, provenance_json,"
        " revision, last_operation_id) VALUES (?,?,?,?,?,?,?, 'PENDING', ?,?, '[]',"
        " ?,?,?,?,?,?, 1, ?)",
        (goal_id, sv, gtype, title, payload.get("description"), source, owner,
         priority, payload.get("parentGoalId"),
         json.dumps(target) if target else None, target_key, deadline, now, now,
         json.dumps(provenance), operation_id),
    )
    _goal_trace_insert(conn, corr, goal_id, "transition", "goal_created",
                       prior_state=None, new_state="PENDING", action="create",
                       source=source)
    conn.commit()
    _goal_log("create", goalId=goal_id, type=gtype, source=source)
    stored = _goal_by_id(conn, goal_id)
    return _row_to_goal(stored), True


# ── Controlled transition (FSM-validated, revision-guarded, idempotent) ──────

def _goal_completion_block(conn, goal):
    """Evidence gate for `complete` (design §3 completion is evidence-based).
    Returns a human reason string when completion must be REFUSED, else None.
    Honest: a `career.followup` (a SEND objective) can never be system-completed
    because no send capability exists; a `career.prepare_followup` completes only
    when a durable follow-up draft actually exists for its target."""
    gtype = goal["type"]
    target = json.loads(goal["target_json"]) if goal["target_json"] else None
    app_id = (target or {}).get("id") if isinstance(target, dict) else None
    if gtype == "career.followup":
        return ("no send capability exists, so an external follow-up cannot be"
                " verified as sent — completion is not evidence-backed")
    if gtype == "career.prepare_followup":
        if not app_id:
            return "no target application to check for a prepared draft"
        drafts = _exec_unresolved_followups(conn, app_id)
        if not drafts:
            return "no prepared follow-up draft exists for the target yet"
        return None
    return None  # generic goals: no special evidence rule in V1


def _transition_goal_impl(conn, goal_id, payload):
    action = payload.get("action")
    operation_id = payload.get("operationId")
    expected_revision = payload.get("expectedRevision")
    row = _goal_by_id(conn, goal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="goal not found")
    # Idempotent replay: same operationId already applied -> no-op.
    if operation_id and row["last_operation_id"] == operation_id:
        _goal_log("transition.replay", goalId=goal_id, operationId=operation_id)
        return _row_to_goal(row), False
    if action not in _GOAL_ACTIONS:
        raise HTTPException(status_code=400, detail="unknown action")
    allowed_from, target_state, ts_col = _GOAL_ACTIONS[action]
    if expected_revision is not None and expected_revision != row["revision"]:
        raise HTTPException(status_code=409, detail={
            "error": "revision_conflict", "current": _row_to_goal(row),
            "revision": row["revision"]})
    cur_state = row["lifecycle_state"]
    if cur_state not in allowed_from:
        _goal_log("transition.illegal", goalId=goal_id,
                  **{"from": cur_state, "action": action})
        raise HTTPException(status_code=409, detail={
            "error": "illegal_transition", "from": cur_state, "action": action,
            "allowedFrom": sorted(allowed_from)})
    # Evidence-based completion gate.
    if action == "complete":
        block = _goal_completion_block(conn, row)
        if block:
            raise HTTPException(status_code=409, detail={
                "error": "evidence_required", "reason": block})
    now = _goal_now()
    corr = payload.get("correlationId") or ("g_" + now)
    reason = payload.get("reason") or ("action:" + action)
    new_rev = row["revision"] + 1

    sets = ["lifecycle_state=?", "updated_at=?", "revision=?", "last_operation_id=?"]
    args = [target_state, now, new_rev, operation_id or row["last_operation_id"]]
    if ts_col:
        sets.append(ts_col + "=?"); args.append(now)
    if action == "block":
        sets.append("blocked_reason=?"); args.append(payload.get("blockedReason") or reason)
        bb = payload.get("blockedBy")
        sets.append("blocked_by_json=?"); args.append(json.dumps(bb) if bb is not None else None)
        sets.append("resume_conditions=?"); args.append(payload.get("resumeConditions"))
    if action in ("unblock", "resume"):
        # Clear the blocker annotations on an explicit return to ACTIVE.
        sets.append("blocked_reason=?"); args.append(None)
        sets.append("blocked_by_json=?"); args.append(None)
        sets.append("resume_conditions=?"); args.append(payload.get("resumeConditions"))
    # Optimistic-concurrency guard: only lands if revision unchanged.
    args += [goal_id, row["revision"]]
    cur = conn.execute(
        "UPDATE goal SET " + ", ".join(sets) + " WHERE goal_id=? AND revision=?", args)
    if cur.rowcount == 0:
        conn.rollback()
        fresh = _goal_by_id(conn, goal_id)
        raise HTTPException(status_code=409, detail={
            "error": "revision_conflict", "current": _row_to_goal(fresh),
            "revision": fresh["revision"]})
    _goal_trace_insert(conn, corr, goal_id, "transition", reason,
                       prior_state=cur_state, new_state=target_state, action=action,
                       source=row["source"])
    conn.commit()
    _goal_log("transition", goalId=goal_id, action=action,
              **{"from": cur_state, "to": target_state, "revision": new_rev})
    return _row_to_goal(_goal_by_id(conn, goal_id)), True


def _goal_autoblock_followup(conn, goal_id):
    """Evidence-derived, traced auto-block for a career.followup goal whose target
    has >=2 unresolved (UNSENT) follow-up drafts — the real application-14 case.
    Deterministic; performs an explicit PENDING/ACTIVE -> BLOCKED transition with
    an explainable reason. Does NOT touch or delete the drafts."""
    row = _goal_by_id(conn, goal_id)
    if row is None or row["type"] != "career.followup":
        return None
    if row["lifecycle_state"] not in ("PENDING", "ACTIVE"):
        return None
    target = json.loads(row["target_json"]) if row["target_json"] else None
    app_id = (target or {}).get("id") if isinstance(target, dict) else None
    if not app_id:
        return None
    drafts = _exec_unresolved_followups(conn, app_id)
    if len(drafts) < 2:
        return None
    return _transition_goal_impl(conn, goal_id, {
        "action": "block",
        "reason": "duplicate_unsent_followup_drafts_require_reconciliation",
        "blockedReason": ("%d unresolved unsent follow-up drafts for application %s"
                          " require reconciliation before this goal can proceed"
                          % (len(drafts), app_id)),
        "blockedBy": ["draft:" + d for d in drafts],
        "resumeConditions": ("reconcile to a single unresolved follow-up draft for"
                             " application %s (keep one, discard the rest)" % app_id),
    })[0]


# ── Deterministic arbitration + derived focus (design §5) ───────────────────

def _goal_epoch(iso):
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _goal_sort_key(g):
    life = _GOAL_LIFE_RANK.get(g["lifecycle_state"], 9)
    prio = _GOAL_PRIO_RANK.get(g["priority"], 9)
    has_deadline = 0 if g["deadline"] else 1
    deadline = g["deadline"] or ""
    src = _GOAL_SOURCE_RANK.get(g["source"], 9)
    recency = -_goal_epoch(g["updated_at"])
    return (life, prio, has_deadline, deadline, src, recency, g["goal_id"])


def _goal_rule_values(g):
    return {
        "lifecycle": g["lifecycle_state"],
        "priority": g["priority"],
        "deadline": g["deadline"],
        "source": g["source"],
        "recency": g["updated_at"],
        "id": g["goal_id"],
    }


def _goal_first_distinguishing_rule(winner, loser):
    """Return the first arbitration rule (by precedence) whose comparison places
    winner strictly ahead of loser — the reason winner beats this loser."""
    wk = _goal_sort_key(winner)
    lk = _goal_sort_key(loser)
    for i, rule in enumerate(_GOAL_ARB_RULES):
        if wk[i] != lk[i]:
            return rule
    return "id"


def _arbitrate(conn):
    """Compute the single current-focus goal deterministically from durable rows.
    Candidates = ACTIVE or PENDING (BLOCKED/SUSPENDED/terminal excluded)."""
    rows = conn.execute(
        "SELECT * FROM goal WHERE lifecycle_state IN ('ACTIVE','PENDING')").fetchall()
    cands = sorted(rows, key=_goal_sort_key)
    if not cands:
        return {"focus": None, "candidates": [], "arbitration": {
            "winner": None, "ruleFired": None, "alternatives": [],
            "reason": "no active or pending goals"}}
    winner = cands[0]
    alternatives = []
    for l in cands[1:]:
        alternatives.append({
            "goalId": l["goal_id"],
            "eliminatedBy": _goal_first_distinguishing_rule(winner, l),
            "lifecycle": l["lifecycle_state"], "priority": l["priority"],
            "source": l["source"],
        })
    return {
        "focus": _row_to_goal(winner),
        "candidates": [_row_to_goal(c) for c in cands],
        "arbitration": {
            "winner": winner["goal_id"],
            "ruleFired": _GOAL_ARB_RULES[0],
            "priorityInputs": _goal_rule_values(winner),
            "alternatives": alternatives,
            "reason": ("deterministic rank over %s" % ", ".join(_GOAL_ARB_RULES)),
        },
    }


def _record_focus_trace(conn, result):
    """Write an arbitration trace only when the computed winner changes vs the
    last recorded arbitration winner (avoids trace spam; focus stays derived)."""
    winner = result["arbitration"]["winner"]
    last = conn.execute(
        "SELECT arbitration_winner FROM goal_trace WHERE kind='arbitration'"
        " ORDER BY id DESC LIMIT 1").fetchone()
    last_winner = last["arbitration_winner"] if last else None
    if winner != last_winner:
        _goal_trace_insert(
            conn, "g_arb_" + _goal_now(), winner, "arbitration",
            result["arbitration"]["reason"], arb_winner=winner,
            arb_alternatives=result["arbitration"]["alternatives"],
            priority_inputs=result["arbitration"].get("priorityInputs"))
        conn.commit()


# ── Read API (GET) ──────────────────────────────────────────────────────────

@app.get("/os/goals")
def list_goals(limit: int = 50, state: str = None, type: str = None, owner: str = None):
    limit = max(1, min(int(limit or 50), 200))
    conn = _goals_db()
    try:
        q = "SELECT * FROM goal"
        clauses, args = [], []
        if state:
            clauses.append("lifecycle_state=?"); args.append(state)
        if type:
            clauses.append("type=?"); args.append(type)
        if owner:
            clauses.append("owner=?"); args.append(owner)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(q, args).fetchall()
        return {"goals": [_row_to_goal(r) for r in rows], "count": len(rows),
                "schemaVersion": GOAL_SCHEMA_VERSION}
    finally:
        conn.close()


@app.get("/os/goals/focus")
def goal_focus():
    conn = _goals_db()
    try:
        result = _arbitrate(conn)
        _record_focus_trace(conn, result)
        return result
    finally:
        conn.close()


@app.get("/os/goals/{goal_id}")
def get_goal(goal_id: str):
    if not _GOAL_ID_RE.match(goal_id or ""):
        raise HTTPException(status_code=400, detail="invalid goalId")
    conn = _goals_db()
    try:
        row = _goal_by_id(conn, goal_id)
        if row is None:
            raise HTTPException(status_code=404, detail="goal not found")
        return {"goal": _row_to_goal(row)}
    finally:
        conn.close()


# ── Controlled write API (typed operations; NO generic setGoal/setState) ────

@app.post("/os/goals")
def post_goal(payload: dict = _Body(default=None)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    conn = _goals_db()
    try:
        goal, created = _create_goal_impl(conn, payload)
        # Optional evidence-derived auto-block for career.followup (design §12):
        # reflects the REAL duplicate-draft blocker; explicit + traced, drafts
        # untouched. Only when the caller asks (the cognitive lane sets this).
        if created and payload.get("evaluateBlock") and goal["type"] == "career.followup":
            blocked = _goal_autoblock_followup(conn, goal["goalId"])
            if blocked is not None:
                goal = blocked
        return {"goal": goal, "created": created}
    finally:
        conn.close()


@app.post("/os/goals/{goal_id}/transition")
def post_goal_transition(goal_id: str, payload: dict = _Body(default=None)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    if not _GOAL_ID_RE.match(goal_id or ""):
        raise HTTPException(status_code=400, detail="invalid goalId")
    op = payload.get("operationId")
    if op is not None and not _GOAL_OP_RE.match(str(op)):
        raise HTTPException(status_code=400, detail="invalid operationId")
    conn = _goals_db()
    try:
        goal, applied = _transition_goal_impl(conn, goal_id, payload)
        return {"goal": goal, "applied": applied}
    finally:
        conn.close()


@app.post("/os/goals/{goal_id}/link_task")
def post_goal_link_task(goal_id: str, payload: dict = _Body(default=None)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    if not _GOAL_ID_RE.match(goal_id or ""):
        raise HTTPException(status_code=400, detail="invalid goalId")
    task_id = payload.get("taskId")
    operation_id = payload.get("operationId")
    if not isinstance(task_id, str) or not _TASK_ID_RE.match(task_id):
        raise HTTPException(status_code=400, detail="invalid taskId")
    conn = _goals_db()
    try:
        row = _goal_by_id(conn, goal_id)
        if row is None:
            raise HTTPException(status_code=404, detail="goal not found")
        if operation_id and row["last_operation_id"] == operation_id:
            return {"goal": _row_to_goal(row), "applied": False}
        # Validate the task exists (read-only; tasks table is NOT mutated here).
        texists = conn.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if texists is None:
            raise HTTPException(status_code=404, detail="task not found")
        links = json.loads(row["linked_task_ids"] or "[]")
        if task_id in links:
            return {"goal": _row_to_goal(row), "applied": False}
        links.append(task_id)
        now = _goal_now()
        new_rev = row["revision"] + 1
        conn.execute(
            "UPDATE goal SET linked_task_ids=?, updated_at=?, revision=?,"
            " last_operation_id=? WHERE goal_id=? AND revision=?",
            (json.dumps(links), now, new_rev, operation_id or row["last_operation_id"],
             goal_id, row["revision"]))
        _goal_trace_insert(conn, "g_" + now, goal_id, "transition",
                           "task_linked:" + task_id, prior_state=row["lifecycle_state"],
                           new_state=row["lifecycle_state"], action="link_task",
                           source=row["source"])
        conn.commit()
        _goal_log("link_task", goalId=goal_id, taskId=task_id)
        return {"goal": _row_to_goal(_goal_by_id(conn, goal_id)), "applied": True}
    finally:
        conn.close()

# ============================================================================
# END SLICE 8 — GOAL / EXECUTIVE SYSTEM V1
# ============================================================================
