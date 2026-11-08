"""LILITH Router: one-time Discord owner-DM link, proven through the owner's verified Telegram DM.

Owner request 2026-11-08: the owner's private Discord DM becomes an owner channel for the SAME LILITH identity, but only
after a challenge that ties the Discord account to the already-verified owner Telegram DM. Display names, server
membership and roles prove nothing.

    1. In a Discord DM (no guild, not a bot, not yet an owner channel) the user sends exactly:  link owner
    2. LILITH sends a one-time code to the owner's Telegram DM (the first configured owner Telegram id), naming the
       Discord user id and DM channel id that asked.
    3. The user types that code in the same Discord DM within 10 minutes (5 tries). Only the code's salted hash is
       kept, and the comparison is constant-time.
    4. On a match the pair {userId, chatId} is recorded in ~/.hermes/owner-link/verified.json (0600) and the owner is
       told on Telegram. That record is evidence, not access: the DM becomes an owner channel only when the operator
       copies the pair into the root-owned lilith_router/canonical_memory.json (`ownerDiscordDms`) and adds the label
       `discord_owner_dm` to the owner's channel grant. Nothing here can make a turn an owner turn.

Replies are ready replies (no model call, no tools). Every failure is quiet: no reply means the turn goes on as a normal
non-owner turn. At most 3 link requests per hour, one pending challenge at a time.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional

LINK_RE = re.compile(r"\s*link owner\s*\Z", re.IGNORECASE)
CODE_RE = re.compile(r"\s*([A-Z2-9]{4})-?([A-Z2-9]{4})\s*\Z", re.IGNORECASE)
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"        # no 0/O, 1/I/L
TTL_S = 600
MAX_ATTEMPTS = 5
MAX_REQUESTS_PER_HOUR = 3
DIR_NAME = "owner-link"


def _dm_source(source: Any) -> Optional[tuple]:
    user = str(getattr(source, "user_id", "") or "")
    chat = str(getattr(source, "chat_id", "") or "")
    kind = str(getattr(source, "chat_type", "") or "").lower()
    guild = getattr(source, "guild_id", None) or getattr(source, "scope_id", None)
    if kind != "dm" or guild or getattr(source, "thread_id", None) or getattr(source, "is_bot", False) is True:
        return None
    if not (user.isdigit() and chat.isdigit()):
        return None
    return user, chat


def _hash(salt: str, code: str) -> str:
    return hashlib.sha256((salt + ":" + code.upper().replace("-", "")).encode("ascii")).hexdigest()


def _read(path: Path) -> Optional[dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(value, f)
    os.replace(tmp, path)


def _bot_token(home: Path) -> Optional[str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token
    try:
        for line in (Path(home) / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    except OSError:
        pass
    return None


def telegram_sender(home: Path) -> Callable[[str, str], bool]:
    def send(chat_id: str, text: str) -> bool:
        token = _bot_token(home)
        if not token:
            return False
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
        req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % token, data=data)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8")).get("ok") is True
        except Exception:
            return False
    return send


def handle(settings: Optional[dict], platform: str, source: Any, message: str, *, home: Any,
           send: Optional[Callable[[str, str], bool]] = None, now: Optional[float] = None) -> Optional[str]:
    """The ready reply for a link turn, or None (not a link turn: the turn continues unchanged). Never raises."""
    try:
        if platform != "discord" or not settings or not settings.get("ownerTelegramUserIds"):
            return None
        pair = _dm_source(source)
        text = message if isinstance(message, str) else ""
        is_link, code = bool(LINK_RE.match(text)), CODE_RE.match(text)
        if pair is None or not (is_link or code):
            return None
        home = Path(home)
        now = time.time() if now is None else now
        send = send or telegram_sender(home)
        state_dir = home / DIR_NAME
        pending_path = state_dir / "pending.json"
        pending = _read(pending_path) or {}
        owner_tg = str(settings["ownerTelegramUserIds"][0])

        if is_link:
            recent = [t for t in pending.get("requests", []) if isinstance(t, (int, float)) and now - t < 3600]
            if len(recent) >= MAX_REQUESTS_PER_HOUR:
                return "Too many link requests. Try again in an hour."
            code_raw = "".join(secrets.choice(ALPHABET) for _ in range(8))
            salt = secrets.token_hex(16)
            _write(pending_path, {"userId": pair[0], "chatId": pair[1], "salt": salt, "codeHash": _hash(salt, code_raw),
                                  "expiresAt": now + TTL_S, "attempts": 0, "requests": recent + [now]})
            shown = code_raw[:4] + "-" + code_raw[4:]
            name = str(getattr(source, "user_name", "") or "?")[:64]
            if not send(owner_tg, "A Discord DM asked to be linked to you as LILITH's owner.\n"
                                  "Discord user: %s (id %s), DM channel %s.\n\n"
                                  "If that was you, type this code in that Discord DM within 10 minutes:\n%s\n\n"
                                  "If it wasn't you, ignore this message." % (name, pair[0], pair[1], shown)):
                _write(pending_path, {"requests": recent + [now]})
                return "I couldn't reach the owner's Telegram just now, so I can't link this DM. Try again later."
            return "I've sent a one-time code to the owner's Telegram DM. Type it here within 10 minutes to link this DM."

        # a code
        if not pending.get("codeHash"):
            return None                                   # no challenge in flight: an ordinary message
        if (pending.get("userId"), pending.get("chatId")) != pair:
            return None                                   # someone else's DM: never a hint
        if now > float(pending.get("expiresAt", 0)):
            _write(pending_path, {"requests": pending.get("requests", [])})
            return "That code has expired. Send \"link owner\" to get a new one."
        if not hmac.compare_digest(_hash(pending["salt"], code.group(1) + code.group(2)), pending["codeHash"]):
            pending["attempts"] = int(pending.get("attempts", 0)) + 1
            if pending["attempts"] >= MAX_ATTEMPTS:
                _write(pending_path, {"requests": pending.get("requests", [])})
                return "Too many wrong codes. Send \"link owner\" to start again."
            _write(pending_path, pending)
            return "That code doesn't match."
        _write(state_dir / "verified.json", {"userId": pair[0], "chatId": pair[1], "verifiedAt": now,
                                             "via": "telegram_owner_dm"})
        _write(pending_path, {"requests": pending.get("requests", [])})
        send(owner_tg, "Discord DM verified (user id %s). It becomes an owner channel once activation is installed."
             % pair[0])
        return "Verified. This DM is linked to the owner; it switches on once activation is installed."
    except Exception:
        return None
