"""The canonical-memory context service: the release's `first-memory-context` plus owner decision D-2 (TEST_ONLY;
POSIX; synthetic data; no DEV contact, no provider).

1. the release decides everything it decided before: request and host output validation, v1 grants (exact session
   AND Hermes floor), UNAVAILABLE on anything not exact; the internal floor flag never leaves root;
2. a v2 grant (`forgetScope: CANONICAL_RECORDS_ONLY`, root-owned, <= 7 days, `lilith_os` only) lets owner-personal
   memories reach the owner's console and says so in the answer; nothing else changes;
3. recall / missing / stale / conflicting / no-write cases on the real First Memory DEV vertical (real host, real
   signer bridge restricted to LOOKUP): the origin statement reaches a brand-new `lilith_os` session, never another
   channel; a kind that was never admitted is simply absent; Privacy not READY or a pending FORGET gives no note;
   duplicate (conflicting) memories of one kind give no note at all; the route writes nothing.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/owner-memory-control", ROOT / "services/core-api", HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pr1s_fixtures as X  # noqa: E402
from lilith_owner_memory import hermes_memory_context as HMC  # noqa: E402

SERVICE_PATH = ROOT / "services/owner-memory-control/tools/hermes_context/canonical_context_service.py"
_spec = importlib.util.spec_from_file_location("canonical_context_service", SERVICE_PATH)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

if X.POSIX:
    import test_hermes_context_route as R  # noqa: E402
    from lilith_authority_dev import protocol as W  # noqa: E402
    from lilith_authority_root import cli as ROOT_CLI  # noqa: E402

NOW = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)


def stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class AssetTests(unittest.TestCase):
    UNITS = ROOT / "services/owner-memory-control/tools/hermes_context"

    def test_the_unit_runs_this_service_under_the_installed_release(self):
        service = [line for line in (self.UNITS / "lilith-first-memory-context@.service").read_text().splitlines()
                   if line.startswith("Exec")]
        self.assertEqual(service, ["ExecStart=/opt/lilith-authority-dev/current/venv/bin/python -I -B "
                                   "/usr/local/lib/lilith-canonical-context/canonical_context_service.py"])
        self.assertEqual(S.RELEASE, "/opt/lilith-authority-dev/current")

    def test_no_copy_of_release_logic(self):
        source = SERVICE_PATH.read_text(encoding="utf-8")
        for borrowed in ("cli.context_response(", "cli.run_first_memory(", "cli.owner_channel_granted(",
                         "cli.CONTEXT_OPERATIONS", "cli.CONTEXT_REQUEST"):
            self.assertIn(borrowed, source)
        for forbidden in ("ISSUE_OWNER_EVIDENCE", "RESERVE_EVIDENCE_USE", "os.fork", "socket.socket", "sqlite3",
                          '"remember"'):
            self.assertFalse(forbidden in source, forbidden)


@unittest.skipUnless(X.POSIX, "the root CLI is POSIX")
class ResponseTests(unittest.TestCase):
    def respond(self, basis=None, output=None, raw=None):
        return S.context_response(ROOT_CLI, R.request() if raw is None else raw,
                                  host_context=lambda session: output if output is not None
                                  else R.host_output(R.CODENAME, R.ORIGIN),
                                  basis=lambda channel, session: basis)

    def test_the_release_rule_is_unchanged_without_a_v2_grant(self):
        floor = {**R.ORIGIN, "hermesErasable": True}
        for basis, origin, kinds in ((None, R.ORIGIN, ["codename"]), (S.V1, R.ORIGIN, ["codename"]),
                                     (S.V1, floor, ["codename", "relationship-origin"])):
            with self.subTest(basis=basis, floor=origin["hermesErasable"]):
                mine = self.respond(basis=basis, output=R.host_output(R.CODENAME, origin))
                theirs = ROOT_CLI.context_response(R.request(), host_context=lambda s: R.host_output(R.CODENAME, origin),
                                                   granted=lambda c, s: basis is not None)
                self.assertEqual(mine, theirs)
                self.assertEqual([m["kind"] for m in mine["memories"]], kinds)
                self.assertNotIn("forgetScope", mine)

    def test_a_v2_grant_adds_the_held_back_personal_memory_and_states_the_forget_scope(self):
        answer = self.respond(basis=S.V2)
        self.assertEqual((answer["status"], answer["ownerChannel"], answer["forgetScope"]),
                         ("CONTEXT", True, "CANONICAL_RECORDS_ONLY"))
        self.assertEqual([m["kind"] for m in answer["memories"]], ["codename", "relationship-origin"])
        self.assertTrue(all("hermesErasable" not in m for m in answer["memories"]))
        note = HMC.render_context_note(answer, include_personal=answer["ownerChannel"] is True)
        self.assertIn(json.dumps(R.ORIGIN["value"]), note)
        self.assertIn("SYNTH-ORCHID", note)

    def test_v2_never_rescues_an_answer_the_release_refused(self):
        bad = (R.host_output(status="UNAVAILABLE", reason="PRIVACY_FRESHNESS_NOT_READY:BOOT_NOT_VERIFIED"),
               R.host_output(R.ORIGIN, R.ORIGIN),                             # conflicting: two of one kind
               R.host_output(R.CODENAME, {**R.CODENAME, "value": "OTHER-NAME"}),   # the release lets this through
               R.host_output({**R.ORIGIN, "extra": 1}), b"", b"not json\n")
        for output in bad:
            with self.subTest(output=output[:50]):
                answer = self.respond(basis=S.V2, output=output)
                self.assertEqual((answer["status"], answer["memories"], answer["ownerChannel"]),
                                 ("UNAVAILABLE", [], False))
                self.assertIsNone(HMC.render_context_note(answer, include_personal=True))
        self.assertEqual(self.respond(basis=S.V2, raw=b'{"v":1}')["status"], "UNAVAILABLE")

    def test_missing_is_absent_and_nothing_admitted_means_no_note(self):
        only_origin = self.respond(basis=S.V2, output=R.host_output(R.ORIGIN))
        self.assertEqual([m["kind"] for m in only_origin["memories"]], ["relationship-origin"])
        note = HMC.render_context_note(only_origin, include_personal=True)
        self.assertNotIn("Project codename", note)
        empty = self.respond(basis=S.V2, output=R.host_output())
        self.assertEqual((empty["status"], empty["memories"]), ("CONTEXT", []))
        self.assertIsNone(HMC.render_context_note(empty, include_personal=True))

    def test_main_is_root_only_and_any_failure_is_an_unavailable_answer(self):
        out = io.StringIO()
        self.assertEqual(S.main(io.BytesIO(R.request()), out, cli=ROOT_CLI, euid=1000), 2)
        self.assertEqual(out.getvalue(), "")

        class Broken:
            def __getattr__(self, name):
                return getattr(ROOT_CLI, name)

            @staticmethod
            def run_first_memory(*_a, **_k):
                raise RuntimeError("host exploded")

        out = io.StringIO()
        self.assertEqual(S.main(io.BytesIO(R.request()), out, cli=Broken(), euid=0), 0)
        answer = json.loads(out.getvalue())
        self.assertEqual((answer["status"], answer["memories"], answer["ownerChannel"]), ("UNAVAILABLE", [], False))


@unittest.skipUnless(X.POSIX, "POSIX ownership and modes")
class GrantTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "hermes-owner-channel.json"

    def write(self, mode=0o644, raw=None, **fields):
        value = {"schemaVersion": 2, "channel": "lilith_os", "sessionScope": "ALL_LILITH_OS_SESSIONS",
                 "forgetScope": "CANONICAL_RECORDS_ONLY", "grantedAt": stamp(NOW - timedelta(hours=1)),
                 "expiresAt": stamp(NOW + timedelta(days=2)), **fields}
        self.path.write_text(raw if raw is not None else json.dumps(value), encoding="ascii")
        os.chmod(self.path, mode)

    def basis(self, channel="lilith_os", session="0f5c2d3e-uuid", uid=None, now=NOW):
        return S.grant_basis(ROOT_CLI, channel, session, path=str(self.path),
                             owner_uid=os.getuid() if uid is None else uid, now=lambda: now)

    def test_a_valid_v2_grant(self):
        self.assertIsNone(self.basis())                                       # no file
        self.write()
        self.assertEqual(self.basis(), S.V2)
        self.assertEqual(self.basis(session="any-other-session"), S.V2)       # channel-wide scope
        self.write(sessionScope="sess.one")
        self.assertEqual(self.basis(session="sess.one"), S.V2)
        self.assertIsNone(self.basis(session="sess.two"))

    def test_everything_else_is_no_grant(self):
        self.write()
        self.assertIsNone(self.basis(channel="telegram"))
        self.assertIsNone(self.basis(channel="discord"))
        self.assertIsNone(self.basis(uid=os.getuid() + 1))                    # not root's file
        self.assertIsNone(self.basis(now=NOW + timedelta(days=3)))            # expired
        self.assertIsNone(self.basis(now=NOW - timedelta(days=1)))            # not yet valid
        self.write(mode=0o664)
        self.assertIsNone(self.basis())
        for fields in ({"forgetScope": "CANONICAL_AND_CONVERSATION"}, {"forgetScope": None},
                       {"channel": "telegram"}, {"sessionScope": "../x"}, {"sessionScope": ""},
                       {"expiresAt": stamp(NOW + timedelta(days=8)), "grantedAt": stamp(NOW)},
                       {"grantedAt": "yesterday"}, {"schemaVersion": 3}, {"extra": True}):
            with self.subTest(fields=fields):
                self.write(**fields)
                self.assertIsNone(self.basis())
        for raw in ("[]", "not json", '{"schemaVersion":2,"schemaVersion":2}', "x" * 2000):
            with self.subTest(raw=raw[:20]):
                self.write(raw=raw)
                self.assertIsNone(self.basis())

    def v3(self, **fields):
        value = {"schemaVersion": 3, "channels": ["lilith_os", "telegram_owner_dm"],
                 "sessionScope": "ALL_OWNER_CHANNEL_SESSIONS", "forgetScope": "CANONICAL_RECORDS_ONLY",
                 "grantedAt": stamp(NOW - timedelta(hours=1)), "expiresAt": stamp(NOW + timedelta(days=2)), **fields}
        self.write(raw=json.dumps(value))

    def test_a_v3_grant_names_each_owner_channel(self):
        self.v3()
        self.assertEqual(self.basis(channel="lilith_os"), S.V2)
        self.assertEqual(self.basis(channel="telegram_owner_dm", session="agent:main:telegram:dm:42"), S.V2)
        for channel in ("public", "telegram", "discord", "telegram_group"):
            self.assertIsNone(self.basis(channel=channel))                    # never an owner channel
        self.v3(channels=["lilith_os"])
        self.assertIsNone(self.basis(channel="telegram_owner_dm"))            # Telegram only when listed
        self.assertEqual(self.basis(channel="lilith_os"), S.V2)
        for fields in ({"channels": []}, {"channels": ["lilith_os", "lilith_os"]}, {"channels": ["public"]},
                       {"channels": ["lilith_os", "discord"]}, {"channels": "lilith_os"},
                       {"sessionScope": "ALL_LILITH_OS_SESSIONS"}, {"forgetScope": "ALL"}, {"channel": "lilith_os"}):
            with self.subTest(fields=fields):
                self.v3(**fields)
                self.assertIsNone(self.basis(channel="lilith_os"))
        self.write(channel="lilith_os")                                       # a v2 grant never covers Telegram
        self.assertIsNone(self.basis(channel="telegram_owner_dm"))

    def test_a_v1_grant_keeps_the_release_meaning(self):
        v1 = {"schemaVersion": 1, "channel": "lilith_os", "sessionId": "sess.owner",
              "grantedAt": stamp(NOW - timedelta(hours=1)), "expiresAt": stamp(NOW + timedelta(days=1))}
        self.write(raw=json.dumps(v1))
        self.assertEqual(self.basis(session="sess.owner"), S.V1)
        self.assertIsNone(self.basis(session="sess.other"))


if X.POSIX:
    class ServiceVertical(R.VerticalContextTests):
        """The route harness with the service's `context_response` in place of the release's."""

        def serve_v2(self, basis):
            original = ROOT_CLI.context_response

            class Release:                       # the real release module, with its own context_response
                context_response = staticmethod(original)

                def __getattr__(self, name):
                    return getattr(ROOT_CLI, name)
            release = Release()

            def patched(raw, *, host_context, granted):
                return S.context_response(release, raw, host_context=host_context, basis=basis)
            ROOT_CLI.context_response = patched
            self.addCleanup(setattr, ROOT_CLI, "context_response", original)
            return self.serve()

    ServiceVertical.test_a_new_hermes_session_receives_the_codename_and_not_chat_history = None
    ServiceVertical.test_privacy_not_ready_means_no_note = None


@unittest.skipUnless(X.POSIX, "ownership and modes are POSIX")
class VerticalTests(ServiceVertical if X.POSIX else unittest.TestCase):
    def admit_both(self):
        self.register_owner()
        self.assertEqual(self.remember(R.V.REMEMBER, "sess.codename")[0]["status"], R.V.FMC.ADMITTED)
        self.assertEqual(self.remember(R.OV.ORIGIN, "sess.origin")[0]["status"], R.V.FMC.ADMITTED)

    def owner_v2(self, channel, session):
        return S.V2 if channel == "lilith_os" else None

    def test_recall_the_origin_in_a_brand_new_console_session_with_no_history(self):
        self.admit_both()
        journal, counts = self.journal_ops(), self.canonical_counts()
        shutil.rmtree(self.hermes)                                           # every chat history gone
        path, bridge = self.serve_v2(self.owner_v2)
        note = HMC.note_for_turn(path, channel="lilith_os", session="0f5c2d3e-brand-new")
        self.assertIn(json.dumps(R.OV.STATEMENT), note)
        self.assertIn('"SYNTH-ORCHID"', note)
        self.assertIn("separate from this chat's history", note)
        payload = HMC.request_context(path, channel="lilith_os", session="another-new")
        self.assertEqual(payload["forgetScope"], "CANONICAL_RECORDS_ONLY")
        self.assertEqual(set(bridge.frames), {W.LOOKUP_EVIDENCE_USE})        # only looked up
        self.assertEqual((self.journal_ops(), self.canonical_counts()), (journal, counts))   # wrote nothing

    def test_other_channels_never_receive_personal_memory(self):
        self.admit_both()
        path, _bridge = self.serve_v2(self.owner_v2)
        for channel in ("telegram", "discord"):
            note = HMC.note_for_turn(path, channel=channel, session="chat.1")
            self.assertIn('"SYNTH-ORCHID"', note)
            self.assertNotIn(R.OV.STATEMENT, note)

    def test_without_a_grant_it_is_the_release_behaviour(self):
        self.admit_both()
        path, _bridge = self.serve_v2(lambda channel, session: None)
        note = HMC.note_for_turn(path, channel="lilith_os", session="s.1")
        self.assertNotIn(R.OV.STATEMENT, note)

    def test_missing_memory_is_absent(self):
        self.register_owner()
        self.assertEqual(self.remember(R.OV.ORIGIN, "sess.origin")[0]["status"], R.V.FMC.ADMITTED)
        path, _bridge = self.serve_v2(self.owner_v2)
        note = HMC.note_for_turn(path, channel="lilith_os", session="s.2")
        self.assertIn(json.dumps(R.OV.STATEMENT), note)
        self.assertNotIn("Project codename", note)

    def test_stale_privacy_means_no_note_even_with_the_grant(self):
        self.admit_both()
        self.fresh.reboot()                                                  # a new boot, not yet unlocked
        path, _bridge = self.serve_v2(self.owner_v2)
        payload = HMC.request_context(path, channel="lilith_os", session="s.3")
        self.assertEqual((payload["status"], payload["memories"]), ("UNAVAILABLE", []))
        self.assertTrue(payload["reason"].startswith("PRIVACY_FRESHNESS_NOT_READY"))
        self.assertIsNone(HMC.note_for_turn(path, channel="lilith_os", session="s.3"))


if __name__ == "__main__":
    unittest.main()
