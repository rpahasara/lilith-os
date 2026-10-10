#!/usr/bin/env python3
"""15B2b-B1b-3e M-B10 (WRITE_HELD): the reviewed owner-laptop operator.

Record: docs/architecture/slice-15b2b-b1b3e-mb10-held-package.md.
DESIGN / SOURCE ONLY: no form below is authorized by this repository. Each live use needs its own explicit owner act
(record §8). The continuity wording in the templates is the PROPOSED one (record §10, OD-M10-1); it is not accepted.

It reuses the pinned Package B operator (`mb9_operator.Operator`: the reviewed `gcloud compute ssh` mutation
transport, the direct-plink verifier bundles, the one-attempt marker, the go check), unchanged, and adds only the
M-B10 forms. Every form is closed: no free path, command or principal argument reaches DEV.

| Form | Effect |
| --- | --- |
| `pins <repo>` | local, read-only: clean checkout; control = `HEAD`; every pinned tool exact |
| `render <repo> <workdir> <D1\\|D2\\|D3\\|STOP> [<facts.json>]` | local: the exact canonical owner text with every value inserted (D1 needs the facts) |
| `open <repo> <workdir> <statement> <facts.json>` | local: the owner's verbatim D1 (read-only opening; the freeze per the accepted continuity) in a NEW work directory |
| `export <repo> <workdir>` | read-only DEV: one fresh chain export (`chain/1.json`, `witness.json`) with a receipt bound to this sequence |
| `host <repo> <workdir> <PRE\\|POST>` | read-only DEV: the Package B host reads with the M-B10 expectations, plus the W10 verifier |
| `gate <repo> <workdir> <host-dir> <eligibility.json> <facts.json>` | local: the M-B10 gate over a fresh, never-consumed host PRE read and a fresh owner eligibility record |
| `mb10 <repo> <workdir> <go-file>` | **mutation, one D2 go, one marker**: a fresh W10_0 read; marker `mb10`; ONE `lilith-authority-hold-dev create-initial-held`; an independent W10 read-back |
| `post <repo> <workdir>` | read-only DEV: POST10 (host POST, the P1B-10, P1B-9b and P1B-5 proofs, health, hold observe, HELD bytes, chain); on exact, `POST10_VERIFIED` |
| `classify <repo> <workdir> <evidence-dir>` | read-only DEV: the W10 verifier combined with this sequence's records into one sequence phase |
| `accept <repo> <workdir> <statement>` | local: records the owner's verbatim D3 (M-B10 acceptance; authorizes nothing) |
| `stop <repo> <workdir> <statement>` | local: the owner's verbatim pre-marker stop; refused once the marker exists |
| `dr5 <repo> <verified-w10-phase> <deploy-log>` | local: the post-HELD phase-bound DR-5 comparison (`mb10_dr5_target.py`) |

Four owner acts, each its own text and none implied by another: D1 opens the sequence (read-only only); D2
authorizes the ONE HELD write and acknowledges its point of no return; D3 accepts M-B10 (authorizes nothing); a
pre-marker STOP may instead end the sequence. The `O_EXCL` marker is written BEFORE the remote write; whatever
happens after it, the go is consumed: no automatic retry and no second invocation path. The writer itself refuses a
second HELD (`HOLD_STORE_NOT_EMPTY`), but that is defence in depth, never the reason it is not retried.

    gate / pin / marker / go check != authorization;  W10_1 technical PASS != owner acceptance
    HELD = restrictive custody state only;  HELD != issuance != signer (M-B11) != activation != First Memory

It never opens, loads, decrypts or copies a key, never starts, stops, enables or reloads a unit, never starts the
signer, never runs a release, head-advance, epoch-advance, recovery, activation, record or First Memory form, and
runs the hold CLI's `create-initial-held` only inside `mb10`, once.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mb9_operator as M9  # noqa: E402  (pinned Package B operator; reused unchanged)

M6 = M9.M6
A = M9.A
Stop = M9.Stop
_need = M9._need
sha256_hex = M9.sha256_hex

OPERATOR = "services/owner-memory-control/tools/mb10_operator.py"
MB9_OPERATOR = M9.OPERATOR
PKGC_OPERATOR = "services/owner-memory-control/tools/pkgc_operator.py"
DR5_SCRIPT = "scripts/deployer_authority_boundary_proof.sh"
MB10_VERIFIER = "services/owner-memory-control/tools/mb10_held_verifier.py"
MB10_DENIAL = "services/owner-memory-control/tools/mb10_hold_denial_proof.py"
MB10_DR5 = "services/owner-memory-control/tools/mb10_dr5_target.py"
MB10_ELIGIBILITY = "services/owner-memory-control/tools/mb10_owner_eligibility.py"
TOOL_PINS = {
    **M9.TOOL_PINS,
    MB9_OPERATOR: "2312e26a9cc8c2076539ae8bdde98cc5d79c2bbeb5138d66d07863ec3303c928",
    PKGC_OPERATOR: "c5e5a5cc265f48721715e43b4bec40ccbaf865c4149d095c86c853331c2767c0",
    DR5_SCRIPT: "9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43",
    MB10_VERIFIER: "35b2cb19a2a6e4673f2425d0a13432b6af736cfc0eeaeab81a48121b1de66cf5",
    MB10_DENIAL: "3685472f865113357e3010003c3bb24ff47e66b528f114f5fca23d9d7a664b7b",
    MB10_DR5: "29c359617605f67e812732c4bb6a9ca1b9439bfffcf22285e44d9f6c1999ccf0",
    MB10_ELIGIBILITY: "8d9edfd4110529efb047e5e45eff9e48233ee3ddfe2f8d2bbd7b2015b6c51ea7",
}
W10_BUNDLE = (M9.W5_VERIFIER, M9.MB6_VERIFIER, M9.MB8_VERIFIER, M9.VERIFIER, MB10_VERIFIER)

CONTINUITY = "MB10_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_HOLD_BOUNDARY"
HOLD_CLI = "/usr/local/sbin/lilith-authority-hold-dev"
HOLD_COMMAND = f"sudo -n {HOLD_CLI} create-initial-held"
HOLD_OBSERVE_COMMAND = f"sudo -n {HOLD_CLI} observe"
HOLD_STORE = "/var/lib/lilith-authority-custody/holds"
WITNESS_STATE = M9.WITNESS_STATE
GENESIS = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
CHAIN_1_SHA256 = "252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99"
RECORD_1 = "77752db11d80eef50eaeaa8b931d65a489bb919f9e864584fbf8d00746e2cec6"
ENVELOPE_1 = "95da36cd6edd49c2bae244611cc429a174dee72ec2454c4f73c57a83bfcb0f0c"
# The owner-accepted post-reboot witness incarnation and boot (post-reboot re-pin record; preserved EQUAL since).
ACCEPTED_WITNESS = ("8af12bd64d024d0eba56bbcedbc534a6", "1580")
ACCEPTED_BOOT_ID = "cb0d71da-32a7-402b-b85e-5748da012bff"
MARKER = "mb10"
SEQUENCE_DIR, HOST_DIR, EXPORT_DIR, GATE_DIR, POST_DIR, ACCEPT_DIR = (
    "sequence", "host", "exports", "gates", "post10", "acceptance")
OPENING_FILE, STOP_FILE, ACCEPT_FILE = "D1_OPENING.json", "STOPPED.json", "D3_ACCEPTANCE.json"
OPEN_FACTS = ("lastDeployRunId", "workflowQueueEmpty", "predecessorWorkdir")
GATE_FACTS = ("lastDeployRunId", "workflowQueueEmpty")
_RUN_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

PONR_ACKNOWLEDGEMENT = ("I understand that INITIAL_CUSTODY HELD is forward only: once written it is never deleted, "
                        "recreated or re-bound, and no automatic retry is authorized after the attempt marker.")
ADOPTION_LINE = ("I adopt this HELD record although the writer's response was not received exactly: the independent "
                 "read-back is exact.")

# ------------------------------------------------------------ owner texts ---
# Record §8. `{...}` placeholders are bound from the files; tool pins are static.
OPEN_LINES = (
    "I authorize opening the M-B10 / WRITE_HELD live sequence now, read-only only, for this current DEV_SYNTHETIC "
    "sequence.",
    "Continuity: " + CONTINUITY + ".",
    "The M-B10 freeze begins with this opening and holds through M-B10, POST10 and D3: no intentional merge, deploy, "
    "reboot, witness restart, broker restart or signer action is permitted inside this sequence.",
    "Control commit: {control}. Operator: " + OPERATOR + " SHA-256 {operator}. Last deploy: {deploy}.",
    "Predecessor sequence: {predecessor}.",
    "Expected HELD record: {held_name}, SHA-256 {held_sha}, bound to witness genesis " + GENESIS + ".",
    "This authorizes opening the sequence and read-only evidence only. It does not authorize M-B10, HELD, the signer, "
    "authority activation, First Memory or PROD.",
)
GO_LINES = (
    "I authorize M-B10 / WRITE_HELD now for exactly one attempt within this current M-B10 sequence {sequence}.",
    "Continuity: " + CONTINUITY + ".",
    "Control commit: {control}. Operator: " + OPERATOR + " SHA-256 {operator}.",
    "W10 verifier: " + MB10_VERIFIER + " SHA-256 " + TOOL_PINS[MB10_VERIFIER] + ".",
    "Hold denial proof: " + MB10_DENIAL + " SHA-256 " + TOOL_PINS[MB10_DENIAL] + ".",
    "Gate SHA-256: {gate}. Owner eligibility SHA-256: {eligibility}.",
    "Pre-state: W10_0_PRE_HELD_EXACT (hold store empty; W9_5_GENESIS_COMMITTED_EXACT; witness InvocationID "
    "{invocation}, MainPID {mainpid}; boot {boot}).",
    "Record 1 digest: " + RECORD_1 + ". Envelope 1 digest: " + ENVELOPE_1 + ". Freshness: AUTHENTIC + CURRENT. "
    "Acceptance: ACCEPTANCE_COMPLETE.",
    f"Command: {HOLD_CLI} create-initial-held, exactly one invocation.",
    "Expected HELD record: {held_name}, SHA-256 {held_sha}, bound to witness genesis " + GENESIS + ".",
    PONR_ACKNOWLEDGEMENT,
    "HELD is restrictive custody state only and grants no issuance or other authority. This go does not authorize "
    "the signer (M-B11), authority activation, Registry V1 effectiveness, First Memory or PROD.",
    "Any REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output or other STOP after the attempt marker "
    "consumes this go. The host classification decides; there is no automatic retry.",
)
ACCEPT_LINES = (
    "I accept M-B10 / WRITE_HELD for sequence {sequence}: INITIAL_CUSTODY HELD is COMPLETED.",
    "HELD record: {held_name}, SHA-256 {held_sha}, bound to witness genesis " + GENESIS + ". POST10_VERIFIED SHA-256: "
    "{post10}.",
    "HELD is restrictive custody state only. REGISTRY_EFFECTIVE remains NO. AUTHORITY_ACTIVE remains NO. "
    "authorityGranted remains false. The signer remains inactive.",
    "This acceptance authorizes nothing further: not the signer (M-B11), authority activation, First Memory or PROD. "
    "The M-B10 freeze ends now; the first deploy after it must compare EQUAL to the post-HELD DR-5 target under "
    "W10_1_HELD_EXACT.",
)
STOP_LINES = (
    "I stop M-B10 sequence {sequence} now, before the attempt marker, for this current DEV_SYNTHETIC sequence only.",
    "Control commit: {control}. D1 record SHA-256: {opening}.",
    "No M-B10 attempt marker exists and no HELD was written by this sequence.",
    "This sequence is STOPPED / HISTORICAL / NON-REUSABLE. Its freeze is released; the release authorizes nothing.",
)


def _verifier_module(repo: Path):
    return sys.modules.get("mb10_held_verifier_operator") or load_tool(Path(repo), MB10_VERIFIER,
                                                                        "mb10_held_verifier_operator")


def load_tool(repo: Path, path: str, name: str):
    """Hash-gated, registered in `sys.modules` before execution, with this package's pins."""
    source = Path(repo) / path
    _need(sha256_hex(source.read_bytes()) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, source)
    _need(spec is not None and spec.loader is not None, "TOOL_LOAD_FAILED:" + path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        if sys.modules.get(name) is module:
            del sys.modules[name]
        raise Stop("TOOL_LOAD_FAILED:" + path) from exc
    return module


def _json_file(path: Path, reason: str) -> Any:
    try:
        return json.loads(Path(path).read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise Stop(reason) from exc


class Operator(M9.Operator):
    """The Package B transport, marker and go helpers, unchanged; every pin lookup is this package's."""

    # ------------------------------------------------------------ pinned bytes ---

    def tool_bytes(self, repo: Path, path: str) -> bytes:
        data = self._git(repo, "show", f"HEAD:{path}")
        _need(sha256_hex(data) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return data

    def streamed(self, repo: Path, path: str, interpreter: str, args: str) -> str:
        import gzip

        blob = base64.b64encode(gzip.compress(self.tool_bytes(repo, path), mtime=0)).decode("ascii")
        return (f"B={blob}; printf %s \"$B\" | base64 -d | gunzip | sha256sum | cut -c1-64 | grep -qx "
                f"'{TOOL_PINS[path]}' || exit 96; printf %s \"$B\" | base64 -d | gunzip | sudo -n {interpreter} "
                f"-I -B - {args}")

    def bundled(self, repo: Path, paths: Sequence[str], args: str) -> tuple[str, bytes]:
        import gzip

        sources = {Path(path).stem: self.tool_bytes(repo, path).decode("utf-8") for path in paths}
        payload = base64.b64encode(gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0))
        pins = ",".join(f"{Path(path).stem}={TOOL_PINS[path]}" for path in paths)
        boot = base64.b64encode(M6.BOOT.encode("ascii")).decode("ascii")
        loader = f"import base64;exec(base64.b64decode('{boot}'))"
        command = (f"B=$(cat); printf %s \"$B\" | sha256sum | cut -c1-64 | grep -qx '{sha256_hex(payload)}' || exit 96; "
                   f"printf %s \"$B\" | base64 -d | sudo -n {M9.RELEASE_PYTHON} -I -B -c \"{loader}\" "
                   f"{pins} {Path(paths[-1]).stem} {args}")
        return command, payload + b"\n"

    def pins(self, repo: Path) -> dict:
        status = self._git(repo, "status", "--porcelain", "--untracked-files=no")
        _need(status.strip() == b"", "CONTROL_CHECKOUT_NOT_CLEAN")
        control = self.control(repo)
        for path in TOOL_PINS:
            self.tool_bytes(repo, path)
        return {"control": control, "tools": dict(TOOL_PINS), "result": "MB10_TOOL_PINS_EXACT"}

    def _operator_at_control(self, repo: Path) -> str:
        operator = sha256_hex(self._git(repo, "show", f"HEAD:{OPERATOR}"))
        _need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")
        _need(sha256_hex(Path(M9.__file__).read_bytes()) == TOOL_PINS[MB9_OPERATOR], "TOOL_PIN_MISMATCH:" + MB9_OPERATOR)
        _need(sha256_hex(Path(M6.__file__).read_bytes()) == TOOL_PINS[M9.MB6_OPERATOR],
              "TOOL_PIN_MISMATCH:" + M9.MB6_OPERATOR)
        _need(sha256_hex(Path(A.__file__).read_bytes()) == TOOL_PINS[M9.MB7_MB8_OPERATOR],
              "TOOL_PIN_MISMATCH:" + M9.MB7_MB8_OPERATOR)
        return operator

    # ----------------------------------------------------------------- helpers ---

    def _now(self) -> str:
        return self.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def expected(repo: Path) -> dict:
        held = _verifier_module(repo).pinned_expected_held(GENESIS)
        return {"held_name": held["name"], "held_sha": held["sha256"], "record": held["record"], "bytes": held["bytes"]}

    def _w10(self, repo: Path, args: str) -> tuple[int | None, dict | None, Any]:
        result = self.remote_bundle(repo, W10_BUNDLE, args)
        try:
            report = json.loads((result.stdout or b"").decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            report = None
        return result.returncode, report if isinstance(report, dict) else None, result

    @staticmethod
    def _opening(workdir: Path) -> tuple[dict, str]:
        path = Path(workdir) / SEQUENCE_DIR / OPENING_FILE
        _need(path.is_file(), "SEQUENCE_NOT_OPENED")
        raw = path.read_bytes()
        return _json_file(path, "OPENING_INVALID"), sha256_hex(raw)

    def _live_opening(self, repo: Path, workdir: Path) -> tuple[dict, str, str]:
        control = self.pins(repo)["control"]
        opening, opening_sha = self._opening(workdir)
        _need(not (Path(workdir) / SEQUENCE_DIR / STOP_FILE).exists(), "SEQUENCE_STOPPED")
        _need(opening.get("control") == control, "CONTROL_NOT_THE_SEQUENCE_CONTROL")
        return opening, opening_sha, control

    @staticmethod
    def _numbered(directory: Path, suffix: str) -> Path:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        index = len([p for p in directory.iterdir()]) + 1
        return directory / f"{index:02d}-{suffix}"

    @staticmethod
    def _marker(workdir: Path) -> Path:
        return Path(workdir) / M9.ATTEMPT_DIR / f"{MARKER}.json"

    @staticmethod
    def _gates(workdir: Path) -> list[Path]:
        directory = Path(workdir) / GATE_DIR
        return sorted(directory.iterdir()) if directory.is_dir() else []

    def _last_gate(self, workdir: Path) -> tuple[dict, str]:
        gates = self._gates(workdir)
        _need(bool(gates), "FRESH_GATE_REQUIRED")
        raw = gates[-1].read_bytes()
        record = _json_file(gates[-1], "GATE_INVALID")
        _need(record.get("exact") is True, "FRESH_GATE_REQUIRED")
        return record, sha256_hex(raw)

    def _posts(self, workdir: Path) -> tuple[list[Path], list[Path]]:
        directory = Path(workdir) / POST_DIR
        runs = sorted(directory.iterdir()) if directory.is_dir() else []
        verified = [run / "POST10_VERIFIED.json" for run in runs if (run / "POST10_VERIFIED.json").is_file()]
        return runs, verified

    def _sequence_records(self, workdir: Path, verifier) -> dict:
        marker = self._marker(workdir).is_file()
        transcript = self._read_class(Path(workdir) / M9.ATTEMPT_DIR, MARKER, verifier)
        runs, verified = self._posts(workdir)
        return {"marker": marker, "transcript": transcript, "post_verified": bool(verified),
                "post_failed": bool(runs) and not verified,
                "adoption_required": marker and transcript != verifier.HELD_RETURNED_EXACT,
                "accepted": (Path(workdir) / ACCEPT_DIR / ACCEPT_FILE).is_file()}

    # ------------------------------------------------------------- owner texts ---

    def _open_values(self, repo: Path, workdir: Path, facts: dict) -> dict:
        control = self.pins(repo)["control"]
        operator = self._operator_at_control(repo)
        _need(isinstance(facts, dict) and set(facts) == set(OPEN_FACTS), "OPEN_FACTS_INVALID")
        _need(isinstance(facts["lastDeployRunId"], str) and _RUN_ID.fullmatch(facts["lastDeployRunId"]) is not None,
              "LAST_DEPLOY_INVALID")
        _need(facts["workflowQueueEmpty"] is True, "WORKFLOW_QUEUE_NOT_EMPTY")
        predecessor = "none"
        if facts["predecessorWorkdir"] is not None:
            predecessor = self._predecessor(repo, Path(facts["predecessorWorkdir"]))
        e = self.expected(repo)
        return {"control": control, "operator": operator, "deploy": facts["lastDeployRunId"],
                "predecessor": predecessor, "held_name": e["held_name"], "held_sha": e["held_sha"]}

    def _predecessor(self, repo: Path, previous: Path) -> str:
        """A linked successor may follow only a predecessor that ended without a HELD write (record §6.3)."""
        opening, opening_sha = self._opening(previous)
        _need(opening.get("operatorSha256") is not None, "PREDECESSOR_INVALID")
        _need(not (previous / ACCEPT_DIR / ACCEPT_FILE).exists() and not self._posts(previous)[1],
              "PREDECESSOR_WROTE_HELD")
        stopped = (previous / SEQUENCE_DIR / STOP_FILE).is_file()
        verifier = _verifier_module(repo)
        transcript = self._read_class(previous / M9.ATTEMPT_DIR, MARKER, verifier)
        _need(stopped or (self._marker(previous).is_file()
                          and transcript not in (verifier.HELD_RETURNED_EXACT, verifier.HELD_RETURNED_NOT_EXACT)),
              "PREDECESSOR_NOT_ENDED_WITHOUT_WRITE")
        return opening_sha

    def _go_values(self, repo: Path, workdir: Path) -> dict:
        opening, _sha, control = self._live_opening(repo, workdir)
        gate, gate_sha = self._last_gate(workdir)
        e = self.expected(repo)
        return {"sequence": opening["sequenceId"], "control": control, "operator": self._operator_at_control(repo),
                "gate": gate_sha, "eligibility": gate["eligibilitySha256"], "invocation": gate["witness"][0],
                "mainpid": gate["witness"][1], "boot": gate["bootId"], "held_name": e["held_name"],
                "held_sha": e["held_sha"]}

    def _accept_values(self, repo: Path, workdir: Path) -> tuple[dict, bool]:
        opening, _sha, _control = self._live_opening(repo, workdir)
        _runs, verified = self._posts(workdir)
        _need(len(verified) == 1, "POST10_NOT_VERIFIED")
        record = _json_file(verified[0], "POST10_INVALID")
        e = self.expected(repo)
        return ({"sequence": opening["sequenceId"], "held_name": e["held_name"], "held_sha": e["held_sha"],
                 "post10": sha256_hex(verified[0].read_bytes())}, record.get("adoptionRequired") is True)

    def render(self, repo: Path, workdir: Path, act: str, facts: Path | None = None) -> dict:
        if act == "D1":
            _need(facts is not None, "FACTS_REQUIRED")
            values, lines = self._open_values(repo, workdir, _json_file(facts, "FACTS_INVALID")), OPEN_LINES
        elif act == "D2":
            values, lines = self._go_values(repo, workdir), GO_LINES
            _need(not self._marker(workdir).exists(), "ATTEMPT_ALREADY_CONSUMED:" + MARKER)
        elif act == "D3":
            values, adoption = self._accept_values(repo, workdir)
            lines = ACCEPT_LINES + ((ADOPTION_LINE,) if adoption else ())
        elif act == "STOP":
            opening, opening_sha, control = self._live_opening(repo, workdir)
            values, lines = {"sequence": opening["sequenceId"], "control": control, "opening": opening_sha}, STOP_LINES
        else:
            raise Stop("ACT_INVALID")
        text = "\n".join(line.format(**values) for line in lines) + "\n"
        self.check_go(text, lines, **values)
        return {"act": act, "text": text, "textSha256": sha256_hex(text.encode("utf-8")), "values": values}

    # ------------------------------------------------------------- local forms ---

    def open(self, repo: Path, workdir: Path, statement: Path, facts: Path) -> dict:
        values = self._open_values(repo, workdir, _json_file(facts, "FACTS_INVALID"))
        raw = Path(statement).read_bytes()
        self.check_go(raw.decode("utf-8"), OPEN_LINES, **values)
        workdir = Path(workdir)
        _need(not (workdir / SEQUENCE_DIR).exists(), "SEQUENCE_ALREADY_OPENED")
        self.candidate(workdir)                                       # the Package A emission copy must be present
        (workdir / SEQUENCE_DIR).mkdir(mode=0o700, parents=True)
        sequence = os.urandom(16).hex()
        self._record(workdir / SEQUENCE_DIR / OPENING_FILE, {
            "act": "D1", "sequenceId": sequence, "openedAt": self._now(), "control": values["control"],
            "operatorSha256": values["operator"], "lastDeployRunId": values["deploy"],
            "predecessor": values["predecessor"], "expectedHeld": {"name": values["held_name"],
                                                                  "sha256": values["held_sha"]},
            "statementSha256": sha256_hex(raw)})
        return {"sequenceId": sequence, "result": "MB10_SEQUENCE_OPENED_READ_ONLY",
                "next": "fresh export, host PRE, owner eligibility, gate; then the separate D2"}

    def stop(self, repo: Path, workdir: Path, statement: Path) -> dict:
        _need(not self._marker(workdir).exists() and not (Path(workdir) / M9.ATTEMPT_DIR).exists(),
              "STOP_REFUSED_ATTEMPT_MARKER_PRESENT")
        values = self.render(repo, workdir, "STOP")["values"]
        raw = Path(statement).read_bytes()
        self.check_go(raw.decode("utf-8"), STOP_LINES, **values)
        try:
            self._record(Path(workdir) / SEQUENCE_DIR / STOP_FILE, {
                "act": "STOP", "statementSha256": sha256_hex(raw), "freeze": "RELEASED",
                "classification": "STOPPED_BEFORE_MARKER"})
        except FileExistsError as exc:
            raise Stop("SEQUENCE_ALREADY_STOPPED") from exc
        return {"result": "MB10_SEQUENCE_STOPPED_BEFORE_MARKER", "next": "nothing is authorized"}

    def accept(self, repo: Path, workdir: Path, statement: Path) -> dict:
        values, adoption = self._accept_values(repo, workdir)
        raw = Path(statement).read_bytes()
        lines = ACCEPT_LINES + ((ADOPTION_LINE,) if adoption else ())
        self.check_go(raw.decode("utf-8"), lines, **values)
        directory = Path(workdir) / ACCEPT_DIR
        directory.mkdir(mode=0o700, exist_ok=True)
        try:
            self._record(directory / ACCEPT_FILE, {"act": "D3", "statementSha256": sha256_hex(raw),
                                                   "post10Sha256": values["post10"], "adoption": adoption})
        except FileExistsError as exc:
            raise Stop("ACCEPTANCE_ALREADY_RECORDED") from exc
        return {"result": "MB10_ACCEPTED", "authorityGranted": False,
                "next": "nothing is authorized; the first deploy after the freeze must compare EQUAL (`dr5`)"}

    def dr5(self, repo: Path, phase: str, log: Path) -> dict:
        target = load_tool(Path(repo), MB10_DR5, "mb10_dr5_target_operator")
        try:
            return target.compare(phase, Path(log).read_bytes().decode("utf-8", "replace"))
        except target.TargetError as exc:
            raise Stop(exc.reason) from exc

    # --------------------------------------------------------- read-only remote ---

    def export(self, repo: Path, workdir: Path) -> dict:
        opening, _sha, control = self._live_opening(repo, workdir)
        out = self._numbered(Path(workdir) / EXPORT_DIR, os.urandom(8).hex())
        out.mkdir(mode=0o700)
        started = self._now()
        result = M9.Operator.chain_export(self, repo, workdir, out / "export")
        receipt = {"receiptType": "LILITH_MB10_CHAIN_EXPORT_RECEIPT", "schemaVersion": 1,
                   "sequenceId": opening["sequenceId"], "control": control, "startedAt": started,
                   "completedAt": self._now(), "files": result["files"], "w9Phase": result["phase"]}
        data = self._record(out / "RECEIPT.json", receipt)
        exact = result["files"] == {"chain-1.json": CHAIN_1_SHA256, "witness.json": CHAIN_1_SHA256}
        return {"export": out.name, "receiptSha256": sha256_hex(data), "files": result["files"],
                "result": "MB10_EXPORT_EXACT" if exact else "MB10_EXPORT_NOT_EXACT"}

    def _reads(self, repo: Path, out: Path, phase: str, workdir: Path) -> dict[str, int]:
        """The Package B POST9B host reads (identity, custody, readiness, preservation, observer, W5, M-B6, W8),
        with the installer stage and the W9 expectation of the M-B10 phase, plus the W10 verifier."""
        status, w9, w10 = {"PRE": ("P1B-9b", "W9_5_GENESIS_COMMITTED_EXACT", "W10_0_PRE_HELD_EXACT"),
                           "POST": ("P1B-10", "W9_LATER_STATE", "W10_1_HELD_EXACT")}[phase]
        args = self._w9_args(workdir)
        codes = {}
        # The Package B reads for the POST9B phase, except the two whose expectation M-B10 changes.
        for name, command in self._package_b_commands(repo, args).items():
            codes[name] = self._save(out, name, command())
        codes["status"] = self._save(out, "status", self.ssh(self.streamed(
            repo, M9.INSTALLER, M9.SYSTEM_PYTHON, f"status --expect {status} {M9.RELEASE_SHA}")))
        codes["w9verifier"] = self._save(out, "w9verifier", self.remote_bundle(repo, M9.VERIFIER_BUNDLE,
                                                                                 f"expect {w9} {args}"))
        codes["w10verifier"] = self._save(out, "w10verifier", self.remote_bundle(repo, W10_BUNDLE,
                                                                                   f"expect {w10} {args}"))
        return codes

    def _package_b_commands(self, repo: Path, args: str) -> dict:
        identity = ("date -u +%FT%TZ; hostname; cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id; "
                    "uname -r; [ -e /var/run/reboot-required ] && echo REBOOT_REQUIRED=present "
                    "|| echo REBOOT_REQUIRED=absent")
        custody = (
            "systemctl show -p Id,LoadState,ActiveState,SubState,UnitFileState,NeedDaemonReload,MainPID,NRestarts,"
            "InvocationID,Result lilith-memory-broker.service lilith-authority-dev.service lilith-authority-dev.socket "
            "lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket "
            "--no-pager; "
            "sudo -n /usr/local/sbin/lilith-activation-verify; echo activation_rc=$?; "
            "sudo -n /usr/bin/ls -A1 /var/lib/lilith-authority-custody /var/lib/lilith-authority-custody/holds; "
            "sudo -n /usr/bin/stat -c '%n %F %U:%G %a %s %h' /var/lib/lilith-authority-custody "
            "/var/lib/lilith-authority-custody/holds; "
            "sudo -n /usr/bin/sha256sum /var/lib/lilith-recovery-witness/chain/1.json "
            "/var/lib/lilith-recovery-witness/witness.json; "
            + M9.TMP_RESIDUE + "; echo TMP_RESIDUE_END")
        readiness = (f"readlink /opt/lilith-authority-dev/current; sudo -n test -x {M9.RELEASE_PYTHON} "
                     f"&& echo RELEASE_PYTHON=executable; sudo -n {M9.RELEASE_PYTHON} -I -B -c \"{M9.READINESS_PROBE}\"")
        return {
            "identity": lambda: self.ssh(identity),
            "custody": lambda: self.ssh(custody),
            "readiness": lambda: self.ssh(readiness),
            "preservation": lambda: self.ssh(self.streamed(repo, M9.BROKER, M9.SYSTEM_PYTHON, "preservation")),
            "observer": lambda: self.ssh(self.streamed(repo, M9.OBSERVER, M9.SYSTEM_PYTHON, "observe")),
            "w5verifier": lambda: self.ssh(self.streamed(repo, M9.W5_VERIFIER, M9.RELEASE_PYTHON,
                                                         "expect OUT_OF_SCOPE_POST_LEDGER")),
            "mb6verifier": lambda: self.remote_bundle(repo, M9.MB6_VERIFIER_BUNDLE,
                                                      f"expect OUT_OF_SCOPE_LATER_STATE {M9.LEDGER_HEAD}"),
            "w8verifier": lambda: self.remote_bundle(repo, M9.W8_BUNDLE, f"expect OUT_OF_SCOPE_LATER_STATE {args}"),
        }

    def host(self, repo: Path, workdir: Path, phase: str) -> dict:
        _need(phase in ("PRE", "POST"), "PHASE_INVALID")
        opening, _sha, _control = self._live_opening(repo, workdir)
        out = self._numbered(Path(workdir) / HOST_DIR, phase)
        out.mkdir(mode=0o700)
        codes = self._reads(repo, out, phase, workdir)
        readiness_ok = codes["readiness"] == 0 and self.readiness_ok((out / "readiness.out").read_bytes())
        residue = A.Operator.tmp_residue((out / "custody.out").read_bytes())
        passed = all(code == 0 for code in codes.values()) and readiness_ok and residue == []
        result = {"phase": phase, "codes": codes, "readinessExact": readiness_ok, "tmpResidue": residue,
                  "sequenceId": opening["sequenceId"], "completedAt": self._now(),
                  "result": f"MB10_HOST_{phase}_" + ("PASS" if passed else "NOT_PASS")}
        self._record(out / "HOST_RESULT.json", result)
        return dict(result, hostDir=out.name)

    @staticmethod
    def _identity(out: Path) -> dict:
        lines = (out / "identity.out").read_text(encoding="utf-8", errors="replace").splitlines()
        return {"bootId": lines[3] if len(lines) > 3 else None,
                "rebootRequired": "absent" if "REBOOT_REQUIRED=absent" in lines else "present_or_unknown"}

    # --------------------------------------------------------------------- gate ---

    def gate(self, repo: Path, workdir: Path, host_dir: str, eligibility: Path, facts_path: Path) -> dict:
        opening, opening_sha, control = self._live_opening(repo, workdir)
        _need(not self._marker(workdir).exists(), "ATTEMPT_ALREADY_CONSUMED:" + MARKER)
        workdir = Path(workdir)
        events: list[str] = []
        consumed = [_json_file(g, "GATE_INVALID") for g in self._gates(workdir)]
        # the host PRE read: this sequence's, never used by an earlier gate, PASS, W10_0 exact
        out = workdir / HOST_DIR / host_dir
        _need(re.fullmatch(r"[0-9]{2}-PRE", host_dir) is not None and out.is_dir(), "HOST_READ_NOT_A_PRE_READ")
        _need(host_dir not in [g.get("hostDir") for g in consumed], "HOST_READ_REUSED")
        host = _json_file(out / "HOST_RESULT.json", "HOST_RESULT_INVALID")
        _need(host.get("sequenceId") == opening["sequenceId"], "HOST_READ_NOT_IN_SEQUENCE")
        if host.get("result") != "MB10_HOST_PRE_PASS":
            events.append("HOST_PRE_NOT_PASS")
        report = _json_file(out / "w10verifier.out", "W10_REPORT_INVALID") if (out / "w10verifier.out").is_file() else {}
        witness = (report.get("witnessInvocationId"), report.get("witnessMainPid"))
        if report.get("phase") != "W10_0_PRE_HELD_EXACT" or report.get("holdClass") != "EMPTY":
            events.append("HOST_NOT_W10_0")
        if report.get("w9PhaseDirect") != "W9_5_GENESIS_COMMITTED_EXACT":
            events.append("W9_NOT_EXACT")
        if witness != ACCEPTED_WITNESS or report.get("witnessNRestarts") != "0":
            events.append("WITNESS_INCARNATION_CHANGED")
        identity = self._identity(out)
        if identity["bootId"] != ACCEPTED_BOOT_ID:
            events.append("BOOT_CHANGED")
        if identity["rebootRequired"] != "absent":
            events.append("REBOOT_REQUIRED_PRESENT_OR_UNKNOWN")
        # the owner eligibility: fresh, ELIGIBLE, bound to a never-consumed export receipt of this sequence
        raw = Path(eligibility).read_bytes()
        record = _json_file(eligibility, "ELIGIBILITY_INVALID")
        receipts = {}
        for run in sorted((workdir / EXPORT_DIR).iterdir()) if (workdir / EXPORT_DIR).is_dir() else []:
            if (run / "RECEIPT.json").is_file():
                receipts[sha256_hex((run / "RECEIPT.json").read_bytes())] = _json_file(run / "RECEIPT.json",
                                                                                       "RECEIPT_INVALID")
        receipt = receipts.get(record.get("exportReceiptSha256"))
        if receipt is None or receipt.get("sequenceId") != opening["sequenceId"]:
            events.append("ELIGIBILITY_NOT_BOUND_TO_THIS_SEQUENCE")
        elif record.get("exportReceiptSha256") in [g.get("exportReceiptSha256") for g in consumed]:
            events.append("EXPORT_REUSED")
        elif receipt.get("files") != {"chain-1.json": CHAIN_1_SHA256, "witness.json": CHAIN_1_SHA256}:
            events.append("EXPORT_NOT_GENESIS")
        elif not (receipt["completedAt"] <= str(record.get("observedAt")) and opening["openedAt"] <= receipt["startedAt"]):
            events.append("ELIGIBILITY_NOT_AFTER_EXPORT")
        if record.get("result") != "MB10_OWNER_ELIGIBLE" or record.get("reasons") != []:
            events.append("OWNER_NOT_ELIGIBLE")
        # the freeze facts: unchanged since the opening
        facts = _json_file(facts_path, "FACTS_INVALID")
        if not isinstance(facts, dict) or set(facts) != set(GATE_FACTS):
            events.append("EVIDENCE_UNKNOWN")
        else:
            if facts["lastDeployRunId"] != opening["lastDeployRunId"]:
                events.append("DEPLOY_SINCE_OPENING")
            if facts["workflowQueueEmpty"] is not True:
                events.append("WORKFLOW_QUEUE_NOT_EMPTY")
        events = sorted(set(events))
        gate = {"stage": "MB10", "sequenceId": opening["sequenceId"], "openingSha256": opening_sha, "control": control,
                "hostDir": host_dir, "hostResultSha256": sha256_hex((out / "HOST_RESULT.json").read_bytes()),
                "w10ReportSha256": sha256_hex((out / "w10verifier.out").read_bytes()) if (out / "w10verifier.out")
                .is_file() else None, "eligibilitySha256": sha256_hex(raw),
                "exportReceiptSha256": record.get("exportReceiptSha256"), "witness": list(witness),
                "bootId": identity["bootId"], "events": events, "exact": not events,
                "route": "CONTINUE" if not events else "REVALIDATE"}
        path = self._numbered(workdir / GATE_DIR, "MB10.json")
        data = self._record(path, gate)
        return {"gate": path.name, "gateSha256": sha256_hex(data), "events": events,
                "result": "MB10_GATE_PASS" if not events else "MB10_GATE_REVALIDATE"}

    # ------------------------------------------------------------------- M-B10 ---

    def mb10(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        workdir = Path(workdir)
        _need(not self._marker(workdir).exists(), "ATTEMPT_ALREADY_CONSUMED:" + MARKER)
        values = self._go_values(repo, workdir)
        raw = Path(go_file).read_bytes()
        self.check_go(raw.decode("utf-8"), GO_LINES, **values)
        _need(PONR_ACKNOWLEDGEMENT in " ".join(raw.decode("utf-8").replace(">", " ").split()), "PONR_NOT_ACKNOWLEDGED")
        verifier = _verifier_module(repo)                                             # before any write
        expected = verifier.pinned_expected_held(GENESIS)
        args = self._w9_args(workdir)
        pre = self._numbered(workdir / "premarker", "W10")
        pre.mkdir(mode=0o700)
        code, report, result = self._w10(repo, f"expect {verifier.W10_0} {args}")
        self._save(pre, "w10verifier", result)
        _need(code == 0 and report is not None and report.get("phase") == verifier.W10_0
              and report.get("holdClass") == verifier.HS_EMPTY, "PRE_STATE_NOT_W10_0")
        _need((report.get("witnessInvocationId"), report.get("witnessMainPid")) == (values["invocation"],
                                                                                    values["mainpid"]),
              "WITNESS_INCARNATION_CHANGED_SINCE_GATE")
        directory = self._one_attempt(workdir, MARKER, raw)
        hold = self._invoke(HOLD_COMMAND)                                            # the ONE HELD write
        self._save(directory, "mb10-hold", hold)
        transcript, detail = verifier.classify_hold_transcript(hold.returncode, hold.stdout or b"",
                                                               hold.stderr or b"", expected=expected)
        self._write_class(directory, MARKER, transcript, detail)
        code2, after, raw2 = self._w10(repo, f"observe {args}")
        self._save(directory, "mb10-w10", raw2)
        phase, hold_class = (after or {}).get("phase"), (after or {}).get("holdClass")
        sequence = verifier.classify_sequence(host_phase=phase or verifier.UNCLASSIFIED,
                                              hold_class=hold_class or verifier.HS_UNREADABLE, marker=True,
                                              transcript=transcript)
        return {"code": hold.returncode, "attempt": "CONSUMED", "transcript": transcript, "detail": detail,
                "hostPhase": phase, "holdClass": hold_class, "sequencePhase": sequence,
                "routing": verifier.SEQUENCE_TABLE[sequence][0],
                "result": "MB10_HELD" if phase == verifier.W10_1 and transcript == verifier.HELD_RETURNED_EXACT
                else "MB10_STOP",
                "next": verifier.SEQUENCE_TABLE[sequence][1]}

    def post(self, repo: Path, workdir: Path) -> dict:
        workdir = Path(workdir)
        self._live_opening(repo, workdir)
        verifier = _verifier_module(repo)
        expected = verifier.pinned_expected_held(GENESIS)
        _need(self._marker(workdir).is_file(), "MB10_NOT_IN_THIS_SEQUENCE")
        _need(not self._posts(workdir)[1], "POST10_ALREADY_VERIFIED")
        args = self._w9_args(workdir)
        code, report, _ = self._w10(repo, f"observe {args}")
        _need(code == 0 and report is not None, "VERIFIER_FAILED")
        records = self._sequence_records(workdir, verifier)
        sequence = verifier.classify_sequence(host_phase=report["phase"], hold_class=report["holdClass"], **records)
        _need(sequence in (verifier.S10_POST_PENDING, verifier.S10_UNACKNOWLEDGED, verifier.S10_POST_NOT_VERIFIED),
              "SEQUENCE_NOT_POST_PENDING:" + sequence)
        out = self._numbered(workdir / POST_DIR, "POST10")
        out.mkdir(mode=0o700)
        codes = self._reads(repo, out, "POST", workdir)
        codes["hold-denial"] = self._save(out, "hold-denial", self.ssh(self.streamed(
            repo, MB10_DENIAL, M9.SYSTEM_PYTHON, "P1B-10")))
        codes["witness-denial"] = self._save(out, "witness-denial", self.ssh(self.streamed(
            repo, M9.WITNESS_DENIAL, M9.SYSTEM_PYTHON, "P1B-9b")))
        codes["denial"] = self._save(out, "denial", self.ssh(self.streamed(repo, M9.DENIAL, M9.SYSTEM_PYTHON, "P1B-5")))
        reply = self.ssh(M9.HEALTH_COMMAND)
        codes["health"] = self._save(out, "health", reply)
        health = M9._verifier_module(repo).check_health(
            reply.stdout or b"", expected_classification="CONSISTENT", kwit_public_key_sha256=M9.KWIT_PUBLIC_KEY_SHA256,
            witness_key_id=M9.KWIT_KEY_ID)
        observe = self.ssh(HOLD_OBSERVE_COMMAND)
        codes["hold-observe"] = self._save(out, "hold-observe", observe)
        fetched = {}
        for name, remote in (("held.json", f"{HOLD_STORE}/{expected['name']}"),
                             ("chain-1.json", f"{WITNESS_STATE}/chain/1.json"),
                             ("witness.json", f"{WITNESS_STATE}/witness.json")):
            result = self.ssh(f"sudo -n /usr/bin/base64 -w0 {remote}")
            codes["export-" + name] = self._save(out, name + ".b64", result)
            if result.returncode == 0:
                data = base64.b64decode((result.stdout or b"").strip(), validate=True)
                (out / name).write_bytes(data)
                fetched[name] = data
        readiness_ok = codes["readiness"] == 0 and self.readiness_ok((out / "readiness.out").read_bytes())
        residue = A.Operator.tmp_residue((out / "custody.out").read_bytes())
        try:
            w10 = json.loads((out / "w10verifier.out").read_bytes().decode("utf-8"))
            observed = json.loads((observe.stdout or b"").decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            w10, observed = {}, {}
        checks = {
            "codesZero": all(c == 0 for c in codes.values()), "readinessExact": readiness_ok, "tmpResidueEmpty":
            residue == [], "w10Phase": w10.get("phase") == verifier.W10_1, "w9DirectLaterState":
            w10.get("w9PhaseDirect") == "W9_LATER_STATE", "w9WitnessSideExact":
            w10.get("w9PhaseHoldJudgedSeparately") == "W9_5_GENESIS_COMMITTED_EXACT",
            "heldBytesExact": fetched.get("held.json") == expected["bytes"],
            "heldVerifierSha": w10.get("observedHeldSha256") == expected["sha256"],
            "holdObserveOneEntry": isinstance(observed.get("listingDigest"), str)
            and _HEX64.fullmatch(observed["listingDigest"]) is not None and observed.get("authorityGranted") is False
            and expected["name"] in json.dumps(observed.get("snapshot")),
            "chainUnchanged": sha256_hex(fetched.get("chain-1.json", b"")) == CHAIN_1_SHA256
            and fetched.get("witness.json") == fetched.get("chain-1.json"),
            "healthExact": health["exact"],
            "witnessUnchanged": (w10.get("witnessInvocationId"), w10.get("witnessMainPid")) == ACCEPTED_WITNESS,
        }
        if all(checks.values()):
            data = self._record(out / "POST10_VERIFIED.json", {
                "heldName": expected["name"], "heldSha256": expected["sha256"], "genesis": GENESIS,
                "holdListingDigest": observed["listingDigest"], "adoptionRequired": records["adoption_required"],
                "holdDenialSha256": sha256_hex((out / "hold-denial.out").read_bytes()),
                "witnessDenialSha256": sha256_hex((out / "witness-denial.out").read_bytes()),
                "denialSha256": sha256_hex((out / "denial.out").read_bytes()),
                "healthSha256": sha256_hex((out / "health.out").read_bytes()), "ownerAccepted": False})
            return {"codes": codes, "post10Sha256": sha256_hex(data), "result": "MB10_POST_VERIFIED",
                    "next": "HARD STOP for the owner acceptance D3" + (" (with the adoption sentence)"
                                                                       if records["adoption_required"] else "")}
        return {"codes": codes, "checks": checks, "result": "MB10_POST_NOT_VERIFIED",
                "next": "STOP: `classify`, then owner review; HELD is forward only and is never re-written"}

    def classify(self, repo: Path, workdir: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code, report, result = self._w10(repo, f"observe {self._w9_args(workdir)}")
        self._save(out, "w10verifier", result)
        _need(code == 0 and report is not None, "VERIFIER_FAILED")
        verifier = _verifier_module(repo)
        records = self._sequence_records(workdir, verifier)
        phase = verifier.classify_sequence(host_phase=report["phase"], hold_class=report["holdClass"], **records)
        disposition, action = verifier.SEQUENCE_TABLE[phase]
        return {"hostPhase": report["phase"], "holdClass": report["holdClass"], "sequencePhase": phase,
                "disposition": disposition, "action": action, "records": records, "result": "MB10_CLASSIFIED"}


USAGE = __doc__.split("| Form |", 1)[1].split("\n\n", 1)[0]


def main(argv: list[str], operator: Operator | None = None) -> int:
    operator = operator or Operator()
    forms = {
        ("pins", 1): lambda a: operator.pins(Path(a[0])),
        ("render", 3): lambda a: operator.render(Path(a[0]), Path(a[1]), a[2]),
        ("render", 4): lambda a: operator.render(Path(a[0]), Path(a[1]), a[2], Path(a[3])),
        ("open", 4): lambda a: operator.open(Path(a[0]), Path(a[1]), Path(a[2]), Path(a[3])),
        ("export", 2): lambda a: operator.export(Path(a[0]), Path(a[1])),
        ("host", 3): lambda a: operator.host(Path(a[0]), Path(a[1]), a[2]),
        ("gate", 5): lambda a: operator.gate(Path(a[0]), Path(a[1]), a[2], Path(a[3]), Path(a[4])),
        ("mb10", 3): lambda a: operator.mb10(Path(a[0]), Path(a[1]), Path(a[2])),
        ("post", 2): lambda a: operator.post(Path(a[0]), Path(a[1])),
        ("classify", 3): lambda a: operator.classify(Path(a[0]), Path(a[1]), Path(a[2])),
        ("accept", 3): lambda a: operator.accept(Path(a[0]), Path(a[1]), Path(a[2])),
        ("stop", 3): lambda a: operator.stop(Path(a[0]), Path(a[1]), Path(a[2])),
        ("dr5", 3): lambda a: operator.dr5(Path(a[0]), a[1], Path(a[2])),
    }
    form = forms.get((argv[0], len(argv) - 1)) if argv else None
    if form is None:
        print("mb10_operator: USAGE" + USAGE, file=sys.stderr)
        return 2
    try:
        result = form(argv[1:])
    except Stop as stop:
        print(f"mb10_operator: STOP {stop.code}", file=sys.stderr)
        return 1
    if argv[0] == "render":
        sys.stdout.write(result["text"])
        print(f"TEXT_SHA256={result['textSha256']}", file=sys.stderr)
        return 0
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
