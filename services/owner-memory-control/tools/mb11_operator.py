#!/usr/bin/env python3
"""15B2b-B1b-3e M-B11 (START_SIGNER): the owner-laptop operator of the ONE signer start.

Record: docs/architecture/slice-15b2b-b1b3e-mb11-signer-start-operator.md. SOURCE ONLY: no form below is authorized by
this repository. The start needs its own verbatim owner go (`render`), consumed by an `O_EXCL` marker written BEFORE its
one remote invocation: no retry, no second invocation path, no automatic stop, no rollback, no repair.

It reuses, unchanged: the E-19 operator (`e19_operator.Operator`: the pinned `gcloud compute ssh` route for a plain
command, the direct-plink stdin route for the mb6 BOOT bundles, the marker and the record helpers), the W10 chain, the
P1B-10R tools and the W11 verifier (`mb11_signer_verifier.py`). The host side is `mb11_start_remote.py`, bundled after
them with one generated data module carrying the owner inputs.

| Form | Effect |
| --- | --- |
| `pins <repo>` | local: clean control checkout; every pinned tool exact |
| `gate <repo> <workdir> <envelope>` | read-only DEV: one W11 judgement; PASS only for exactly `W11_0_PRE_SIGNER_EXACT` |
| `render <repo> <workdir>` | local: the exact owner go text bound to the latest PASS gate |
| `start <repo> <workdir> <go>` | **mutation**: a fresh read-only gate (same bound facts), the marker, ONE `systemctl start` of the service, ONE read-only post (HEALTH capture + W11) |
| `current <repo> <workdir>` | read-only DEV: one release `observe_current_blob().to_dict()` (the readiness `current` input), judged against the DEV readiness pins; no W11, no HEALTH |
| `observe <repo> <workdir>` | read-only DEV, only after the one consumed start reached W11_1: the SAME POST11 document once more (one HEALTH query of the running signer + W11); exact only for the accepted incarnation, key and single load |

Bindings: release `ba943e1` (E-19 U5), the owner-accepted effective P1B-10R boundary (plan `2a004a41…`, Option A; every
exact W11 phase requires `boundary_reasons == []`), the accepted replacement witness `90b28f9d…` / 69238, the W11
judgement and its derived DR-5 targets (`mb11_dr5_target.py`, applied by the routine post-deploy compare, not here).

    gate W11_0 != go;  go != start;  start (one invocation) != one K-ACT load (journal-counted);  W11_1 != acceptance
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import e19_operator as X  # noqa: E402  (pinned E-19 operator; reused unchanged)
import mb11_start_remote as R  # noqa: E402  (pinned below)

M10, M9, M6 = X.M10, X.M9, X.M6
Stop = X.Stop
_need = X._need
sha256_hex = X.sha256_hex

T = "services/owner-memory-control/tools/"
OPERATOR = T + "mb11_operator.py"
E19_OPERATOR = X.OPERATOR
RESTART_BOUNDARY = X.RESTART_BOUNDARY
RESTART_BOUNDARY_INSTALL = X.RESTART_BOUNDARY_INSTALL
W11_VERIFIER = T + "mb11_signer_verifier.py"
W11_DR5_TARGET = T + "mb11_dr5_target.py"
REMOTE = T + "mb11_start_remote.py"
READINESS_INPUTS = T + "mb12_readiness_inputs.py"
E19_RECORD = T + "e19_completion_record.json"
TOOL_PINS = {
    **{path: M10.TOOL_PINS[path] for path in M10.W10_BUNDLE},
    RESTART_BOUNDARY: X.TOOL_PINS[RESTART_BOUNDARY],
    RESTART_BOUNDARY_INSTALL: X.TOOL_PINS[RESTART_BOUNDARY_INSTALL],
    W11_VERIFIER: "e21fd26fd68bcdea3d645a12ff53b647ef3aa8f62824e9c89712b8fcb85d4e1d",
    W11_DR5_TARGET: "775f43e84e1e58c2c9d1e8b4f2f32dc955462d034963b74761a133003a16daf3",
    REMOTE: "04461ffe4d30d443c49e5ef2d314972fda41a0b3b8dda1765609fb64c1cad72f",
    E19_OPERATOR: "b98328162b72795de0579d5e7abb58ff55f1bd7498e53b8699d91af5d453c1dd",
    READINESS_INPUTS: "a1c68c7e054d3f7cb2d5368e8772bbeb19d977e7552a5d770c4f0461696b0435",
    E19_RECORD: "31bc707ebc9b58b376d233a30594eaa0e1f4d3b32444b172c741dbaeec66b3b8",
}
# The W10 chain, the restart-boundary tools, the W11 verifier, then the generated evidence and the remote tail.
BUNDLE = (*M10.W10_BUNDLE, RESTART_BOUNDARY, RESTART_BOUNDARY_INSTALL, W11_VERIFIER)

RELEASE = X.E.NEW_RELEASE                                                 # E-19 NEW, sole installed (U5); the contract pin
P1B10R_PLAN = "2a004a4195116462d60fdff978229f9a2364427704e4d16d5dec729801106592"   # installed once; Option A
WITNESS = ("90b28f9d06fd48a1a1bdc3ae39474fb1", "69238")                  # the accepted E-19 replacement
W11_0, W11_1, W10_1 = "W11_0_PRE_SIGNER_EXACT", "W11_1_SIGNER_STARTED_EXACT", "W10_1_HELD_EXACT"
SIGNER_SERVICE = "lilith-authority-dev.service"
START_SIGNER_COMMAND = f"sudo -n /usr/bin/systemctl start {SIGNER_SERVICE}"
GATE_DIR, STEP_DIR, MARKER = "gates", "steps", "mb11-start"
GATE_FILE, START_FILE, ENVELOPE_FILE = "GATE.json", "START.json", "inputs.envelope"
CURRENT_DIR, CURRENT_FILE = "current", "CURRENT.json"
OBSERVE_DIR, OBSERVE_FILE = "observe", "OBSERVE.json"
RELEASE_TREE_PREFIX = "/opt/lilith-authority-dev/current/"              # = mb6_ledger_verifier.RELEASE_TREE + "/"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

GO_LINES = (
    "I authorize MB11-GO-START now: `" + START_SIGNER_COMMAND + "` on lilith-dev-01, exactly one invocation of the "
    "service start path, never the socket.",
    "It may load K-ACT at most once: no automatic retry, restart, stop, enable or daemon-reload is part of this go.",
    "Release {release}. Effective P1B-10R restart boundary: plan {plan}, owner-accepted P10R_2_EFFECTIVE_EXACT "
    "(Option A).",
    "Gate " + W11_0 + " observation SHA-256 {gate}; journal cursor {cursor}; ledger DB SHA-256 {db}; witness "
    "{wid} / {wpid}.",
    "Owner readiness inputs envelope SHA-256 {envelope}.",
    "Control commit: {control}. Operator: " + OPERATOR + " SHA-256 {operator}.",
    "This authorizes the signer start only: not its acceptance, M-B12, Registry effectiveness, authority, First "
    "Memory or PROD.",
)


class Operator(X.Operator):
    """The E-19 operator's transport and records; MB11 pins, bundle and forms."""

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
        for module, path in ((X, E19_OPERATOR), (R, REMOTE)):
            _need(sha256_hex(Path(module.__file__).read_bytes()) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        accepted = json.loads(self.tool_bytes(repo, E19_RECORD)).get("replacementAcceptance") or {}
        _need((accepted.get("invocationId"), accepted.get("mainPid")) == WITNESS, "WITNESS_NOT_THE_E19_REPLACEMENT")
        return {"control": control, "operatorSha256": operator, "tools": dict(TOOL_PINS), "result": "MB11_TOOL_PINS_EXACT"}

    def bundle(self, repo: Path, doc: dict) -> tuple[str, bytes]:
        """The reviewed mb6 BOOT stdin bundle: pinned repository sources, then the generated evidence module (pinned
        by its own bytes, bound to `doc`), then the remote tail. Release interpreter, root, no host file."""
        import base64
        import gzip

        sources = {Path(path).stem: self.tool_bytes(repo, path).decode("utf-8") for path in BUNDLE}
        sources[R.EVIDENCE_MODULE] = R.evidence_module_source(doc)
        sources[Path(REMOTE).stem] = self.tool_bytes(repo, REMOTE).decode("utf-8")
        payload = base64.b64encode(gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0))
        pins = ",".join(f"{name}={sha256_hex(text.encode('utf-8'))}" for name, text in sources.items())
        boot = base64.b64encode(M6.BOOT.encode("ascii")).decode("ascii")
        loader = f"import base64;exec(base64.b64decode('{boot}'))"
        command = (f"B=$(cat); printf %s \"$B\" | sha256sum | cut -c1-64 | grep -qx '{sha256_hex(payload)}' || exit 96; "
                   f"printf %s \"$B\" | base64 -d | sudo -n {M9.RELEASE_PYTHON} -I -B -c \"{loader}\" "
                   f"{pins} {Path(REMOTE).stem} {doc['form']} {R.evidence_digest(doc)}")
        return command, payload + b"\n"

    # ------------------------------------------------------------ owner inputs ---

    @staticmethod
    def readiness_tool() -> Any:
        """The pinned `mb12_readiness_inputs` module (the envelope reader and the DEV readiness pins)."""
        import importlib.util

        source = Path(__file__).resolve().parents[3] / READINESS_INPUTS
        _need(sha256_hex(source.read_bytes()) == TOOL_PINS[READINESS_INPUTS], "TOOL_PIN_MISMATCH:" + READINESS_INPUTS)
        tool = sys.modules.get("mb12_readiness_inputs")
        if tool is None:
            spec = importlib.util.spec_from_file_location("mb12_readiness_inputs", source)
            tool = importlib.util.module_from_spec(spec)
            sys.modules["mb12_readiness_inputs"] = tool
            spec.loader.exec_module(tool)
        _need(sha256_hex(Path(tool.__file__).read_bytes()) == TOOL_PINS[READINESS_INPUTS],
              "TOOL_PIN_MISMATCH:" + READINESS_INPUTS)
        return tool

    def owner_inputs(self, raw: bytes) -> dict:
        """The verifier input document, only from exactly these envelope bytes (`mb12_readiness_inputs`, pinned)."""
        tool = self.readiness_tool()
        try:
            return dict(tool.read_envelope(raw, expected_sha256=sha256_hex(raw), environment="dev"))
        except Exception as exc:  # noqa: BLE001 - the reader's own refusal is a STOP, never a default
            raise Stop("OWNER_INPUTS_REFUSED:" + str(getattr(exc, "reason", None) or type(exc).__name__)) from exc

    def _doc(self, form: str, inputs: dict, baseline: dict | None = None) -> dict:
        doc = {"form": form, "expectedHead": X.LEDGER_HEAD, "candidateDigest": X.GENESIS,
               "updatedAt": X.GENESIS_UPDATED_AT, "witness": list(WITNESS), "ownerInputs": inputs}
        if baseline is not None:
            doc["baseline"] = baseline
        return doc

    # ------------------------------------------------------------ read-only DEV ---

    def _remote(self, repo: Path, out: Path, name: str, doc: dict) -> dict | None:
        """ONE read-only bundle; the parsed remote document only if it echoes this exact evidence."""
        result = self._invoke_once(*self.bundle(repo, doc))
        code = self._save(out, name, result)
        try:
            value = json.loads((result.stdout or b"").decode("utf-8")) if code == 0 else None
        except (UnicodeDecodeError, ValueError):
            value = None
        if not isinstance(value, dict) or value.get("remoteType") != R.REMOTE_TYPE or value.get("form") != doc["form"] \
                or value.get("evidenceSha256") != R.evidence_digest(doc) or not isinstance(value.get("report"), dict):
            return None
        return value

    @staticmethod
    def judge_gate(remote: dict | None) -> list[str]:
        """`[]` only for exactly W11_0 with the accepted witness, the effective boundary and a usable cursor."""
        if remote is None:
            return ["GATE_NOT_RECEIVED"]
        report = remote["report"]
        obs = report.get("observation") or {}
        reasons = []
        if report.get("phase") != W11_0:
            reasons.append("PHASE:" + str(report.get("phase")))
        if report.get("kActLoadCount") != 0 or report.get("signerState") != "STOPPED":
            reasons.append("SIGNER_NOT_NEVER_STARTED")
        if report.get("w10PhaseSignerJudgedSeparately") != W10_1 or report.get("w10PhaseDirect") != W10_1:
            reasons.append("W10_NOT_W10_1")
        w10 = obs.get("w10") or {}
        if (w10.get("witnessInvocationId"), w10.get("witnessMainPid")) != WITNESS:
            reasons.append("WITNESS_NOT_THE_ACCEPTED_REPLACEMENT")
        if (obs.get("restartBoundary") or {}).get("reasons") != []:
            reasons.append("RESTART_BOUNDARY_NOT_EFFECTIVE")
        cursor = remote.get("journalCursor")
        if not isinstance(cursor, str) or not cursor or any(c.isspace() for c in cursor):
            reasons.append("JOURNAL_CURSOR_UNKNOWN")
        if not isinstance(remote.get("ledgerDbSha256"), str) or _HEX64.fullmatch(remote["ledgerDbSha256"]) is None:
            reasons.append("LEDGER_DB_UNKNOWN")
        return reasons

    def _gate(self, repo: Path, workdir: Path, label: str, raw: bytes) -> tuple[Path, dict]:
        inputs = self.owner_inputs(raw)
        out = self._new_numbered(Path(workdir) / GATE_DIR, label)
        (out / ENVELOPE_FILE).write_bytes(raw)
        doc = self._doc("gate", inputs)
        remote = self._remote(repo, out, "remote", doc)
        reasons = self.judge_gate(remote)
        stdout = (out / "remote.out").read_bytes()
        record = {"gate": out.name, "acquiredAt": self.now().strftime("%Y-%m-%dT%H:%M:%SZ"), "reasons": reasons,
                  "phase": None if remote is None else remote["report"].get("phase"),
                  "observationSha256": sha256_hex(stdout), "evidenceSha256": R.evidence_digest(doc),
                  "envelopeSha256": sha256_hex(raw), "witness": list(WITNESS), "release": RELEASE,
                  "journalCursor": None if remote is None else remote.get("journalCursor"),
                  "dbSha256": None if remote is None else remote.get("ledgerDbSha256"),
                  "result": "MB11_GATE_" + ("W11_0" if not reasons else "STOP")}
        self._record(out / GATE_FILE, record)
        return out, record

    def gate(self, repo: Path, workdir: Path, envelope: Path) -> dict:
        self.pins(repo)
        _need(not (Path(workdir) / M6.ATTEMPT_DIR / f"{MARKER}.json").exists(), "ATTEMPT_ALREADY_CONSUMED:" + MARKER)
        out, record = self._gate(repo, workdir, "GATE", Path(envelope).read_bytes())
        return dict(record, next="nothing is authorized; the start needs the separate MB11-GO-START"
                    if not record["reasons"] else "STOP: read-only re-observation and owner adjudication")

    def _latest_gate(self, workdir: Path) -> tuple[Path, dict]:
        directory = Path(workdir) / GATE_DIR
        gates = sorted(p for p in directory.iterdir() if p.name.endswith("-GATE")) if directory.is_dir() else []
        _need(bool(gates), "NO_GATE")
        latest = gates[-1]
        record = json.loads((latest / GATE_FILE).read_bytes())
        _need(record.get("result") == "MB11_GATE_W11_0" and record.get("reasons") == [], "LATEST_GATE_NOT_W11_0")
        _need(sha256_hex((latest / "remote.out").read_bytes()) == record["observationSha256"]
              and sha256_hex((latest / ENVELOPE_FILE).read_bytes()) == record["envelopeSha256"], "GATE_EVIDENCE_CHANGED")
        return latest, record

    # ------------------------------------------------------- CURRENT (read-only) ---

    @staticmethod
    def judge_current(remote: dict | None, tool: Any) -> list[str]:
        """`[]` only for the release observer's exact pinned CURRENT slot, observed after the DEV freshness cutoff."""
        if remote is None:
            return ["CURRENT_NOT_RECEIVED"]
        report = remote["report"]
        current = report.get("current")
        if not isinstance(current, dict) or set(current) != set(tool._CURRENT_FIELDS):
            return ["CURRENT_NOT_CANONICAL"]
        reasons = []
        if (current["path"], current["kind"], current["mode"]) != (tool.SC.CURRENT_PATH, tool.WR.REGULAR, "0600"):
            reasons.append("CURRENT_NOT_PINNED_SLOT")
        if (current["uid"], current["gid"]) != (0, 0):
            reasons.append("CURRENT_NOT_ROOT_OWNED")
        if current["sha256"] != tool.DEV_PINS["pinnedCurrentSha256"]:
            reasons.append("CURRENT_SHA256_NOT_PINNED")
        try:
            canonical = all(tool.PA.parse_decimal(current[name]) is not None
                            for name in ("device", "inode", "mtimeNs", "ctimeNs"))
        except ValueError:
            canonical = False
        if not canonical or type(current["size"]) is not int:
            reasons.append("CURRENT_IDENTITY_MALFORMED")
        at, until = report.get("observedAt"), report.get("observedUntil")
        if not all(isinstance(v, str) and tool._INSTANT.fullmatch(v) for v in (at, until)) or not at <= until \
                or tool.I2.DEV_FRESHNESS_NOT_BEFORE is None or at < tool.I2.DEV_FRESHNESS_NOT_BEFORE:
            reasons.append("CURRENT_NOT_AFTER_FRESHNESS_CUTOFF")
        if not str(report.get("observersModule", "")).startswith(RELEASE_TREE_PREFIX):
            reasons.append("CURRENT_NOT_THE_RELEASE_OBSERVER")
        return reasons

    def current(self, repo: Path, workdir: Path) -> dict:
        """ONE read-only bundle: the release's canonical CURRENT observation, never decrypted, never a W11 judgement."""
        self.pins(repo)
        tool = self.readiness_tool()
        out = self._new_numbered(Path(workdir) / CURRENT_DIR, "CURRENT")
        doc = {"form": "current"}
        remote = self._remote(repo, out, "remote", doc)
        reasons = self.judge_current(remote, tool)
        report = None if remote is None else remote["report"]
        record = {"current": out.name, "acquiredAt": self.now().strftime("%Y-%m-%dT%H:%M:%SZ"), "reasons": reasons,
                  "observationSha256": sha256_hex((out / "remote.out").read_bytes()),
                  "evidenceSha256": R.evidence_digest(doc), "release": RELEASE,
                  "observedAt": None if report is None else report.get("observedAt"),
                  "observedUntil": None if report is None else report.get("observedUntil"),
                  "observation": None if report is None else report.get("current"),
                  "result": "MB11_CURRENT_" + ("EXACT" if not reasons else "STOP")}
        self._record(out / CURRENT_FILE, record)
        return dict(record, next="nothing is authorized; the observation is an input, never readiness")

    # ------------------------------------------------------------------ the go ---

    def render(self, repo: Path, workdir: Path) -> dict:
        text = self._go_text(workdir, self.pins(repo)).encode("ascii")
        return {"text": text.decode("ascii"), "textSha256": sha256_hex(text)}

    def _go_text(self, workdir: Path, pins: dict) -> str:
        _, gate = self._latest_gate(workdir)
        values = {"release": RELEASE, "plan": P1B10R_PLAN, "gate": gate["observationSha256"],
                  "cursor": gate["journalCursor"], "db": gate["dbSha256"], "wid": WITNESS[0], "wpid": WITNESS[1],
                  "envelope": gate["envelopeSha256"], "control": pins["control"], "operator": pins["operatorSha256"]}
        return "\n".join(line.format(**values) for line in GO_LINES) + "\n"

    # ---------------------------------------------------------------- mutation ---

    def start(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        """One owner go, one fresh read-only gate, one marker, ONE `systemctl start`, one read-only post."""
        pins = self.pins(repo)
        raw = Path(go_file).read_bytes()
        _need(raw == self._go_text(workdir, pins).encode("ascii"), "GO_NOT_CANONICAL_FOR_THE_LATEST_GATE")
        _need(not (Path(workdir) / M6.ATTEMPT_DIR / f"{MARKER}.json").exists(), "ATTEMPT_ALREADY_CONSUMED:" + MARKER)
        latest, gate = self._latest_gate(workdir)
        envelope = (latest / ENVELOPE_FILE).read_bytes()
        fresh_dir, fresh = self._gate(repo, workdir, "START_PRE", envelope)            # read-only, before the marker
        _need(not fresh["reasons"], "FRESH_GATE_NOT_W11_0:" + ",".join(fresh["reasons"]))
        _need((fresh["dbSha256"], fresh["witness"], fresh["envelopeSha256"])
              == (gate["dbSha256"], gate["witness"], gate["envelopeSha256"]), "STALE_GATE_BOUND_FACTS_CHANGED")
        out = self._new_numbered(Path(workdir) / STEP_DIR, "START")
        self._one_attempt(workdir, MARKER, raw)                                        # the go is consumed HERE
        result = self._invoke_once(START_SIGNER_COMMAND, None)
        code = self._save(out, "start", result)
        inputs = self.owner_inputs(envelope)
        post = self._remote(repo, out, "post", self._doc("post", inputs, {"dbSha256": gate["dbSha256"],
                                                                          "journalCursor": gate["journalCursor"]}))
        report = None if post is None else post["report"]
        reached = (code == 0 and report is not None and report.get("phase") == W11_1
                   and report.get("kActLoadCount") == 1 and post.get("healthCaptureAttempted") is True)
        if report is None:
            result_name = "MB11_START_UNKNOWN_POST_NOT_RECEIVED"
        elif reached:
            result_name = "MB11_START_REACHED_" + W11_1
        else:
            result_name = "MB11_START_STOP:" + str(report.get("phase"))
        record = {"goSha256": sha256_hex(raw), "gate": latest.name, "freshGate": fresh_dir.name, "startCode": code,
                  "postPhase": None if report is None else report.get("phase"),
                  "postRouting": None if report is None else report.get("routing"),
                  "postReasons": None if report is None else report.get("reasons"),
                  "kActLoadCount": None if report is None else report.get("kActLoadCount"),
                  "postSha256": sha256_hex((out / "post.out").read_bytes()), "result": result_name}
        self._record(out / START_FILE, record)
        return dict(record, next="read-only POST11, then the owner acceptance; nothing further is authorized"
                    if reached else "STOP: no retry, no automatic stop; read-only re-observation and owner adjudication")

    # ------------------------------------------------- OBSERVE (read-only) ---

    def _accepted_start(self, workdir: Path) -> tuple[Path, dict, dict, dict]:
        """The one consumed start that reached W11_1: its gate, its record and its POST11 document (bytes re-checked)."""
        _need((Path(workdir) / M6.ATTEMPT_DIR / f"{MARKER}.json").exists(), "START_NOT_CONSUMED")
        directory = Path(workdir) / STEP_DIR
        steps = sorted(p for p in directory.iterdir() if p.name.endswith("-START")) if directory.is_dir() else []
        _need(len(steps) == 1, "START_STEP_NOT_EXACTLY_ONE")
        record = json.loads((steps[0] / START_FILE).read_bytes())
        post = (steps[0] / "post.out").read_bytes()
        _need(record.get("result") == "MB11_START_REACHED_" + W11_1 and record.get("kActLoadCount") == 1
              and record.get("postSha256") == sha256_hex(post), "START_NOT_THE_REACHED_W11_1")
        latest, gate = self._latest_gate(workdir)
        _need(latest.name == record.get("gate"), "START_GATE_NOT_THE_LATEST_GATE")
        return latest, gate, record, json.loads(post)

    @staticmethod
    def judge_observe(remote: dict | None, accepted: dict) -> list[str]:
        """`[]` only for W11_1 with the accepted signer incarnation and key, one K-ACT load and authority disabled."""
        if remote is None:
            return ["OBSERVE_NOT_RECEIVED"]
        report, then = remote["report"], accepted["report"]

        def signer(rep: dict) -> tuple:
            unit = ((rep.get("observation") or {}).get("units") or {}).get(SIGNER_SERVICE) or {}
            return unit.get("InvocationID"), unit.get("MainPID"), unit.get("NRestarts")

        reasons = []
        if report.get("phase") != W11_1 or report.get("reasons") != []:
            reasons.append("PHASE:" + str(report.get("phase")))
        if report.get("kActLoadCount") != 1 or remote.get("healthCaptureAttempted") is not True:
            reasons.append("NOT_ONE_LOAD_WITH_HEALTH")
        if signer(report) != signer(then) or None in signer(report):
            reasons.append("SIGNER_NOT_THE_ACCEPTED_INCARNATION")
        if report.get("healthPublicKeySha256") is None \
                or report.get("healthPublicKeySha256") != then.get("healthPublicKeySha256"):
            reasons.append("KEY_NOT_THE_ACCEPTED_KEY")
        w10 = (report.get("observation") or {}).get("w10") or {}
        if report.get("w10PhaseSignerJudgedSeparately") != W10_1 \
                or (w10.get("witnessInvocationId"), w10.get("witnessMainPid")) != WITNESS:
            reasons.append("W10_NOT_W10_1_WITH_THE_ACCEPTED_WITNESS")
        if ((report.get("observation") or {}).get("restartBoundary") or {}).get("reasons") != []:
            reasons.append("RESTART_BOUNDARY_NOT_EFFECTIVE")
        if (report.get("authorityGranted"), report.get("authorityActive"), report.get("registryEffective"),
                report.get("issuanceAuthority")) != (False, False, False, "NONE"):
            reasons.append("AUTHORITY_NOT_DISABLED")
        return reasons

    def observe(self, repo: Path, workdir: Path) -> dict:
        """ONE read-only re-observation of the accepted start: the identical POST11 document (same gate baseline, same
        owner inputs), so the same W11 judgement and one HEALTH query. Never a gate, never the marker, never a start."""
        self.pins(repo)
        latest, gate, start, accepted = self._accepted_start(workdir)
        inputs = self.owner_inputs((latest / ENVELOPE_FILE).read_bytes())
        doc = self._doc("post", inputs, {"dbSha256": gate["dbSha256"], "journalCursor": gate["journalCursor"]})
        _need(R.evidence_digest(doc) == accepted.get("evidenceSha256"), "OBSERVE_DOC_NOT_THE_ACCEPTED_POST11")
        out = self._new_numbered(Path(workdir) / OBSERVE_DIR, "POST11")
        remote = self._remote(repo, out, "remote", doc)
        reasons = self.judge_observe(remote, accepted)
        report = None if remote is None else remote["report"]
        record = {"observe": out.name, "acquiredAt": self.now().strftime("%Y-%m-%dT%H:%M:%SZ"), "reasons": reasons,
                  "phase": None if report is None else report.get("phase"),
                  "kActLoadCount": None if report is None else report.get("kActLoadCount"),
                  "observationSha256": sha256_hex((out / "remote.out").read_bytes()),
                  "acceptedPostSha256": start["postSha256"], "evidenceSha256": R.evidence_digest(doc),
                  "release": RELEASE, "result": "MB11_OBSERVE_" + ("W11_1_EXACT" if not reasons else "STOP")}
        self._record(out / OBSERVE_FILE, record)
        return dict(record, next="nothing is authorized; the phase is an input to the W11 DR-5 compare"
                    if not reasons else "STOP: owner adjudication; no stop, restart or repair")


USAGE = __doc__.split("| Form |", 1)[1].split("\n\n", 1)[0]


def main(argv: Sequence[str], operator: Operator | None = None) -> int:
    operator = operator or Operator()
    forms = {
        ("pins", 1): lambda a: operator.pins(Path(a[0])),
        ("gate", 3): lambda a: operator.gate(Path(a[0]), Path(a[1]), Path(a[2])),
        ("render", 2): lambda a: operator.render(Path(a[0]), Path(a[1])),
        ("start", 3): lambda a: operator.start(Path(a[0]), Path(a[1]), Path(a[2])),
        ("current", 2): lambda a: operator.current(Path(a[0]), Path(a[1])),
        ("observe", 2): lambda a: operator.observe(Path(a[0]), Path(a[1])),
    }
    form = forms.get((argv[0], len(argv) - 1)) if argv else None
    if form is None:
        print("mb11_operator: USAGE" + USAGE, file=sys.stderr)
        return 2
    try:
        result = form(list(argv[1:]))
    except Stop as exc:
        print(f"mb11_operator: STOP {getattr(exc, 'code', None) or exc}", file=sys.stderr)
        return 1
    if argv[0] == "render":
        sys.stdout.write(result["text"])
        print(f"TEXT_SHA256={result['textSha256']}", file=sys.stderr)
        return 0
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
