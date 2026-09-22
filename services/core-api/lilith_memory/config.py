"""Fail-closed server-owned configuration for the Slice 15 runtime.

The browser, model, proposal payload, and HTTP caller have no input to this
loader.  A missing or malformed file returns an invalid, disabled snapshot.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Optional

try:
    from .canonical_contracts import CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE
except ImportError:  # deploy-exact flat-directory regression staging
    from canonical_contracts import CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE


CONFIG_ENV = "LILITH_CANONICAL_CONFIG_FILE"
ALLOWED_CAPABILITIES = frozenset({CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE})
_CONFIG_KEYS = frozenset(
    {"schemaVersion", "canonicalLtmEnabled", "activeCapabilities"}
)


@dataclass(frozen=True)
class RuntimeConfig:
    canonical_ltm_enabled: bool = False
    canonical_ltm_config_valid: bool = False
    active_capabilities: FrozenSet[str] = frozenset()
    memory_consolidation_enabled: bool = False
    memory_consolidation_mode: str = "DISABLED"
    resolved_log_path: Optional[Path] = None
    source_path: Optional[Path] = None
    failure_code: Optional[str] = "CONFIG_MISSING"

    def capability_active(self, capability: str) -> bool:
        return (
            self.canonical_ltm_config_valid
            and capability in self.active_capabilities
        )


def _disabled(code: str, source: Optional[Path] = None) -> RuntimeConfig:
    return RuntimeConfig(source_path=source, failure_code=code)


def load(path: Optional[Path] = None) -> RuntimeConfig:
    """Load one exact JSON config snapshot; failure always means disabled."""
    configured = path
    if configured is None:
        raw_path = os.environ.get(CONFIG_ENV)
        if not raw_path:
            return _disabled("CONFIG_MISSING")
        configured = Path(raw_path)
    source = Path(configured).resolve()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _disabled("CONFIG_MISSING", source)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _disabled("CONFIG_MALFORMED", source)
    if not isinstance(raw, dict) or set(raw) != _CONFIG_KEYS:
        return _disabled("CONFIG_MALFORMED", source)
    enabled = raw.get("canonicalLtmEnabled")
    capabilities = raw.get("activeCapabilities")
    if (
        raw.get("schemaVersion") != 1
        or not isinstance(enabled, bool)
        or not isinstance(capabilities, list)
        or any(not isinstance(value, str) for value in capabilities)
        or len(set(capabilities)) != len(capabilities)
        or not set(capabilities).issubset(ALLOWED_CAPABILITIES)
    ):
        return _disabled("CONFIG_MALFORMED", source)
    return RuntimeConfig(
        canonical_ltm_enabled=enabled,
        canonical_ltm_config_valid=True,
        active_capabilities=frozenset(capabilities),
        source_path=source,
        failure_code=None,
    )


def assert_nonproduction_database(
    candidate: Path,
    *,
    production_path: Path,
    environment: str,
) -> Path:
    """Reject CI/test/DEV use of the production cognitive or privacy path."""
    target = Path(candidate).resolve()
    production = Path(production_path).resolve()
    if environment.lower() in {"test", "ci", "dev", "development"} and target == production:
        raise ValueError("non-production runtime cannot open production database")
    return target
