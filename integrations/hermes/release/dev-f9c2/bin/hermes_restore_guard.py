#!/usr/bin/env python3
"""F9-C restore guard (root): refuse to restore Hermes conversation history captured at or before the latest
completed erasure epoch.

    hermes_restore_guard.py check <artefact> [<artefact> ...]

An artefact is a backup directory, quarantine or archive about to be restored. Once any erasure epoch exists, every
conversation-bearing item inside it (HERMES_HOME conversation/runtime/log paths, state.db*, namespace journal copies,
tar members of those) whose capture time is not after the latest epoch is refused: exit 3,
F8_RESTORE_CONVERSATION_SUPPRESSED. Capture time is the earliest of the artefact's own UTC name stamp (pre-, upgrade-
pre-, rollback-, f8r2-preserved-<YYYYmmddTHHMMSSZ>) and its mtime, so neither alone can make an old copy look new.
Code/config-only artefacts, or history captured after the epoch, are allowed (exit 0). Read-only; content-free output.
"""

from __future__ import annotations

import os
import re
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hermes_forget_executor as X  # noqa: E402  (same release directory)

EPOCH_LOG = Path("/var/lib/hermes-forget/epochs/epochs.log")
STAMP_RE = re.compile(r"(\d{8}T\d{6}Z)")
SUPPRESSED, ALLOWED = 3, 0


def _parse(at: str) -> float:
    return datetime.fromisoformat(at.replace("Z", "+00:00")).timestamp()


def capture_time(path: Path) -> float:
    times = [os.lstat(path).st_mtime]
    for part in path.parts:
        m = STAMP_RE.search(part)
        if m:
            times.append(datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp())
    return min(times)


def conversation_items(path: Path) -> int:
    if path.is_symlink():
        return 0
    if path.is_file():
        if path.name.endswith((".tar", ".tar.gz", ".tgz")):
            return len(X._tar_conversation_members(path))
        return 1 if X._conversation_rel((path.name,)) else 0
    count = 0
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        rel = Path(dirpath).relative_to(path).parts
        for name in list(dirnames):
            if X._conversation_rel(rel + (name,)) == "JOURNAL_COPY":
                count += 1
                dirnames.remove(name)
        for name in filenames:
            p = Path(dirpath) / name
            if p.is_symlink():
                continue
            if X._conversation_rel(rel + (name,)):
                count += 1
            elif name.endswith((".tar", ".tar.gz", ".tgz")):
                count += len(X._tar_conversation_members(p))
    return count


def check(artefacts: Sequence[Path], epoch_log: Path = EPOCH_LOG) -> tuple:
    epochs = X.read_epochs(epoch_log)
    if not epochs:
        return ALLOWED, 0, 0
    latest = epochs[-1]
    cutoff = _parse(latest["at"])
    refused = sum(conversation_items(a) for a in artefacts if capture_time(a) <= cutoff)
    return (SUPPRESSED if refused else ALLOWED), refused, int(latest["epoch"])


def main(argv: Sequence[str]) -> int:
    args = list(argv[1:])
    log = EPOCH_LOG
    if len(args) >= 2 and args[0] == "--epoch-log":
        log, args = Path(args[1]), args[2:]
    if not args or args[0] != "check" or len(args) < 2:
        print("usage: hermes_restore_guard.py [--epoch-log P] check <artefact>...", file=sys.stderr)
        return 2
    try:
        code, refused, epoch = check([Path(a) for a in args[1:]], log)
    except X.ExecutorError as exc:
        print(f"F8_RESTORE_GUARD_FAIL {exc.code}", file=sys.stderr)
        return 1
    if code == SUPPRESSED:
        print(f"F8_RESTORE_CONVERSATION_SUPPRESSED items={refused} epoch={epoch}", file=sys.stderr)
    else:
        print(f"F9_RESTORE_ALLOWED epoch={epoch}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
