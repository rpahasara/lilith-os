"""Bounded one-shot Slice 15A shadow worker.

The worker is manually invoked.  It has no daemon loop, model/tool access,
connector path, prompt integration, retrieval consumer, or canonical-memory
apply behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    from . import config as router_config
    from . import learning
    from . import learning_store as store_module
    from . import memory_contracts as C
except ImportError:  # deploy-exact flat-directory tests
    try:
        import config as router_config
    except ImportError:
        router_config = None
    import learning
    import learning_store as store_module
    import memory_contracts as C


TRACE_LANE = "memory_consolidation"
MODE_SHADOW = "SHADOW"
DEFAULT_BATCH_RECORDS = 10


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


def default_source_db() -> Path:
    return _hermes_home() / "lilith-os" / "data" / "lilith.db"


def default_learning_db() -> Path:
    return _hermes_home() / "lilith-os" / "data" / "cognitive_memory.db"


def _safe_trace(path: Path, trace: Dict[str, Any]) -> None:
    """Append one bounded metadata-only record to the existing Router log."""
    allowed = {
        "lane", "jobId", "sourceOwner", "sourceStream", "sourceCount",
        "candidateCount", "validationCounts", "assessmentCounts", "cursorFrom",
        "cursorThrough", "idempotentReplayCount", "failureCode", "durationMs",
        "mode", "schemaVersion", "timestamp",
    }
    if set(trace) - allowed:
        raise ValueError("trace contains unsupported fields")
    encoded = json.dumps(trace, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    if len(encoded.encode("ascii")) > 4096:
        raise ValueError("trace exceeds safe bound")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, (encoded + "\n").encode("ascii"))
    finally:
        os.close(descriptor)


def _trace_path(cfg: Any) -> Path:
    resolver = getattr(cfg, "resolved_log_path", None)
    if callable(resolver):
        return Path(resolver())
    return _hermes_home() / "lilith_router" / "decisions.log"


def _worker_active(cfg: Any) -> bool:
    return bool(getattr(cfg, "memory_consolidation_enabled", False)) and (
        str(getattr(cfg, "memory_consolidation_mode", "shadow")).strip().lower() == "shadow"
    )


def _disabled_result(cfg: Any) -> Dict[str, Any]:
    enabled = bool(getattr(cfg, "memory_consolidation_enabled", False))
    mode = str(getattr(cfg, "memory_consolidation_mode", "shadow")).strip().lower()
    return {
        "status": "DISABLED" if not enabled else "DISABLED_UNSUPPORTED_MODE",
        "mode": mode.upper() if mode else "UNSUPPORTED",
        "ledgerMutation": False,
    }


def _emit_best_effort(cfg: Any, trace: Dict[str, Any]) -> None:
    try:
        _safe_trace(_trace_path(cfg), trace)
    except Exception:
        # Existing Router trace behavior is fail-open; an operational log failure
        # cannot reinterpret or retry durable Learning state.
        pass


def run_once(
    *,
    source_db: Path,
    learning_db: Path,
    cfg: Optional[Any] = None,
    limit: int = DEFAULT_BATCH_RECORDS,
    worker_id: Optional[str] = None,
    lease_seconds: int = store_module.DEFAULT_LEASE_SECONDS,
    capacity: int = store_module.DEFAULT_LEDGER_CAPACITY,
    now_fn: Callable[[], str] = store_module.utc_now,
    fault_hook: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Run at most one bounded source batch and return metadata only."""
    if cfg is None and router_config is None:
        raise RuntimeError("Router config is required outside the deployed package")
    settings = cfg if cfg is not None else router_config.load()
    if not _worker_active(settings):
        return _disabled_result(settings)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= learning.MAX_BATCH_RECORDS:
        return {"status": "FAILED", "failureCode": "SOURCE_TOO_LARGE", "ledgerMutation": False}

    started = time.monotonic()
    now = now_fn()
    ledger = store_module.LearningStore(Path(learning_db), capacity=capacity)
    worker = worker_id or f"manual.{uuid.uuid4().hex}"
    try:
        job = ledger.lease_job(worker, now, lease_seconds=lease_seconds)
    except store_module.SchemaError:
        return {"status": "FAILED", "failureCode": "SOURCE_SCHEMA_MISMATCH", "ledgerMutation": False}
    except (sqlite3.Error, store_module.LearningStoreError):
        return {"status": "FAILED", "failureCode": "DB_BUSY", "ledgerMutation": False}

    job_id = str(job["job_id"])
    lease_token = str(job["lease_token"])
    cursor_from = int(job["cursor_from"])
    validation_counts: Counter[str] = Counter()
    assessment_counts: Counter[str] = Counter()
    source_count = 0

    try:
        rows = learning.CareerEventsSource(Path(source_db)).read_batch(cursor_from, limit)
        source_count = len(rows)
        if fault_hook:
            fault_hook("after_source_read")

        processed = []
        for row in rows:
            source_ref, descriptor = learning.build_source_record_ref(row)
            candidate = learning.derive_candidate(source_ref, descriptor, now)
            validation = learning.validate_candidate(candidate)
            validation_counts[validation.state] += 1
            if validation.state != C.VALID:
                raise learning.InvalidSourceRecord("deterministic candidate failed validation")
            assessment = learning.assess_candidate(candidate, validation, now)
            assessment_counts[assessment.outcome] += 1
            processed.append((candidate, source_ref, assessment))

        cursor_through = int(rows[-1]["id"]) if rows else cursor_from
        if fault_hook:
            fault_hook("before_ledger_commit")
        committed_at = now_fn()
        result = ledger.commit_batch(
            job_id, lease_token, processed, cursor_through, committed_at,
        )
        if fault_hook:
            fault_hook("after_ledger_commit")
        trace = {
            "lane": TRACE_LANE,
            "jobId": job_id,
            "sourceOwner": C.SOURCE_OWNER,
            "sourceStream": C.SOURCE_STREAM,
            "sourceCount": source_count,
            "candidateCount": len(processed),
            "validationCounts": dict(sorted(validation_counts.items())),
            "assessmentCounts": dict(sorted(assessment_counts.items())),
            "cursorFrom": cursor_from,
            "cursorThrough": cursor_through,
            "idempotentReplayCount": int(result["replayed"]),
            "failureCode": None,
            "durationMs": max(0, int((time.monotonic() - started) * 1000)),
            "mode": MODE_SHADOW,
            "schemaVersion": C.SCHEMA_VERSION,
            "timestamp": committed_at,
        }
        _emit_best_effort(settings, trace)
        return {
            "status": "SUCCEEDED",
            "jobId": job_id,
            "sourceCount": source_count,
            "candidateCount": len(processed),
            "insertedCount": int(result["inserted"]),
            "idempotentReplayCount": int(result["replayed"]),
            "cursorFrom": cursor_from,
            "cursorThrough": cursor_through,
            "mode": MODE_SHADOW,
            "canonicalMemoryMutation": False,
        }
    except (learning.LearningSourceError, store_module.CapacityPaused) as exc:
        code = getattr(exc, "code", "INVALID_SOURCE_RECORD")
        retryable = bool(getattr(exc, "retryable", False))
        failed_at = now_fn()
        try:
            status = ledger.fail_job(job_id, lease_token, code, retryable, failed_at)
        except store_module.LeaseLost:
            code = "LEASE_LOST"
            status = store_module.FAILED_TERMINAL
        trace = {
            "lane": TRACE_LANE,
            "jobId": job_id,
            "sourceOwner": C.SOURCE_OWNER,
            "sourceStream": C.SOURCE_STREAM,
            "sourceCount": source_count,
            "candidateCount": 0,
            "validationCounts": dict(sorted(validation_counts.items())),
            "assessmentCounts": dict(sorted(assessment_counts.items())),
            "cursorFrom": cursor_from,
            "cursorThrough": None,
            "idempotentReplayCount": 0,
            "failureCode": code,
            "durationMs": max(0, int((time.monotonic() - started) * 1000)),
            "mode": MODE_SHADOW,
            "schemaVersion": C.SCHEMA_VERSION,
            "timestamp": failed_at,
        }
        _emit_best_effort(settings, trace)
        return {
            "status": status,
            "jobId": job_id,
            "failureCode": code,
            "cursorFrom": cursor_from,
            "mode": MODE_SHADOW,
            "canonicalMemoryMutation": False,
        }
    except store_module.LeaseLost:
        return {
            "status": "FAILED_TERMINAL",
            "jobId": job_id,
            "failureCode": "LEASE_LOST",
            "canonicalMemoryMutation": False,
        }
    except store_module.LearningStoreError as exc:
        code = getattr(exc, "code", "DB_BUSY")
        failed_at = now_fn()
        try:
            status = ledger.fail_job(job_id, lease_token, code, False, failed_at)
        except Exception:
            status = store_module.FAILED_TERMINAL
        return {
            "status": status,
            "jobId": job_id,
            "failureCode": code,
            "canonicalMemoryMutation": False,
        }
    except sqlite3.OperationalError:
        failed_at = now_fn()
        try:
            status = ledger.fail_job(job_id, lease_token, "DB_BUSY", True, failed_at)
        except Exception:
            status = store_module.FAILED_TERMINAL
        return {
            "status": status,
            "jobId": job_id,
            "failureCode": "DB_BUSY",
            "canonicalMemoryMutation": False,
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Slice 15A one-shot shadow worker")
    sub = parser.add_subparsers(dest="command", required=True)
    migrate_cmd = sub.add_parser("migrate", help="create or verify the L18 ledger schema")
    migrate_cmd.add_argument("--learning-db", type=Path, default=default_learning_db())
    run_cmd = sub.add_parser("run", help="process one bounded shadow batch")
    run_cmd.add_argument("--source-db", type=Path, default=default_source_db())
    run_cmd.add_argument("--learning-db", type=Path, default=default_learning_db())
    run_cmd.add_argument("--limit", type=int, default=DEFAULT_BATCH_RECORDS)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "migrate":
        fingerprint = store_module.migrate(args.learning_db)
        print(json.dumps({
            "status": "MIGRATED",
            "schemaVersion": store_module.SCHEMA_VERSION,
            "schemaFingerprint": fingerprint,
        }, sort_keys=True))
        return 0
    result = run_once(
        source_db=args.source_db,
        learning_db=args.learning_db,
        limit=args.limit,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in {"SUCCEEDED", "DISABLED", "DISABLED_UNSUPPORTED_MODE"} else 1


if __name__ == "__main__":
    sys.exit(main())
