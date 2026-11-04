"""LILITH canonical-memory context service (root; one socket connection per run). Host-setup asset, not signer payload.

The socket-activated unit `lilith-first-memory-context@.service` runs this file under the installed authority
release's venv, once per connection, with the connection as stdin/stdout. It is the installed release's own
`first-memory-context` form (`lilith_authority_root.cli`) with exactly one policy added, owner decision D-2
(2026-11-04): owner-personal canonical memory may reach the owner's own `lilith_os` console when the root-owned,
owner-approved grant SAYS that FORGET covers canonical records only.

Everything else is the release's code, imported, not copied:
  - the request, the host output and every memory field are validated by `cli.context_response`, unchanged;
  - the host runs through `cli.run_first_memory("recall", …)` with only the context token on stdin and a bridge that
    forwards only `LOOKUP_EVIDENCE_USE` (no issuance, no evidence-use write, no recovery);
  - a schemaVersion 1 grant is read by `cli.owner_channel_granted` and keeps its original meaning (exact session AND
    the Hermes Privacy floor).

The grant, `/etc/lilith-first-memory-dev/hermes-owner-channel.json` (root-owned, not group/other-writable, <= 1 KiB):

    {"schemaVersion": 2, "channel": "lilith_os", "sessionScope": "ALL_LILITH_OS_SESSIONS" | "<exact session id>",
     "forgetScope": "CANONICAL_RECORDS_ONLY", "grantedAt": "<UTC Z>", "expiresAt": "<UTC Z, at most 7 days later>"}

schemaVersion 3 (owner decision D-5) names the owner channels explicitly instead of one channel; the only owner
channels are the console and the owner's private Telegram chat, and the gateway decides which a turn is in:

    {"schemaVersion": 3, "channels": ["lilith_os", "telegram_owner_dm"] (a non-empty subset, no duplicates),
     "sessionScope": "ALL_OWNER_CHANNEL_SESSIONS" | "<exact session id>", "forgetScope": "CANONICAL_RECORDS_ONLY",
     "grantedAt": "<UTC Z>", "expiresAt": "<UTC Z, at most 7 days later>"}

`public` (Discord, groups, any other chat) can never be granted.

What `forgetScope: CANONICAL_RECORDS_ONLY` states, and the answer repeats: a FORGET of a memory erases its canonical
records (L04 / L18) and, because the context note is rebuilt from canonical storage on every turn and never persisted,
stops it reaching any later turn. It does NOT erase what LILITH already said in past chat turns (Hermes `state.db`).
No conversation-history erasure is claimed. Without a valid grant the behaviour is exactly the release's.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

RELEASE = "/opt/lilith-authority-dev/current"
GRANT_PATH = "/etc/lilith-first-memory-dev/hermes-owner-channel.json"
GRANT_V2_FIELDS = frozenset({"schemaVersion", "channel", "sessionScope", "forgetScope", "grantedAt", "expiresAt"})
GRANT_V3_FIELDS = frozenset({"schemaVersion", "channels", "sessionScope", "forgetScope", "grantedAt", "expiresAt"})
ALL_SESSIONS = "ALL_LILITH_OS_SESSIONS"
ALL_OWNER_SESSIONS = "ALL_OWNER_CHANNEL_SESSIONS"
CANONICAL_ONLY = "CANONICAL_RECORDS_ONLY"
GRANT_MAX_SECONDS = 7 * 24 * 3600
OWNER_CHANNEL = "lilith_os"
TELEGRAM_OWNER_DM = "telegram_owner_dm"
OWNER_CHANNELS = frozenset({OWNER_CHANNEL, TELEGRAM_OWNER_DM})     # never "public"
OWNER_PERSONAL = "OWNER_PERSONAL"

V1 = "V1_EXACT_SESSION_AND_HERMES_FLOOR"     # the release's own rule
V2 = "V2_" + CANONICAL_ONLY                   # D-2


def grant_basis(cli: Any, channel: str, session: str, *, path: str = GRANT_PATH, owner_uid: int = 0,
                now: Optional[Callable[[], datetime]] = None) -> Optional[str]:
    """V2, V1 or None. A missing, foreign-owned, writable, oversized, malformed, expired or not-yet-valid grant is no
    grant; a v1 grant is judged by the release itself."""
    if channel not in OWNER_CHANNELS:
        return None
    try:
        meta = os.lstat(path)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != owner_uid or meta.st_mode & 0o022 or meta.st_size > 1024:
            return None
        grant = json.loads(Path(path).read_text(encoding="ascii"), object_pairs_hook=cli._no_duplicates)
    except (OSError, ValueError, UnicodeDecodeError, cli.Refused):
        return None
    if not isinstance(grant, dict):
        return None
    if grant.get("schemaVersion") == 1:
        return V1 if cli.owner_channel_granted(channel, session, path=path, owner_uid=owner_uid, now=now) else None
    if grant.get("schemaVersion") == 2:
        if set(grant) != GRANT_V2_FIELDS or grant["channel"] != OWNER_CHANNEL or channel != OWNER_CHANNEL:
            return None
        everyone = ALL_SESSIONS
    elif grant.get("schemaVersion") == 3:
        channels = grant.get("channels")
        if set(grant) != GRANT_V3_FIELDS or not isinstance(channels, list) or not channels \
                or len(set(channels)) != len(channels) or not set(channels) <= OWNER_CHANNELS \
                or channel not in channels:
            return None
        everyone = ALL_OWNER_SESSIONS
    else:
        return None
    if grant["forgetScope"] != CANONICAL_ONLY:
        return None
    scope = grant["sessionScope"]
    if not (isinstance(scope, str) and (scope == everyone or cli._SESSION.match(scope))):
        return None
    if not all(isinstance(grant[k], str) and cli._INSTANT.match(grant[k]) for k in ("grantedAt", "expiresAt")):
        return None
    granted, expires = (datetime.strptime(grant[k], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        for k in ("grantedAt", "expiresAt"))
    current = (now or (lambda: datetime.now(timezone.utc)))()
    if not granted <= current < expires or (expires - granted).total_seconds() > GRANT_MAX_SECONDS:
        return None
    return V2 if scope in (everyone, session) else None


def context_response(cli: Any, raw: bytes, *, host_context: Callable[[str], bytes],
                     basis: Callable[[str, str], Optional[str]]) -> dict:
    """The release's `context_response`, plus D-2. The release validates and filters first; only when it answered
    CONTEXT (so the host output is exact) and the grant is v2 are the owner-personal memories it held back added."""
    seen: dict = {}

    def capture(session: str) -> bytes:
        seen["output"] = host_context(session)
        return seen["output"]

    decided: dict = {}

    def granted(channel: str, session: str) -> bool:
        decided["basis"] = basis(channel, session)
        return decided["basis"] is not None

    answer = cli.context_response(raw, host_context=capture, granted=granted)
    if answer.get("status") != "CONTEXT" or decided.get("basis") != V2:
        return answer
    payload = json.loads(seen["output"].decode("utf-8").strip().splitlines()[-1])   # exact: the release accepted it
    memories = [{k: v for k, v in m.items() if k != "hermesErasable"} for m in payload["memories"]]
    if len({m["kind"] for m in memories}) != len(memories):          # two memories of one kind conflict: none at all
        return cli._unavailable("CONTEXT_HOST_CONFLICT")
    return {**answer, "memories": memories, "ownerChannel": True, "forgetScope": CANONICAL_ONLY}


def main(stdin: Any = None, stdout: Any = None, *, cli: Any = None, euid: Optional[int] = None) -> int:
    if cli is None:
        sys.path.insert(0, RELEASE)
        from lilith_authority_root import cli as release_cli   # the installed, attested release
        cli = release_cli
    out = stdout or sys.stdout
    if (os.geteuid() if euid is None else euid) != 0:
        print("lilith-canonical-context: REFUSED NOT_ROOT", file=sys.stderr)
        return 2
    raw = (stdin or sys.stdin.buffer).read(cli.CONTEXT_MAX_REQUEST + 1)

    def host_context(session: str) -> bytes:
        result = cli.run_first_memory("recall", session, operations=cli.CONTEXT_OPERATIONS,
                                      host_input=(cli.CONTEXT_REQUEST + "\n").encode("ascii"))
        if result["hostExit"] != 0 or result["hostOutput"] is None:
            raise cli.Refused("CONTEXT_HOST_UNAVAILABLE")
        return result["hostOutput"]

    try:
        answer = context_response(cli, raw, host_context=host_context,
                                  basis=lambda channel, session: grant_basis(cli, channel, session))
    except Exception as exc:                                    # never a partial or guessed context
        print(f"lilith-canonical-context: UNAVAILABLE {type(exc).__name__}", file=sys.stderr)
        answer = cli._unavailable("CONTEXT_SERVICE_ERROR")
    out.write(json.dumps(answer, sort_keys=True, separators=(",", ":")) + "\n")
    out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
