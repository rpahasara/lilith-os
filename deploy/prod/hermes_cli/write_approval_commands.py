#!/usr/bin/env python3
"""Shared handlers for the /memory and /skills write-approval subcommands.

Both the interactive CLI (``cli.py``) and the gateway (``gateway/run.py``) call
into this module so the pending-review UX (list / approve / reject / diff /
mode) lives in one place. Each caller owns only its surface concerns:
formatting the returned text and, for the gateway, persisting config + evicting
the cached agent on a mode change.

Every public handler returns a plain text string suitable for both a terminal
and a chat message. Skill diffs are intentionally NOT inlined here — the
``diff`` handler returns the full diff for the CLI pager, but on a messaging
platform the gateway truncates it and points the user at the dashboard / file.
"""

from __future__ import annotations

import json
from typing import List, Optional

from tools import write_approval as wa


# ---------------------------------------------------------------------------
# LILITH OS first (owner decision 2026-11-06)
# ---------------------------------------------------------------------------
# An approved memory is recorded in LILITH OS's World Model (POST /os/owner-memory on the local Core API) BEFORE
# Hermes applies it to USER.md / MEMORY.md, which are now projections. If LILITH OS cannot record it, the approval
# stops and the proposal stays pending, so nothing is reported as saved that is not durable; a retry is safe because
# the endpoint is idempotent per proposal. A rejection is logged so the nightly review never proposes it again.

import datetime as _dt
import hashlib as _hashlib
import os as _os
import urllib.error as _urlerror
import urllib.request as _urlrequest
from pathlib import Path as _Path

_LILITH_API = _os.environ.get("LILITH_OS_API_URL", "http://127.0.0.1:8765")
_LILITH_DELIM = "\n§\n"
_LILITH_FILES = {"user": "USER.md", "memory": "MEMORY.md"}


class _LilithNotSaved(Exception):
    pass


def _lilith_home() -> _Path:
    return _Path(_os.environ.get("HERMES_HOME") or _Path.home() / ".hermes")


def _lilith_norm(text) -> str:
    return " ".join(str(text).split())


def lilith_memory_id(store: str, text: str) -> str:
    """The Core API's owner_memory_id: the same store + text is always the same memory."""
    return "om_" + _hashlib.sha256((store + "\n" + _lilith_norm(text)).encode("utf-8")).hexdigest()[:20]


def _lilith_post(body: dict) -> dict:
    req = _urlrequest.Request(_LILITH_API + "/os/owner-memory", data=json.dumps(body).encode("utf-8"),
                              method="POST", headers={"Content-Type": "application/json"})
    try:
        with _urlrequest.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except _urlerror.HTTPError as exc:
        raise _LilithNotSaved("LILITH OS refused (%s)" % exc.code) from exc
    except (_urlerror.URLError, OSError, ValueError) as exc:
        raise _LilithNotSaved("LILITH OS unreachable (%s)" % type(exc).__name__) from exc


def _lilith_entries(store: str) -> list:
    try:
        raw = (_lilith_home() / "memories" / _LILITH_FILES[store]).read_text(encoding="utf-8")
    except OSError:
        return []
    return [e.strip() for e in raw.split(_LILITH_DELIM) if e.strip()]


def _lilith_one_entry(entries: list, old_text: str) -> str:
    matches = [e for e in entries if old_text and old_text in e]
    if len(matches) != 1:
        raise _LilithNotSaved("the entry to change is %s" % ("ambiguous" if matches else "not in memory"))
    return matches[0]


def lilith_record_approval(rec: dict, post=None, now=None) -> None:
    """Record every write of one approved proposal in LILITH OS, or raise _LilithNotSaved (nothing is lost)."""
    post = post or _lilith_post
    payload = rec.get("payload") or {}
    pid = str(rec.get("id"))
    target = payload.get("target", "memory")
    ops = payload.get("operations") if payload.get("action") == "batch" else [payload]
    stamp = (now or _dt.datetime.now(_dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    prov = {"kind": "OWNER_APPROVED_PROPOSAL", "proposal_id": pid, "approved_at": stamp,
            "note": "approved with /memory approve"}
    working = {s: _lilith_entries(s) for s in _LILITH_FILES}
    for op in ops or []:
        action = op.get("action")
        store = op.get("target") or target
        if store not in _LILITH_FILES:
            raise _LilithNotSaved("unknown memory target %r" % store)
        content, old_text = op.get("content") or "", op.get("old_text") or ""
        if action == "add":
            post({"store": store, "text": content, "provenance": prov})
            working[store].append(content)
        elif action == "replace":
            old = _lilith_one_entry(working[store], old_text)
            body = {"store": store, "text": content, "provenance": prov, "supersedes": [lilith_memory_id(store, old)]}
            try:
                post(body)
            except _LilithNotSaved as exc:
                if "(409)" not in str(exc):
                    raise
                # the replaced entry was never recorded (hand-written in Hermes): record it truthfully, then replace
                post({"store": store, "text": old, "provenance": {
                    "kind": "HERMES_PREEXISTING_IMPORT", "note": "present in Hermes when replaced by %s" % pid}})
                post(body)
            working[store] = [content if e == old else e for e in working[store]]
        elif action == "remove":
            old = _lilith_one_entry(working[store], old_text)
            try:
                post({"action": "retract", "store": store, "entry_id": lilith_memory_id(store, old), "provenance": prov})
            except _LilithNotSaved as exc:
                if "(409)" not in str(exc):       # 409: never recorded in LILITH OS, so nothing to retract
                    raise
            working[store] = [e for e in working[store] if e != old]
        else:
            raise _LilithNotSaved("unknown memory action %r" % action)


def _lilith_event_post(body: dict) -> None:
    req = _urlrequest.Request(_LILITH_API + "/os/learning-events", data=json.dumps(body).encode("utf-8"),
                              method="POST", headers={"Content-Type": "application/json"})
    with _urlrequest.urlopen(req, timeout=10) as resp:
        resp.read()


def lilith_log_rejection(rec: dict) -> None:
    """Remember a rejected proposal so it is never proposed again: an L18 REJECTED event in LILITH OS, plus a local
    log (memory-review/rejected.jsonl) as the fallback when LILITH OS is unreachable."""
    payload = rec.get("payload") or {}
    target = payload.get("target", "memory")
    ops = payload.get("operations") if payload.get("action") == "batch" else [payload]
    items = [{"store": o.get("target") or target, "action": o.get("action"),
              "text": o.get("content") or o.get("old_text")} for o in ops or []
             if isinstance(o, dict) and (o.get("content") or o.get("old_text"))]
    try:
        if items:
            _lilith_event_post({"kind": "REJECTED", "proposal_id": str(rec.get("id")), "items": items, "source": "hermes"})
    except Exception:
        pass
    try:
        path = _lilith_home() / "memory-review" / "rejected.jsonl"
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": rec.get("id"), "rejected_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                                "contents": [o.get("content") for o in ops or [] if isinstance(o, dict) and o.get("content")]},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass


def _fmt_state(subsystem: str) -> str:
    on = wa.write_approval_enabled(subsystem)
    return f"{subsystem}.write_approval = {'on' if on else 'off'}"


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_pending_list(subsystem: str) -> str:
    records = wa.list_pending(subsystem)
    if not records:
        return f"No pending {subsystem} writes."
    lines = [f"Pending {subsystem} writes ({len(records)}):"]
    for r in records:
        origin = r.get("origin", "foreground")
        tag = " [auto]" if origin == "background_review" else ""
        lines.append(f"  {r['id']}{tag}  {r.get('summary', '')}")
    where = "/{s} approve <id>".format(s=subsystem)
    lines.append("")
    lines.append(f"Apply: {where}   Reject: /{subsystem} reject <id>")
    if subsystem == wa.SKILLS:
        lines.append("Review full diff: /skills diff <id>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Subcommand dispatch
# ---------------------------------------------------------------------------

def handle_pending_subcommand(
    subsystem: str,
    args: List[str],
    *,
    memory_store=None,
    set_mode_fn=None,
) -> Optional[str]:
    """Dispatch a /memory or /skills subcommand.

    Args:
        subsystem: ``memory`` or ``skills``.
        args: tokens after the slash command (e.g. ``["approve", "a1b2"]``).
        memory_store: live MemoryStore for applying approved memory writes
            (CLI passes ``self.agent._memory_store``; gateway applies against a
            freshly loaded store).
        set_mode_fn: optional callable ``(enabled: bool) -> None`` that
            persists the new write_approval boolean to config (gateway provides
            this; CLI uses its own ``save_config_value`` and passes a closure).

    Returns a text string to show the user. Returns None when the args are not
    a write-approval subcommand (caller falls through to its other handling,
    e.g. /skills search).
    """
    if not args:
        # Bare /memory or /skills with no sub → show pending + gate state.
        return f"{_fmt_state(subsystem)}\n\n" + _fmt_pending_list(subsystem)

    sub = args[0].lower()
    rest = args[1:]

    if sub == "pending":
        return _fmt_pending_list(subsystem)

    if sub in {"approve", "apply"}:
        return _approve(subsystem, rest, memory_store)

    if sub in {"reject", "deny", "drop"}:
        return _reject(subsystem, rest)

    if sub == "diff" and subsystem == wa.SKILLS:
        return _diff(rest)

    if sub in {"approval", "mode"}:  # 'mode' kept as a back-compat alias
        return _set_approval(subsystem, rest, set_mode_fn)

    return None  # not ours — caller handles


def _resolve_one(subsystem: str, rest: List[str]):
    if not rest:
        return None, f"Usage: /{subsystem} approve|reject <id>  (or 'all')"
    return rest[0], None


def _approve(subsystem: str, rest: List[str], memory_store) -> str:
    target, err = _resolve_one(subsystem, rest)
    if err or target is None:
        return err or f"Usage: /{subsystem} approve <id>"

    records = wa.list_pending(subsystem)
    if not records:
        return f"No pending {subsystem} writes."

    if target.lower() == "all":
        targets = list(records)
    else:
        rec = wa.get_pending(subsystem, target)
        if not rec:
            return f"No pending {subsystem} write with id '{target}'."
        targets = [rec]

    applied, failed, notes = 0, [], []
    for rec in targets:
        if subsystem == wa.MEMORY:
            try:
                lilith_record_approval(rec)            # LILITH OS first; Hermes files are the projection
            except _LilithNotSaved as exc:
                failed.append(f"{rec['id']}: not saved: {exc}. It is still pending; try /memory approve {rec['id']} again")
                continue
        ok, msg = _apply_one(subsystem, rec, memory_store)
        if ok:
            wa.discard_pending(subsystem, rec["id"])
            applied += 1
        elif subsystem == wa.MEMORY:
            # durable in LILITH OS already: the Hermes copy is repaired by the sync job, so do not keep it pending
            wa.discard_pending(subsystem, rec["id"])
            applied += 1
            notes.append(f"{rec['id']}: saved in LILITH OS; the Hermes copy will be repaired ({msg})")
        else:
            failed.append(f"{rec['id']}: {msg}")

    out = [f"Approved {applied} {subsystem} write(s)."]
    out.extend(notes)
    if failed:
        out.append("Failed:")
        out.extend(f"  {f}" for f in failed)
    return "\n".join(out)


def _apply_one(subsystem: str, rec, memory_store):
    payload = rec.get("payload", {})
    try:
        if subsystem == wa.MEMORY:
            if memory_store is None:
                return False, "memory store unavailable"
            from tools.memory_tool import apply_memory_pending
            result = apply_memory_pending(payload, memory_store)
            return bool(result.get("success")), result.get("error", "")
        else:
            from tools.skill_manager_tool import apply_skill_pending
            result = json.loads(apply_skill_pending(payload))
            return bool(result.get("success")), result.get("error", "")
    except Exception as e:
        return False, str(e)


def _reject(subsystem: str, rest: List[str]) -> str:
    target, err = _resolve_one(subsystem, rest)
    if err or target is None:
        return err or f"Usage: /{subsystem} reject <id>"
    if target.lower() == "all":
        n = 0
        for rec in wa.list_pending(subsystem):
            if subsystem == wa.MEMORY:
                lilith_log_rejection(rec)
            if wa.discard_pending(subsystem, rec["id"]):
                n += 1
        return f"Rejected {n} pending {subsystem} write(s)."
    if subsystem == wa.MEMORY:
        rec = wa.get_pending(subsystem, target)
        if rec:
            lilith_log_rejection(rec)
    if wa.discard_pending(subsystem, target):
        return f"Rejected pending {subsystem} write '{target}'."
    return f"No pending {subsystem} write with id '{target}'."


def _diff(rest: List[str]) -> str:
    if not rest:
        return "Usage: /skills diff <id>"
    rec = wa.get_pending(wa.SKILLS, rest[0])
    if not rec:
        return f"No pending skill write with id '{rest[0]}'."
    diff = wa.skill_pending_diff(rec)
    header = f"# Pending skill write {rec['id']}: {rec.get('summary', '')}\n"
    return header + "\n" + diff


def _set_approval(subsystem: str, rest: List[str], set_mode_fn) -> str:
    """Turn the approval gate on/off for a subsystem.

    ``set_mode_fn`` (when provided) persists the new boolean to config.
    """
    if not rest:
        return (f"{_fmt_state(subsystem)}\n"
                f"Set with: /{subsystem} approval <on|off>")
    arg = rest[0].strip().lower()
    truthy = {"on", "true", "yes", "1", "enable", "enabled"}
    falsey = {"off", "false", "no", "0", "disable", "disabled"}
    if arg in truthy:
        enabled = True
    elif arg in falsey:
        enabled = False
    else:
        return f"Invalid value '{arg}'. Use: on or off."
    if set_mode_fn is None:
        val = "true" if enabled else "false"
        return (f"To change the {subsystem} approval gate, run:\n"
                f"  hermes config set {subsystem}.write_approval {val}")
    try:
        set_mode_fn(enabled)
    except Exception as e:
        return f"Failed to set {subsystem}.write_approval: {e}"
    return f"{subsystem}.write_approval set to '{'on' if enabled else 'off'}'."
