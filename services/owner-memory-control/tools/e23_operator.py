#!/usr/bin/env python3
"""Track B E-23: the owner-laptop operator of `UPGRADE_E23_PRIVACY_ANCHOR_DEV_SYNTHETIC` (E0 … E8).

Record: docs/architecture/trackb-e23-transition.md. SOURCE ONLY: no form below is authorized by this repository. Every
mutation needs its own verbatim owner go (`render`), consumed by an `O_EXCL` marker written BEFORE its one remote
invocation: no retry, no second invocation path, no automatic stop or start, no rollback, no repair. A step runs only
after every earlier step was consumed and reached its phase, from a fresh read-only gate in exactly its pre-phase.

It reuses, unchanged, the E-22 operator (`e22_operator.Operator`): its pinned DEV-only transport (the IAP route for a
plain command and the pinned-host-key route for a BOOT bundle, both refusing any host but lilith-dev-01), the marker,
the records, the E-22 tool-pin check, and the reviewed signer / witness stop and start commands. New here: the E-23 host tail (`e23_release_stages`) and the acceptance judgement (`verify`).

| Form | Effect |
| --- | --- |
| `pins <repo>` | local: clean control checkout; every pinned tool exact (the E-22 chain and the E-23 tools) |
| `status <repo> <workdir> <label>` | read-only DEV: `e23-status`, the E-phase re-judged locally |
| `preflight <repo> <workdir>` | read-only DEV: E0 exact (DEV_SYNTHETIC host, OLD only, pinned NEW, the E-22 accepted signer and witness, OLD witness units); records the baseline |
| `render <repo> <workdir> <STEP\\|ACCEPT_WITNESS\\|ACCEPT_SIGNER>` | local: the exact owner text |
| `stage <repo> <workdir> <go>` | **mutation** E0 -> E1: `e23-stage` (NEW beside OLD) |
| `stop-signer <repo> <workdir> <go>` | **mutation** E1 -> E2: the signer stop, once |
| `stop-witness <repo> <workdir> <go>` | **mutation** E2 -> E3: the witness stop (service + both sockets), once |
| `select <repo> <workdir> <go>` | **mutation** E3 -> E4: `e23-select` (current -> NEW) |
| `witness-units <repo> <workdir> <go>` | **mutation** E4 -> E5: `e23-witness-units`; the K-PAN credential must already exist |
| `start-witness <repo> <workdir> <go>` | **mutation** E5 -> E6: the witness start, once (one K-WIT and one K-PAN load) |
| `verify <repo> <workdir> <WITNESS\\|SIGNER>` | read-only DEV, E6 / E7: the replacement against the preflight baseline |
| `accept-witness <repo> <workdir> <statement>` | local: the owner's verbatim witness acceptance |
| `start-signer <repo> <workdir> <go>` | **mutation** E6 -> E7: the signer service start, once (one K-ACT load) |
| `accept-signer <repo> <workdir> <statement>` | local: the owner's verbatim signer acceptance |
| `retire <repo> <workdir> <go>` | **mutation** E7 -> E8: `e23-retire-old`, both accepted replacements named |

    status != classification != permission;  VERIFIED != accepted (the owner's verbatim statement);  E8 != Privacy active
"""

from __future__ import annotations

import base64
import gzip
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import e22_operator as E22OP  # noqa: E402  (pinned E-22 operator; transport, marker, records, unit commands)
import e23_privacy_anchor_upgrade as E23  # noqa: E402  (the merged, pinned contract)

M9, M6, X = E22OP.M9, E22OP.M6, E22OP.X
Stop = E22OP.Stop
_need = E22OP._need
sha256_hex = E22OP.sha256_hex

T = E22OP.T
OPERATOR = T + "e23_operator.py"
CONTRACT = T + "e23_privacy_anchor_upgrade.py"
STAGES = T + "e23_release_stages.py"
TOOL_PINS = {
    E22OP.OPERATOR: "7a04d4567ea6d8ea5d4f9074ba4d61d51beeb17cd61c366edfcaddfa8ba3452b",
    CONTRACT: "8d3b7baa2552d6268af19deed385348311da0c3777b5e0747538b1807a69301a",
    STAGES: "2f9e80f06c1f10f8a73d260f0e24da73615e176736fd66dead44e9a2f922a0f3",
}
ALL_PINS = {**E22OP.TOOL_PINS, **TOOL_PINS}
# The E-23 stages run with the byte-unchanged installer V1, the E-19 and E-22 contracts and stage tools (reused host
# reads and signer rule) and the E-23 contract, under the system interpreter (as every installer stage).
STAGES_BUNDLE = (M9.INSTALLER, X.CONTRACT, X.STAGES, E22OP.CONTRACT, E22OP.STAGES, CONTRACT, STAGES)

OLD = E23.OLD_RELEASE
SIGNER_SERVICE, WITNESS_SERVICE = E22OP.SIGNER_SERVICE, E22OP.WITNESS_SERVICE
SIGNER_STOP_COMMAND = E22OP.SIGNER_STOP_COMMAND
WITNESS_STOP_COMMAND = E22OP.WITNESS_STOP_COMMAND
WITNESS_START_COMMAND = E22OP.WITNESS_START_COMMAND
SIGNER_START_COMMAND = E22OP.SIGNER_START_COMMAND
TRANSFER_DIR = f"/home/{M9.OSLOGIN_USER}/lilith-e23-transfer"
OBS_DIR, PRE_DIR, STEP_DIR, VERIFY_DIR, ACCEPT_DIR = "observations", "preflight", "steps", "verify", "acceptance"
PREFLIGHT_FILE, STEP_FILE, VERIFY_FILE = "PREFLIGHT.json", "STEP.json", "VERIFY.json"
ACCEPTANCE = {"WITNESS": "WITNESS_ACCEPTANCE.json", "SIGNER": "SIGNER_ACCEPTANCE.json"}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def stages_module() -> Any:
    """`e23_release_stages`, locally, for the pure E-phase re-judgement (its installer import needs the ceremony dir)."""
    ceremony = str(HERE.parents[1] / "authority-dev/ceremony")
    if ceremony not in sys.path:
        sys.path.append(ceremony)
    import e23_release_stages as S23  # noqa: N813

    return S23


S = stages_module()
E0, E1, E2, E3, E4, E5, E6, E7, E8 = S.PHASES
# Mutating steps, in order: form -> (step, required pre-phase, expected post-phase, marker).
STEPS = {
    "stage": ("STAGE", E0, E1, "e23-stage"),
    "stop-signer": ("SIGNER_STOP", E1, E2, "e23-signer-stop"),
    "stop-witness": ("WITNESS_STOP", E2, E3, "e23-witness-stop"),
    "select": ("SELECT", E3, E4, "e23-select"),
    "witness-units": ("WITNESS_UNITS", E4, E5, "e23-witness-units"),
    "start-witness": ("WITNESS_START", E5, E6, "e23-witness-start"),
    "start-signer": ("SIGNER_START", E6, E7, "e23-signer-start"),
    "retire": ("RETIRE", E7, E8, "e23-retire"),
}
BY_STEP = {step: (form, pre, post, marker) for form, (step, pre, post, marker) in STEPS.items()}
ORDER = [step for step, _p, _q, _m in STEPS.values()]

GO_COMMON = ("Mode: " + E23.MODE + " (E-23, DEV_SYNTHETIC, lilith-dev-01 only). OLD release {old}; NEW release {new}, "
             "manifest SHA-256 {manifest}, archive SHA-256 {archive}.",
             "Control commit: {control}. Operator: " + OPERATOR + " SHA-256 {operator}.",
             "Preflight record SHA-256: {preflight}. Latest {phase} status SHA-256: {observation}.",
             "Deploy freeze: no Core API, Hermes or broker deploy or restart until E8 or a STOP.")
GO_LINES = {
    "STAGE": ("I authorize E23-GO-STAGE now: stage releases/{new} beside releases/{old} on lilith-dev-01, exactly one "
              "invocation of e23_release_stages e23-stage.",
              "Archive " + TRANSFER_DIR + "/release-{new}.tar.gz and builder stamp " + TRANSFER_DIR
              + "/release-{new}.json, transferred by me.",
              "This authorizes staging only: not a unit stop, the selector change, a unit file change, a credential "
              "load or retirement."),
    "SIGNER_STOP": ("I authorize E23-GO-SIGNER-STOP now: `" + SIGNER_STOP_COMMAND + "`, exactly one invocation.",
                    "It ends the signer incarnation " + " / ".join(S.ENDING_SIGNER_INCARNATION) + "; the service and "
                    "its socket stop in one transaction.",
                    "This authorizes the signer stop only."),
    "WITNESS_STOP": ("I authorize E23-GO-WITNESS-STOP now: `" + WITNESS_STOP_COMMAND + "`, exactly one invocation.",
                     "It ends the witness incarnation " + " / ".join(S.ENDING_WITNESS_INCARNATION) + "; the service "
                     "and both sockets stop in one transaction.",
                     "This authorizes the witness stop only."),
    "SELECT": ("I authorize E23-GO-SELECT now: point current to releases/{new} while the signer and the witness are "
               "stopped, exactly one invocation of e23_release_stages e23-select.",
               "This authorizes the selector change only: not a unit file change, a credential load or retirement."),
    "WITNESS_UNITS": ("I authorize E23-GO-WITNESS-UNITS now: exactly one invocation of e23_release_stages "
                      "e23-witness-units: replace the witness unit and tmpfiles files with releases/{new}'s, "
                      "`systemctl daemon-reload`, and create " + E23.ANCHOR_STATE_DIR + " from the new tmpfiles line.",
                      "The encrypted K-PAN credential " + E23.KPAN_CREDENTIAL_BLOB + " exists (metadata only: inode "
                      "{kpan_ino}, size {kpan_size}); K-WIT is unchanged.",
                      "This authorizes the unit files and reload only: not a unit start, a credential load or "
                      "retirement."),
    "WITNESS_START": ("I authorize E23-GO-WITNESS-START now: `" + WITNESS_START_COMMAND + "`, exactly one invocation; "
                      "exactly one K-WIT and one K-PAN load of the custodied blobs, no automatic retry.",
                      "This authorizes the replacement witness start only: not its acceptance, the signer start or "
                      "retirement."),
    "SIGNER_START": ("I authorize E23-GO-SIGNER-START now: `" + SIGNER_START_COMMAND + "`, exactly one invocation of "
                     "the service start path, never the socket; at most one K-ACT load, no automatic retry.",
                     "Accepted replacement witness {winv} / {wpid}; acceptance SHA-256 {wacc}.",
                     "This authorizes the replacement signer start only: not its acceptance, retirement, authority or "
                     "PROD."),
    "RETIRE": ("I authorize E23-GO-RETIRE now: remove releases/{old}, exactly one invocation of e23_release_stages "
               "e23-retire-old, while the accepted replacements signer {sinv} and witness {winv} run from "
               "releases/{new} and no process uses releases/{old}.",
               "Acceptance SHA-256: witness {wacc}; signer {sacc}.",
               "This authorizes the retirement only: not Privacy activation, K-PAN genesis, First Memory, authority "
               "or PROD."),
}
ACCEPT_LINES = {
    "WITNESS": ("I accept the E-23 replacement witness {inv} / {pid}, running from releases/{new} with the new witness "
                "units, as verified by record SHA-256 {verify}.",
                "One start: K-WIT and K-PAN loaded (credential names {creds}); K-WIT metadata unchanged; the anchor "
                "directory holds no chain version; Core API, Hermes and broker incarnations unchanged.",
                "This accepts the replacement witness only: not the signer start, retirement or Privacy activation."),
    "SIGNER": ("I accept the E-23 replacement signer {inv} / {pid}, running from releases/{new}, as verified by record "
               "SHA-256 {verify}.",
               "One start (one K-ACT load); signer credential names unchanged; the accepted witness unchanged; Core "
               "API, Hermes and broker incarnations unchanged.",
               "This accepts the replacement signer only: not retirement, authority, First Memory or PROD."),
}


def _json(path: Path, reason: str) -> Any:
    try:
        return json.loads(Path(path).read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise Stop(reason) from exc


def unit_identity(report: dict, unit: str) -> tuple[str, str]:
    return E22OP.unit_identity(report, unit)


def judge_acceptance(kind: str, report: dict, baseline: dict, kpan_meta: dict | None,
                     accepted_witness: tuple[str, str] | None) -> list[str]:
    """`[]` only for the exact replacement (WITNESS at E6, SIGNER at E7) with every boundary unchanged."""
    reasons = []
    expected = E6 if kind == "WITNESS" else E7
    if report.get("phase") != expected or report.get("result") != "PASS":
        reasons.append("PHASE:" + str(report.get("phase")))
    if report.get("newManifestSha256") != E23.NEW_MANIFEST_SHA256:
        reasons.append("NEW_MANIFEST_NOT_THE_PIN")
    units = report.get("units") or {}
    witness = units.get(WITNESS_SERVICE) or {}
    if witness.get("InvocationID") in (None, "", S.ENDING_WITNESS_INCARNATION[0]) or witness.get("NRestarts") != "0":
        reasons.append("WITNESS_NOT_ONE_REPLACEMENT_START")
    if report.get("witnessCredentials") != S.WITNESS_CREDENTIALS_NEW:
        reasons.append("WITNESS_CREDENTIALS_NOT_KWIT_AND_KPAN")
    if report.get("kWitMeta") is None or report.get("kWitMeta") != baseline.get("kWitMeta"):
        reasons.append("KWIT_CREDENTIAL_CHANGED")
    if kpan_meta is None or report.get("kPanMeta") != kpan_meta:
        reasons.append("KPAN_CREDENTIAL_CHANGED")
    anchor = report.get("anchor") or {}
    if anchor.get("exact") is not True or anchor.get("chainVersions") != 0:
        reasons.append("ANCHOR_STATE_NOT_EMPTY")
    if report.get("witnessUnits") != "NEW":
        reasons.append("WITNESS_UNITS_NOT_NEW")
    if report.get("foreignUnits") != baseline.get("foreignUnits"):
        reasons.append("FOREIGN_UNIT_INCARNATION_CHANGED")
    if kind == "SIGNER":
        signer = units.get(SIGNER_SERVICE) or {}
        if signer.get("InvocationID") in (None, "", S.ENDING_SIGNER_INCARNATION[0]) or signer.get("NRestarts") != "0":
            reasons.append("SIGNER_NOT_ONE_REPLACEMENT_START")
        if report.get("signerCredentials") != baseline.get("signerCredentials"):
            reasons.append("SIGNER_CREDENTIALS_CHANGED")
        if accepted_witness is None or unit_identity(report, WITNESS_SERVICE) != accepted_witness:
            reasons.append("WITNESS_NOT_THE_ACCEPTED_REPLACEMENT")
    return reasons


@dataclass
class Operator(E22OP.Operator):
    """`new_release` / `new_manifest` default to the merged E-23 pins: TEST seams."""

    new_release: str | None = E23.NEW_RELEASE
    new_manifest: str | None = E23.NEW_MANIFEST_SHA256

    # ------------------------------------------------------------ pinned bytes ---

    def tool_bytes(self, repo: Path, path: str) -> bytes:
        data = self._git(repo, "show", f"HEAD:{path}")
        _need(sha256_hex(data) == ALL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return data

    def pins(self, repo: Path) -> dict:
        """The E-22 chain exactly as the E-22 operator checks it, then the E-23 tools and this operator."""
        chain = super().pins(repo)
        for path in TOOL_PINS:
            self.tool_bytes(repo, path)
        operator = sha256_hex(self._git(repo, "show", f"HEAD:{OPERATOR}"))
        _need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")
        for module, path in ((E22OP, E22OP.OPERATOR), (E23, CONTRACT), (S, STAGES)):
            _need(sha256_hex(Path(module.__file__).read_bytes()) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return {"control": chain["control"], "operatorSha256": operator, "tools": dict(ALL_PINS),
                "result": "E23_TOOL_PINS_EXACT"}

    def _new_release(self) -> tuple[str, str]:
        new, manifest = self.new_release, self.new_manifest
        _need(new == E23.NEW_RELEASE and manifest == E23.NEW_MANIFEST_SHA256 and isinstance(new, str)
              and M6._SHA40.fullmatch(new) is not None and new != OLD
              and isinstance(manifest, str) and _HEX64.fullmatch(manifest) is not None, "NEW_RELEASE_NOT_THE_E23_PIN")
        return new, manifest

    def bundled(self, repo: Path, paths: Sequence[str], args: str,
                interpreter: str = M9.SYSTEM_PYTHON) -> tuple[str, bytes]:
        """The reviewed mb6 BOOT stdin bundle (`e22_operator.bundled`), pinned by this operator's table."""
        sources = {Path(path).stem: self.tool_bytes(repo, path).decode("utf-8") for path in paths}
        payload = base64.b64encode(gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0))
        pins = ",".join(f"{Path(path).stem}={ALL_PINS[path]}" for path in paths)
        boot = base64.b64encode(M6.BOOT.encode("ascii")).decode("ascii")
        loader = f"import base64;exec(base64.b64decode('{boot}'))"
        command = (f"B=$(cat); printf %s \"$B\" | sha256sum | cut -c1-64 | grep -qx '{sha256_hex(payload)}' || exit 96; "
                   f"printf %s \"$B\" | base64 -d | sudo -n {interpreter} -I -B -c \"{loader}\" "
                   f"{pins} {Path(paths[-1]).stem} {args}")
        return command, payload + b"\n"

    # ------------------------------------------------------------ read-only DEV ---

    def judge_status(self, raw: bytes, code: int | None, new: str) -> tuple[str, dict | None]:
        """The E-phase of one `e23-status` report, re-judged locally (the pure `e23_release_stages.phase`)."""
        try:
            report = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return "STATUS_NOT_RECEIVED", None
        if code not in (0, 1) or not isinstance(report, dict) or report.get("mode") != E23.MODE \
                or (report.get("oldRelease"), report.get("newRelease")) != (OLD, new):
            return "STATUS_NOT_RECEIVED", None
        try:
            local = S.phase(report)
        except (KeyError, TypeError, AttributeError, ValueError):
            return "STATUS_MALFORMED", report
        if local != report.get("phase") or (local in S.PHASES and (report.get("result"), code) != ("PASS", 0)):
            return "STATUS_REJUDGED_DIFFERENTLY", report
        return local, report

    def _status(self, repo: Path, workdir: Path, label: str) -> tuple[Path, str, dict | None]:
        new, _ = self._new_release()
        out = self._new_numbered(Path(workdir) / OBS_DIR, label)
        command, stdin = self.bundled(repo, STAGES_BUNDLE, f"e23-status {OLD} {new}")
        code = self._save(out, "status", self._invoke_once(command, stdin))
        phase, report = self.judge_status((out / "status.out").read_bytes(), code, new)
        self._record(out / "VERDICT.json", {"phase": phase, "code": code,
                                            "statusSha256": sha256_hex((out / "status.out").read_bytes())})
        return out, phase, report

    def status(self, repo: Path, workdir: Path, label: str) -> dict:
        self.pins(repo)
        _need(re.fullmatch(r"[0-9A-Za-z_]{1,24}", label) is not None, "LABEL_INVALID")
        out, phase, report = self._status(repo, workdir, label)
        return {"observationDir": out.name, "phase": phase, "kPan": None if report is None else report.get("kPan"),
                "result": "E23_STATUS_" + ("E_PHASE" if phase in S.PHASES else "STOP")}

    def _latest_status(self, workdir: Path, phase: str) -> tuple[Path, dict, str]:
        """The latest recorded status, required to be exactly `phase` (re-judged from its retained bytes)."""
        directory = Path(workdir) / OBS_DIR
        runs = sorted(directory.iterdir()) if directory.is_dir() else []
        _need(bool(runs), "NO_STATUS")
        raw = (runs[-1] / "status.out").read_bytes()
        verdict = _json(runs[-1] / "VERDICT.json", "VERDICT_INVALID")
        _need(verdict.get("phase") == phase and verdict.get("statusSha256") == sha256_hex(raw),
              f"LATEST_STATUS_NOT_{phase}:{verdict.get('phase')}")
        judged, report = self.judge_status(raw, verdict.get("code"), self._new_release()[0])
        _need(judged == phase, "STATUS_REJUDGED_DIFFERENTLY")
        return runs[-1], report, verdict["statusSha256"]

    def preflight(self, repo: Path, workdir: Path) -> dict:
        """E0: OLD only, the E-22 accepted signer and witness, OLD witness units, the pinned NEW; the baseline every
        later verification compares against (K-WIT / K-PAN metadata, signer credential names, foreign units)."""
        self.pins(repo)
        _need(not (Path(workdir) / M6.ATTEMPT_DIR / "e23-stage.json").exists(), "ATTEMPT_ALREADY_CONSUMED:e23-stage")
        status_dir, phase, report = self._status(repo, workdir, "PREFLIGHT")
        reasons = [] if phase == E0 else ["STATUS:" + phase]
        report = report or {}
        if (report.get("kWitMeta") or {}).get("kind") != "file":
            reasons.append("KWIT_CREDENTIAL_MISSING")
        if unit_identity(report, SIGNER_SERVICE) != S.ENDING_SIGNER_INCARNATION \
                or unit_identity(report, WITNESS_SERVICE) != S.ENDING_WITNESS_INCARNATION:
            reasons.append("NOT_THE_E22_ACCEPTED_INCARNATIONS")
        out = self._new_numbered(Path(workdir) / PRE_DIR, "E0")
        record = {"status": status_dir.name, "reasons": reasons, "kPan": report.get("kPan"),
                  "kWitMeta": report.get("kWitMeta"), "kPanMeta": report.get("kPanMeta"),
                  "signerCredentials": report.get("signerCredentials"), "foreignUnits": report.get("foreignUnits"),
                  "statusSha256": sha256_hex((status_dir / "status.out").read_bytes()),
                  "result": "E23_PREFLIGHT_" + ("EXACT" if not reasons else "STOP")}
        self._record(out / PREFLIGHT_FILE, record)
        nxt = ("STOP: owner adjudication; no stop, restart or repair" if reasons else
               "nothing is authorized; staging needs the separate E23-GO-STAGE" + (
                   "" if report.get("kPan") == "PRESENT_EXACT" else
                   "; WITNESS_UNITS also needs the K-PAN credential first (trackb_kpan_keygen, its own owner go)"))
        return dict(record, next=nxt)

    def _preflight(self, workdir: Path) -> tuple[dict, str]:
        directory = Path(workdir) / PRE_DIR
        runs = sorted(directory.iterdir()) if directory.is_dir() else []
        _need(bool(runs), "NO_PREFLIGHT")
        raw = (runs[-1] / PREFLIGHT_FILE).read_bytes()
        record = json.loads(raw)
        _need(record.get("result") == "E23_PREFLIGHT_EXACT", "LATEST_PREFLIGHT_NOT_EXACT")
        return record, sha256_hex(raw)

    # ------------------------------------------------------------------ steps ---

    def _step_record(self, workdir: Path, step: str) -> dict | None:
        """The one consumed step that reached its phase (or None if it never ran); anything else is a STOP."""
        _, _, post, marker = BY_STEP[step]
        consumed = (Path(workdir) / M6.ATTEMPT_DIR / f"{marker}.json").exists()
        directory = Path(workdir) / STEP_DIR
        runs = sorted(p for p in directory.iterdir() if p.name.endswith("-" + step)) if directory.is_dir() else []
        if not consumed and not runs:
            return None
        _need(consumed and len(runs) == 1, "STEP_NOT_EXACTLY_ONE:" + step)
        record = _json(runs[0] / STEP_FILE, "STEP_INVALID:" + step)
        _need(record.get("result") == f"E23_{step}_REACHED_{post}", "STEP_NOT_REACHED:" + step)
        return record

    def _acceptance(self, workdir: Path, kind: str) -> tuple[dict, str] | None:
        path = Path(workdir) / ACCEPT_DIR / ACCEPTANCE[kind]
        if not path.is_file():
            return None
        raw = path.read_bytes()
        record = _json(path, "ACCEPTANCE_INVALID")
        _need(record.get("verifySha256") == self._latest_verify(workdir, kind)[1]
              and record.get("statement") == self._accept_text(workdir, kind).decode("ascii"),
              "ACCEPTANCE_NOT_THE_LATEST_VERIFY")
        return record, sha256_hex(raw)

    def _go_values(self, workdir: Path, step: str, pins: dict, new: str, manifest: str) -> dict:
        _, pre, _, _ = BY_STEP[step]
        for earlier in ORDER[:ORDER.index(step)]:
            _need(self._step_record(workdir, earlier) is not None, "EARLIER_STEP_NOT_REACHED:" + earlier)
        preflight = self._preflight(workdir)[1]
        _, report, observation = self._latest_status(workdir, pre)
        values = {"old": OLD, "new": new, "manifest": manifest, "archive": E23.NEW_RELEASE_ATTESTATION["archiveSha256"],
                  "control": pins["control"], "operator": pins["operatorSha256"],
                  "preflight": preflight, "phase": pre, "observation": observation}
        if step == "WITNESS_UNITS":
            _need(report.get("kPan") == "PRESENT_EXACT", "KPAN_CREDENTIAL_REQUIRED_BEFORE_WITNESS_UNITS")
            values.update(kpan_ino=report["kPanMeta"]["ino"], kpan_size=report["kPanMeta"]["size"])
        if step in ("SIGNER_START", "RETIRE"):
            witness = self._acceptance(workdir, "WITNESS")
            _need(witness is not None, "WITNESS_ACCEPTANCE_REQUIRED")
            values.update(winv=witness[0]["invocationId"], wpid=witness[0]["mainPid"], wacc=witness[1])
        if step == "RETIRE":
            signer = self._acceptance(workdir, "SIGNER")
            _need(signer is not None, "SIGNER_ACCEPTANCE_REQUIRED")
            values.update(sinv=signer[0]["invocationId"], sacc=signer[1])
        return values

    def _go_text(self, workdir: Path, step: str, pins: dict, new: str, manifest: str) -> str:
        values = self._go_values(workdir, step, pins, new, manifest)
        return "\n".join(line.format(**values) for line in GO_LINES[step] + GO_COMMON) + "\n"

    def _step(self, repo: Path, workdir: Path, step: str, go_file: Path) -> dict:
        """One owner go, one fresh read-only gate, one marker, ONE remote invocation, one read-only post status."""
        pins = self.pins(repo)
        new, manifest = self._new_release()
        _, pre, post_phase, marker = BY_STEP[step]
        _need(not (Path(workdir) / M6.ATTEMPT_DIR / f"{marker}.json").exists(), "ATTEMPT_ALREADY_CONSUMED:" + marker)
        raw = Path(go_file).read_bytes()
        _need(raw == self._go_text(workdir, step, pins, new, manifest).encode("ascii"), "GO_NOT_CANONICAL")
        values = self._go_values(workdir, step, pins, new, manifest)
        gate, phase, report = self._status(repo, workdir, f"{step}_PRE")                 # read-only, before the marker
        _need(phase == pre, f"GATE_NOT_{pre}:{phase}")
        if step == "WITNESS_UNITS":
            _need(report.get("kPan") == "PRESENT_EXACT"
                  and (report["kPanMeta"]["ino"], report["kPanMeta"]["size"]) == (values["kpan_ino"], values["kpan_size"]),
                  "KPAN_CREDENTIAL_NOT_THE_GO_CREDENTIAL")
        if step in ("SIGNER_START", "RETIRE"):
            _need(unit_identity(report, WITNESS_SERVICE) == (values["winv"], values["wpid"]),
                  "RUNNING_WITNESS_NOT_THE_ACCEPTED_REPLACEMENT")
        if step == "RETIRE":
            _need(unit_identity(report, SIGNER_SERVICE)[0] == values["sinv"], "RUNNING_SIGNER_NOT_THE_ACCEPTED_REPLACEMENT")
        command, stdin = self._command(repo, step, new, manifest, values)
        out = self._new_numbered(Path(workdir) / STEP_DIR, step)
        self._one_attempt(workdir, marker, raw)                                           # the go is consumed HERE
        code = self._save(out, marker, self._invoke_once(command, stdin))
        post_dir, phase, _ = self._status(repo, workdir, f"{step}_POST")
        reached = code == 0 and phase == post_phase
        record = {"step": step, "marker": marker, "goSha256": sha256_hex(raw), "gate": gate.name, "code": code,
                  "post": post_dir.name, "postPhase": phase, "expected": post_phase,
                  "kPanMeta": report.get("kPanMeta") if step == "WITNESS_UNITS" else None,
                  "result": f"E23_{step}_" + ("REACHED_" + post_phase if reached else "STOP")}
        self._record(out / STEP_FILE, record)
        return dict(record, next="nothing further is authorized by this; the next step needs its own owner go"
                    if reached else "STOP: no retry, no automatic stop or start; read-only re-observation and owner "
                                    "adjudication")

    def _command(self, repo: Path, step: str, new: str, manifest: str, values: dict) -> tuple[str, bytes | None]:
        plain = {"SIGNER_STOP": SIGNER_STOP_COMMAND, "WITNESS_STOP": WITNESS_STOP_COMMAND,
                 "WITNESS_START": WITNESS_START_COMMAND, "SIGNER_START": SIGNER_START_COMMAND}
        if step in plain:
            return plain[step], None
        args = {"STAGE": f"e23-stage {OLD} {new} {manifest} {TRANSFER_DIR}/release-{new}.tar.gz "
                         f"{TRANSFER_DIR}/release-{new}.json",
                "SELECT": f"e23-select {OLD} {new}",
                "WITNESS_UNITS": f"e23-witness-units {OLD} {new}",
                "RETIRE": f"e23-retire-old {OLD} {new} {values.get('sinv')} {values.get('winv')}"}[step]
        return self.bundled(repo, STAGES_BUNDLE, args)

    # ------------------------------------------------------------- verification ---

    def verify(self, repo: Path, workdir: Path, kind: str) -> dict:
        """Read-only: the replacement (WITNESS at E6, SIGNER at E7) against the preflight baseline."""
        self.pins(repo)
        self._new_release()
        _need(kind in ACCEPTANCE, "KIND_INVALID")
        baseline, _ = self._preflight(workdir)
        units = self._step_record(workdir, "WITNESS_UNITS")
        _need(units is not None and self._step_record(workdir, "WITNESS_START") is not None, "WITNESS_NOT_STARTED")
        accepted = None
        if kind == "SIGNER":
            _need(self._step_record(workdir, "SIGNER_START") is not None, "SIGNER_NOT_STARTED")
            witness = self._acceptance(workdir, "WITNESS")
            _need(witness is not None, "WITNESS_ACCEPTANCE_REQUIRED")
            accepted = (witness[0]["invocationId"], witness[0]["mainPid"])
        status_dir, phase, report = self._status(repo, workdir, "VERIFY_" + kind)
        reasons = judge_acceptance(kind, report or {}, baseline, units["kPanMeta"], accepted)
        identity = unit_identity(report or {}, WITNESS_SERVICE if kind == "WITNESS" else SIGNER_SERVICE)
        out = self._new_numbered(Path(workdir) / VERIFY_DIR, kind)
        record = {"kind": kind, "status": status_dir.name, "phase": phase, "reasons": reasons,
                  "invocationId": identity[0], "mainPid": identity[1], "release": self._new_release()[0],
                  "witnessCredentials": (report or {}).get("witnessCredentials"),
                  "statusSha256": sha256_hex((status_dir / "status.out").read_bytes()),
                  "result": f"E23_{kind}_" + ("VERIFIED" if not reasons else "STOP")}
        data = self._record(out / VERIFY_FILE, record)
        return dict(record, verifySha256=sha256_hex(data),
                    next=f"the owner's verbatim statement (`render ACCEPT_{kind}`); nothing is accepted by this"
                    if not reasons else "STOP: owner adjudication; no stop, restart or repair")

    def _latest_verify(self, workdir: Path, kind: str) -> tuple[dict, str]:
        directory = Path(workdir) / VERIFY_DIR
        runs = sorted(p for p in directory.iterdir() if p.name.endswith("-" + kind)) if directory.is_dir() else []
        _need(bool(runs), f"NO_{kind}_VERIFY")
        raw = (runs[-1] / VERIFY_FILE).read_bytes()
        return json.loads(raw), sha256_hex(raw)

    def _accept_text(self, workdir: Path, kind: str) -> bytes:
        report, digest = self._latest_verify(workdir, kind)
        _need(report.get("result") == f"E23_{kind}_VERIFIED", f"{kind}_NOT_VERIFIED")
        values = {"inv": report["invocationId"], "pid": report["mainPid"], "new": self._new_release()[0],
                  "verify": digest, "creds": ",".join(report.get("witnessCredentials") or [])}
        return ("\n".join(line.format(**values) for line in ACCEPT_LINES[kind]) + "\n").encode("ascii")

    def render(self, repo: Path, workdir: Path, what: str) -> dict:  # type: ignore[override]
        pins = self.pins(repo)
        new, manifest = self._new_release()
        if what in ("ACCEPT_WITNESS", "ACCEPT_SIGNER"):
            text = self._accept_text(workdir, what.split("_", 1)[1])
        else:
            _need(what in BY_STEP, "RENDER_INVALID")
            text = self._go_text(workdir, what, pins, new, manifest).encode("ascii")
        return {"text": text.decode("ascii"), "textSha256": sha256_hex(text)}

    def _accept(self, repo: Path, workdir: Path, kind: str, statement: Path) -> dict:
        self.pins(repo)
        _need(self._acceptance(workdir, kind) is None, f"{kind}_ALREADY_ACCEPTED")
        raw = Path(statement).read_bytes()
        _need(raw == self._accept_text(workdir, kind), "STATEMENT_NOT_CANONICAL")
        report, digest = self._latest_verify(workdir, kind)
        directory = Path(workdir) / ACCEPT_DIR
        directory.mkdir(mode=0o700, exist_ok=True)
        try:
            data = self._record(directory / ACCEPTANCE[kind], {
                "kind": kind, "statement": raw.decode("ascii"), "verifySha256": digest,
                "invocationId": report["invocationId"], "mainPid": report["mainPid"]})
        except FileExistsError as exc:
            raise Stop(f"{kind}_ALREADY_ACCEPTED") from exc
        nxt = {"WITNESS": "the signer start needs the separate E23-GO-SIGNER-START",
               "SIGNER": "retiring OLD needs the separate E23-GO-RETIRE"}[kind]
        return {"acceptanceSha256": sha256_hex(data), "invocationId": report["invocationId"],
                "result": f"E23_{kind}_ACCEPTANCE_RECORDED", "next": "nothing is authorized; " + nxt}


USAGE = __doc__.split("| Form |", 1)[1].split("\n\n", 1)[0]


def main(argv: Sequence[str], operator: Operator | None = None) -> int:
    operator = operator or Operator()
    forms = {
        ("pins", 1): lambda a: operator.pins(Path(a[0])),
        ("status", 3): lambda a: operator.status(Path(a[0]), Path(a[1]), a[2]),
        ("preflight", 2): lambda a: operator.preflight(Path(a[0]), Path(a[1])),
        ("render", 3): lambda a: operator.render(Path(a[0]), Path(a[1]), a[2]),
        ("verify", 3): lambda a: operator.verify(Path(a[0]), Path(a[1]), a[2]),
        ("accept-witness", 3): lambda a: operator._accept(Path(a[0]), Path(a[1]), "WITNESS", Path(a[2])),
        ("accept-signer", 3): lambda a: operator._accept(Path(a[0]), Path(a[1]), "SIGNER", Path(a[2])),
        **{(form, 3): (lambda step: lambda a: operator._step(Path(a[0]), Path(a[1]), step, Path(a[2])))(step)
           for form, (step, _p, _q, _m) in STEPS.items()},
    }
    form = forms.get((argv[0], len(argv) - 1)) if argv else None
    if form is None:
        print("e23_operator: USAGE" + USAGE, file=sys.stderr)
        return 2
    try:
        result = form(list(argv[1:]))
    except (Stop, E23.Refused) as exc:
        print(f"e23_operator: STOP {getattr(exc, 'code', None) or exc}", file=sys.stderr)
        return 1
    if argv[0] == "render":
        sys.stdout.write(result["text"])
        print(f"TEXT_SHA256={result['textSha256']}", file=sys.stderr)
        return 0
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
