"""Closed transient read-only execution policy for the DEV snapshot tool."""

from __future__ import annotations

import shlex


TOOL = "/opt/lilith-trusted-controls/broker-snapshot/current/bin/lilith-broker-dev-snapshot"
OPERATION = "SNAPSHOT_ACCEPTED_STAGE2"
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


def command() -> tuple[str, ...]:
    """No caller-selected executable, profile, path, unit, or environment."""
    return (
        "/usr/bin/systemd-run", "--pipe", "--wait", "--collect", "--quiet",
        *("--property=" + value for value in PROPERTIES),
        "--", "/usr/bin/python3", "-I", "-B", TOOL, OPERATION,
    )


def ssh_command() -> str:
    return shlex.join(("/usr/bin/sudo", "-n", *command()))
