"""15B2b-B1b-3e PR-1S signer runtime wiring tests (repository only).

The durable authority recovery ledger, the narrow C-4 recovery wiring, the
signer protocol / core / self-view, and the release contract. Every ledger
lives in a temporary directory; every witness and registry is Source Prep B
TEST material in the TEST environment `test`. Nothing contacts DEV or PROD.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import socket
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pr1s_fixtures as X
from pr1s_fixtures import F, PB, J, PA, SC, WR, RC

import release_file_set as RFS
import synthetic_b1b3e_prep_b as PBF
from lilith_authority_dev import core as CORE
from lilith_authority_dev import credential as CRED
from lilith_authority_dev import ledger as L
from lilith_authority_dev import protocol as W
from lilith_authority_dev import recovery as REC
from lilith_authority_dev import server as S
from lilith_authority_dev import state as STATE
from lilith_authority_host import paths as P
from lilith_authority_signer import synthetic_recovery_ledger as RL
from lilith_authority_signer import synthetic_witness_v2 as W2
from lilith_owner_memory import successor_readiness as SR

ROOT = X.ROOT
SERVICE = ROOT / "services/authority-dev"
POSIX = X.POSIX
PRESENT = CRED.CredentialStatusV1(CRED.CREDENTIAL_PRESENT_UNVERIFIED, "a" * 64)
UNIT = (SERVICE / "deploy/lilith-authority-dev.service").read_text(encoding="utf-8")


def state_dir(directory: str) -> Path:
    path = Path(directory) / "state"
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def seeded_ledger(directory: str, log: tuple) -> L.DurableAuthorityLedgerV1:
    """A durable ledger holding exactly `log` (TEST helper: journals through the
    module-private writer, the same one `append_recovery` uses)."""
    path = state_dir(directory) / "authority_ledger.db"
    L.DurableAuthorityLedgerV1.provision(path, environment=X.ENV, genesis=log[0], expected_uid=X.UID)
    if len(log) > 1:
        conn = L._connect(path)
        conn.execute("BEGIN IMMEDIATE")
        L._write_ops(conn, (log[0],), log[1:])
        conn.execute("COMMIT")
        conn.close()
    return L.DurableAuthorityLedgerV1.open_existing(path, environment=X.ENV, expected_uid=X.UID)


def reserved_log() -> tuple:
    """A TEST journal with a CONSUMED+ISSUED challenge, a RESERVED use, and a PREPARED challenge."""
    state = RL.AuthorityLedgerStateV1.genesis(environment=X.ENV, recovery_epoch=PBF.EG, policy_version=PBF.POLICY,
                                              registry_version=1, signing_key_ids=(PB.P0,))
    lep = RL.R.ledger_epoch_id(PBF.EG, X.ENV)
    for step in (lambda s: s.prepare("c1", lep, ready=F.seeded_ready(s)),
                 lambda s: s.consume("c1", ready=F.seeded_ready(s)),
                 lambda s: s.issue("c1", "aev.c1", F.digest("pr1s c1"), ready=F.seeded_ready(s)),
                 lambda s: s.reserve("aev.c1", F.digest("pr1s c1"), PBF.EG, "prop.1", ready=F.seeded_ready(s)),
                 lambda s: s.prepare("c2", lep, ready=F.seeded_ready(s))):
        state = step(state)
    return state.log


# ----------------------------------------------------------- the journal ---

class JournalEquivalenceTests(unittest.TestCase):
    def test_shared_journal_is_the_test_model(self):
        self.assertIs(RL.replay, J.replay)
        self.assertIs(RL.LedgerRefusal, J.LedgerRefusal)
        self.assertEqual(RL.LEDGER_HEAD_DOMAIN_SEPARATOR, b"LILITH_AUTHORITY_LEDGER_HEAD_V1\x00")
        state = RL.AuthorityLedgerStateV1.from_log(reserved_log())
        self.assertEqual((state.sequence, state.head), (J.replay(state.log).sequence, J.replay(state.log).head))

    def test_genesis_op_and_initial_position_are_owner_derivable(self):
        op = J.genesis_op(PB.g1())
        self.assertEqual(op, {"op": "GENESIS", "environment": X.ENV, "recoveryEpoch": PBF.EG.to_dict(),
                              "policyVersion": PBF.POLICY, "registryVersion": 1, "signingKeyIds": [PB.P0]})
        model = RL.AuthorityLedgerStateV1.genesis(environment=X.ENV, recovery_epoch=PBF.EG,
                                                  policy_version=PBF.POLICY, registry_version=1,
                                                  signing_key_ids=(PB.P0,))
        self.assertEqual(J.initial_position(PB.g1()), (model.sequence, model.head))
        with self.assertRaises(J.LedgerRefusal):
            J.genesis_op(PB.mark2())  # no current OWNER_ACTOR key

    def test_epoch_adoption_op_equals_the_test_adoption(self):
        s = PB.PrepBScenario().mark()
        eaa = s.issue_epoch_advance(PB.rec3())
        ours = J.epoch_adoption_op(s.ledger.log, authorization=eaa, witness=s.head, target_registry=PB.rec3(),
                                   registry_root=F.root())
        theirs = W2.adopt_authorized_epoch(s.ledger, authorization=eaa, witness=s.head, target_registry=PB.rec3(),
                                           registry_root=F.root()).log[-1]
        self.assertEqual(ours, theirs)


# ---------------------------------------------------- the durable ledger ---

@unittest.skipUnless(POSIX, "ownership and modes are POSIX")
class DurableLedgerTests(unittest.TestCase):
    def test_explicit_provisioning_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = state_dir(directory) / "authority_ledger.db"
            with self.assertRaises(L.LedgerError) as caught:
                L.DurableAuthorityLedgerV1.open_existing(path, environment=X.ENV, expected_uid=X.UID)
            self.assertEqual(caught.exception.reason, "AUTHORITY_STATE_MISSING")
            self.assertFalse(path.exists())  # opening never creates
            observed = L.DurableAuthorityLedgerV1.provision(path, environment=X.ENV, genesis=J.genesis_op(PB.g1()),
                                                            expected_uid=X.UID)
            self.assertEqual((observed.sequence, observed.head), J.initial_position(PB.g1()))
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            for bad in (dict(genesis=J.genesis_op(PB.g1())),):
                with self.assertRaises(L.LedgerError) as caught:
                    L.DurableAuthorityLedgerV1.provision(path, environment=X.ENV, expected_uid=X.UID, **bad)
                self.assertEqual(caught.exception.reason, "LEDGER_ALREADY_EXISTS")
            ledger = L.DurableAuthorityLedgerV1.open_existing(path, environment=X.ENV, expected_uid=X.UID)
            try:
                conn = ledger._conn
                self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
                self.assertEqual(conn.execute("PRAGMA synchronous").fetchone()[0], 2)  # FULL
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            finally:
                ledger.close()

    def test_provisioning_refuses_unsafe_state_and_bad_genesis(self):
        with tempfile.TemporaryDirectory() as directory:
            loose = Path(directory) / "loose"
            loose.mkdir(mode=0o755)
            os.chmod(loose, 0o755)
            with self.assertRaises(L.LedgerError) as caught:
                L.DurableAuthorityLedgerV1.provision(loose / "authority_ledger.db", environment=X.ENV,
                                                     genesis=J.genesis_op(PB.g1()), expected_uid=X.UID)
            self.assertEqual(caught.exception.reason, "LEDGER_PATH_UNSAFE")
            path = state_dir(directory) / "authority_ledger.db"
            for environment, genesis, reason in (("prod", J.genesis_op(PB.g1()), "LEDGER_ENVIRONMENT_INVALID"),
                                                 ("dev", J.genesis_op(PB.g1()), "LEDGER_GENESIS_INVALID"),
                                                 (X.ENV, {"op": "PREPARE"}, "LEDGER_GENESIS_INVALID")):
                with self.assertRaises(L.LedgerError) as caught:
                    L.DurableAuthorityLedgerV1.provision(path, environment=environment, genesis=genesis,
                                                         expected_uid=X.UID)
                self.assertEqual(caught.exception.reason, reason)
                self.assertFalse(path.exists())

    def test_rows_and_head_equal_the_test_model_and_wrong_environment_refuses(self):
        log = reserved_log()
        with tempfile.TemporaryDirectory() as directory:
            ledger = seeded_ledger(directory, log)
            try:
                observed = ledger.observe()
                model = RL.AuthorityLedgerStateV1.from_log(log)
                self.assertEqual((observed.sequence, observed.head), (model.sequence, model.head))
                self.assertEqual(L._rows(ledger._conn), model.rows)
                self.assertTrue(observed.rows_consistent and not observed.terminal_reopened)
                self.assertEqual(ledger.journal(), tuple(log))
            finally:
                ledger.close()
            with self.assertRaises(L.LedgerError) as caught:
                L.DurableAuthorityLedgerV1.open_existing(Path(directory) / "state/authority_ledger.db",
                                                         environment="dev", expected_uid=X.UID)
            self.assertEqual(caught.exception.reason, "LEDGER_META_MISMATCH")

    def test_recovery_operations_and_refusals(self):
        s = PB.PrepBScenario().mark()
        eaa = s.issue_epoch_advance(PB.rec3())
        log = reserved_log()
        with tempfile.TemporaryDirectory() as directory:
            ledger = seeded_ledger(directory, log)
            try:
                before = ledger.observe()
                op = J.epoch_adoption_op(ledger.journal(), authorization=eaa, witness=s.head,
                                         target_registry=PB.rec3(), registry_root=F.root())
                for bad in ([{"op": "ISSUE"}], [{"op": "PREPARE"}], [{"op": "CONSUME"}], [{"op": "RESERVE"}],
                            [{"op": "CONFIRM"}], [{"op": "REGISTRY_VIEW"}], [{"op": "GENESIS"}], []):
                    with self.assertRaises(L.LedgerError) as caught:
                        ledger.append_recovery(bad, expected_sequence=before.sequence, expected_head=before.head)
                    self.assertEqual(caught.exception.reason, "LEDGER_OPERATION_NOT_PERMITTED")
                with self.assertRaises(L.LedgerError) as caught:
                    ledger.append_recovery([op], expected_sequence=before.sequence, expected_head="0" * 64)
                self.assertEqual(caught.exception.reason, "LEDGER_HEAD_STALE")
                after = ledger.append_recovery([op], expected_sequence=before.sequence, expected_head=before.head)
                self.assertEqual(after.recovery_epoch, PBF.EN)
                with self.assertRaises(L.LedgerError) as caught:  # replay of the same adoption
                    ledger.append_recovery([op], expected_sequence=after.sequence, expected_head=after.head)
                self.assertEqual((caught.exception.reason, caught.exception.detail),
                                 ("LEDGER_REFUSED", "LEDGER_MALFORMED"))
                self.assertEqual(ledger.observe(), after)  # a refused write wrote nothing
                replayed = ledger.replay()
                ops = [{"op": J.VOID_CHALLENGE, "challengeId": cid} for cid in J.stale_prepared_challenges(replayed)]
                ops += [{"op": J.QUARANTINE_USE, "evidenceId": eid} for eid in J.stale_reserved_uses(replayed)]
                self.assertEqual([o["op"] for o in ops], ["VOID_CHALLENGE", "QUARANTINE_USE"])
                final = ledger.append_recovery(ops, expected_sequence=after.sequence, expected_head=after.head)
                rows = L._rows(ledger._conn)
                self.assertEqual(rows["challenges"]["c2"]["state"], "VOIDED_BY_RECOVERY")
                self.assertEqual(rows["challenges"]["c1"]["state"], "CONSUMED")  # terminal stays history
                self.assertEqual(rows["uses"]["aev.c1"]["state"], "QUARANTINED_BY_RECOVERY")
                with self.assertRaises(L.LedgerError) as caught:
                    ledger.append_recovery([{"op": J.VOID_CHALLENGE, "challengeId": "c1"}],
                                           expected_sequence=final.sequence, expected_head=final.head)
                self.assertEqual((caught.exception.reason, caught.exception.detail),
                                 ("LEDGER_REFUSED", "NOT_PRE_RECOVERY_WORK"))
            finally:
                ledger.close()

    def test_terminal_rows_never_reopen_and_the_journal_is_append_only(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = seeded_ledger(directory, reserved_log())
            conn = ledger._conn
            try:
                for sql in ("UPDATE authority_challenge_v2 SET state = 'PREPARED' WHERE challenge_id = 'c1'",
                            "DELETE FROM authority_challenge_v2 WHERE challenge_id = 'c2'",
                            "UPDATE authority_journal_v1 SET payload = x'00' WHERE seq = 2",
                            "DELETE FROM authority_journal_v1 WHERE seq = 6",
                            "UPDATE authority_evidence_v2 SET evidence_digest = 'x' WHERE evidence_id = 'aev.c1'",
                            "INSERT INTO authority_journal_v1 VALUES (9, 'ABANDON', x'00', "
                            "'0000000000000000000000000000000000000000000000000000000000000000', "
                            "'1111111111111111111111111111111111111111111111111111111111111111', 'x')"):
                    with self.subTest(sql=sql[:40]), self.assertRaises(sqlite3.DatabaseError):
                        conn.execute(sql)
            finally:
                ledger.close()

    def test_edited_or_foreign_schema_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = seeded_ledger(directory, reserved_log())
            path = ledger.path
            ledger._conn.execute("DROP TRIGGER authority_challenge_v2_terminal")
            ledger._conn.execute("UPDATE authority_challenge_v2 SET state = 'PREPARED' WHERE challenge_id = 'c1'")
            ledger.close()
            with self.assertRaises(L.LedgerError) as caught:
                L.DurableAuthorityLedgerV1.open_existing(path, environment=X.ENV, expected_uid=X.UID)
            self.assertEqual(caught.exception.reason, "LEDGER_SCHEMA_MISMATCH")

    def test_root_observation_reads_a_private_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = seeded_ledger(directory, reserved_log())
            expected = ledger.observe()
            path = ledger.path
            ledger.close()
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(L.observe_copy(path, environment=X.ENV), expected)
            self.assertEqual(L.journal_copy(path, environment=X.ENV), reserved_log())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
            with self.assertRaises(L.LedgerError):
                L.observe_copy(Path(directory) / "absent.db", environment=X.ENV)

    def test_ledger_is_signer_state_only(self):
        source = (SERVICE / "lilith_authority_dev/ledger.py").read_text(encoding="utf-8")
        for needle in ("owner_control", "synthetic_evidence", "l04", "memory-broker", "L04_", "lilith_memory_broker"):
            self.assertNotIn(needle, source)
        public = {name for name in dir(L.DurableAuthorityLedgerV1) if not name.startswith("_")}
        self.assertEqual(public, {"open_existing", "provision", "close", "journal", "observe", "replay",
                                  "append_recovery"})
        self.assertEqual(L.SCHEMA_FINGERPRINT, L.schema_fingerprint_of(L.SCHEMA))
        self.assertEqual(P.AUTHORITY_LEDGER, "/var/lib/lilith-authority-dev/authority_ledger.db")


# ---------------------------------------------------------- C-4 wiring ---

class _Witness:
    """A fake signer-socket witness: records RECORD_LEDGER_ADVANCE calls."""

    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply or {"status": "OK"}

    def __call__(self, previous, sequence, head):
        self.calls.append((previous, sequence, head))
        return self.reply


@unittest.skipUnless(POSIX, "ownership and modes are POSIX")
class RecoveryWiringTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.s = PB.PrepBScenario().mark()
        self.eaa = self.s.issue_epoch_advance(PB.rec3())
        self.ledger_path = None
        ledger = seeded_ledger(self.directory.name, self.s.ledger.log)
        self.ledger_path = ledger.path
        ledger.close()
        self.witness = _Witness()
        self.kcr = PB.hold(kind=SC.KEY_COMPROMISE_RECOVERY, witness=self.s.digests["holdEngaged"])

    def tearDown(self):
        self.directory.cleanup()

    def handler(self, **overrides):
        def view():
            return REC.SignerViewV1(self.s.context(), tuple(self.s.registries), self.s.observation())

        def open_ledger():
            return L.DurableAuthorityLedgerV1.open_existing(self.ledger_path, environment=X.ENV, expected_uid=X.UID)
        value = dict(view=view, open_ledger=open_ledger, record_ledger_advance=self.witness, profile=PBF.PROFILE)
        value.update(overrides)
        return REC.RecoveryHandlerV1(**value)

    def snapshot(self, *holds):
        return PA.hold_snapshot_document(SC.hold_store(*holds), environment=X.ENV)

    def test_the_full_c4_sequence_through_the_runtime(self):
        handler = self.handler()
        result = handler.handle(W.RECOVERY_ADVANCE_EPOCH, {"epochAuthorization": self.eaa,
                                                           "holdStore": self.snapshot(self.kcr)})
        self.assertEqual(result["status"], "OK", result)
        self.assertEqual(result["journalled"], ["ADVANCE_EPOCH"])
        self.assertFalse(result["signingPermitted"] or result["issuancePermitted"] or result["authorityGranted"])
        self.assertEqual(self.witness.calls, [])  # the witness binds the adoption by its own epoch execution
        model = W2.adopt_authorized_epoch(self.s.ledger, authorization=self.eaa, witness=self.s.head,
                                          target_registry=PB.rec3(), registry_root=F.root())
        self.assertEqual((result["ledgerSequence"], result["ledgerHead"]), (model.sequence, model.head))
        again = handler.handle(W.RECOVERY_ADVANCE_EPOCH, {"epochAuthorization": self.eaa,
                                                          "holdStore": self.snapshot(self.kcr)})
        self.assertEqual((again["status"], again["reason"]), ("REFUSED", "ADOPTION_ALREADY_JOURNALLED"))
        # The witness executes the same authorization over the post-adoption position (C-4).
        self.s.ledger = model
        self.s.execute_epoch_advance(self.eaa, PB.rec3())
        voided = handler.handle(W.RECOVERY_VOID_CHALLENGE, {"holdStore": self.snapshot(self.kcr)})
        self.assertEqual((voided["status"], voided["journalled"], voided["witness"]),
                         ("OK", ["VOID_CHALLENGE"], "RECORDED"))
        quarantined = RL.quarantine_pre_recovery(model)
        self.assertEqual((voided["ledgerSequence"], voided["ledgerHead"]), (quarantined.sequence, quarantined.head))
        self.assertEqual(self.witness.calls, [(self.s.head.digest, quarantined.sequence, quarantined.head)])
        nothing = handler.handle(W.RECOVERY_QUARANTINE_USE, {"holdStore": self.snapshot(self.kcr)})
        self.assertEqual(nothing["reason"], "LEDGER_NOT_AT_WITNESS")  # the witness has not recorded the voids here

    def test_unwitnessed_commit_is_reported_ahead_of_the_witness(self):
        model = W2.adopt_authorized_epoch(self.s.ledger, authorization=self.eaa, witness=self.s.head,
                                          target_registry=PB.rec3(), registry_root=F.root())
        self.handler().handle(W.RECOVERY_ADVANCE_EPOCH, {"epochAuthorization": self.eaa,
                                                         "holdStore": self.snapshot(self.kcr)})
        self.s.ledger = model
        self.s.execute_epoch_advance(self.eaa, PB.rec3())
        down = _Witness({"status": "REFUSED", "reason": "STORE_BUSY"})
        result = self.handler(record_ledger_advance=down).handle(W.RECOVERY_VOID_CHALLENGE,
                                                                 {"holdStore": self.snapshot(self.kcr)})
        self.assertEqual(result["status"], REC.LEDGER_AHEAD_OF_WITNESS)

    def test_complete_hold_observation_is_required(self):
        handler = self.handler()
        other = PB.hold(kind=SC.ROTATION, ceremony=PB.C3, successor=PB.S3, witness=self.s.digests["holdEngaged"])
        full = self.snapshot(self.kcr, PB.hold(kind=SC.ROTATION, state=SC.RELEASED, ceremony=PB.C3, successor=PB.S3,
                                                      witness=self.s.head.digest))
        cases = {
            "single hold record": (self.kcr, "HOLD_SNAPSHOT_MALFORMED"),
            "subset of a listing": (dict(full, entries=full["entries"][:1]), "HOLD_SNAPSHOT_DIGEST_MISMATCH"),
            "missing": (None, "HOLD_SNAPSHOT_MISSING"),
            "wrong environment": (dict(full, environment="dev"), "HOLD_SNAPSHOT_ENVIRONMENT_MISMATCH"),
            "two HELD records": (self.snapshot(self.kcr, other), "HOLD_SET_OTHER_HELD"),
            "no HELD record": (self.snapshot(PB.hold(kind=SC.ROTATION, state=SC.RELEASED, ceremony=PB.C3, successor=PB.S3,
                                                      witness=self.s.head.digest)),
                               "HOLD_SET_NO_HELD"),
            "boolean hold": ({"hold": True}, "HOLD_SNAPSHOT_MALFORMED"),
        }
        for label, (snapshot, reason) in cases.items():
            with self.subTest(label=label):
                result = handler.handle(W.RECOVERY_ADVANCE_EPOCH, {"epochAuthorization": self.eaa,
                                                                   "holdStore": snapshot})
                self.assertEqual((result["status"], result["reason"]), ("REFUSED", reason))

    def test_the_gate_decides_hold_key_epoch_and_authorization(self):
        handler = self.handler()
        initial = PB.initial_hold(witness=self.s.digests["genesis"])
        wrong_key = PB.hold(kind=SC.KEY_COMPROMISE_RECOVERY, predecessor=PB.S3, witness=self.s.digests["holdEngaged"])
        other_reason = self.s.issue_epoch_advance(PB.rec3(), reason="OPERATOR_RECOVERY",
                                                  authorization_id="eaa.pr1s-operator")
        cases = (
            (initial, self.eaa, "HOLD_NOT_COMPROMISE_RECOVERY"),   # INITIAL_CUSTODY HELD: the live PR-1 answer
            (wrong_key, self.eaa, "RECOVERY_SEQUENCE_INVALID"),
            (self.kcr, other_reason, "EPOCH_AUTHORIZATION_REASON_INVALID"),
            (self.kcr, {**self.eaa, "signature": self.eaa["signature"][:-2] + "AA"}, "EPOCH_AUTHORIZATION_NOT_VERIFIED"),
        )
        for hold, authorization, reason in cases:
            with self.subTest(reason=reason):
                result = handler.handle(W.RECOVERY_ADVANCE_EPOCH, {"epochAuthorization": authorization,
                                                                   "holdStore": self.snapshot(hold)})
                self.assertEqual((result["status"], result["reason"]), ("REFUSED", reason))
        for operation in (W.RECOVERY_VOID_CHALLENGE, W.RECOVERY_QUARANTINE_USE):
            result = handler.handle(operation, {"holdStore": self.snapshot(self.kcr)})
            self.assertEqual(result["reason"], "RECOVERY_PHASE_MISMATCH")  # before the witness advanced

    def test_ledger_observation_is_mandatory(self):
        os.unlink(self.ledger_path)
        result = self.handler().handle(W.RECOVERY_ADVANCE_EPOCH, {"epochAuthorization": self.eaa,
                                                                  "holdStore": self.snapshot(self.kcr)})
        self.assertEqual(result["reason"], "AUTHORITY_STATE_MISSING")
        incomplete = self.handler(view=lambda: REC.SignerViewV1(None, (), WR.WitnessStoreObservationV1(()),
                                                                ("WITNESS_ANCHOR_MISSING",)))
        result = incomplete.handle(W.RECOVERY_ADVANCE_EPOCH, {"epochAuthorization": self.eaa,
                                                             "holdStore": self.snapshot(self.kcr)})
        self.assertEqual((result["reason"], result["detail"]), ("SIGNER_INPUTS_INCOMPLETE", "WITNESS_ANCHOR_MISSING"))

    def test_nothing_but_the_three_ledger_operations_is_reachable(self):
        handler = self.handler()
        for operation in ("SIGN", "ISSUE", "ISSUE_OWNER_EVIDENCE", "RESERVE", "CONSUME", "PRIVACY", "REGISTRY_SIGN",
                          "GENERIC_SQL", "GENERIC_LEDGER", "ADVANCE_EPOCH", "VOID_CHALLENGE", "PREPARE", "HEALTH"):
            self.assertEqual(handler.handle(operation, {"holdStore": self.snapshot(self.kcr)})["reason"],
                             "RECOVERY_OPERATION_UNKNOWN")
        self.assertEqual(REC.RECOVERY_OPERATIONS, W.RECOVERY_OPERATIONS)
        self.assertEqual(set(REC.GATE_OPERATIONS.values()), SR.RECOVERY_ALLOWLIST)
        source = (SERVICE / "lilith_authority_dev/recovery.py").read_text(encoding="utf-8")
        for needle in ("evidence_minter", "OwnerActorEvidenceMinterV1", "load_der_private_key", ".sign(", "sqlite",
                       "execute(", "credential", "lilith_authority_signer"):
            self.assertNotIn(needle, source, needle)

    def test_root_peer_only_over_the_owner_socket(self):
        core = CORE.DevAuthoritySignerCoreV1(PRESENT, recovery=self.handler())
        frame = W.encode_frame(W.RECOVERY_VOID_CHALLENGE, {"holdStore": self.snapshot(self.kcr)})
        for peer, served in ((0, True), (990, False), (1001, False)):
            with self.subTest(peer=peer):
                left, right = socket.socketpair()
                left.sendall(frame)
                S.serve_connection(right, core, peer_uid_reader=lambda _c, uid=peer: uid)
                left.settimeout(2)
                try:
                    reply = left.recv(W.MAX_FRAME_BYTES + 8)
                except ConnectionResetError:
                    reply = b""
                left.close()
                self.assertEqual(bool(reply), served)


# ---------------------------------------------------- protocol / core / server ---

class MarkingLagTests(unittest.TestCase):
    """The one tolerated registry-view lag stays narrow (owner-accepted, pre-PR closure).

    Accepted only for ADVANCE_EPOCH, only under a KEY_COMPROMISE_RECOVERY / HELD
    hold, and only when the witness head's own transition is the in-epoch
    COMPROMISE_MARKING of the hold's predecessor from exactly the ledger's
    registry view. Never "a registry may be one version stale".
    """

    def setUp(self):
        self.s = PB.PrepBScenario().mark()
        self.kcr = PB.hold(kind=SC.KEY_COMPROMISE_RECOVERY, witness=self.s.digests["holdEngaged"])

    def view(self, scenario=None):
        scenario = scenario or self.s
        return REC.SignerViewV1(scenario.context(), tuple(scenario.registries), scenario.observation())

    def observation(self, scenario=None):
        return W2.observe_authority_recovery_ledger((scenario or self.s).ledger)

    def reason(self, *, observation=None, view=None, governing=None):
        return REC.marking_lag_reason(observation=observation or self.observation(), view=view or self.view(),
                                      governing=self.kcr if governing is None else governing, profile=PBF.PROFILE)

    def test_the_accepted_marking_lag(self):
        head = WR.classify_witness_store(observation=self.s.observation(), context=self.s.context()).head
        observation = self.observation()
        self.assertEqual(RC.authority_ledger_position_reason(observation, head), REC.MARKING_LAG)
        self.assertEqual((observation.registry_view, head.registry_version), (1, 2))
        self.assertIsNone(self.reason())

    def test_a_lag_of_more_than_the_marking_is_refused(self):
        stale = dataclasses.replace(self.observation(), registry_view=0)
        self.assertEqual(self.reason(observation=stale), "LAG_NOT_EXACT_PREDECESSOR")
        ahead = dataclasses.replace(self.observation(), registry_view=2)
        self.assertEqual(self.reason(observation=ahead), "LAG_NOT_EXACT_PREDECESSOR")

    def test_only_a_held_key_compromise_recovery_of_the_marked_predecessor(self):
        cases = {
            "rotation hold": (PB.hold(kind=SC.ROTATION, witness=self.s.digests["holdEngaged"]),
                              "LAG_HOLD_NOT_COMPROMISE_RECOVERY"),
            "released recovery hold": (PB.hold(kind=SC.KEY_COMPROMISE_RECOVERY, state=SC.RELEASED,
                                               witness=self.s.head.digest), "LAG_HOLD_NOT_COMPROMISE_RECOVERY"),
            "hold naming another predecessor": (PB.hold(kind=SC.KEY_COMPROMISE_RECOVERY, predecessor=PB.S2,
                                                        witness=self.s.digests["holdEngaged"]),
                                                "LAG_HOLD_NOT_COMPROMISE_RECOVERY"),
        }
        for label, (governing, reason) in cases.items():
            with self.subTest(label=label):
                self.assertEqual(self.reason(governing=governing), reason)

    def test_an_ordinary_rotation_lag_is_not_the_marking(self):
        rotated = PBF.rotated()
        self.assertEqual(self.reason(observation=dataclasses.replace(self.observation(rotated), registry_view=1),
                                     view=self.view(rotated)), "LAG_RECOVERY_NOT_MARKED")

    def test_the_marking_must_mark_the_holds_current_predecessor(self):
        real = SR.verify_history

        def other_key(**kwargs):
            history, reason, detail = real(**kwargs)
            last = dataclasses.replace(history.steps[-1], marked_compromised=(PB.S2,))
            return dataclasses.replace(history, steps=history.steps[:-1] + (last,)), reason, detail
        with mock.patch.object(REC.SR, "verify_history", other_key):
            self.assertEqual(self.reason(), "LAG_RECOVERY_NOT_MARKED")

    def test_the_marking_must_be_the_head_transition(self):
        real = SR.verify_history

        def later_step(**kwargs):
            history, reason, detail = real(**kwargs)
            last = history.steps[-1]
            extra = dataclasses.replace(last, witness_version=last.witness_version + 1, marked_compromised=(),
                                        prior_current=None)
            return dataclasses.replace(history, steps=history.steps + (extra,)), reason, detail
        with mock.patch.object(REC.SR, "verify_history", later_step):
            self.assertEqual(self.reason(), "LAG_MARKING_NOT_HEAD_TRANSITION")

    def test_the_tolerance_is_confined_to_the_advance_epoch_branch(self):
        source = (SERVICE / "lilith_authority_dev/recovery.py").read_text(encoding="utf-8")
        branch = source[source.index("if operation == RECOVERY_ADVANCE_EPOCH:"):]
        branch = branch[:branch.index("\n        else:")]
        self.assertEqual(source.count("position == MARKING_LAG"), 1)
        self.assertIn("position == MARKING_LAG", branch)
        # No other signer, witness, or root-tooling module tolerates a stale registry view.
        for tree in ("services/authority-dev/lilith_authority_dev", "services/authority-dev/lilith_authority_root",
                     "services/authority-dev/lilith_authority_host", "services/recovery-witness/lilith_recovery_witness"):
            for path in (ROOT / tree).rglob("*.py"):
                if path.name != "recovery.py":
                    self.assertNotIn("BROKER_REGISTRY_VIEW_STALE", path.read_text(encoding="utf-8"), path)
                    self.assertNotIn("MARKING_LAG", path.read_text(encoding="utf-8"), path)
        self.assertEqual(source.count("BROKER_REGISTRY_VIEW_STALE"), 1)


class SignerSurfaceTests(unittest.TestCase):
    def test_protocol_recovery_payloads_are_closed(self):
        ok = W.parse_frame(W.encode_frame(W.RECOVERY_ADVANCE_EPOCH, {"epochAuthorization": {}, "holdStore": {}}))
        self.assertEqual(ok.operation, W.RECOVERY_ADVANCE_EPOCH)
        for operation, payload in ((W.RECOVERY_VOID_CHALLENGE, {"holdStore": {}, "challengeId": "c1"}),
                                   (W.RECOVERY_QUARANTINE_USE, {}),
                                   (W.RECOVERY_ADVANCE_EPOCH, {"holdStore": {}}),
                                   (W.RECOVERY_VOID_CHALLENGE, {"holdStore": [1]})):
            raw = json.dumps({"operation": operation, "payload": payload, "protocol": W.PROTOCOL,
                              "schemaVersion": 1}, sort_keys=True, separators=(",", ":")).encode()
            with self.assertRaises(W.ProtocolError):
                W.parse_frame(len(raw).to_bytes(4, "big") + raw)

    def test_issuance_stays_unwired_even_with_the_runtime_collaborators(self):
        view = {"readiness": "NOT_READY", "reasons": list(STATE.STRUCTURAL_SELF_VIEW_REASONS)}
        core = CORE.DevAuthoritySignerCoreV1(PRESENT, recovery=object(), self_view=lambda: view)
        import test_authority_dev_foundation as FOUNDATION
        message = W.parse_frame(FOUNDATION.frame(FOUNDATION.envelope(W.ISSUE_OWNER_EVIDENCE,
                                                                     FOUNDATION.issue_payload())))
        result = core.dispatch(message)
        self.assertEqual((result["status"], result["reason"]), ("REFUSED", CORE.SIGNING_NOT_AVAILABLE))
        health = core.health()
        self.assertEqual(health["readiness"], "NOT_READY")
        self.assertIn("ISSUANCE_UNWIRED", health["reasons"])
        self.assertEqual(CORE.DevAuthoritySignerCoreV1(PRESENT).dispatch(
            W.parse_frame(W.encode_frame(W.RECOVERY_VOID_CHALLENGE, {"holdStore": {}}))),
            {"status": "REFUSED", "reason": "RECOVERY_NOT_WIRED"})

    @unittest.skipUnless(POSIX, "POSIX paths")
    def test_self_view_is_always_not_ready_and_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            host = X.Pr1Host(directory).genesis_host()
            view = STATE.signer_view(environment=X.ENV, root=host.root, owner_uid=X.UID)
            reasons = STATE.self_view(view, host.ledger)["reasons"]
            self.assertEqual(reasons, list(STATE.STRUCTURAL_SELF_VIEW_REASONS))
            empty = STATE.signer_view(environment=X.ENV, root=Path(directory) / "nowhere", owner_uid=X.UID)
            def missing():
                raise L.LedgerError("AUTHORITY_STATE_MISSING")
            reasons = STATE.self_view(empty, missing)["reasons"]
            for needed in ("WITNESS_MISSING", "AUTHORITY_STATE_MISSING", "REGISTRY_ROOT_ANCHOR_MISSING",
                           "ISSUANCE_UNWIRED", "CREDENTIAL_INVENTORY_UNOBSERVABLE_BY_SIGNER"):
                self.assertIn(needed, reasons)

    def test_build_core_performs_no_io_and_wires_only_fixed_paths(self):
        core = S.build_core(PRESENT)
        self.assertIsInstance(core._recovery, REC.RecoveryHandlerV1)
        server = (SERVICE / "lilith_authority_dev/server.py").read_text(encoding="utf-8")
        for needle in ("LEDGER_PATH", "open_existing", "witness_client.record_ledger_advance"):
            self.assertIn(needle, server)
        self.assertNotIn("provision", server)  # the signer never creates its ledger


# ----------------------------------------------------------- unit / paths ---

class UnitHardeningTests(unittest.TestCase):
    def test_signer_unit_denies_witness_custody_and_holds(self):
        denied = next(line for line in UNIT.splitlines() if line.startswith("InaccessiblePaths=")).split("=", 1)[1].split()
        for path in ("/etc/credstore.encrypted", "/etc/lilith-authority-custody", "/var/lib/lilith-authority-custody",
                     "/etc/lilith-recovery-witness", "/var/lib/lilith-memory-broker"):
            self.assertIn(path, denied)
        writable = next(line for line in UNIT.splitlines() if line.startswith("ReadWritePaths=")).split("=", 1)[1]
        self.assertEqual(writable, "/var/lib/lilith-authority-dev")
        readable = next(line for line in UNIT.splitlines() if line.startswith("ReadOnlyPaths=")).split("=", 1)[1]
        self.assertIn("/var/lib/lilith-recovery-witness", readable)  # read-only witness verification
        self.assertNotIn("[Install]", UNIT)

    def test_installer_and_host_paths_agree(self):
        import install_authority_dev as I
        self.assertEqual(I.CLI_TARGETS, P.CLI_TARGETS)
        self.assertEqual(I.WITNESS_UNIT_TARGETS, P.WITNESS_UNIT_TARGETS)
        self.assertEqual(I.UNIT_TARGETS, P.AUTHORITY_UNIT_TARGETS)
        for name in ("WITNESS_BLOB", "HOLD_STORE", "AUTHORITY_LEDGER", "WITNESS_STATE", "TRUST_DIR", "REGISTRY_DIR",
                     "OWNER_INPUT_DIR", "GENESIS_PIN_COPY", "AUTHORIZATION_REGISTER_COPY", "REGISTRY_ROOT_ANCHOR",
                     "WITNESS_ANCHOR"):
            self.assertEqual(getattr(I, name), getattr(P, name), name)
        self.assertEqual(I.HOLD_PARENT, P.HOLD_STORE_PARENT)
        self.assertEqual(I.WITNESS_CREDENTIAL_ROOT, P.WITNESS_CREDENTIAL_ROOT)
        self.assertEqual(I.WITNESS_USER, P.WITNESS_USER)
        self.assertEqual(PA.HOLD_STORE_DIRECTORY, P.HOLD_STORE)


# ---------------------------------------------------------- release set ---

class ReleaseIdentityTests(unittest.TestCase):
    def test_one_release_carries_every_runtime_owner(self):
        manifest = RFS.runtime_manifest(ROOT)
        self.assertEqual(manifest, RFS.runtime_manifest(ROOT))
        self.assertEqual(manifest["status"], "SOURCE_PREPARED_NOT_INSTALLED")
        files = manifest["files"]
        for member in ("lilith_authority_dev/ledger.py", "lilith_authority_dev/recovery.py",
                       "lilith_recovery_witness/writer.py", "lilith_authority_root/hold_store.py",
                       "lilith_authority_host/paths.py", "lilith_owner_memory/successor_readiness.py",
                       "assets/lilith-recovery-witness.service"):
            self.assertIn(member, files)
        import install_authority_dev as I
        self.assertEqual(frozenset(RFS.RUNTIME_SOURCE_MAP.values()), I.RUNTIME_PATHS)
        self.assertEqual(set(RFS.CLI_SOURCES), set(I.CLI_TARGETS))
        members = {**files, **{name: hashlib.sha256(data).hexdigest() for name, data in RFS.cli_payloads(ROOT).items()}}
        self.assertEqual(manifest["runtimeDigests"], {
            "authority": PA.runtime_files_digest(members, prefixes=PA.AUTHORITY_RUNTIME_PREFIXES),
            "witness": PA.runtime_files_digest(members, prefixes=PA.WITNESS_RUNTIME_PREFIXES),
            "rootTooling": PA.runtime_files_digest(members, prefixes=PA.ROOT_TOOLING_PREFIXES)})
        self.assertEqual(manifest["witnessManifestSha256"], RFS.WITNESS.runtime_manifest(ROOT)["runtimeSha256"])

    def test_shared_contracts_are_pinned(self):
        for path, digest in RFS.SHARED_HASHES.items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest, path)
        for name in ("authority_verifier", "rotation_contracts", "witness_readiness", "successor_custody",
                     "successor_readiness", "recovery_contracts", "authority_ledger_journal", "pr1_bootstrap",
                     "pr1_acceptance"):
            self.assertIn(f"services/owner-memory-control/lilith_owner_memory/{name}.py", RFS.SHARED_HASHES)

    def test_no_second_executable_release_is_retained(self):
        installer = (SERVICE / "ceremony/install_authority_dev.py").read_text(encoding="utf-8")
        self.assertEqual(installer.count('failures.append("RELEASE_SET")'), 1)
        self.assertIn("shutil.rmtree(doomed)", installer)  # RR-25: the old executable release is removed

    def test_activation_stays_dark(self):
        texts = [(SERVICE / relative).read_text(encoding="utf-8") for relative in (
            "lilith_authority_dev/core.py", "lilith_authority_dev/recovery.py", "lilith_authority_root/hold_store.py",
            "lilith_authority_root/verifier.py", "ceremony/install_authority_dev.py")]
        for text in texts:
            for needle in ("activation grant", "ACTIVATION=ACCEPTED", "lilith-canonical-activation", "sudoers"):
                self.assertNotIn(needle, text)
        # E-19 (record slice-15b2b-b1b3e-e19-release-maintenance.md): the complete host line, exact.
        self.assertEqual(PA.ACTIVATION_DARK_LINE,
                         "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false")


if __name__ == "__main__":
    unittest.main()
