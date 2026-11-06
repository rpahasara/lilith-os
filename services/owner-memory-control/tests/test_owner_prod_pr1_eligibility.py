"""OWNER_PROD PR-1 eligibility (`tools/owner_prod_pr1_eligibility.py`): E-8, E-9 and E-19 re-judged for PROD.

The release verifier runs unchanged over the PR-1S synthetic host (the same host that reaches READY in
`test_pr1s_root_tooling`). OWNER_PROD inputs (no broker proof, the PROD deployer scope, the PROD activation line)
make the release judge exactly E-8 / E-9 / E-19 NOT_READY; the OWNER_PROD re-judgement over the host's own
observations then reaches READY on all 24 checks and through the release's own hold store. Every false or missing
piece of evidence still fails. Every key is a TEST_ONLY fixture; nothing contacts DEV or PROD.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_FIXTURES = _HERE.parents[1] / "authority-dev/tests"          # the PR-1S fixtures (read, never changed)
if str(_FIXTURES) not in sys.path:
    sys.path.insert(0, str(_FIXTURES))

import pr1s_fixtures as X  # noqa: E402
from pr1s_fixtures import PA, SC  # noqa: E402

import install_authority_dev as I  # noqa: E402

from lilith_authority_root import verifier as V  # noqa: E402
from lilith_authority_root.hold_store import HoldStoreError  # noqa: E402
from lilith_owner_memory import successor_readiness as SR  # noqa: E402

ROOT = X.ROOT
_spec = importlib.util.spec_from_file_location(
    "owner_prod_pr1_eligibility", ROOT / "services/owner-memory-control/tools/owner_prod_pr1_eligibility.py")
T = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = T          # dataclasses resolve their module by name
_spec.loader.exec_module(T)

ELIGIBILITY, FULL = SR.HOLD_RELEASE_ELIGIBILITY, SR.FULL_READINESS
NO_UNITS = lambda argv: subprocess.CompletedProcess(list(argv), 0, "", "")  # noqa: E731
NO_ACCOUNT = lambda name: (_ for _ in ()).throw(KeyError(name))          # noqa: E731


def prod_proofs(**changes):
    value = {name: X.proof(name, T.REQUIRED_PROD_DEPLOYER_SCOPE if name == "DEPLOYER_DENIAL" else None)
             for name in PA.REQUIRED_PROOFS if name not in T.BROKER_PROOFS}
    value.update(changes)
    return {k: v for k, v in value.items() if v is not None}


PROD_ACTIVATION = {"line": T.PROD_ACTIVATION_DARK_LINE, "b1cUnchanged": None}


@unittest.skipUnless(X.POSIX, "ownership and modes are POSIX")
class RuleTests(unittest.TestCase):
    def parsed(self, proofs):
        return {name: PA.ExternalProofV1(name, p["result"], p["transcriptSha256"], p["detail"])
                for name, p in proofs.items()}

    def test_deployer_needs_the_exact_prod_scope(self):
        self.assertIsNone(T.deployer_reason(self.parsed(prod_proofs())))
        dev = prod_proofs(DEPLOYER_DENIAL=X.proof("DEPLOYER_DENIAL", PA.REQUIRED_DEPLOYER_MATURITY))
        self.assertEqual(T.deployer_reason(self.parsed(dev)), "PROOF_SCOPE_MISMATCH:DEPLOYER_DENIAL")
        failed = prod_proofs(DEPLOYER_DENIAL={**X.proof("DEPLOYER_DENIAL", T.REQUIRED_PROD_DEPLOYER_SCOPE),
                                              "result": "FAIL"})
        self.assertEqual(T.deployer_reason(self.parsed(failed)), "PROOF_NOT_PASS:DEPLOYER_DENIAL")
        self.assertEqual(T.deployer_reason(self.parsed(prod_proofs(DEPLOYER_DENIAL=None))),
                         "PROOF_MISSING:DEPLOYER_DENIAL")

    def test_broker_absence_must_be_observed_and_never_claimed(self):
        absent = T.BrokerAbsenceV1((), (), False, ())
        self.assertIsNone(T.broker_reason(self.parsed(prod_proofs()), absent))
        claimed = self.parsed(prod_proofs(BROKER_DENIAL=X.proof("BROKER_DENIAL")))
        self.assertEqual(T.broker_reason(claimed, absent), "BROKER_PROOF_FOR_ABSENT_BROKER:BROKER_DENIAL")
        self.assertEqual(T.broker_reason(self.parsed(prod_proofs()), None), "BROKER_ABSENCE_UNOBSERVED")
        for present in (T.BrokerAbsenceV1(("/etc/systemd/system/lilith-memory-broker.service",), (), False, ()),
                        T.BrokerAbsenceV1((), ("lilith-memory-broker.socket",), False, ()),
                        T.BrokerAbsenceV1((), (), True, ()),
                        T.BrokerAbsenceV1((), (), False, ("/var/lib/lilith-memory-broker",))):
            self.assertEqual(T.broker_reason(self.parsed(prod_proofs()), present), "BROKER_PRESENT")

    def test_activation_needs_the_prod_line_no_b1c_claim_and_a_dark_host(self):
        line = PA.ActivationObservationV1(T.PROD_ACTIVATION_DARK_LINE, None)
        dark = T.ProdActivationV1(True, True, True)
        self.assertIsNone(T.activation_reason(line, dark))
        self.assertEqual(T.activation_reason(PA.ActivationObservationV1(PA.ACTIVATION_DARK_LINE, True), dark),
                         "ACTIVATION_NOT_DARK")
        self.assertEqual(T.activation_reason(PA.ActivationObservationV1(T.PROD_ACTIVATION_DARK_LINE, True), dark),
                         "ACTIVATION_NOT_DARK")
        self.assertEqual(T.activation_reason(None, dark), "ACTIVATION_UNOBSERVED")
        self.assertEqual(T.activation_reason(line, None), "ACTIVATION_DARK_UNOBSERVED")
        for host in (T.ProdActivationV1(False, True, True), T.ProdActivationV1(True, False, True),
                     T.ProdActivationV1(True, True, False)):
            self.assertEqual(T.activation_reason(line, host), "ACTIVATION_NOT_DARK_ON_HOST")


@unittest.skipUnless(X.POSIX, "ownership and modes are POSIX")
class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def observe(self, run=NO_UNITS, passwd=NO_ACCOUNT):
        return T.observe_broker_absence(self.root, run=run, passwd=passwd, owner_uid=X.UID, owner_gid=X.GID)

    def placeholder(self, absolute, mode=0o700):
        path = self.root / absolute.lstrip("/")
        path.mkdir(parents=True)
        os.chmod(path, mode)
        return path

    def test_absent_and_empty_placeholders_are_absent(self):
        self.assertTrue(self.observe().absent)
        for absolute in T.BROKER_PATHS[:2]:
            self.placeholder(absolute)
        self.assertTrue(self.observe().absent)

    def test_any_broker_trace_is_present(self):
        path = self.placeholder("/var/lib/lilith-memory-broker")
        (path / "state.db").write_bytes(b"x")
        self.assertEqual(self.observe().occupied_paths, ("/var/lib/lilith-memory-broker",))
        (path / "state.db").unlink()
        os.chmod(path, 0o755)
        self.assertFalse(self.observe().absent)
        os.chmod(path, 0o700)
        unit = self.root / "etc/systemd/system/lilith-memory-broker.service"
        unit.parent.mkdir(parents=True)
        unit.write_bytes(b"[Service]\n")
        self.assertEqual(self.observe().unit_files, ("/etc/systemd/system/lilith-memory-broker.service",))
        unit.unlink()
        listing = lambda argv: subprocess.CompletedProcess(list(argv), 0, "lilith-memory-broker.socket loaded\n", "")  # noqa: E731
        self.assertEqual(self.observe(run=listing).loaded_units, ("lilith-memory-broker.socket",))
        failing = lambda argv: subprocess.CompletedProcess(list(argv), 1, "", "")  # noqa: E731
        self.assertFalse(self.observe(run=failing).absent)
        self.assertTrue(self.observe(passwd=lambda name: object()).account_present)
        link = self.root / "opt/lilith-memory-broker"
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(path, link)
        self.assertIn("/opt/lilith-memory-broker", self.observe().occupied_paths)

    def test_activation_dark_is_exact(self):
        config = self.root / T.CANONICAL_CONFIG.lstrip("/")
        config.parent.mkdir(parents=True)
        self.assertFalse(T.observe_prod_activation(self.root).dark)
        config.write_bytes(T.CANONICAL_DISABLED)
        self.assertTrue(T.observe_prod_activation(self.root).dark)
        config.write_bytes(T.CANONICAL_DISABLED.replace(b"false", b"true"))
        self.assertFalse(T.observe_prod_activation(self.root).dark)
        config.write_bytes(T.CANONICAL_DISABLED + b"\n")
        (self.root / T.OWNER_CHANNEL_GRANT.lstrip("/")).write_bytes(b"{}")
        self.assertEqual(T.observe_prod_activation(self.root).to_dict(),
                         {"canonicalDisabled": True, "grantAbsent": False, "routerSettingsAbsent": True})


@unittest.skipUnless(X.POSIX, "ownership and modes are POSIX")
class EndToEndTests(unittest.TestCase):
    """The release verifier + hold store on the PR-1S synthetic host, re-judged by the OWNER_PROD rules."""

    def setUp(self):
        self.stack = contextlib.ExitStack()
        directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.host = X.Pr1Host(directory).genesis_host()
        with X.stand_in_wheels() as wheels:
            self.payloads = X.release_payloads(wheels)
        self.manifest = X.install_release(self.host.root, X.RELEASE_SHA, self.payloads)
        self.manifest_sha = hashlib.sha256(X.I.canonical(self.manifest)).hexdigest() if hasattr(X, "I") else \
            hashlib.sha256(__import__("install_authority_dev").canonical(self.manifest)).hexdigest()
        self.first = X.current_document(self.host)
        config = self.host.root / T.CANONICAL_CONFIG.lstrip("/")
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_bytes(T.CANONICAL_DISABLED)
        for absolute in ("/etc/lilith-memory-broker", "/var/lib/lilith-memory-broker"):
            path = self.host.root / absolute.lstrip("/")
            path.mkdir(parents=True, exist_ok=True)
            os.chmod(path, 0o700)

    def tearDown(self):
        self.stack.close()

    def owner(self, **inputs):
        defaults = dict(proofs=prod_proofs(), activation=PROD_ACTIVATION, with_pr2=True, with_pr3=True)
        defaults.update(inputs)
        return V.parse_verifier_inputs(X.verifier_inputs(self.host, manifest_sha256=self.manifest_sha,
                                                         first_current=self.first, **defaults))

    def release_result(self, owner, mode=ELIGIBILITY, hold=None):
        return V.evaluate(mode, owner, root=self.host.root, owner_uid=X.UID, owner_gid=X.GID, health=X.health_p0,
                          run=X.fake_systemctl(), hold=hold)

    def prod_result(self, owner, mode=ELIGIBILITY, hold=None, run=NO_UNITS, passwd=NO_ACCOUNT):
        base = self.release_result(owner, mode, hold)
        return T.rejudge(base, proofs=owner.proofs, activation=owner.activation,
                         broker=T.observe_broker_absence(self.host.root, run=run, passwd=passwd,
                                                         owner_uid=X.UID, owner_gid=X.GID),
                         dark=T.observe_prod_activation(self.host.root))

    def failing(self, result):
        return {name for name, outcome in result.checks.items() if outcome.status != PA.PASS}

    def test_release_rules_fail_exactly_the_three_dev_specific_checks(self):
        self.assertEqual(self.failing(self.release_result(self.owner())), set(T.REJUDGED))

    def test_owner_prod_reaches_ready_on_all_24_checks_with_a_stable_digest(self):
        owner = self.owner()
        result = self.prod_result(owner)
        self.assertEqual(result.status, PA.READY, result.reasons)
        self.assertEqual(len(result.checks), 24)
        self.assertTrue(all(o.status == PA.PASS for o in result.checks.values()))
        self.assertEqual(result.package_digest, self.prod_result(owner).package_digest)
        self.assertEqual(result.package_digest, PA.package_digest(result.package))
        evidence = result.package["evidence"]["ownerProd"]
        self.assertEqual(evidence["rules"], T.RULES)
        self.assertEqual(evidence["releaseJudgement"]["E09_BROKER_DENIAL_PRESERVATION"][0], PA.FAIL)
        for flag in ("authorityGranted", "activationGranted", "issuanceWired"):
            self.assertIs(result.package[flag], False)

    def test_release_through_the_release_hold_store_then_full_readiness(self):
        owner = self.owner()
        eligibility = self.prod_result(owner)
        released = self.host.holds.release_initial(
            approved_package_digest=eligibility.package_digest, rerun=lambda held: self.prod_result(owner, hold=held),
            witness_store=self.host.witness_store(), context=self.host.context())
        self.assertEqual((released["state"], released["reason"]), (SC.RELEASED, SC.OWNER_RELEASE_AFTER_ELIGIBILITY))
        full = self.prod_result(owner, FULL)
        self.assertEqual(full.status, PA.READY, full.reasons)
        self.assertTrue(full.readiness.facts["issuanceReady"])

    def test_false_or_missing_evidence_is_still_rejected(self):
        ready = self.prod_result(self.owner()).package_digest
        cases = {
            "E08_DEPLOYER_DENIAL": [
                dict(proofs=prod_proofs(DEPLOYER_DENIAL=X.proof("DEPLOYER_DENIAL", PA.REQUIRED_DEPLOYER_MATURITY))),
                dict(proofs=prod_proofs(DEPLOYER_DENIAL=None))],
            "E09_BROKER_DENIAL_PRESERVATION": [
                dict(proofs=prod_proofs(BROKER_DENIAL=X.proof("BROKER_DENIAL"),
                                        BROKER_PRESERVATION=X.proof("BROKER_PRESERVATION")))],
            "E19_ACTIVATION_DARK": [dict(activation={"line": PA.ACTIVATION_DARK_LINE, "b1cUnchanged": True}),
                                    dict(activation={"line": T.PROD_ACTIVATION_DARK_LINE, "b1cUnchanged": True})],
            "E07_SIGNER_CUSTODY_DENIAL": [dict(proofs=prod_proofs(OS_DENIAL=None))],
            "E22_SECRET_HYGIENE": [dict(proofs=prod_proofs(SECRET_HYGIENE={**X.proof("SECRET_HYGIENE"),
                                                                           "result": "FAIL"}))],
            "E20_SNAPSHOT_INVENTORY": [dict(with_pr2=False)],
        }
        for check, variants in cases.items():
            for inputs in variants:
                with self.subTest(check=check, inputs=sorted(inputs)):
                    result = self.prod_result(self.owner(**inputs))
                    self.assertEqual(result.status, PA.NOT_READY)
                    self.assertIn(check, self.failing(result))
                    self.assertNotEqual(result.package_digest, ready)
        broker_unit = lambda argv: subprocess.CompletedProcess(list(argv), 0, "lilith-memory-broker.service\n", "")  # noqa: E731
        for label, kwargs in (("loaded broker unit", dict(run=broker_unit)),
                              ("broker account", dict(passwd=lambda name: object()))):
            with self.subTest(label=label):
                self.assertIn("E09_BROKER_DENIAL_PRESERVATION", self.failing(self.prod_result(self.owner(), **kwargs)))
        (self.host.root / "var/lib/lilith-memory-broker/ledger.db").write_bytes(b"x")
        self.assertIn("E09_BROKER_DENIAL_PRESERVATION", self.failing(self.prod_result(self.owner())))
        (self.host.root / "var/lib/lilith-memory-broker/ledger.db").unlink()
        (self.host.root / T.OWNER_CHANNEL_GRANT.lstrip("/")).write_bytes(b"{}")
        self.assertIn("E19_ACTIVATION_DARK", self.failing(self.prod_result(self.owner())))

    def test_the_hold_refuses_a_digest_once_the_evidence_changes(self):
        owner = self.owner()
        approved = self.prod_result(owner).package_digest
        (self.host.root / T.ROUTER_CANONICAL_SETTINGS.lstrip("/")).parent.mkdir(parents=True, exist_ok=True)
        (self.host.root / T.ROUTER_CANONICAL_SETTINGS.lstrip("/")).write_bytes(b"{}")
        with self.assertRaises(HoldStoreError) as caught:
            self.host.holds.release_initial(
                approved_package_digest=approved, rerun=lambda held: self.prod_result(owner, hold=held),
                witness_store=self.host.witness_store(), context=self.host.context())
        self.assertEqual(caught.exception.reason, "HOLD_RELEASE_NOT_PERMITTED")

    def test_evaluate_refuses_anything_but_prod_and_the_cli_needs_root_and_prod(self):
        with self.assertRaises(T.Refused) as caught:
            T.evaluate(ELIGIBILITY, self.owner(), root=self.host.root)
        self.assertEqual(caught.exception.reason, "ENVIRONMENT_NOT_OWNER_PROD")
        self.assertEqual(T.main(["eligibility", "x.json"], euid=1000), 2)

    def test_no_release_module_is_changed(self):
        source = (ROOT / "services/owner-memory-control/tools/owner_prod_pr1_eligibility.py").read_text(encoding="utf-8")
        for forbidden in ("def evaluate_pr1_acceptance", "REQUIRED_PROOFS =", "open(P.", "write_bytes", "unlink("):
            self.assertNotIn(forbidden, source)


# ===================================================================== OWNER_PROD host ===
# The same PR-1B host shape, built with the OWNER_PROD identities lilith-01 actually has (environment `prod`, K-ROOT
# prod.registry-root.owner-prod.1, K-ACT prod.owner-prod.actor.1, K-WIT prod.witness.owner-prod.1, OWNER_PROD
# profiles) through the repository's own PROD builders (owner_prod_keygen publications, owner_prod_owner_tool registry v1
# and witness anchor) with TEST_ONLY seeds: the end-to-end proof of a `prod` evaluation.

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: E402

_TOOLS = ROOT / "services/owner-memory-control/tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import owner_prod_keygen as KG  # noqa: E402
import owner_prod_owner_tool as OT  # noqa: E402
from lilith_authority_dev.ledger import DurableAuthorityLedgerV1  # noqa: E402
from lilith_authority_host import inputs as HI  # noqa: E402
from lilith_authority_host import paths as P  # noqa: E402
from lilith_authority_host.store_observer import observe_witness_state  # noqa: E402
from lilith_authority_root import observers as O  # noqa: E402
from lilith_authority_root.hold_store import HoldStoreV1  # noqa: E402
from lilith_owner_memory import authority_contracts as A  # noqa: E402
from lilith_owner_memory import authority_ledger_journal as J  # noqa: E402
from lilith_owner_memory import pr1_bootstrap as B  # noqa: E402
from lilith_owner_memory import rotation_contracts as RC  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402
from lilith_recovery_witness.credential import WitnessSigningKeyV1  # noqa: E402
from lilith_recovery_witness.storage import FilesystemWitnessStorageV1  # noqa: E402
from lilith_recovery_witness.writer import DevSyntheticWitnessWriterV1  # noqa: E402

PROD = "prod"
MACHINE_ID = "0123456789abcdef0123456789abcdef"
KACT_BLOB = b"TEST_ONLY OWNER_PROD stand-in K-ACT ciphertext (never a credential)"
KWIT_BLOB = b"TEST_ONLY OWNER_PROD stand-in K-WIT ciphertext (never a credential)"
ISSUED = "2026-11-06T04:11:02Z"
UPDATED = "2026-11-06T04:11:14Z"


def _key(name: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(b"TEST_ONLY owner-prod " + name.encode()).digest())


def _raw(name: str) -> bytes:
    return _key(name).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


class ProdHost:
    """lilith-01 after Gate 6.2b (TEST_ONLY keys): trust inputs, ledger seq 1, witness genesis, INITIAL_CUSTODY HELD."""

    def __init__(self, directory: str):
        self.root = Path(directory)
        self.kact = KG.publication(_raw("kact"), KACT_BLOB, MACHINE_ID)
        self.kwit = KG.witness_publication(_raw("kwit"), KWIT_BLOB, MACHINE_ID)
        self.registry = OT.registry_v1(_key("kroot"), self.kact, epoch_random="1" * 32,
                                       policy_version=OT.POLICY_VERSION, issued_at=ISSUED)
        self.root_anchor = {"algorithm": "Ed25519", "environment": PROD, "publicKey": X.b64u(_raw("kroot")),
                            "rootKeyId": OT.ROOT_KEY_ID, "schemaVersion": 1}
        self.witness_anchor = OT.witness_anchor(self.kwit)
        self.witness_profile = B.witness_profile(PROD)
        for path in ("etc/systemd/system", "etc/tmpfiles.d", "usr/local/sbin", "var/lib/systemd", "opt"):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        (self.root / "etc/machine-id").write_text(MACHINE_ID + "\n")
        for absolute in (P.AUTHORITY_CONFIG, P.TRUST_DIR, P.REGISTRY_DIR, P.OWNER_INPUT_DIR):
            X._dir(self.path(absolute), 0o755)
        for absolute in (P.CREDSTORE, P.CUSTODY_ROOT, P.PREPARED_DIR, P.RETIRED_DIR, P.WITNESS_CREDENTIAL_PARENT,
                         P.WITNESS_CREDENTIAL_ROOT, P.HOLD_STORE_PARENT, P.HOLD_STORE, P.AUTHORITY_STATE):
            X._dir(self.path(absolute), 0o700)
        X._dir(self.path(P.WITNESS_STATE), 0o750)
        X._write(self.path(P.CURRENT_SLOT), KACT_BLOB, 0o600)
        X._write(self.path(P.WITNESS_BLOB), KWIT_BLOB, 0o600)
        X._write(self.path(f"{P.UNIT_DIR}/lilith-authority-dev.service"),
                 (ROOT / "services/authority-dev/deploy/lilith-authority-dev.service").read_bytes(), 0o644)
        self.holds = HoldStoreV1(environment=PROD, root=self.root, owner_uid=X.UID, owner_gid=X.GID)
        # Gates 6.1, 6.2 and 6.2b on lilith-01: deployment, anchors, registry, ledger, pin, witness genesis, HELD.
        self.document(P.DEPLOYMENT, json.loads(b'{"environment":"prod","profile":"OWNER_PROD","schemaVersion":1}'))
        self.document(P.REGISTRY_ROOT_ANCHOR, self.root_anchor)
        self.document(P.WITNESS_ANCHOR, self.witness_anchor)
        self.document(f"{P.REGISTRY_DIR}/{HI.registry_file_name(1)}", self.registry)
        DurableAuthorityLedgerV1.provision(self.path(P.AUTHORITY_LEDGER), environment=PROD,
                                           genesis=J.genesis_op(self.registry), expected_uid=X.UID)
        candidate = B.build_genesis_candidate(registry=self.registry,
                                              registry_root=A.TrustedRegistryRootV1.from_dict(self.root_anchor),
                                              ledger_observation=self.ledger_observation(), updated_at=UPDATED,
                                              profile=self.witness_profile)
        self.document(P.GENESIS_PIN_COPY, WR.OwnerGenesisPinV1(PROD, candidate.digest).to_dict())
        self.document(P.AUTHORIZATION_REGISTER_COPY, {
            "registerType": WR.REGISTER_TYPE, "schemaVersion": WR.REGISTER_SCHEMA_VERSION, "environment": PROD,
            "authorizations": [], "headRegistries": [RC.registry_head(self.registry).to_dict()]})
        writer = DevSyntheticWitnessWriterV1(
            signing_key=WitnessSigningKeyV1(_key("kwit"), witness_key_id=self.witness_profile.witness_key_id),
            storage=FilesystemWitnessStorageV1(self.path(P.WITNESS_STATE)), profile=self.witness_profile)
        writer.bootstrap(registry=self.registry, ledger_observation=self.ledger_observation(), context=self.context(),
                         updated_at=UPDATED)
        self.holds.create_initial_held(witness_store=self.witness_store(), context=self.context())
        self.genesis = candidate.digest

    def path(self, absolute: str) -> Path:
        return self.root / absolute.lstrip("/")

    def document(self, absolute: str, value) -> None:
        X._write(self.path(absolute), WR.document_bytes(value), 0o644)

    def ledger_observation(self):
        ledger = DurableAuthorityLedgerV1.open_existing(self.path(P.AUTHORITY_LEDGER), environment=PROD,
                                                        expected_uid=X.UID)
        try:
            return ledger.observe()
        finally:
            ledger.close()

    def context(self):
        inputs = HI.read_host_inputs(environment=PROD, root=self.root, owner_uid=X.UID)
        return inputs.store_context(authority_public_keys=HI.authority_public_keys(inputs))

    def witness_store(self):
        return observe_witness_state(self.path(P.WITNESS_STATE))

    def health(self):
        return {"profile": "OWNER_PROD", "signingDomain": A.OWNER_ACTOR, "foundation": "B1B3D_L1_SOURCE_FOUNDATION",
                "service": "SERVICE_AVAILABLE", "credential": RC.HEALTH_CREDENTIAL_PRESENT,
                "publicKeySha256": hashlib.sha256(_raw("kact")).hexdigest(), "signing": "SIGNING_NOT_AVAILABLE",
                "readiness": "NOT_READY", "reasons": []}


def _systemctl(states=None):
    units = X.fake_systemctl(states)

    def run(argv):
        if "list-units" in argv:                       # the broker observation: no broker unit loaded
            return subprocess.CompletedProcess(list(argv), 0, "", "")
        return units(argv)
    return run


@unittest.skipUnless(X.POSIX, "ownership and modes are POSIX")
class OwnerProdEndToEndTests(unittest.TestCase):
    """`T.evaluate` itself (environment prod, the widened readiness) on an OWNER_PROD host, truthful evidence only."""

    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.host = ProdHost(self.stack.enter_context(tempfile.TemporaryDirectory()))
        with X.stand_in_wheels() as wheels:
            payloads = X.release_payloads(wheels)
        self.manifest_sha = hashlib.sha256(I.canonical(X.install_release(self.host.root, X.RELEASE_SHA,
                                                                         payloads))).hexdigest()
        self.first = O.observe_current_blob(self.host.root).to_dict()
        config = self.host.path(T.CANONICAL_CONFIG)
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_bytes(T.CANONICAL_DISABLED)
        for absolute in ("/etc/lilith-memory-broker", "/var/lib/lilith-memory-broker", "/etc/lilith-os-dev"):
            X._dir(self.host.path(absolute), 0o700)

    def tearDown(self):
        self.stack.close()

    def offhost(self, **changes):
        h = self.host
        value = {"status": "PRESENT",
                 "registerSha256": hashlib.sha256(h.path(P.AUTHORIZATION_REGISTER_COPY).read_bytes()).hexdigest(),
                 "genesisPinDigest": h.genesis, "kRootPublicKeySha256": hashlib.sha256(_raw("kroot")).hexdigest(),
                 "kWitPublicKeySha256": hashlib.sha256(_raw("kwit")).hexdigest(),
                 "kActPublicationSha256": hashlib.sha256(SC.canonical_publication_bytes(h.kact)).hexdigest(),
                 "registryHead": RC.registry_head(h.registry).to_dict(), "releaseSha": X.RELEASE_SHA,
                 "releaseManifestSha256": self.manifest_sha, "authorizationIds": [], "burnedOrdinals": []}
        value.update(changes)
        return value

    def owner(self, **changes):
        h = self.host
        doc = {
            "inputType": "LILITH_PR1_VERIFIER_INPUTS", "schemaVersion": 1, "environment": PROD,
            "releaseSha": X.RELEASE_SHA, "attestedManifestSha256": self.manifest_sha, "reviewedRuntimeDigests": None,
            "pinnedCurrentSha256": hashlib.sha256(KACT_BLOB).hexdigest(), "firstPreflightCurrent": self.first,
            "kActPublication": X.b64u(SC.canonical_publication_bytes(h.kact)),
            "kWitPublication": X.b64u(SC.canonical_publication_bytes(h.kwit)),
            "proofs": prod_proofs(), "activation": PROD_ACTIVATION,
            "snapshotInventory": {"status": "ACCEPTED",
                                  "recordSha256": hashlib.sha256(b"TEST_ONLY inventory").hexdigest(),
                                  "artefactClasses": ["KNOWN_CUSTODY_DEBT"], "namedDebts": ["SNAPSHOTS_HOLD_HOST_KEY"]},
            "offHostMaterial": self.offhost(),
        }
        doc.update(changes)
        return V.parse_verifier_inputs(doc)

    def evaluate(self, owner=None, mode=ELIGIBILITY, hold=None, health=None, run=None):
        return T.evaluate(mode, owner or self.owner(), root=self.host.root, owner_uid=X.UID, owner_gid=X.GID,
                          health=health or self.host.health, run=run or _systemctl(), hold=hold, passwd=NO_ACCOUNT)

    def failing(self, result):
        return {name: outcome.reason for name, outcome in result.checks.items() if outcome.status != PA.PASS}

    def test_the_release_alone_cannot_reach_ready_on_owner_prod(self):
        base = V.evaluate(ELIGIBILITY, self.owner(), root=self.host.root, owner_uid=X.UID, owner_gid=X.GID,
                          health=self.host.health, run=_systemctl())
        self.assertEqual(base.status, PA.NOT_READY)
        self.assertIn("PROFILE_NOT_DEV_SYNTHETIC", ",".join(base.reasons))

    def test_owner_prod_reaches_ready_on_all_24_checks_end_to_end(self):
        result = self.evaluate()
        self.assertEqual(result.status, PA.READY, self.failing(result))
        self.assertEqual(len(result.checks), 24)
        self.assertEqual(result.package["environment"], PROD)
        self.assertEqual(result.package["evidence"]["registry"]["rootKeyId"], OT.ROOT_KEY_ID)
        self.assertEqual(result.package["evidence"]["kWit"]["witnessKeyId"], "prod.witness.owner-prod.1")
        self.assertEqual(result.package["evidence"]["kActPublication"]["keyId"], "prod.owner-prod.actor.1")
        self.assertEqual(result.package["evidence"]["holdStore"]["records"],
                         [["prod.initial-custody.prod.owner-prod.actor.1", SC.INITIAL_CUSTODY, SC.HELD]])
        self.assertEqual(result.package_digest, self.evaluate().package_digest)

    def test_release_then_full_readiness_and_the_signer_issuance_gate(self):
        owner = self.owner()
        approved = self.evaluate(owner).package_digest
        released = self.host.holds.release_initial(
            approved_package_digest=approved, rerun=lambda held: self.evaluate(owner, hold=held),
            witness_store=self.host.witness_store(), context=self.host.context())
        self.assertEqual(released["state"], SC.RELEASED)
        full = self.evaluate(owner, FULL)
        self.assertEqual(full.status, PA.READY, self.failing(full))
        self.assertTrue(full.readiness.facts["issuanceReady"])
        # the signer's own issuance gate (release code, unchanged) accepts the released OWNER_PROD store
        profile = SC.custody_profile(PROD)
        history, reason, _ = SR.verify_history(store=self.host.context(), witness_store=self.host.witness_store(),
                                               head_registries=(self.host.registry,))
        self.assertIsNone(reason)
        transition, reason, _ = SR.derive_key_transition(history, profile=profile)
        self.assertIsNone(reason)
        holds, reason, _ = SC.parse_hold_store(self.host.holds.observe().observation, profile=profile)
        self.assertIsNone(reason)
        _governing, reason, _ = SR.governing_hold_reason(holds, mode=SR.FULL_READINESS, transition=transition,
                                                         history=history, inventory_phase=WR.STEADY)
        self.assertIsNone(reason)

    def test_false_evidence_still_fails_on_owner_prod(self):
        ready = self.evaluate().package_digest
        bad_health = lambda: {**self.host.health(), "publicKeySha256": "0" * 64}  # noqa: E731
        cases = [
            ("E03_HEALTH_FINGERPRINT", lambda: dict(health=bad_health)),
            ("E06_UNIT_CREDENTIAL_MAPPING",
             lambda: dict(run=_systemctl({"lilith-authority-dev.service": {"NeedDaemonReload": "yes"}}))),
            ("E04_CURRENT_PRESERVED", lambda: dict(owner=self.owner(pinnedCurrentSha256="1" * 64))),
            ("E08_DEPLOYER_DENIAL", lambda: dict(owner=self.owner(proofs=prod_proofs(
                DEPLOYER_DENIAL=X.proof("DEPLOYER_DENIAL", PA.REQUIRED_DEPLOYER_MATURITY))))),
            ("E09_BROKER_DENIAL_PRESERVATION", lambda: dict(owner=self.owner(proofs=prod_proofs(
                BROKER_DENIAL=X.proof("BROKER_DENIAL"))))),
            ("E19_ACTIVATION_DARK", lambda: dict(owner=self.owner(activation={"line": PA.ACTIVATION_DARK_LINE,
                                                                               "b1cUnchanged": True}))),
            ("E18_OFFHOST_REPRODUCTION_INPUTS",
             lambda: dict(owner=self.owner(offHostMaterial=self.offhost(genesisPinDigest="2" * 64)))),
            ("E20_SNAPSHOT_INVENTORY", lambda: dict(owner=self.owner(snapshotInventory=None))),
            ("E22_SECRET_HYGIENE", lambda: dict(owner=self.owner(proofs=prod_proofs(
                SECRET_HYGIENE={**X.proof("SECRET_HYGIENE"), "result": "FAIL"})))),
        ]
        for check, kwargs in cases:
            with self.subTest(check=check):
                result = self.evaluate(**kwargs())
                self.assertEqual(result.status, PA.NOT_READY)
                self.assertIn(check, self.failing(result))
                self.assertNotEqual(result.package_digest, ready)


@unittest.skipUnless(X.POSIX, "ownership and modes are POSIX")
class ReadinessWideningTests(unittest.TestCase):
    """The OWNER_PROD readiness is the release function with exactly one line widened, and changes nothing else."""

    def test_exactly_one_line_differs_and_it_only_adds_owner_prod(self):
        import difflib
        release, widened = T.owner_prod_readiness_source()
        changed = [l for l in difflib.ndiff(release.splitlines(), widened.splitlines()) if l[:2] in ("- ", "+ ")]
        self.assertEqual(changed, ["- " + T.READINESS_GATE.rstrip("\n"),
                                   "+ " + T.READINESS_GATE_OWNER_PROD.rstrip("\n")])

    def test_the_release_module_is_restored_even_on_error(self):
        release_fn = SR.evaluate_successor_readiness
        with self.assertRaises(RuntimeError):
            with T._owner_prod_readiness_in_force():
                self.assertIsNot(SR.evaluate_successor_readiness, release_fn)
                raise RuntimeError("boom")
        self.assertIs(SR.evaluate_successor_readiness, release_fn)

    def test_dev_and_test_packages_are_identical_under_the_widened_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            host = X.Pr1Host(directory).genesis_host()
            with X.stand_in_wheels() as wheels:
                payloads = X.release_payloads(wheels)
            manifest_sha = hashlib.sha256(I.canonical(X.install_release(host.root, X.RELEASE_SHA, payloads))).hexdigest()
            owner = V.parse_verifier_inputs(X.verifier_inputs(host, manifest_sha256=manifest_sha, with_pr2=True,
                                                              with_pr3=True))
            run = lambda: V.evaluate(ELIGIBILITY, owner, root=host.root, owner_uid=X.UID, owner_gid=X.GID,  # noqa: E731
                                     health=X.health_p0, run=X.fake_systemctl())
            release = run()
            with T._owner_prod_readiness_in_force():
                widened = run()
            self.assertEqual(release.status, PA.READY, release.reasons)
            self.assertEqual((widened.status, widened.package_digest), (release.status, release.package_digest))

    def test_a_release_without_the_exact_gate_is_refused(self):
        original = T.READINESS_GATE
        try:
            T.READINESS_GATE = "    if not SC.is_dev_synthetic(profile) and False:\n"
            with self.assertRaises(T.Refused) as caught:
                T.owner_prod_readiness_source()
            self.assertEqual(caught.exception.reason, "RELEASE_READINESS_GATE_NOT_FOUND")
        finally:
            T.READINESS_GATE = original


if __name__ == "__main__":
    unittest.main()
