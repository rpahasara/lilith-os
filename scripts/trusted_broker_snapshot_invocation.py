"""Fixed root-side sudo observation and confined DEV snapshot invocation."""

from __future__ import annotations

import base64
import json
import os
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path


CONTROL = Path("/opt/lilith-trusted-controls/broker-snapshot")
TOOL = "/opt/lilith-trusted-controls/broker-snapshot/current/bin/lilith-broker-dev-snapshot"
INVOKER = "/opt/lilith-trusted-controls/broker-snapshot/current/bin/lilith-broker-dev-invocation"
OPERATION = "SNAPSHOT_ACCEPTED_STAGE2"
SUDO_ENV = "LILITH_TRUSTED_SUDO_OBSERVATION_V1"
SUDO_SCHEMA = "TrustedSudoPrivilegeObservationV1"
SUDO_ACCOUNTS = ("lilith-memory-broker", "lilith-memory-relay")
MAX_SUDO_TEXT = 4096
MAX_SUDO_EVIDENCE = 16384
PROPERTIES = (
    "ProtectSystem=strict",
    "ProtectHome=read-only",
    "NoNewPrivileges=yes",
    "CapabilityBoundingSet=CAP_DAC_READ_SEARCH",
    "AmbientCapabilities=CAP_DAC_READ_SEARCH",
    "PrivateTmp=yes",
    "PrivateDevices=yes",
    "ProtectKernelTunables=yes",
    "ProtectKernelModules=yes",
    "ProtectControlGroups=yes",
    "ReadOnlyPaths=/run",
)


class InvocationError(RuntimeError):
    pass


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def observe_sudo() -> str:
    """Run exactly two fixed read-only policy queries before sandbox creation."""
    if os.name != "posix" or os.geteuid() != 0:
        raise InvocationError("SNAPSHOT_INVOCATION_ROOT_REQUIRED")
    accounts = []
    for name in SUDO_ACCOUNTS:
        argv = ("/usr/bin/sudo", "-n", "-l", "-U", name)
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InvocationError("SNAPSHOT_SUDO_OBSERVATION_FAILED:" + name) from exc
        if len(result.stdout) > MAX_SUDO_TEXT or len(result.stderr) > MAX_SUDO_TEXT or \
                not -255 <= result.returncode <= 255:
            raise InvocationError("SNAPSHOT_SUDO_OBSERVATION_BOUNDS:" + name)
        try:
            stdout = result.stdout.decode("utf-8", "strict")
            stderr = result.stderr.decode("utf-8", "strict")
        except UnicodeError as exc:
            raise InvocationError("SNAPSHOT_SUDO_OBSERVATION_ENCODING:" + name) from exc
        accounts.append({"account": name, "argv": list(argv), "returncode": result.returncode,
                         "stdout": stdout, "stderr": stderr})
    raw = canonical({"schema": SUDO_SCHEMA, "accounts": accounts})
    if len(raw) > MAX_SUDO_EVIDENCE:
        raise InvocationError("SNAPSHOT_SUDO_OBSERVATION_TOTAL_BOUNDS")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def command(encoded_observation: str) -> tuple[str, ...]:
    """No caller-selected executable, profile, path, unit, or environment."""
    if not isinstance(encoded_observation, str) or not encoded_observation or \
            len(encoded_observation) > MAX_SUDO_EVIDENCE * 2 or \
            re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", encoded_observation) is None:
        raise InvocationError("SNAPSHOT_SUDO_OBSERVATION_TRANSPORT")
    return (
        "/usr/bin/systemd-run", "--pipe", "--wait", "--collect", "--quiet",
        *("--property=" + value for value in PROPERTIES),
        "--setenv=" + SUDO_ENV + "=" + encoded_observation,
        "--", "/usr/bin/python3", "-I", "-B", TOOL, OPERATION,
    )


def ssh_command() -> str:
    return shlex.join(("/usr/bin/sudo", "-n", "/usr/bin/python3", "-I", "-B", INVOKER))


def _selected_invoker() -> None:
    selector = CONTROL / "current"
    info = selector.lstat()
    if not stat.S_ISLNK(info.st_mode) or (info.st_uid, info.st_gid) != (0, 0):
        raise InvocationError("SNAPSHOT_INVOKER_NOT_SELECTED")
    target = os.readlink(selector)
    if not re.fullmatch(r"releases/[0-9a-f]{64}", target) or \
            Path(__file__).resolve() != CONTROL / target / "bin/lilith-broker-dev-invocation":
        raise InvocationError("SNAPSHOT_INVOKER_NOT_SELECTED")


def run() -> subprocess.CompletedProcess:
    _selected_invoker()
    encoded = observe_sudo()
    try:
        result = subprocess.run(command(encoded), stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InvocationError("SNAPSHOT_CONFINED_INVOCATION_FAILED") from exc
    if len(result.stdout) > 3 * 1024 * 1024 or len(result.stderr) > 4096:
        raise InvocationError("SNAPSHOT_CONFINED_INVOCATION_BOUNDS")
    return result


def main() -> None:
    if sys.argv[1:]:
        raise InvocationError("SNAPSHOT_INVOCATION_NO_ARGUMENTS")
    result = run()
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
