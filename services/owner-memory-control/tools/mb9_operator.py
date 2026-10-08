#!/usr/bin/env python3
"""15B2b-B1b-3e Package B (M-B9a START_WITNESS + M-B9b COMMIT_WITNESS_GENESIS): the reviewed owner-laptop operator.

Record: docs/architecture/slice-15b2b-b1b3e-mb9-witness-genesis-package.md.
SOURCE PREPARED / NOT AUTHORIZED: no form below is authorized by this repository; each live use needs its own
explicit owner authorization. The templates bind the owner-ACCEPTED continuity (record §9, OD-B1, 2026-10-08):
`PACKAGE_B_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_AUTHORITY_BOUNDARIES`.

It reuses the pinned M-B6 operator's transport and marker helpers (`mb6_operator.Operator`, unchanged) and the
pinned Package A owner candidate tool, and adds only Package B forms. Every form is closed: no free path,
command or principal argument reaches DEV.

| Form | Effect |
| --- | --- |
| `pins <repo>` | local, read-only: clean checkout; control = `HEAD`; every pinned tool hashes to its pin |
| `cloud <evidence-dir> <since>` | read-only GCP: the 11 JSON captures + bucket list + Admin Activity since `<since>` |
| `open-sequence <repo> <workdir> <statement>` | local: records the owner's verbatim B1 (sequence opening + freeze; read-only only) |
| `stop-sequence <repo> <workdir> <statement>` | local: records the owner's verbatim pre-M-B9a stop (record §10.8); refused once any attempt marker exists |
| `host <repo> <workdir> <evidence-dir> <PRE\\|POST9A\\|POST9B>` | read-only DEV: identity, custody (+ witness state facts), release readiness (+ the owner witness CLI), installer `status` (P1B-8 / P1B-9a / P1B-9b), broker preservation, observer, W5, M-B6, W8 and W9 verifiers |
| `denial` / `ledger-denial` / `owner-denial` `<repo> <evidence-dir>` | read-only DEV: the P1B-5, P1B-6 and P1B-8 proofs (P1B-6 / P1B-8 only while the witness is inactive) |
| `witness-denial <repo> <evidence-dir> <P1B-9a\\|P1B-9b>` | read-only DEV: the Package B witness denial proof |
| `classify <repo> <workdir> <evidence-dir>` | read-only DEV: the W9 verifier combined with this sequence's records into one sequence phase |
| `mb9a <repo> <workdir> <go-file>` | **mutation, one B2 go, two ordered one-attempt markers**: W9-0 check; marker `mb9a-1`, ONE `witness-state`; only if exact (W9-1), marker `mb9a-2`, ONE start of the two sockets and the service; then the read-only health |
| `post9a <repo> <workdir>` | read-only DEV: `host POST9A`, the P1B-9a and P1B-5 proofs, health; on exact, `POST9A_VERIFIED` bound to InvocationID / MainPID |
| `accept-9a <workdir> <statement>` | local: records the owner's verbatim B3 (WITNESS_STARTED) for that incarnation |
| `mb9b <repo> <workdir> <go-file>` | **mutation, one B4 go, one marker**: the accepted incarnation still running; marker `mb9b`; ONE `bootstrap 1 <updatedAt>` |
| `post9b <repo> <workdir>` | read-only DEV: `host POST9B`, the P1B-9b and P1B-5 proofs, health, read, chain export; on exact, `POST9B_VERIFIED` |
| `chain-export <repo> <workdir> <evidence-dir>` | read-only DEV: the exact bytes of `chain/1.json` and `witness.json` (evidence only; OD-B10) |
| `health <repo> <workdir> <evidence-dir>` | read-only DEV: witness HEALTH, only when the W9 verifier shows the witness running |
| `dr5 <repo> <verified-w9-phase> <deploy-log>` | local: the phase-bound DR-5 comparison (`mb9_dr5_target.py`) |
| `removal-plan <repo> <workdir> <evidence-dir>` | read-only DEV: the W9 phase and the bounded pre-commit removal plan with its digest |
| `removal <repo> <workdir> <plan-evidence-dir> <authorization-file>` | **mutation**: exactly that plan (W9-1P, W9-1, W9-2S, W9-3 only; separate owner authorization) |
| `restart-plan <repo> <workdir> <evidence-dir>` | read-only DEV: a stopped witness (W9-1, W9-2S, W9-3, W9-4, W9-5S) and its restart plan digest |
| `restart <repo> <workdir> <plan-evidence-dir> <authorization-file>` | **mutation**: ONE start of the two sockets and the service for exactly that plan (separate owner authorization) |

Five owner acts, each its own text and none implied by another (record §10): B1 opens the sequence (read-only
only); B2 authorizes M-B9a (one go, two markers); B3 accepts WITNESS_STARTED (authorizes nothing); B4 authorizes
the one M-B9b `BOOTSTRAP` and acknowledges the lineage point of no return; B5 accepts Package B (ends the freeze;
authorizes nothing). Before any attempt marker exists, an owner pre-M-B9a stop (record §10.8) may instead end the
sequence: it releases that sequence's freeze, consumes its control and authorizes nothing.

Verifier bundles (W5 + M-B6, W8, W9) travel over stdin (record §8.1): the command line carries only the bundle
digest, the per-module pins and the arguments, so its length does not grow with the verifier sources. The remote
shell refuses (exit 96) unless the received bytes hash to that digest, and the unchanged M-B6 loader refuses
(exit 96) unless every module hashes to its pin. That stdin is the stdin of PuTTY `plink`, launched directly over
the existing IAP tunnel with a pinned client, key, OS Login user and host key (remediation R-B5): `gcloud compute
ssh` on Windows replaces the caller's stdin with "y\n". Only these read-only bundles use plink; every other form,
and every mutation, keeps the reviewed `gcloud compute ssh` command.

The `O_EXCL` marker is written BEFORE each remote mutation; whatever happens after it, that stage is consumed: no
automatic retry and no second invocation path.

    tool / pin / marker / go-file check != authorization
    MB9A technical PASS != WITNESS_STARTED accepted != M-B9b go;  B4 = exactly one `bootstrap`
    commit point = chain/ fsync;  after it: forward only;  committed != pin -> REBOOTSTRAP_FORBIDDEN (no second genesis)

It never opens, loads, decrypts or copies K-ROOT, K-WIT or K-ACT, never runs a keygen or `systemd-creds`, never
enables, reloads, stops or restarts a running unit, never starts the signer, and never runs a ledger, hold,
head-advance, epoch-advance, record, activation or First Memory form. The verifier never contacts a socket.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mb6_operator as M6  # noqa: E402  (pinned; its helpers are reused unchanged)
import mb7_mb8_operator as A  # noqa: E402  (pinned Package A operator; constants only)

Stop = M6.Stop
_need = M6._need
sha256_hex = M6.sha256_hex

DEV = M6.DEV
RELEASE_SHA = M6.RELEASE_SHA
RELEASE_PYTHON = M6.RELEASE_PYTHON
SYSTEM_PYTHON = M6.SYSTEM_PYTHON
LEDGER_HEAD = A.LEDGER_HEAD
REGISTRY_DIGEST = M6.REGISTRY_DIGEST
P_A_DIR, P_B_DIR = A.P_A_DIR, A.P_B_DIR
ATTEMPT_DIR = M6.ATTEMPT_DIR
TMP_RESIDUE = A.TMP_RESIDUE
CONTINUITY = "PACKAGE_B_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_AUTHORITY_BOUNDARIES"
KWIT_KEY_ID = "test-only.witness.dev-synthetic.b1b3d.1"
KWIT_PUBLIC_KEY_SHA256 = "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf"

VERIFY_CLI = A.VERIFY_CLI
OWNER_CLI = "/usr/local/sbin/lilith-recovery-witness-owner-dev"
# Release member `cli/lilith-recovery-witness-owner-dev` of aee323e (= services/authority-dev/bin/, unchanged).
OWNER_CLI_SHA256 = "9fce2e460a9c279f99b59c6e251b813375a1be404ae611d379fed5cd812f16ab"
WITNESS_STATE = "/var/lib/lilith-recovery-witness"
START_COMMAND = ("sudo -n /usr/bin/systemctl start lilith-recovery-witness-owner.socket "
                 "lilith-recovery-witness-signer.socket && sudo -n /usr/bin/systemctl start "
                 "lilith-recovery-witness.service")
HEALTH_COMMAND = f"sudo -n {OWNER_CLI} health"
READ_COMMAND = f"sudo -n {OWNER_CLI} read"

INSTALLER = M6.INSTALLER
W5_VERIFIER = M6.W5_VERIFIER
MB6_VERIFIER = M6.VERIFIER
OBSERVER = M6.OBSERVER
BROKER = M6.BROKER
DENIAL = M6.DENIAL
LEDGER_DENIAL = M6.LEDGER_DENIAL
MB6_OPERATOR = A.MB6_OPERATOR
MB7_MB8_OPERATOR = A.OPERATOR
CANDIDATE = A.CANDIDATE
MB8_VERIFIER = A.VERIFIER
OWNER_DENIAL = A.OWNER_DENIAL
VERIFIER = "services/owner-memory-control/tools/mb9_witness_verifier.py"
WITNESS_DENIAL = "services/owner-memory-control/tools/mb9_witness_denial_proof.py"
REMOVAL = "services/owner-memory-control/tools/mb9_witness_state_removal.py"
DR5_TARGET = "services/owner-memory-control/tools/mb9_dr5_target.py"
OWNER_VERIFY = "services/owner-memory-control/tools/mb9_owner_genesis_verify.py"
OPERATOR = "services/owner-memory-control/tools/mb9_operator.py"

TOOL_PINS = {
    **{path: M6.TOOL_PINS[path] for path in (INSTALLER, W5_VERIFIER, MB6_VERIFIER, OBSERVER, BROKER, DENIAL,
                                             LEDGER_DENIAL)},
    **{path: A.TOOL_PINS[path] for path in (MB6_OPERATOR, CANDIDATE, MB8_VERIFIER, OWNER_DENIAL)},
    MB7_MB8_OPERATOR: "9f13411f363dc956795ce4832d1948e7e6a9a7f7c8d1057291de852e9e2a20cd",
    VERIFIER: "e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78",
    WITNESS_DENIAL: "2720100cf56f22db7b063641ce63c22512326b794c447901d9b2551c8ab7663a",
    REMOVAL: "4e5094ebb6f1624a6f4de1769a0c2c131a6ff9b4284c6e5a4b19e40b1c383640",
    DR5_TARGET: "d176864a2f15cd9a64462c1ffc0bb46364428e97d3ec64b5fd547bb380ef1675",
    OWNER_VERIFY: "30b66fd2be9f29e820041840a75dc87f7623eff44551c025a0141790e7c89a5a",
}
VERIFIER_BUNDLE = (W5_VERIFIER, MB6_VERIFIER, MB8_VERIFIER, VERIFIER)
MB6_VERIFIER_BUNDLE = M6.VERIFIER_BUNDLE
W8_BUNDLE = A.VERIFIER_BUNDLE

INSTALLER_STAGE = {"PRE": "P1B-8", "POST9A": "P1B-9a", "POST9B": "P1B-9b"}
W5_PHASE = dict.fromkeys(INSTALLER_STAGE, "OUT_OF_SCOPE_POST_LEDGER")
MB6_PHASE = dict.fromkeys(INSTALLER_STAGE, "OUT_OF_SCOPE_LATER_STATE")
W8_PHASE = {"PRE": "OWNER_INPUTS_INSTALLED_EXACT", "POST9A": "OUT_OF_SCOPE_LATER_STATE",
            "POST9B": "OUT_OF_SCOPE_LATER_STATE"}
W9_PHASE = {"PRE": "W9_0_PRE_WITNESS", "POST9A": "W9_2_STARTED_UNINITIALIZED",
            "POST9B": "W9_5_GENESIS_COMMITTED_EXACT"}
MARKERS = ("mb9a-1", "mb9a-2", "mb9b")
REMOVABLE_PHASES = ("W9_1P_STATE_DIR_PARTIAL", "W9_1_STATE_DIR_ONLY", "W9_2S_STOPPED_UNINITIALIZED",
                    "W9_3_PRECOMMIT_DIRS")
RESTARTABLE_PHASES = ("W9_1_STATE_DIR_ONLY", "W9_2S_STOPPED_UNINITIALIZED", "W9_3_PRECOMMIT_DIRS",
                      "W9_4_COMMITTED_POINTER_PENDING", "W9_5S_GENESIS_COMMITTED_STOPPED")
RUNNING_PHASES = ("W9_2_STARTED_UNINITIALIZED", "W9_5_GENESIS_COMMITTED_EXACT")

READINESS_PROBE = A.READINESS_PROBE.replace(
    "'deserialize':", f"'witnessOwnerCli':hashlib.sha256(open('{OWNER_CLI}','rb').read()).hexdigest(),'deserialize':",
    1)

PONR_ACKNOWLEDGEMENT = ("I understand that the witness lineage becomes irreversible at the canonical chain-directory "
                        "fsync commit point and that no second witness genesis or automatic retry is authorized after "
                        "that point.")

# ------------------------------------------------------------ owner texts ---
# Record §10. `{...}` placeholders are bound at runtime; tool pins are static.
SEQUENCE_LINES = (
    "I authorize opening the Package B (M-B9a + M-B9b) live sequence now, for this current DEV_SYNTHETIC sequence "
    "only.",
    "Continuity: " + CONTINUITY + ".",
    "The Package B deployment freeze begins now and holds through M-B9a, B3, M-B9b, POST, the owner offline "
    "verification and B5; no deploy is permitted inside this sequence.",
    "E-A18 was completed and owner-recorded before this act, and the deploy of this control commit preserved the "
    "accepted W8-exact DR-5 result.",
    "Control commit: {control}.",
    "Operator: " + OPERATOR + " SHA-256 {operator}.",
    "W9 verifier: " + VERIFIER + " SHA-256 " + TOOL_PINS[VERIFIER] + ".",
    "Candidate digest: {candidate}. MB7_MB8_UPDATED_AT: {updated_at}.",
    "This authorizes opening the sequence and read-only evidence only. It does not authorize M-B9a, M-B9b, witness "
    "genesis, record 1, the signer, First Memory or PROD.",
)
MB9A_GO_LINES = (
    "I authorize M-B9a / START_WITNESS now for exactly one attempt within this current Package B sequence.",
    "Continuity: " + CONTINUITY + ".",
    "Control commit: {control}.",
    "Operator: " + OPERATOR + " SHA-256 {operator}.",
    "Installer: " + INSTALLER + " SHA-256 " + TOOL_PINS[INSTALLER] + ".",
    "W9 verifier: " + VERIFIER + " SHA-256 " + TOOL_PINS[VERIFIER] + ".",
    "Witness denial proof: " + WITNESS_DENIAL + " SHA-256 " + TOOL_PINS[WITNESS_DENIAL] + ".",
    "Removal: " + REMOVAL + " SHA-256 " + TOOL_PINS[REMOVAL] + ".",
    f"Release: {RELEASE_SHA}.",
    f"Stage 9A-1 (marker mb9a-1): install_authority_dev.py witness-state {RELEASE_SHA}, exactly one invocation.",
    "Stage 9A-2 (marker mb9a-2), only after stage 9A-1 is exact (W9_1_STATE_DIR_ONLY): systemctl start "
    "lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket, then systemctl start "
    "lilith-recovery-witness.service, exactly one invocation; no enable and no daemon-reload.",
    "Then the read-only witness health, only after the service is observed running.",
    "Pre-state: W9_0_PRE_WITNESS (OWNER_INPUTS_INSTALLED_EXACT).",
    "Candidate digest: {candidate}. Genesis-pin copy SHA-256: {pin}. Authorization-register copy SHA-256: {register}.",
    "OWNER_REGISTER = KNOWN_EMPTY was freshly established in this sequence from Replica A and Replica B.",
    "The P1B-5, P1B-6 and P1B-8 denial proofs passed in this sequence before this go.",
    "This go does not authorize BOOTSTRAP, M-B9b, witness genesis, record 1, the signer, First Memory or PROD, and "
    "does not accept WITNESS_STARTED.",
    "Any REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output, or other STOP after a stage marker "
    "consumes that stage. There is no automatic retry, and stage 9A-2 never runs unless stage 9A-1 is exact.",
    "A partial state enters only the reviewed W9 classifier and the separately authorized removal or restart path.",
)
WITNESS_STARTED_LINES = (
    "I accept WITNESS_STARTED for this Package B sequence.",
    "W9 phase: W9_2_STARTED_UNINITIALIZED. Witness service InvocationID: {invocation}. MainPID: {mainpid}.",
    "POST9A_VERIFIED evidence SHA-256: {post9a}.",
    "Witness health: publicKeySha256 " + KWIT_PUBLIC_KEY_SHA256 + ", witnessKeyId " + KWIT_KEY_ID
    + ", classification UNINITIALIZED.",
    "This acceptance authorizes nothing further. It is not M-B9b authorization; M-B9b needs its own go after a "
    "fresh closing gate.",
)
MB9B_GO_LINES = (
    "I authorize M-B9b / COMMIT_WITNESS_GENESIS now for exactly one attempt within this current Package B sequence.",
    "Continuity: " + CONTINUITY + ".",
    "Control commit: {control}.",
    "Operator: " + OPERATOR + " SHA-256 {operator}.",
    "W9 verifier: " + VERIFIER + " SHA-256 " + TOOL_PINS[VERIFIER] + ".",
    "Witness denial proof: " + WITNESS_DENIAL + " SHA-256 " + TOOL_PINS[WITNESS_DENIAL] + ".",
    "Owner genesis verifier: " + OWNER_VERIFY + " SHA-256 " + TOOL_PINS[OWNER_VERIFY] + ".",
    f"Release: {RELEASE_SHA}.",
    f"Command: {OWNER_CLI} bootstrap 1 {{updated_at}}, exactly one invocation.",
    "Pre-state: W9_2_STARTED_UNINITIALIZED. WITNESS_STARTED was owner-accepted in this sequence for InvocationID "
    "{invocation}, MainPID {mainpid} (POST9A_VERIFIED SHA-256 {post9a}), and the witness has run continuously since.",
    "Candidate digest: {candidate}. Genesis-pin copy SHA-256: {pin}. Authorization-register copy SHA-256: {register}. "
    "Pin-record SHA-256: {record}. MB7_MB8_UPDATED_AT: {updated_at}.",
    f"Expected genesis: registryVersion 1, registryDigest {REGISTRY_DIGEST}, ledgerSequence 1, ledgerHead "
    f"{LEDGER_HEAD}, witnessVersion 1, previousWitnessDigest null, consumedAuthorizationId null, witnessKeyId "
    f"{KWIT_KEY_ID}.",
    "The owner records P-A " + P_A_DIR + " (laptop) and P-B " + P_B_DIR + " (S25) each hold exactly the three Package "
    "A record files, byte-identical and separately hash-verified, re-verified in this sequence.",
    "OWNER_REGISTER = KNOWN_EMPTY was freshly established in this sequence, after WITNESS_STARTED, from Replica A and "
    "Replica B.",
    PONR_ACKNOWLEDGEMENT,
    "A committed genesis that differs from the owner pin is REBOOTSTRAP_FORBIDDEN: STOP, with no second genesis.",
    "This go does not accept WITNESS_GENESIS_COMMITTED and does not authorize record 1, the acceptance envelope, "
    "HELD, the signer, First Memory or PROD.",
    "Any REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output, or other STOP after the attempt marker "
    "consumes this go. There is no automatic retry.",
)
PACKAGE_B_ACCEPTANCE_LINES = (
    "I accept Package B for this sequence: M-B9a / START_WITNESS and M-B9b / COMMIT_WITNESS_GENESIS are COMPLETED.",
    "Committed witness genesis digest: {candidate} (= the owner pin = the Package A candidate). chain/1.json "
    "SHA-256: {genesis}. POST9B_VERIFIED evidence SHA-256: {post9b}. Owner offline verification: "
    "MB9B_OWNER_GENESIS_VERIFIED.",
    "This acceptance authorizes nothing further. The Package B deployment freeze ends now; the first deploy after "
    "it must compare EQUAL to the derived running-witness DR-5 target (separate owner record).",
)
REMOVAL_LINES = (
    "I authorize the bounded pre-commit witness-state removal for exactly one invocation.",
    "Plan digest: {plan}.",
    "Classified W9 phase: {phase}.",
    "I acknowledge: this removal is not a retry of M-B9a or M-B9b and removes no lineage; a new attempt needs a new "
    "owner go and a fresh re-proof.",
)
RESTART_LINES = (
    "I authorize one start of the stopped witness (the two sockets, then the service) for exactly this plan.",
    "Plan digest: {plan}.",
    "Classified W9 phase: {phase}.",
    "I acknowledge: this start is not a retry of M-B9a or M-B9b; any earlier WITNESS_STARTED acceptance is stale and "
    "a fresh POST is required before anything else.",
)
# Record §10.8: the owner pre-M-B9a stop. `{control}`, `{b1}` (the B1 record SHA-256) and `{operator}` are bound.
STOP_LINES = (
    "I stop this Package B sequence now, before M-B9a, for this current DEV_SYNTHETIC sequence only.",
    "Control commit: {control}. B1 record SHA-256: {b1}.",
    "Operator: " + OPERATOR + " SHA-256 {operator}.",
    "No B2 was issued, no M-B9a or M-B9b attempt marker exists, and no witness mutation was made by this sequence.",
    "This sequence is OPENED THEN STOPPED BEFORE M-B9a / HISTORICAL / NON-REUSABLE; its evidence is preserved and "
    "must not be replayed into a later sequence.",
    "The Package B deployment freeze of this sequence is RELEASED by this stop; the release authorizes no deployment, "
    "merge or DEV change.",
    "The selected Package B live control {control} is CONSUMED by this sequence and is not reusable.",
    "This stop authorizes nothing further. A new sequence needs a new merged control, a fresh preservation deploy, a "
    "new owner control selection and a new canonical B1.",
)
# Windows CreateProcess caps the whole command line at 32767 characters; every argv the operator builds must stay
# below this margin (record §8.1). Only the verifier bundles exceeded it, and they now travel over stdin.
COMMAND_LINE_LIMIT = 32767
# Record §8.1 (remediation R-B5): the read-only verifier bundles ride the stdin of PuTTY `plink`, launched directly.
# `gcloud compute ssh` on Windows writes "y\n" to plink's stdin when ssh/putty_force_connect is set (Cloud SDK
# 581.0.0, `SSHCommand.Run`), so the caller's bytes never arrive (R-B2, R-B3). The route below is the one R-B4
# proved byte-exact for raw stdin: the same client, key, OS Login user, host alias and IAP tunnel, no prompt.
PLINK_ENV = "LILITH_MB9_PLINK"
# Cloud SDK 581.0.0 `bin/sdk/plink.exe` (PuTTY release 0.83), the client R-B4 used.
PLINK_SHA256 = "7308e9d356f14aa1f08cab1af363f71a077bf35dcb49e50b363418044758cd1e"
PPK_PATH = Path.home() / ".ssh" / "google_compute_engine.ppk"
# SHA-256 of the PPK's public key blob (= `google_compute_engine.pub`), already in the OS Login profile (R-B4).
PPK_PUBLIC_KEY_SHA256 = "e830598a20880490d8b1644d48a448e600503367d3ab130d051e67d2a6e1a12e"
OSLOGIN_USER = "ravindupahasara2_gmail_com"
HOST_ALIAS = "compute.7687007163730582258"
HOST_KEY = "SHA256:XfNINpbMvAzlla6rma0q+whKd6UT12C4Fhc0mpOrEXU"
# No terminal, no prompt (a host-key or authentication question fails instead of reading stdin), no agent.
# `-legacy-stdio-prompts` is never passed: with it, plink reads prompt answers from the verifier's stdin.
PLINK_FLAGS = ("-ssh", "-T", "-batch", "-noagent")
IAP_VERBOSITY = "--verbosity=warning"
# plink exited 0 but wrote to stderr: never a PASS (record §8.1).
TRANSPORT_STDERR_EXIT = 95
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


def _escape_windows_argv(text: str) -> str:
    """The Cloud SDK's Windows argv escape (`ssh._EscapeWindowsArgvElement`): always quoted."""
    result, following_quote = [], True
    for char in text[::-1]:
        if char == '"':
            result.append('"\\')
            following_quote = True
        elif char == "\\":
            result.append("\\\\" if following_quote else "\\")
        else:
            result.append(char)
            following_quote = False
    return '"' + "".join(result)[::-1] + '"'


def _proxy_arg(text: str) -> str:
    """The Cloud SDK's PuTTY ProxyCommand escape (`ssh._EscapeProxyCommandArg`): printable ASCII only."""
    _need(bool(text) and all(0x20 <= ord(char) < 0x7F for char in text), "PROXYCMD_BAD_CHARACTER")
    return _escape_windows_argv(text).replace("\\", "\\\\").replace("%", "%%")


def iap_proxy_command(gcloud: Sequence[str]) -> str:
    """The IAP tunnel exactly as `gcloud compute ssh --tunnel-through-iap` builds it for plink (Cloud SDK 581.0.0
    `ssh._BuildIapTunnelProxyCommandArgs`), from the operator's own gcloud prefix."""
    return " ".join([*(_proxy_arg(part) for part in gcloud), "compute", "start-iap-tunnel", _proxy_arg(DEV), "%port",
                     "--listen-on-stdin", _proxy_arg(f"--project={M6.PROJECT}"), _proxy_arg(f"--zone={M6.ZONE}"),
                     _proxy_arg(IAP_VERBOSITY)])


def ppk_public_key_sha256(path: Path) -> str:
    """SHA-256 of a PuTTY key file's public blob (`Public-Lines`); the private lines are never decoded."""
    try:
        text = Path(path).read_bytes().decode("ascii").replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError) as exc:
        raise Stop("PPK_UNAVAILABLE") from exc
    match = re.search(r"^Public-Lines: (\d+)\n", text, re.MULTILINE)
    _need(match is not None, "PPK_MALFORMED")
    lines = text[match.end():].split("\n")[:int(match.group(1))]
    try:
        return sha256_hex(base64.b64decode("".join(lines), validate=True))
    except ValueError as exc:
        raise Stop("PPK_MALFORMED") from exc


def _verifier_module(repo: Path):
    return sys.modules.get("mb9_witness_verifier_operator") or load_tool(Path(repo), VERIFIER,
                                                                          "mb9_witness_verifier_operator")


class Operator(M6.Operator):
    """Transport, marker and go-check helpers are the pinned M-B6 ones; every pin lookup is this package's."""

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
        """The verifier bundle as (command, stdin payload). The payload is the same base64 gzip'd JSON the M-B6
        loader has always read; only the channel changed (record §8.1). The command carries its SHA-256."""
        import gzip

        sources = {Path(path).stem: self.tool_bytes(repo, path).decode("utf-8") for path in paths}
        payload = base64.b64encode(gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0))
        pins = ",".join(f"{Path(path).stem}={TOOL_PINS[path]}" for path in paths)
        boot = base64.b64encode(M6.BOOT.encode("ascii")).decode("ascii")
        loader = f"import base64;exec(base64.b64decode('{boot}'))"
        command = (f"B=$(cat); printf %s \"$B\" | sha256sum | cut -c1-64 | grep -qx '{sha256_hex(payload)}' || exit 96; "
                   f"printf %s \"$B\" | base64 -d | sudo -n {RELEASE_PYTHON} -I -B -c \"{loader}\" "
                   f"{pins} {Path(paths[-1]).stem} {args}")
        return command, payload + b"\n"

    def plink_argv(self, command: str) -> list[str]:
        """The direct plink route (record §8.1, R-B5). Every binding is checked before launch; any doubt is a STOP,
        never a fallback to `gcloud compute ssh` stdin."""
        plink = os.environ.get(PLINK_ENV, "")
        _need(bool(plink), "PLINK_UNSET")
        try:
            client = Path(plink).read_bytes()
        except OSError as exc:
            raise Stop("PLINK_UNAVAILABLE") from exc
        _need(sha256_hex(client) == PLINK_SHA256, "PLINK_PIN_MISMATCH")
        _need(ppk_public_key_sha256(PPK_PATH) == PPK_PUBLIC_KEY_SHA256, "PPK_KEY_MISMATCH")
        guarded = f'test "$(hostname)" = {DEV} || exit 97; {command}'
        return [plink, *PLINK_FLAGS, "-hostkey", HOST_KEY, "-i", str(PPK_PATH), "-proxycmd",
                iap_proxy_command(self.gcloud), f"{OSLOGIN_USER}@{HOST_ALIAS}", guarded]

    def plink_stdin(self, command: str, data: bytes) -> "subprocess.CompletedProcess[bytes]":
        """`data` on plink's stdin and nothing else, with the capture and 900 s timeout of the pinned `ssh`. A clean
        exit with anything on stderr is reported as TRANSPORT_STDERR_EXIT, never as success."""
        argv = self.plink_argv(command)
        if self.run is M6._default_run:
            result = subprocess.run(argv, input=data, capture_output=True, timeout=900, check=False)
        else:
            result = self.run(argv, input=data)
        if result.returncode == 0 and result.stderr:
            return subprocess.CompletedProcess(result.args, TRANSPORT_STDERR_EXIT, result.stdout, result.stderr)
        return result

    def remote_bundle(self, repo: Path, paths: Sequence[str], args: str) -> "subprocess.CompletedProcess[bytes]":
        return self.plink_stdin(*self.bundled(repo, paths, args))

    # ---------------------------------------------------------------- helpers ---

    @staticmethod
    def candidate(workdir: Path) -> dict:
        """The Package A owner emission (`<workdir>/genesis`, a copy of the accepted one), re-verified."""
        tool = sys.modules.get("mb7_genesis_candidate_operator")
        if tool is None:
            tool = load_tool(Path(__file__).resolve().parents[3], CANDIDATE, "mb7_genesis_candidate_operator")
        files = tool.load_emitted(Path(workdir) / "genesis")
        value = json.loads(files["candidate.json"].decode("ascii"))
        _need(_HEX64.fullmatch(str(value.get("candidateDigest"))) is not None
              and value.get("ledgerHead") == LEDGER_HEAD, "CANDIDATE_INVALID")
        return {"candidate": value["candidateDigest"], "updated_at": value["updatedAt"],
                "pin": sha256_hex(files["genesis-pin.json"]), "register": sha256_hex(files["authorization-register.json"]),
                "record": sha256_hex(files["pin-record.json"])}

    def _w9_args(self, workdir: Path) -> str:
        c = self.candidate(workdir)
        return f"{LEDGER_HEAD} {c['candidate']} {c['updated_at']}"

    def _w9(self, repo: Path, args: str) -> tuple[int | None, dict | None, "subprocess.CompletedProcess[bytes]"]:
        result = self.remote_bundle(repo, VERIFIER_BUNDLE, args)
        try:
            report = json.loads((result.stdout or b"").decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            report = None
        return result.returncode, report if isinstance(report, dict) else None, result

    def _operator_at_control(self, repo: Path) -> str:
        operator = sha256_hex(self._git(repo, "show", f"HEAD:{OPERATOR}"))
        _need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")
        _need(sha256_hex(Path(M6.__file__).read_bytes()) == TOOL_PINS[MB6_OPERATOR], "TOOL_PIN_MISMATCH:" + MB6_OPERATOR)
        _need(sha256_hex(Path(A.__file__).read_bytes()) == TOOL_PINS[MB7_MB8_OPERATOR],
              "TOOL_PIN_MISMATCH:" + MB7_MB8_OPERATOR)
        return operator

    @staticmethod
    def _record(path: Path, value: dict) -> bytes:
        data = json.dumps(value, sort_keys=True).encode("ascii") + b"\n"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        return data

    def _invoke(self, command: str) -> "subprocess.CompletedProcess[bytes]":
        """One remote invocation; a local timeout or launch failure is recorded, never retried."""
        try:
            return self.ssh(command)
        except subprocess.TimeoutExpired as exc:
            return subprocess.CompletedProcess(exc.cmd, None, exc.output or b"", exc.stderr or b"")
        except OSError as exc:
            return subprocess.CompletedProcess([], None, b"", f"LOCAL_{type(exc).__name__}".encode("ascii"))

    @staticmethod
    def _write_class(directory: Path, name: str, value: str, detail: str | None) -> None:
        (directory / f"{name}-transcript.json").write_text(
            json.dumps({"class": value, "detail": detail}, sort_keys=True) + "\n", encoding="ascii", newline="\n")

    @staticmethod
    def _read_class(directory: Path, name: str, verifier) -> str:
        marker = directory / f"{name}.json"
        path = directory / f"{name}-transcript.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="ascii"))["class"]
        return verifier.FAILED_UNCLASSIFIED if marker.is_file() else verifier.NOT_INVOKED

    def _sequence_opened(self, workdir: Path) -> dict:
        path = Path(workdir) / "sequence" / "B1_SEQUENCE_AUTHORIZATION.json"
        _need(path.is_file(), "SEQUENCE_NOT_OPENED")
        _need(not (Path(workdir) / "sequence" / "B1_SEQUENCE_STOPPED.json").exists(), "SEQUENCE_STOPPED")
        return json.loads(path.read_text(encoding="ascii"))

    @staticmethod
    def _post9a_records(workdir: Path) -> list[dict]:
        records = []
        for path in sorted(Path(workdir).glob("post9a-*/POST9A_VERIFIED.json")):
            data = path.read_bytes()
            records.append(dict(json.loads(data), sha256=sha256_hex(data)))
        return records

    @staticmethod
    def _accepted9a(workdir: Path) -> list[dict]:
        return [json.loads(p.read_text(encoding="ascii"))
                for p in sorted((Path(workdir) / "mb9a").glob("WITNESS_STARTED_ACCEPTED-*.json"))]

    def _records(self, workdir: Path, report: dict | None, verifier) -> dict:
        directory = Path(workdir) / ATTEMPT_DIR
        markers = [name for name in MARKERS if (directory / f"{name}.json").is_file()]
        invocation = (report or {}).get("witnessInvocationId")
        mainpid = (report or {}).get("witnessMainPid")
        posts, accepted = self._post9a_records(workdir), self._accepted9a(workdir)
        current = lambda r: r.get("invocationId") == invocation and r.get("mainPid") == mainpid  # noqa: E731
        return {"markers": markers, "stage": self._read_class(directory, "mb9a-1", verifier),
                "start": self._read_class(directory, "mb9a-2", verifier),
                "bootstrap": self._read_class(directory, "mb9b", verifier),
                "post9a_current": bool(invocation) and any(current(r) for r in posts),
                "accepted9a_current": bool(invocation) and any(current(r) for r in accepted),
                "stale9a": bool(posts or accepted) and not any(current(r) for r in posts + accepted),
                "post9b": (Path(workdir) / "post9b" / "POST9B_VERIFIED.json").is_file()}

    # ------------------------------------------------------------ local forms ---

    def pins(self, repo: Path) -> dict:
        status = self._git(repo, "status", "--porcelain", "--untracked-files=no")
        _need(status.strip() == b"", "CONTROL_CHECKOUT_NOT_CLEAN")
        control = self.control(repo)
        for path in TOOL_PINS:
            self.tool_bytes(repo, path)
        return {"control": control, "tools": dict(TOOL_PINS), "result": "MB9_TOOL_PINS_EXACT"}

    def open_sequence(self, repo: Path, workdir: Path, statement: Path) -> dict:
        control = self.pins(repo)["control"]
        operator = self._operator_at_control(repo)
        c = self.candidate(workdir)
        raw = Path(statement).read_bytes()
        self.check_go(raw.decode("utf-8"), SEQUENCE_LINES, control=control, operator=operator,
                      candidate=c["candidate"], updated_at=c["updated_at"])
        directory = Path(workdir) / "sequence"
        directory.mkdir(mode=0o700, exist_ok=True)
        try:
            self._record(directory / "B1_SEQUENCE_AUTHORIZATION.json", {
                "control": control, "operatorSha256": operator, "candidateDigest": c["candidate"],
                "updatedAt": c["updated_at"], "statementSha256": sha256_hex(raw)})
        except FileExistsError as exc:
            raise Stop("SEQUENCE_ALREADY_OPENED") from exc
        return {"control": control, "result": "PACKAGE_B_SEQUENCE_OPENED_READ_ONLY",
                "next": "fresh evidence and the closing gate, then the separate B2; nothing is authorized by this"}

    def stop_sequence(self, repo: Path, workdir: Path, statement: Path) -> dict:
        """Record §10.8: the owner pre-M-B9a stop. Only while B1 is recorded and the attempt directory is absent or
        empty; once any marker exists the W9 classifier, removal, restart and recovery routes govern instead."""
        control = self.pins(repo)["control"]
        operator = self._operator_at_control(repo)
        opened = self._sequence_opened(workdir)
        _need(opened.get("control") == control, "CONTROL_NOT_THE_SEQUENCE_CONTROL")
        attempts = Path(workdir) / ATTEMPT_DIR
        _need(not attempts.exists() or not any(attempts.iterdir()), "STOP_REFUSED_ATTEMPT_MARKER_PRESENT")
        b1 = sha256_hex((Path(workdir) / "sequence" / "B1_SEQUENCE_AUTHORIZATION.json").read_bytes())
        raw = Path(statement).read_bytes()
        self.check_go(raw.decode("utf-8"), STOP_LINES, control=control, b1=b1, operator=operator)
        try:
            self._record(Path(workdir) / "sequence" / "B1_SEQUENCE_STOPPED.json", {
                "control": control, "operatorSha256": operator, "b1RecordSha256": b1, "statementSha256": sha256_hex(raw),
                "classification": "OPENED_THEN_STOPPED_BEFORE_MB9A", "freeze": "RELEASED", "controlSelection": "CONSUMED"})
        except FileExistsError as exc:
            raise Stop("SEQUENCE_ALREADY_STOPPED") from exc
        return {"control": control, "result": "PACKAGE_B_SEQUENCE_STOPPED_BEFORE_MB9A",
                "next": "nothing is authorized; a new sequence needs a new control, a preservation deploy, a new owner "
                        "control selection and a new canonical B1"}

    def accept_9a(self, workdir: Path, statement: Path) -> dict:
        raw = Path(statement).read_bytes()
        text = raw.decode("utf-8")
        for post in self._post9a_records(workdir):
            try:
                self.check_go(text, WITNESS_STARTED_LINES, invocation=post["invocationId"], mainpid=post["mainPid"],
                              post9a=post["sha256"])
            except Stop:
                continue
            directory = Path(workdir) / "mb9a"
            directory.mkdir(mode=0o700, exist_ok=True)
            try:
                self._record(directory / f"WITNESS_STARTED_ACCEPTED-{post['invocationId']}.json", {
                    "invocationId": post["invocationId"], "mainPid": post["mainPid"], "post9aSha256": post["sha256"],
                    "statementSha256": sha256_hex(raw)})
            except FileExistsError as exc:
                raise Stop("WITNESS_STARTED_ALREADY_RECORDED") from exc
            return {"invocationId": post["invocationId"], "result": "WITNESS_STARTED_OWNER_ACCEPTANCE_RECORDED",
                    "next": "fresh KNOWN_EMPTY, P-A / P-B, the M-B9b closing gate, then the separate B4 go; "
                            "M-B9b is not authorized by this"}
        raise Stop("NO_POST9A_MATCHES_STATEMENT")

    def dr5(self, repo: Path, phase: str, log: Path) -> dict:
        target = load_tool(Path(repo), DR5_TARGET, "mb9_dr5_target_operator")
        try:
            return target.compare(phase, Path(log).read_bytes().decode("utf-8", "replace"))
        except target.TargetError as exc:
            raise Stop(exc.reason) from exc

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
            "systemctl show -p Id,LoadState,ActiveState,SubState,UnitFileState,NeedDaemonReload,MainPID,NRestarts,"
            "InvocationID,Result lilith-memory-broker.service lilith-authority-dev.service lilith-authority-dev.socket "
            "lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket "
            "--no-pager; "
            "sudo -n /usr/local/sbin/lilith-activation-verify; echo activation_rc=$?; "
            "sudo -n /usr/bin/ls -A1 /etc/lilith-authority-dev/trust /etc/lilith-authority-dev/registry "
            "/etc/lilith-authority-dev/owner /var/lib/lilith-authority-custody/holds; "
            "sudo -n /usr/bin/stat -c '%n %U:%G %a %s %h' /etc/lilith-authority-dev/owner "
            "/etc/lilith-authority-dev/owner/genesis-pin.json /etc/lilith-authority-dev/owner/authorization-register.json; "
            "sudo -n /usr/bin/sha256sum /etc/lilith-authority-dev/owner/genesis-pin.json "
            "/etc/lilith-authority-dev/owner/authorization-register.json; "
            "for p in /var/lib/lilith-authority-dev /var/lib/lilith-recovery-witness; do "
            "if sudo -n test -e $p; then echo \"STATE $p PRESENT\"; else echo \"STATE $p ABSENT\"; fi; done; "
            "sudo -n /usr/bin/stat -c '%n %F %U:%G %a %s %h' /var/lib/lilith-recovery-witness "
            "/run/lilith-recovery-witness /run/lilith-recovery-witness/owner.sock /run/lilith-recovery-witness/signer.sock "
            "/run/credentials/lilith-recovery-witness.service; "
            "sudo -n /usr/bin/ls -A1 /var/lib/lilith-recovery-witness /var/lib/lilith-recovery-witness/chain "
            "/var/lib/lilith-recovery-witness/authorizations; "
            "sudo -n /usr/bin/sha256sum /var/lib/lilith-recovery-witness/chain/1.json "
            "/var/lib/lilith-recovery-witness/witness.json; "
            + TMP_RESIDUE + "; echo TMP_RESIDUE_END")
        readiness = (f"readlink /opt/lilith-authority-dev/current; sudo -n test -x {RELEASE_PYTHON} "
                     f"&& echo RELEASE_PYTHON=executable; sudo -n {RELEASE_PYTHON} -I -B -c \"{READINESS_PROBE}\"")
        args = self._w9_args(workdir)
        return {
            "identity": self._save(out, "identity", self.ssh(identity)),
            # the custody chain ends with `echo`: an absent witness path is recorded on stderr, not as a code
            "custody": self._save(out, "custody", self.ssh(custody)),
            "readiness": self._save(out, "readiness", self.ssh(readiness)),
            "status": self._save(out, "status", self.ssh(self.streamed(
                repo, INSTALLER, SYSTEM_PYTHON, f"status --expect {INSTALLER_STAGE[phase]} {RELEASE_SHA}"))),
            "preservation": self._save(out, "preservation", self.ssh(self.streamed(
                repo, BROKER, SYSTEM_PYTHON, "preservation"))),
            "observer": self._save(out, "observer", self.ssh(self.streamed(repo, OBSERVER, SYSTEM_PYTHON, "observe"))),
            "w5verifier": self._save(out, "w5verifier", self.ssh(self.streamed(
                repo, W5_VERIFIER, RELEASE_PYTHON, f"expect {W5_PHASE[phase]}"))),
            "mb6verifier": self._save(out, "mb6verifier", self.remote_bundle(
                repo, MB6_VERIFIER_BUNDLE, f"expect {MB6_PHASE[phase]} {LEDGER_HEAD}")),
            "w8verifier": self._save(out, "w8verifier", self.remote_bundle(
                repo, W8_BUNDLE, f"expect {W8_PHASE[phase]} {args}")),
            "w9verifier": self._save(out, "w9verifier", self.remote_bundle(
                repo, VERIFIER_BUNDLE, f"expect {W9_PHASE[phase]} {args}")),
        }

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
                and probe.get("verifyCli") == A.VERIFY_CLI_SHA256 and probe.get("witnessOwnerCli") == OWNER_CLI_SHA256
                and probe.get("release") == "/opt/lilith-authority-dev/current" and probe.get("deserialize") is True)

    def host(self, repo: Path, workdir: Path, evidence: Path, phase: str) -> dict:
        _need(phase in INSTALLER_STAGE, "PHASE_INVALID")
        self.candidate(workdir)
        out = self._new_dir(Path(evidence))
        codes = self._host_reads(repo, out, phase, workdir)
        readiness_ok = codes["readiness"] == 0 and self.readiness_ok((out / "readiness.out").read_bytes())
        residue = A.Operator.tmp_residue((out / "custody.out").read_bytes())
        result = "MB9_HOST_" + phase + ("_PASS" if all(c == 0 for c in codes.values()) and readiness_ok
                                        and residue == [] else "_NOT_PASS")
        return {"codes": codes, "readinessExact": readiness_ok, "tmpResidue": residue, "result": result,
                "note": "PASS requires every code 0 and the owner's comparison of the recorded facts"}

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

    def witness_denial(self, repo: Path, evidence: Path, phase: str) -> dict:
        _need(phase in ("P1B-9a", "P1B-9b"), "PHASE_INVALID")
        return self._proof(repo, evidence, WITNESS_DENIAL, phase, "witness-denial")

    def classify(self, repo: Path, workdir: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code, report, result = self._w9(repo, f"observe {self._w9_args(workdir)}")
        self._save(out, "w9verifier", result)
        _need(code == 0 and report is not None, "VERIFIER_FAILED")
        verifier = _verifier_module(repo)
        records = self._records(workdir, report, verifier)
        phase = verifier.classify_sequence(host_phase=report["phase"], **records)
        route = verifier.SEQUENCE_ROUTING.get(phase, verifier.SEQUENCE_ROUTING[verifier.UNCLASSIFIED])
        return {"hostPhase": report["phase"], "hostRouting": report["routing"], "sequencePhase": phase,
                "routing": route[0], "action": route[1], "records": records, "result": "MB9_CLASSIFIED"}

    def health(self, repo: Path, workdir: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code, report, result = self._w9(repo, f"observe {self._w9_args(workdir)}")
        self._save(out, "w9verifier", result)
        _need(code == 0 and report is not None and report.get("phase") in RUNNING_PHASES,
              "WITNESS_NOT_RUNNING_NO_SOCKET_CONTACT")
        reply = self.ssh(HEALTH_COMMAND)
        self._save(out, "health", reply)
        expected = "UNINITIALIZED" if report["phase"] == RUNNING_PHASES[0] else "CONSISTENT"
        check = _verifier_module(repo).check_health(reply.stdout or b"", expected_classification=expected,
                                                    kwit_public_key_sha256=KWIT_PUBLIC_KEY_SHA256,
                                                    witness_key_id=KWIT_KEY_ID)
        return {"phase": report["phase"], "health": check, "result": "MB9_HEALTH_EXACT" if check["exact"]
                and reply.returncode == 0 else "MB9_HEALTH_NOT_EXACT"}

    def chain_export(self, repo: Path, workdir: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code, report, result = self._w9(repo, f"observe {self._w9_args(workdir)}")
        self._save(out, "w9verifier", result)
        files = {}
        for name, remote in (("chain-1.json", f"{WITNESS_STATE}/chain/1.json"),
                             ("witness.json", f"{WITNESS_STATE}/witness.json")):
            fetched = self.ssh(f"sudo -n /usr/bin/base64 -w0 {remote}")
            self._save(out, name + ".b64", fetched)
            if fetched.returncode == 0:
                data = base64.b64decode((fetched.stdout or b"").strip(), validate=True)
                (out / name).write_bytes(data)
                files[name] = sha256_hex(data)
        return {"phase": (report or {}).get("phase"), "files": files,
                "result": "MB9_CHAIN_EXPORTED" if len(files) == 2 else "MB9_CHAIN_EXPORT_INCOMPLETE",
                "note": "evidence storage only (OD-B10): not record 1, not FRESHNESS=CURRENT, no replica write"}

    # ------------------------------------------------------------------ M-B9a ---

    def mb9a(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        control = self.pins(repo)["control"]
        operator = self._operator_at_control(repo)
        c = self.candidate(workdir)
        self._sequence_opened(workdir)
        raw = Path(go_file).read_bytes()
        self.check_go(raw.decode("utf-8"), MB9A_GO_LINES, control=control, operator=operator, candidate=c["candidate"],
                      pin=c["pin"], register=c["register"])
        directory = Path(workdir) / ATTEMPT_DIR
        _need(not (directory / "mb9a-1.json").exists(), "ATTEMPT_ALREADY_CONSUMED:mb9a-1")
        verifier = _verifier_module(repo)                                             # before any write
        args = self._w9_args(workdir)
        code, report, _ = self._w9(repo, f"expect {verifier.W9_0} {args}")
        _need(code == 0 and report is not None and report.get("phase") == verifier.W9_0, "PRE_STATE_NOT_W9_0")

        # ---- stage 9A-1: the ONE `witness-state`
        directory = self._one_attempt(workdir, "mb9a-1", raw)
        result = self._invoke(self.streamed(repo, INSTALLER, SYSTEM_PYTHON, f"witness-state {RELEASE_SHA}"))
        self._save(directory, "mb9a-1-witness-state", result)
        stage, detail = verifier.classify_stage_transcript(result.returncode, result.stdout or b"", result.stderr or b"")
        self._write_class(directory, "mb9a-1", stage, detail)
        code1, after1, raw1 = self._w9(repo, f"observe {args}")
        self._save(directory, "mb9a-1-w9", raw1)
        phase1 = (after1 or {}).get("phase")
        if not (stage == verifier.STAGE_PASS and code1 == 0 and phase1 == verifier.W9_1):
            return {"stage1": stage, "detail": detail, "hostPhase": phase1, "stage2": "NOT_RUN",
                    "result": "MB9A_STOP_AFTER_STAGE_1",
                    "next": "STOP: `classify`, then owner review; stage 9A-2 never runs over an inexact stage 9A-1"}

        # ---- stage 9A-2: the ONE start of the two sockets and the service
        self._one_attempt(workdir, "mb9a-2", raw)
        result = self._invoke(START_COMMAND)
        self._save(directory, "mb9a-2-start", result)
        start, detail = verifier.classify_start_transcript(result.returncode, result.stdout or b"", result.stderr or b"")
        self._write_class(directory, "mb9a-2", start, detail)
        code2, after2, raw2 = self._w9(repo, f"observe {args}")
        self._save(directory, "mb9a-2-w9", raw2)
        phase2 = (after2 or {}).get("phase")
        health = None
        if code2 == 0 and phase2 == verifier.W9_2:                       # observed running: health is now read-only
            reply = self.ssh(HEALTH_COMMAND)
            self._save(directory, "mb9a-health", reply)
            health = verifier.check_health(reply.stdout or b"", expected_classification="UNINITIALIZED",
                                           kwit_public_key_sha256=KWIT_PUBLIC_KEY_SHA256, witness_key_id=KWIT_KEY_ID)
        passed = start == verifier.START_OK and phase2 == verifier.W9_2 and bool(health and health["exact"])
        return {"stage1": verifier.STAGE_PASS, "stage2": start, "detail": detail, "hostPhase": phase2,
                "invocationId": (after2 or {}).get("witnessInvocationId"), "mainPid": (after2 or {}).get("witnessMainPid"),
                "health": health, "result": "MB9A_STARTED" if passed else "MB9A_STOP",
                "next": "read-only POST9A (`post9a`), then HARD STOP for owner B3; never M-B9b" if passed
                else "STOP: `classify`, then owner review; restart or removal only under a separate authorization"}

    def post9a(self, repo: Path, workdir: Path) -> dict:
        verifier = _verifier_module(repo)
        directory = Path(workdir) / ATTEMPT_DIR
        _need(all((directory / f"{name}.json").is_file() for name in ("mb9a-1", "mb9a-2")), "MB9A_NOT_IN_THIS_SEQUENCE")
        code, report, _ = self._w9(repo, f"observe {self._w9_args(workdir)}")
        _need(code == 0 and report is not None and report.get("phase") == verifier.W9_2, "HOST_NOT_W9_2")
        invocation, mainpid = report.get("witnessInvocationId"), report.get("witnessMainPid")
        _need(bool(invocation) and bool(mainpid), "WITNESS_INCARNATION_UNKNOWN")
        _need(not any(r.get("invocationId") == invocation for r in self._post9a_records(workdir)),
              "POST9A_ALREADY_VERIFIED_FOR_THIS_INCARNATION")
        records = self._records(workdir, report, verifier)
        sequence = verifier.classify_sequence(host_phase=report["phase"], **records)
        _need(sequence in (verifier.S9A_POST_PENDING, verifier.S9A2_INCOMPLETE, verifier.S9A_STALE),
              "SEQUENCE_NOT_POST_PENDING:" + sequence)
        out = self._new_dir(Path(workdir) / f"post9a-{len(list(Path(workdir).glob('post9a-*'))) + 1}")
        codes = self._host_reads(repo, out, "POST9A", workdir)
        codes["witness-denial"] = self._save(out, "witness-denial", self.ssh(self.streamed(
            repo, WITNESS_DENIAL, SYSTEM_PYTHON, "P1B-9a")))
        codes["denial"] = self._save(out, "denial", self.ssh(self.streamed(repo, DENIAL, SYSTEM_PYTHON, "P1B-5")))
        reply = self.ssh(HEALTH_COMMAND)
        codes["health"] = self._save(out, "health", reply)
        health = verifier.check_health(reply.stdout or b"", expected_classification="UNINITIALIZED",
                                       kwit_public_key_sha256=KWIT_PUBLIC_KEY_SHA256, witness_key_id=KWIT_KEY_ID)
        readiness_ok = codes["readiness"] == 0 and self.readiness_ok((out / "readiness.out").read_bytes())
        residue = A.Operator.tmp_residue((out / "custody.out").read_bytes())
        try:
            post = json.loads((out / "w9verifier.out").read_bytes().decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            post = {}
        same = (post.get("witnessInvocationId"), post.get("witnessMainPid")) == (invocation, mainpid)
        verified = (all(code == 0 for code in codes.values()) and readiness_ok and residue == []
                    and post.get("phase") == verifier.W9_2 and all(post.get("evidence9a", {}).get(name) is True
                                                                   for name in verifier.EVIDENCE_9A)
                    and post.get("witnessNRestarts") == "0" and same and health["exact"])
        if verified:
            data = self._record(out / "POST9A_VERIFIED.json", {
                "invocationId": invocation, "mainPid": mainpid, "phase": verifier.S9A_POST_VERIFIED,
                "w9Sha256": sha256_hex((out / "w9verifier.out").read_bytes()),
                "healthSha256": sha256_hex((out / "health.out").read_bytes()),
                "witnessDenialSha256": sha256_hex((out / "witness-denial.out").read_bytes()),
                "denialSha256": sha256_hex((out / "denial.out").read_bytes()), "ownerAccepted": False})
            return {"codes": codes, "post9aSha256": sha256_hex(data), "invocationId": invocation, "mainPid": mainpid,
                    "result": "MB9A_POST_VERIFIED", "next": "HARD STOP: owner B3 (WITNESS_STARTED); M-B9b is not "
                                                            "authorized"}
        return {"codes": codes, "readinessExact": readiness_ok, "health": health, "sameIncarnation": same,
                "result": "MB9A_POST_NOT_VERIFIED", "next": "STOP: `classify`, then owner review"}

    # ------------------------------------------------------------------ M-B9b ---

    def mb9b(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        control = self.pins(repo)["control"]
        operator = self._operator_at_control(repo)
        c = self.candidate(workdir)
        self._sequence_opened(workdir)
        directory = Path(workdir) / ATTEMPT_DIR
        _need(not (directory / "mb9b.json").exists(), "ATTEMPT_ALREADY_CONSUMED:mb9b")
        verifier = _verifier_module(repo)                                             # before any write
        args = self._w9_args(workdir)
        code, report, _ = self._w9(repo, f"expect {verifier.W9_2} {args}")
        _need(code == 0 and report is not None and report.get("phase") == verifier.W9_2, "PRE_STATE_NOT_W9_2")
        invocation, mainpid = report.get("witnessInvocationId"), report.get("witnessMainPid")
        accepted = [r for r in self._accepted9a(workdir)
                    if (r.get("invocationId"), r.get("mainPid")) == (invocation, mainpid)]
        _need(len(accepted) == 1, "WITNESS_INCARNATION_CHANGED_OR_NOT_ACCEPTED")
        raw = Path(go_file).read_bytes()
        self.check_go(raw.decode("utf-8"), MB9B_GO_LINES, control=control, operator=operator, candidate=c["candidate"],
                      pin=c["pin"], register=c["register"], record=c["record"], updated_at=c["updated_at"],
                      invocation=invocation, mainpid=mainpid, post9a=accepted[0]["post9aSha256"])
        _need(PONR_ACKNOWLEDGEMENT in " ".join(raw.decode("utf-8").replace(">", " ").split()), "PONR_NOT_ACKNOWLEDGED")
        directory = self._one_attempt(workdir, "mb9b", raw)
        result = self._invoke(f"sudo -n {OWNER_CLI} bootstrap 1 {c['updated_at']}")    # the ONE lineage command
        self._save(directory, "mb9b-bootstrap", result)
        transcript, detail = verifier.classify_bootstrap_transcript(result.returncode, result.stdout or b"",
                                                                    result.stderr or b"", candidate_digest=c["candidate"])
        self._write_class(directory, "mb9b", transcript, detail)
        code2, after, raw2 = self._w9(repo, f"observe {args}")
        self._save(directory, "mb9b-w9", raw2)
        phase = (after or {}).get("phase")
        return {"code": result.returncode, "attempt": "CONSUMED", "transcript": transcript, "detail": detail,
                "hostPhase": phase,
                "result": "MB9B_COMMITTED" if transcript == verifier.BOOTSTRAP_PASS and phase == verifier.W9_5
                else "MB9B_STOP",
                "next": "read-only POST9B (`post9b`) and the owner offline verification, then HARD STOP for B5"
                if phase == verifier.W9_5 else "STOP: `classify`; the host phase decides; never a retry"}

    def post9b(self, repo: Path, workdir: Path) -> dict:
        verifier = _verifier_module(repo)
        c = self.candidate(workdir)
        _need((Path(workdir) / ATTEMPT_DIR / "mb9b.json").is_file(), "MB9B_NOT_IN_THIS_SEQUENCE")
        _need(not (Path(workdir) / "post9b" / "POST9B_VERIFIED.json").exists(), "POST9B_ALREADY_VERIFIED")
        code, report, _ = self._w9(repo, f"observe {self._w9_args(workdir)}")
        _need(code == 0 and report is not None, "VERIFIER_FAILED")
        records = self._records(workdir, report, verifier)
        sequence = verifier.classify_sequence(host_phase=report["phase"], **records)
        _need(sequence in (verifier.S9B_POST_PENDING, verifier.S9B_UNACKNOWLEDGED), "SEQUENCE_NOT_POST_PENDING:"
              + sequence)
        out = self._new_dir(Path(workdir) / "post9b")
        codes = self._host_reads(repo, out, "POST9B", workdir)
        codes["witness-denial"] = self._save(out, "witness-denial", self.ssh(self.streamed(
            repo, WITNESS_DENIAL, SYSTEM_PYTHON, "P1B-9b")))
        codes["denial"] = self._save(out, "denial", self.ssh(self.streamed(repo, DENIAL, SYSTEM_PYTHON, "P1B-5")))
        reply = self.ssh(HEALTH_COMMAND)
        codes["health"] = self._save(out, "health", reply)
        health = verifier.check_health(reply.stdout or b"", expected_classification="CONSISTENT",
                                       kwit_public_key_sha256=KWIT_PUBLIC_KEY_SHA256, witness_key_id=KWIT_KEY_ID)
        read = self.ssh(READ_COMMAND)
        codes["read"] = self._save(out, "read", read)
        exported = {}
        for name, remote in (("chain-1.json", f"{WITNESS_STATE}/chain/1.json"),
                             ("witness.json", f"{WITNESS_STATE}/witness.json")):
            fetched = self.ssh(f"sudo -n /usr/bin/base64 -w0 {remote}")
            codes["export-" + name] = self._save(out, name + ".b64", fetched)
            if fetched.returncode == 0:
                data = base64.b64decode((fetched.stdout or b"").strip(), validate=True)
                (out / name).write_bytes(data)
                exported[name] = data
        readiness_ok = codes["readiness"] == 0 and self.readiness_ok((out / "readiness.out").read_bytes())
        residue = A.Operator.tmp_residue((out / "custody.out").read_bytes())
        try:
            post = json.loads((out / "w9verifier.out").read_bytes().decode("utf-8"))
            read_reply = json.loads((read.stdout or b"").decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            post, read_reply = {}, {}
        genesis = exported.get("chain-1.json", b"")
        read_ok = (read_reply.get("status") == "OK" and read_reply.get("classification") == "CONSISTENT"
                   and isinstance(read_reply.get("witness"), dict)
                   and read_reply["witness"].get("witnessVersion") == 1)
        verified = (all(code == 0 for code in codes.values()) and readiness_ok and residue == []
                    and post.get("phase") == verifier.W9_5
                    and all(post.get("evidence9b", {}).get(name) is True for name in verifier.EVIDENCE_9B)
                    and post.get("committedGenesis", {}).get("digest") == c["candidate"]
                    and post.get("committedGenesis", {}).get("sha256") == sha256_hex(genesis)
                    and exported.get("witness.json") == genesis and health["exact"] and read_ok)
        if verified:
            data = self._record(out / "POST9B_VERIFIED.json", {
                "candidateDigest": c["candidate"], "genesisSha256": sha256_hex(genesis), "phase": verifier.S9B_POST_VERIFIED
                if sequence == verifier.S9B_POST_PENDING else verifier.S9B_ADOPTION_PENDING,
                "adoptionRequired": sequence == verifier.S9B_UNACKNOWLEDGED,
                "witnessDenialSha256": sha256_hex((out / "witness-denial.out").read_bytes()),
                "denialSha256": sha256_hex((out / "denial.out").read_bytes()),
                "healthSha256": sha256_hex((out / "health.out").read_bytes()), "ownerAccepted": False})
            return {"codes": codes, "post9bSha256": sha256_hex(data), "genesisSha256": sha256_hex(genesis),
                    "result": "MB9B_POST_VERIFIED",
                    "next": "the owner offline verification (`mb9_owner_genesis_verify.py verify`), then HARD STOP "
                            "for B5; record 1 is not authorized"}
        return {"codes": codes, "readinessExact": readiness_ok, "health": health, "read": read_ok,
                "result": "MB9B_POST_NOT_VERIFIED", "next": "STOP: `classify`, then owner review"}

    # ------------------------------------------------------- removal / restart ---

    def removal_plan(self, repo: Path, workdir: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code, report, result = self._w9(repo, f"observe {self._w9_args(workdir)}")
        self._save(out, "w9verifier", result)
        plan = self.ssh(self.streamed(repo, REMOVAL, SYSTEM_PYTHON, "plan"))
        plan_code = self._save(out, "removal-plan", plan)
        phase = (report or {}).get("phase")
        return {"code": plan_code, "w9Phase": phase, "removable": phase in REMOVABLE_PHASES and plan_code == 0,
                "result": "MB9_REMOVAL_PLAN_RECORDED" if plan_code == 0 else "MB9_REMOVAL_PLAN_REFUSED",
                "authorityGranted": False}

    def removal(self, repo: Path, workdir: Path, plan_evidence: Path, authorization: Path) -> dict:
        self.pins(repo)
        observed = json.loads((Path(plan_evidence) / "w9verifier.out").read_text(encoding="utf-8"))
        plan = json.loads((Path(plan_evidence) / "removal-plan.out").read_text(encoding="utf-8"))
        digest, phase = plan.get("planDigest"), observed.get("phase")
        _need(isinstance(digest, str) and _HEX64.fullmatch(digest) is not None and plan.get("remove"),
              "PLAN_NOT_ACTIONABLE")
        _need(phase in REMOVABLE_PHASES, "PHASE_NOT_REMOVABLE:" + str(phase))
        raw = Path(authorization).read_bytes()
        self.check_go(raw.decode("utf-8"), REMOVAL_LINES, plan=digest, phase=phase)
        directory = self._one_attempt(workdir, "removal-" + digest[:16], raw)
        result = self._invoke(self.streamed(repo, REMOVAL, SYSTEM_PYTHON, f"remove {digest}"))
        code = self._save(directory, "removal-" + digest[:16], result)
        after_code, after, raw_after = self._w9(repo, f"observe {self._w9_args(workdir)}")
        self._save(directory, "removal-" + digest[:16] + "-w9", raw_after)
        return {"code": code, "planDigest": digest, "hostPhase": (after or {}).get("phase"),
                "result": "MB9_PRE_MB9A_RESTORED" if code == 0 and (after or {}).get("phase") == "W9_0_PRE_WITNESS"
                else "MB9_REMOVAL_STOP", "authorityGranted": False,
                "next": "a new M-B9a attempt needs a new owner B2 and a fresh re-proof (a new operator work directory)"}

    def _restart_plan_body(self, report: dict) -> dict:
        store = report.get("store", {})
        return {"planType": "LILITH_MB9_WITNESS_RESTART_PLAN", "schemaVersion": 1, "phase": report.get("phase"),
                "runtime": report.get("runtime"), "storeClassification": report.get("storeClassification"),
                "listing": store.get("listing"), "chain": sorted(store.get("chain", {})),
                "committedGenesisSha256": report.get("committedGenesis", {}).get("sha256")}

    def restart_plan(self, repo: Path, workdir: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code, report, result = self._w9(repo, f"observe {self._w9_args(workdir)}")
        self._save(out, "w9verifier", result)
        _need(code == 0 and report is not None, "VERIFIER_FAILED")
        body = self._restart_plan_body(report)
        restartable = body["phase"] in RESTARTABLE_PHASES and body["runtime"] == "STOPPED"
        digest = sha256_hex(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii"))
        (out / "restart-plan.json").write_text(json.dumps(dict(body, planDigest=digest), sort_keys=True) + "\n",
                                               encoding="ascii", newline="\n")
        return {"planDigest": digest, "w9Phase": body["phase"], "restartable": restartable,
                "result": "MB9_RESTART_PLAN_RECORDED" if restartable else "MB9_RESTART_NOT_APPLICABLE",
                "authorityGranted": False}

    def restart(self, repo: Path, workdir: Path, plan_evidence: Path, authorization: Path) -> dict:
        self.pins(repo)
        planned = json.loads((Path(plan_evidence) / "restart-plan.json").read_text(encoding="ascii"))
        digest = planned.get("planDigest")
        _need(isinstance(digest, str) and _HEX64.fullmatch(digest) is not None, "PLAN_NOT_ACTIONABLE")
        _need(planned.get("phase") in RESTARTABLE_PHASES and planned.get("runtime") == "STOPPED", "PHASE_NOT_RESTARTABLE")
        raw = Path(authorization).read_bytes()
        self.check_go(raw.decode("utf-8"), RESTART_LINES, plan=digest, phase=planned["phase"])
        args = self._w9_args(workdir)
        code, report, _ = self._w9(repo, f"observe {args}")
        _need(code == 0 and report is not None, "VERIFIER_FAILED")
        current = self._restart_plan_body(report)
        _need(sha256_hex(json.dumps(current, sort_keys=True, separators=(",", ":")).encode("ascii")) == digest,
              "PLAN_CHANGED")
        verifier = _verifier_module(repo)
        directory = self._one_attempt(workdir, "restart-" + digest[:16], raw)
        result = self._invoke(START_COMMAND)
        self._save(directory, "restart-" + digest[:16], result)
        start, detail = verifier.classify_start_transcript(result.returncode, result.stdout or b"", result.stderr or b"")
        after_code, after, raw_after = self._w9(repo, f"observe {args}")
        self._save(directory, "restart-" + digest[:16] + "-w9", raw_after)
        phase = (after or {}).get("phase")
        return {"start": start, "detail": detail, "hostPhase": phase, "planDigest": digest,
                "result": "MB9_WITNESS_RESTARTED" if start == verifier.START_OK and phase in RUNNING_PHASES
                else "MB9_RESTART_STOP", "authorityGranted": False,
                "next": "a fresh POST9A (pre-lineage) or POST9B (committed) before anything else; no earlier "
                        "acceptance is replayed"}


USAGE = __doc__.split("| Form |", 1)[1].split("\n\n", 1)[0]


def main(argv: list[str], operator: Operator | None = None) -> int:
    operator = operator or Operator()
    forms = {
        ("pins", 1): lambda a: operator.pins(Path(a[0])),
        ("cloud", 2): lambda a: operator.cloud(Path(a[0]), a[1]),
        ("open-sequence", 3): lambda a: operator.open_sequence(Path(a[0]), Path(a[1]), Path(a[2])),
        ("stop-sequence", 3): lambda a: operator.stop_sequence(Path(a[0]), Path(a[1]), Path(a[2])),
        ("host", 4): lambda a: operator.host(Path(a[0]), Path(a[1]), Path(a[2]), a[3]),
        ("denial", 2): lambda a: operator.denial(Path(a[0]), Path(a[1])),
        ("ledger-denial", 2): lambda a: operator.ledger_denial(Path(a[0]), Path(a[1])),
        ("owner-denial", 2): lambda a: operator.owner_denial(Path(a[0]), Path(a[1])),
        ("witness-denial", 3): lambda a: operator.witness_denial(Path(a[0]), Path(a[1]), a[2]),
        ("classify", 3): lambda a: operator.classify(Path(a[0]), Path(a[1]), Path(a[2])),
        ("mb9a", 3): lambda a: operator.mb9a(Path(a[0]), Path(a[1]), Path(a[2])),
        ("post9a", 2): lambda a: operator.post9a(Path(a[0]), Path(a[1])),
        ("accept-9a", 2): lambda a: operator.accept_9a(Path(a[0]), Path(a[1])),
        ("mb9b", 3): lambda a: operator.mb9b(Path(a[0]), Path(a[1]), Path(a[2])),
        ("post9b", 2): lambda a: operator.post9b(Path(a[0]), Path(a[1])),
        ("chain-export", 3): lambda a: operator.chain_export(Path(a[0]), Path(a[1]), Path(a[2])),
        ("health", 3): lambda a: operator.health(Path(a[0]), Path(a[1]), Path(a[2])),
        ("dr5", 3): lambda a: operator.dr5(Path(a[0]), a[1], Path(a[2])),
        ("removal-plan", 3): lambda a: operator.removal_plan(Path(a[0]), Path(a[1]), Path(a[2])),
        ("removal", 4): lambda a: operator.removal(Path(a[0]), Path(a[1]), Path(a[2]), Path(a[3])),
        ("restart-plan", 3): lambda a: operator.restart_plan(Path(a[0]), Path(a[1]), Path(a[2])),
        ("restart", 4): lambda a: operator.restart(Path(a[0]), Path(a[1]), Path(a[2]), Path(a[3])),
    }
    form = forms.get((argv[0], len(argv) - 1)) if argv else None
    if form is None:
        print("mb9_operator: USAGE" + USAGE, file=sys.stderr)
        return 2
    try:
        result = form(argv[1:])
    except Stop as stop:
        print(f"mb9_operator: STOP {stop.code}", file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
