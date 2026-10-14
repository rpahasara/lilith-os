#!/usr/bin/env python3
"""15B2b-B1b-3e E-19: the owner-laptop operator of `UPGRADE_FROM_P1B10_DEV_SYNTHETIC` (OLD -> the NEW release).

Record: docs/architecture/slice-15b2b-b1b3e-e19-transition-implementation.md. Owner decisions E19-D1 … E19-D5 and
OD-M11-13 are ACCEPTED (direction and scope). SOURCE ONLY: no form below is authorized by this repository; every
mutation needs its own verbatim owner go, rendered here, and each go is consumed by an `O_EXCL` marker written BEFORE
its one remote invocation (no retry, no second invocation path, no rollback, no repair).

It reuses, unchanged: the merged contract `e19_p1b10_upgrade.py` (judgement, U0 / replacement acceptances, POST9A-R),
the observer `e19_maintenance_observer.py`, the M-B10 operator (`mb10_operator.Operator`: the pinned `gcloud compute
ssh` route, the direct-plink stdin route for the mb6 BOOT bundles, the go check, the marker, the record helpers, the
Package B host reads), the byte-unchanged installer `install_authority_dev.py`, and the effective WRB_2 restart
boundary. The release stages run from `e19_release_stages.py`, bundled with the installer. Every form is closed: no
free path, command or principal reaches DEV.

| Form | Effect |
| --- | --- |
| `pins <repo>` | local: clean control checkout; every pinned tool exact |
| `observe <repo> <workdir> <label>` | read-only DEV: one observer bundle (BOOT, inline digest-bound inputs), judged locally |
| `render <repo> <workdir> <U0\\|STAGE\\|STOP\\|SELECT\\|START\\|REPLACEMENT\\|RETIRE>` | local: the exact owner text |
| `accept-u0 <repo> <workdir> <statement>` | local: the owner's verbatim U0 statement -> the U0 acceptance bundle |
| `stage <repo> <workdir> <go>` | **mutation** (E19-GO-STAGE), from U0: `e19-stage` (NEW beside OLD) -> U1 |
| `stop <repo> <workdir> <go>` | **mutation** (E19-GO-STOP), from U1: `STOP_COMMAND` once (ends 8af12bd6…/1580) -> U2 |
| `select <repo> <workdir> <go>` | **mutation** (E19-GO-SELECT), from U2: `e19-select` (current -> NEW) -> U3 |
| `start <repo> <workdir> <go>` | **mutation** (E19-GO-START), from U3: `START_COMMAND` once (ONE K-WIT load) -> U4 |
| `post9a-r <repo> <workdir>` | read-only DEV, U4: observer bundle + the P1B-9b / P1B-10 / P1B-5 denial proofs -> POST9A-R |
| `accept-replacement <repo> <workdir> <statement>` | local: the owner's verbatim replacement statement (VERIFIED POST9A-R) |
| `retire <repo> <workdir> <go>` | **mutation** (E19-GO-RETIRE), from U4 + the accepted replacement: `e19-retire-old` -> U5 |
| `host <repo> <workdir> <U0\\|U1\\|U4\\|U5>` | read-only DEV: the two-release-aware Package B host reads (blocker C) |

    observation != classification != permission;  one start go != one K-WIT load (counted, never inferred)
    POST9A-R VERIFIED != replacement accepted (the owner's verbatim statement);  U5 != package READY

The NEW release identity (`E.NEW_RELEASE`, `E.NEW_MANIFEST_SHA256`) is established only by a later merged owner pin
after the reproducible build and attestation; until then every DEV form refuses (`NEW_RELEASE_NOT_ESTABLISHED`).
It never reloads a unit, never starts or stops one except the two reviewed commands, never starts the signer, loads
K-ACT, writes HELD or the ledger, activates authority, or prepares First Memory.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import e19_maintenance_observer as O  # noqa: E402  (pinned below)
import e19_p1b10_upgrade as E  # noqa: E402  (the merged contract; pinned below)
import mb10_operator as M10  # noqa: E402  (pinned M-B10 operator; reused unchanged)

M9 = M10.M9
M6 = M9.M6
A = M9.A
Stop = M9.Stop
_need = M9._need
sha256_hex = M9.sha256_hex

OPERATOR = "services/owner-memory-control/tools/e19_operator.py"
CONTRACT = "services/owner-memory-control/tools/e19_p1b10_upgrade.py"
OBSERVER = "services/owner-memory-control/tools/e19_maintenance_observer.py"
STAGES = "services/owner-memory-control/tools/e19_release_stages.py"
RESTART_BOUNDARY = "services/owner-memory-control/tools/mb11_restart_boundary.py"
RESTART_BOUNDARY_INSTALL = "services/owner-memory-control/tools/mb11_restart_boundary_install.py"
MB10_OPERATOR = M10.OPERATOR
TOOL_PINS = {
    **{path: M10.TOOL_PINS[path] for path in (
        M9.INSTALLER, M9.W5_VERIFIER, M9.MB6_VERIFIER, M9.MB8_VERIFIER, M9.VERIFIER, M10.MB10_VERIFIER, M9.BROKER,
        M9.OBSERVER, M9.DENIAL, M9.WITNESS_DENIAL, M10.MB10_DENIAL, M9.MB6_OPERATOR, M9.MB7_MB8_OPERATOR,
        M10.MB9_OPERATOR)},
    MB10_OPERATOR: "74e1611fd067b67841029b6d2ae0189e2b2d417bc88122811bde11f3bea5042b",
    CONTRACT: O.E19_CONTRACT_SHA256,
    OBSERVER: "bc3017d13a222db7af7aa590a8efeaf8959f8840ffbbf9e14c69b3de1ac4a38e",
    STAGES: "77279d4546db1da85dac489ccbcbf477adc9a3f1a9fcea274fc487ff0ab0396d",
    RESTART_BOUNDARY: "10147341819c27bb3720a87264ffea78f1bf1c3c2a23d7804ac900370cfe7419",
    RESTART_BOUNDARY_INSTALL: "44ab3f048ffe5b2cbe8e721f469e3a913004be87a1d6dfcb8092bb575e452b48",
}
# The observer runs in ONE BOOT bundle with the W10 chain (it judges W9 / M-B6 / W10 in-process), the restart-boundary
# helpers, the contract and the pinned broker reader. Dependency order: each import is registered before it executes.
OBSERVER_BUNDLE = (M9.W5_VERIFIER, M9.MB6_VERIFIER, M9.MB8_VERIFIER, M9.VERIFIER, M10.MB10_VERIFIER, RESTART_BOUNDARY,
                   RESTART_BOUNDARY_INSTALL, CONTRACT, M9.BROKER, OBSERVER)
# The release stages run with the byte-unchanged installer and the contract under the system interpreter (as every
# installer stage).
STAGES_BUNDLE = (M9.INSTALLER, CONTRACT, STAGES)
DENIALS = {"P1B-9b": M9.WITNESS_DENIAL, "P1B-10": M10.MB10_DENIAL, "P1B-5": M9.DENIAL}

# The accepted W10 judgement inputs (M-B6 head; M-B9b genesis and its candidate `updatedAt`, completion records).
LEDGER_HEAD = A.LEDGER_HEAD
GENESIS = M10.GENESIS
GENESIS_UPDATED_AT = "2026-10-08T07:21:43Z"
STOP_COMMAND = "sudo -n " + E.STOP_COMMAND
START_COMMAND = "sudo -n " + E.START_COMMAND
# The owner's transfer of the attested NEW archive and its builder stamp (a separate owner act, gcloud scp; M-A1
# precedent). The stage form reads exactly these two host paths, never a free argument.
TRANSFER_DIR = f"/home/{M9.OSLOGIN_USER}/lilith-e19-transfer"
OBS_DIR, STEP_DIR, HOST_DIR, POST_DIR, ACCEPT_DIR = "observations", "steps", "host", "post9a-r", "acceptance"
U0_FILE, REPLACEMENT_FILE = "U0_ACCEPTANCE.json", "REPLACEMENT_ACCEPTANCE.json"

# Mutating steps: (required pre-phase, expected post-phase, marker).
STEPS = {"STAGE": (E.U0, E.U1, "e19-stage"), "STOP": (E.U1, E.U2, "e19-stop"), "SELECT": (E.U2, E.U3, "e19-select"),
         "START": (E.U3, E.U4, "e19-start"), "RETIRE": (E.U4, E.U5, "e19-retire")}
# Two-release-aware host reads: the phases with a running witness, the selected release, the stages state.
HOST_PHASES = {E.U0: (E.OLD_RELEASE, "E19_OLD_ONLY"), E.U1: (E.OLD_RELEASE, "E19_NEW_STAGED"),
               E.U4: ("NEW", "E19_NEW_SELECTED"), E.U5: ("NEW", "E19_OLD_RETIRED")}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

GO_COMMON = ("Mode: UPGRADE_FROM_P1B10_DEV_SYNTHETIC (E-19, DEV_SYNTHETIC). OLD release {old}; NEW release {new}, "
             "manifest SHA-256 {manifest}.",
             "Control commit: {control}. Operator: " + OPERATOR + " SHA-256 {operator}.",
             "U0 baseline statement SHA-256: {u0}. Latest {phase} observation SHA-256: {observation}.")
GO_LINES = {
    "STAGE": ("I authorize E19-GO-STAGE now: stage releases/{new} beside releases/{old} on lilith-dev-01, exactly one "
              "invocation of e19_release_stages e19-stage.",
              "Archive " + TRANSFER_DIR + "/release-{new}.tar.gz and builder stamp " + TRANSFER_DIR
              + "/release-{new}.json, transferred by me.",
              "This authorizes staging only: not the witness stop, the selector change, a K-WIT load, retirement, the "
              "signer or authority."),
    "STOP": ("I authorize E19-GO-STOP now: `" + STOP_COMMAND + "`, exactly one invocation.",
             "It ends the witness incarnation " + E.ENDING_INCARNATION[0] + " / " + E.ENDING_INCARNATION[1]
             + "; the service and both sockets stop in one transaction and nothing may contact a witness socket "
               "until the replacement start.",
             "This authorizes the stop only: not the selector change, a K-WIT load, retirement, the signer or "
             "authority."),
    "SELECT": ("I authorize E19-GO-SELECT now: point current to releases/{new} while the witness is stopped, exactly one "
               "invocation of e19_release_stages e19-select.",
               "This authorizes the selector change only: not a K-WIT load, retirement, the signer or authority."),
    "START": ("I authorize E19-GO-START now: `" + START_COMMAND + "`, exactly one invocation; exactly one K-WIT "
              "load of the custodied blob, no automatic retry.",
              "This authorizes the replacement start only: not its acceptance, retirement, the signer or authority."),
    "RETIRE": ("I authorize E19-GO-RETIRE now: remove releases/{old}, exactly one invocation of e19_release_stages "
               "e19-retire-old, while the accepted replacement {invocation} runs from releases/{new}.",
               "Replacement acceptance statement SHA-256: {replacement}.",
               "This authorizes the retirement only: not package READY, the signer, M-B11 or authority."),
}


def _json(path: Path, reason: str) -> Any:
    try:
        return json.loads(Path(path).read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise Stop(reason) from exc


def release_modules(release: str, new_release: str | None) -> dict[str, str]:
    """The release modules the readiness probe loads (M-B6 RELEASE_MODULES + PROVISION_MODULES), for OLD (the
    accepted pins of the installed release) or NEW (exactly `PAYLOAD_DELTA` moved: record §3.2). Anything else has
    no pins."""
    old = {**M6.RELEASE_MODULES, **M6.PROVISION_MODULES}
    if release == E.OLD_RELEASE:
        return old
    _need(release == new_release and isinstance(new_release, str), "RELEASE_NOT_OLD_OR_NEW")
    return E.new_release_module_pins(old)


def readiness_ok_for(raw: bytes, release: str, new_release: str | None) -> bool:
    """The Package B readiness judgement (`mb9_operator.readiness_ok`) for the SELECTED release of the phase: the
    selector target and the module pins of exactly that release; the fixed CLIs are byte-identical in both."""
    lines = raw.decode("utf-8", "replace").splitlines()
    if len(lines) != 3 or lines[0] != f"releases/{release}" or lines[1] != "RELEASE_PYTHON=executable":
        return False
    try:
        probe = json.loads(lines[2])
        modules = {file: digest for file, digest in probe.get("modules", {}).values()}
        expected = release_modules(release, new_release)
    except (ValueError, AttributeError, TypeError, Stop):
        return False
    return (modules == expected and probe.get("ledgerCli") == M6.LEDGER_CLI_SHA256
            and probe.get("verifyCli") == A.VERIFY_CLI_SHA256 and probe.get("witnessOwnerCli") == M9.OWNER_CLI_SHA256
            and probe.get("release") == "/opt/lilith-authority-dev/current" and probe.get("deserialize") is True)


@dataclass
class Operator(M10.Operator):
    """`new_release` / `new_manifest` default to the merged contract pins (None until the owner pin): TEST seams."""

    new_release: str | None = E.NEW_RELEASE
    new_manifest: str | None = E.NEW_MANIFEST_SHA256

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

    def bundled(self, repo: Path, paths: Sequence[str], args: str,
                interpreter: str = M9.RELEASE_PYTHON) -> tuple[str, bytes]:
        """The reviewed mb6 BOOT stdin bundle (`mb10_operator.bundled`) with the interpreter explicit."""
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

    def pins(self, repo: Path) -> dict:
        status = self._git(repo, "status", "--porcelain", "--untracked-files=no")
        _need(status.strip() == b"", "CONTROL_CHECKOUT_NOT_CLEAN")
        control = self.control(repo)
        for path in TOOL_PINS:
            self.tool_bytes(repo, path)
        operator = sha256_hex(self._git(repo, "show", f"HEAD:{OPERATOR}"))
        _need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")
        for module, path in ((O, OBSERVER), (E, CONTRACT), (M10, MB10_OPERATOR), (M9, M10.MB9_OPERATOR),
                             (M6, M9.MB6_OPERATOR), (A, M9.MB7_MB8_OPERATOR)):         # every imported operator module
            _need(sha256_hex(Path(module.__file__).read_bytes()) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return {"control": control, "operatorSha256": operator, "tools": dict(TOOL_PINS), "result": "E19_TOOL_PINS_EXACT"}

    def _new_release(self) -> tuple[str, str]:
        new, manifest = self.new_release, self.new_manifest
        _need(isinstance(new, str) and M6._SHA40.fullmatch(new) is not None and new != E.OLD_RELEASE
              and isinstance(manifest, str) and _HEX64.fullmatch(manifest) is not None, "NEW_RELEASE_NOT_ESTABLISHED")
        return new, manifest

    # ------------------------------------------------------------ local records ---

    def _u0(self, workdir: Path) -> dict | None:
        path = Path(workdir) / ACCEPT_DIR / U0_FILE
        if not path.is_file():
            return None
        bundle = _json(path, "U0_ACCEPTANCE_INVALID")
        E.trusted_baseline(bundle, new_release=self._new_release()[0])            # re-verified on every use
        return bundle

    def _replacement(self, workdir: Path, u0: dict | None) -> dict | None:
        path = Path(workdir) / ACCEPT_DIR / REPLACEMENT_FILE
        if not path.is_file():
            return None
        _need(u0 is not None, "U0_ACCEPTANCE_REQUIRED")
        bundle = _json(path, "REPLACEMENT_ACCEPTANCE_INVALID")
        E.trusted_replacement(bundle, u0, new_release=self._new_release()[0])
        return bundle

    @staticmethod
    def _new_numbered(directory: Path, suffix: str) -> Path:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = directory / f"{len(list(directory.iterdir())) + 1:02d}-{suffix}"
        path.mkdir(mode=0o700)
        return path

    def judge(self, workdir: Path, bundle: dict) -> dict:
        """The merged classifier, against the accepted U0 bundle and (U5) the verified replacement acceptance. Without
        an accepted U0 only the U0 candidate is judged (any other observation is refused)."""
        new = self._new_release()[0]
        u0 = self._u0(workdir)
        if u0 is None:
            try:
                verdict = E.classify(bundle["observation"], new_release=new)
            except E.Refused as exc:
                return {"phase": "REFUSED:" + exc.reason, "maintenanceReady": False}
            reasons = O.boundary_reasons(bundle["observation"]) + O.unit_fragment_reasons(bundle)
            return {**verdict, "restartBoundaryReasons": reasons, "maintenanceReady": verdict["phase"] == E.U0
                    and not reasons}
        try:
            return O.verify(bundle, u0, self._replacement(workdir, u0), new_release=new)
        except E.Refused as exc:
            return {"phase": "REFUSED:" + exc.reason, "maintenanceReady": False}

    # ------------------------------------------------------------ read-only DEV ---

    def _observe(self, repo: Path, workdir: Path, label: str) -> tuple[Path, dict | None, dict]:
        new, _ = self._new_release()
        u0 = self._u0(workdir)
        inputs = {"newRelease": new, "afterCursor": None if u0 is None else u0["observation"]["journalCursor"],
                  "expectedHead": LEDGER_HEAD, "candidateDigest": GENESIS, "updatedAt": GENESIS_UPDATED_AT}
        encoded, digest = O.encode_inputs(inputs)
        out = self._new_numbered(Path(workdir) / OBS_DIR, label)
        result = self.remote_bundle(repo, OBSERVER_BUNDLE, "observe-inline " + shlex.quote(encoded) + " " + digest)
        code = self._save(out, "observer", result)
        bundle = None
        if code == 0:
            try:
                bundle = json.loads((result.stdout or b"").decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                bundle = None
        if not isinstance(bundle, dict) or bundle.get("bundleType") != O.BUNDLE_TYPE \
                or bundle.get("inputsSha256") != digest:
            verdict = {"phase": "OBSERVATION_NOT_RECEIVED", "maintenanceReady": False, "code": code}
            bundle = None
        else:
            verdict = self.judge(workdir, bundle)
        self._record(out / "VERDICT.json", {"verdict": verdict, "inputsSha256": digest,
                                            "observationSha256": None if bundle is None else
                                            E.document_sha256(bundle["observation"])})
        return out, bundle, verdict

    def observe(self, repo: Path, workdir: Path, label: str) -> dict:
        self.pins(repo)
        _need(re.fullmatch(r"[0-9A-Za-z_]{1,24}", label) is not None, "LABEL_INVALID")
        out, bundle, verdict = self._observe(repo, workdir, label)
        return {"observationDir": out.name, "phase": verdict["phase"], "maintenanceReady": verdict["maintenanceReady"],
                "result": "E19_OBSERVED" if bundle is not None else "E19_OBSERVATION_NOT_RECEIVED"}

    def _latest(self, workdir: Path, phase: str) -> tuple[Path, dict]:
        """The latest recorded observation, required to be exactly `phase` and maintenance-ready."""
        runs = sorted((Path(workdir) / OBS_DIR).iterdir()) if (Path(workdir) / OBS_DIR).is_dir() else []
        _need(bool(runs), "NO_OBSERVATION")
        latest = runs[-1]
        verdict = _json(latest / "VERDICT.json", "VERDICT_INVALID")["verdict"]
        _need(verdict.get("phase") == phase and verdict.get("maintenanceReady") is True,
              f"LATEST_OBSERVATION_NOT_{phase}:{verdict.get('phase')}")
        bundle = _json(latest / "observer.out", "OBSERVATION_INVALID")
        _need(self.judge(workdir, bundle).get("phase") == phase, "OBSERVATION_REJUDGED_DIFFERENTLY")
        return latest, bundle

    # ------------------------------------------------------------------ owner texts ---

    def render(self, repo: Path, workdir: Path, what: str) -> dict:
        pins = self.pins(repo)
        new, manifest = self._new_release()
        if what == "U0":
            _need(self._u0(workdir) is None, "U0_ALREADY_ACCEPTED")
            _, bundle = self._latest(workdir, E.U0)
            text = E.render_u0_statement(bundle["observation"], new_release=new)
        elif what == "REPLACEMENT":
            u0 = self._u0(workdir)
            _need(u0 is not None, "U0_ACCEPTANCE_REQUIRED")
            text = E.render_replacement_statement(self._post9a_r_evidence(workdir), u0, new_release=new)
        else:
            _need(what in STEPS, "RENDER_INVALID")
            text = self._go_text(workdir, what, pins, new, manifest).encode("ascii")
        return {"text": text.decode("ascii"), "textSha256": sha256_hex(text)}

    def _go_values(self, workdir: Path, step: str, pins: dict, new: str, manifest: str) -> dict:
        u0 = self._u0(workdir)
        _need(u0 is not None, "U0_ACCEPTANCE_REQUIRED")
        phase = STEPS[step][0]
        latest, bundle = self._latest(workdir, phase)
        values = {"old": E.OLD_RELEASE, "new": new, "manifest": manifest, "control": pins["control"],
                  "operator": pins["operatorSha256"], "u0": sha256_hex(E._statement_bytes(u0["statement"])),
                  "phase": phase, "observation": E.document_sha256(bundle["observation"])}
        if step == "RETIRE":
            replacement = self._replacement(workdir, u0)
            _need(replacement is not None, "REPLACEMENT_ACCEPTANCE_REQUIRED")
            values["invocation"] = replacement["record"]["invocationId"]
            values["replacement"] = sha256_hex(E._statement_bytes(replacement["statement"]))
        return values

    def _go_text(self, workdir: Path, step: str, pins: dict, new: str, manifest: str) -> str:
        values = self._go_values(workdir, step, pins, new, manifest)
        return "\n".join(line.format(**values) for line in GO_LINES[step] + GO_COMMON) + "\n"

    def _accept(self, workdir: Path, name: str, bundle: dict) -> bytes:
        directory = Path(workdir) / ACCEPT_DIR
        directory.mkdir(mode=0o700, exist_ok=True)
        try:
            return self._record(directory / name, bundle)
        except FileExistsError as exc:
            raise Stop("ACCEPTANCE_ALREADY_RECORDED:" + name) from exc

    def accept_u0(self, repo: Path, workdir: Path, statement: Path) -> dict:
        self.pins(repo)
        new = self._new_release()[0]
        _need(self._u0(workdir) is None, "U0_ALREADY_ACCEPTED")
        _, bundle = self._latest(workdir, E.U0)
        raw = Path(statement).read_bytes()
        _need(raw == E.render_u0_statement(bundle["observation"], new_release=new), "STATEMENT_NOT_CANONICAL")
        doc = E.parse_observation(bundle["observation"], new_release=new)
        acceptance = {"observation": bundle["observation"], "statement": raw.decode("ascii"),
                      "record": E.acceptance_record(E.U0_RECORD_TYPE, doc, raw, new_release=new,
                                                    invocation=E.ENDING_INCARNATION, cursor=doc["journalCursor"])}
        E.trusted_baseline(acceptance, new_release=new)
        data = self._accept(workdir, U0_FILE, acceptance)
        return {"u0AcceptanceSha256": sha256_hex(data), "journalCursor": doc["journalCursor"],
                "result": "E19_U0_BASELINE_ACCEPTANCE_RECORDED",
                "next": "nothing is authorized; staging needs the separate E19-GO-STAGE"}

    # --------------------------------------------------------------------- mutations ---

    def _mutation(self, repo: Path, workdir: Path, step: str, go_file: Path) -> dict:
        """One owner go, one fresh read-only gate, one marker, ONE remote invocation, one read-only post observation."""
        pins = self.pins(repo)
        new, manifest = self._new_release()
        pre_phase, post_phase, marker = STEPS[step]
        raw = Path(go_file).read_bytes()
        self.check_go(raw.decode("utf-8"), GO_LINES[step] + GO_COMMON,
                      **self._go_values(workdir, step, pins, new, manifest))
        _need(not (Path(workdir) / M6.ATTEMPT_DIR / f"{marker}.json").exists(), "ATTEMPT_ALREADY_CONSUMED:" + marker)
        gate, bundle, verdict = self._observe(repo, workdir, f"{step}_PRE")           # read-only, before the marker
        _need(bundle is not None and verdict.get("phase") == pre_phase and verdict.get("maintenanceReady") is True,
              f"GATE_NOT_{pre_phase}:{verdict.get('phase')}")
        if step == "RETIRE":
            accepted = self._replacement(workdir, self._u0(workdir))["record"]
            service = bundle["observation"]["witness"]["service"]
            _need((service["InvocationID"], service["MainPID"]) == (accepted["invocationId"], accepted["mainPid"]),
                  "RUNNING_INCARNATION_NOT_THE_ACCEPTED_REPLACEMENT")
        command, stdin = self._command(repo, step, new, manifest, workdir)
        out = self._new_numbered(Path(workdir) / STEP_DIR, step)
        self._one_attempt(workdir, marker, raw)                                        # the go is consumed HERE
        result = self._invoke_once(command, stdin)
        code = self._save(out, marker, result)
        post_dir, post_bundle, post = self._observe(repo, workdir, f"{step}_POST")
        reached = post.get("phase") == post_phase and post.get("maintenanceReady") is True
        record = {"step": step, "marker": marker, "goSha256": sha256_hex(raw), "gate": gate.name, "code": code,
                  "post": post_dir.name, "postPhase": post.get("phase"), "expected": post_phase,
                  "result": f"E19_{step}_" + ("REACHED_" + post_phase if code == 0 and reached else "STOP")}
        self._record(out / "STEP.json", record)
        return dict(record, next="nothing further is authorized by this; the next step needs its own owner go"
                    if code == 0 and reached else "STOP: no retry; read-only re-observation and owner adjudication")

    def _command(self, repo: Path, step: str, new: str, manifest: str, workdir: Path) -> tuple[str, bytes | None]:
        old = E.OLD_RELEASE
        if step == "STOP":
            return STOP_COMMAND, None
        if step == "START":
            return START_COMMAND, None
        if step == "STAGE":
            args = (f"e19-stage {old} {new} {manifest} {TRANSFER_DIR}/release-{new}.tar.gz "
                    f"{TRANSFER_DIR}/release-{new}.json")
        elif step == "SELECT":
            args = f"e19-select {old} {new}"
        else:
            invocation = self._replacement(workdir, self._u0(workdir))["record"]["invocationId"]
            args = f"e19-retire-old {old} {new} {invocation}"
        return self.bundled(repo, STAGES_BUNDLE, args, M9.SYSTEM_PYTHON)

    def _invoke_once(self, command: str, stdin: bytes | None):
        """The one remote invocation: the reviewed `gcloud compute ssh` route for a plain command, the direct-plink
        stdin route for a BOOT bundle. A local timeout or launch failure is recorded, never retried."""
        import subprocess

        if stdin is None:
            return self._invoke(command)
        try:
            return self.plink_stdin(command, stdin)
        except subprocess.TimeoutExpired as exc:
            return subprocess.CompletedProcess(exc.cmd, None, exc.output or b"", exc.stderr or b"")
        except OSError as exc:
            return subprocess.CompletedProcess([], None, b"", f"LOCAL_{type(exc).__name__}".encode("ascii"))

    def stage(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        return self._mutation(repo, workdir, "STAGE", go_file)

    def stop(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        return self._mutation(repo, workdir, "STOP", go_file)

    def select(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        return self._mutation(repo, workdir, "SELECT", go_file)

    def start(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        return self._mutation(repo, workdir, "START", go_file)

    def retire(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        return self._mutation(repo, workdir, "RETIRE", go_file)

    # ---------------------------------------------------------- POST9A-R and acceptance ---

    def post9a_r(self, repo: Path, workdir: Path) -> dict:
        self.pins(repo)
        new = self._new_release()[0]
        u0 = self._u0(workdir)
        _need(u0 is not None, "U0_ACCEPTANCE_REQUIRED")
        obs_dir, bundle, verdict = self._observe(repo, workdir, "POST9A_R")
        _need(bundle is not None and verdict.get("phase") == E.U4, "OBSERVATION_NOT_U4:" + str(verdict.get("phase")))
        out = self._new_numbered(Path(workdir) / POST_DIR, "POST9A_R")
        denials = {}
        for proof, path in sorted(DENIALS.items()):
            result = self.ssh(self.streamed(repo, path, M9.SYSTEM_PYTHON, proof))
            self._save(out, proof, result)
            denials[proof] = (result.stdout or b"", result.returncode)
        report = O.post9a_r(bundle, denials, u0, new_release=new)
        data = self._record(out / "POST9A_R.json", {**report, "observationDir": obs_dir.name})
        return {"post9aRDir": out.name, "result": report["result"], "reasons": report["reasons"],
                "invocationId": report["invocationId"], "mainPid": report["mainPid"], "recordSha256": sha256_hex(data),
                "next": "the owner's verbatim replacement statement (`render REPLACEMENT`); nothing is accepted by this"}

    def _post9a_r_evidence(self, workdir: Path) -> dict:
        runs = sorted((Path(workdir) / POST_DIR).iterdir()) if (Path(workdir) / POST_DIR).is_dir() else []
        _need(bool(runs), "NO_POST9A_R")
        report = _json(runs[-1] / "POST9A_R.json", "POST9A_R_INVALID")
        _need(report.get("result") == "POST9A_R_VERIFIED", "POST9A_R_NOT_VERIFIED")
        return report["evidence"]

    def accept_replacement(self, repo: Path, workdir: Path, statement: Path) -> dict:
        self.pins(repo)
        new = self._new_release()[0]
        u0 = self._u0(workdir)
        _need(u0 is not None, "U0_ACCEPTANCE_REQUIRED")
        _need(self._replacement(workdir, u0) is None, "REPLACEMENT_ALREADY_ACCEPTED")
        evidence = self._post9a_r_evidence(workdir)
        raw = Path(statement).read_bytes()
        _need(raw == E.render_replacement_statement(evidence, u0, new_release=new), "STATEMENT_NOT_CANONICAL")
        report = E.post9a_r(evidence, u0, new_release=new)
        acceptance = {"evidence": evidence, "statement": raw.decode("ascii"),
                      "record": E.acceptance_record(E.REPLACEMENT_RECORD_TYPE, evidence, raw, new_release=new,
                                                    invocation=(report["invocationId"], report["mainPid"]),
                                                    cursor=u0["observation"]["journalCursor"])}
        E.trusted_replacement(acceptance, u0, new_release=new)
        data = self._accept(workdir, REPLACEMENT_FILE, acceptance)
        return {"replacementAcceptanceSha256": sha256_hex(data), "invocationId": report["invocationId"],
                "result": "E19_REPLACEMENT_ACCEPTANCE_RECORDED",
                "next": "nothing is authorized; retiring OLD needs the separate E19-GO-RETIRE"}

    # ------------------------------------------------- two-release-aware host reads (C) ---

    def host(self, repo: Path, workdir: Path, phase: str) -> dict:
        """The Package B host reads (`mb10_operator`) for a phase with a running witness, judged against the SELECTED
        release of that phase: readiness by that release's module pins (OLD: the accepted M-B6 pins; NEW: exactly
        `PAYLOAD_DELTA` moved) and the installer state by `e19-status` (whose only admissible installer failure while
        two releases are installed is RELEASE_SET) instead of the single-release `status --expect P1B-10 <OLD>`.
        W9 (direct LATER, seamed W9_5) and W10 (W10_1_HELD_EXACT) are unchanged and release-agnostic."""
        self.pins(repo)
        new, _ = self._new_release()
        _need(phase in HOST_PHASES, "HOST_PHASE_INVALID")
        selected, expected_state = HOST_PHASES[phase]
        selected = new if selected == "NEW" else selected
        out = self._new_numbered(Path(workdir) / HOST_DIR, phase)
        args = f"{LEDGER_HEAD} {GENESIS} {GENESIS_UPDATED_AT}"
        codes = {name: self._save(out, name, command()) for name, command in self._package_b_commands(repo, args).items()}
        command, stdin = self.bundled(repo, STAGES_BUNDLE, f"e19-status {E.OLD_RELEASE} {new}", M9.SYSTEM_PYTHON)
        codes["e19status"] = self._save(out, "e19status", self.plink_stdin(command, stdin))
        codes["w9verifier"] = self._save(out, "w9verifier", self.remote_bundle(repo, M9.VERIFIER_BUNDLE,
                                                                                 f"expect W9_LATER_STATE {args}"))
        codes["w10verifier"] = self._save(out, "w10verifier", self.remote_bundle(repo, M10.W10_BUNDLE,
                                                                                   f"expect W10_1_HELD_EXACT {args}"))
        readiness = codes["readiness"] == 0 and readiness_ok_for((out / "readiness.out").read_bytes(), selected, new)
        try:
            state = json.loads((out / "e19status.out").read_bytes().decode("utf-8")).get("state")
        except (UnicodeDecodeError, ValueError, AttributeError):
            state = None
        residue = A.Operator.tmp_residue((out / "custody.out").read_bytes())
        passed = all(code == 0 for code in codes.values()) and readiness and state == expected_state and residue == []
        result = {"phase": phase, "selectedRelease": selected, "codes": codes, "readinessExact": readiness,
                  "e19State": state, "tmpResidue": residue,
                  "result": f"E19_HOST_{phase}_" + ("PASS" if passed else "NOT_PASS")}
        self._record(out / "HOST_RESULT.json", result)
        return dict(result, hostDir=out.name)


USAGE = __doc__.split("| Form |", 1)[1].split("\n\n", 1)[0]


def main(argv: list[str], operator: Operator | None = None) -> int:
    operator = operator or Operator()
    forms = {
        ("pins", 1): lambda a: operator.pins(Path(a[0])),
        ("observe", 3): lambda a: operator.observe(Path(a[0]), Path(a[1]), a[2]),
        ("render", 3): lambda a: operator.render(Path(a[0]), Path(a[1]), a[2]),
        ("accept-u0", 3): lambda a: operator.accept_u0(Path(a[0]), Path(a[1]), Path(a[2])),
        ("stage", 3): lambda a: operator.stage(Path(a[0]), Path(a[1]), Path(a[2])),
        ("stop", 3): lambda a: operator.stop(Path(a[0]), Path(a[1]), Path(a[2])),
        ("select", 3): lambda a: operator.select(Path(a[0]), Path(a[1]), Path(a[2])),
        ("start", 3): lambda a: operator.start(Path(a[0]), Path(a[1]), Path(a[2])),
        ("post9a-r", 2): lambda a: operator.post9a_r(Path(a[0]), Path(a[1])),
        ("accept-replacement", 3): lambda a: operator.accept_replacement(Path(a[0]), Path(a[1]), Path(a[2])),
        ("retire", 3): lambda a: operator.retire(Path(a[0]), Path(a[1]), Path(a[2])),
        ("host", 3): lambda a: operator.host(Path(a[0]), Path(a[1]), a[2]),
    }
    form = forms.get((argv[0], len(argv) - 1)) if argv else None
    if form is None:
        print("e19_operator: USAGE" + USAGE, file=sys.stderr)
        return 2
    try:
        result = form(argv[1:])
    except (Stop, E.Refused) as exc:
        print(f"e19_operator: STOP {getattr(exc, 'code', None) or exc}", file=sys.stderr)
        return 1
    if argv[0] == "render":
        sys.stdout.write(result["text"])
        print(f"TEXT_SHA256={result['textSha256']}", file=sys.stderr)
        return 0
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
