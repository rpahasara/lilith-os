"""TEST-ONLY driver: runs the real executor (fresh interpreter, real pinned Core API import) with a fake systemd /
journald host and an optional SIGKILL-equivalent fault point. Never part of the package.

    python3.11 -I -B executor_driver.py <bin dir> <config> <fault point or ''> <host state json>
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BIN, CONFIG, FAULT, HOST = sys.argv[1:5]
sys.path.insert(0, BIN)
import hermes_forget_executor as X  # noqa: E402


class FakeHost(X.Host):
    def _state(self):
        return json.loads(Path(HOST).read_text())

    def _save(self, state):
        Path(HOST).write_text(json.dumps(state))

    def unit_active(self, unit):
        return bool(self._state().get("gatewayActive", False))

    def stop_unit(self, unit):
        state = self._state()
        state["stopCalls"] = state.get("stopCalls", 0) + 1
        if not state.get("refuseStop"):
            state["gatewayActive"] = False
        self._save(state)

    def gateway_process_present(self, hermes_home):
        return bool(self._state().get("processPresent", False))

    def port_open(self, port):
        return bool(self._state().get("portOpen", False))

    def journal(self, namespace, *args):
        state = self._state()
        state.setdefault("journalCalls", []).append(list(args))
        failing = state.get("journalFail")
        if failing and failing in args[0]:
            self._save(state)
            return subprocess.CompletedProcess(args, 1, b"", b"")
        if args[0].startswith("--vacuum-time") and not state.get("journalStuck"):
            state["journalEntries"] = 0             # journalStuck: vacuum "succeeds" but old entries remain
        self._save(state)
        return subprocess.CompletedProcess(args, 0, b"", b"")

    def journal_entries_until(self, namespace, until_usec):
        return int(self._state().get("journalEntries", 0))


def fault(point):
    if FAULT and point == FAULT:
        os._exit(137)                       # as abrupt as SIGKILL: no cleanup, no finally blocks
    if FAULT == "raise:" + point:           # the exact error SQLite raises when the disk is full
        import sqlite3
        raise sqlite3.OperationalError("database or disk is full")


cfg = X.Config.load(Path(CONFIG))
if FAULT.startswith("reconcile"):                     # "reconcile" or "reconcile:<fault point>"
    FAULT = FAULT.partition(":")[2]
    sys.exit(X.Executor(cfg, FakeHost(), fault=fault).run_reconcile())
sys.exit(X.Executor(cfg, FakeHost(), fault=fault).run())
