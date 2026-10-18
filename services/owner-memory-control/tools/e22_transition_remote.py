#!/usr/bin/env python3
"""15B2b-B1b-3e M-B12 E-22: the READ-ONLY host side of `e22_operator.py` (the tail of its W11 BOOT bundle).

Record: docs/architecture/slice-15b2b-b1b3e-e22-judge-transition.md §6. SOURCE ONLY: running it on DEV needs the
operator and a separate owner authorization.

It runs as root under the release interpreter in the reviewed mb6 BOOT stdin bundle, after the UNCHANGED W10 chain,
the P1B-10R tools, the UNCHANGED W11 verifier (`mb11_signer_verifier`) and the UNCHANGED M-B11 host tail
(`mb11_start_remote`). The owner-side inputs arrive as one generated data module, `e22_transition_evidence` (`DOC`),
never as a host file or a free argument; `main` refuses before any host read unless the argv digest equals the
canonical digest of `DOC` and `DOC.form` equals the form.

    window  OD-M12-11 window marker facts: the journal tail cursor, the boot id and the host UTC instant; nothing else
    post    the M-B11 `post` form (HEALTH only from an exact RUNNING pair, then the W11 judgement) with the W11 release
            working directory set to the release the phase runs from (`release`, bound by the operator: OLD before the
            select, the pinned NEW after it); plus the journal-counted signer invocations after `kActCursor` (the
            M-B11 gate cursor: every K-ACT load since the first) and the witness invocations after `kWitCursor` (the
            V5 window cursor), or null

It never starts, stops, enables or reloads a unit, never reads a credential and never writes.

    window != a load record;  post W11_1 != owner acceptance;  a start != a load (journal-counted, never inferred)
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
from typing import Any, Callable, Iterator, Mapping

import mb11_start_remote as R  # noqa: E402  (BOOT bundle member; the M-B11 host tail, unchanged)

REMOTE_TYPE = "LILITH_E22_TRANSITION_REMOTE"
EVIDENCE_MODULE = "e22_transition_evidence"
FORMS = ("window", "post")
RELEASES = "/opt/lilith-authority-dev/releases/"
WITNESS_SERVICE = "lilith-recovery-witness.service"
BOOT_ID = "/proc/sys/kernel/random/boot_id"
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_LABEL = re.compile(r"V[56]_(OPEN|CLOSE)\Z")
_FIELDS = {"window": frozenset({"form", "label"}),
           "post": frozenset({"form", "release", "post", "kActCursor", "kWitCursor"})}

Refused = R.Refused
canonical = R.canonical
evidence_digest = R.evidence_digest
evidence_module_source = R.evidence_module_source


def _cursor(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and not any(c.isspace() for c in value)


def check_evidence(doc: Any, form: str) -> Mapping[str, Any]:
    if form not in FORMS or not isinstance(doc, Mapping) or set(doc) != _FIELDS[form] or doc.get("form") != form:
        raise Refused("EVIDENCE_NOT_EXACT")
    if form == "window":
        if not isinstance(doc["label"], str) or _LABEL.fullmatch(doc["label"]) is None:
            raise Refused("EVIDENCE_LABEL_INVALID")
        return doc
    if not isinstance(doc["release"], str) or _SHA40.fullmatch(doc["release"]) is None:
        raise Refused("EVIDENCE_RELEASE_INVALID")
    if not _cursor(doc["kActCursor"]) or not (doc["kWitCursor"] is None or _cursor(doc["kWitCursor"])):
        raise Refused("EVIDENCE_CURSOR_INVALID")
    R.check_evidence(doc["post"], "post")
    return doc


# ------------------------------------------------------------------ host facts ---

def boot_id(path: str = BOOT_ID) -> str | None:
    try:
        with open(path, encoding="ascii") as handle:
            value = handle.read().strip().replace("-", "")
    except (OSError, UnicodeDecodeError):
        return None
    return value if re.fullmatch(r"[0-9a-f]{32}", value) else None


def unit_invocations(unit: str, cursor: str, *, W: Any, run: Callable[..., Any] = subprocess.run) -> dict[str, Any]:
    """The invocations of `unit` after `cursor` (the W11 verifier's journal parser, unchanged). UNKNOWN, never empty."""
    if not _cursor(cursor):
        return {"readable": False, "invocations": [], "reason": "CURSOR_INVALID"}
    result = run([W.JOURNALCTL, "-u", unit, "-o", "json", "--no-pager", "--quiet", "--after-cursor=" + cursor],
                 env=W.FIXED_ENV, capture_output=True, text=True, timeout=60, check=False)
    if result.returncode != 0:
        return {"readable": False, "invocations": [], "reason": f"JOURNALCTL_EXIT_{result.returncode}"}
    return W.parse_journal(result.stdout.splitlines())


@contextlib.contextmanager
def release_of_phase(W: Any, release: str) -> Iterator[None]:
    """The W11 verifier's release binding (the signer's resolved WorkingDirectory) for the release of this phase."""
    saved = W.RELEASE_SHA, W.RELEASE_CWD
    W.RELEASE_SHA, W.RELEASE_CWD = release, RELEASES + release
    try:
        yield
    finally:
        W.RELEASE_SHA, W.RELEASE_CWD = saved


# --------------------------------------------------------------------- forms ---

def run_form(doc: Mapping[str, Any], *, root: Any = "/", W: Any = None, tail: Callable[[], str | None] | None = None,
             boot: Callable[[], str | None] | None = None, clock: Callable[[], str] | None = None,
             kact: Callable[[str], dict] | None = None, kwit: Callable[[str], dict] | None = None,
             **post_seams: Any) -> dict[str, Any]:
    """One read-only form. Every keyword argument is a TEST seam (`post_seams` go to `mb11_start_remote.run_form`)."""
    out: dict[str, Any] = {"remoteType": REMOTE_TYPE, "schemaVersion": 1, "form": doc["form"],
                           "evidenceSha256": evidence_digest(doc)}
    if doc["form"] == "window":
        out.update(label=doc["label"], journalCursor=(tail or R.journal_tail)(), bootId=(boot or boot_id)(),
                   observedAt=(clock or R.utc_now)())
        return out
    if W is None:
        import mb11_signer_verifier as W  # noqa: N811
    with release_of_phase(W, doc["release"]):
        out["w11"] = R.run_form(doc["post"], root=root, W=W, **post_seams)
    out["release"] = doc["release"]
    out["kActInvocations"] = (kact or W.journal_invocations)(doc["kActCursor"])
    out["kWitInvocations"] = None if doc["kWitCursor"] is None else \
        (kwit or (lambda cursor: unit_invocations(WITNESS_SERVICE, cursor, W=W)))(doc["kWitCursor"])
    return out


def main(argv: list[str]) -> int:
    try:
        if len(argv) != 2 or argv[0] not in FORMS:
            raise Refused("USAGE")
        module = sys.modules.get(EVIDENCE_MODULE)
        doc = check_evidence(getattr(module, "DOC", None), argv[0])
        if evidence_digest(doc) != argv[1]:
            raise Refused("EVIDENCE_DIGEST_MISMATCH")
        import mb6_ledger_verifier as V6

        V6.require_dev_root()
        if V6.RELEASE_TREE not in sys.path:
            sys.path.insert(0, V6.RELEASE_TREE)
        result = run_form(doc)
    except Refused as exc:
        print(f"e22_transition_remote: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - e.g. mb6_ledger_verifier.Refused (NOT_ROOT / NOT_DEV_HOST)
        print(f"e22_transition_remote: REFUSED {getattr(exc, 'reason', type(exc).__name__)}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
