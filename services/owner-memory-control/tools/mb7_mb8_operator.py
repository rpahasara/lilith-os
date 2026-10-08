"""15B2b-B1b-3e Package A (M-B7 PREPARE_GENESIS_CANDIDATE + M-B8 PIN_GENESIS): the reviewed owner-laptop operator.

Record: docs/architecture/slice-15b2b-b1b3e-mb7-mb8-genesis-prep-package.md.
SOURCE PREPARED / NOT AUTHORIZED: no form below is authorized by this
repository; each live use needs its own explicit owner authorization. The
templates bind the owner-ACCEPTED continuity (record §9, OD-1, 2026-10-08):
`MB7_MB8_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_STAGE`.

It reuses the pinned M-B6 operator's transport and marker helpers (`mb6_operator.Operator`,
unchanged) and adds only Package A forms. Every form is closed: no free path,
command or principal argument reaches DEV. Forms:

| Form | Effect |
| --- | --- |
| `pins <repo>` | local, read-only: clean checkout; control = `HEAD`; every pinned tool hashes to its pin |
| `genesis <repo> <authority-registry.v1.json> <registry-root.json> <witness-anchor.json> <updatedAt> <workdir>` | local, off-host: the owner candidate (derived twice) into a NEW `<workdir>/genesis` |
| `cloud <evidence-dir> <since>` | read-only GCP: the 11 JSON captures + bucket list + Admin Activity since `<since>` |
| `host <repo> <workdir> <evidence-dir> <PRE\\|POST>` | read-only DEV: identity, custody, release readiness (38 modules + the verify and ledger CLIs), installer `status` (P1B-6 / P1B-8), broker preservation, observer, W5 verifier, M-B6 verifier, W8 verifier |
| `mb7 <repo> <workdir> <evidence-dir> <sequence-authorization>` | **M-B7, read-only**: W8 before, exactly ONE `lilith-authority-verify-dev genesis-candidate 1 <updatedAt>`, byte comparison with the owner stdout, W8 and `/tmp` residue after; on PASS the `MB7_TECHNICAL_PASS` record |
| `accept-b7 <workdir> <statement>` | local: records the owner's verbatim ACT 2 (GENESIS_PREPARED acceptance + P-A / P-B record authorization), after MB7_TECHNICAL_PASS |
| `stage <workdir>` | DEV operator home only: the 0700 stage directory, the two owner-input files, re-hashed there |
| `mb8 <repo> <workdir> <go-file>` | **mutation, one attempt**: a read-only W8-0 pre-state check, the `O_EXCL` marker, then exactly ONE `install-owner-inputs` |
| `post <repo> <workdir>` | read-only DEV: the `host POST` reads and the P1B-8 proof into `<workdir>/post`; on S8-5 + all PASS, `POST_VERIFIED` (S8-6). Never continues to M-B9a |
| `classify <repo> <workdir> <evidence-dir>` | read-only DEV: the W8 verifier combined with this sequence's records into one W8 phase |
| `denial` / `ledger-denial` / `owner-denial` `<repo> <evidence-dir>` | read-only DEV: the P1B-5 (unchanged), P1B-6 (unchanged) and P1B-8 denial proofs |
| `removal-plan <repo> <workdir> <evidence-dir>` | read-only DEV: the W8 phase and the bounded removal plan with its digest |
| `removal <repo> <workdir> <plan-evidence-dir> <authorization-file>` | **mutation**: the bounded removal of exactly that plan (W8-1, W8-2 or W8-3 only; a separate owner authorization) |
| `cleanup <workdir>` | DEV operator home only: remove the two staged files and the stage directory |
| `dr5 <repo> <verified-host-phase> <deploy-log>` | local: the phase-bound DR-5 comparison (the accepted post-M-B6 baseline, unchanged by Package A) |

Three owner acts, each its own text and none implied by another: ACT 1, the
sequence authorization (the read-only M-B7 only); ACT 2, the GENESIS_PREPARED
acceptance and the authorization to record that exact candidate in P-A and
P-B (never the host install); ACT 3, the one-attempt M-B8 host-install go
(never M-B9a or later). A go file must
contain every binding line of its template with the exact values. The
`O_EXCL` marker is written BEFORE the remote install; whatever happens after
it, the attempt is consumed: no automatic retry and no second invocation path.

    tool / pin / marker / go-file check != authorization
    MB7_TECHNICAL_PASS != GENESIS_PREPARED accepted != M-B8 go;  one go = exactly one `install-owner-inputs`
    Package A POST != owner acceptance != M-B9a authorization

It never opens, loads, decrypts or copies K-ROOT, K-WIT or K-ACT, never runs
a keygen, `systemd-creds`, a unit start/stop/reload/enable, the signer or the
witness, and never runs a ledger, `bootstrap`, hold, record or First Memory form.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mb6_operator as M6  # noqa: E402  (pinned below; its helpers are reused unchanged)

Stop = M6.Stop
_need = M6._need
sha256_hex = M6.sha256_hex

DEV = M6.DEV
RELEASE_SHA = M6.RELEASE_SHA
RELEASE_PYTHON = M6.RELEASE_PYTHON
SYSTEM_PYTHON = M6.SYSTEM_PYTHON
OPERATOR_HOME = "/home/ravindupahasara2_gmail_com"
STAGE_DIR = OPERATOR_HOME + "/lilith-mb8-stage"
VERIFY_CLI = "/usr/local/sbin/lilith-authority-verify-dev"
# Release member `cli/lilith-authority-verify-dev` of aee323e (= services/authority-dev/bin/, unchanged at control).
VERIFY_CLI_SHA256 = "bc331636eedbbae22a53667aa230ba0672fb1e22b8a5bd4975ac9f8557a400a4"
LEDGER_HEAD = "19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630"   # owner-accepted (M-B6)
REGISTRY_DIGEST = M6.REGISTRY_DIGEST
CONTINUITY = "MB7_MB8_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_STAGE"
# OD-3: the owner record directories (B-4 dedicated pin directories; the record names them, the operator writes neither).
P_A_DIR = "/root/lilith-genesis-pin-dev-synthetic"
P_B_DIR = "$HOME/lilith-genesis-pin-dev-synthetic"
ATTEMPT_DIR = M6.ATTEMPT_DIR
MB8_ATTEMPT = "mb8"
TMP_RESIDUE = "sudo -n /usr/bin/find /tmp -maxdepth 1 -name 'lilith-ledger-observe.*' -printf '%f\\n'"

INSTALLER = M6.INSTALLER
W5_VERIFIER = M6.W5_VERIFIER
MB6_VERIFIER = M6.VERIFIER
OBSERVER = M6.OBSERVER
BROKER = M6.BROKER
DENIAL = M6.DENIAL
LEDGER_DENIAL = M6.LEDGER_DENIAL
DR5_TARGET = M6.DR5_TARGET
MB6_OPERATOR = "services/owner-memory-control/tools/mb6_operator.py"
OWNER_DEV = "services/authority-dev/ceremony/lilith_authority_owner_dev.py"
CANDIDATE = "services/owner-memory-control/tools/mb7_genesis_candidate.py"
VERIFIER = "services/owner-memory-control/tools/mb8_owner_input_verifier.py"
REMOVAL = "services/owner-memory-control/tools/mb8_owner_input_removal.py"
OWNER_DENIAL = "services/owner-memory-control/tools/mb8_owner_input_denial_proof.py"
OPERATOR = "services/owner-memory-control/tools/mb7_mb8_operator.py"

TOOL_PINS = {
    **{path: M6.TOOL_PINS[path] for path in (INSTALLER, W5_VERIFIER, MB6_VERIFIER, OBSERVER, BROKER, DENIAL,
                                             LEDGER_DENIAL, DR5_TARGET)},
    MB6_OPERATOR: "4a91d98421e38326858e141152180c127f5a67306eebe51a8ca8762f0504dcc5",
    OWNER_DEV: "49b82760dae20201172548d8d4802a3dc5436c58a1339982fc274b1a69b21c99",
    CANDIDATE: "d50fcb36afab51a79c7918a7a43c86f97338241f62144c780d8b342c68b3c8b2",
    VERIFIER: "b190c255c88a1bdca0ff8d9cb050443ad24d42f269d49947d47b87775351e341",
    REMOVAL: "d9a6e0d5dcfb07558ca7533e8144b7f2b7c29b1b4db28400571aede55b99f7f5",
    OWNER_DENIAL: "5d63137a2c6e43f12f663febdd4e22fd7b2b519a6c0cfa544dad12f0bc958517",
}
VERIFIER_BUNDLE = (W5_VERIFIER, MB6_VERIFIER, VERIFIER)
MB6_VERIFIER_BUNDLE = M6.VERIFIER_BUNDLE

INSTALLER_STAGE = {"PRE": "P1B-6", "POST": "P1B-8"}
W5_PHASE = {"PRE": "OUT_OF_SCOPE_POST_LEDGER", "POST": "OUT_OF_SCOPE_POST_LEDGER"}
MB6_PHASE = {"PRE": "LEDGER_COMMITTED_EXACT", "POST": "OUT_OF_SCOPE_LATER_STATE"}
W8_PHASE = {"PRE": "W8_0_NO_OWNER_INPUTS", "POST": "OWNER_INPUTS_INSTALLED_EXACT"}
PARTIAL_PHASES = ("W8_1_PIN_PARTIAL", "W8_2_PIN_ONLY_EXACT", "W8_3_PIN_EXACT_REGISTER_PARTIAL")
DR5_PHASES = ("W8_0_NO_OWNER_INPUTS", "OWNER_INPUTS_INSTALLED_EXACT")

READINESS_PROBE = M6.READINESS_PROBE.replace(
    "'deserialize':", f"'verifyCli':hashlib.sha256(open('{VERIFY_CLI}','rb').read()).hexdigest(),'deserialize':", 1)

# ------------------------------------------------------------ owner texts ---
# Record §10 (sequence authorization), §11 (GENESIS_PREPARED acceptance), §12 (the M-B8 go), §6.3 (removal).
SEQUENCE_LINES = (
    "I authorize the Package A (M-B7 + M-B8) live sequence now, for this current DEV_SYNTHETIC sequence only.",
    "Continuity: " + CONTINUITY + ".",
    "The deploy freeze holds from the start of this sequence through the Package A close.",
    "Control commit: {control}.",
    "Operator: " + OPERATOR + " SHA-256 {operator}.",
    "Owner candidate tool: " + CANDIDATE + " SHA-256 " + TOOL_PINS[CANDIDATE] + ".",
    "W8 verifier: " + VERIFIER + " SHA-256 " + TOOL_PINS[VERIFIER] + ".",
    f"M-B7 command: {VERIFY_CLI} genesis-candidate 1 {{updated_at}}, read-only, exactly one invocation per M-B7 run.",
    "MB7_MB8_UPDATED_AT: {updated_at}, captured once by the owner at the opening of this sequence; immutable for "
    "this bootstrap lineage.",
    "Owner candidate digest: {candidate}.",
    "This authorizes the read-only M-B7 only. It does not accept GENESIS_PREPARED and does not authorize M-B8, "
    "M-B9a, M-B9b, witness genesis, record 1, First Memory or PROD.",
)
GENESIS_PREPARED_LINES = (
    "I accept GENESIS_PREPARED for exactly this candidate in this Package A sequence.",
    "Candidate digest: {candidate}. MB7_MB8_UPDATED_AT: {updated_at}.",
    "M-B7 host stdout SHA-256: {stdout} equals the owner-computed expected stdout.",
    "The S25 reproduce result equals this candidate digest.",
    "I authorize recording exactly this candidate, create-only, in P-A " + P_A_DIR + " (laptop WSL) and P-B "
    + P_B_DIR + " (S25 Termux): genesis-pin.json SHA-256 {pin}, authorization-register.json SHA-256 {register}, "
    "pin-record.json SHA-256 {record}.",
    "This act does not authorize the M-B8 host install; that needs its own go.",
)
MB8_GO_LINES = (
    "I authorize M-B8 / PIN_GENESIS on-host install now for exactly one attempt within this current Package A "
    "sequence.",
    "Continuity: " + CONTINUITY + ".",
    "Control commit: {control}.",
    "Operator: " + OPERATOR + " SHA-256 {operator}.",
    "Installer: " + INSTALLER + " SHA-256 " + TOOL_PINS[INSTALLER] + ".",
    "W8 verifier: " + VERIFIER + " SHA-256 " + TOOL_PINS[VERIFIER] + ".",
    "Removal: " + REMOVAL + " SHA-256 " + TOOL_PINS[REMOVAL] + ".",
    "Owner-input denial proof: " + OWNER_DENIAL + " SHA-256 " + TOOL_PINS[OWNER_DENIAL] + ".",
    f"Release: {RELEASE_SHA}.",
    f"Command: install-owner-inputs {RELEASE_SHA} {STAGE_DIR}/genesis-pin.json {STAGE_DIR}/authorization-register.json, "
    "exactly one invocation.",
    "Pre-state: W8_0_NO_OWNER_INPUTS.",
    "Candidate digest: {candidate}.",
    "Genesis-pin copy SHA-256: {pin}. Authorization-register copy SHA-256: {register}.",
    "MB7_MB8_UPDATED_AT: {updated_at}. Pin-record SHA-256: {record}.",
    "The owner records P-A " + P_A_DIR + " (laptop) and P-B " + P_B_DIR + " (S25) each hold exactly these three "
    "files, byte-identical and separately hash-verified.",
    "GENESIS_PREPARED was owner-accepted in this sequence.",
    "OWNER_REGISTER = KNOWN_EMPTY was freshly established in this sequence from Replica A and Replica B.",
    "This go does not accept GENESIS_PINNED, and does not authorize M-B9a, M-B9b, witness genesis, record 1, First "
    "Memory or PROD.",
    "Any REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output, or other STOP after the attempt marker "
    "consumes this go and ends the sequence. There is no automatic retry.",
    "A partial state enters only the reviewed W8 classifier and the separately authorized removal or adoption path.",
)
REMOVAL_LINES = (
    "I authorize the bounded M-B8 owner-input removal for exactly one invocation.",
    "Plan digest: {plan}.",
    "Classified W8 phase: {phase}.",
    "I acknowledge: this removal is not a retry of M-B8 and is not a new pin; the owner pin copies P-A and P-B and "
    "the candidate are unchanged; a new M-B8 attempt needs a new owner go and a fresh re-proof.",
)
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def load_tool(repo: Path, path: str, name: str):
    """Hash-gated, registered in `sys.modules` before execution (the M-B6 loader with this package's pins)."""
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


class Operator(M6.Operator):
    """Transport, marker and go-check helpers are the pinned M-B6 ones; every pin lookup is this package's."""

    def tool_bytes(self, repo: Path, path: str) -> bytes:
        data = self._git(repo, "show", f"HEAD:{path}")
        _need(sha256_hex(data) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return data

    def streamed(self, repo: Path, path: str, interpreter: str, args: str) -> str:
        import base64
        import gzip

        blob = base64.b64encode(gzip.compress(self.tool_bytes(repo, path), mtime=0)).decode("ascii")
        return (f"B={blob}; printf %s \"$B\" | base64 -d | gunzip | sha256sum | cut -c1-64 | grep -qx "
                f"'{TOOL_PINS[path]}' || exit 96; printf %s \"$B\" | base64 -d | gunzip | sudo -n {interpreter} "
                f"-I -B - {args}")

    def bundled(self, repo: Path, paths: Sequence[str], args: str) -> str:
        import base64
        import gzip

        sources = {Path(path).stem: self.tool_bytes(repo, path).decode("utf-8") for path in paths}
        blob = base64.b64encode(gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0)).decode("ascii")
        pins = ",".join(f"{Path(path).stem}={TOOL_PINS[path]}" for path in paths)
        boot = base64.b64encode(M6.BOOT.encode("ascii")).decode("ascii")
        loader = f"import base64;exec(base64.b64decode('{boot}'))"
        return (f"B={blob}; printf %s \"$B\" | base64 -d | sudo -n {RELEASE_PYTHON} -I -B -c \"{loader}\" "
                f"{pins} {Path(paths[-1]).stem} {args}")

    # ---------------------------------------------------------------- helpers ---

    @staticmethod
    def candidate(workdir: Path) -> dict:
        """The emitted owner candidate (`<workdir>/genesis`), re-verified against its SHA256SUMS."""
        tool = sys.modules.get("mb7_genesis_candidate_operator")
        if tool is None:
            tool = load_tool(Path(__file__).resolve().parents[3], CANDIDATE, "mb7_genesis_candidate_operator")
        files = tool.load_emitted(Path(workdir) / "genesis")
        value = json.loads(files["candidate.json"].decode("ascii"))
        _need(_HEX64.fullmatch(str(value.get("candidateDigest"))) is not None
              and value.get("ledgerHead") == LEDGER_HEAD, "CANDIDATE_INVALID")
        return {"candidate": value["candidateDigest"], "updated_at": value["updatedAt"],
                "pin": sha256_hex(files["genesis-pin.json"]), "register": sha256_hex(files["authorization-register.json"]),
                "record": sha256_hex(files["pin-record.json"]),
                "stdout": sha256_hex(files["expected-host-stdout.txt"]), "files": files}

    def _w8_args(self, workdir: Path) -> str:
        c = self.candidate(workdir)
        return f"{LEDGER_HEAD} {c['candidate']} {c['updated_at']}"

    def _w8(self, repo: Path, args: str) -> tuple[int, dict | None, "subprocess.CompletedProcess[bytes]"]:
        result = self.ssh(self.bundled(repo, VERIFIER_BUNDLE, args))
        try:
            report = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            report = None
        return result.returncode, report, result

    def _operator_at_control(self, repo: Path) -> str:
        operator = sha256_hex(self._git(repo, "show", f"HEAD:{OPERATOR}"))
        _need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")
        _need(sha256_hex(Path(M6.__file__).read_bytes()) == TOOL_PINS[MB6_OPERATOR], "TOOL_PIN_MISMATCH:" + MB6_OPERATOR)
        return operator

    @staticmethod
    def _record(path: Path, value: dict) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, json.dumps(value, sort_keys=True).encode("ascii") + b"\n")
            os.fsync(fd)
        finally:
            os.close(fd)

    # ------------------------------------------------------------ local forms ---

    def pins(self, repo: Path) -> dict:
        status = self._git(repo, "status", "--porcelain", "--untracked-files=no")
        _need(status.strip() == b"", "CONTROL_CHECKOUT_NOT_CLEAN")
        control = self.control(repo)
        for path in TOOL_PINS:
            self.tool_bytes(repo, path)
        return {"control": control, "tools": dict(TOOL_PINS), "result": "MB7_MB8_TOOL_PINS_EXACT"}

    def genesis(self, repo: Path, registry: Path, root_anchor: Path, witness_anchor: Path, updated_at: str,
                workdir: Path, tool=None) -> dict:
        """Owner workstation: the candidate from the owner's own accepted installables (needs the pinned wheels)."""
        tool = tool or load_tool(Path(repo), CANDIDATE, "mb7_genesis_candidate_operator")
        out = tool.emit(Path(registry).read_bytes(), Path(root_anchor).read_bytes(), Path(witness_anchor).read_bytes(),
                        updated_at, Path(workdir) / "genesis")
        return dict(out, next="sequence authorization (record §10) binding this digest and updatedAt")

    def accept_b7(self, workdir: Path, statement: Path) -> dict:
        directory = Path(workdir) / "mb7"
        _need((directory / "MB7_TECHNICAL_PASS.json").is_file(), "MB7_TECHNICAL_PASS_ABSENT")
        c = self.candidate(workdir)
        raw = Path(statement).read_bytes()
        self.check_go(raw.decode("utf-8"), GENESIS_PREPARED_LINES, candidate=c["candidate"],
                      updated_at=c["updated_at"], stdout=c["stdout"], pin=c["pin"], register=c["register"],
                      record=c["record"])
        try:
            self._record(directory / "GENESIS_PREPARED_ACCEPTED.json", {
                "candidateDigest": c["candidate"], "updatedAt": c["updated_at"], "statementSha256": sha256_hex(raw)})
        except FileExistsError as exc:
            raise Stop("GENESIS_PREPARED_ALREADY_RECORDED") from exc
        return {"candidateDigest": c["candidate"], "result": "GENESIS_PREPARED_OWNER_ACCEPTANCE_RECORDED",
                "next": "P-A (`record-p-a`) and P-B records, fresh KNOWN_EMPTY, then the separate ACT 3 go; "
                        "the M-B8 host install is not authorized by this"}

    # --------------------------------------------------------- read-only remote ---

    def _host_reads(self, repo: Path, out: Path, phase: str, workdir: Path) -> dict[str, int]:
        identity = ("date -u +%FT%TZ; hostname; cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id; "
                    "uname -r; [ -e /var/run/reboot-required ] && echo REBOOT_REQUIRED=present "
                    "|| echo REBOOT_REQUIRED=absent")
        custody = (
            "sudo -n /usr/bin/ls -A1 /etc/credstore.encrypted; "
            "sudo -n /usr/bin/stat -c '%n %U:%G %a %s %d %i %Y %Z' "
            "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred; "
            "sudo -n /usr/bin/sha256sum /etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred; "
            "sudo -n /usr/bin/ls -A1 /etc/lilith-recovery-witness/credentials; "
            "sudo -n /usr/bin/stat -c '%n %U:%G %a %s %d %i %Y %Z' "
            "/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred; "
            "sudo -n /usr/bin/sha256sum /etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred; "
            f"sudo -n /usr/bin/sha256sum {M6.KACT_PUBLICATION}; "
            "systemctl show -p Id,ActiveState,UnitFileState,MainPID,NRestarts,InvocationID lilith-memory-broker.service "
            "lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service "
            "lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket --no-pager; "
            "sudo -n /usr/local/sbin/lilith-activation-verify; echo activation_rc=$?; "
            "sudo -n /usr/bin/ls -A1 /etc/lilith-authority-dev/trust /etc/lilith-authority-dev/registry "
            "/etc/lilith-authority-dev/owner /var/lib/lilith-authority-custody/holds; "
            "sudo -n /usr/bin/stat -c '%n %U:%G %a %s %h' /etc/lilith-authority-dev/owner "
            "/etc/lilith-authority-dev/owner/genesis-pin.json /etc/lilith-authority-dev/owner/authorization-register.json; "
            "sudo -n /usr/bin/sha256sum /etc/lilith-authority-dev/owner/genesis-pin.json "
            "/etc/lilith-authority-dev/owner/authorization-register.json; "
            "for p in /var/lib/lilith-authority-dev /var/lib/lilith-recovery-witness; do "
            "if sudo -n test -e $p; then echo \"STATE $p PRESENT\"; else echo \"STATE $p ABSENT\"; fi; done; "
            + TMP_RESIDUE + "; echo TMP_RESIDUE_END")
        readiness = (f"readlink /opt/lilith-authority-dev/current; sudo -n test -x {RELEASE_PYTHON} "
                     f"&& echo RELEASE_PYTHON=executable; sudo -n {RELEASE_PYTHON} -I -B -c \"{READINESS_PROBE}\"")
        return {
            "identity": self._save(out, "identity", self.ssh(identity)),
            # the custody chain ends with `echo`: a missing copy (before M-B8) is recorded on stderr, not as a code
            "custody": self._save(out, "custody", self.ssh(custody)),
            "readiness": self._save(out, "readiness", self.ssh(readiness)),
            "status": self._save(out, "status", self.ssh(self.streamed(
                repo, INSTALLER, SYSTEM_PYTHON, f"status --expect {INSTALLER_STAGE[phase]} {RELEASE_SHA}"))),
            "preservation": self._save(out, "preservation", self.ssh(self.streamed(
                repo, BROKER, SYSTEM_PYTHON, "preservation"))),
            "observer": self._save(out, "observer", self.ssh(self.streamed(repo, OBSERVER, SYSTEM_PYTHON, "observe"))),
            "w5verifier": self._save(out, "w5verifier", self.ssh(self.streamed(
                repo, W5_VERIFIER, RELEASE_PYTHON, f"expect {W5_PHASE[phase]}"))),
            "mb6verifier": self._save(out, "mb6verifier", self.ssh(self.bundled(
                repo, MB6_VERIFIER_BUNDLE, f"expect {MB6_PHASE[phase]} {LEDGER_HEAD}"))),
            "w8verifier": self._save(out, "w8verifier", self.ssh(self.bundled(
                repo, VERIFIER_BUNDLE, f"expect {W8_PHASE[phase]} {self._w8_args(workdir)}"))),
        }

    def host(self, repo: Path, workdir: Path, evidence: Path, phase: str) -> dict:
        _need(phase in INSTALLER_STAGE, "PHASE_INVALID")
        self.candidate(workdir)
        out = self._new_dir(Path(evidence))
        codes = self._host_reads(repo, out, phase, workdir)
        readiness_ok = codes["readiness"] == 0 and self.readiness_ok((out / "readiness.out").read_bytes())
        residue = self.tmp_residue((out / "custody.out").read_bytes())
        result = "MB7_MB8_HOST_" + phase + ("_PASS" if all(c == 0 for c in codes.values()) and readiness_ok
                                            and residue == [] else "_NOT_PASS")
        return {"codes": codes, "readinessExact": readiness_ok, "tmpResidue": residue, "result": result,
                "note": "PASS requires every code 0 and the owner's comparison of the recorded facts"}

    @staticmethod
    def tmp_residue(raw: bytes) -> list[str] | None:
        text = raw.decode("utf-8", "replace")
        if "TMP_RESIDUE_END" not in text:
            return None
        lines = text.split("TMP_RESIDUE_END", 1)[0].splitlines()
        return [line for line in lines if line.startswith("lilith-ledger-observe.")]

    @staticmethod
    def readiness_ok(raw: bytes) -> bool:
        lines = raw.decode("utf-8", "replace").splitlines()
        if len(lines) != 3 or lines[0] != f"releases/{RELEASE_SHA}" or lines[1] != "RELEASE_PYTHON=executable":
            return False
        try:
            probe = json.loads(lines[2])
        except ValueError:
            return False
        modules = {file: digest for file, digest in probe.get("modules", {}).values()}
        return (modules == {**M6.RELEASE_MODULES, **M6.PROVISION_MODULES} and probe.get("ledgerCli") == M6.LEDGER_CLI_SHA256
                and probe.get("verifyCli") == VERIFY_CLI_SHA256
                and probe.get("release") == "/opt/lilith-authority-dev/current" and probe.get("deserialize") is True)

    def _proof(self, repo: Path, evidence: Path, path: str, phase: str, name: str) -> dict:
        out = self._new_dir(Path(evidence))
        code = self._save(out, name, self.ssh(self.streamed(repo, path, SYSTEM_PYTHON, phase)))
        return {"code": code, "transcriptSha256": sha256_hex((out / f"{name}.out").read_bytes()),
                "result": f"{name.upper().replace('-', '_')}_{phase.replace('-', '')}_" + (
                    "PASS" if code == 0 else "NOT_PASS")}

    def denial(self, repo: Path, evidence: Path) -> dict:
        return self._proof(repo, evidence, DENIAL, "P1B-5", "denial")

    def ledger_denial(self, repo: Path, evidence: Path) -> dict:
        return self._proof(repo, evidence, LEDGER_DENIAL, "P1B-6", "ledger-denial")

    def owner_denial(self, repo: Path, evidence: Path) -> dict:
        return self._proof(repo, evidence, OWNER_DENIAL, "P1B-8", "owner-denial")

    # ------------------------------------------------------------------ M-B7 ---

    def mb7(self, repo: Path, workdir: Path, evidence: Path, authorization: Path) -> dict:
        """Read-only. One `genesis-candidate` per run; a run that is not PASS records nothing and may be repeated
        into a NEW evidence directory under the same sequence authorization (SAFE_RETRY; nothing was written)."""
        control = self.pins(repo)["control"]
        operator = self._operator_at_control(repo)
        c = self.candidate(workdir)
        raw = Path(authorization).read_bytes()
        self.check_go(raw.decode("utf-8"), SEQUENCE_LINES, control=control, operator=operator,
                      candidate=c["candidate"], updated_at=c["updated_at"])
        directory = Path(workdir) / "mb7"
        _need(not (directory / "MB7_TECHNICAL_PASS.json").exists(), "MB7_ALREADY_PASSED")
        out = self._new_dir(Path(evidence))
        args = self._w8_args(workdir)
        before = self._save(out, "w8-before", self.ssh(self.bundled(repo, VERIFIER_BUNDLE,
                                                                     f"expect W8_0_NO_OWNER_INPUTS {args}")))
        _need(before == 0, "MB7_PRE_STATE_NOT_W8_0")
        result = self.ssh(f"sudo -n {VERIFY_CLI} genesis-candidate 1 {c['updated_at']}")     # the ONE M-B7 command
        self._save(out, "mb7-genesis-candidate", result)
        after_code, report, after = self._w8(repo, f"expect W8_0_NO_OWNER_INPUTS {args}")
        self._save(out, "w8-after", after)
        residue = self.ssh(TMP_RESIDUE + "; echo TMP_RESIDUE_END")
        self._save(out, "tmp-residue", residue)
        leftover = self.tmp_residue(residue.stdout or b"")
        stdout = result.stdout or b""
        equal = stdout == c["files"]["expected-host-stdout.txt"]
        passed = (result.returncode == 0 and (result.stderr or b"") == b"" and equal and after_code == 0
                  and isinstance(report, dict) and report.get("evidence", {}).get("hostCandidateDigestEqualsOwnerDigest")
                  is True and leftover == [])
        summary = {"control": control, "candidateDigest": c["candidate"], "updatedAt": c["updated_at"],
                   "hostStdoutSha256": sha256_hex(stdout), "expectedStdoutSha256": c["stdout"], "stdoutEqual": equal,
                   "cliCode": result.returncode, "w8AfterCode": after_code, "tmpResidue": leftover,
                   "authorizationSha256": sha256_hex(raw)}
        if passed:
            directory.mkdir(mode=0o700, exist_ok=True)
            self._record(directory / "MB7_TECHNICAL_PASS.json", dict(summary, ownerAccepted=False))
        return dict(summary, result="MB7_TECHNICAL_PASS" if passed else "MB7_NOT_PASS",
                    next="HARD STOP: owner GENESIS_PREPARED decision (`accept-b7`); M-B8 is not authorized"
                    if passed else "STOP: owner review; a read-only re-run needs a NEW evidence directory")

    # ------------------------------------------------------ operator-home forms ---

    def stage(self, workdir: Path) -> dict:
        c = self.candidate(workdir)
        files = Path(workdir) / "genesis"
        created = self.ssh(f"test ! -e {STAGE_DIR} && mkdir -m 0700 {STAGE_DIR} && echo STAGE_CREATED")
        _need(created.returncode == 0 and created.stdout.strip() == b"STAGE_CREATED", "STAGE_DIRECTORY")
        copied = self.run([*self.gcloud, "compute", "scp", str(files / "genesis-pin.json"),
                           str(files / "authorization-register.json"), f"{DEV}:{STAGE_DIR}/", f"--zone={M6.ZONE}",
                           f"--project={M6.PROJECT}", "--tunnel-through-iap"])
        _need(copied.returncode == 0, "STAGE_COPY_FAILED")
        return self.staged_check(workdir, c)

    def staged_check(self, workdir: Path, c: dict | None = None) -> dict:
        c = c or self.candidate(workdir)
        check = self.ssh(
            f"cd {STAGE_DIR} && test \"$(ls -A | LC_ALL=C sort | tr '\\n' ' ')\" = "
            "'authorization-register.json genesis-pin.json ' && test -z \"$(find . -mindepth 1 ! -type f)\" && "
            f"printf '%s  %s\\n%s  %s\\n' {c['register']} authorization-register.json {c['pin']} genesis-pin.json "
            "| sha256sum -c --strict -")
        _need(check.returncode == 0, "STAGED_FILES_NOT_PINNED")
        return {"stage": STAGE_DIR, "genesisPinSha256": c["pin"], "authorizationRegisterSha256": c["register"],
                "result": "MB8_STAGED_FILES_PINNED_ON_HOST"}

    def cleanup(self, workdir: Path) -> dict:
        self.staged_check(workdir)
        done = self.ssh(f"rm -f {STAGE_DIR}/genesis-pin.json {STAGE_DIR}/authorization-register.json && "
                        f"rmdir {STAGE_DIR} && test ! -e {STAGE_DIR} && echo STAGE_DIR_ABSENT")
        _need(done.returncode == 0 and done.stdout.strip() == b"STAGE_DIR_ABSENT", "CLEANUP_FAILED")
        return {"result": "MB8_STAGE_CLEANED"}

    # ------------------------------------------------------------------ M-B8 ---

    def mb8(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        control = self.pins(repo)["control"]
        operator = self._operator_at_control(repo)
        c = self.candidate(workdir)
        _need((Path(workdir) / "mb7" / "MB7_TECHNICAL_PASS.json").is_file(), "MB7_TECHNICAL_PASS_ABSENT")
        _need((Path(workdir) / "mb7" / "GENESIS_PREPARED_ACCEPTED.json").is_file(), "GENESIS_PREPARED_NOT_ACCEPTED")
        raw = Path(go_file).read_bytes()
        self.check_go(raw.decode("utf-8"), MB8_GO_LINES, control=control, operator=operator, candidate=c["candidate"],
                      pin=c["pin"], register=c["register"], record=c["record"], updated_at=c["updated_at"])
        _need(not (Path(workdir) / ATTEMPT_DIR / f"{MB8_ATTEMPT}.json").exists(), "ATTEMPT_ALREADY_CONSUMED:mb8")
        verifier = load_tool(Path(repo), VERIFIER, "mb8_owner_input_verifier_operator")   # before any write
        self.staged_check(workdir, c)
        code, report, _ = self._w8(repo, f"expect W8_0_NO_OWNER_INPUTS {self._w8_args(workdir)}")
        _need(code == 0 and isinstance(report, dict) and report.get("phase") == "W8_0_NO_OWNER_INPUTS",
              "PRE_STATE_NOT_W8_0")
        directory = self._one_attempt(workdir, MB8_ATTEMPT, raw)
        args = (f"install-owner-inputs {RELEASE_SHA} {STAGE_DIR}/genesis-pin.json "
                f"{STAGE_DIR}/authorization-register.json")
        try:
            result = self.ssh(self.streamed(repo, INSTALLER, SYSTEM_PYTHON, args))          # the ONE mutation
        except subprocess.TimeoutExpired as exc:
            result = subprocess.CompletedProcess(exc.cmd, None, exc.output or b"", exc.stderr or b"")
        except OSError as exc:
            result = subprocess.CompletedProcess([], None, b"", f"LOCAL_{type(exc).__name__}".encode("ascii"))
        self._save(directory, "mb8-install-owner-inputs", result)
        transcript, detail = verifier.classify_transcript(result.returncode, result.stdout or b"", result.stderr or b"")
        (directory / "mb8-transcript.json").write_text(json.dumps({"class": transcript, "detail": detail},
                                                                  sort_keys=True) + "\n", encoding="ascii", newline="\n")
        return {"code": result.returncode, "attempt": "CONSUMED", "transcript": transcript, "detail": detail,
                "next": "M-B8 POST (`post`), then HARD STOP for owner review; never M-B9a",
                "result": "MB8_INVOKED_ONCE" if transcript == verifier.INSTALL_PASS else "MB8_STOP"}

    # ------------------------------------------------------- classification ---

    def _records(self, workdir: Path) -> tuple[bool, str, bool]:
        directory = Path(workdir) / ATTEMPT_DIR
        consumed = (directory / f"{MB8_ATTEMPT}.json").is_file()
        transcript = "NOT_INVOKED"
        if (directory / "mb8-transcript.json").is_file():
            transcript = json.loads((directory / "mb8-transcript.json").read_text(encoding="ascii"))["class"]
        elif consumed:
            transcript = "FAILED_UNCLASSIFIED"     # marker without a recorded transcript: the laptop died
        return consumed, transcript, (Path(workdir) / "post" / "POST_VERIFIED.json").is_file()

    def classify(self, repo: Path, workdir: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code, report, result = self._w8(repo, f"observe {self._w8_args(workdir)}")
        self._save(out, "w8verifier", result)
        _need(code == 0 and isinstance(report, dict), "VERIFIER_FAILED")
        verifier = load_tool(Path(repo), VERIFIER, "mb8_owner_input_verifier_operator")
        consumed, transcript, post = self._records(workdir)
        phase = verifier.classify_sequence(host_phase=report["phase"], attempt_consumed=consumed,
                                           transcript=transcript, post_verified=post)
        route = verifier.ROUTING.get(phase, verifier.ROUTING[verifier.UNCLASSIFIED])
        return {"hostPhase": report["phase"], "sequencePhase": phase, "routing": route[0], "action": route[1],
                "attemptConsumed": consumed, "transcript": transcript, "postVerified": post, "result": "MB8_CLASSIFIED"}

    def post(self, repo: Path, workdir: Path) -> dict:
        consumed, transcript, post = self._records(workdir)
        _need(consumed, "MB8_NOT_IN_THIS_SEQUENCE")
        _need(not post, "POST_ALREADY_VERIFIED")
        out = self._new_dir(Path(workdir) / "post")
        codes = self._host_reads(repo, out, "POST", workdir)
        codes["owner-denial"] = self._save(out, "owner-denial", self.ssh(self.streamed(repo, OWNER_DENIAL,
                                                                                        SYSTEM_PYTHON, "P1B-8")))
        readiness_ok = codes["readiness"] == 0 and self.readiness_ok((out / "readiness.out").read_bytes())
        residue = self.tmp_residue((out / "custody.out").read_bytes())
        try:
            report = json.loads((out / "w8verifier.out").read_bytes().decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            report = {"phase": "UNCLASSIFIED_STOP", "evidence": {}}
        verifier = load_tool(Path(repo), VERIFIER, "mb8_owner_input_verifier_operator")
        phase = verifier.classify_sequence(host_phase=report.get("phase", "UNCLASSIFIED_STOP"), attempt_consumed=True,
                                           transcript=transcript, post_verified=False)
        evidence = report.get("evidence", {})
        verified = (phase == verifier.S8_5 and all(c == 0 for c in codes.values()) and readiness_ok and residue == []
                    and all(evidence.get(name) is True for name in verifier.EVIDENCE)
                    and report.get("registryEffective") is False and report.get("authorityGranted") is False)
        if verified:
            c = self.candidate(workdir)
            self._record(out / "POST_VERIFIED.json", {
                "candidateDigest": c["candidate"], "genesisPinSha256": c["pin"],
                "authorizationRegisterSha256": c["register"], "evidence": evidence, "phase": verifier.S8_6,
                "ownerDenialSha256": sha256_hex((out / "owner-denial.out").read_bytes()), "ownerAccepted": False})
        return {"codes": codes, "readinessExact": readiness_ok, "sequencePhase": verifier.S8_6 if verified else phase,
                "evidence": evidence, "result": "MB8_POST_VERIFIED" if verified else "MB8_POST_NOT_VERIFIED",
                "next": "HARD STOP: owner acceptance of Package A (separate); M-B9a is not authorized"
                if verified else "STOP: `classify`, then owner review; removal only under a separate authorization"}

    # --------------------------------------------------------------- removal ---

    def removal_plan(self, repo: Path, workdir: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code, report, result = self._w8(repo, f"observe {self._w8_args(workdir)}")
        self._save(out, "w8verifier", result)
        plan = self.ssh(self.streamed(repo, REMOVAL, SYSTEM_PYTHON, "plan"))
        plan_code = self._save(out, "removal-plan", plan)
        phase = report.get("phase") if isinstance(report, dict) else None
        return {"code": plan_code, "w8Phase": phase, "removable": phase in PARTIAL_PHASES and plan_code == 0,
                "result": "MB8_REMOVAL_PLAN_RECORDED" if plan_code == 0 else "MB8_REMOVAL_PLAN_REFUSED",
                "authorityGranted": False}

    def removal(self, repo: Path, workdir: Path, plan_evidence: Path, authorization: Path) -> dict:
        self.pins(repo)
        observed = json.loads((Path(plan_evidence) / "w8verifier.out").read_text(encoding="utf-8"))
        plan = json.loads((Path(plan_evidence) / "removal-plan.out").read_text(encoding="utf-8"))
        digest, phase = plan.get("planDigest"), observed.get("phase")
        _need(isinstance(digest, str) and _HEX64.fullmatch(digest) is not None and plan.get("remove"),
              "PLAN_NOT_ACTIONABLE")
        _need(phase in PARTIAL_PHASES, "PHASE_NOT_REMOVABLE")
        raw = Path(authorization).read_bytes()
        self.check_go(raw.decode("utf-8"), REMOVAL_LINES, plan=digest, phase=phase)
        directory = self._one_attempt(workdir, "removal-" + digest[:16], raw)
        code = self._save(directory, "removal", self.ssh(self.streamed(repo, REMOVAL, SYSTEM_PYTHON,
                                                                        f"remove {digest}")))
        return {"code": code, "result": "MB8_REMOVAL_INVOKED_ONCE" if code == 0 else "MB8_REMOVAL_STOP",
                "next": "installer status --expect P1B-6 and W8 expect W8_0_NO_OWNER_INPUTS; a new M-B8 attempt needs "
                        "a new owner go and a fresh re-proof"}

    # ------------------------------------------------------------------- DR-5 ---

    def dr5(self, repo: Path, phase: str, log: Path) -> dict:
        """Package A changes no DR-5-observable object: the accepted post-M-B6 baseline stays the target, for an
        independently verified W8-0 or OWNER_INPUTS_INSTALLED_EXACT host only (record §7)."""
        target = load_tool(Path(repo), DR5_TARGET, "mb6_dr5_target_mb7_mb8")
        _need(phase in DR5_PHASES, "NO_BASELINE_STOP:" + phase)
        sets = target.extract(Path(log).read_bytes().decode("utf-8", "replace"))
        observed = {name: (len(lines), target.digest(lines)) for name, lines in sets.items()}
        unequal = [name for name in target.SETS if observed[name] != target.POST[name]]
        kinds = target.counts(sets["result-set"])
        return {"phase": phase, "target": "POST_MB6_ACCEPTED_BASELINE_UNCHANGED_BY_PACKAGE_A",
                "observed": {name: {"lines": n, "sha256": h} for name, (n, h) in observed.items()},
                "allowed": kinds["ALLOWED"], "fail": kinds["FAIL"], "unequal": unequal,
                "result": "EQUAL" if not unequal and kinds["ALLOWED"] == 0 else "DRIFT", "accepted": False}


USAGE = __doc__.split("| Form |", 1)[1].split("\n\n", 1)[0]


def main(argv: list[str], operator: Operator | None = None) -> int:
    operator = operator or Operator()
    forms: dict[tuple[str, int], Callable[..., dict]] = {
        ("pins", 1): lambda a: operator.pins(Path(a[0])),
        ("genesis", 6): lambda a: operator.genesis(Path(a[0]), Path(a[1]), Path(a[2]), Path(a[3]), a[4], Path(a[5])),
        ("cloud", 2): lambda a: operator.cloud(Path(a[0]), a[1]),
        ("host", 4): lambda a: operator.host(Path(a[0]), Path(a[1]), Path(a[2]), a[3]),
        ("mb7", 4): lambda a: operator.mb7(Path(a[0]), Path(a[1]), Path(a[2]), Path(a[3])),
        ("accept-b7", 2): lambda a: operator.accept_b7(Path(a[0]), Path(a[1])),
        ("stage", 1): lambda a: operator.stage(Path(a[0])),
        ("mb8", 3): lambda a: operator.mb8(Path(a[0]), Path(a[1]), Path(a[2])),
        ("post", 2): lambda a: operator.post(Path(a[0]), Path(a[1])),
        ("classify", 3): lambda a: operator.classify(Path(a[0]), Path(a[1]), Path(a[2])),
        ("denial", 2): lambda a: operator.denial(Path(a[0]), Path(a[1])),
        ("ledger-denial", 2): lambda a: operator.ledger_denial(Path(a[0]), Path(a[1])),
        ("owner-denial", 2): lambda a: operator.owner_denial(Path(a[0]), Path(a[1])),
        ("removal-plan", 3): lambda a: operator.removal_plan(Path(a[0]), Path(a[1]), Path(a[2])),
        ("removal", 4): lambda a: operator.removal(Path(a[0]), Path(a[1]), Path(a[2]), Path(a[3])),
        ("cleanup", 1): lambda a: operator.cleanup(Path(a[0])),
        ("dr5", 3): lambda a: operator.dr5(Path(a[0]), a[1], Path(a[2])),
    }
    form = forms.get((argv[0], len(argv) - 1)) if argv else None
    if form is None:
        print("mb7_mb8_operator: USAGE" + USAGE, file=sys.stderr)
        return 2
    try:
        result = form(argv[1:])
    except Stop as stop:
        print(f"mb7_mb8_operator: STOP {stop.code}", file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
