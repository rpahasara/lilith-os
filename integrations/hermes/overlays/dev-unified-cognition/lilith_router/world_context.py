# -*- coding: utf-8 -*-
"""DEV unified Working Memory for Router V2 (``lilith_router.world_context``). PLANNED overlay, not deployed.

In a future, separately approved DEV release this file replaces the 723-byte DEV import stub. It runs the recovered
PROD Working Memory unchanged and replaces only that module's I/O seam:

* The PROD module is installed beside this file as ``_prod_world_context.py``: PROD ``world_context.py``, byte-exact,
  SHA-256 ``46b8187e…0104``. It is compiled from the same bytes whose digest was checked, so a changed file is
  never executed.
* Its three I/O helpers (``_get_json``, ``_post_draft``, ``_post_goal_json``) are replaced. Every other function
  runs as it ran on PROD: intent detection, grounding, goals, and the reasoning, workspace, motivation, planning
  and ethics inputs.
* Reads are GET only, to the loopback Core API only, and only to an exact path allowlist (World Model, tasks,
  drafts, goals, career applications; never ``/memory/*``). They use no proxy, follow no redirects, accept JSON
  only, and are size-capped.
* Read bounds. Each call into this module has its own budget of ``MAX_CALLS_PER_ENTRY`` reads; there is no
  budget for a whole turn. The bound for a whole turn is structural: the DEV gateway has ``MAX_IO_ENTRIES_PER_TURN``
  call sites that can read, and none of them is inside a loop. That gives ``MAX_READS_PER_TURN`` at most; the
  offline scenarios measure 9 reads per call and 19 per turn at most. A transport failure (refused, timeout) opens
  a breaker: reads are skipped for ``BREAKER_COOLDOWN_SECONDS``, so a hung Core API costs one timeout, not one
  per read.
* Writes are never sent. Core API ``POST /os/drafts`` and ``POST /os/goals`` have no caller authentication or
  approval gate, so the historical PROD draft and goal writes stay off until a reviewed write-governance path
  exists. The PROD code then tells the model that nothing was saved.
* The grounding text a lane adds to the prompt is length-capped.
* If the PROD bytes do not match, or the module fails to load, every detector reports no intent and every builder
  raises inside the gateway's existing ``try``. Router V2 then routes exactly as it does with the stub.

Which lanes run is decided by ``router.yaml`` alone, and the DEV file keeps every lane off. This module logs no
message text, no Core API content and no paths.
"""
from __future__ import annotations

import contextvars
import functools
import hashlib
import importlib.util
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEV_IMPORT_STUB = False
DEV_UNIFIED_COGNITION = True

LEGACY_FILE = "_prod_world_context.py"
LEGACY_SHA256 = "46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104"

API_BASE = "http://127.0.0.1:8765"          # the PROD module's Core API origin; loopback only
GET_TIMEOUT_MAX = 2.5
MAX_RESPONSE_BYTES = 512 * 1024
MAX_CALLS_PER_ENTRY = 16
MAX_IO_ENTRIES_PER_TURN = 10                # read-capable call sites in DEV gateway_integration.py (tests check)
MAX_READS_PER_TURN = MAX_IO_ENTRIES_PER_TURN * MAX_CALLS_PER_ENTRY
BREAKER_COOLDOWN_SECONDS = 30.0
MAX_GROUNDING_CHARS = 16000
TRUNCATION_MARK = "\n[grounding truncated]"

_ID = r"[A-Za-z0-9._~%-]{1,64}"
READ_ALLOWLIST = tuple(re.compile(p) for p in (
    r"/os/world",
    r"/os/world\?entity_type=career\.application(?:&entity_id=" + _ID + r")?",
    r"/os/tasks\?limit=200",
    r"/os/drafts\?limit=200",
    r"/os/drafts\?target_id=" + _ID,
    r"/os/goals\?limit=200",
    r"/os/goals\?state=[A-Za-z_]{1,32}",
    r"/os/goals/focus",
    r"/career/applications",
))


class CognitionUnavailable(RuntimeError):
    """The recovered Working Memory is not loaded; the gateway's lane ``try`` falls open."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None                         # a 3xx then raises HTTPError, which reads as unavailable


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
_BUDGET: contextvars.ContextVar = contextvars.ContextVar("lilith_wm_budget", default=None)
_STATS = {"reads": 0, "reads_refused": 0, "reads_skipped_breaker": 0, "writes_refused": 0}
_BREAKER = {"open_until": 0.0}


def _path_allowed(path) -> bool:
    return isinstance(path, str) and any(p.fullmatch(path) for p in READ_ALLOWLIST)


def _governed_get(path, timeout=GET_TIMEOUT_MAX):
    budget = _BUDGET.get()
    if budget is None or budget[0] <= 0 or not _path_allowed(path):
        _STATS["reads_refused"] += 1
        return None
    if time.monotonic() < _BREAKER["open_until"]:
        _STATS["reads_skipped_breaker"] += 1
        return None
    budget[0] -= 1
    try:
        req = urllib.request.Request(API_BASE + path, headers={"accept": "application/json"}, method="GET")
        with _OPENER.open(req, timeout=min(float(timeout), GET_TIMEOUT_MAX)) as resp:
            if resp.getcode() != 200:
                return None
            if "application/json" not in (resp.headers.get("content-type") or "").lower():
                return None
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.HTTPError, ValueError):
        return None                         # Core API answered: no breaker
    except Exception:
        _BREAKER["open_until"] = time.monotonic() + BREAKER_COOLDOWN_SECONDS
        return None
    try:
        if len(raw) > MAX_RESPONSE_BYTES:
            return None
        _STATS["reads"] += 1
        return json.loads(raw.decode("utf-8") or "null")
    except Exception:
        return None


def _refused_post_draft(payload):
    _STATS["writes_refused"] += 1
    return None


def _refused_post_goal_json(path, payload):
    _STATS["writes_refused"] += 1
    return 0, None


def _load_legacy():
    """Compile the PROD module from the exact bytes whose digest matched, then replace its I/O seam."""
    try:
        source = Path(__file__).resolve().with_name(LEGACY_FILE)
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != LEGACY_SHA256:
            return None, "legacy_digest_mismatch"
        name = (__package__ + "." if __package__ else "") + LEGACY_FILE[:-3]
        spec = importlib.util.spec_from_loader(name, loader=None, origin=str(source))
        module = importlib.util.module_from_spec(spec)
        module.__file__ = str(source)
        module.__package__ = __package__ or ""
        exec(compile(data, str(source), "exec"), module.__dict__)
        module._get_json = _governed_get
        module._post_draft = _refused_post_draft
        module._post_goal_json = _refused_post_goal_json
        sys.modules[name] = module
        return module, None
    except Exception:
        return None, "legacy_load_failed"


_LEGACY, _UNAVAILABLE_REASON = _load_legacy()


def status() -> dict:
    """Non-sensitive state for diagnostics and tests."""
    return {"legacy_loaded": _LEGACY is not None, "reason": _UNAVAILABLE_REASON,
            "legacy_sha256": LEGACY_SHA256, "writes_enabled": False,
            "breaker_open": time.monotonic() < _BREAKER["open_until"], **_STATS}


def _cap(suffix):
    if isinstance(suffix, str) and len(suffix) > MAX_GROUNDING_CHARS:
        return suffix[: MAX_GROUNDING_CHARS - len(TRUNCATION_MARK)] + TRUNCATION_MARK
    return suffix


def _raise_unavailable():
    raise CognitionUnavailable(_UNAVAILABLE_REASON)


def _entry(name, unavailable=_raise_unavailable):
    """One gateway entry point: a fresh read budget per outermost call, and a defined result when not loaded."""
    def call(*args, **kwargs):
        if _LEGACY is None:
            return unavailable()
        token = _BUDGET.set([MAX_CALLS_PER_ENTRY]) if _BUDGET.get() is None else None
        try:
            result = getattr(_LEGACY, name)(*args, **kwargs)
        finally:
            if token is not None:
                _BUDGET.reset(token)
        if name in ("build_grounding", "build_goal_grounding"):
            suffix, action = result
            return _cap(suffix), action
        return result
    call.__name__ = call.__qualname__ = name
    if _LEGACY is not None:
        functools.update_wrapper(call, getattr(_LEGACY, name), assigned=("__doc__",), updated=())
    return call


# Every world_context attribute the DEV gateway_integration uses (the tests check this list against its source).
detect_intent = _entry("detect_intent", lambda: None)
detect_goal_intent = _entry("detect_goal_intent", lambda: None)
detect_reasoning_intent = _entry("detect_reasoning_intent", lambda: None)
detect_planning_intent = _entry("detect_planning_intent", lambda: None)
detect_ethics_intent = _entry("detect_ethics_intent", lambda: None)
build_grounding = _entry("build_grounding")
build_goal_grounding = _entry("build_goal_grounding")
build_attention_candidates = _entry("build_attention_candidates")
build_motivation_snapshot = _entry("build_motivation_snapshot")
motivation_candidates = _entry("motivation_candidates", list)
motivation_trace = _entry("motivation_trace", lambda: {"fallback_reason": "cognition_unavailable"})
select_reasoning_input_m = _entry("select_reasoning_input_m")
build_planning_input = _entry("build_planning_input")
build_ethical_input = _entry("build_ethical_input")

GATEWAY_API = (
    "detect_intent", "detect_goal_intent", "detect_reasoning_intent", "detect_planning_intent",
    "detect_ethics_intent", "build_grounding", "build_goal_grounding", "build_attention_candidates",
    "build_motivation_snapshot", "motivation_candidates", "motivation_trace", "select_reasoning_input_m",
    "build_planning_input", "build_ethical_input",
)
