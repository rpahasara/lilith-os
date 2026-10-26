"""First Memory root bridge: the privilege boundary between the unprivileged conversation host and the root-only
signer socket (TEST_ONLY; POSIX; the identity tests need root and use the system `nobody` account).

1. a dropped host can never regain uid 0 (real, effective and saved ids; no supplementary groups);
2. code a non-root principal can change is never run by the bridge, and the bridge never imports host code;
3. malformed, unexpected or authority-bearing requests are refused before anything reaches the signer;
4. the bridge supplies root's own genuine hold-store snapshot, never the caller's.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/owner-memory-control/tools", ROOT / "services/owner-memory-control/tests",
              ROOT / "services/owner-memory-control", ROOT / "services/core-api", ROOT / "services/authority-dev", HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pr1s_fixtures as X  # noqa: E402

if X.POSIX:
    import first_memory_dev_host as HOST  # noqa: E402
    import test_rr39_issuance as RR39  # noqa: E402
    from lilith_authority_dev import protocol as W  # noqa: E402
    from lilith_authority_root import cli as ROOT_CLI  # noqa: E402

AS_ROOT = X.POSIX and os.geteuid() == 0
# Execution tests need a base whose whole parent chain is root-owned and not writable by others (never /tmp).
TRUSTED_BASE = "/opt"
CAN_EXECUTE = (AS_ROOT and os.path.isdir(TRUSTED_BASE) and os.stat(TRUSTED_BASE).st_uid == 0
               and not os.stat(TRUSTED_BASE).st_mode & 0o022)
UNPRIVILEGED = "nobody"


def frame(value) -> bytes:
    body = value if isinstance(value, bytes) else json.dumps(value).encode()
    return struct.pack(">I", len(body)) + body


def trusted_tree(base: Path) -> Path:
    tree = base / "host-tree"
    (tree / "services/owner-memory-control/tools").mkdir(parents=True)
    for path in [tree, *tree.rglob("*")]:
        os.chmod(path, 0o755)
    return tree


@unittest.skipUnless(X.POSIX, "POSIX identities and modes")
class BridgeRequestTests(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.hold = {"root": "genuine"}

    def exchange(self, signer_frame):
        message = W.parse_frame(signer_frame)
        self.sent.append(message)
        return {"status": "OK", "operation": message.operation}

    def request(self, value):
        raw = value if isinstance(value, bytes) else json.dumps(value).encode()
        return ROOT_CLI.bridge_request(raw, hold_snapshot=lambda: dict(self.hold), exchange=self.exchange)

    def use_payload(self, **extra):
        return {"evidenceId": "aev.x", "evidenceDigest": "0" * 64, "challengeId": "och.x", "proposalRefId": "p.x",
                "actionDigest": "1" * 64, **extra}

    def test_malformed_unexpected_or_authority_bearing_requests_are_refused(self):
        cases = [
            b"\xff\xfe", b"not json", b"[]", json.dumps({"operation": "HEALTH"}).encode(),
            {"operation": W.HEALTH, "payload": {}},
            {"operation": W.RECOVERY_VOID_CHALLENGE, "payload": {}},
            {"operation": W.RECOVERY_ADVANCE_EPOCH, "payload": {"epochAuthorization": {}}},
            {"operation": "SIGN", "payload": {}},
            {"operation": W.RESERVE_EVIDENCE_USE, "payload": self.use_payload(holdStore={"forged": True})},
            {"operation": W.ISSUE_OWNER_EVIDENCE, "payload": {"holdStore": {}}},
            {"operation": W.ISSUE_OWNER_EVIDENCE, "payload": {"challengeId": "och.x"}},          # legacy / partial
            {"operation": W.RESERVE_EVIDENCE_USE, "payload": self.use_payload(evidenceDigest="zz")},
            {"operation": W.LOOKUP_EVIDENCE_USE, "payload": {"evidenceId": "aev.x", "path": "/etc/shadow"}},
            {"operation": W.LOOKUP_EVIDENCE_USE, "payload": {"evidenceId": "aev.x"}, "command": "id"},
            b'{"operation":"LOOKUP_EVIDENCE_USE","operation":"HEALTH","payload":{}}',          # duplicate key
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.request(case), ROOT_CLI.BRIDGE_REFUSAL)
        self.assertEqual(self.sent, [])                                     # nothing reached the signer

    def test_only_issue_and_evidence_use_are_forwarded(self):
        self.assertEqual(ROOT_CLI.BRIDGE_OPERATIONS, {W.ISSUE_OWNER_EVIDENCE, W.RESERVE_EVIDENCE_USE,
                                                      W.CONFIRM_EVIDENCE_USE, W.ABANDON_EVIDENCE_USE,
                                                      W.LOOKUP_EVIDENCE_USE})
        self.assertEqual(self.request({"operation": W.LOOKUP_EVIDENCE_USE, "payload": {"evidenceId": "aev.x"}})
                         ["operation"], W.LOOKUP_EVIDENCE_USE)
        self.assertNotIn("holdStore", self.sent[-1].payload)                # a read carries no snapshot

    def test_writes_carry_roots_own_hold_snapshot(self):
        self.request({"operation": W.RESERVE_EVIDENCE_USE, "payload": self.use_payload()})
        self.assertEqual(self.sent[-1].payload["holdStore"], {"root": "genuine"})
        self.hold = {"root": "changed"}                                     # read fresh, per request
        self.request({"operation": W.ABANDON_EVIDENCE_USE,
                      "payload": {"evidenceId": "aev.x", "proposalRefId": "p.x"}})
        self.assertEqual(self.sent[-1].payload["holdStore"], {"root": "changed"})

    def test_the_snapshot_is_the_genuine_root_hold_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            host = RR39.DevHost(Path(tmp) / "host").genesis_host()           # a real HoldStoreV1 with a HELD record
            genuine = dict(host.holds.observe().snapshot)
            self.hold = genuine
            self.request({"operation": W.CONFIRM_EVIDENCE_USE, "payload": {
                "evidenceId": "aev.x", "proposalRefId": "p.x", "admissionId": "adm.x", "revisionId": "rev.x"}})
            self.assertEqual(self.sent[-1].payload["holdStore"], genuine)
            self.assertTrue(genuine)

    def test_serve_bridge_ends_on_a_malformed_frame(self):
        server, client = socket.socketpair()
        with server, client:
            client.sendall(struct.pack(">I", 0) + b"x")                      # an invalid length ends the bridge
            client.shutdown(socket.SHUT_WR)
            served = ROOT_CLI.serve_bridge(server, hold_snapshot=dict, exchange=self.exchange)
        self.assertEqual((served, self.sent), (0, []))


@unittest.skipUnless(X.POSIX, "POSIX identities and modes")
class HostIdentityTests(unittest.TestCase):
    def test_the_host_refuses_any_root_identity(self):
        self.assertIsNone(HOST.unprivileged_reason((1000, 1000, 1000), (1000, 1000, 1000)))
        for resuid, resgid in (((0, 0, 0), (1000,) * 3), ((1000, 0, 1000), (1000,) * 3),
                               ((1000, 1000, 0), (1000,) * 3), ((1000,) * 3, (1000, 1000, 0))):
            self.assertEqual(HOST.unprivileged_reason(resuid, resgid), "HOST_HAS_ROOT_IDENTITY")

    def test_the_host_has_no_privilege_switch_and_no_root_client(self):
        source = (ROOT / "services/owner-memory-control/tools/first_memory_dev_host.py").read_text(encoding="utf-8")
        for needle in ("seteuid", "setegid", "setresuid", "setuid(", "as_root", "import clients", "hold_store",
                       "HoldStoreV1", "owner.sock"):
            self.assertNotIn(needle, source)
        bridge = (ROOT / "services/authority-dev/lilith_authority_root/cli.py").read_text(encoding="utf-8")
        self.assertNotIn("first_memory_dev_host", bridge.replace("/tools/first_memory_dev_host.py", ""))

    @unittest.skipUnless(AS_ROOT, "needs root to drop")
    def test_a_dropped_process_can_never_regain_root(self):
        read, write = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read)
            report = {}
            try:
                ROOT_CLI.drop_privileges(UNPRIVILEGED)
                report["resuid"], report["resgid"], report["groups"] = os.getresuid(), os.getresgid(), os.getgroups()
                for name, attempt in (("setuid", lambda: os.setuid(0)), ("seteuid", lambda: os.seteuid(0)),
                                      ("setresuid", lambda: os.setresuid(0, 0, 0)), ("setgid", lambda: os.setgid(0)),
                                      ("setgroups", lambda: os.setgroups([0]))):
                    try:
                        attempt()
                        report[name] = "REGAINED"
                    except PermissionError:
                        report[name] = "REFUSED"
            except BaseException as exc:  # noqa: BLE001 - reported to the parent
                report["error"] = repr(exc)
            os.write(write, json.dumps(report).encode())
            os._exit(0)
        os.close(write)
        raw = b""
        while chunk := os.read(read, 65536):
            raw += chunk
        os.close(read)
        os.waitpid(pid, 0)
        report = json.loads(raw)
        import pwd
        entry = pwd.getpwnam(UNPRIVILEGED)
        self.assertEqual(report.get("resuid"), [entry.pw_uid] * 3, report)
        self.assertEqual(report["resgid"], [entry.pw_gid] * 3)
        self.assertEqual(report["groups"], [])
        for name in ("setuid", "seteuid", "setresuid", "setgid", "setgroups"):
            self.assertEqual(report[name], "REFUSED", name)

    def test_root_is_never_the_target(self):
        with self.assertRaises(ROOT_CLI.Refused) as caught:
            ROOT_CLI.drop_privileges("root")
        self.assertEqual(caught.exception.reason, "FIRST_MEMORY_USER_IS_ROOT")


@unittest.skipUnless(X.POSIX, "POSIX identities and modes")
class TrustedTreeTests(unittest.TestCase):
    def test_a_tree_a_non_root_principal_can_change_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o755)
            base = Path(tmp)
            tree = trusted_tree(base)
            entry = tree / "services/owner-memory-control/tools/first_memory_dev_host.py"
            entry.write_text("print('host')\n")
            os.chmod(entry, 0o644)
            owner = os.getuid()
            # The test tree's parents (the temp dir) are not part of the contract here: check the tree itself.
            relevant = lambda failures: [f for f in failures if str(tree) in f]  # noqa: E731
            self.assertEqual(relevant(ROOT_CLI.trusted_tree_failures(str(tree), owner_uid=owner)), [])
            os.chmod(entry, 0o664)                                          # group-writable code
            self.assertEqual(relevant(ROOT_CLI.trusted_tree_failures(str(tree), owner_uid=owner)),
                             ["UNTRUSTED:" + str(entry)])
            os.chmod(entry, 0o644)
            os.chmod(tree / "services", 0o757)                              # a writable directory in the tree
            self.assertTrue(relevant(ROOT_CLI.trusted_tree_failures(str(tree), owner_uid=owner)))
            os.chmod(tree / "services", 0o755)
            (tree / "link").symlink_to("/tmp")                              # a symlink out of the tree
            self.assertEqual(relevant(ROOT_CLI.trusted_tree_failures(str(tree), owner_uid=owner)),
                             ["UNTRUSTED:" + str(tree / "link")])
            (tree / "link").unlink()
            self.assertTrue(ROOT_CLI.trusted_tree_failures(str(tree), owner_uid=owner + 1))   # another owner

    @unittest.skipUnless(CAN_EXECUTE, "needs root and a root-owned base")
    def test_an_untrusted_host_tree_is_never_executed(self):
        with tempfile.TemporaryDirectory(dir=TRUSTED_BASE) as tmp:
            os.chmod(tmp, 0o755)
            tree = trusted_tree(Path(tmp))
            marker = Path(tmp) / "ran"
            entry = tree / "services/owner-memory-control/tools/first_memory_dev_host.py"
            entry.write_text(f"open({str(marker)!r}, 'w').write('ran')\n")
            os.chmod(entry, 0o666)                                          # lilith (anyone) could rewrite it
            with self.assertRaises(ROOT_CLI.Refused) as caught:
                ROOT_CLI.run_first_memory("recall", "sess.a", tree=str(tree), entry=str(entry),
                                          python=sys.executable, user=UNPRIVILEGED,
                                          hold_snapshot=dict, exchange=lambda frame: {})
            self.assertTrue(caught.exception.reason.startswith("FIRST_MEMORY_HOST_UNTRUSTED"))
            self.assertFalse(marker.exists())

    @unittest.skipUnless(CAN_EXECUTE, "needs root and a root-owned base")
    def test_the_host_runs_unprivileged_and_reaches_only_the_bridge(self):
        with tempfile.TemporaryDirectory(dir=TRUSTED_BASE) as tmp, tempfile.TemporaryDirectory() as scratch:
            os.chmod(tmp, 0o755)
            self.assertEqual(ROOT_CLI.trusted_tree_failures(str(trusted_tree(Path(tmp)))), [])
            tree = Path(tmp) / "host-tree"
            out = Path(scratch)                                             # the report lands outside the tree
            os.chmod(out, 0o777)
            entry = tree / "services/owner-memory-control/tools/first_memory_dev_host.py"
            entry.write_text(
                "import json, os, socket, struct, sys\n"
                "report = {'argv': sys.argv[1:], 'resuid': os.getresuid(), 'groups': os.getgroups()}\n"
                "try:\n    os.seteuid(0); report['seteuid'] = 'REGAINED'\n"
                "except PermissionError:\n    report['seteuid'] = 'REFUSED'\n"
                "s = socket.socket(fileno=3)\n"
                "body = json.dumps({'operation': 'LOOKUP_EVIDENCE_USE', 'payload': {'evidenceId': 'aev.x'}}).encode()\n"
                "s.sendall(struct.pack('>I', len(body)) + body)\n"
                "n = struct.unpack('>I', s.recv(4))[0]; report['bridge'] = json.loads(s.recv(n))\n"
                f"open({str(out / 'report.json')!r}, 'w').write(json.dumps(report))\n")
            os.chmod(entry, 0o644)
            sent = []
            result = ROOT_CLI.run_first_memory(
                "recall", "sess.a", tree=str(tree), entry=str(entry), python=sys.executable, user=UNPRIVILEGED,
                hold_snapshot=lambda: {"root": "genuine"},
                exchange=lambda f: sent.append(W.parse_frame(f)) or {"status": "OK", "use": None})
            report = json.loads((out / "report.json").read_text())
        import pwd
        uid = pwd.getpwnam(UNPRIVILEGED).pw_uid
        self.assertEqual((result["hostExit"], result["bridgeRequests"]), (0, 1))
        self.assertEqual(report["argv"], ["recall", "sess.a"])
        self.assertEqual(report["resuid"], [uid] * 3)
        self.assertEqual((report["groups"], report["seteuid"]), ([], "REFUSED"))
        self.assertEqual(report["bridge"], {"status": "OK", "use": None})
        self.assertEqual([m.operation for m in sent], [W.LOOKUP_EVIDENCE_USE])

    def test_cli_forms_are_closed(self):
        for argv, euid, reason in ((["first-memory", "recall", "sess.a"], 1000, "NOT_ROOT"),
                                   (["first-memory", "forget", "sess.a"], 0, "USAGE"),
                                   (["first-memory", "recall", "../etc"], 0, "SESSION_INVALID"),
                                   (["first-memory", "recall"], 0, "USAGE")):
            with self.subTest(argv=argv):
                with self.assertRaises(ROOT_CLI.Refused) as caught:
                    ROOT_CLI._ledger(argv, euid)
                self.assertEqual(caught.exception.reason, reason)


if __name__ == "__main__":
    unittest.main()
