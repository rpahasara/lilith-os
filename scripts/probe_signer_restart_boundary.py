#!/usr/bin/python3 -IB
"""LILITH 15B2b-B1b-3e M-B11 PR-A1: synthetic systemd probe of the CANDIDATE signer restart boundary (OD-M11-11).

DISPOSABLE GITHUB-HOSTED RUNNER ONLY. It refuses to run unless it is root on a systemd host that is not DEV
(machine-id and hostname), carries no LILITH authority path, holds none of its own probe units yet, and is given
`--disposable-runner`. It never touches a LILITH unit, credential, socket or path: every unit it starts is a
uniquely named synthetic copy derived from the release unit files (`signer_restart_boundary.derive_probe_units`),
and its credential is a throwaway encrypted with THIS runner's own host key.

    sudo -n /usr/bin/python3 -I -B scripts/probe_signer_restart_boundary.py run --disposable-runner --out <json>

Phases (one run):

- BASELINE: the release directives unchanged. It must REPRODUCE the hazards (a socket-first start is allowed; a
  socket connection starts the service; an exit failure restarts automatically; after an explicit stop the socket
  still reactivates the service). If it cannot, the probe is not discriminating and fails.
- CANDIDATE: the two candidate drop-ins installed byte-exact under the probe names. Each safety property is
  observed, including connection attempts DURING the failure and stop transitions.

Counts are kept apart and never conflated:

- process invocations: lines the synthetic child writes when its Python code runs;
- service exec attempts: distinct systemd invocation IDs of the probe service in the journal window;
- credential decryptions observed: child invocations whose decrypted credential digest equals the throwaway's;
- credential setup failures: journal credential-failure markers. A decryption attempt that fails BEFORE either is
  logged would not be counted: the journal does not independently prove every decryption attempt.

The judgement (`judge`) is pure and fails closed: a missing observation is a FAIL, never a PASS.

    probe PASS on a runner != live proof on DEV;  candidate != accepted configuration
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CEREMONY = ROOT / "services/authority-dev/ceremony"
if str(CEREMONY) not in sys.path:
    sys.path.insert(0, str(CEREMONY))

import signer_restart_boundary as B  # noqa: E402

NAME = "lilith-mb11rb-probe"
USER = "lilith-mb11rb-probe"
SERVICE = NAME + ".service"
SOCKET = NAME + ".socket"
UNIT_DIR = "/etc/systemd/system"
PATHS = B.probe_paths(NAME)
SYSTEMCTL = "/usr/bin/systemctl"
JOURNALCTL = "/usr/bin/journalctl"
SYSTEMD_CREDS = "/usr/bin/systemd-creds"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"}
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
DEV_HOSTNAME = "lilith-dev-01"
# Any of these on the host means it is not a disposable runner: refuse.
REFUSE_IF_PRESENT = ("/opt/lilith-authority-dev", "/etc/lilith-authority-dev", "/etc/lilith-authority-custody",
                     "/var/lib/lilith-authority-custody", "/var/lib/lilith-authority-dev", "/etc/lilith-recovery-witness",
                     "/var/lib/lilith-recovery-witness", "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred",
                     "/etc/systemd/system/lilith-authority-dev.service", "/etc/systemd/system/lilith-authority-dev.socket",
                     "/opt/lilith-memory-broker", "/home/lilith")
RESTART_WAIT = 12.0          # > 2 x RestartSec (5 s): an automatic restart would have happened
HAMMER_AFTER = 7.0           # connection attempts continue this long after the transition
CREDENTIAL_FAILURE_MARKERS = ("Failed to set up credentials", "243/CREDENTIALS")

CHILD = r'''
import hashlib, json, os, socket, sys, time
state = os.environ["STATE_DIRECTORY"]
mode = open("%(control)s").read().strip()
directory = os.environ.get("CREDENTIALS_DIRECTORY")
digest = None
if directory:
    try:
        digest = hashlib.sha256(open(os.path.join(directory, "%(credential)s"), "rb").read()).hexdigest()
    except OSError:
        digest = "UNREADABLE"
record = {"pid": os.getpid(), "invocation": os.environ.get("INVOCATION_ID"), "mode": mode,
          "credentialSha256": digest, "listenFds": os.environ.get("LISTEN_FDS"), "t": time.time()}
with open(os.path.join(state, "invocations.jsonl"), "a") as handle:
    handle.write(json.dumps(record) + "\n")
    handle.flush()
    os.fsync(handle.fileno())
if mode == "exit3":
    sys.exit(3)
listener = socket.socket(fileno=3)
while True:
    conn, _ = listener.accept()
    data = conn.recv(64)
    if data.startswith(b"CRASH"):
        conn.sendall(b"BYE")
        conn.close()
        os._exit(3)
    conn.sendall(b"PONG")
    conn.close()
'''


class Refused(Exception):
    pass


# ------------------------------------------------------------------- safety gate ---

def require_disposable_runner(argv: list[str], *, euid: Callable[[], int] = getattr(os, "geteuid", lambda: -1),
                              exists: Callable[[str], bool] = os.path.lexists,
                              read: Callable[[str], str] = lambda p: Path(p).read_text(encoding="ascii"),
                              hostname: Callable[[], str] = lambda: os.uname().nodename) -> None:
    if "--disposable-runner" not in argv:
        raise Refused("NOT_DECLARED_DISPOSABLE")
    if euid() != 0:
        raise Refused("NOT_ROOT")
    try:
        if read("/proc/1/comm").strip() != "systemd":
            raise Refused("PID1_NOT_SYSTEMD")
        machine_id = read("/etc/machine-id").strip()
    except OSError as exc:
        raise Refused("HOST_FACTS_UNREADABLE") from exc
    if machine_id == DEV_MACHINE_ID or hostname().split(".", 1)[0] == DEV_HOSTNAME:
        raise Refused("DEV_HOST")
    present = [path for path in REFUSE_IF_PRESENT if exists(path)]
    if present:
        raise Refused("LILITH_PATH_PRESENT:" + ",".join(present))
    own = [path for path in (f"{UNIT_DIR}/{SERVICE}", f"{UNIT_DIR}/{SOCKET}", f"{UNIT_DIR}/{SERVICE}.d",
                             f"{UNIT_DIR}/{SOCKET}.d", PATHS["runtime"], f"/etc/{NAME}") if exists(path)]
    if own:
        raise Refused("PROBE_STATE_ALREADY_PRESENT:" + ",".join(own))


# --------------------------------------------------------------------- host ops ---

def run(argv: list[str], *, check: bool = False, timeout: float = 90) -> subprocess.CompletedProcess:
    result = subprocess.run(argv, env=FIXED_ENV, capture_output=True, text=True, timeout=timeout, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"{argv[:3]} rc={result.returncode} {result.stderr.strip()[:300]}")
    return result


def ctl(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    for arg in args:
        if arg.startswith("lilith-") and arg not in (SERVICE, SOCKET):
            raise Refused("NOT_A_PROBE_UNIT:" + arg)            # the probe never names a LILITH unit
    return run([SYSTEMCTL, *args], check=check)


def show(unit: str, *props: str) -> dict[str, str]:
    out = ctl("show", "-p", ",".join(props), "--", unit).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def write(path: str, data: bytes, mode: int) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    os.chmod(path, mode)


def set_mode(mode: str) -> None:
    write(PATHS["control"], mode.encode() + b"\n", 0o644)


def wait_until(predicate: Callable[[], bool], timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()


def active(unit: str) -> str:
    return show(unit, "ActiveState").get("ActiveState", "")


def connect(path: str, payload: bytes = b"PING") -> str:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2.0)
            client.connect(path)
            client.sendall(payload)
            reply = client.recv(16)
            return reply.decode("ascii", "replace") or "CONNECTED_NO_REPLY"
    except FileNotFoundError:
        return "ENOENT"
    except ConnectionRefusedError:
        return "ECONNREFUSED"
    except socket.timeout:
        return "TIMEOUT"
    except OSError as exc:
        return "OSERROR_" + str(exc.errno)


class Hammer:
    """Connection attempts from two threads, continuously, across a transition."""

    def __init__(self, path: str):
        self.path, self.stop_flag, self.results, self.threads = path, threading.Event(), [], []

    def __enter__(self):
        for _ in range(2):
            thread = threading.Thread(target=self._loop, daemon=True)
            thread.start()
            self.threads.append(thread)
        return self

    def _loop(self):
        while not self.stop_flag.is_set():
            self.results.append((time.time(), connect(self.path)))
            time.sleep(0.002)

    def __exit__(self, *exc):
        self.stop_flag.set()
        for thread in self.threads:
            thread.join(5)

    def histogram(self, after: float | None = None) -> dict[str, int]:
        out: dict[str, int] = {}
        for t, outcome in list(self.results):
            if after is None or t >= after:
                out[outcome] = out.get(outcome, 0) + 1
        return out


# --------------------------------------------------------------------- windows ---

class Window:
    """One observation window: exec attempts, process invocations, decryptions and credential failures."""

    def __init__(self, expected_credential: str):
        self.expected = expected_credential
        run([JOURNALCTL, "--sync"])
        self.t0 = time.time()
        self.usec0 = int(self.t0 * 1_000_000)

    def counts(self) -> dict[str, Any]:
        run([JOURNALCTL, "--sync"])
        out = run([JOURNALCTL, "-u", SERVICE, "-o", "json", "--no-pager", "--since", f"@{int(self.t0) - 1}"]).stdout
        invocations, failures = set(), 0
        for line in out.splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if int(entry.get("__REALTIME_TIMESTAMP", "0")) < self.usec0:
                continue
            invocation = entry.get("_SYSTEMD_INVOCATION_ID") or entry.get("INVOCATION_ID")
            if invocation:
                invocations.add(invocation)
            message = entry.get("MESSAGE") if isinstance(entry.get("MESSAGE"), str) else ""
            if any(marker in message for marker in CREDENTIAL_FAILURE_MARKERS):
                failures += 1
        records = []
        log = Path(f"/var/lib/{PATHS['state']}/invocations.jsonl")
        if log.exists():
            records = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
        records = [r for r in records if r["t"] >= self.t0]
        return {"serviceExecAttempts": len(invocations), "invocationIds": sorted(invocations),
                "processInvocations": len(records),
                "credentialDecryptionsObserved": sum(1 for r in records if r["credentialSha256"] == self.expected),
                "credentialSetupFailures": failures,
                "processInvocationIds": [r["invocation"] for r in records]}


# ---------------------------------------------------------------------- phases ---

def install_units() -> dict:
    service_text = (ROOT / "services/authority-dev/deploy/lilith-authority-dev.service").read_text(encoding="utf-8")
    socket_text = (ROOT / "services/authority-dev/deploy/lilith-authority-dev.socket").read_text(encoding="utf-8")
    service, sock, report = B.derive_probe_units(service_text, socket_text, NAME, USER)
    run(["/usr/sbin/useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin", USER], check=True)
    os.makedirs(PATHS["runtime"], mode=0o700, exist_ok=True)               # the tmpfiles `d ... 0700 root root`
    write(PATHS["child"], (CHILD % {"control": PATHS["control"], "credential": B.CREDENTIAL_NAME}).encode(), 0o644)
    os.chmod(os.path.dirname(PATHS["child"]), 0o755)
    write(f"{UNIT_DIR}/{SERVICE}", service.encode(), 0o644)
    write(f"{UNIT_DIR}/{SOCKET}", sock.encode(), 0o644)
    return {"derivation": report, "serviceText": service, "socketText": sock}


def make_credential() -> tuple[str, bytes]:
    run([SYSTEMD_CREDS, "setup"])                                          # this runner's own host key
    plain = os.urandom(48)
    scratch = f"/run/{NAME}-plain"
    write(scratch, plain, 0o600)
    try:
        run([SYSTEMD_CREDS, "encrypt", "--with-key=host", f"--name={B.CREDENTIAL_NAME}", scratch,
             PATHS["credential"]], check=True)
    finally:
        os.unlink(scratch)
    os.chmod(PATHS["credential"], 0o600)
    return B.sha256(plain), Path(PATHS["credential"]).read_bytes()


def reset() -> None:
    ctl("stop", SERVICE, SOCKET)
    ctl("reset-failed", SERVICE, SOCKET)


def state_facts() -> dict:
    service = show(SERVICE, "ActiveState", "SubState", "Result", "NRestarts", "InvocationID", "MainPID")
    sock = show(SOCKET, "ActiveState", "SubState", "Result")
    return {"service": service, "socket": sock, "socketPathExists": os.path.lexists(PATHS["socket"])}


def baseline(expected: str) -> dict:
    out: dict[str, Any] = {}
    reset()
    set_mode("serve")
    w = Window(expected)
    started = ctl("start", SOCKET)
    listening = wait_until(lambda: active(SOCKET) == "active", 5)
    reply = connect(PATHS["socket"])
    wait_until(lambda: active(SERVICE) == "active", 5)
    out["socketFirst"] = {"rc": started.returncode, "socketActive": listening, "reply": reply,
                          "serviceActiveAfterConnect": active(SERVICE), "counts": w.counts()}
    reset()
    set_mode("exit3")
    w = Window(expected)
    ctl("start", SERVICE)
    time.sleep(RESTART_WAIT + 4)
    out["exitFailure"] = {"facts": state_facts(), "counts": w.counts()}
    reset()
    set_mode("serve")
    ctl("start", SERVICE)
    wait_until(lambda: active(SERVICE) == "active", 5)
    ctl("stop", SERVICE)
    wait_until(lambda: active(SERVICE) != "active", 5)
    w = Window(expected)
    socket_after_stop = active(SOCKET)
    reply = connect(PATHS["socket"])
    wait_until(lambda: active(SERVICE) == "active", 5)
    out["afterStop"] = {"socketActiveAfterStop": socket_after_stop, "reply": reply,
                        "serviceActiveAfterConnect": active(SERVICE), "counts": w.counts()}
    reset()
    out["dropInPathsBefore"] = {SERVICE: show(SERVICE, "DropInPaths").get("DropInPaths", ""),
                                SOCKET: show(SOCKET, "DropInPaths").get("DropInPaths", "")}
    return out


def read_dropins(unit: str) -> tuple[dict[str, str], dict[str, bytes]]:
    facts = show(unit, *B.SHOW_PROPERTIES[B.SERVICE_UNIT if unit == SERVICE else B.SOCKET_UNIT])
    data = {}
    for path in facts.get("DropInPaths", "").split():
        try:
            data[path] = Path(path).read_bytes()
        except OSError:
            pass
    return facts, data


def effective(preexisting: dict[str, list[str]]) -> dict:
    out = {}
    for real, probe in ((B.SERVICE_UNIT, SERVICE), (B.SOCKET_UNIT, SOCKET)):
        facts, data = read_dropins(probe)
        out[probe] = {"show": facts, "reasons": B.check_effective(real, facts, data, probe_unit=probe,
                                                                  preexisting=preexisting[probe])}
    return out


def candidate(expected: str, credential: bytes, preexisting: dict[str, list[str]]) -> dict:
    out: dict[str, Any] = {}
    for real, probe in ((B.SERVICE_UNIT, SERVICE), (B.SOCKET_UNIT, SOCKET)):
        name, _pin = B.DROPINS[real]
        write(f"{UNIT_DIR}/{probe}.d/{name}", B.candidate_bytes(real), 0o644)
        os.chmod(f"{UNIT_DIR}/{probe}.d", 0o755)
    ctl("daemon-reload", check=True)
    reset()
    out["effective"] = effective(preexisting)

    # socket-first is refused
    w = Window(expected)
    refused = ctl("start", SOCKET)
    time.sleep(1)
    out["socketFirst"] = {"rc": refused.returncode, "stderr": refused.stderr.strip()[:200], "facts": state_facts(),
                          "reply": connect(PATHS["socket"]), "counts": w.counts()}

    # a normal explicit start, then a crash with connection attempts across the transition
    reset()
    set_mode("serve")
    w = Window(expected)
    start = ctl("start", SERVICE)
    up = wait_until(lambda: active(SERVICE) == "active" and active(SOCKET) == "active", 10)
    deps = show(SERVICE, "Requires", "TriggeredBy")
    out["normalStart"] = {"rc": start.returncode, "up": up, "facts": state_facts(), "dependencies": deps,
                          "reply": connect(PATHS["socket"]), "counts": w.counts()}
    w = Window(expected)
    with Hammer(PATHS["socket"]) as hammer:
        time.sleep(0.5)
        crash_at = time.time()
        crash_reply = connect(PATHS["socket"], b"CRASH")
        time.sleep(HAMMER_AFTER)
    time.sleep(2)
    out["crash"] = {"crashReply": crash_reply, "facts": state_facts(), "counts": w.counts(),
                    "connectsAfterCrash": hammer.histogram(after=crash_at + 0.5),
                    "connectsTotal": hammer.histogram(), "replyAfter": connect(PATHS["socket"])}

    # an exit failure at start does not restart
    reset()
    set_mode("exit3")
    w = Window(expected)
    ctl("start", SERVICE)
    time.sleep(RESTART_WAIT)
    out["exitFailure"] = {"facts": state_facts(), "counts": w.counts(), "reply": connect(PATHS["socket"])}

    # a credential decryption failure is attempted once
    reset()
    set_mode("serve")
    corrupt = credential[:-1] + bytes([credential[-1] ^ 0xFF])
    write(PATHS["credential"], corrupt, 0o600)
    w = Window(expected)
    ctl("start", SERVICE)
    time.sleep(RESTART_WAIT)
    out["credentialFailure"] = {"facts": state_facts(), "counts": w.counts(), "reply": connect(PATHS["socket"])}
    write(PATHS["credential"], credential, 0o600)

    # an explicit stop with connection attempts across the transition
    reset()
    set_mode("serve")
    ctl("start", SERVICE)
    wait_until(lambda: active(SERVICE) == "active", 10)
    w = Window(expected)
    with Hammer(PATHS["socket"]) as hammer:
        time.sleep(0.5)
        stop_at = time.time()
        stopped = ctl("stop", SERVICE)
        time.sleep(HAMMER_AFTER)
    time.sleep(2)
    out["explicitStop"] = {"rc": stopped.returncode, "facts": state_facts(), "counts": w.counts(),
                           "connectsAfterStop": hammer.histogram(after=stop_at + 1.0),
                           "replyAfter": connect(PATHS["socket"])}

    # daemon-reload: stopped, then running
    reset()
    w = Window(expected)
    ctl("daemon-reload", check=True)
    time.sleep(3)
    out["reloadStopped"] = {"facts": state_facts(), "counts": w.counts()}
    ctl("start", SERVICE)
    wait_until(lambda: active(SERVICE) == "active", 10)
    before = show(SERVICE, "InvocationID", "MainPID")
    w = Window(expected)
    ctl("daemon-reload", check=True)
    time.sleep(3)
    out["reloadRunning"] = {"before": before, "after": show(SERVICE, "InvocationID", "MainPID"),
                            "facts": state_facts(), "counts": w.counts()}

    # reboot-style: the manager re-executes and re-reads every unit; nothing starts, nothing reverts
    reset()
    w = Window(expected)
    ctl("daemon-reexec", check=True)
    wait_until(lambda: show(SERVICE, "LoadState").get("LoadState") == "loaded", 30)
    time.sleep(2)
    out["reexec"] = {"effective": effective(preexisting), "facts": state_facts(), "counts": w.counts(),
                     "socketFirstRc": ctl("start", SOCKET).returncode,
                     "unitFileStates": {SERVICE: show(SERVICE, "UnitFileState").get("UnitFileState"),
                                        SOCKET: show(SOCKET, "UnitFileState").get("UnitFileState")}}
    reset()

    # foreign or altered drop-ins are never accepted
    foreign = {}
    service_name, _ = B.DROPINS[B.SERVICE_UNIT]
    socket_name, _ = B.DROPINS[B.SOCKET_UNIT]
    cases = {
        "foreignServiceRestartAlways": (f"{UNIT_DIR}/{SERVICE}.d/20-foreign.conf", b"[Service]\nRestart=always\n"),
        "foreignSocketManualStart": (f"{UNIT_DIR}/{SOCKET}.d/20-foreign.conf", b"[Unit]\nRefuseManualStart=no\n"),
        "alteredCandidateBytes": (f"{UNIT_DIR}/{SERVICE}.d/{service_name}", b"[Service]\nRestart=no\n"),
    }
    for label, (path, data) in cases.items():
        original = Path(path).read_bytes() if os.path.exists(path) else None
        write(path, data, 0o644)
        ctl("daemon-reload", check=True)
        foreign[label] = effective(preexisting)
        if original is None:
            os.unlink(path)
        else:
            write(path, original, 0o644)
        ctl("daemon-reload", check=True)
    foreign["restored"] = effective(preexisting)
    out["foreign"] = foreign
    out["socketDropInName"] = socket_name
    return out


def cleanup() -> dict:
    reset()
    for path in (f"{UNIT_DIR}/{SERVICE}", f"{UNIT_DIR}/{SOCKET}"):
        if os.path.exists(path):
            os.unlink(path)
    for directory in (f"{UNIT_DIR}/{SERVICE}.d", f"{UNIT_DIR}/{SOCKET}.d"):
        if os.path.isdir(directory):
            for entry in os.listdir(directory):
                os.unlink(os.path.join(directory, entry))
            os.rmdir(directory)
    ctl("daemon-reload")
    return {"unitsRemoved": not os.path.exists(f"{UNIT_DIR}/{SERVICE}")}


def observe() -> dict:
    observations: dict[str, Any] = {"probe": NAME, "systemd": run([SYSTEMCTL, "--version"]).stdout.splitlines()[:1]}
    observations["units"] = install_units()
    expected, credential = make_credential()
    observations["credential"] = {"plaintextSha256": expected, "encryptedSha256": B.sha256(credential),
                                  "key": "this runner's host key (systemd-creds --with-key=host)"}
    ctl("daemon-reload", check=True)
    try:
        observations["baseline"] = baseline(expected)
        before = observations["baseline"]["dropInPathsBefore"]
        preexisting = {unit: before[unit].split() for unit in (SERVICE, SOCKET)}
        observations["candidate"] = candidate(expected, credential, preexisting)
    finally:
        observations["cleanup"] = cleanup()
    return observations


# ------------------------------------------------------------------- judgement ---

def _get(obj: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if not isinstance(obj, dict) or key not in obj:
            return default
        obj = obj[key]
    return obj


def judge(obs: dict) -> list[dict]:
    """Pure, fail-closed judgement. Every check is (id, pass, detail); a missing observation fails."""
    checks: list[dict] = []

    def check(check_id: str, ok: bool, detail: Any) -> None:
        checks.append({"id": check_id, "pass": bool(ok), "detail": detail})

    b, c = obs.get("baseline") or {}, obs.get("candidate") or {}
    # baseline: the hazards must be reproduced, or the probe is not discriminating
    check("BASELINE_SOCKET_FIRST_START_ALLOWED", _get(b, "socketFirst", "rc") == 0
          and _get(b, "socketFirst", "socketActive") is True, _get(b, "socketFirst"))
    check("BASELINE_SOCKET_CONNECTION_STARTS_SERVICE",
          (_get(b, "socketFirst", "counts", "serviceExecAttempts") or 0) >= 1
          and _get(b, "socketFirst", "reply") == "PONG", _get(b, "socketFirst", "counts"))
    check("BASELINE_EXIT_FAILURE_RESTARTS_AUTOMATICALLY",
          (_get(b, "exitFailure", "counts", "serviceExecAttempts") or 0) >= 2, _get(b, "exitFailure"))
    check("BASELINE_SOCKET_REACTIVATES_AFTER_STOP", _get(b, "afterStop", "socketActiveAfterStop") == "active"
          and _get(b, "afterStop", "reply") == "PONG"
          and (_get(b, "afterStop", "counts", "serviceExecAttempts") or 0) >= 1, _get(b, "afterStop"))

    # candidate: the safety properties
    for unit in (SERVICE, SOCKET):
        check(f"EFFECTIVE_EXACT:{unit}", _get(c, "effective", unit, "reasons") == [],
              _get(c, "effective", unit))
    sf = _get(c, "socketFirst") or {}
    check("SOCKET_FIRST_START_REFUSED", sf.get("rc") not in (None, 0)
          and _get(sf, "facts", "socket", "ActiveState") in ("inactive", "failed")
          and _get(sf, "counts", "serviceExecAttempts") == 0 and sf.get("reply") in ("ENOENT", "ECONNREFUSED"), sf)
    ns = _get(c, "normalStart") or {}
    check("NORMAL_START_ONE_LOAD_WITH_SOCKET", ns.get("rc") == 0 and ns.get("up") is True
          and ns.get("reply") == "PONG" and SOCKET in (_get(ns, "dependencies", "Requires") or "")
          and _get(ns, "counts", "serviceExecAttempts") == 1 and _get(ns, "counts", "processInvocations") == 1
          and _get(ns, "counts", "credentialDecryptionsObserved") == 1, ns)
    cr = _get(c, "crash") or {}
    check("CRASH_NO_RESTART_NO_REACTIVATION", cr.get("crashReply") == "BYE"
          and _get(cr, "facts", "service", "ActiveState") in ("failed", "inactive")
          and _get(cr, "facts", "service", "NRestarts") == "0"
          and _get(cr, "facts", "socket", "ActiveState") in ("inactive", "failed")
          and _get(cr, "facts", "socketPathExists") is False
          and _get(cr, "counts", "serviceExecAttempts") == 0 and _get(cr, "counts", "processInvocations") == 0
          and "PONG" not in (cr.get("connectsAfterCrash") or {"PONG": 1})
          and cr.get("replyAfter") in ("ENOENT", "ECONNREFUSED"), cr)
    ef = _get(c, "exitFailure") or {}
    check("EXIT_FAILURE_NO_AUTOMATIC_RESTART", _get(ef, "counts", "serviceExecAttempts") == 1
          and _get(ef, "counts", "processInvocations") == 1 and _get(ef, "facts", "service", "NRestarts") == "0"
          and _get(ef, "facts", "socket", "ActiveState") in ("inactive", "failed")
          and _get(ef, "facts", "socketPathExists") is False and ef.get("reply") in ("ENOENT", "ECONNREFUSED"), ef)
    cf = _get(c, "credentialFailure") or {}
    check("CREDENTIAL_FAILURE_ATTEMPTED_ONCE", _get(cf, "counts", "serviceExecAttempts") == 1
          and _get(cf, "counts", "processInvocations") == 0
          and (_get(cf, "counts", "credentialSetupFailures") or 0) >= 1
          and _get(cf, "facts", "service", "NRestarts") == "0"
          and _get(cf, "facts", "socket", "ActiveState") in ("inactive", "failed")
          and cf.get("reply") in ("ENOENT", "ECONNREFUSED"), cf)
    es = _get(c, "explicitStop") or {}
    check("EXPLICIT_STOP_LEAVES_NO_ACTIVATION_ROUTE", es.get("rc") == 0
          and _get(es, "facts", "service", "ActiveState") == "inactive"
          and _get(es, "facts", "socket", "ActiveState") == "inactive"
          and _get(es, "facts", "socketPathExists") is False
          and _get(es, "counts", "serviceExecAttempts") == 0 and _get(es, "counts", "processInvocations") == 0
          and "PONG" not in (es.get("connectsAfterStop") or {"PONG": 1})
          and es.get("replyAfter") in ("ENOENT", "ECONNREFUSED"), es)
    rs = _get(c, "reloadStopped") or {}
    check("DAEMON_RELOAD_STARTS_NOTHING", _get(rs, "counts", "serviceExecAttempts") == 0
          and _get(rs, "facts", "service", "ActiveState") == "inactive"
          and _get(rs, "facts", "socket", "ActiveState") == "inactive", rs)
    rr = _get(c, "reloadRunning") or {}
    check("DAEMON_RELOAD_DOES_NOT_RESTART_A_RUNNING_SIGNER", rr.get("before") == rr.get("after")
          and bool(_get(rr, "before", "InvocationID")) and _get(rr, "counts", "serviceExecAttempts") == 0, rr)
    rx = _get(c, "reexec") or {}
    check("REEXEC_KEEPS_THE_BOUNDARY_AND_STARTS_NOTHING",
          all(_get(rx, "effective", unit, "reasons") == [] for unit in (SERVICE, SOCKET))
          and _get(rx, "counts", "serviceExecAttempts") == 0 and rx.get("socketFirstRc") not in (None, 0)
          and _get(rx, "facts", "service", "ActiveState") == "inactive"
          and set((rx.get("unitFileStates") or {"x": "enabled"}).values()) <= {"static", ""}, rx)
    fo = _get(c, "foreign") or {}
    for label, reason in (("foreignServiceRestartAlways", "DROPIN_SET_NOT_EXACT"),
                          ("foreignSocketManualStart", "DROPIN_SET_NOT_EXACT"),
                          ("alteredCandidateBytes", "CANDIDATE_DROPIN_BYTES_NOT_PINNED")):
        unit = SOCKET if "Socket" in label else SERVICE
        reasons = _get(fo, label, unit, "reasons")
        check(f"FOREIGN_OR_ALTERED_DROPIN_REFUSED:{label}", isinstance(reasons, list) and reason in reasons,
              _get(fo, label))
    check("RESTORED_CANDIDATE_EXACT", all(_get(fo, "restored", unit, "reasons") == [] for unit in (SERVICE, SOCKET)),
          _get(fo, "restored"))
    check("CLEANUP", _get(obs, "cleanup", "unitsRemoved") is True, obs.get("cleanup"))
    return checks


def main(argv: list[str]) -> int:
    if len(argv) < 1 or argv[0] != "run" or "--out" not in argv:
        print("probe_signer_restart_boundary: REFUSED USAGE", file=sys.stderr)
        return 2
    out = Path(argv[argv.index("--out") + 1])
    try:
        require_disposable_runner(argv)
    except Refused as exc:
        print(f"probe_signer_restart_boundary: REFUSED {exc}", file=sys.stderr)
        return 2
    try:
        observations = observe()
    except Exception as exc:  # noqa: BLE001 - any probe error is a FAIL, never a PASS
        observations = {"error": f"{type(exc).__name__}: {exc}"}
        print(f"ERROR {observations['error']}")
    checks = judge(observations)
    verdict = "PASS" if checks and all(item["pass"] for item in checks) else "FAIL"
    result = {"resultType": "LILITH_MB11_RESTART_BOUNDARY_PROBE", "schemaVersion": 1, "verdict": verdict,
              "checks": checks, "observations": observations, "candidateAccepted": False, "liveProof": False}
    out.write_text(json.dumps(result, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
    for item in checks:
        print(f"{'PASS' if item['pass'] else 'FAIL'} {item['id']}")
    print(f"MB11_RESTART_BOUNDARY_PROBE={verdict}")
    if verdict != "PASS":
        for item in checks:
            if not item["pass"]:
                print(f"DETAIL {item['id']}: {json.dumps(item['detail'], sort_keys=True, default=str)[:1500]}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
