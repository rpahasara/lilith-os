#!/usr/bin/env python3
"""15B2b-B1b-3e M-B12 E-22: the owner-laptop operator of `UPGRADE_E22_JUDGE_DEV_SYNTHETIC` (V0 … V7).

Record: docs/architecture/slice-15b2b-b1b3e-e22-judge-transition.md §6. SOURCE ONLY: no form below is authorized by
this repository. Every mutation needs its own verbatim owner go (`render`), consumed by an `O_EXCL` marker written
BEFORE its one remote invocation: no retry, no second invocation path, no automatic stop, no rollback, no repair.

It reuses, unchanged: the M-B11 operator (`mb11_operator.Operator`, itself the E-19 operator: the pinned `gcloud
compute ssh` route for a plain command, the direct-plink stdin route for the mb6 BOOT bundles, the go check, the
marker, the record helpers, the owner-inputs reader, the accepted-start reader and the POST11 judgement), the W10 chain,
the P1B-10R tools, the W11 verifier, the M-B11 host tail, the E-19 witness denial proofs and their judgement, the
installer and the E-19 stage tool. New here: the E-22 stages (`e22_release_stages`, the merged contract
`e22_judge_upgrade`) and the read-only host tail `e22_transition_remote` (OD-M12-11 window facts; W11 with the phase's
release; journal-counted K-ACT and K-WIT loads).

| Form | Effect |
| --- | --- |
| `pins <repo>` | local: clean control checkout; every pinned tool exact |
| `bind <repo> <workdir> <mb11-workdir>` | local: the accepted M-B11 start (gate, envelope, POST11) re-verified and copied |
| `status <repo> <workdir> <label>` | read-only DEV: `e22-status`, the V-phase re-judged locally |
| `v0 <repo> <workdir>` | read-only DEV: status V0 and the identical M-B11 POST11 (ending signer, one K-ACT load) |
| `render <repo> <workdir> <STEP\\|ACCEPT_WITNESS\\|ACCEPT_SIGNER>` | local: the exact owner text |
| `stage <repo> <workdir> <go>` | **mutation** V0 -> V1: `e22-stage` (NEW beside OLD) |
| `stop-signer <repo> <workdir> <go>` | **mutation** V1 -> V2: `SIGNER_STOP` once (ends c7ba0fb7…/84806) |
| `stop-witness <repo> <workdir> <go>` | **mutation** V2 -> V3: `WITNESS_STOP` once (ends 90b28f9d…/69238) |
| `select <repo> <workdir> <go>` | **mutation** V3 -> V4: `e22-select` (current -> NEW) |
| `start-witness <repo> <workdir> <go>` | **mutation** V4 -> V5: OD-M12-11 window, `WITNESS_START` once (ONE K-WIT load) |
| `post-witness <repo> <workdir> <envelope>` | read-only DEV, V5: the replacement witness POST (W11_1S, one K-WIT load, denials) |
| `accept-witness <repo> <workdir> <statement>` | local: the owner's verbatim witness acceptance |
| `start-signer <repo> <workdir> <go>` | **mutation** V5 -> V6: OD-M12-11 window, `SIGNER_START` once (the SECOND K-ACT load) |
| `post-signer <repo> <workdir> <envelope>` | read-only DEV, V6: the replacement signer POST (W11_1; K-ACT load count 2) |
| `accept-signer <repo> <workdir> <statement>` | local: the owner's verbatim signer acceptance |
| `retire <repo> <workdir> <go>` | **mutation** V6 -> V7: `e22-retire-old`, both accepted replacements named |
| `windows <repo> <workdir>` | local: the two OD-M12-11 windows (boot, cursors, instants, transcript digests) |
| `package <repo> <outdir> <envelope>` | read-only DEV, after V7: the release verifier's HOLD_RELEASE_ELIGIBILITY report (E-01 … E-24, `packageDigest`) over the envelope, in a fresh `<outdir>` |

    status != classification != permission;  one start go != one credential load (journal-counted, never inferred)
    POST VERIFIED != acceptance (the owner's verbatim statement);  V7 != M-B12 PASS

The NEW release identity (`J.NEW_RELEASE`, `J.NEW_MANIFEST_SHA256`) is established only by a later merged owner pin of
the attested build; until then every DEV form refuses (`NEW_RELEASE_NOT_ESTABLISHED`).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
# The owner-inputs reader (`mb12_readiness_inputs`, via `mb11_operator.readiness_tool`) imports `lilith_owner_memory`,
# which imports `lilith_memory` (services/core-api): both come from this checkout, never from the environment.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
for _path in (HERE.parents[1] / "core-api", HERE.parent):
    if str(_path) not in sys.path:
        sys.path.append(str(_path))

import e22_judge_upgrade as J  # noqa: E402  (the merged contract; pinned below)
import e22_transition_remote as Q  # noqa: E402  (pinned below)
import mb11_operator as M11  # noqa: E402  (pinned M-B11 operator; reused unchanged)

X = M11.X                                                           # the E-19 operator
O = X.O                                                             # the E-19 observer (denial judgement only)
M10, M9, M6 = M11.M10, M11.M9, M11.M6
Stop = M11.Stop
_need = M11._need
sha256_hex = M11.sha256_hex

T = M11.T
OPERATOR = T + "e22_operator.py"
MB11_OPERATOR = M11.OPERATOR
CONTRACT = T + "e22_judge_upgrade.py"
STAGES = T + "e22_release_stages.py"
REMOTE = T + "e22_transition_remote.py"
TOOL_PINS = {
    **M11.TOOL_PINS,
    **{path: X.TOOL_PINS[path] for path in (M9.INSTALLER, X.CONTRACT, X.STAGES, X.OBSERVER, *X.DENIALS.values())},
    MB11_OPERATOR: "aa8c93fc1aea676d7888e20b94cc5f471df2663f2dab9c6e82e7956cc97e1256",
    CONTRACT: "505966d4c065a07ab53d7b9a16875b301a04525032ac5b553f8f216f20d21ec9",
    STAGES: "97359e84c89e3e70fd0bcb3d49de1bdc996d04b5233b807adf74b506c06050d2",
    REMOTE: "051416c315b8a3a12986a3cca0a3e03e1d615951f1d8cd7f731922c4b17bc75e",
}
# The E-22 stages run with the byte-unchanged installer, the E-19 contract and stage tool (reused host reads) and the
# E-22 contract, under the system interpreter (as every installer stage).
STAGES_BUNDLE = (M9.INSTALLER, X.CONTRACT, X.STAGES, CONTRACT, STAGES)
# The W11 reads: the M-B11 bundle and host tail, then the generated evidence and the E-22 tail (release interpreter).
W11_BUNDLE = (*M11.BUNDLE, M11.REMOTE)

OLD = J.OLD_RELEASE
V0, V1, V2, V3, V4, V5, V6, V7 = J.PHASES
SIGNER_SERVICE = M11.SIGNER_SERVICE
WITNESS_SERVICE = Q.WITNESS_SERVICE
W11_1, W11_1S, W10_1 = M11.W11_1, "W11_1S_STOPPED_AFTER_FIRST_LOAD", M11.W10_1
LOADED = "LOADED"
SIGNER_STOP_COMMAND = "sudo -n " + J.SIGNER_STOP_COMMAND
WITNESS_STOP_COMMAND = "sudo -n " + J.WITNESS_STOP_COMMAND
WITNESS_START_COMMAND = "sudo -n " + J.WITNESS_START_COMMAND
SIGNER_START_COMMAND = M11.START_SIGNER_COMMAND
TRANSFER_DIR = f"/home/{M9.OSLOGIN_USER}/lilith-e22-transfer"
BIND_DIR, OBS_DIR, V0_DIR, STEP_DIR, POST_DIR, ACCEPT_DIR = "binding", "observations", "v0", "steps", "posts", "acceptance"
BINDING_FILE, V0_FILE, STEP_FILE, WINDOW_FILE, POST_FILE = "BINDING.json", "V0.json", "STEP.json", "WINDOW.json", \
    "POST.json"
ACCEPTANCE = {"WITNESS": "WITNESS_ACCEPTANCE.json", "SIGNER": "SIGNER_ACCEPTANCE.json"}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

# Mutating steps: form -> (step, required pre-phase, expected post-phase, marker).
STEPS = {
    "stage": ("STAGE", V0, V1, "e22-stage"),
    "stop-signer": ("SIGNER_STOP", V1, V2, "e22-signer-stop"),
    "stop-witness": ("WITNESS_STOP", V2, V3, "e22-witness-stop"),
    "select": ("SELECT", V3, V4, "e22-select"),
    "start-witness": ("WITNESS_START", V4, V5, "e22-witness-start"),
    "start-signer": ("SIGNER_START", V5, V6, "e22-signer-start"),
    "retire": ("RETIRE", V6, V7, "e22-retire"),
}
BY_STEP = {step: (form, pre, post, marker) for form, (step, pre, post, marker) in STEPS.items()}
# OD-M12-11: the two credential-load steps, each with its own window (record §2).
WINDOWS = {"WITNESS_START": (V5, "K-WIT"), "SIGNER_START": (V6, "K-ACT")}

GO_COMMON = ("Mode: " + J.MODE + " (E-22, DEV_SYNTHETIC). OLD release {old}; NEW release {new}, manifest SHA-256 "
             "{manifest}.",
             "Control commit: {control}. Operator: " + OPERATOR + " SHA-256 {operator}.",
             "V0 record SHA-256: {v0}. Latest {phase} status SHA-256: {observation}.")
GO_LINES = {
    "STAGE": ("I authorize E22-GO-STAGE now: stage releases/{new} beside releases/{old} on lilith-dev-01, exactly one "
              "invocation of e22_release_stages e22-stage.",
              "Archive " + TRANSFER_DIR + "/release-{new}.tar.gz and builder stamp " + TRANSFER_DIR
              + "/release-{new}.json, transferred by me.",
              "This authorizes staging only: not a unit stop, the selector change, a credential load or retirement."),
    "SIGNER_STOP": ("I authorize E22-GO-SIGNER-STOP now: `" + SIGNER_STOP_COMMAND + "`, exactly one invocation.",
                    "It ends the signer incarnation " + " / ".join(J.ENDING_SIGNER_INCARNATION) + " (one K-ACT load "
                    "so far); the service and its socket stop in one transaction.",
                    "This authorizes the signer stop only: not the witness stop, the selector change, a credential "
                    "load or retirement."),
    "WITNESS_STOP": ("I authorize E22-GO-WITNESS-STOP now: `" + WITNESS_STOP_COMMAND + "`, exactly one invocation.",
                     "It ends the witness incarnation " + " / ".join(J.ENDING_WITNESS_INCARNATION) + "; the service "
                     "and both sockets stop in one transaction.",
                     "This authorizes the witness stop only: not the selector change, a credential load or "
                     "retirement."),
    "SELECT": ("I authorize E22-GO-SELECT now: point current to releases/{new} while the signer and the witness are "
               "stopped, exactly one invocation of e22_release_stages e22-select.",
               "This authorizes the selector change only: not a credential load or retirement."),
    "WITNESS_START": ("I authorize E22-GO-WITNESS-START now: `" + WITNESS_START_COMMAND + "`, exactly one invocation; "
                      "exactly one K-WIT load of the custodied blob, no automatic retry.",
                      "OD-M12-11: this load is its own private-material event; its window is recorded by the operator "
                      "and its transcript retained.",
                      "This authorizes the replacement witness start only: not its acceptance, the signer start or "
                      "retirement."),
    "SIGNER_START": ("I authorize E22-GO-SIGNER-START now: `" + SIGNER_START_COMMAND + "`, exactly one invocation of "
                     "the service start path, never the socket; at most one K-ACT load (the second), no automatic "
                     "retry.",
                     "OD-M12-11: this load is its own private-material event; its window is recorded by the operator "
                     "and its transcript retained.",
                     "Accepted replacement witness {winv} / {wpid}; acceptance SHA-256 {wacc}.",
                     "This authorizes the replacement signer start only: not its acceptance, retirement, M-B12, "
                     "authority or PROD."),
    "RETIRE": ("I authorize E22-GO-RETIRE now: remove releases/{old}, exactly one invocation of e22_release_stages "
               "e22-retire-old, while the accepted replacements signer {sinv} and witness {winv} run from "
               "releases/{new}.",
               "Acceptance SHA-256: witness {wacc}; signer {sacc}.",
               "This authorizes the retirement only: not M-B12, Registry effectiveness, authority, First Memory or "
               "PROD."),
}
ACCEPT_LINES = {
    "WITNESS": ("I accept the E-22 replacement witness {inv} / {pid}, running from releases/{new}, as verified by POST "
                "record SHA-256 {post}.",
                "One K-WIT load, journal-counted in the OD-M12-11 V5 window (record SHA-256 {window}); the signer "
                "stays stopped after exactly one K-ACT load.",
                "This accepts the replacement witness only: not the signer start, retirement, M-B12, authority or "
                "PROD."),
    "SIGNER": ("I accept the E-22 replacement signer {inv} / {pid}, running from releases/{new}, as verified by POST "
               "record SHA-256 {post}.",
               "K-ACT load count {count}, journal-counted after the M-B11 gate cursor; one load in the OD-M12-11 V6 "
               "window (record SHA-256 {window}); HEALTH key {key}.",
               "This accepts the replacement signer only: not retirement, M-B12, Registry effectiveness, authority, "
               "First Memory or PROD."),
}


def _json(path: Path, reason: str) -> Any:
    try:
        return json.loads(Path(path).read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise Stop(reason) from exc


def stages_module() -> Any:
    """`e22_release_stages`, locally, for the pure V-phase re-judgement (its installer import needs the ceremony dir)."""
    ceremony = str(HERE.parents[1] / "authority-dev/ceremony")
    if ceremony not in sys.path:
        sys.path.append(ceremony)
    import e22_release_stages as S22  # noqa: N813

    return S22


def unit_identity(report: dict, unit: str) -> tuple[str, str]:
    service = (report.get("units") or {}).get(unit) or {}
    return str(service.get("InvocationID", "")), str(service.get("MainPID", ""))


def invocation_ids(journal: Any) -> list[str] | None:
    """The journal-counted invocation ids, only when readable and every one LOADED; else None (UNKNOWN)."""
    if not isinstance(journal, dict) or journal.get("readable") is not True:
        return None
    items = journal.get("invocations")
    if not isinstance(items, list) or any(not isinstance(i, dict) or i.get("credentials") != LOADED for i in items):
        return None
    return [str(i.get("id")) for i in items]


def dark(report: dict) -> bool:
    return (report.get("authorityGranted"), report.get("authorityActive"), report.get("registryEffective"),
            report.get("issuanceAuthority")) == (False, False, False, "NONE")


@dataclass
class Operator(M11.Operator):
    """`new_release` / `new_manifest` default to the merged E-22 contract pins (None until the owner pin): TEST seams."""

    new_release: str | None = J.NEW_RELEASE
    new_manifest: str | None = J.NEW_MANIFEST_SHA256

    # ------------------------------------------------------------ pinned bytes ---

    def tool_bytes(self, repo: Path, path: str) -> bytes:
        data = self._git(repo, "show", f"HEAD:{path}")
        _need(sha256_hex(data) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return data

    def pins(self, repo: Path) -> dict:
        status = self._git(repo, "status", "--porcelain", "--untracked-files=no")
        _need(status.strip() == b"", "CONTROL_CHECKOUT_NOT_CLEAN")
        control = self.control(repo)
        for path in TOOL_PINS:
            self.tool_bytes(repo, path)
        operator = sha256_hex(self._git(repo, "show", f"HEAD:{OPERATOR}"))
        _need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")
        for module, path in ((M11, MB11_OPERATOR), (J, CONTRACT), (Q, REMOTE), (M11.R, M11.REMOTE),
                             (X, M11.E19_OPERATOR), (O, X.OBSERVER)):
            _need(sha256_hex(Path(module.__file__).read_bytes()) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return {"control": control, "operatorSha256": operator, "tools": dict(TOOL_PINS), "result": "E22_TOOL_PINS_EXACT"}

    def _new_release(self) -> tuple[str, str]:
        new, manifest = self.new_release, self.new_manifest
        _need(isinstance(new, str) and M6._SHA40.fullmatch(new) is not None and new != OLD
              and isinstance(manifest, str) and _HEX64.fullmatch(manifest) is not None, "NEW_RELEASE_NOT_ESTABLISHED")
        return new, manifest

    def bundled(self, repo: Path, paths: Sequence[str], args: str,
                interpreter: str = M9.RELEASE_PYTHON) -> tuple[str, bytes]:
        """The E-19 operator's BOOT stdin bundle (`e19_operator.bundled`), pinned by this operator's table."""
        import base64
        import gzip

        sources = {Path(path).stem: self.tool_bytes(repo, path).decode("utf-8") for path in paths}
        payload = base64.b64encode(gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0))
        pins = ",".join(f"{Path(path).stem}={TOOL_PINS[path]}" for path in paths)
        boot = base64.b64encode(M6.BOOT.encode("ascii")).decode("ascii")
        loader = f"import base64;exec(base64.b64decode('{boot}'))"
        command = (f"B=$(cat); printf %s \"$B\" | sha256sum | cut -c1-64 | grep -qx '{sha256_hex(payload)}' || exit 96; "
                   f"printf %s \"$B\" | base64 -d | sudo -n {interpreter} -I -B -c \"{loader}\" "
                   f"{pins} {Path(paths[-1]).stem} {args}")
        return command, payload + b"\n"

    def w11_bundle(self, repo: Path, doc: dict) -> tuple[str, bytes]:
        """The reviewed mb6 BOOT stdin bundle: pinned sources, the generated evidence module, then the E-22 tail."""
        import base64
        import gzip

        sources = {Path(path).stem: self.tool_bytes(repo, path).decode("utf-8") for path in W11_BUNDLE}
        sources[Q.EVIDENCE_MODULE] = Q.evidence_module_source(doc)
        sources[Path(REMOTE).stem] = self.tool_bytes(repo, REMOTE).decode("utf-8")
        payload = base64.b64encode(gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0))
        pins = ",".join(f"{name}={sha256_hex(text.encode('utf-8'))}" for name, text in sources.items())
        boot = base64.b64encode(M6.BOOT.encode("ascii")).decode("ascii")
        loader = f"import base64;exec(base64.b64decode('{boot}'))"
        command = (f"B=$(cat); printf %s \"$B\" | sha256sum | cut -c1-64 | grep -qx '{sha256_hex(payload)}' || exit 96; "
                   f"printf %s \"$B\" | base64 -d | sudo -n {M9.RELEASE_PYTHON} -I -B -c \"{loader}\" "
                   f"{pins} {Path(REMOTE).stem} {doc['form']} {Q.evidence_digest(doc)}")
        return command, payload + b"\n"

    def _e22_remote(self, repo: Path, out: Path, name: str, doc: dict) -> dict | None:
        """ONE read-only E-22 tail invocation; the parsed document only if it echoes this exact evidence."""
        Q.check_evidence(doc, doc["form"])
        code = self._save(out, name, self._invoke_once(*self.w11_bundle(repo, doc)))
        try:
            value = json.loads((out / f"{name}.out").read_bytes().decode("utf-8")) if code == 0 else None
        except (UnicodeDecodeError, ValueError):
            value = None
        if not isinstance(value, dict) or value.get("remoteType") != Q.REMOTE_TYPE or value.get("form") != doc["form"] \
                or value.get("evidenceSha256") != Q.evidence_digest(doc):
            return None
        if doc["form"] == "post":
            w11 = value.get("w11")
            if value.get("release") != doc["release"] or not isinstance(w11, dict) \
                    or w11.get("remoteType") != M11.R.REMOTE_TYPE \
                    or w11.get("evidenceSha256") != M11.R.evidence_digest(doc["post"]) \
                    or not isinstance(w11.get("report"), dict):
                return None
        return value

    # ------------------------------------------------------------ the M-B11 binding ---

    def bind(self, repo: Path, workdir: Path, mb11_workdir: Path) -> dict:
        """Copy the accepted M-B11 start (re-verified by the M-B11 reader) into the E-22 workdir, once."""
        self.pins(repo)
        latest, gate, start, post = self._accepted_start(Path(mb11_workdir))
        signer = unit_identity(((post.get("report") or {}).get("observation") or {}), SIGNER_SERVICE)
        _need(signer == J.ENDING_SIGNER_INCARNATION, "MB11_SIGNER_NOT_THE_ENDING_INCARNATION")
        directory = Path(workdir) / BIND_DIR
        _need(not directory.exists(), "ALREADY_BOUND")
        directory.mkdir(mode=0o700, parents=True)
        envelope = (latest / M11.ENVELOPE_FILE).read_bytes()
        step = next(p for p in (Path(mb11_workdir) / M11.STEP_DIR).iterdir() if p.name.endswith("-START"))
        post_raw = (step / "post.out").read_bytes()
        _need(sha256_hex(post_raw) == start["postSha256"], "MB11_POST_CHANGED")
        (directory / M11.ENVELOPE_FILE).write_bytes(envelope)
        (directory / "mb11-post.out").write_bytes(post_raw)
        record = {"gateCursor": gate["journalCursor"], "dbSha256": gate["dbSha256"], "envelopeSha256": gate["envelopeSha256"],
                  "mb11PostSha256": start["postSha256"], "mb11GoSha256": start["goSha256"], "signer": list(signer),
                  "healthPublicKeySha256": post["report"].get("healthPublicKeySha256"),
                  "result": "E22_BOUND_TO_THE_ACCEPTED_MB11_START"}
        data = self._record(directory / BINDING_FILE, record)
        return dict(record, bindingSha256=sha256_hex(data))

    def _binding(self, workdir: Path) -> tuple[dict, bytes, dict]:
        """(binding record, the M-B11 gate envelope bytes, the M-B11 POST11 document), digests re-checked."""
        directory = Path(workdir) / BIND_DIR
        _need((directory / BINDING_FILE).is_file(), "NOT_BOUND")
        record = _json(directory / BINDING_FILE, "BINDING_INVALID")
        envelope = (directory / M11.ENVELOPE_FILE).read_bytes()
        post = (directory / "mb11-post.out").read_bytes()
        _need(sha256_hex(envelope) == record["envelopeSha256"] and sha256_hex(post) == record["mb11PostSha256"]
              and tuple(record["signer"]) == J.ENDING_SIGNER_INCARNATION, "BINDING_EVIDENCE_CHANGED")
        return record, envelope, json.loads(post)

    def _post_doc(self, inputs: dict, witness: Sequence[str], db: str, cursor: str) -> dict:
        doc = self._doc("post", inputs, {"dbSha256": db, "journalCursor": cursor})
        doc["witness"] = list(witness)
        return doc

    # ------------------------------------------------------------ read-only DEV ---

    def judge_status(self, raw: bytes, code: int | None, new: str) -> tuple[str, dict | None]:
        """The V-phase of one `e22-status` report, re-judged locally (the pure `e22_release_stages.phase`)."""
        try:
            report = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return "STATUS_NOT_RECEIVED", None
        if code not in (0, 1) or not isinstance(report, dict) or report.get("mode") != J.MODE \
                or (report.get("oldRelease"), report.get("newRelease")) != (OLD, new):
            return "STATUS_NOT_RECEIVED", None
        try:
            local = stages_module().phase(report)
        except (KeyError, TypeError, AttributeError, ValueError):
            return "STATUS_MALFORMED", report
        if local != report.get("phase") or (local in J.PHASES and (report.get("result"), code) != ("PASS", 0)):
            return "STATUS_REJUDGED_DIFFERENTLY", report
        return local, report

    def _status(self, repo: Path, workdir: Path, label: str) -> tuple[Path, str, dict | None]:
        new, _ = self._new_release()
        out = self._new_numbered(Path(workdir) / OBS_DIR, label)
        command, stdin = self.bundled(repo, STAGES_BUNDLE, f"e22-status {OLD} {new}", M9.SYSTEM_PYTHON)
        code = self._save(out, "status", self._invoke_once(command, stdin))
        phase, report = self.judge_status((out / "status.out").read_bytes(), code, new)
        self._record(out / "VERDICT.json", {"phase": phase, "code": code,
                                            "statusSha256": sha256_hex((out / "status.out").read_bytes())})
        return out, phase, report

    def status(self, repo: Path, workdir: Path, label: str) -> dict:
        self.pins(repo)
        _need(re.fullmatch(r"[0-9A-Za-z_]{1,24}", label) is not None, "LABEL_INVALID")
        out, phase, _ = self._status(repo, workdir, label)
        return {"observationDir": out.name, "phase": phase, "result": "E22_STATUS_" + ("V_PHASE" if phase in J.PHASES
                                                                                    else "STOP")}

    def _latest_status(self, workdir: Path, phase: str) -> tuple[Path, dict, str]:
        """The latest recorded status, required to be exactly `phase` (re-judged from its retained bytes)."""
        directory = Path(workdir) / OBS_DIR
        runs = sorted(directory.iterdir()) if directory.is_dir() else []
        _need(bool(runs), "NO_STATUS")
        latest = runs[-1]
        raw = (latest / "status.out").read_bytes()
        verdict = _json(latest / "VERDICT.json", "VERDICT_INVALID")
        _need(verdict.get("phase") == phase and verdict.get("statusSha256") == sha256_hex(raw),
              f"LATEST_STATUS_NOT_{phase}:{verdict.get('phase')}")
        judged, report = self.judge_status(raw, verdict.get("code"), self._new_release()[0])
        _need(judged == phase, "STATUS_REJUDGED_DIFFERENTLY")
        return latest, report, verdict["statusSha256"]

    def v0(self, repo: Path, workdir: Path) -> dict:
        """V0: status V0 and the identical M-B11 POST11 (the accepted M-B11 `observe` judgement), both now."""
        self.pins(repo)
        binding, envelope, accepted = self._binding(workdir)
        _need(not (Path(workdir) / M6.ATTEMPT_DIR / "e22-stage.json").exists(), "ATTEMPT_ALREADY_CONSUMED:e22-stage")
        status_dir, phase, _ = self._status(repo, workdir, "V0")
        out = self._new_numbered(Path(workdir) / V0_DIR, "V0")
        doc = self._doc("post", self.owner_inputs(envelope), {"dbSha256": binding["dbSha256"],
                                                               "journalCursor": binding["gateCursor"]})
        _need(M11.R.evidence_digest(doc) == accepted.get("evidenceSha256"), "V0_DOC_NOT_THE_ACCEPTED_POST11")
        remote = self._e22_remote(repo, out, "remote", {"form": "post", "release": OLD, "post": doc,
                                                         "kActCursor": binding["gateCursor"], "kWitCursor": None})
        reasons = [] if phase == V0 else ["STATUS:" + phase]
        reasons += self.judge_observe(None if remote is None else remote["w11"], accepted)
        if remote is not None and invocation_ids(remote["kActInvocations"]) != [J.ENDING_SIGNER_INCARNATION[0]]:
            reasons.append("KACT_LOADS_NOT_EXACTLY_THE_MB11_LOAD")
        record = {"status": status_dir.name, "v0": out.name, "reasons": reasons, "kActLoadCount": 1 if not reasons
                  else None, "observationSha256": sha256_hex((out / "remote.out").read_bytes()),
                  "result": "E22_V0_" + ("EXACT" if not reasons else "STOP")}
        self._record(out / V0_FILE, record)
        return dict(record, next="nothing is authorized; staging needs the separate E22-GO-STAGE"
                    if not reasons else "STOP: owner adjudication; no stop, restart or repair")

    def _latest_v0(self, workdir: Path) -> str:
        directory = Path(workdir) / V0_DIR
        runs = sorted(directory.iterdir()) if directory.is_dir() else []
        _need(bool(runs), "NO_V0")
        raw = (runs[-1] / V0_FILE).read_bytes()
        _need(json.loads(raw).get("result") == "E22_V0_EXACT", "LATEST_V0_NOT_EXACT")
        return sha256_hex(raw)

    # ------------------------------------------------------------------ owner texts ---

    def _acceptance(self, workdir: Path, kind: str) -> tuple[dict, str] | None:
        path = Path(workdir) / ACCEPT_DIR / ACCEPTANCE[kind]
        if not path.is_file():
            return None
        raw = path.read_bytes()
        record = _json(path, "ACCEPTANCE_INVALID")
        post = self._latest_post(workdir, kind)
        _need(record.get("postSha256") == post[1] and record.get("statement")
              == self._accept_text(workdir, kind).decode("ascii"), "ACCEPTANCE_NOT_THE_LATEST_POST")
        return record, sha256_hex(raw)

    def _go_values(self, workdir: Path, step: str, pins: dict, new: str, manifest: str) -> dict:
        _, pre, _, _ = BY_STEP[step]
        _, _, observation = self._latest_status(workdir, pre)
        values = {"old": OLD, "new": new, "manifest": manifest, "control": pins["control"],
                  "operator": pins["operatorSha256"], "v0": self._latest_v0(workdir), "phase": pre,
                  "observation": observation}
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

    def _accept_text(self, workdir: Path, kind: str) -> bytes:
        report, digest = self._latest_post(workdir, kind)
        _need(report.get("result") == f"E22_{kind}_POST_VERIFIED", f"{kind}_POST_NOT_VERIFIED")
        values = {"inv": report["invocationId"], "pid": report["mainPid"], "new": self._new_release()[0],
                  "post": digest, "window": report["windowSha256"], "count": report.get("kActLoadCount"),
                  "key": report.get("healthPublicKeySha256")}
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
        report, digest = self._latest_post(workdir, kind)
        directory = Path(workdir) / ACCEPT_DIR
        directory.mkdir(mode=0o700, exist_ok=True)
        try:
            data = self._record(directory / ACCEPTANCE[kind], {
                "kind": kind, "statement": raw.decode("ascii"), "postSha256": digest,
                "invocationId": report["invocationId"], "mainPid": report["mainPid"],
                "kActLoadCount": report.get("kActLoadCount"), "windowSha256": report["windowSha256"]})
        except FileExistsError as exc:
            raise Stop(f"{kind}_ALREADY_ACCEPTED") from exc
        nxt = {"WITNESS": "the signer start needs the separate E22-GO-SIGNER-START",
               "SIGNER": "retiring OLD needs the separate E22-GO-RETIRE"}[kind]
        return {"acceptanceSha256": sha256_hex(data), "invocationId": report["invocationId"],
                "result": f"E22_{kind}_ACCEPTANCE_RECORDED", "next": "nothing is authorized; " + nxt}

    def accept_witness(self, repo: Path, workdir: Path, statement: Path) -> dict:
        return self._accept(repo, workdir, "WITNESS", statement)

    def accept_signer(self, repo: Path, workdir: Path, statement: Path) -> dict:
        return self._accept(repo, workdir, "SIGNER", statement)

    # --------------------------------------------------------------------- mutations ---

    def _window(self, repo: Path, out: Path, label: str) -> dict | None:
        remote = self._e22_remote(repo, out, "window-" + label.split("_")[1].lower(), {"form": "window", "label": label})
        if remote is None or not Q._cursor(remote.get("journalCursor")) or not isinstance(remote.get("bootId"), str) \
                or not isinstance(remote.get("observedAt"), str):
            return None
        return {k: remote[k] for k in ("journalCursor", "bootId", "observedAt")}

    def _step(self, repo: Path, workdir: Path, step: str, go_file: Path) -> dict:
        """One owner go, one fresh read-only gate, (window open,) one marker, ONE remote invocation, (window close,)
        one read-only post status."""
        pins = self.pins(repo)
        new, manifest = self._new_release()
        _, pre, post_phase, marker = BY_STEP[step]
        raw = Path(go_file).read_bytes()
        _need(raw == self._go_text(workdir, step, pins, new, manifest).encode("ascii"), "GO_NOT_CANONICAL")
        _need(not (Path(workdir) / M6.ATTEMPT_DIR / f"{marker}.json").exists(), "ATTEMPT_ALREADY_CONSUMED:" + marker)
        values = self._go_values(workdir, step, pins, new, manifest)
        gate, phase, report = self._status(repo, workdir, f"{step}_PRE")                # read-only, before the marker
        _need(phase == pre, f"GATE_NOT_{pre}:{phase}")
        if step in ("SIGNER_START", "RETIRE"):
            _need(unit_identity(report, WITNESS_SERVICE) == (values["winv"], values["wpid"]),
                  "RUNNING_WITNESS_NOT_THE_ACCEPTED_REPLACEMENT")
        if step == "RETIRE":
            _need(unit_identity(report, SIGNER_SERVICE)[0] == values["sinv"], "RUNNING_SIGNER_NOT_THE_ACCEPTED_REPLACEMENT")
        command, stdin = self._command(repo, step, new, manifest, values)
        out = self._new_numbered(Path(workdir) / STEP_DIR, step)
        opened = None
        if step in WINDOWS:
            opened = self._window(repo, out, f"{WINDOWS[step][0][:2]}_OPEN")
            _need(opened is not None, "WINDOW_NOT_OPENED")                               # still before the marker
        self._one_attempt(workdir, marker, raw)                                          # the go is consumed HERE
        code = self._save(out, marker, self._invoke_once(command, stdin))
        window_ok = True
        if step in WINDOWS:
            closed = self._window(repo, out, f"{WINDOWS[step][0][:2]}_CLOSE")
            window_ok = closed is not None and closed["bootId"] == opened["bootId"]
            transcript = {p.name: sha256_hex(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()}
            self._record(out / WINDOW_FILE, {
                "decision": "OD-M12-11", "event": WINDOWS[step][1], "phase": WINDOWS[step][0], "marker": marker,
                "goSha256": sha256_hex(raw), "open": opened, "close": closed, "sameBoot": window_ok,
                "transcript": transcript, "retained": True, "joinsCeremoniesTable": False})
        post_dir, phase, _ = self._status(repo, workdir, f"{step}_POST")
        reached = code == 0 and phase == post_phase and window_ok
        record = {"step": step, "marker": marker, "goSha256": sha256_hex(raw), "gate": gate.name, "code": code,
                  "post": post_dir.name, "postPhase": phase, "expected": post_phase,
                  "window": WINDOW_FILE if step in WINDOWS else None,
                  "result": f"E22_{step}_" + ("REACHED_" + post_phase if reached else "STOP")}
        self._record(out / STEP_FILE, record)
        return dict(record, next="nothing further is authorized by this; the next step needs its own owner go"
                    if reached else "STOP: no retry, no automatic stop; read-only re-observation and owner adjudication")

    def _command(self, repo: Path, step: str, new: str, manifest: str, values: dict) -> tuple[str, bytes | None]:
        plain = {"SIGNER_STOP": SIGNER_STOP_COMMAND, "WITNESS_STOP": WITNESS_STOP_COMMAND,
                 "WITNESS_START": WITNESS_START_COMMAND, "SIGNER_START": SIGNER_START_COMMAND}
        if step in plain:
            return plain[step], None
        if step == "STAGE":
            args = (f"e22-stage {OLD} {new} {manifest} {TRANSFER_DIR}/release-{new}.tar.gz "
                    f"{TRANSFER_DIR}/release-{new}.json")
        elif step == "SELECT":
            args = f"e22-select {OLD} {new}"
        else:
            args = f"e22-retire-old {OLD} {new} {values['sinv']} {values['winv']}"
        return self.bundled(repo, STAGES_BUNDLE, args, M9.SYSTEM_PYTHON)

    # ------------------------------------------------------------------ POSTs ---

    def _window_record(self, workdir: Path, step: str) -> tuple[dict, str]:
        """The one consumed load step that reached its phase, and its OD-M12-11 window (bytes re-checked)."""
        _, _, post_phase, marker = BY_STEP[step]
        _need((Path(workdir) / M6.ATTEMPT_DIR / f"{marker}.json").exists(), "STEP_NOT_CONSUMED:" + step)
        directory = Path(workdir) / STEP_DIR
        steps = sorted(p for p in directory.iterdir() if p.name.endswith("-" + step)) if directory.is_dir() else []
        _need(len(steps) == 1, "STEP_NOT_EXACTLY_ONE:" + step)
        record = _json(steps[0] / STEP_FILE, "STEP_INVALID")
        _need(record.get("result") == f"E22_{step}_REACHED_{post_phase}", "STEP_NOT_REACHED:" + step)
        raw = (steps[0] / WINDOW_FILE).read_bytes()
        window = json.loads(raw)
        _need(window.get("sameBoot") is True and all(sha256_hex((steps[0] / name).read_bytes()) == digest
                                                     for name, digest in window["transcript"].items()),
              "WINDOW_TRANSCRIPT_CHANGED:" + step)
        return window, sha256_hex(raw)

    def _post(self, repo: Path, workdir: Path, kind: str, envelope: Path) -> dict:
        self.pins(repo)
        new, _ = self._new_release()
        binding, _, accepted = self._binding(workdir)
        expected_phase = V5 if kind == "WITNESS" else V6
        status_dir, phase, report = self._status(repo, workdir, f"POST_{kind}")
        kwit_window, kwit_sha = self._window_record(workdir, "WITNESS_START")
        reasons = [] if phase == expected_phase else ["STATUS:" + phase]
        witness = unit_identity(report or {}, WITNESS_SERVICE)
        signer = unit_identity(report or {}, SIGNER_SERVICE)
        if kind == "SIGNER":
            window, window_sha = self._window_record(workdir, "SIGNER_START")
            accepted_witness = self._acceptance(workdir, "WITNESS")
            _need(accepted_witness is not None, "WITNESS_ACCEPTANCE_REQUIRED")
            if witness != (accepted_witness[0]["invocationId"], accepted_witness[0]["mainPid"]):
                reasons.append("WITNESS_NOT_THE_ACCEPTED_REPLACEMENT")
            cursor = window["open"]["journalCursor"]                     # W11 counts the one load of this window
        else:
            window, window_sha, cursor = kwit_window, kwit_sha, binding["gateCursor"]   # signer stopped after load 1
        raw = Path(envelope).read_bytes()
        out = self._new_numbered(Path(workdir) / POST_DIR, kind)
        (out / M11.ENVELOPE_FILE).write_bytes(raw)
        doc = self._post_doc(self.owner_inputs(raw), witness, binding["dbSha256"], cursor)
        remote = self._e22_remote(repo, out, "remote", {"form": "post", "release": new, "post": doc,
                                                         "kActCursor": binding["gateCursor"],
                                                         "kWitCursor": kwit_window["open"]["journalCursor"]})
        if remote is None:
            reasons.append("POST_NOT_RECEIVED")
            w11, kact, kwit = {}, None, None
        else:
            w11 = remote["w11"]["report"]
            kact, kwit = invocation_ids(remote["kActInvocations"]), invocation_ids(remote["kWitInvocations"])
            reasons += self.judge_post(kind, w11, remote["w11"].get("healthCaptureAttempted"), witness, signer,
                                       accepted)
            if kwit != [witness[0]]:
                reasons.append("KWIT_LOADS_NOT_EXACTLY_ONE_IN_THE_V5_WINDOW")
            loads = [J.ENDING_SIGNER_INCARNATION[0]] + ([signer[0]] if kind == "SIGNER" else [])
            if kact != loads:
                reasons.append(f"KACT_LOADS_NOT_EXACTLY_{len(loads)}")
        denials = {}
        if kind == "WITNESS":
            for proof, path in sorted(X.DENIALS.items()):
                result = self.ssh(self.streamed(repo, path, M9.SYSTEM_PYTHON, proof))
                self._save(out, proof, result)
                denials[proof] = O.denial_result(proof, result.stdout or b"", result.returncode)
            reasons += [f"DENIAL_NOT_PASS:{proof}" for proof, value in sorted(denials.items()) if value != "PASS"]
        identity = witness if kind == "WITNESS" else signer
        record = {"kind": kind, "status": status_dir.name, "phase": phase, "w11Phase": w11.get("phase"),
                  "invocationId": identity[0], "mainPid": identity[1], "release": new, "reasons": reasons,
                  "kActLoadCount": None if kact is None else len(kact), "kWitLoadsInWindow": None if kwit is None
                  else len(kwit), "denials": denials, "healthPublicKeySha256": w11.get("healthPublicKeySha256"),
                  "windowSha256": window_sha, "envelopeSha256": sha256_hex(raw),
                  "observationSha256": sha256_hex((out / "remote.out").read_bytes()),
                  "result": f"E22_{kind}_POST_" + ("VERIFIED" if not reasons else "STOP")}
        data = self._record(out / POST_FILE, record)
        return dict(record, postSha256=sha256_hex(data),
                    next=f"the owner's verbatim statement (`render ACCEPT_{kind}`); nothing is accepted by this"
                    if not reasons else "STOP: owner adjudication; no stop, restart or repair")

    def judge_post(self, kind: str, report: dict, health_attempted: Any, witness: tuple, signer: tuple,
                   accepted: dict) -> list[str]:
        """`[]` only for the exact W11 phase of the replacement (V5: W11_1S, signer stopped after the one M-B11
        load; V6: W11_1, one load in the window, the accepted key) with W10_1 on the replacement witness."""
        obs = report.get("observation") or {}
        reasons = []
        if kind == "WITNESS":
            if report.get("phase") != W11_1S or report.get("signerState") != "STOPPED" \
                    or report.get("kActLoadCount") != 1:
                reasons.append("W11_NOT_SIGNER_STOPPED_AFTER_ONE_LOAD:" + str(report.get("phase")))
        else:
            if report.get("phase") != W11_1 or report.get("reasons") != [] or report.get("kActLoadCount") != 1 \
                    or health_attempted is not True:
                reasons.append("W11_NOT_ONE_EXACT_LOAD_IN_THE_WINDOW:" + str(report.get("phase")))
            unit = (obs.get("units") or {}).get(SIGNER_SERVICE) or {}
            if (unit.get("InvocationID"), unit.get("MainPID"), unit.get("NRestarts")) != (*signer, "0") \
                    or signer[0] == J.ENDING_SIGNER_INCARNATION[0]:
                reasons.append("SIGNER_NOT_THE_REPLACEMENT_INCARNATION")
            key = accepted["report"].get("healthPublicKeySha256")
            if report.get("healthPublicKeySha256") is None or report.get("healthPublicKeySha256") != key:
                reasons.append("KEY_NOT_THE_ACCEPTED_KEY")
        w10 = obs.get("w10") or {}
        if report.get("w10PhaseSignerJudgedSeparately") != W10_1 \
                or (w10.get("witnessInvocationId"), w10.get("witnessMainPid")) != tuple(witness) \
                or witness[0] == J.ENDING_WITNESS_INCARNATION[0]:
            reasons.append("W10_NOT_W10_1_WITH_THE_REPLACEMENT_WITNESS")
        if (obs.get("restartBoundary") or {}).get("reasons") != []:
            reasons.append("RESTART_BOUNDARY_NOT_EFFECTIVE")
        if not dark(report):
            reasons.append("AUTHORITY_NOT_DISABLED")
        return reasons

    def post_witness(self, repo: Path, workdir: Path, envelope: Path) -> dict:
        return self._post(repo, workdir, "WITNESS", envelope)

    def post_signer(self, repo: Path, workdir: Path, envelope: Path) -> dict:
        return self._post(repo, workdir, "SIGNER", envelope)

    def _latest_post(self, workdir: Path, kind: str) -> tuple[dict, str]:
        directory = Path(workdir) / POST_DIR
        runs = sorted(p for p in directory.iterdir() if p.name.endswith("-" + kind)) if directory.is_dir() else []
        _need(bool(runs), f"NO_{kind}_POST")
        raw = (runs[-1] / POST_FILE).read_bytes()
        return json.loads(raw), sha256_hex(raw)

    # ------------------------------------------------------------------ OD-M12-11 ---

    def windows(self, repo: Path, workdir: Path) -> dict:
        """Local: both load windows, for the post-transition `journal` / `attribute` reads (same boot as the last)."""
        self.pins(repo)
        found = {step: self._window_record(workdir, step) for step in WINDOWS}
        last = found["SIGNER_START"][0]
        return {"decision": "OD-M12-11", "rule": J.OD_M12_11_RULE,
                "windows": {window["event"]: {"phase": window["phase"], "open": window["open"],
                                              "close": window["close"], "recordSha256": digest}
                            for window, digest in found.values()},
                "readsBootId": last["close"]["bootId"], "readsAfterCursor": last["close"]["journalCursor"],
                "kActLoadCount": J.KACT_LOAD_COUNT_AFTER,
                "next": "the OD-M12-11 journal and attribute reads, in boot readsBootId: exactly the historical 12 "
                        "attributed matches and no new marker; nothing is authorized by this"}

    # ------------------------------------------------------------------ M-B12 package ---

    def package(self, repo: Path, outdir: Path, envelope: Path) -> dict:
        """ONE read-only evaluation of the canonical PR-1 package on DEV (the M-B12 owner-acceptance input)."""
        self.pins(repo)
        outdir = Path(outdir)
        _need(not outdir.exists(), "OUTDIR_EXISTS")
        outdir.mkdir(mode=0o700, parents=True)
        raw = Path(envelope).read_bytes()
        (outdir / M11.ENVELOPE_FILE).write_bytes(raw)
        remote = self._e22_remote(repo, outdir, "remote", {"form": "package", "ownerInputs": self.owner_inputs(raw)})
        report = None if remote is None else remote.get("report")
        record = {"envelopeSha256": sha256_hex(raw), "observationSha256": sha256_hex((outdir / "remote.out").read_bytes()),
                  "mode": None if report is None else report.get("mode"),
                  "status": None if report is None else report.get("status"),
                  "reasons": None if report is None else report.get("reasons"),
                  "packageDigest": None if report is None else report.get("packageDigest"),
                  "result": "E22_PACKAGE_" + ("NOT_RECEIVED" if remote is None else "NOT_EVALUATED" if report is None
                                             else str(report.get("status")))}
        self._record(outdir / "PACKAGE.json", record)
        return dict(record, next="the owner's M-B12 acceptance names exactly packageDigest; nothing is accepted by this")


USAGE =__doc__.split("| Form |", 1)[1].split("\n\n", 1)[0]


def main(argv: Sequence[str], operator: Operator | None = None) -> int:
    operator = operator or Operator()
    forms = {
        ("pins", 1): lambda a: operator.pins(Path(a[0])),
        ("bind", 3): lambda a: operator.bind(Path(a[0]), Path(a[1]), Path(a[2])),
        ("status", 3): lambda a: operator.status(Path(a[0]), Path(a[1]), a[2]),
        ("v0", 2): lambda a: operator.v0(Path(a[0]), Path(a[1])),
        ("render", 3): lambda a: operator.render(Path(a[0]), Path(a[1]), a[2]),
        ("post-witness", 3): lambda a: operator.post_witness(Path(a[0]), Path(a[1]), Path(a[2])),
        ("accept-witness", 3): lambda a: operator.accept_witness(Path(a[0]), Path(a[1]), Path(a[2])),
        ("post-signer", 3): lambda a: operator.post_signer(Path(a[0]), Path(a[1]), Path(a[2])),
        ("accept-signer", 3): lambda a: operator.accept_signer(Path(a[0]), Path(a[1]), Path(a[2])),
        ("windows", 2): lambda a: operator.windows(Path(a[0]), Path(a[1])),
        ("package", 3): lambda a: operator.package(Path(a[0]), Path(a[1]), Path(a[2])),
        **{(form, 3): (lambda step: lambda a: operator._step(Path(a[0]), Path(a[1]), step, Path(a[2])))(step)
           for form, (step, _p, _q, _m) in STEPS.items()},
    }
    form = forms.get((argv[0], len(argv) - 1)) if argv else None
    if form is None:
        print("e22_operator: USAGE" + USAGE, file=sys.stderr)
        return 2
    try:
        result = form(list(argv[1:]))
    except (Stop, J.Refused, Q.Refused) as exc:
        print(f"e22_operator: STOP {getattr(exc, 'code', None) or exc}", file=sys.stderr)
        return 1
    if argv[0] == "render":
        sys.stdout.write(result["text"])
        print(f"TEXT_SHA256={result['textSha256']}", file=sys.stderr)
        return 0
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
