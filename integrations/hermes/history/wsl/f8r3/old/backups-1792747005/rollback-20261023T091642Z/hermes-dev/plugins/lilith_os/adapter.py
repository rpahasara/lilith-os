"""
LILITH OS operator-console inbound adapter.

A minimal, trusted, localhost-only HTTP front end for the gateway. It mirrors
the a2a plugin's proven synchronous mechanics (stdlib http.server on a daemon
thread + a per-request Future resolved from ``send()``) WITHOUT importing or
modifying a2a, and without a2a's untrusted-agent security boundary: the caller
is the local operator, so input is passed through unframed and replies are not
email/token-redacted (only a narrow secret-string scrub is applied so raw
credentials are never echoed).

Request  (POST /):   {"message": "<text>", "session": "<stable id>"}
Response (200):      {"reply": "<text>", "state": "completed", "session": "<id>"}
Health   (GET /health): {"status": "ok"}
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import deque
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FuturesTimeout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Deque, Dict, Optional, Tuple

from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    ProcessingOutcome,
    SendResult,
)
from gateway.config import Platform

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 9901
# DEV candidate: bounded request body (the Core API relay sends one short JSON object).
_MAX_BODY_BYTES = 64 * 1024
_OPERATOR_ID = "operator"
_OPERATOR_NAME = "Operator"


def _reply_timeout() -> float:
    try:
        return max(5.0, float(os.getenv("LILITH_OS_REPLY_TIMEOUT", "180")))
    except (TypeError, ValueError):
        return 180.0


# Narrow, high-confidence credential shapes. We deliberately do NOT redact
# emails or other normal text (that is the operator's own data). This only
# stops raw secrets from being echoed back verbatim.
_SECRET_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = (
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"), "sk-ant-[redacted]"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk-[redacted]"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_[redacted]"),
    (re.compile(r"gho_[A-Za-z0-9]{20,}"), "gho_[redacted]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_[redacted]"),
    (re.compile(r"xox[bapr]-[A-Za-z0-9\-]{10,}"), "xox-[redacted]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA[redacted]"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{20,}"), "AIza[redacted]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}"), "Bearer [redacted]"),
    (
        re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
        "[redacted-jwt]",
    ),
)


def _scrub_secrets(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern, repl in _SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out


class _ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, handler_cls, adapter: "LilithOSAdapter"):
        super().__init__(addr, handler_cls)
        self.adapter = adapter


class _ConsoleHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    @property
    def _adapter(self) -> "LilithOSAdapter":
        return self.server.adapter  # type: ignore[attr-defined]

    # Silence default stderr access logging.
    def log_message(self, *_args) -> None:  # noqa: D401
        return

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def do_GET(self) -> None:
        if self.path.rstrip("/") in ("/health", ""):
            self._json(200, {"status": "ok", "service": "lilith-os-console"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        adapter = self._adapter

        # DEV candidate: the shared token is MANDATORY (fail closed when it is not
        # configured) and compared in constant time. The 127.0.0.1 bind alone is
        # not authentication: other local processes could otherwise drive the
        # operator console.
        token = os.getenv("LILITH_OS_TOKEN", "").strip()
        if len(token) < 32:
            self._json(503, {"error": "console token not configured"})
            return
        presented = (self.headers.get("X-LILITH-OS-Token") or "").strip()
        if not hmac.compare_digest(presented.encode("utf-8"), token.encode("utf-8")):
            self._json(401, {"error": "unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length < 0 or length > _MAX_BODY_BYTES:
            self._json(413, {"error": "request too large"})
            return
        try:
            raw = self.rfile.read(length) if length > 0 else b""
            data = json.loads(raw or b"{}")
        except Exception:
            self._json(400, {"error": "invalid json"})
            return
        if not isinstance(data, dict):
            self._json(400, {"error": "body must be an object"})
            return

        message = str(data.get("message") or data.get("text") or "").strip()
        session = str(
            data.get("session") or data.get("session_id") or "lilith-os"
        ).strip() or "lilith-os"
        if not message:
            self._json(400, {"error": "empty message"})
            return

        try:
            state, reply = adapter.submit(message, session)
        except FuturesTimeout:
            self._json(
                504,
                {"error": "timed out waiting for LILITH's reply", "session": session},
            )
            return
        except Exception:
            logger.debug("lilith_os: submit failed", exc_info=True)
            self._json(500, {"error": "internal error", "session": session})
            return

        if state == "starting":
            # F8r3 B-4: the gateway is still in its startup restore; nothing was dispatched.
            self._json(503, {"error": "starting", "detail": reply, "session": session})
            return
        self._json(200, {"reply": reply, "state": state, "session": session})


class LilithOSAdapter(BasePlatformAdapter):
    """Trusted, localhost-only operator console adapter."""

    def __init__(self, config, **_kwargs):
        super().__init__(config=config, platform=Platform("lilith_os"))
        extra = getattr(config, "extra", {}) or {}
        self.port = int(os.getenv("LILITH_OS_PORT") or extra.get("port", _DEFAULT_PORT))
        # Always localhost — this console is never exposed off-box.
        self.host = "127.0.0.1"
        self._httpd: Optional[_ConsoleServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # context_id (session) -> FIFO of waiting reply futures.
        self._pending: Dict[str, Deque[Future]] = {}
        self._pending_lock = threading.Lock()

    # ── Identity ───────────────────────────────────────────────────────────
    @property
    def name(self) -> str:
        return "LILITH OS"

    @property
    def authorization_is_upstream(self) -> bool:
        """The 127.0.0.1-only bind (plus the optional shared token) IS the
        authorization: the sole caller is the trusted local operator. Without
        this, the gateway's ``{PLATFORM}_ALLOWED_USERS`` allow-list would reject
        the synthetic operator identity. This is not a fail-open — remote access
        is impossible (localhost bind) and the token is checked when set."""
        return True

    # ── Lifecycle ────────────────────────────────────────────────────────────
    async def connect(self, **_kwargs) -> bool:
        # Capture the running gateway loop so the HTTP thread can marshal
        # events onto it via run_coroutine_threadsafe.
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        try:
            self._httpd = _ConsoleServer((self.host, self.port), _ConsoleHandler, self)
        except OSError as exc:
            logger.error(
                "lilith_os: could not bind %s:%s — %s", self.host, self.port, exc
            )
            self._set_fatal_error(
                "bind_failed", f"LILITH OS console bind failed: {exc}", retryable=True
            )
            return False
        self._server_thread = threading.Thread(
            target=self._httpd.serve_forever, name="lilith-os-http", daemon=True
        )
        self._server_thread.start()
        self._mark_connected()
        secured = "token+localhost" if len(os.getenv("LILITH_OS_TOKEN", "").strip()) >= 32 else "REFUSING POSTS: token unset"
        logger.info(
            "lilith_os: operator console serving on http://%s:%s (%s)",
            self.host,
            self.port,
            secured,
        )
        return True

    async def disconnect(self) -> None:
        self._mark_disconnected()
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
        # Fail any in-flight replies so blocked HTTP threads don't hang.
        with self._pending_lock:
            for queue in self._pending.values():
                for fut in queue:
                    if not fut.done():
                        fut.set_result(("failed", "[console shutting down]"))
            self._pending.clear()

    # ── Request plumbing ─────────────────────────────────────────────────────
    def submit(self, message: str, session: str) -> Tuple[str, str]:
        """Dispatch one operator turn into the live gateway session and block
        (on an HTTP worker thread) until LILITH's final reply resolves."""
        if self._loop is None or self._message_handler is None:
            return ("failed", "LILITH gateway is not ready yet — try again in a moment.")
        if self._startup_restore_in_progress():
            return ("starting", "LILITH is starting — try again in a moment.")

        fut: Future = Future()
        with self._pending_lock:
            self._pending.setdefault(session, deque()).append(fut)

        event = MessageEvent(
            text=message,  # trusted operator text — passed through unframed
            message_type=MessageType.TEXT,
            source=self.build_source(
                chat_id=session,
                chat_name="LILITH OS",
                chat_type="dm",
                user_id=_OPERATOR_ID,
                user_name=_OPERATOR_NAME,
                role_authorized=True,
            ),
            user_id=_OPERATOR_ID,
            user_name=_OPERATOR_NAME,
            message_id=uuid.uuid4().hex,
        )

        try:
            asyncio.run_coroutine_threadsafe(self.handle_message(event), self._loop)
        except Exception as exc:
            self._discard(session, fut)
            logger.debug("lilith_os: dispatch failed: %s", exc, exc_info=True)
            return ("failed", "Could not reach LILITH's conversation engine.")

        state, reply = fut.result(timeout=_reply_timeout())
        reply = _scrub_secrets(reply or "")
        if state == "completed" and not reply:
            reply = "(LILITH completed the turn without a text reply.)"
        return state, reply

    def _discard(self, session: str, fut: Future) -> None:
        with self._pending_lock:
            queue = self._pending.get(session)
            if queue and fut in queue:
                try:
                    queue.remove(fut)
                except ValueError:
                    pass
            if queue is not None and not queue:
                self._pending.pop(session, None)

    def _resolve_oldest(self, session: str, state: str, text: str) -> bool:
        """Resolve the oldest outstanding future for a session (the gateway
        processes a session's turns in order, and the frontend disables
        concurrent sends, so FIFO is exact)."""
        with self._pending_lock:
            queue = self._pending.get(session)
            while queue:
                fut = queue.popleft()
                if not fut.done():
                    fut.set_result((state, text))
                    if not queue:
                        self._pending.pop(session, None)
                    return True
            if queue is not None and not queue:
                self._pending.pop(session, None)
        return False

    # ── Reply path ───────────────────────────────────────────────────────────
    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """The gateway delivers LILITH's reply here. Only the final,
        user-visible reply carries ``metadata['notify']``; progress/preview
        sends are ignored so they don't prematurely satisfy the HTTP caller."""
        message_id = str(int(time.time() * 1000))
        if not (metadata or {}).get("notify"):
            return SendResult(success=True, message_id=message_id)
        self._resolve_oldest(chat_id, "completed", content or "")
        return SendResult(success=True, message_id=message_id)

    async def on_processing_complete(
        self, event: MessageEvent, outcome: ProcessingOutcome
    ) -> None:
        """Guarantee the HTTP caller never hangs: if the turn ended without a
        notify reply (e.g. failure/cancel, or a turn with no user-visible
        text), resolve the waiter. A no-op when ``send()`` already resolved."""
        session = getattr(getattr(event, "source", None), "chat_id", None) or ""
        if not session:
            return
        if outcome == ProcessingOutcome.SUCCESS and self._startup_restore_in_progress():
            return
        if outcome == ProcessingOutcome.SUCCESS:
            state = "completed"
        elif outcome == ProcessingOutcome.CANCELLED:
            state = "cancelled"
        else:
            state = "failed"
        self._resolve_oldest(session, state, "")

    def _startup_restore_in_progress(self) -> bool:
        """F8r3 B-4: True while the gateway runner is replaying its startup restore queue."""
        runner = getattr(self._message_handler, "__self__", None)
        return bool(getattr(runner, "_startup_restore_in_progress", False))

    # ── Required by BasePlatformAdapter ───────────────────────────────────────
    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {"chat_id": chat_id, "chat_type": "dm", "platform": "lilith_os"}
