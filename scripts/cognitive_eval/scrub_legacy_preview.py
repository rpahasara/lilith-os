#!/usr/bin/env python3
"""P-1 T-6(b): remove the legacy `preview` field (message-text snippets written by pre-Cutover-2 router code) from
JSONL decision logs, keeping every other field and every record. Owner decision 2026-11-08.

- Only the `preview` key is removed. Non-content metadata (ts, lane, mode, signals, routes, lengths...) is kept.
- Lines that are not JSON objects are kept unchanged.
- Atomic: a temp file is written, then it replaces the original with the same owner and mode, and only if the file
  did not change while scrubbing (the gateway appends to the live log). Up to 3 attempts.
- Prints counts only. No backup copy containing the text is made.

    python3 scrub_legacy_preview.py <log> [<log> ...]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def scrub_lines(lines):
    out, removed = [], 0
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            out.append(line)
            continue
        if isinstance(rec, dict) and "preview" in rec:
            rec.pop("preview")
            removed += 1
            out.append(json.dumps(rec, ensure_ascii=False) + "\n")
        else:
            out.append(line)
    return out, removed


def scrub_file(path: Path, attempts: int = 3) -> dict:
    for _ in range(attempts):
        st = path.stat()
        data = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        out, removed = scrub_lines(data)
        if not removed:
            return {"file": path.name, "records": len(data), "removed": 0, "status": "CLEAN"}
        tmp = path.with_name(path.name + ".scrub-tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, st.st_mode & 0o777)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.writelines(out)
        try:
            os.chown(tmp, st.st_uid, st.st_gid)
        except (PermissionError, AttributeError):
            pass
        now = path.stat()
        if (now.st_size, now.st_mtime_ns) == (st.st_size, st.st_mtime_ns):
            os.replace(tmp, path)
            return {"file": path.name, "records": len(data), "removed": removed, "status": "SCRUBBED"}
        os.unlink(tmp)                                    # appended meanwhile: retry on the new content
    return {"file": path.name, "status": "BUSY_RETRY_LATER"}


def main(argv=None) -> int:
    paths = [Path(p) for p in (argv if argv is not None else sys.argv[1:])]
    if not paths:
        print(__doc__)
        return 2
    for p in paths:
        print(json.dumps(scrub_file(p) if p.exists() else {"file": p.name, "status": "MISSING"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
