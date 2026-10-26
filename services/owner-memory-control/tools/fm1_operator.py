#!/usr/bin/env python3
"""First Memory FM-1: the owner-laptop operator for `UPGRADE_FM1_FIRST_MEMORY_SIGNER_DEV_SYNTHETIC` (SOURCE ONLY).

Record: docs/architecture/first-memory-fm1-release-transition.md. No form below is authorized by this repository.

It is the E-23 operator (`e23_operator.py`, unchanged) moved to the FM-1 contract and stage tool: the same E-22
transport, marker, record, go / acceptance machinery and unit commands; the E-22 order without E-23's witness-units
step (the witness payload and host unit files do not change). The witness is stopped before the select and started
again from NEW, under its own owner go, because its unit follows the shared `current` selector with
`Restart=on-failure`; a witness left on OLD could restart into NEW unapproved.

| Form | Effect |
| --- | --- |
| `pins <repo>` | local: clean control checkout; every pinned tool exact (the E-22 / E-23 chain and the FM-1 tools) |
| `status <repo> <workdir> <label>` | read-only DEV: `fm1-status`, the F-phase re-judged locally |
| `preflight <repo> <workdir>` | read-only DEV: F0 exact (OLD only, the E-23 accepted signer and witness, K-WIT and K-PAN present, installed witness units, the anchor directory); records the baseline |
| `render <repo> <workdir> <STEP\\|ACCEPT_WITNESS\\|ACCEPT_SIGNER>` | local: the exact owner text |
| `stage <repo> <workdir> <go>` | **mutation** F0 -> F1: `fm1-stage` (NEW beside OLD) |
| `stop-signer <repo> <workdir> <go>` | **mutation** F1 -> F2: the signer stop, once |
| `stop-witness <repo> <workdir> <go>` | **mutation** F2 -> F3: the witness stop (service + both sockets), once |
| `select <repo> <workdir> <go>` | **mutation** F3 -> F4: `fm1-select` (current -> NEW) |
| `start-witness <repo> <workdir> <go>` | **mutation** F4 -> F5: the unchanged witness start from NEW, once (one K-WIT and one K-PAN load) |
| `verify <repo> <workdir> <WITNESS\\|SIGNER>` | read-only DEV, F5 / F6: the replacement against the preflight baseline |
| `accept-witness <repo> <workdir> <statement>` | local: the owner's verbatim witness acceptance |
| `start-signer <repo> <workdir> <go>` | **mutation** F5 -> F6: the signer service start, once (one K-ACT load) |
| `accept-signer <repo> <workdir> <statement>` | local: the owner's verbatim signer acceptance |
| `retire <repo> <workdir> <go>` | **mutation** F6 -> F7: `fm1-retire-old`, both accepted replacements named, no process on OLD |

    status != classification != permission;  VERIFIED != accepted (the owner's verbatim statement);  F7 != First Memory
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

import e23_operator as E23OP  # noqa: E402  (pinned E-23 operator; its pins, bundle and unit commands, reused)
import fm1_signer_upgrade as FM1  # noqa: E402  (this transition's contract)

E22OP = E23OP.E22OP
M9, M6, X = E22OP.M9, E22OP.M6, E22OP.X
Stop = E22OP.Stop
_need = E22OP._need
sha256_hex = E22OP.sha256_hex

T = E22OP.T
OPERATOR = T + "fm1_operator.py"
CONTRACT = T + "fm1_signer_upgrade.py"
STAGES = T + "fm1_release_stages.py"
TOOL_PINS = {
    E23OP.OPERATOR: "b84ca602c6b49b39396639686275128ad2e39580a1fa1eaf62a70ef83b7a9fdf",
    CONTRACT: "749bd4ee2721682733adf95ee9b670bf86a9671b91370eb6da56f832caf0270b",
    STAGES: "7bb29f88cab4e91484e2a8b373491099f0a5a5197562b29da25a2f4a76d73779",
}
ALL_PINS = {**E23OP.ALL_PINS, **TOOL_PINS}
# The FM-1 stages run with the byte-unchanged installer V1, the E-19 / E-22 / E-23 contracts and stage tools (reused
# host reads, signer rule, K-PAN and anchor facts) and the FM-1 contract, under the system interpreter.
STAGES_BUNDLE = (*E23OP.STAGES_BUNDLE, CONTRACT, STAGES)

OLD = FM1.OLD_RELEASE
SIGNER_SERVICE, WITNESS_SERVICE = E22OP.SIGNER_SERVICE, E22OP.WITNESS_SERVICE
SIGNER_STOP_COMMAND = E22OP.SIGNER_STOP_COMMAND
WITNESS_STOP_COMMAND = E22OP.WITNESS_STOP_COMMAND
WITNESS_START_COMMAND = E22OP.WITNESS_START_COMMAND
SIGNER_START_COMMAND = E22OP.SIGNER_START_COMMAND
TRANSFER_DIR = f"/home/{M9.OSLOGIN_USER}/lilith-fm1-transfer"
OBS_DIR, PRE_DIR, STEP_DIR, VERIFY_DIR, ACCEPT_DIR = "observations", "preflight", "steps", "verify", "acceptance"
PREFLIGHT_FILE, STEP_FILE, VERIFY_FILE = "PREFLIGHT.json", "STEP.json", "VERIFY.json"
ACCEPTANCE = {"WITNESS": "WITNESS_ACCEPTANCE.json", "SIGNER": "SIGNER_ACCEPTANCE.json"}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def stages_module() -> Any:
    """`fm1_release_stages`, locally, for the pure F-phase re-judgement (its installer import needs the ceremony dir)."""
    ceremony = str(HERE.parents[1] / "authority-dev/ceremony")
    if ceremony not in sys.path:
        sys.path.append(ceremony)
    import fm1_release_stages as SF  # noqa: N813

    return SF


S = stages_module()
F0, F1, F2, F3, F4, F5, F6, F7 = S.PHASES
# Mutating steps, in order: form -> (step, required pre-phase, expected post-phase, marker).
STEPS = {
    "stage": ("STAGE", F0, F1, "fm1-stage"),
    "stop-signer": ("SIGNER_STOP", F1, F2, "fm1-signer-stop"),
    "stop-witness": ("WITNESS_STOP", F2, F3, "fm1-witness-stop"),
    "select": ("SELECT", F3, F4, "fm1-select"),
    "start-witness": ("WITNESS_START", F4, F5, "fm1-witness-start"),
    "start-signer": ("SIGNER_START", F5, F6, "fm1-signer-start"),
    "retire": ("RETIRE", F6, F7, "fm1-retire"),
}
BY_STEP = {step: (form, pre, post, marker) for form, (step, pre, post, marker) in STEPS.items()}
ORDER = [step for step, _p, _q, _m in STEPS.values()]
# Owner-adjudicated STOP records (docs/architecture/first-memory-fm1-release-transition.md §4, PROPOSED until merged):
# step -> SHA-256 of its exact consumed `STEP.json`. Such a step counts as reached for the step chain ONLY; it never
# re-runs, and the next step's own fresh gate must still read its post-phase. The 2026-10-26 STAGE STOP was the local
# plink exit crash (0xC0000005) on the post-status read; the remote stage reported F1 and a clean re-read is F1.
ADJUDICATED_STEPS = {"STAGE": "b82b4a5b94451313b84818860a5b8d0e06fc4815c275966c8b35d252f5e7fb4e"}

GO_COMMON = ("Mode: " + FM1.MODE + " (FM-1, DEV_SYNTHETIC, lilith-dev-01 only). OLD release {old}; NEW release {new}, "
             "manifest SHA-256 {manifest}, archive SHA-256 {archive}.",
             "Control commit: {control}. Operator: " + OPERATOR + " SHA-256 {operator}.",
             "Preflight record SHA-256: {preflight}. Latest {phase} status SHA-256: {observation}.",
             "Deploy freeze: no Core API, Hermes or broker deploy or restart until F7 or a STOP. No memory creation.")
GO_LINES = {
    "STAGE": ("I authorize FM1-GO-STAGE now: stage releases/{new} beside releases/{old} on lilith-dev-01, exactly one "
              "invocation of fm1_release_stages fm1-stage.",
              "Archive " + TRANSFER_DIR + "/release-{new}.tar.gz and builder stamp " + TRANSFER_DIR
              + "/release-{new}.json, transferred by me.",
              "This authorizes staging only: not a unit stop, the selector change, a credential load or retirement."),
    "SIGNER_STOP": ("I authorize FM1-GO-SIGNER-STOP now: `" + SIGNER_STOP_COMMAND + "`, exactly one invocation.",
                    "It ends the signer incarnation " + " / ".join(S.ENDING_SIGNER_INCARNATION) + "; the service and "
                    "its socket stop in one transaction.",
                    "This authorizes the signer stop only."),
    "WITNESS_STOP": ("I authorize FM1-GO-WITNESS-STOP now: `" + WITNESS_STOP_COMMAND + "`, exactly one invocation.",
                     "It ends the witness incarnation " + " / ".join(S.ENDING_WITNESS_INCARNATION) + "; the service "
                     "and both sockets stop in one transaction, so it cannot restart across the selector change.",
                     "This authorizes the witness stop only."),
    "SELECT": ("I authorize FM1-GO-SELECT now: point current to releases/{new} while the signer and the witness are "
               "stopped, exactly one invocation of fm1_release_stages fm1-select.",
               "This authorizes the selector change only: not a unit start, a credential load or retirement."),
    "WITNESS_START": ("I authorize FM1-GO-WITNESS-START now: `" + WITNESS_START_COMMAND + "`, exactly one invocation; "
                      "the unchanged witness payload from releases/{new}; exactly one K-WIT and one K-PAN load of the "
                      "custodied blobs (K-WIT inode {kwit_ino}, K-PAN inode {kpan_ino}), no automatic retry.",
                      "This authorizes the replacement witness start only: not its acceptance, the signer start or "
                      "retirement."),
    "SIGNER_START": ("I authorize FM1-GO-SIGNER-START now: `" + SIGNER_START_COMMAND + "`, exactly one invocation of "
                     "the service start path, never the socket; at most one K-ACT load, no automatic retry.",
                     "Accepted replacement witness {winv} / {wpid}; acceptance SHA-256 {wacc}.",
                     "This authorizes the replacement signer start only: not its acceptance, retirement, owner "
                     "registration, memory creation, authority or PROD."),
    "RETIRE": ("I authorize FM1-GO-RETIRE now: remove releases/{old}, exactly one invocation of fm1_release_stages "
               "fm1-retire-old, while the accepted replacements signer {sinv} and witness {winv} run from "
               "releases/{new} and no process uses releases/{old}.",
               "Acceptance SHA-256: witness {wacc}; signer {sacc}.",
               "This authorizes the retirement only: not owner registration, First Memory, authority or PROD."),
}
ACCEPT_LINES = {
    "WITNESS": ("I accept the FM-1 replacement witness {inv} / {pid}, running the unchanged witness payload from "
                "releases/{new}, as verified by record SHA-256 {verify}.",
                "One start: K-WIT and K-PAN loaded (credential names {creds}); K-WIT and K-PAN metadata unchanged; the "
                "Privacy anchor directory unchanged; Core API, Hermes and broker incarnations unchanged.",
                "This accepts the replacement witness only: not the signer start, retirement or First Memory."),
    "SIGNER": ("I accept the FM-1 replacement signer {inv} / {pid}, running from releases/{new}, as verified by record "
               "SHA-256 {verify}.",
               "One start (one K-ACT load); signer credential names unchanged; the accepted witness unchanged; Core "
               "API, Hermes and broker incarnations unchanged.",
               "This accepts the replacement signer only: not retirement, owner registration, memory creation, "
               "authority or PROD."),
}


def _json(path: Path, reason: str) -> Any:
    try:
        return json.loads(Path(path).read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise Stop(reason) from exc


def unit_identity(report: dict, unit: str) -> tuple[str, str]:
    return E22OP.unit_identity(report, unit)


def judge_acceptance(kind: str, report: dict, baseline: dict, accepted_witness: tuple[str, str] | None) -> list[str]:
    """`[]` only for the exact replacement (WITNESS at F5, SIGNER at F6) with every boundary unchanged."""
    reasons = []
    expected = F5 if kind == "WITNESS" else F6
    if report.get("phase") != expected or report.get("result") != "PASS":
        reasons.append("PHASE:" + str(report.get("phase")))
    if report.get("newManifestSha256") != FM1.NEW_MANIFEST_SHA256:
        reasons.append("NEW_MANIFEST_NOT_THE_PIN")
    units = report.get("units") or {}
    witness = units.get(WITNESS_SERVICE) or {}
    if witness.get("InvocationID") in (None, "", S.ENDING_WITNESS_INCARNATION[0]) or witness.get("NRestarts") != "0":
        reasons.append("WITNESS_NOT_ONE_REPLACEMENT_START")
    if report.get("witnessCredentials") != S.WITNESS_CREDENTIALS:
        reasons.append("WITNESS_CREDENTIALS_NOT_KWIT_AND_KPAN")
    if report.get("kWitMeta") is None or report.get("kWitMeta") != baseline.get("kWitMeta"):
        reasons.append("KWIT_CREDENTIAL_CHANGED")
    if report.get("kPanMeta") is None or report.get("kPanMeta") != baseline.get("kPanMeta"):
        reasons.append("KPAN_CREDENTIAL_CHANGED")
    if report.get("anchor") is None or report.get("anchor") != baseline.get("anchor"):
        reasons.append("ANCHOR_STATE_CHANGED")
    if report.get("witnessUnits") != "NEW":
        reasons.append("WITNESS_UNITS_NOT_INSTALLED_EXACT")
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
    """`new_release` / `new_manifest` default to the FM-1 contract pins: TEST seams."""

    new_release: str | None = FM1.NEW_RELEASE
    new_manifest: str | None = FM1.NEW_MANIFEST_SHA256

    # ------------------------------------------------------------ pinned bytes ---

    def tool_bytes(self, repo: Path, path: str) -> bytes:
        data = self._git(repo, "show", f"HEAD:{path}")
        _need(sha256_hex(data) == ALL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return data

    def pins(self, repo: Path) -> dict:
        """The E-22 chain exactly as the E-22 operator checks it, then the E-23 and FM-1 tools and this operator."""
        chain = super().pins(repo)
        for path in E23OP.TOOL_PINS | TOOL_PINS:
            self.tool_bytes(repo, path)
        operator = sha256_hex(self._git(repo, "show", f"HEAD:{OPERATOR}"))
        _need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")
        for module, path in ((E23OP, E23OP.OPERATOR), (FM1, CONTRACT), (S, STAGES)):
            _need(sha256_hex(Path(module.__file__).read_bytes()) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return {"control": chain["control"], "operatorSha256": operator, "tools": dict(ALL_PINS),
                "result": "FM1_TOOL_PINS_EXACT"}

    def _new_release(self) -> tuple[str, str]:
        new, manifest = self.new_release, self.new_manifest
        _need(new == FM1.NEW_RELEASE and manifest == FM1.NEW_MANIFEST_SHA256 and isinstance(new, str)
              and M6._SHA40.fullmatch(new) is not None and new != OLD
              and isinstance(manifest, str) and _HEX64.fullmatch(manifest) is not None, "NEW_RELEASE_NOT_THE_FM1_PIN")
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
        """The F-phase of one `fm1-status` report, re-judged locally (the pure `fm1_release_stages.phase`)."""
        try:
            report = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return "STATUS_NOT_RECEIVED", None
        if code not in (0, 1) or not isinstance(report, dict) or report.get("mode") != FM1.MODE \
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
        command, stdin = self.bundled(repo, STAGES_BUNDLE, f"fm1-status {OLD} {new}")
        code = self._save(out, "status", self._invoke_once(command, stdin))
        phase, report = self.judge_status((out / "status.out").read_bytes(), code, new)
        self._record(out / "VERDICT.json", {"phase": phase, "code": code,
                                            "statusSha256": sha256_hex((out / "status.out").read_bytes())})
        return out, phase, report

    def status(self, repo: Path, workdir: Path, label: str) -> dict:
        self.pins(repo)
        _need(re.fullmatch(r"[0-9A-Za-z_]{1,24}", label) is not None, "LABEL_INVALID")
        out, phase, report = self._status(repo, workdir, label)
        return {"observationDir": out.name, "phase": phase,
                "oldReleaseUsers": None if report is None else report.get("oldReleaseUsers"),
                "result": "FM1_STATUS_" + ("F_PHASE" if phase in S.PHASES else "STOP")}

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
        """F0: OLD only, the E-23 accepted signer and witness, K-WIT and K-PAN present, the installed witness units,
        the pinned NEW; the baseline every later verification compares against (credential metadata, anchor
        directory, signer credential names, foreign units)."""
        self.pins(repo)
        _need(not (Path(workdir) / M6.ATTEMPT_DIR / "fm1-stage.json").exists(), "ATTEMPT_ALREADY_CONSUMED:fm1-stage")
        status_dir, phase, report = self._status(repo, workdir, "PREFLIGHT")
        reasons = [] if phase == F0 else ["STATUS:" + phase]
        report = report or {}
        if (report.get("kWitMeta") or {}).get("kind") != "file":
            reasons.append("KWIT_CREDENTIAL_MISSING")
        if report.get("kPan") != "PRESENT_EXACT":
            reasons.append("KPAN_CREDENTIAL_NOT_EXACT")
        if unit_identity(report, SIGNER_SERVICE) != S.ENDING_SIGNER_INCARNATION \
                or unit_identity(report, WITNESS_SERVICE) != S.ENDING_WITNESS_INCARNATION:
            reasons.append("NOT_THE_E23_ACCEPTED_INCARNATIONS")
        out = self._new_numbered(Path(workdir) / PRE_DIR, "F0")
        record = {"status": status_dir.name, "reasons": reasons, "kWitMeta": report.get("kWitMeta"),
                  "kPanMeta": report.get("kPanMeta"), "anchor": report.get("anchor"),
                  "signerCredentials": report.get("signerCredentials"), "foreignUnits": report.get("foreignUnits"),
                  "statusSha256": sha256_hex((status_dir / "status.out").read_bytes()),
                  "result": "FM1_PREFLIGHT_" + ("EXACT" if not reasons else "STOP")}
        self._record(out / PREFLIGHT_FILE, record)
        nxt = ("STOP: owner adjudication; no stop, restart or repair" if reasons else
               "nothing is authorized; staging needs the separate FM1-GO-STAGE")
        return dict(record, next=nxt)

    def _preflight(self, workdir: Path) -> tuple[dict, str]:
        directory = Path(workdir) / PRE_DIR
        runs = sorted(directory.iterdir()) if directory.is_dir() else []
        _need(bool(runs), "NO_PREFLIGHT")
        raw = (runs[-1] / PREFLIGHT_FILE).read_bytes()
        record = json.loads(raw)
        _need(record.get("result") == "FM1_PREFLIGHT_EXACT", "LATEST_PREFLIGHT_NOT_EXACT")
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
        adjudicated = record.get("result") == f"FM1_{step}_STOP" \
            and ADJUDICATED_STEPS.get(step) == sha256_hex((runs[0] / STEP_FILE).read_bytes())
        _need(record.get("result") == f"FM1_{step}_REACHED_{post}" or adjudicated, "STEP_NOT_REACHED:" + step)
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
        preflight, preflight_sha = self._preflight(workdir)
        _, report, observation = self._latest_status(workdir, pre)
        values = {"old": OLD, "new": new, "manifest": manifest, "archive": FM1.NEW_RELEASE_ATTESTATION["archiveSha256"],
                  "control": pins["control"], "operator": pins["operatorSha256"],
                  "preflight": preflight_sha, "phase": pre, "observation": observation}
        if step == "WITNESS_START":
            _need(report.get("kPanMeta") == preflight["kPanMeta"] and report.get("kWitMeta") == preflight["kWitMeta"],
                  "WITNESS_CREDENTIALS_NOT_THE_PREFLIGHT_CREDENTIALS")
            values.update(kwit_ino=report["kWitMeta"]["ino"], kpan_ino=report["kPanMeta"]["ino"])
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
        if step == "WITNESS_START":
            _need((report["kWitMeta"]["ino"], report["kPanMeta"]["ino"]) == (values["kwit_ino"], values["kpan_ino"]),
                  "WITNESS_CREDENTIALS_NOT_THE_GO_CREDENTIALS")
        if step in ("SIGNER_START", "RETIRE"):
            _need(unit_identity(report, WITNESS_SERVICE) == (values["winv"], values["wpid"]),
                  "RUNNING_WITNESS_NOT_THE_ACCEPTED_REPLACEMENT")
        if step == "RETIRE":
            _need(unit_identity(report, SIGNER_SERVICE)[0] == values["sinv"], "RUNNING_SIGNER_NOT_THE_ACCEPTED_REPLACEMENT")
            _need(report.get("oldReleaseUsers") == [], "OLD_RELEASE_IN_USE:" + ",".join(report.get("oldReleaseUsers")
                                                                                          or ["UNKNOWN"]))
        command, stdin = self._command(repo, step, new, manifest, values)
        out = self._new_numbered(Path(workdir) / STEP_DIR, step)
        self._one_attempt(workdir, marker, raw)                                           # the go is consumed HERE
        code = self._save(out, marker, self._invoke_once(command, stdin))
        post_dir, phase, _ = self._status(repo, workdir, f"{step}_POST")
        reached = code == 0 and phase == post_phase
        record = {"step": step, "marker": marker, "goSha256": sha256_hex(raw), "gate": gate.name, "code": code,
                  "post": post_dir.name, "postPhase": phase, "expected": post_phase,
                  "result": f"FM1_{step}_" + ("REACHED_" + post_phase if reached else "STOP")}
        self._record(out / STEP_FILE, record)
        return dict(record, next="nothing further is authorized by this; the next step needs its own owner go"
                    if reached else "STOP: no retry, no automatic stop or start; read-only re-observation and owner "
                                    "adjudication")

    def _command(self, repo: Path, step: str, new: str, manifest: str, values: dict) -> tuple[str, bytes | None]:
        plain = {"SIGNER_STOP": SIGNER_STOP_COMMAND, "WITNESS_STOP": WITNESS_STOP_COMMAND,
                 "WITNESS_START": WITNESS_START_COMMAND, "SIGNER_START": SIGNER_START_COMMAND}
        if step in plain:
            return plain[step], None
        args = {"STAGE": f"fm1-stage {OLD} {new} {manifest} {TRANSFER_DIR}/release-{new}.tar.gz "
                         f"{TRANSFER_DIR}/release-{new}.json",
                "SELECT": f"fm1-select {OLD} {new}",
                "RETIRE": f"fm1-retire-old {OLD} {new} {values.get('sinv')} {values.get('winv')}"}[step]
        return self.bundled(repo, STAGES_BUNDLE, args)

    # ------------------------------------------------------------- verification ---

    def verify(self, repo: Path, workdir: Path, kind: str) -> dict:
        """Read-only: the replacement (WITNESS at F5, SIGNER at F6) against the preflight baseline."""
        self.pins(repo)
        self._new_release()
        _need(kind in ACCEPTANCE, "KIND_INVALID")
        baseline, _ = self._preflight(workdir)
        _need(self._step_record(workdir, "WITNESS_START") is not None, "WITNESS_NOT_STARTED")
        accepted = None
        if kind == "SIGNER":
            _need(self._step_record(workdir, "SIGNER_START") is not None, "SIGNER_NOT_STARTED")
            witness = self._acceptance(workdir, "WITNESS")
            _need(witness is not None, "WITNESS_ACCEPTANCE_REQUIRED")
            accepted = (witness[0]["invocationId"], witness[0]["mainPid"])
        status_dir, phase, report = self._status(repo, workdir, "VERIFY_" + kind)
        reasons = judge_acceptance(kind, report or {}, baseline, accepted)
        identity = unit_identity(report or {}, WITNESS_SERVICE if kind == "WITNESS" else SIGNER_SERVICE)
        out = self._new_numbered(Path(workdir) / VERIFY_DIR, kind)
        record = {"kind": kind, "status": status_dir.name, "phase": phase, "reasons": reasons,
                  "invocationId": identity[0], "mainPid": identity[1], "release": self._new_release()[0],
                  "witnessCredentials": (report or {}).get("witnessCredentials"),
                  "statusSha256": sha256_hex((status_dir / "status.out").read_bytes()),
                  "result": f"FM1_{kind}_" + ("VERIFIED" if not reasons else "STOP")}
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
        _need(report.get("result") == f"FM1_{kind}_VERIFIED", f"{kind}_NOT_VERIFIED")
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
        nxt = {"WITNESS": "the signer start needs the separate FM1-GO-SIGNER-START",
               "SIGNER": "retiring OLD needs the separate FM1-GO-RETIRE (only once no process uses OLD)"}[kind]
        return {"acceptanceSha256": sha256_hex(data), "invocationId": report["invocationId"],
                "result": f"FM1_{kind}_ACCEPTANCE_RECORDED", "next": "nothing is authorized; " + nxt}


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
        print("fm1_operator: USAGE" + USAGE, file=sys.stderr)
        return 2
    try:
        result = form(list(argv[1:]))
    except (Stop, FM1.Refused) as exc:
        print(f"fm1_operator: STOP {getattr(exc, 'code', None) or exc}", file=sys.stderr)
        return 1
    if argv[0] == "render":
        sys.stdout.write(result["text"])
        print(f"TEXT_SHA256={result['textSha256']}", file=sys.stderr)
        return 0
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
