"""15B2b-B1b-3e PR-1S root tooling tests (repository only).

The RR-34 hold store, the independent root verifier and RR-38 package, the
installed-release observer, the ledger and genesis tools, the fixed CLIs,
the K-WIT keygen form, the owner-workstation tool, and the fixed denial
proof. Every host is a temporary directory; every key is a TEST_ONLY
fixture seed or a local pipeline key; nothing contacts DEV or PROD.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import pr1s_fixtures as X
from pr1s_fixtures import F, PB, J, PA, B, SC, WR, RC

import install_authority_dev as I
import lilith_authority_keygen_dev as G
import lilith_authority_owner_dev as OWNER
import test_custody_preparation as L2
from lilith_authority_host import paths as P
from lilith_authority_root import cli as CLI
from lilith_authority_root import genesis as GEN
from lilith_authority_root import ledger_tool as LT
from lilith_authority_root import observers as O
from lilith_authority_root import verifier as V
from lilith_authority_root.hold_store import HoldStoreError, HoldStoreV1
from lilith_owner_memory import successor_readiness as SR
from lilith_recovery_witness import core as WCORE
from lilith_recovery_witness import protocol as WP

POSIX = X.POSIX
ROOT = X.ROOT
ELIGIBILITY, FULL = SR.HOLD_RELEASE_ELIGIBILITY, SR.FULL_READINESS


def _denial_module():
    spec = importlib.util.spec_from_file_location("authority_custody_denial_proof",
                                                  ROOT / "scripts/authority_custody_denial_proof.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DENIAL = _denial_module()


# ------------------------------------------------------------ hold store ---

@unittest.skipUnless(POSIX, "ownership and modes are POSIX")
class HoldStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.host = X.Pr1Host(self.directory.name)
        self.host.install_public()
        self.host.provision_ledger()
        self.host.install_owner_inputs(self.host.candidate().digest)
        self.host.bootstrap()
        self.store = self.host.path(P.HOLD_STORE)

    def tearDown(self):
        self.directory.cleanup()

    def test_empty_store_then_the_one_initial_held_record(self):
        empty = self.host.holds.observe()
        self.assertEqual(empty.observation.entries, ())
        self.assertEqual(empty.listing_digest, hashlib.sha256(b"[]").hexdigest())
        record = self.host.create_held()
        self.assertEqual((record["transitionKind"], record["state"], record["ceremonyId"]),
                         (SC.INITIAL_CUSTODY, SC.HELD, SC.initial_ceremony_id(X.ENV, SC.INITIAL_KEY_ID)))
        self.assertEqual(record["observedWitnessDigest"], self.host.inputs().genesis_pin["genesisWitnessDigest"])
        name = SC.hold_record_name(record["ceremonyId"])
        self.assertEqual(os.listdir(self.store), [name])
        self.assertEqual(os.stat(self.store / name).st_mode & 0o777, 0o600)
        self.assertEqual(sorted(os.listdir(self.host.path(P.HOLD_STORE_PARENT))), ["holds"])  # no leftover scratch
        observed = self.host.holds.observe()
        self.assertEqual([e.name for e in observed.observation.entries], [name])
        self.assertEqual(observed.snapshot["listingDigest"], observed.listing_digest)
        self.assertEqual(PA.parse_hold_snapshot(observed.snapshot, environment=X.ENV)[0], observed.observation)
        with self.assertRaises(HoldStoreError) as caught:
            self.host.create_held()  # RR-40: never recreated
        self.assertEqual(caught.exception.reason, "HOLD_STORE_NOT_EMPTY")

    def test_every_entry_is_judged(self):
        self.host.create_held()
        name = os.listdir(self.store)[0]
        cases = {
            "dot file": lambda: (self.store / ".hidden").write_bytes(b"x"),
            "temp file": lambda: (self.store / f"{name}.tmp").write_bytes(b"x"),
            "subdirectory": lambda: (self.store / "nested").mkdir(),
            "symlink": lambda: os.symlink(self.store / name, self.store / ("f" * 64 + ".json")),
        }
        for label, plant in cases.items():
            with self.subTest(label=label):
                plant()
                with self.assertRaises(HoldStoreError) as caught:
                    self.host.holds.observe()
                self.assertEqual(caught.exception.reason, "HOLD_STORE_ENTRY_INVALID")
                for extra in os.listdir(self.store):
                    if extra != name:
                        path = self.store / extra
                        path.rmdir() if path.is_dir() and not path.is_symlink() else path.unlink()
        os.chmod(self.store / name, 0o644)
        with self.assertRaises(HoldStoreError) as caught:
            self.host.holds.observe()
        self.assertEqual(caught.exception.reason, "HOLD_STORE_ENTRY_INVALID")
        os.chmod(self.store / name, 0o600)
        misnamed = self.store / ("e" * 64 + ".json")
        (self.store / name).rename(misnamed)
        with self.assertRaises(HoldStoreError) as caught:
            self.host.holds.observe()
        self.assertEqual(caught.exception.reason, "HOLD_STORE_RECORDS_INVALID")
        misnamed.rename(self.store / name)
        (self.host.path(P.HOLD_STORE_PARENT) / "other").mkdir()
        with self.assertRaises(HoldStoreError) as caught:
            self.host.holds.observe()
        self.assertEqual(caught.exception.reason, "HOLD_PARENT_UNEXPECTED_ENTRY")
        (self.host.path(P.HOLD_STORE_PARENT) / "other").rmdir()
        os.chmod(self.store, 0o755)
        with self.assertRaises(HoldStoreError) as caught:
            self.host.holds.observe()
        self.assertEqual(caught.exception.reason, "HOLD_DIRECTORY_UNSAFE")
        os.chmod(self.store, 0o700)
        wrong_owner = HoldStoreV1(environment=X.ENV, root=self.host.root, owner_uid=X.UID + 1, owner_gid=X.GID)
        with self.assertRaises(HoldStoreError):
            wrong_owner.observe()

    def test_observation_is_lock_consistent(self):
        import fcntl
        self.host.create_held()
        fd = os.open(self.store, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            with self.assertRaises(HoldStoreError) as caught:
                self.host.holds.observe()
            self.assertEqual(caught.exception.reason, "HOLD_STORE_BUSY")
        finally:
            os.close(fd)

    def test_forward_only_bounded_writes(self):
        self.host.create_held()
        held = self.host.holds.observe()
        # A released custody-debt needs its released successor ceremony first.
        with self.assertRaises(HoldStoreError) as caught:
            self.host.holds.create_custody_debt_held(ordinal=2, witness_store=self.host.witness_store(),
                                                     context=self.host.context())
        self.assertEqual(caught.exception.reason, "HOLD_CEREMONY_ABSENT")
        with self.assertRaises(HoldStoreError) as caught:
            self.host.holds.create_successor_held(kind=SC.INITIAL_CUSTODY, ordinal=2,
                                                  witness_store=self.host.witness_store(),
                                                  context=self.host.context(), registries=self.host.inputs().registries)
        self.assertEqual(caught.exception.reason, "HOLD_ARGUMENT_INVALID")
        record = self.host.holds.create_successor_held(kind=SC.ROTATION, ordinal=2,
                                                       witness_store=self.host.witness_store(),
                                                       context=self.host.context(),
                                                       registries=self.host.inputs().registries)
        self.assertEqual((record["expectedPredecessorKeyId"], record["expectedSuccessorKeyId"]), (PB.P0, PB.S2))
        with self.assertRaises(HoldStoreError) as caught:
            self.host.holds.create_successor_held(kind=SC.ROTATION, ordinal=2, witness_store=self.host.witness_store(),
                                                  context=self.host.context(), registries=self.host.inputs().registries)
        self.assertEqual(caught.exception.reason, "HOLD_CEREMONY_EXISTS")
        self.assertEqual(len(self.host.holds.observe().observation.entries), 2)
        self.assertNotEqual(self.host.holds.observe().listing_digest, held.listing_digest)
        maintenance = self.host.holds.create_maintenance_held(
            authorization_id="rhaa.pr1s-maint-1", target_registry=PB.rot2(), witness_store=self.host.witness_store(),
            context=self.host.context(), registries=self.host.inputs().registries)
        self.assertEqual(maintenance["transitionKind"], SC.REGISTRY_MAINTENANCE)
        self.assertEqual(maintenance["expectedPredecessorKeyId"], maintenance["expectedSuccessorKeyId"])
        source = (ROOT / "services/authority-dev/lilith_authority_root/hold_store.py").read_text(encoding="utf-8")
        for needle in ("json.loads(argv", "def write_record", "def write_json", "shutil.rmtree", "os.unlink"):
            self.assertNotIn(needle, source)


# ------------------------------------------------------ root verifier / package ---

@unittest.skipUnless(POSIX, "ownership and modes are POSIX")
class RootVerifierTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.host = X.Pr1Host(directory).genesis_host()
        with X.stand_in_wheels() as wheels:
            self.payloads = X.release_payloads(wheels)
        self.manifest = X.install_release(self.host.root, X.RELEASE_SHA, self.payloads)
        self.manifest_sha = hashlib.sha256(I.canonical(self.manifest)).hexdigest()
        self.first = X.current_document(self.host)

    def tearDown(self):
        self.stack.close()

    def evaluate(self, mode=ELIGIBILITY, *, run=None, health=X.health_p0, hold=None, **inputs):
        owner = V.parse_verifier_inputs(X.verifier_inputs(self.host, manifest_sha256=self.manifest_sha,
                                                          first_current=self.first, **inputs))
        return V.evaluate(mode, owner, root=self.host.root, owner_uid=X.UID, owner_gid=X.GID, health=health,
                          run=run or X.fake_systemctl(), hold=hold)

    def test_pr2_and_pr3_absent_is_not_ready_never_a_default_pass(self):
        result = self.evaluate()
        self.assertEqual(result.status, "NOT_READY")
        failing = {name for name, outcome in result.checks.items() if outcome.status != "PASS"}
        self.assertEqual(failing, {"E18_OFFHOST_REPRODUCTION_INPUTS", "E20_SNAPSHOT_INVENTORY", "E21_OFFHOST_REGISTER"})
        self.assertEqual(result.checks["E20_SNAPSHOT_INVENTORY"].reason, "SNAPSHOT_INVENTORY_ABSENT_PR2")
        self.assertEqual(result.checks["E21_OFFHOST_REGISTER"].reason, "OFFHOST_REGISTER_ABSENT_PR3")
        self.assertTrue(result.readiness.ready)  # HOLD_RELEASE_ELIGIBILITY itself is READY
        for flag in ("authorityGranted", "activationGranted", "issuanceWired", "wholeHostRollbackProtected"):
            self.assertIs(result.package[flag], False, flag)

    def test_eligibility_ready_with_every_input_and_a_stable_digest(self):
        first = self.evaluate(with_pr2=True, with_pr3=True)
        self.assertEqual(first.status, "READY", first.reasons)
        self.assertEqual(first.package_digest, self.evaluate(with_pr2=True, with_pr3=True).package_digest)
        self.assertEqual(first.package_digest, PA.package_digest(first.package))
        self.assertNotEqual(first.package_digest, hashlib.sha256(json.dumps(first.package).encode()).hexdigest())
        self.assertEqual(first.package["evidence"]["holdStore"]["records"],
                         [[SC.initial_ceremony_id(X.ENV, SC.INITIAL_KEY_ID), SC.INITIAL_CUSTODY, SC.HELD]])
        self.assertEqual(first.package["evidence"]["authorityLedger"]["sequence"], 1)
        self.assertEqual(first.package["nonclaims"], list(PA.PR1_NONCLAIMS))

    def test_every_security_relevant_change_changes_the_package(self):
        base = self.evaluate(with_pr2=True, with_pr3=True).package_digest
        changes = {
            "unit state": dict(run=X.fake_systemctl({"lilith-recovery-witness.service": {"NeedDaemonReload": "yes"}})),
            "health": dict(health=lambda: {**X.health_p0(), "publicKeySha256": "0" * 64}),
            "proof": dict(proofs={**X.proofs(), "SECRET_HYGIENE": X.proof("other")}),
            "activation": dict(activation={"line": "ACTIVATION=ACCEPTED", "b1cUnchanged": True}),
            "pr2": dict(snapshotInventory={**X.snapshot_inventory(), "recordSha256": "1" * 64}),
        }
        for label, change in changes.items():
            with self.subTest(label=label):
                kwargs = {k: v for k, v in change.items() if k in ("run", "health")}
                inputs = {k: v for k, v in change.items() if k not in ("run", "health")}
                result = self.evaluate(with_pr2=True, with_pr3=True, **kwargs, **inputs)
                self.assertNotEqual(result.package_digest, base, label)
        blob = self.host.path(P.CURRENT_SLOT)
        os.chmod(blob, 0o600)
        os.utime(blob, ns=(1, 1))
        changed = self.evaluate(with_pr2=True, with_pr3=True)
        self.assertNotEqual(changed.package_digest, base)
        self.assertEqual(changed.checks["E04_CURRENT_PRESERVED"].reason, "CURRENT_MTIME_CHANGED")

    def test_release_requires_the_approved_digest_of_a_current_rerun(self):
        eligibility = self.evaluate(with_pr2=True, with_pr3=True)
        stale = self.evaluate()
        rerun = lambda held: self.evaluate(with_pr2=True, with_pr3=True, hold=held)  # noqa: E731
        with self.assertRaises(HoldStoreError) as caught:
            self.host.holds.release_initial(approved_package_digest=stale.package_digest, rerun=rerun,
                                            witness_store=self.host.witness_store(), context=self.host.context())
        self.assertEqual((caught.exception.reason, caught.exception.detail),
                         ("HOLD_RELEASE_NOT_PERMITTED", "PACKAGE_DIGEST_MISMATCH"))
        with self.assertRaises(HoldStoreError) as caught:
            self.host.holds.release_initial(approved_package_digest="nope", rerun=rerun,
                                            witness_store=self.host.witness_store(), context=self.host.context())
        self.assertEqual(caught.exception.detail, "APPROVED_DIGEST_MALFORMED")
        self.assertEqual(PA.release_decision(None, eligibility).reason, "APPROVED_DIGEST_MISSING")
        self.assertEqual(PA.release_decision(stale.package_digest, stale).reason, "PACKAGE_NOT_READY")
        self.assertEqual(self.evaluate(FULL, with_pr2=True, with_pr3=True).checks["E16_HOLD_STORE"].reason,
                         "CEREMONY_HOLD:CEREMONY_HOLD_HELD")
        released = self.host.holds.release_initial(approved_package_digest=eligibility.package_digest, rerun=rerun,
                                                   witness_store=self.host.witness_store(),
                                                   context=self.host.context())
        self.assertEqual((released["state"], released["reason"]), (SC.RELEASED, SC.OWNER_RELEASE_AFTER_ELIGIBILITY))
        full = self.evaluate(FULL, with_pr2=True, with_pr3=True)
        self.assertEqual(full.status, "READY", full.reasons)
        self.assertTrue(full.readiness.facts["issuanceReady"])  # readiness only
        self.assertIs(full.package["issuanceWired"], False)    # RR-39: issuance stays unwired
        self.assertEqual(PA.release_decision(full.package_digest, full).reason, "PACKAGE_MODE_NOT_ELIGIBILITY")
        with self.assertRaises(HoldStoreError):
            self.host.holds.release_initial(approved_package_digest=eligibility.package_digest, rerun=rerun,
                                            witness_store=self.host.witness_store(), context=self.host.context())

    def test_offhost_material_must_bind_what_the_host_shows(self):
        for field, value, reason in (("genesisPinDigest", "0" * 64, "OFFHOST_PIN_MISMATCH"),
                                     ("kWitPublicKeySha256", "0" * 64, "OFFHOST_KWIT_MISMATCH"),
                                     ("releaseManifestSha256", "0" * 64, "OFFHOST_RELEASE_PROVENANCE_MISMATCH"),
                                     ("authorizationIds", ["rhaa.x"], "OFFHOST_MATERIAL_UNAVAILABLE")):
            with self.subTest(field=field):
                material = X.offhost_material(self.host, manifest_sha256=self.manifest_sha, **{field: value})
                result = self.evaluate(with_pr2=True, offHostMaterial=material)
                self.assertEqual(result.checks["E18_OFFHOST_REPRODUCTION_INPUTS"].reason, reason)

    def test_installed_release_is_checked_byte_for_byte(self):
        top = self.host.root / f"opt/lilith-authority-dev/releases/{X.RELEASE_SHA}"
        observe = lambda: O.observe_installed_release(self.host.root, release_sha=X.RELEASE_SHA,  # noqa: E731
                                                      host_targets=tuple(P.RELEASE_HOST_TARGETS.values()))
        verify = lambda observation: PA.verify_installed_release(  # noqa: E731
            observation, release_sha=X.RELEASE_SHA, attested_manifest_sha256=self.manifest_sha,
            host_targets={t: m for m, t in P.RELEASE_HOST_TARGETS.items()}, owner=(X.UID, X.GID))
        self.assertTrue(verify(observe()).verified, verify(observe()).reason)
        core = top / "lilith_authority_dev/core.py"
        saved = core.read_bytes()
        core.write_bytes(saved + b"# x\n")
        self.assertEqual(verify(observe()).reason, "RELEASE_TREE_FILE_MISMATCH")
        core.write_bytes(saved)
        (top / "lilith_authority_dev/extra.py").write_bytes(b"")
        self.assertEqual(verify(observe()).reason, "RELEASE_TREE_EXTRA_FILE")
        (top / "lilith_authority_dev/extra.py").unlink()
        (top.parent / ("2" * 40)).mkdir()
        self.assertEqual(verify(observe()).reason, "RELEASE_SET_UNEXPECTED")
        (top.parent / ("2" * 40)).rmdir()
        cli = self.host.path(P.HOLD_CLI)
        cli.write_bytes(b"#!/bin/false\n")
        self.assertEqual((verify(observe()).reason, verify(observe()).detail), ("HOST_FILE_BYTES_MISMATCH", P.HOLD_CLI))
        wrong = PA.verify_installed_release(observe(), release_sha=X.RELEASE_SHA, attested_manifest_sha256="0" * 64,
                                            host_targets={}, owner=(X.UID, X.GID))
        self.assertEqual(wrong.reason, "RELEASE_MANIFEST_HASH_MISMATCH")

    def test_verifier_is_read_only(self):
        def snapshot():
            return {str(p.relative_to(self.host.root)): (p.stat().st_mtime_ns, p.stat().st_ino)
                    for p in self.host.root.rglob("*") if not p.is_symlink()}
        before = snapshot()
        self.evaluate(with_pr2=True, with_pr3=True)
        self.evaluate(FULL)
        self.assertEqual(snapshot(), before)
        source = (ROOT / "services/authority-dev/lilith_authority_root/verifier.py").read_text(encoding="utf-8")
        for needle in ("create_initial_held", "release_initial", "append_recovery", "provision", "sign(",
                       "open(", "write_bytes", "systemd-creds"):
            self.assertNotIn(needle, source, needle)


# ------------------------------------------------------ ledger / genesis tools ---

@unittest.skipUnless(POSIX, "ownership and modes are POSIX")
class LedgerAndGenesisToolTests(unittest.TestCase):
    def test_ledger_provisioning_is_two_halves_and_one_time(self):
        with tempfile.TemporaryDirectory() as directory:
            host = X.Pr1Host(directory).install_public()
            os.rmdir(host.path(P.AUTHORITY_STATE))
            calls = []

            def as_signer(version):
                # The real signer half (M-B6 remediation T-1): it re-verifies the installed registry and
                # provisions the ledger as the signer uid. The signer half refuses euid 0 by design, so a
                # root test run provisions through the same durable ledger call directly instead.
                calls.append(version)
                if X.UID != 0:
                    observed = LT.provision_as_signer(environment=X.ENV, registry_version=version, root=host.root,
                                                      owner_uid=X.UID, euid=X.UID, signer_uid=X.UID)
                    self.assertEqual((observed.sequence, observed.head), J.initial_position(host.registry))
                else:
                    from lilith_authority_dev.ledger import DurableAuthorityLedgerV1
                    DurableAuthorityLedgerV1.provision(host.path(P.AUTHORITY_LEDGER), environment=X.ENV,
                                                       genesis=J.genesis_op(host.registry), expected_uid=X.UID)
                return 0
            with self.assertRaises(LT.LedgerToolError) as caught:
                LT.provision(environment=X.ENV, registry_version=1, euid=1000, signer_uid=X.UID, signer_gid=X.GID,
                             run_as_signer=as_signer, root=host.root, owner_uid=X.UID, chown=False)
            self.assertEqual(caught.exception.reason, "LEDGER_TOOL_NOT_ROOT")
            result = LT.provision(environment=X.ENV, registry_version=1, euid=0, signer_uid=X.UID, signer_gid=X.GID,
                                  run_as_signer=as_signer, root=host.root, owner_uid=X.UID, chown=False)
            self.assertEqual((result["stateDirectory"], result["ledgerSequence"]), ("CREATED", 1))
            self.assertEqual(result["ledgerHead"], J.initial_position(host.registry)[1])
            self.assertEqual(calls, [1])
            self.assertEqual(os.stat(host.path(P.AUTHORITY_STATE)).st_mode & 0o777, 0o700)
            with self.assertRaises(LT.LedgerToolError) as caught:
                LT.provision(environment=X.ENV, registry_version=1, euid=0, signer_uid=X.UID, signer_gid=X.GID,
                             run_as_signer=as_signer, root=host.root, owner_uid=X.UID, chown=False)
            self.assertEqual(caught.exception.reason, "LEDGER_TOOL_ALREADY_PROVISIONED")
            with self.assertRaises(LT.LedgerToolError) as caught:
                LT.provision_as_signer(environment=X.ENV, registry_version=1, root=host.root, owner_uid=X.UID,
                                       euid=0, signer_uid=X.UID)
            self.assertEqual(caught.exception.reason, "LEDGER_TOOL_NOT_SIGNER")
            with self.assertRaises(LT.LedgerToolError) as caught:
                LT.verified_genesis_op(environment=X.ENV, registry_version=2, root=host.root, owner_uid=X.UID)
            self.assertEqual(caught.exception.reason, "LEDGER_TOOL_REGISTRY_NOT_INSTALLED")

    def test_genesis_tool_pins_before_commit_through_the_witness(self):
        with tempfile.TemporaryDirectory() as directory:
            host = X.Pr1Host(directory).install_public()
            host.provision_ledger()
            built, _inputs, _ledger = GEN.candidate(environment=X.ENV, registry_version=1, updated_at=X.T_GENESIS,
                                                    root=host.root, owner_uid=X.UID)
            report = GEN.candidate_report(built)
            self.assertEqual(report["pin"]["genesisWitnessDigest"], built.digest)
            self.assertIs(report["genesis"], False)

            def witness_owner(operation, payload):
                core = WCORE.RecoveryWitnessCoreV1(writer=host.writer(), storage=host.storage, inputs=host.inputs,
                                                   clock=lambda: X.T_GENESIS)
                return core.dispatch(WP.OWNER, WP.parse_frame(WP.encode_frame(operation, payload), role=WP.OWNER))
            host.install_owner_inputs("0" * 64)
            with self.assertRaises(GEN.GenesisToolError) as caught:
                GEN.bootstrap(environment=X.ENV, registry_version=1, updated_at=X.T_GENESIS,
                              witness_owner=witness_owner, root=host.root, owner_uid=X.UID)
            self.assertEqual(caught.exception.reason, "GENESIS_PIN_NOT_CANDIDATE")
            self.assertEqual(os.listdir(host.path(P.WITNESS_STATE)), [])  # nothing reached the witness
            host.install_owner_inputs(built.digest)
            result = GEN.bootstrap(environment=X.ENV, registry_version=1, updated_at=X.T_GENESIS,
                                   witness_owner=witness_owner, root=host.root, owner_uid=X.UID)
            self.assertEqual((result["genesisDigest"], result["pinned"]), (built.digest, True))
            with self.assertRaises(GEN.GenesisToolError) as caught:
                GEN.bootstrap(environment=X.ENV, registry_version=1, updated_at=X.T_GENESIS,
                              witness_owner=witness_owner, root=host.root, owner_uid=X.UID)
            self.assertEqual(caught.exception.reason, "GENESIS_WITNESS_REFUSED")


# ------------------------------------------------------------ fixed CLIs ---

class FixedCliTests(unittest.TestCase):
    def run_cli(self, name, argv, euid=0):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = CLI.main(name, argv, euid=euid)
        return code, err.getvalue()

    def test_closed_forms_and_root_only(self):
        for name in CLI.COMMANDS:
            code, err = self.run_cli(name, ["--help"], euid=1000)
            self.assertEqual(code, 2)
            self.assertIn("REFUSED", err)
        self.assertIn("NOT_ROOT", self.run_cli("lilith-authority-hold-dev", ["observe"], euid=1000)[1])
        for argv in (["release-initial", "not-a-digest", "/x"], ["create-successor-held", "INITIAL_CUSTODY", "2"],
                     ["create-successor-held", "ROTATION", "02"], ["create-maintenance-held", "../x", "2"],
                     ["write", "{}"], ["release", "x"]):
            code, err = self.run_cli("lilith-authority-hold-dev", argv)
            self.assertEqual(code, 2, argv)
        self.assertIn("UNKNOWN_CLI", self.run_cli("lilith-authority-sign-dev", [])[1])
        self.assertEqual(set(CLI.COMMANDS), {path.rsplit("/", 1)[1] for path in P.FIXED_CLIS} -
                         {"lilith-authority-keygen-dev"})

    def test_wrappers_import_only_the_selected_release(self):
        for name in CLI.COMMANDS:
            text = (ROOT / "services/authority-dev/bin" / name).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("#!/opt/lilith-authority-dev/current/venv/bin/python -IB\n"))
            self.assertIn('sys.path.insert(0, "/opt/lilith-authority-dev/current")', text)
            self.assertIn(f'main("{name}", sys.argv[1:])', text)
        source = (ROOT / "services/authority-dev/lilith_authority_root/cli.py").read_text(encoding="utf-8")
        for needle in ('"start"', '"enable"', "daemon-reload", "systemd-creds", ".sign(", "eval(", "exec(",
                       "shell=True"):
            self.assertNotIn(needle, source, needle)


# -------------------------------------------------------- K-WIT keygen form ---

@unittest.skipUnless(POSIX, "owner and mode semantics are POSIX")
class WitnessKeygenTests(unittest.TestCase):
    def ready(self, directory):
        host = L2.FakeHost(directory)
        host.systemd_creds_setup()
        store = host.root / "etc/credstore.encrypted"
        store.mkdir(mode=0o700)
        os.chmod(store, 0o700)
        blob = store / "lilith-authority-dev.owner-actor.cred"
        blob.write_bytes(b"TEST_ONLY stand-in CURRENT")
        os.chmod(blob, 0o600)
        for path in (G.WITNESS_PARENT, G.WITNESS_CREDENTIAL_DIR):
            (host.root / path.lstrip("/")).mkdir(mode=0o700)
            os.chmod(host.root / path.lstrip("/"), 0o700)
        return host

    def preflight(self, host, **overrides):
        value = dict(euid=0, isolated=True, hostname="lilith-dev-01")
        value.update(overrides)
        return G.witness_preflight(host.keygen_host(), **value)

    def test_fixed_identity_matches_the_witness_profile(self):
        self.assertEqual(G.WITNESS_KEY_ID, B.WITNESS_KEY_ID)
        self.assertEqual(G.WITNESS_CREDENTIAL_NAME, B.WITNESS_CREDENTIAL_NAME)
        self.assertEqual(G.WITNESS_BLOB_PATH, B.WITNESS_CREDENTIAL_PATH)
        self.assertEqual(G.WITNESS_BLOB_PATH, P.WITNESS_BLOB)
        self.assertEqual(G.WITNESS_ENCRYPT_ARGV, ("/usr/bin/systemd-creds", "encrypt", "--with-key=host",
                                                  "--name=recovery-witness-signing-key", "-", "-"))
        self.assertNotEqual(G.WITNESS_CREDENTIAL_NAME, G.CREDENTIAL_NAME)
        self.assertFalse(G.WITNESS_BLOB_PATH.startswith(G.CREDSTORE))
        self.assertEqual(G.WITNESS_PUBLICATION_TYPE, B.WITNESS_PUBLICATION_TYPE)
        self.assertNotEqual(G.WITNESS_PUBLICATION_TYPE, G.PUBLICATION_TYPE)
        for argv in (["witness", "2"], ["witness", "--force"], ["witness", "--output", "/tmp/k"], ["WITNESS"]):
            with self.assertRaises(G.Refused):
                G.parse_argv(argv)

    def test_the_ceremony_writes_only_the_k_wit_blob_and_proves_current_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            machine_id, before = self.preflight(host)
            seen = []
            result = G.witness_ceremony(host.keygen_host(), machine_id, before, key_factory=L2.pipeline_key,
                                        encrypt=L2.fake_encrypt(seen))
            blob = host.root / G.WITNESS_BLOB_PATH.lstrip("/")
            self.assertEqual(os.stat(blob).st_mode & 0o777, 0o600)
            self.assertEqual(result, B.witness_publication(
                L2.pipeline_key().public_key().public_bytes(L2.Encoding.Raw, L2.PublicFormat.Raw), blob.read_bytes(),
                machine_id))
            self.assertEqual(sorted(os.listdir(host.root / "etc/credstore.encrypted")),
                             ["lilith-authority-dev.owner-actor.cred"])  # the K-ACT credstore is untouched
            self.assertEqual(G.current_facts(host.keygen_host()), before)
            printed = G.canonical(result)
            for marker in (L2.PIPELINE_KEY_BYTES, seen[0]):
                self.assertNotIn(marker, printed)
                self.assertNotIn(marker.hex().encode(), printed)
            with self.assertRaises(G.Refused) as caught:
                self.preflight(host)
            self.assertEqual(caught.exception.reason, "WITNESS_CREDENTIAL_ALREADY_PRESENT")
            with self.assertRaises(G.Failed) as caught:
                G.write_witness_blob(host.keygen_host(), b"again")
            self.assertEqual(caught.exception.reason, "WITNESS_CREDENTIAL_ALREADY_PRESENT")

    def test_preconditions(self):
        cases = {
            "CREDSTORE_NOT_EXACTLY_CURRENT": lambda h: (h.root / "etc/credstore.encrypted/other.cred").write_bytes(b"x"),
            "WITNESS_PARENT_UNEXPECTED_ENTRY": lambda h: (h.root / "etc/lilith-recovery-witness/extra").mkdir(),
            "WITNESS_CREDENTIAL_DIR_CUSTODY": lambda h: os.chmod(h.root / "etc/lilith-recovery-witness/credentials",
                                                                 0o755),
            "WITNESS_PARENT_CUSTODY": lambda h: os.chmod(h.root / "etc/lilith-recovery-witness", 0o755),
            "CURRENT_ABSENT": lambda h: (h.root / "etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred")
            .rename(h.root / "etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred.x") or
            (h.root / "etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred.x").rename(
                h.root / "etc/credstore.encrypted/zz"),
        }
        for reason, damage in cases.items():
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                host = self.ready(directory)
                damage(host)
                with self.assertRaises(G.Refused) as caught:
                    self.preflight(host)
                if reason == "CURRENT_ABSENT":
                    self.assertEqual(caught.exception.reason, "CREDSTORE_NOT_EXACTLY_CURRENT")
                else:
                    self.assertEqual(caught.exception.reason, reason)
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as elsewhere:
            host = self.ready(directory)
            credentials = host.root / "etc/lilith-recovery-witness/credentials"
            credentials.rmdir()
            os.symlink(elsewhere, credentials)
            with self.assertRaises(G.Refused):
                self.preflight(host)
            self.assertEqual(os.listdir(elsewhere), [])
        with tempfile.TemporaryDirectory() as directory:
            host = self.ready(directory)
            for overrides, reason in ((dict(euid=1000), "NOT_ROOT"), (dict(hostname="lilith-prod-01"), "NOT_DEV_HOST"),
                                      (dict(isolated=False), "INTERPRETER_NOT_ISOLATED")):
                with self.assertRaises(G.Refused) as caught:
                    self.preflight(host, **overrides)
                self.assertEqual(caught.exception.reason, reason)

    def test_keygen_source_stays_closed(self):
        code = L2.code_only(L2.KEYGEN_SOURCE)
        for needle in ("PRIVACY", '"prod"', "argparse", "Encoding.PEM", "OpenSSH", "from_private_bytes",
                       "SEEDS", "TEST_ONLY", "synthetic_", ".sign(", "socket", "sqlite", "registry",
                       "lilith_owner_memory", "load_der"):
            self.assertNotIn(needle, code, needle)


# ------------------------------------------------------ owner workstation tool ---

@unittest.skipUnless(POSIX, "file modes are POSIX")
class OwnerToolTests(unittest.TestCase):
    def test_root_keygen_registry_and_off_host_reproduction(self):
        with tempfile.TemporaryDirectory() as directory:
            key_path = Path(directory) / "k-root.der"
            anchor = OWNER.root_keygen(key_path, passphrase=b"TEST_ONLY passphrase 123",
                                       key_factory=L2.pipeline_key)["registryRoot"]
            self.assertEqual(os.stat(key_path).st_mode & 0o777, 0o600)
            self.assertNotIn(L2.PIPELINE_KEY_BYTES, key_path.read_bytes())  # encrypted at rest
            with self.assertRaises(FileExistsError):
                OWNER.root_keygen(key_path, passphrase=b"TEST_ONLY passphrase 123", key_factory=L2.pipeline_key)
            with self.assertRaises(OWNER.OwnerToolError):
                OWNER.root_keygen(Path(directory) / "short.der", passphrase=b"short")
            publication = copy.deepcopy(PB.publication(PB.P0, environment="dev"))
            key = OWNER._root_key(key_path, b"TEST_ONLY passphrase 123")
            registry = OWNER.registry_v1(key, publication, epoch_random="1" * 32, policy_version="policy.dev-synthetic.v1",
                                         issued_at="2026-09-28T00:00:00Z")
            witness = B.witness_publication(F.raw_public("witness"), b"TEST_ONLY c", PB.MACHINE_ID)
            anchor_doc = OWNER.witness_anchor(witness)
            result = OWNER.reproduce(registry, anchor, anchor_doc, "2026-09-28T00:10:00Z")
            self.assertTrue(result["registryVerified"], result["registryReason"])
            self.assertEqual(result["ledgerGenesisOp"]["signingKeyIds"], [PB.P0])
            self.assertEqual((result["ledgerSequence"], result["ledgerHead"]), J.initial_position(registry))
            self.assertEqual(result["genesisPin"]["genesisWitnessDigest"], result["genesisCandidateDigest"])
            self.assertEqual(result["authorizationRegister"]["authorizations"], [])
            self.assertEqual(result["unsignedGenesis"]["witnessKeyId"], B.WITNESS_KEY_ID)
            package = {"packageType": PA.PACKAGE_TYPE, "x": 1}
            path = Path(directory) / "package.json"
            path.write_text(json.dumps(package), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(OWNER.main(["package-digest", str(path)]), 0)
            self.assertEqual(json.loads(out.getvalue())["packageDigest"], PA.package_digest(package))

    def test_owner_tool_is_never_release_payload(self):
        import release_file_set as RFS
        self.assertIn("services/authority-dev/ceremony/lilith_authority_owner_dev.py", RFS.SOURCE_FILES)
        self.assertNotIn("services/authority-dev/ceremony/lilith_authority_owner_dev.py", RFS.RUNTIME_SOURCE_MAP)
        with X.stand_in_wheels() as wheels:
            payloads = X.release_payloads(wheels)
        source = (ROOT / "services/authority-dev/ceremony/lilith_authority_owner_dev.py").read_bytes()
        self.assertNotIn(source, payloads.values())


# ---------------------------------------------------------- denial proof ---

class DenialProofTests(unittest.TestCase):
    def prove(self, phase, *, allowed=(), absent=(), pid="4242", ids=(990, 980), euid=0):
        lines = []
        calls = []

        def run(argv):
            calls.append(list(argv))
            key = (argv[2], argv[-2], argv[-1]) if argv[0] == DENIAL.RUNUSER else ("namespace", argv[-2], argv[-1])
            return 0 if key in allowed else 1
        ok = DENIAL.prove(phase, run=run, exists=lambda path: path not in absent, euid=lambda: euid,
                          signer_pid=lambda: pid, signer_ids=lambda: ids, say=lines.append)
        return ok, lines, calls

    def test_pass_requires_every_fixed_probe_denied(self):
        ok, lines, calls = self.prove("P1B-12")
        self.assertTrue(ok, lines)
        self.assertEqual(lines[-1], "AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-12")
        self.assertIn("DENIED: lilith-memory-broker test -r /etc/lilith-authority-custody", lines)
        self.assertIn("DENIED: lilith-authority-dev test -w /var/lib/lilith-recovery-witness/witness.json", lines)
        self.assertIn("DENIED: lilith-recovery-witness test -r /var/lib/lilith-authority-dev", lines)
        self.assertIn("DENIED: signer-namespace test -r /etc/lilith-authority-custody", lines)
        for call in calls:
            self.assertIn(call[0], (DENIAL.RUNUSER, DENIAL.NSENTER))
            self.assertEqual(call[-3], DENIAL.TEST)
            self.assertIn(call[-2], ("-r", "-w", "-x"))

    def test_absent_path_allowed_access_and_phase_rules(self):
        ok, lines, _ = self.prove("P1A-10", absent=("/var/lib/lilith-authority-custody",))
        self.assertFalse(ok)
        self.assertIn("FAIL: DENIAL_VACUOUS_PATH_ABSENT -r /var/lib/lilith-authority-custody", lines)
        ok, lines, _ = self.prove("P1A-10", allowed={("lilith", "-r", "/etc/lilith-recovery-witness")})
        self.assertFalse(ok)
        self.assertIn("FAIL: ALLOWED(unexpected) lilith test -r /etc/lilith-recovery-witness", lines)
        ok, lines, _ = self.prove("P1A-10")
        self.assertTrue(ok)
        self.assertTrue(any(line.startswith("DEFERRED_UNTIL_PHASE: P1B-12") for line in lines))
        self.assertFalse(any("signer-namespace" in line for line in lines))
        ok, lines, _ = self.prove("P1B-12", pid="0")
        self.assertFalse(ok)
        ok, lines, _ = self.prove("P1B-12", allowed={("namespace", "-x", "/etc/credstore.encrypted")})
        self.assertFalse(ok)
        for bad in ("P1A-9", "anything", "/etc/shadow"):
            self.assertFalse(self.prove(bad)[0])
        self.assertFalse(self.prove("P1A-10", euid=1000)[0])
        self.assertEqual(DENIAL.main([]), 2)
        self.assertEqual(DENIAL.main(["P1A-10", "/etc/shadow"]), 2)

    def test_the_proof_is_fixed_rows_only(self):
        source = (ROOT / "scripts/authority_custody_denial_proof.py").read_text(encoding="utf-8")
        self.assertTrue(source.startswith("#!/usr/bin/python3 -IB\n"))
        for needle in ("shell=True", "os.system", "argv[1:]", "input(", "open(", "chmod", "unlink", "rmtree"):
            self.assertNotIn(needle, source.replace("sys.argv[1:]", ""), needle)
        paths = {row[3] for row in DENIAL.ROWS} | {path for _, path in DENIAL.NAMESPACE_ROWS}
        for required in (P.CUSTODY_ROOT, P.HOLD_STORE_PARENT, P.WITNESS_CREDENTIAL_PARENT, P.AUTHORITY_STATE,
                         P.WITNESS_STATE, P.CREDSTORE):
            self.assertIn(required, paths)
        self.assertEqual(DENIAL.DEPLOYER, "sa_112096412008414111981")


if __name__ == "__main__":
    unittest.main()
