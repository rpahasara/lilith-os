"""B-4 minimal readiness correction for the F7-accepted lilith_os adapter (76948218…). Applied at build time."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
EXTRA = [
    ("""        self._pending_lock = threading.Lock()
""",
     """        self._pending_lock = threading.Lock()
        self._idle: Dict[str, threading.Event] = {}  # F8r3 B-4: per-session serialization
"""),
    ("""        fut: Future = Future()
        with self._pending_lock:
            self._pending.setdefault(session, deque()).append(fut)
""",
     """        idle = self._session_idle(session)
        if not idle.wait(timeout=_reply_timeout()):
            logger.warning("lilith_os: session %s still busy after %ss; dispatching anyway", session, _reply_timeout())
        idle.clear()
        fut: Future = Future()
        with self._pending_lock:
            self._pending.setdefault(session, deque()).append(fut)
"""),
    ("""        except Exception as exc:
            self._discard(session, fut)
""",
     """        except Exception as exc:
            self._discard(session, fut)
            idle.set()
"""),
    ("""        self._resolve_oldest(session, state, "")
""",
     """        self._resolve_oldest(session, state, "")
        self._session_idle(session).set()
"""),
    ("""    def _startup_restore_in_progress(self) -> bool:""",
     """    def _session_idle(self, session: str) -> threading.Event:
        \"\"\"F8r3 B-4: per-session 'previous turn fully processed' flag (set = idle).\"\"\"
        with self._pending_lock:
            ev = self._idle.get(session)
            if ev is None:
                ev = self._idle[session] = threading.Event()
                ev.set()
            return ev

    def _startup_restore_in_progress(self) -> bool:"""),
]

s = p.read_text(encoding="utf-8")
edits = [
    # 1. HTTP: a clear 503 while the gateway is still in its startup restore, instead of an empty "completed" reply.
    ("""        self._json(200, {"reply": reply, "state": state, "session": session})
""",
     """        if state == "starting":
            # F8r3 B-4: the gateway is still in its startup restore; nothing was dispatched.
            self._json(503, {"error": "starting", "detail": reply, "session": session})
            return
        self._json(200, {"reply": reply, "state": state, "session": session})
"""),
    # 2. submit(): refuse (before queuing anything) while the startup restore is in progress.
    ("""        if self._loop is None or self._message_handler is None:
            return ("failed", "LILITH gateway is not ready yet — try again in a moment.")
""",
     """        if self._loop is None or self._message_handler is None:
            return ("failed", "LILITH gateway is not ready yet — try again in a moment.")
        if self._startup_restore_in_progress():
            return ("starting", "LILITH is starting — try again in a moment.")
"""),
    # 3. on_processing_complete(): never resolve the waiter with an empty reply for a turn the gateway only queued
    #    during startup restore (its replay delivers the real reply via send(notify)); otherwise the reply is lost or
    #    resolves the NEXT request's waiter (one turn late).
    ("""        if outcome == ProcessingOutcome.SUCCESS:
            state = "completed"
""",
     """        if outcome == ProcessingOutcome.SUCCESS and self._startup_restore_in_progress():
            return
        if outcome == ProcessingOutcome.SUCCESS:
            state = "completed"
"""),
    ("""    # ── Required by BasePlatformAdapter ───────────────────────────────────────
""",
     """    def _startup_restore_in_progress(self) -> bool:
        \"\"\"F8r3 B-4: True while the gateway runner is replaying its startup restore queue.\"\"\"
        runner = getattr(self._message_handler, "__self__", None)
        return bool(getattr(runner, "_startup_restore_in_progress", False))

    # ── Required by BasePlatformAdapter ───────────────────────────────────────
"""),
]
edits += EXTRA
for old, new in edits:
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)
p.write_text(s, encoding="utf-8", newline="\n")
print("patched")
