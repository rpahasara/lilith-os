"""MIRROR-ONLY stand-in for the Hermes gateway (never installed on DEV). Runs as lilith in the real gateway sandbox
plus the real F9-C drop-in. Its argv contains "-m hermes_cli.main gateway run" so the executor's gateway-process check
sees it exactly like Hermes. It (1) probes, from inside the sandbox, whether the erasure spool, state, receipts,
epochs and executor config are visible (they must not be: T6), (2) writes canary log lines into HERMES_HOME and its
journald namespace, and (3) serves 127.0.0.1:9901 until stopped."""

import http.server
import os
import sys
from pathlib import Path

CANARY = "F9C-MIRROR-CANARY"
HOME = Path(os.environ.get("HERMES_HOME", "/home/lilith/.hermes-dev"))


def probe(path: str, write: bool = False) -> str:
    try:
        if write:
            with open(os.path.join(path, "gateway-probe.req"), "w") as fh:
                fh.write("{}")
            return "WRITABLE"
        os.listdir(path) if os.path.isdir(path) else open(path).close()
        return "VISIBLE"
    except FileNotFoundError:
        return "ABSENT"
    except PermissionError:
        return "DENIED"
    except OSError as exc:
        return "ERR" + str(exc.errno)


results = {
    "spool_list": probe("/run/hermes-forget/spool"),
    "spool_write": probe("/run/hermes-forget/spool", write=True),
    "state": probe("/var/lib/hermes-forget/state"),
    "receipts": probe("/var/lib/hermes-forget/receipts"),
    "epochs": probe("/var/lib/hermes-forget/epochs"),
    "config": probe("/etc/hermes-forget/executor.json"),
    "privacy_db": probe("/home/lilith/.hermes/lilith-os-dev/data/privacy_governance.dev.db"),
}
print("PROBE " + " ".join(f"{k}={v}" for k, v in sorted(results.items())), flush=True)
# Conversation content only while the fixture's state/canary-on exists: the erasure purges state/, so a gateway
# restarted after a FORGET writes none and the host-wide canary scan stays meaningful.
if (HOME / "state" / "canary-on").exists():
    (HOME / "logs").mkdir(exist_ok=True)
    with open(HOME / "logs" / "gateway.log", "a") as fh:
        fh.write(f"stand-in started {CANARY}\n")
    print(f"stand-in inbound message {CANARY}", flush=True)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


if __name__ == "__main__" or True:
    del sys.argv[1:]
    http.server.HTTPServer(("127.0.0.1", 9901), Handler).serve_forever()
