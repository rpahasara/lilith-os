"""F9-C Track A: the durable First Interaction FORGET intent and the hold-first runner (DEV_SYNTHETIC only).

Hold-first: no conversation may continue once the owner's FORGET is recorded, and Privacy authorizes nothing until the
conversation front end is stopped.

1. ``ForgetIntentStore.record`` writes the one fixed-name intent ({v, identity, intentRefId, actorRefId,
   recordedAt}; no content, no evidence) into the root-owned sticky intent directory (``root:lilith-forget 1770``:
   the Core API group may create, and fsync the directory, but never remove a root-owned intent), fully and durably
   before it is visible (temp file, fsync, hard link, fsync of the directory). It never overwrites. Its mere existence blocks the gateway (the drop-in
   ``ConditionPathExistsGlob=!…/intent/*.intent``) and the Core API conversation relay (``app.py``).
2. The root hold unit (``hermes-forget-hold.path`` → ``hermes_forget_executor.py --hold``) takes ownership of the intent
   (``root:lilith-forget 0640``, so the sticky directory stops the Core API from removing it) and stops the gateway
   (``Conflicts=``).
3. ``HoldFirstForgetRunner`` calls Privacy's ``begin_forget`` (through the Slice 3 runner) only when the intent is
   root-owned AND the gateway is observed stopped (unit inactive, port closed).

The intent is removed only by root: the reconcile pass once Privacy itself proves the identity's FORGET COMPLETED with
the Hermes owner, or an explicit operator cancel that refuses while an authorization is in flight. Evidence consumed
by an attempt that never committed (``begin_forget`` consumes it before its transaction) leaves the intent pending and
blocking: the owner re-confirms with fresh evidence for the same intent, or cancels (decision D-10).
"""

from __future__ import annotations

import json
import os
import re
import socket
import stat
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

try:
    from . import canonical_authority as A
    from . import privacy_forget_runner as R
except ImportError:  # deploy-exact flat-directory tests
    import canonical_authority as A
    import privacy_forget_runner as R

INTENT_DIR = Path("/var/lib/hermes-forget/intent")
INTENT_NAME = "first-interaction.intent"
IDENTITY_LABEL = "FIRST_INTERACTION"
INTENT_FIELDS = frozenset({"v", "identity", "intentRefId", "actorRefId", "recordedAt"})
REF_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
MAX_INTENT_BYTES = 1024

INTENT_RECORDED_HOLD_PENDING = "INTENT_RECORDED_HOLD_PENDING"
INTENT_STALLED_EVIDENCE_REFUSED = "INTENT_STALLED_EVIDENCE_REFUSED"

ABSENT, RECORDED, HELD = "ABSENT", "RECORDED", "HELD"


class ForgetIntentError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ForgetIntentStore:
    def __init__(self, intent_dir: Path = INTENT_DIR, *, holder_uid: int = 0):
        self.intent_dir = Path(intent_dir)
        self.path = self.intent_dir / INTENT_NAME
        self.holder_uid = holder_uid

    def read(self) -> Optional[Mapping[str, Any]]:
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_INTENT_BYTES:
                raise ForgetIntentError("FORGET_INTENT_UNTRUSTED")
            data = os.read(fd, MAX_INTENT_BYTES + 1)
        finally:
            os.close(fd)
        try:
            intent = json.loads(data.decode("ascii"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ForgetIntentError("FORGET_INTENT_MALFORMED") from exc
        if not isinstance(intent, dict) or set(intent) != INTENT_FIELDS:
            raise ForgetIntentError("FORGET_INTENT_MALFORMED")
        return intent

    def state(self) -> str:
        try:
            st = os.lstat(self.path)
        except FileNotFoundError:
            return ABSENT
        return HELD if stat.S_ISREG(st.st_mode) and st.st_uid == self.holder_uid else RECORDED

    def record(self, *, intent_ref_id: str, actor_ref_id: str) -> Mapping[str, Any]:
        """Durably record the intent, or return the identical pending one; a different pending intent is refused."""
        if not REF_RE.fullmatch(str(intent_ref_id)) or not REF_RE.fullmatch(str(actor_ref_id)):
            raise ForgetIntentError("FORGET_INTENT_INVALID")
        existing = self.read()
        if existing is not None:
            if existing.get("intentRefId") != intent_ref_id or existing.get("actorRefId") != actor_ref_id:
                raise ForgetIntentError("FORGET_INTENT_PENDING")
            return existing
        intent = {"v": 1, "identity": IDENTITY_LABEL, "intentRefId": intent_ref_id, "actorRefId": actor_ref_id,
                  "recordedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
        data = json.dumps(intent, sort_keys=True, separators=(",", ":")).encode("ascii")
        tmp = self.intent_dir / f".{INTENT_NAME}.{uuid.uuid4().hex}.tmp"     # not matched by *.intent
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            os.link(tmp, self.path)              # complete before visible; never replaces an existing intent
        except FileExistsError:
            os.unlink(tmp)
            return self.record(intent_ref_id=intent_ref_id, actor_ref_id=actor_ref_id)
        os.unlink(tmp)
        dfd = os.open(self.intent_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
        return intent


class GatewayProbe:
    """Unprivileged observation of the Hermes gateway: unit state (systemd D-Bus, read-only) and its loopback port."""

    def __init__(self, unit: str = "hermes-gateway-dev.service", ports=(9901,)):
        self.unit, self.ports = unit, tuple(ports)

    def stopped(self) -> bool:
        try:
            out = subprocess.run(["systemctl", "show", self.unit, "-p", "ActiveState", "--value"],
                                 capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return False
        if out.returncode != 0 or out.stdout.strip() not in {"inactive", "failed"}:
            return False
        for port in self.ports:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return False
        return True


class HoldFirstForgetRunner:
    """The Slice 3 runner behind the durable intent and the root hold. Holds no authority of its own."""

    def __init__(self, runner: R.FirstInteractionForgetRunner, intents: ForgetIntentStore, gateway: GatewayProbe, *,
                 hold_timeout_seconds: float = 120.0, poll_seconds: float = 1.0,
                 sleep: Callable[[float], None] = time.sleep, monotonic: Callable[[], float] = time.monotonic):
        self.runner, self.intents, self.gateway = runner, intents, gateway
        self.hold_timeout_seconds, self.poll_seconds = hold_timeout_seconds, poll_seconds
        self.sleep, self.monotonic = sleep, monotonic

    def _held(self) -> bool:
        deadline = self.monotonic() + self.hold_timeout_seconds
        while True:
            if self.intents.state() == HELD and self.gateway.stopped():
                return True
            if self.monotonic() >= deadline:
                return False
            self.sleep(self.poll_seconds)

    def forget(self, *, actor_ref_id: str, actor_evidence_ref_id: str, intent_ref_id: str,
               confirmation_event_ref: str) -> R.ForgetRunResult:
        self.intents.record(intent_ref_id=intent_ref_id, actor_ref_id=actor_ref_id)
        if not self._held():
            return R.ForgetRunResult(INTENT_RECORDED_HOLD_PENDING, failure_code="HOLD_NOT_ESTABLISHED")
        privacy = self.runner.privacy_authority
        if privacy.in_flight_authorization(R.IDENTITY) is not None:
            return self.runner.resume()                                  # accepted earlier: finish it
        if privacy.suppression_matches(R.IDENTITY):
            return R.ForgetRunResult(R.ALREADY_COMPLETE)                # root reconcile releases the intent
        try:
            return self.runner.forget(actor_ref_id=actor_ref_id, actor_evidence_ref_id=actor_evidence_ref_id,
                                      intent_ref_id=intent_ref_id, confirmation_event_ref=confirmation_event_ref)
        except (A.ActorEvidenceError, R.P.PrivacyError) as exc:
            # Actor evidence refused (ACTOR_*), including evidence consumed by an earlier attempt whose Privacy
            # transaction never committed (H6): the intent stays durable and blocking until fresh evidence for it, or
            # an explicit cancel. Any other Privacy refusal propagates (the intent stays as well).
            if not str(exc).startswith("ACTOR_"):
                raise
            if privacy.in_flight_authorization(R.IDENTITY) is not None:
                return self.runner.resume()
            return R.ForgetRunResult(INTENT_STALLED_EVIDENCE_REFUSED, failure_code=str(exc))

    def resume(self) -> R.ForgetRunResult:
        if self.intents.state() != ABSENT and not self._held():
            return R.ForgetRunResult(INTENT_RECORDED_HOLD_PENDING, failure_code="HOLD_NOT_ESTABLISHED")
        return self.runner.resume()
