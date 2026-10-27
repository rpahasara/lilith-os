"""Groq provider profile — OpenAI-compatible endpoint.

Registers ``groq`` as a first-class Hermes provider so the LILITH Conversation
Intelligence Router can route the *social* path to Groq's Qwen model while the
technical/work path stays on the default gpt-5.6-sol.

Credential handling
-------------------
Hermes' credential resolver reads ``os.environ`` and ``~/.hermes/.env`` only.
The Groq key lives in its own file ``~/.hermes/groq.env`` (0600, single source
of truth), which is NOT auto-loaded. So at import time we export
``GROQ_API_KEY`` from that file into ``os.environ`` *only when unset* — we never
overwrite an already-provided value, never log the value, and never raise if
the file is missing (the provider simply stays unauthenticated until a key is
present, and the router fails open to the default provider).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_groq_env() -> None:
    """Export GROQ_API_KEY from ~/.hermes/groq.env into os.environ if unset.

    Fully defensive: never raises, never logs secret values. A malformed or
    missing file leaves the environment untouched.
    """
    if os.environ.get("GROQ_API_KEY"):
        return
    hermes_home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    env_path = Path(hermes_home) / "groq.env"
    try:
        if not env_path.is_file():
            return
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and not os.environ.get(key):
                os.environ[key] = value
    except Exception:
        # Never let a credential-file quirk break provider discovery.
        logger.debug("groq: could not load %s", env_path, exc_info=True)


def _register() -> None:
    from providers import register_provider
    from providers.base import ProviderProfile

    _load_groq_env()

    groq = ProviderProfile(
        name="groq",
        aliases=("groq-social",),
        api_mode="chat_completions",
        env_vars=("GROQ_API_KEY",),
        display_name="Groq",
        description="Groq LPU inference — fast OpenAI-compatible chat models",
        signup_url="https://console.groq.com/keys",
        base_url="https://api.groq.com/openai/v1",
        models_url="https://api.groq.com/openai/v1/models",
        auth_type="api_key",
        supports_vision=False,
        # Curated fallback list for the picker; the social router pins the model
        # explicitly, so this is only used by the /model UI.
        fallback_models=("qwen/qwen3.8-27b",),
    )
    register_provider(groq)


_register()
