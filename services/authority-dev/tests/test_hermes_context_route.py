"""The read-only Hermes canonical-memory route (TEST_ONLY; POSIX; synthetic data, no DEV contact, no provider).

1. `context_response`: bounded request, host output validated, owner-personal memories only with BOTH the root-owned
   owner-channel grant and the Hermes Privacy floor, the internal flag never leaves, UNAVAILABLE when anything is off;
2. `owner_channel_granted`: only an exact, root-owned, unexpired (<= 7 days) `lilith_os` grant counts;
3. the real fork: the host gets exactly the context token on stdin, its stdout comes back to root, and the bridge
   forwards ONLY `LOOKUP_EVIDENCE_USE` (issuance and use writes are refused);
4. end to end on the First Memory DEV vertical: a NEW Hermes session receives the admitted codename through the
   socket client (`hermes_memory_context.note_for_turn`) with every chat history gone; the owner-personal origin
   statement does not reach Hermes without grant and floor; Privacy not READY yields no note.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/owner-memory-control", ROOT / "services/core-api", HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pr1s_fixtures as X  # noqa: E402
from lilith_owner_memory import hermes_memory_context as HMC  # noqa: E402

if X.POSIX:
    import test_first_memory_bridge as BRIDGE  # noqa: E402
    import test_first_memory_dev_vertical as V  # noqa: E402
    import test_relationship_origin_dev_vertical as OV  # noqa: E402
    from lilith_authority_dev import protocol as W  # noqa: E402
    from lilith_authority_root import cli as ROOT_CLI  # noqa: E402

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
CODENAME = {"kind": "codename", "value": "SYNTH-ORCHID", "epistemicBasis": "USER_ASSERTED",
            "sensitivity": "PROJECT_FACT", "admissionId": "madm.1", "revisionId": "mrev.1", "hermesErasable": False}
ORIGIN = {"kind": "relationship-origin", "value": "TEST_ONLY synthetic origin statement.",
          "epistemicBasis": "USER_ASSERTED", "sensitivity": "OWNER_PERSONAL", "admissionId": "madm.2",
          "revisionId": "mrev.2", "hermesErasable": False}


def request(channel="lilith_os", session="sess.owner", **extra) -> bytes:
    return json.dumps({"v": 1, "channel": channel, "sessionId": session, **extra}).encode("ascii")


def host_output(*memories, status="CONTEXT", reason=None) -> bytes:
    return (json.dumps({"status": status, "schema": HMC.CONTEXT_SCHEMA, "reason": reason,
                        "memories": list(memories)}) + "\n").encode()


class UnitAssetTests(unittest.TestCase):
    """The socket-activated unit pair (host-setup assets, never signer release payload)."""

    UNITS = ROOT / "services/owner-memory-control/tools/hermes_context"

    def lines(self, name):
        return [line for line in (self.UNITS / name).read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")]

    def test_one_closed_root_cli_form_per_connection_over_a_lilith_only_socket(self):
        socket_unit = self.lines("lilith-first-memory-context.socket")
        for expected in ("ListenStream=/run/lilith-first-memory-context.sock", "SocketUser=root", "SocketGroup=lilith",
                         "SocketMode=0660", "Accept=yes"):
            self.assertIn(expected, socket_unit)
        self.assertEqual(HMC.DEFAULT_SOCKET, "/run/lilith-first-memory-context.sock")
        service = self.lines("lilith-first-memory-context@.service")
        self.assertEqual([line for line in service if line.startswith("Exec")],
                         ["ExecStart=/usr/local/sbin/lilith-authority-ledger-dev first-memory-context"])
        for expected in ("User=root", "StandardInput=socket", "StandardOutput=socket", "RestrictAddressFamilies=AF_UNIX",
                         "IPAddressDeny=any", "CapabilityBoundingSet=CAP_SETUID CAP_SETGID CAP_DAC_OVERRIDE "
                         "CAP_DAC_READ_SEARCH", "AmbientCapabilities="):
            self.assertIn(expected, service)
        import release_file_set as RFS
        self.assertFalse(any("hermes_context" in path for path in RFS.input_files()))     # not release payload


@unittest.skipUnless(X.POSIX, "the root CLI is POSIX")
class ContextResponseTests(unittest.TestCase):
    def respond(self, raw=None, output=None, granted=False):
        return ROOT_CLI.context_response(request() if raw is None else raw,
                                         host_context=lambda session: output if output is not None
                                         else host_output(CODENAME, ORIGIN),
                                         granted=lambda channel, session: granted)

    def test_the_token_and_schema_are_the_adapter_contract(self):
        self.assertEqual((ROOT_CLI.CONTEXT_REQUEST, ROOT_CLI.CONTEXT_SCHEMA), (HMC.CONTEXT_REQUEST, HMC.CONTEXT_SCHEMA))
        self.assertEqual(ROOT_CLI.CONTEXT_OPERATIONS, frozenset({W.LOOKUP_EVIDENCE_USE}))

    def test_owner_personal_needs_both_the_grant_and_the_hermes_floor(self):
        floor = {**ORIGIN, "hermesErasable": True}
        cases = ((False, ORIGIN, False), (True, ORIGIN, False), (False, floor, False), (True, floor, True))
        for granted, origin, shown in cases:
            with self.subTest(granted=granted, floor=origin["hermesErasable"]):
                answer = self.respond(output=host_output(CODENAME, origin), granted=granted)
                self.assertEqual(answer["status"], "CONTEXT")
                self.assertEqual(answer["ownerChannel"], granted)
                kinds = [m["kind"] for m in answer["memories"]]
                self.assertEqual(kinds, ["codename", "relationship-origin"] if shown else ["codename"])
                self.assertTrue(all("hermesErasable" not in m for m in answer["memories"]))   # never leaves root
                note = HMC.render_context_note(answer, include_personal=answer["ownerChannel"] is True)
                self.assertIn("SYNTH-ORCHID", note)
                self.assertEqual(ORIGIN["value"] in note, shown)

    def test_anything_not_exact_is_unavailable_with_no_memories(self):
        bad_requests = (b"", b"x" * 600, request(channel="Bad Channel"), request(session="../etc"),
                        request(extra=1), b'{"v":2,"channel":"lilith_os","sessionId":"s"}',
                        b'{"v":1,"channel":"lilith_os","sessionId":"s","v":1}')
        for raw in bad_requests:
            with self.subTest(raw=raw[:40]):
                self.assertEqual(self.respond(raw=raw)["status"], "UNAVAILABLE")
        bad_outputs = (b"", b"not json\n", host_output(status="CONTEXT", reason=None).replace(b"Lilith", b"X"),
                       host_output({**CODENAME, "extra": 1}), host_output(CODENAME, CODENAME, CODENAME),
                       host_output({**CODENAME, "kind": "persona"}), host_output({**CODENAME, "value": "x" * 601}),
                       host_output({**CODENAME, "hermesErasable": "yes"}))
        for output in bad_outputs:
            with self.subTest(output=output[:60]):
                answer = self.respond(output=output, granted=True)
                self.assertEqual((answer["status"], answer["memories"], answer["ownerChannel"]),
                                 ("UNAVAILABLE", [], False))
        refused = self.respond(output=host_output(status="UNAVAILABLE",
                                                  reason="PRIVACY_FRESHNESS_NOT_READY:FORGET_INTENT_PENDING"))
        self.assertEqual((refused["status"], refused["reason"]),
                         ("UNAVAILABLE", "PRIVACY_FRESHNESS_NOT_READY:FORGET_INTENT_PENDING"))
        self.assertIsNone(HMC.render_context_note(refused, include_personal=True))

        def broken(session):
            raise ROOT_CLI.Refused("FIRST_MEMORY_HOST_UNTRUSTED:x")
        self.assertEqual(ROOT_CLI.context_response(request(), host_context=broken,
                                                   granted=lambda c, s: True)["status"], "UNAVAILABLE")


@unittest.skipUnless(X.POSIX, "POSIX ownership and modes")
class OwnerChannelGrantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "hermes-owner-channel.json"

    def grant(self, mode=0o644, **fields):
        value = {"schemaVersion": 1, "channel": "lilith_os", "sessionId": "sess.owner",
                 "grantedAt": "2026-10-26T00:00:00Z", "expiresAt": "2026-10-27T00:00:00Z", **fields}
        self.path.write_text(json.dumps(value), encoding="ascii")
        os.chmod(self.path, mode)

    def granted(self, channel="lilith_os", session="sess.owner", owner_uid=None, now=NOW):
        return ROOT_CLI.owner_channel_granted(channel, session, path=str(self.path),
                                              owner_uid=os.getuid() if owner_uid is None else owner_uid,
                                              now=lambda: now)

    def test_only_the_exact_unexpired_root_owned_grant_counts(self):
        self.assertFalse(self.granted())                                      # no grant at all
        self.grant()
        self.assertTrue(self.granted())
        self.assertFalse(self.granted(session="sess.other"))                  # another session
        self.assertFalse(self.granted(channel="discord"))                     # another channel, even same id
        self.assertFalse(self.granted(owner_uid=os.getuid() + 1))             # not the trusted owner's file
        self.assertFalse(self.granted(now=datetime(2026, 10, 27, 0, 0, 1, tzinfo=timezone.utc)))   # expired
        self.assertFalse(self.granted(now=datetime(2026, 10, 25, tzinfo=timezone.utc)))           # not yet
        self.grant(mode=0o666)
        self.assertFalse(self.granted())                                      # writable by others
        for fields in ({"expiresAt": "2026-11-03T00:00:01Z"}, {"channel": "discord"}, {"schemaVersion": 2},
                       {"sessionId": "../x"}, {"extra": True}, {"grantedAt": "yesterday"}):
            with self.subTest(fields=fields):
                self.grant(**fields)
                self.assertFalse(self.granted())


@unittest.skipUnless(BRIDGE.CAN_EXECUTE if X.POSIX else False, "needs root and a root-owned base")
class ForkedContextTests(unittest.TestCase):
    def test_the_host_gets_only_the_token_and_the_bridge_only_lookups(self):
        with tempfile.TemporaryDirectory(dir=BRIDGE.TRUSTED_BASE) as tmp, tempfile.TemporaryDirectory() as scratch:
            os.chmod(tmp, 0o755)
            os.chmod(scratch, 0o777)
            tree = BRIDGE.trusted_tree(Path(tmp))
            entry = tree / "services/owner-memory-control/tools/first_memory_dev_host.py"
            report = Path(scratch) / "report.json"
            entry.write_text(
                "import json, socket, struct, sys\n"
                "token = sys.stdin.readline().rstrip('\\n')\n"
                "s = socket.socket(fileno=3)\n"
                "def ask(op, payload):\n"
                "    body = json.dumps({'operation': op, 'payload': payload}).encode()\n"
                "    s.sendall(struct.pack('>I', len(body)) + body)\n"
                "    n = struct.unpack('>I', s.recv(4))[0]; return json.loads(s.recv(n))\n"
                "issue = ask('ISSUE_OWNER_EVIDENCE', {'challengeId': 'och.x'})\n"
                "reserve = ask('RESERVE_EVIDENCE_USE', {'evidenceId': 'aev.x'})\n"
                "lookup = ask('LOOKUP_EVIDENCE_USE', {'evidenceId': 'aev.x'})\n"
                f"open({str(report)!r}, 'w').write(json.dumps({{'argv': sys.argv[1:], 'token': token, "
                "'issue': issue, 'reserve': reserve, 'lookup': lookup}))\n"
                "print(json.dumps({'status': 'CONTEXT', 'schema': 'LilithCanonicalMemoryContextV1', 'reason': None,"
                " 'memories': [{'kind': 'codename', 'value': 'SYNTH-ORCHID', 'epistemicBasis': 'USER_ASSERTED',"
                " 'sensitivity': 'PROJECT_FACT', 'admissionId': 'madm.1', 'revisionId': 'mrev.1',"
                " 'hermesErasable': False}]}))\n")
            os.chmod(entry, 0o644)
            sent = []
            answer = ROOT_CLI.run_first_memory_context(
                stdin=io.BytesIO(request(session="hermes.new")), tree=str(tree), entry=str(entry),
                python=sys.executable, user=BRIDGE.UNPRIVILEGED, hold_snapshot=lambda: {"root": "genuine"},
                exchange=lambda f: sent.append(W.parse_frame(f)) or {"status": "OK", "use": None})
            seen = json.loads(report.read_text())
        self.assertEqual(seen["argv"], ["recall", "hermes.new"])
        self.assertEqual(seen["token"], HMC.CONTEXT_REQUEST)
        self.assertEqual((seen["issue"]["reason"], seen["reserve"]["reason"]),
                         ("BRIDGE_REQUEST_INVALID", "BRIDGE_REQUEST_INVALID"))
        self.assertEqual(seen["lookup"], {"status": "OK", "use": None})
        self.assertEqual([m.operation for m in sent], [W.LOOKUP_EVIDENCE_USE])   # nothing else reached the signer
        self.assertEqual((answer["status"], [m["value"] for m in answer["memories"]], answer["ownerChannel"]),
                         ("CONTEXT", ["SYNTH-ORCHID"], False))

    def test_the_cli_form_is_closed(self):
        for argv in (["first-memory-context", "x"], ["first-memory-context", "--owner"]):
            self.assertEqual(ROOT_CLI.main("lilith-authority-ledger-dev", argv, euid=0), 2)
        self.assertEqual(ROOT_CLI.main("lilith-authority-ledger-dev", ["first-memory-context"], euid=1000), 2)


if X.POSIX:
    class ContextBridgeHarness(V.RootBridgeHarness):
        """The vertical's real root bridge, restricted exactly as the context form restricts it."""

        def __init__(self, case):
            self.case, self.frames, self.hold = case, [], case.signer.released_snapshot
            server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            self.client = V.HOST.BridgeTransportV1(client)
            self._sockets = (server, client)
            self._thread = threading.Thread(target=ROOT_CLI.serve_bridge, args=(server,), kwargs=dict(
                hold_snapshot=lambda: self.hold(), exchange=self.exchange, max_requests=10_000,
                operations=ROOT_CLI.CONTEXT_OPERATIONS), daemon=True)
            self._thread.start()


@unittest.skipUnless(X.POSIX, "ownership and modes are POSIX")
class VerticalContextTests(unittest.TestCase):
    """The relationship-origin vertical's setup and helpers (not its tests), plus the Hermes route."""

    if X.POSIX:
        _OV = OV.RelationshipOriginDevVerticalTests
        copy_db = staticmethod(_OV.copy_db)
        setUp = _OV.setUp
        remember = _OV.remember
        forget_first_interaction = _OV.forget_first_interaction
        register_owner = _OV.register_owner
        set_config = _OV.set_config
        make_core = _OV.make_core
        record_ledger_advance = _OV.record_ledger_advance
        paths = _OV.paths
        host = _OV.host
        owner_signs = _OV.owner_signs
        journal_ops = _OV.journal_ops
        canonical_counts = _OV.canonical_counts

    def serve(self, granted=lambda channel, session: False):
        """A real AF_UNIX context socket: one root `context_response` per connection over a LOOKUP-only bridge."""
        bridge = ContextBridgeHarness(self)
        self.addCleanup(bridge.close)
        path = Path(tempfile.mkdtemp()) / "context.sock"
        self.addCleanup(shutil.rmtree, path.parent, True)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(path))
        listener.listen(4)
        self.addCleanup(listener.close)

        def host_context(session):
            host = V.HOST.FirstMemoryDevHostV1(transport=bridge, paths=self.paths(), freshness=self.fresh.gate(),
                                               now_fn=lambda: V.NOW)
            return (json.dumps(V.HOST.recall(host, session, HMC.CONTEXT_REQUEST)) + "\n").encode()

        def loop():
            while True:
                try:
                    conn, _ = listener.accept()
                except OSError:
                    return
                with conn:
                    raw = b""
                    while True:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        raw += chunk
                    answer = ROOT_CLI.context_response(raw, host_context=host_context, granted=granted)
                    conn.sendall(json.dumps(answer).encode())

        threading.Thread(target=loop, daemon=True).start()
        return str(path), bridge

    def test_a_new_hermes_session_receives_the_codename_and_not_chat_history(self):
        self.register_owner()
        self.assertEqual(self.remember(V.REMEMBER, "sess.codename")[0]["status"], V.FMC.ADMITTED)
        self.assertEqual(self.remember(OV.ORIGIN, "sess.origin")[0]["status"], V.FMC.ADMITTED)
        journal = self.journal_ops()
        shutil.rmtree(self.hermes)                                           # every chat history gone
        path, bridge = self.serve(granted=lambda channel, session: True)     # even with an owner grant ...
        note = HMC.note_for_turn(path, channel="lilith_os", session="hermes.brand-new")
        self.assertIn('"SYNTH-ORCHID"', note)
        self.assertIn("separate from this chat's history", note)
        self.assertNotIn(OV.STATEMENT, note)                                 # ... no Hermes floor: no personal memory
        self.assertEqual(set(bridge.frames), {W.LOOKUP_EVIDENCE_USE})        # the route only looked up
        self.assertEqual(self.journal_ops(), journal)                        # and wrote nothing

    def test_privacy_not_ready_means_no_note(self):
        self.register_owner()
        self.assertEqual(self.remember(V.REMEMBER, "sess.codename")[0]["status"], V.FMC.ADMITTED)
        self.fresh.reboot()
        path, _bridge = self.serve()
        payload = HMC.request_context(path, channel="lilith_os", session="hermes.after-reboot")
        self.assertEqual((payload["status"], payload["memories"]), ("UNAVAILABLE", []))
        self.assertTrue(payload["reason"].startswith("PRIVACY_FRESHNESS_NOT_READY"))
        self.assertIsNone(HMC.note_for_turn(path, channel="lilith_os", session="hermes.after-reboot"))
        self.assertIsNone(HMC.note_for_turn(path + ".missing", channel="lilith_os", session="hermes.x"))


if __name__ == "__main__":
    unittest.main()
