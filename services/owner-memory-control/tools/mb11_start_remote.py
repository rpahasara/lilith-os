#!/usr/bin/env python3
"""15B2b-B1b-3e M-B11 (START_SIGNER): the READ-ONLY host side of `mb11_operator.py` (the tail of its BOOT bundle).

Record: docs/architecture/slice-15b2b-b1b3e-mb11-signer-start-operator.md. SOURCE ONLY: running it on DEV needs the
operator and a separate owner authorization.

It runs as root under the release interpreter in the reviewed mb6 BOOT stdin bundle, after the UNCHANGED W10 chain,
the P1B-10R tools and the UNCHANGED W11 verifier (`mb11_signer_verifier.py`). The owner-side inputs arrive as one
generated data module, `mb11_start_evidence` (`DOC`, pinned in the bundle like every other module), never as a host
file or a free argument; `main` refuses before any host read unless the argv digest equals the canonical digest of
`DOC` and `DOC.form` equals the form.

    gate    the W11 judgement with no HEALTH, no first load recorded, the journal from its start (cursor None) and
            the ledger DB bytes observed here as the baseline; plus the journal tail cursor taken BEFORE the judgement
    post    the HEALTH capture (only from an exact RUNNING incarnation, bound to its InvocationID / MainPID before
            and after), then the W11 judgement over the go-bound baseline with the first load recorded
    current the release's own canonical CURRENT observation (`lilith_authority_root.observers.observe_current_blob`,
            `to_dict` form: lstat identity + ciphertext SHA-256, never decrypted) and the host UTC instant; no W11
            judgement, no HEALTH, no socket, no unit query

It never starts, stops, enables or reloads a unit, never reads a credential and never writes. The one socket it may
open is the signer owner socket, through the release's own `lilith_authority_root.clients.signer_health`, and only
while `systemctl show` reports the service active / running and the socket active (an owner-socket connection while
the service is inactive could start it and load K-ACT; with the P1B-10R boundary the socket is not listening then).

    gate W11_0 != a go;  post W11_1 != owner acceptance;  HEALTH (B4) = a signer claim;  UNKNOWN != success
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from typing import Any, Callable, Mapping

REMOTE_TYPE = "LILITH_MB11_START_REMOTE"
EVIDENCE_MODULE = "mb11_start_evidence"
FORMS = ("gate", "post", "current")
JOURNALCTL = "/usr/bin/journalctl"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
SIGNER_USER = "lilith-authority-dev"
_EVIDENCE_FIELDS = {
    "gate": frozenset({"form", "expectedHead", "candidateDigest", "updatedAt", "witness", "ownerInputs"}),
    "post": frozenset({"form", "expectedHead", "candidateDigest", "updatedAt", "witness", "ownerInputs", "baseline"}),
    "current": frozenset({"form"}),
}


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def evidence_digest(doc: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(doc)).hexdigest()


def evidence_module_source(doc: Mapping[str, Any]) -> str:
    """The generated data module the operator adds to the bundle. Pure data: one JSON literal, parsed by `json`."""
    return "import json\nDOC = json.loads(" + repr(canonical(doc).decode("ascii")) + ")\n"


def check_evidence(doc: Any, form: str) -> Mapping[str, Any]:
    if form not in FORMS or not isinstance(doc, Mapping) or set(doc) != _EVIDENCE_FIELDS[form] or doc.get("form") != form:
        raise Refused("EVIDENCE_NOT_EXACT")
    if form == "current":
        return doc
    witness = doc["witness"]
    if not (isinstance(witness, list) and len(witness) == 2 and all(isinstance(v, str) and v for v in witness)):
        raise Refused("EVIDENCE_WITNESS_INVALID")
    if form == "post":
        baseline = doc["baseline"]
        if not isinstance(baseline, Mapping) or set(baseline) != {"dbSha256", "journalCursor"} \
                or not all(isinstance(v, str) and v for v in baseline.values()):
            raise Refused("EVIDENCE_BASELINE_INVALID")
    return doc


# ------------------------------------------------------------------ host facts ---

def journal_tail(run: Callable[..., Any] = subprocess.run) -> str | None:
    """The cursor of the newest journal entry (the e19 observer's form). None is UNKNOWN."""
    result = run([JOURNALCTL, "-n", "1", "-o", "json", "--no-pager", "--quiet"], env=FIXED_ENV, capture_output=True,
                 text=True, timeout=60, check=False)
    try:
        cursor = json.loads(result.stdout.strip().splitlines()[-1]).get("__CURSOR") if result.returncode == 0 else None
    except (ValueError, IndexError, AttributeError):
        return None
    return cursor if isinstance(cursor, str) and cursor and not any(c.isspace() for c in cursor) else None


def signer_ids() -> list[int] | None:
    import pwd

    try:
        entry = pwd.getpwnam(SIGNER_USER)
    except KeyError:
        return None
    return [entry.pw_uid, entry.pw_gid]


def _incarnation(units: Callable, W: Any) -> tuple[dict[str, str] | None, bool]:
    """(the service InvocationID / MainPID, whether the service and socket are an exact RUNNING pair)."""
    try:
        facts = units(W.SIGNER_UNITS)
        service, sock = facts[W.SIGNER_SERVICE], facts[W.SIGNER_SOCKET_UNIT]
    except Exception:  # noqa: BLE001 - unreadable units are UNKNOWN; nothing connects
        return None, False
    current = {"InvocationID": str(service.get("InvocationID", "")), "MainPID": str(service.get("MainPID", ""))}
    running = (service.get("ActiveState"), service.get("SubState"), sock.get("ActiveState")) == \
        ("active", "running", "active") and sock.get("SubState") in ("listening", "running") \
        and len(current["InvocationID"]) == 32 and current["MainPID"] not in ("", "0")
    return current, running


def capture_health(*, units: Callable, health: Callable[[], Mapping[str, Any]], W: Any) -> dict[str, Any]:
    """One HEALTH frame (OD-M11-5: one capture, reused for E and F), bound before and after to one incarnation.
    Nothing connects unless the service and socket are an exact RUNNING pair."""
    before, running = _incarnation(units, W)
    if not running:
        return {"before": before, "after": None, "health": None, "attempted": False}
    try:
        value = dict(health())
        error = None
    except Exception as exc:  # noqa: BLE001 - a refused or failed capture is recorded, never success
        value, error = None, type(exc).__name__
    after, _ = _incarnation(units, W)
    out = {"before": before, "after": after, "health": value, "attempted": True}
    if error is not None:
        out["error"] = error
    return out


# --------------------------------------------------------------------- forms ---

def observe_current(root: Any) -> tuple[dict[str, Any], str]:
    """(the release observer's canonical CURRENT document, the observer module path). Read-only; never decrypted."""
    from lilith_authority_root import observers as O

    return O.observe_current_blob(root).to_dict(), str(O.__file__)


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_form(doc: Mapping[str, Any], *, root: Any = "/", W: Any = None, units: Callable | None = None,
             health: Callable[[], Mapping[str, Any]] | None = None, tail: Callable[[], str | None] | None = None,
             ids: Callable[[], list[int] | None] | None = None, current: Callable | None = None,
             clock: Callable[[], str] | None = None, **seams: Any) -> dict[str, Any]:
    """One read-only form. `W`, `units`, `health`, `tail`, `ids`, `current`, `clock` and `seams` (forwarded to
    `W.evaluate`) are TEST seams."""
    from pathlib import Path

    if doc["form"] == "current":
        before = (clock or utc_now)()
        observed, module = (current or observe_current)(Path(root))
        until = (clock or utc_now)()
        return {"remoteType": REMOTE_TYPE, "schemaVersion": 1, "form": "current",
                "evidenceSha256": evidence_digest(doc),
                "report": {"current": observed, "observedAt": before, "observedUntil": until, "observersModule": module}}
    if W is None:
        import mb11_signer_verifier as W  # noqa: N811
    root = Path(root)
    form = doc["form"]
    unit_reader = units or W._units
    evidence: dict[str, Any] = {"expectedHead": doc["expectedHead"], "candidateDigest": doc["candidateDigest"],
                                "updatedAt": doc["updatedAt"], "ownerInputs": doc["ownerInputs"],
                                "signerIds": (ids or signer_ids)()}
    out: dict[str, Any] = {"remoteType": REMOTE_TYPE, "schemaVersion": 1, "form": form,
                           "evidenceSha256": evidence_digest(doc)}
    if form == "gate":
        cursor = (tail or journal_tail)()
        ledger = W.observe_ledger_bytes(root)
        evidence.update(baseline={"dbSha256": ledger.get("dbSha256"), "witnessInvocationId": doc["witness"][0],
                                  "witnessMainPid": doc["witness"][1], "journalCursor": None},
                        firstLoadRecorded=False, healthCapture=None)
        out["journalCursor"] = cursor
        out["ledgerDbSha256"] = ledger.get("dbSha256")
    else:
        if health is None:
            from lilith_authority_root import clients

            health = clients.signer_health
        capture = capture_health(units=unit_reader, health=health, W=W)
        evidence.update(baseline={"dbSha256": doc["baseline"]["dbSha256"], "witnessInvocationId": doc["witness"][0],
                                  "witnessMainPid": doc["witness"][1],
                                  "journalCursor": doc["baseline"]["journalCursor"]},
                        firstLoadRecorded=True, healthCapture=capture)
        out["healthCaptureAttempted"] = capture["attempted"]
    out["report"] = W.evaluate(evidence, root=root, units=units, **seams)
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
        print(f"mb11_start_remote: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - e.g. mb6_ledger_verifier.Refused (NOT_ROOT / NOT_DEV_HOST)
        print(f"mb11_start_remote: REFUSED {getattr(exc, 'reason', type(exc).__name__)}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
