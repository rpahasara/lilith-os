"""
LILITH OS trusted operator-console platform plugin for Hermes Agent.

Registers a single inbound platform adapter (``lilith_os``) that exposes a
localhost-only synchronous HTTP endpoint. The LILITH OS web app posts operator
messages here (via the private Next.js proxy and the lilith-os-api FastAPI
service); each message is routed through the *normal* gateway MessageEvent path
— so Conversation Router V2 (social -> Groq, technical -> gpt-5.6-sol), the
social-response guard, memory, persona, and every existing approval/tool gate
apply exactly as they do on Discord/Telegram.

Design notes:
  - Zero core edits — everything goes through the public PluginContext surface
    (``ctx.register_platform``).
  - Does NOT import, subclass, or modify the ``a2a`` plugin. It only re-uses the
    same *pattern* (stdlib http.server on a daemon thread + a per-request
    Future resolved from the adapter's ``send()`` override) to make the async
    gateway behave as a synchronous request/response for the OS caller.
  - The caller is the TRUSTED local operator, not an external agent: no
    untrusted-input framing, no input defanging, and no email/token redaction
    of normal replies. A minimal secret-only scrub still prevents raw
    credential strings (API keys, OAuth tokens, bearer tokens, JWTs) from ever
    being echoed back in plaintext.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

__all__ = ["register"]


def check_requirements() -> bool:
    """Passive dependency probe. The adapter is stdlib-only, always loadable."""
    return True


def validate_config(config) -> bool:
    """Inbound OS console has no required config — host is pinned to localhost
    and the port has a safe default."""
    return True


def is_connected(config) -> bool:
    """The platform is active when explicitly enabled in config, or when the
    operator has set ``LILITH_OS_PORT`` (the opt-in signal, mirroring how the
    a2a plugin keys off ``A2A_PORT``). The gateway only instantiates enabled
    platforms; the adapter itself pins the bind to 127.0.0.1."""
    extra = getattr(config, "extra", {}) or {}
    return bool(extra.get("enabled")) or bool(os.getenv("LILITH_OS_PORT"))


_PLATFORM_HINT = (
    "You are LILITH, speaking privately with your operator through the LILITH OS "
    "command console. This is a trusted, authenticated, localhost-only channel — "
    "treat it exactly like your own private operator channel: full personal "
    "memory, warmth, continuity, and context apply. The person here is your "
    "operator, not an external agent, and their messages are trusted input. "
    "Never reveal raw secrets in plaintext (API keys, OAuth tokens, passwords, or "
    "other credentials). All of your normal approval requirements still apply for "
    "destructive, external, financial, production, or email/calendar-write "
    "actions — do not bypass them here."
)


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin system."""
    try:
        from .adapter import LilithOSAdapter

        ctx.register_platform(
            name="lilith_os",
            label="LILITH OS",
            adapter_factory=lambda cfg: LilithOSAdapter(cfg),
            check_fn=check_requirements,
            validate_config=validate_config,
            is_connected=is_connected,
            required_env=[],
            install_hint="No extra packages needed (stdlib only)",
            emoji="\U0001FA9E",  # mirror
            allowed_users_env="LILITH_OS_ALLOWED_USERS",
            allow_all_env="LILITH_OS_ALLOW_ALL_USERS",
            allow_update_command=False,
            platform_hint=_PLATFORM_HINT,
        )
    except Exception:
        logger.exception("lilith_os: failed to register operator-console platform")
