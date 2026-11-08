#!/usr/bin/env python3
"""Mirror owner-approved Hermes memories into LILITH OS's World Model (POST /os/owner-memory, loopback). Compatibility
batch 1, 2026-11-06: Hermes still writes USER.md / MEMORY.md; LILITH OS keeps the durable record.

Rules (owner decisions 2026-11-06):
- First run: BOOTSTRAP gives the entries approved on 2026-11-06 their real proposal ids; every other entry present then
  is imported as HERMES_PREEXISTING_IMPORT (no approval time is invented).
- Afterwards an entry is synced only when an owner-approved proposal for it is on record (memory-review/seen.jsonl):
  it is no longer pending and its text is in the file. Pending, rejected or unattributed entries are never synced.
- An approved replace supersedes the old entry; an approved removal retracts it. An entry that merely disappears from
  a Hermes file is left alone (logged as missing), never retracted.
State: memory-review/world_sync.json (normalised text -> entry id). Prints nothing on success (silent cron job).
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
API = os.environ.get("LILITH_OS_API_URL", "http://127.0.0.1:8765")
STATE = "memory-review/world_sync.json"
SEEN = "memory-review/seen.jsonl"
SEP = "\n§\n"
FILES = (("user", "USER.md"), ("memory", "MEMORY.md"))

# Entries approved on 2026-11-06 before proposal snapshots existed. approved_at = the observed write time of USER.md
# when the owner approved (verified that day); the old Sara line was the pre-existing entry 6e64c725 replaced.
BOOTSTRAP = [
    {"store": "user", "text": "User prefers to be called Sara; he is a boy and uses he/him language.",
     "provenance": {"kind": "HERMES_PREEXISTING_IMPORT", "note": "pre-existing Hermes USER.md entry; replaced on 2026-11-06"}},
    {"store": "user",
     "text": "User's real name is Ravindu. Friends call him Sara, pronounced with a long “aa” sound at the end; "
             "both Ravindu and Sara refer to him, and he uses he/him language.",
     "provenance": {"kind": "OWNER_APPROVED_PROPOSAL", "proposal_id": "6e64c725", "approved_at": "2026-11-06T18:32:52Z",
                    "channel": "telegram_owner_dm", "note": "in-chat proposal; approved_at = USER.md write time"},
     "supersedes_text": "User prefers to be called Sara; he is a boy and uses he/him language."},
    {"store": "user",
     "text": "User prefers LILITH OS development progress reviews in three short sections: What's Done, "
             "What's Broken, and What's Next.",
     "provenance": {"kind": "OWNER_APPROVED_PROPOSAL", "proposal_id": "32b0ef1e", "approved_at": "2026-11-06T19:37:52Z",
                    "channel": "telegram_owner_dm", "note": "nightly-review proposal; approved_at = USER.md write time"}},
]


def norm(text: str) -> str:
    return " ".join(str(text).split())


def entries(home: Path) -> list:
    out = []
    for store, name in FILES:
        try:
            raw = (home / "memories" / name).read_text(encoding="utf-8")
        except OSError:
            continue
        out += [(store, e.strip()) for e in raw.split(SEP) if e.strip()]
    return out


def read_seen(home: Path) -> list:
    try:
        lines = (home / SEEN).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def pending_ids(home: Path) -> set:
    return {p.stem for p in (home / "pending" / "memory").glob("*.json")} if (home / "pending" / "memory").is_dir() else set()


def post(body: dict) -> dict:
    req = urllib.request.Request(API + "/os/owner-memory", data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_state(home: Path) -> dict:
    try:
        return json.loads((home / STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(home: Path, state: dict) -> None:
    path = home / STATE
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _ops(rec: dict) -> list:
    ops = rec.get("ops")
    if isinstance(ops, list):
        return ops
    return [{"action": "add", "content": c} for c in rec.get("contents") or []]       # older snapshots


def get(include_superseded: bool = True) -> list:
    url = API + "/os/owner-memory" + ("?include_superseded=1" if include_superseded else "")
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))["entries"]


def hermes_repairer(home: Path):
    """Hermes' own MemoryStore (its lock, limits and file format) for repairing the projection; None if unavailable."""
    try:
        sys.path.insert(0, str(home / "hermes-agent"))
        from tools.memory_tool import MemoryStore, get_builtin_memory_config
        from hermes_cli.config import load_config_readonly
        cfg = get_builtin_memory_config(load_config_readonly())
        store = MemoryStore(memory_char_limit=cfg.get("memory_char_limit", 2200),
                            user_char_limit=cfg.get("user_char_limit", 1375),
                            memory_enabled=True, user_profile_enabled=True)
        store.load_from_disk()
        return store
    except Exception:
        return None


def repair(home: Path, lilith: list, repairer) -> dict:
    """Make the Hermes files show what LILITH OS holds: add current memories that are missing; drop entries LILITH OS
    superseded on an owner-approved change. Entries LILITH OS does not know are left alone."""
    out = {"repaired_added": 0, "repaired_removed": 0, "repair_failed": 0}
    present = {(s, norm(t)): t for s, t in entries(home)}
    active = {(e["store"], norm(e["text"])) for e in lilith if e["lifecycle_state"] != "SUPERSEDED"}
    todo_add = [e for e in lilith if e["lifecycle_state"] != "SUPERSEDED" and (e["store"], norm(e["text"])) not in present]
    todo_rm = [present[(e["store"], norm(e["text"]))] for e in lilith
               if e["lifecycle_state"] == "SUPERSEDED" and (e["store"], norm(e["text"])) in present
               and (e["store"], norm(e["text"])) not in active]
    if not (todo_add or todo_rm):
        return out
    store = repairer(home) if callable(repairer) else repairer
    if store is None:
        out["repair_failed"] = len(todo_add) + len(todo_rm)
        return out
    for e in todo_add:
        ok = (store.add(e["store"], e["text"]) or {}).get("success")
        out["repaired_added" if ok else "repair_failed"] += 1
    for e in lilith:
        key = (e["store"], norm(e["text"]))
        if e["lifecycle_state"] == "SUPERSEDED" and key in present and key not in active:
            ok = (store.remove(e["store"], present[key]) or {}).get("success")
            out["repaired_removed" if ok else "repair_failed"] += 1
    return out


def sync(home: Path = HOME, poster=post, now: float = None, getter=get, repairer=hermes_repairer) -> dict:
    now = time.time() if now is None else now
    state = _load_state(home)
    synced = state.setdefault("synced", {})            # norm(text) -> entry_id
    inactive = set(state.get("inactive", []))           # entry ids superseded or retracted by an approved change
    report = {"created": 0, "superseded": 0, "retracted": 0, "skipped_unattributed": 0, "missing_in_hermes": 0}
    current = entries(home)
    present = {(s, norm(t)) for s, t in current}

    def assert_(store, text, prov, supersedes=()):
        body = {"store": store, "text": text, "provenance": prov}
        olds = [synced[norm(o)] for o in supersedes if norm(o) in synced]
        if olds:
            body["supersedes"] = olds
        r = poster(body)
        synced[norm(text)] = r["entry_id"]
        report["created"] += r.get("action") == "created"
        report["superseded"] += len(r.get("superseded") or [])
        inactive.update(olds)                           # replaced on the owner's approval: no longer current

    if not state.get("bootstrapped"):
        for b in BOOTSTRAP:
            assert_(b["store"], b["text"], b["provenance"], [b["supersedes_text"]] if b.get("supersedes_text") else ())
        for store, text in current:
            if norm(text) not in synced:
                assert_(store, text, {"kind": "HERMES_PREEXISTING_IMPORT",
                                      "note": "Hermes %s entry present at first sync (2026-11-06)" % store.upper()})
        state["bootstrapped"] = True

    # LILITH OS is the primary record: what it already holds (approvals written directly by /memory approve, earlier
    # syncs) is known, so it is never treated as unattributed or posted twice.
    for e in getter(True):
        synced.setdefault(norm(e["text"]), e["entry_id"])
        if e["lifecycle_state"] == "SUPERSEDED":
            inactive.add(e["entry_id"])

    live = pending_ids(home)
    decided = [r for r in read_seen(home) if r.get("id") not in live and r.get("id") not in state.get("handled", [])]
    handled = state.setdefault("handled", [])
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    for rec in decided:
        pid = str(rec.get("id"))
        prov = {"kind": "OWNER_APPROVED_PROPOSAL", "proposal_id": pid,
                "note": "approval observed by sync at %s" % stamp}
        approved_any = False
        for op in _ops(rec):
            action, content, old = op.get("action"), op.get("content"), op.get("old_text")
            store = op.get("target") or rec.get("target") or "user"
            if action in ("add", "replace") and content and (store, norm(content)) in present:
                if norm(content) not in synced:
                    assert_(store, content, prov, [old] if action == "replace" and old else ())
                approved_any = True
            elif action == "remove" and old and (store, norm(old)) not in present and norm(old) in synced:
                r = poster({"action": "retract", "store": store, "entry_id": synced[norm(old)], "provenance": prov})
                report["retracted"] += r.get("action") == "retracted"
                inactive.add(synced[norm(old)])
                approved_any = True
        handled.append(pid)                             # approved or rejected: decided once, never re-read
    for store, text in current:                          # anything else in the files is unattributed: not synced
        if norm(text) not in synced:
            report["skipped_unattributed"] += 1
    report.update(repair(home, getter(True), repairer))
    present = {(s, norm(t)) for s, t in entries(home)}
    names = {n for _, n in present}
    report["missing_in_hermes"] = sum(1 for t, eid in synced.items() if eid not in inactive and t not in names)
    state["inactive"] = sorted(inactive)
    state["last_run"] = stamp
    state["last_report"] = report
    _save_state(home, state)
    return report


if __name__ == "__main__":
    try:
        sync()
    except Exception as exc:                             # visible in the cron job's output, never silent data loss
        sys.stdout.write("owner_memory_sync FAILED: %s\n" % exc)
        sys.exit(1)
