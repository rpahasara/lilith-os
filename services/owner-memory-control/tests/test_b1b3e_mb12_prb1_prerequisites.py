"""15B2b-B1b-3e M-B12 PR-B1: PR-2 inventory, PR-3 material and readiness-input tooling (TEST-ONLY, synthetic).

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb1-prerequisite-tooling.md. No live system: the PR-2 documents are
synthetic, the PR-3 bytes are the TEST_ONLY Prep B / PR-1S fixture identities, and the end-to-end checks run the
release's root verifier over the synthetic `Pr1Host` (environment `test`, never `dev`).
"""

from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, ROOT / "services/authority-dev", ROOT / "services/authority-dev/tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mb12_pr2_inventory as I2  # noqa: E402
import mb12_pr3_material as M3  # noqa: E402
import mb12_readiness_inputs as RI  # noqa: E402
from lilith_owner_memory import pr1_acceptance as PA  # noqa: E402
from lilith_owner_memory import successor_custody as SC  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402

POSIX = os.name == "posix"
H = lambda label: hashlib.sha256(label.encode()).hexdigest()  # noqa: E731
KEYS = {"K_ACT": H("synthetic k-act"), "K_WIT": H("synthetic k-wit")}
T0, T1, T2 = "2026-10-12T10:00:00Z", "2026-10-12T10:30:00Z", "2026-10-12T11:00:00Z"
REAL_HOST_ACTIVATION = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false"


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


# ----------------------------------------------------------------- PR-2 inventory ---

def inventory(*, artefacts=(), evidence=I2.SYNTHETIC_FIXTURE, environment="test", carried=(), **listing_overrides):
    counts = {kind: 0 for kind in I2.ARTEFACT_KINDS}
    for artefact in artefacts:
        counts[artefact["kind"]] += 1
    listings = []
    for kind in I2.LISTING_KINDS:
        item = {"kind": kind, "complete": True, "count": counts.get(kind, 0), "listingSha256": H(kind)}
        item.update(listing_overrides.get(kind, {}))
        listings.append(item)
    return {"inventoryType": I2.INVENTORY_TYPE, "schemaVersion": 1, "environment": environment,
            "evidenceClass": evidence, "window": {"startedAt": T0, "endedAt": T1},
            "keys": [{"role": "K_ACT", "publicKeySha256": KEYS["K_ACT"], "sealedUnder": "HOST_KEY"},
                     {"role": "K_WIT", "publicKeySha256": KEYS["K_WIT"], "sealedUnder": "HOST_KEY"},
                     {"role": "HOST_KEY", "publicKeySha256": None, "sealedUnder": None}],
            "listings": listings, "artefacts": list(artefacts),
            "carriedDebts": [{"name": name, "role": "K_WIT", "recordSha256": H(name)} for name in carried],
            "privateEvidenceSha256": H("private evidence")}


def artefact(name, material, *, location=I2.INSIDE, access=I2.KNOWN, debt=None, kind="DISK_SNAPSHOTS"):
    return {"artefactId": name, "kind": kind, "material": list(material), "location": location,
            "accessHistory": access, "debtName": debt}


def acceptance(digest, *, environment="test", at=T2):
    return {"acceptanceType": I2.ACCEPTANCE_TYPE, "schemaVersion": 1, "environment": environment,
            "acceptedInventoryDigest": digest, "acceptanceRecordSha256": H("owner record"), "acceptedAt": at}


class Pr2InventoryTests(unittest.TestCase):
    def classify(self, document, **kwargs):
        return I2.classify(document, environment=document["environment"], expected_keys=KEYS, **kwargs)

    def test_no_snapshots_classifies_pass(self):
        report = self.classify(inventory())
        self.assertEqual((report["classification"], report["artefactClasses"]), ("PASS", ["NO_SNAPSHOTS"]))
        self.assertEqual(set(report["keyClasses"].values()), {"NO_SNAPSHOTS"})
        self.assertIs(report["ownerAccepted"], False)

    def test_rr17_minimum_classes(self):
        cases = {
            "ciphertext only, inside": ([artefact("s", ["K_ACT_CIPHERTEXT"])], "SAFE_RETAINED_CIPHERTEXT"),
            "both halves, inside": ([artefact("s", ["K_ACT_CIPHERTEXT", "HOST_KEY_SECRET"], debt="S-1")],
                                    "KNOWN_CUSTODY_DEBT"),
            "both halves, outside": ([artefact("s", ["K_WIT_CIPHERTEXT", "HOST_KEY_SECRET"], location=I2.OUTSIDE)],
                                     "EXPOSED_PRIVATE_MATERIAL"),
            "ciphertext, outside": ([artefact("s", ["K_ACT_CIPHERTEXT"], location=I2.OUTSIDE)], "UNKNOWN_PROVENANCE"),
            "unknown access": ([artefact("s", ["K_ACT_CIPHERTEXT"], access=I2.UNKNOWN)], "UNKNOWN_PROVENANCE"),
            "plaintext": ([artefact("s", ["PLAINTEXT_PRIVATE"])], "EXPOSED_PRIVATE_MATERIAL"),
        }
        for label, (artefacts, expected) in cases.items():
            with self.subTest(label=label):
                report = self.classify(inventory(artefacts=artefacts))
                self.assertEqual(report["artefacts"]["s"], expected)

    def test_host_key_secret_reclassifies_every_ciphertext_under_it(self):
        secret_inside = [artefact("a", ["K_ACT_CIPHERTEXT"]), artefact("b", ["HOST_KEY_SECRET"], debt="S-2")]
        report = self.classify(inventory(artefacts=secret_inside))
        self.assertEqual(report["artefacts"], {"a": "KNOWN_CUSTODY_DEBT", "b": "KNOWN_CUSTODY_DEBT"})
        self.assertEqual(report["keyClasses"]["K_WIT"], "KNOWN_CUSTODY_DEBT")   # K-WIT is sealed under it too
        self.assertEqual(report["classification"], "FAIL")                        # artefact a's debt is unnamed
        self.assertIn("DEBT_NOT_NAMED:a", report["reasons"])
        outside = [artefact("a", ["K_ACT_CIPHERTEXT"]), artefact("b", ["HOST_KEY_SECRET"], location=I2.OUTSIDE)]
        report = self.classify(inventory(artefacts=outside))
        self.assertEqual(report["keyClasses"], {"K_ACT": "EXPOSED_PRIVATE_MATERIAL",
                                                "K_WIT": "EXPOSED_PRIVATE_MATERIAL",
                                                "HOST_KEY": "EXPOSED_PRIVATE_MATERIAL"})
        self.assertEqual(report["classification"], "FAIL")

    def test_incomplete_or_miscounted_listing_is_unknown_provenance(self):
        for overrides in ({"MACHINE_IMAGES": {"complete": False}}, {"IMAGES": {"count": 1}}):
            with self.subTest(overrides=overrides):
                report = self.classify(inventory(**overrides))
                self.assertEqual((report["classification"], report["artefactClasses"]),
                                 ("FAIL", ["UNKNOWN_PROVENANCE"]))
        document = inventory()
        document["listings"] = document["listings"][:-1]
        self.assertEqual(self.classify(document)["artefactClasses"], ["UNKNOWN_PROVENANCE"])

    def test_key_relationships_and_identities_are_exact(self):
        document = inventory()
        document["keys"][0]["sealedUnder"] = None
        with self.assertRaises(I2.Refused) as caught:
            self.classify(document)
        self.assertEqual(caught.exception.reason, "INVENTORY_KEY_RELATIONSHIP")
        document = inventory()
        document["keys"][1]["publicKeySha256"] = H("other")
        with self.assertRaises(I2.Refused) as caught:
            self.classify(document)
        self.assertEqual(caught.exception.reason, "INVENTORY_KEY_IDENTITY_MISMATCH")
        document = inventory()
        document["keys"] = document["keys"][:2]
        with self.assertRaises(I2.Refused) as caught:
            self.classify(document)
        self.assertEqual(caught.exception.reason, "INVENTORY_KEYS_NOT_EXACT")
        self.assertEqual(I2.DEV_KEY_IDENTITIES["K_ACT"], RI.DEV_PINS["kActPublicKeySha256"])
        self.assertEqual(I2.DEV_KEY_IDENTITIES["K_WIT"], RI.DEV_PINS["kWitPublicKeySha256"])

    def test_stale_window_and_carried_debts(self):
        with self.assertRaises(I2.Refused) as caught:
            self.classify(inventory(), not_before=T1)
        self.assertEqual(caught.exception.reason, "INVENTORY_STALE")
        report = self.classify(inventory(), required_carried_debts=("C-4",))
        self.assertIn("CARRIED_DEBT_MISSING:C-4", report["reasons"])
        report = self.classify(inventory(carried=("C-4",)), required_carried_debts=("C-4",))
        self.assertEqual((report["classification"], report["namedDebts"]), ("PASS", ["C-4"]))

    def test_synthetic_fixture_never_becomes_a_package_input(self):
        document = inventory()
        digest = self.classify(document)["inventoryDigest"]
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest), environment="test", expected_keys=KEYS, not_before=T0)
        self.assertEqual(caught.exception.reason, "SYNTHETIC_FIXTURE_NOT_PACKAGE_INPUT")

    def test_live_observation_needs_an_owner_acceptance_of_this_exact_digest(self):
        document = inventory(evidence=I2.LIVE_OBSERVATION, carried=("C-4",))
        digest = self.classify(document)["inventoryDigest"]
        run = lambda owner: I2.package_input(document, owner, environment="test", expected_keys=KEYS,  # noqa: E731
                                             not_before=T0, required_carried_debts=("C-4",))
        for owner, reason in ((None, "OWNER_ACCEPTANCE_ABSENT"),
                              (acceptance(H("other")), "OWNER_ACCEPTANCE_DIGEST_MISMATCH"),
                              (acceptance(digest, at=T0), "OWNER_ACCEPTANCE_BEFORE_WINDOW_END")):
            with self.subTest(reason=reason), self.assertRaises(I2.Refused) as caught:
                run(owner)
            self.assertEqual(caught.exception.reason, reason)
        value = run(acceptance(digest))
        self.assertEqual(value, {"status": "ACCEPTED", "recordSha256": digest, "artefactClasses": ["NO_SNAPSHOTS"],
                                 "namedDebts": ["C-4"]})
        self.assertIsNone(PA._snapshot_reason(PA.SnapshotInventoryResultV1(
            value["status"], value["recordSha256"], tuple(value["artefactClasses"]), tuple(value["namedDebts"]))))

    def test_a_failing_classification_is_refused_not_downgraded(self):
        document = inventory(evidence=I2.LIVE_OBSERVATION,
                             artefacts=[artefact("s", ["K_ACT_CIPHERTEXT"], access=I2.UNKNOWN)])
        digest = self.classify(document)["inventoryDigest"]
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest), environment="test", expected_keys=KEYS, not_before=T0)
        self.assertEqual(caught.exception.reason, "INVENTORY_CLASSIFICATION_FAIL")

    def test_digest_is_domain_separated_and_content_bound(self):
        document = inventory()
        digest = I2.inventory_digest(document)
        self.assertNotEqual(digest, hashlib.sha256(json.dumps(document).encode()).hexdigest())
        changed = copy.deepcopy(document)
        changed["privateEvidenceSha256"] = H("x")
        self.assertNotEqual(I2.inventory_digest(changed), digest)


# ------------------------------------------- synthetic Pr1Host (release verifier) ---

@contextlib.contextmanager
def synthetic_host():
    import pr1s_fixtures as X
    import install_authority_dev as INSTALL
    with tempfile.TemporaryDirectory() as directory:
        host = X.Pr1Host(directory).genesis_host()
        with X.stand_in_wheels() as wheels:
            payloads = X.release_payloads(wheels)
        manifest = X.install_release(host.root, X.RELEASE_SHA, payloads)
        yield X, host, hashlib.sha256(INSTALL.canonical(manifest)).hexdigest()


def pr3_inputs(X, host, *, evidence=M3.OWNER_RETAINED, **overrides):
    from lilith_authority_host import inputs as HI
    from lilith_authority_host import paths as P
    raw = {
        "kActPublication": X.PB.publication_bytes(X.P0),
        "kWitPublication": SC.canonical_publication_bytes(X.witness_publication()),
        "registryRoot": host.path(P.REGISTRY_ROOT_ANCHOR).read_bytes(),
        "registry": host.path(f"{P.REGISTRY_DIR}/{HI.registry_file_name(1)}").read_bytes(),
        "genesisPin": host.path(P.GENESIS_PIN_COPY).read_bytes(),
        "authorizationRegister": host.path(P.AUTHORIZATION_REGISTER_COPY).read_bytes(),
        "ceremonyRegister": WR.document_bytes(SC.empty_ceremony_register(X.ENV)),
    }
    raw.update(overrides)
    return {"inputType": M3.INPUT_TYPE, "schemaVersion": 1, "environment": X.ENV, "evidenceClass": evidence,
            **{name: b64u(value) for name, value in raw.items()}}


def pr3_expected(X, host, manifest_sha):
    from lilith_authority_host import paths as P
    from lilith_owner_memory import rotation_contracts as RC
    pin = json.loads(host.path(P.GENESIS_PIN_COPY).read_bytes())
    return {"kActPublicationFileSha256": hashlib.sha256(X.PB.publication_bytes(X.P0)).hexdigest(),
            "kActPublicKeySha256": X.PB.health(X.P0)["publicKeySha256"],
            "kWitPublicKeySha256": hashlib.sha256(X.F.raw_public("witness")).hexdigest(),
            "kRootPublicKeySha256": hashlib.sha256(X.F.root().public_key).hexdigest(),
            "registryHead": RC.registry_head(host.registry).to_dict(),
            "genesisPinDigest": pin["genesisWitnessDigest"],
            "genesisPinFileSha256": hashlib.sha256(host.path(P.GENESIS_PIN_COPY).read_bytes()).hexdigest(),
            "authorizationRegisterFileSha256":
                hashlib.sha256(host.path(P.AUTHORIZATION_REGISTER_COPY).read_bytes()).hexdigest(),
            "releaseSha": X.RELEASE_SHA, "releaseManifestSha256": manifest_sha}


def confirmation(digest, environment="test"):
    return {"confirmationType": M3.CONFIRMATION_TYPE, "schemaVersion": 1, "environment": environment,
            "confirmedCandidateDigest": digest, "confirmationRecordSha256": H("owner confirmation"),
            "confirmedAt": T2}


@unittest.skipUnless(POSIX, "the synthetic PR-1 host needs POSIX ownership and modes")
class Pr3MaterialTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.X, self.host, self.manifest_sha = self.stack.enter_context(synthetic_host())
        self.expected = pr3_expected(self.X, self.host, self.manifest_sha)

    def tearDown(self):
        self.stack.close()

    def assemble(self, **overrides):
        return M3.assemble(pr3_inputs(self.X, self.host, **overrides), environment=self.X.ENV, expected=self.expected)

    def test_candidate_equals_the_release_fixture_material(self):
        assembled = self.assemble()
        self.assertEqual(assembled["candidate"]["material"],
                         self.X.offhost_material(self.host, manifest_sha256=self.manifest_sha))
        self.assertEqual((assembled["ownerConfirmed"], assembled["pr3FullMaterialAccepted"]), (False, False))
        self.assertEqual(assembled["candidateDigest"], M3.candidate_digest(assembled["candidate"]))
        material = assembled["candidate"]["material"]
        self.assertEqual((material["authorizationIds"], material["burnedOrdinals"]), ([], []))

    def test_every_owner_input_must_be_the_recorded_one(self):
        from lilith_authority_host import paths as P
        other = self.X.witness_publication("other")
        register = json.loads(self.host.path(P.AUTHORIZATION_REGISTER_COPY).read_bytes())
        with_authorization = dict(register, authorizations=[
            {"authorizationId": "test-only.authorization.1", "kind": "REGISTRY_HEAD_ADVANCE",
             "authorizationSha256": H("authorization")}])
        cases = {
            "KACT_PUBLICATION_NOT_RECORD": dict(kActPublication=self.X.PB.publication_bytes(self.X.PB.S2)),
            "KWIT_FINGERPRINT_MISMATCH": dict(kWitPublication=SC.canonical_publication_bytes(other)),
            "GENESIS_PIN_MISMATCH": dict(genesisPin=WR.document_bytes(WR.OwnerGenesisPinV1("test", H("p")).to_dict())),
            "AUTHORIZATION_REGISTER_COPY_MISMATCH": dict(authorizationRegister=WR.document_bytes(with_authorization)),
            "REGISTRY_INVALID": dict(registry=b"{}"),
        }
        for reason, override in cases.items():
            with self.subTest(reason=reason), self.assertRaises(M3.Refused) as caught:
                self.assemble(**override)
            self.assertEqual(caught.exception.reason, reason)

    def test_authorizations_and_burned_ordinals_must_stay_empty(self):
        from lilith_authority_host import paths as P
        register = json.loads(self.host.path(P.AUTHORIZATION_REGISTER_COPY).read_bytes())
        with_authorization = WR.document_bytes(dict(register, authorizations=[
            {"authorizationId": "test-only.authorization.1", "kind": "REGISTRY_HEAD_ADVANCE",
             "authorizationSha256": H("authorization")}]))
        expected = dict(self.expected, authorizationRegisterFileSha256=hashlib.sha256(with_authorization).hexdigest())
        with self.assertRaises(M3.Refused) as caught:
            M3.assemble(pr3_inputs(self.X, self.host, authorizationRegister=with_authorization),
                        environment="test", expected=expected)
        self.assertEqual(caught.exception.reason, "AUTHORIZATION_LIST_NOT_EMPTY_AT_PR1")
        burned = {"registerType": SC.CEREMONY_REGISTER_TYPE, "schemaVersion": 1, "environment": "test",
                  "ceremonies": [{"successorOrdinal": 1, "keyId": "x"}]}
        with self.assertRaises(M3.Refused) as caught:
            self.assemble(ceremonyRegister=json.dumps(burned).encode())
        self.assertEqual(caught.exception.reason, "CEREMONY_REGISTER_INVALID")

    def test_confirmation_gates_the_package_input(self):
        assembled = self.assemble()
        with self.assertRaises(M3.Refused) as caught:
            M3.package_input(assembled, None, environment="test")
        self.assertEqual(caught.exception.reason, "OWNER_CONFIRMATION_ABSENT")
        with self.assertRaises(M3.Refused) as caught:
            M3.package_input(assembled, confirmation(H("other")), environment="test")
        self.assertEqual(caught.exception.reason, "OWNER_CONFIRMATION_DIGEST_MISMATCH")
        self.assertEqual(M3.package_input(assembled, confirmation(assembled["candidateDigest"]), environment="test"),
                         assembled["candidate"]["material"])
        synthetic = self.assemble(evidence=M3.SYNTHETIC_FIXTURE)
        with self.assertRaises(M3.Refused) as caught:
            M3.package_input(synthetic, confirmation(synthetic["candidateDigest"]), environment="test")
        self.assertEqual(caught.exception.reason, "SYNTHETIC_FIXTURE_NOT_PACKAGE_INPUT")

    def test_dev_expectations_name_the_accepted_records(self):
        self.assertEqual(M3.DEV_EXPECTED["registryHead"]["registryVersion"], 1)
        self.assertEqual(M3.DEV_EXPECTED["releaseSha"], RI.DEV_PINS["releaseSha"])
        self.assertEqual(M3.DEV_EXPECTED["releaseManifestSha256"], RI.DEV_PINS["attestedManifestSha256"])
        self.assertEqual(M3.DEV_EXPECTED["kActPublicKeySha256"], RI.DEV_PINS["kActPublicKeySha256"])
        records = ROOT / "docs/architecture"
        for key, record in (("kRootPublicKeySha256", "slice-15b2b-b1b3e-mb1-kroot-completion.md"),
                            ("kWitPublicKeySha256", "slice-15b2b-b1b3e-mb2-kwit-completion.md"),
                            ("genesisPinFileSha256", "slice-15b2b-b1b3e-mb7-mb8-package-a-completion.md"),
                            ("authorizationRegisterFileSha256", "slice-15b2b-b1b3e-mb7-mb8-package-a-completion.md"),
                            ("releaseManifestSha256", "slice-15b2b-b1b3e-pr1a-acceptance.md")):
            with self.subTest(key=key):
                self.assertIn(M3.DEV_EXPECTED[key], (records / record).read_text(encoding="utf-8"))


# ---------------------------------------------------------- readiness inputs ---

def mapped_proof(X, name):
    proof = X.proof(name, PA.REQUIRED_DEPLOYER_MATURITY if name == "DEPLOYER_DENIAL" else None)
    return {**proof, "producer": RI.PROPOSED_PROOF_PRODUCERS[name], "observedAt": T1, "evidenceSha256": H(name)}


def build_inputs(X, host, manifest_sha, *, proofs=None, snapshot=None, material=None, activation=None, **overrides):
    current = X.current_document(host)
    value = {
        "buildType": RI.BUILD_TYPE, "schemaVersion": 1, "environment": X.ENV,
        "window": {"notBefore": T0, "notAfter": T2},
        "release": {"releaseSha": X.RELEASE_SHA, "attestedManifestSha256": manifest_sha,
                    "reviewedRuntimeDigests": None},
        "current": {**current, "observedAt": T1, "evidenceSha256": H("current")},
        "kActPublication": {"bytes": b64u(X.PB.publication_bytes(X.P0))},
        "kWitPublication": {"bytes": b64u(SC.canonical_publication_bytes(X.witness_publication()))},
        "proofs": proofs if proofs is not None else {
            name: mapped_proof(X, name) for name, producer in RI.PROPOSED_PROOF_PRODUCERS.items() if producer},
        "activation": activation or {"stdout": REAL_HOST_ACTIVATION + "\n", "exitCode": 1, "b1cUnchanged": True,
                                     "observedAt": T1, "evidenceSha256": H("activation")},
        "snapshotInventory": snapshot, "offHostMaterial": material,
    }
    value.update(overrides)
    return value


def fixture_pins(X, host, manifest_sha):
    return {"releaseSha": X.RELEASE_SHA, "attestedManifestSha256": manifest_sha,
            "pinnedCurrentSha256": X.PB.BLOB[X.P0],
            "kActPublicationFileSha256": hashlib.sha256(X.PB.publication_bytes(X.P0)).hexdigest(),
            "kActPublicKeySha256": X.PB.health(X.P0)["publicKeySha256"],
            "kWitPublicKeySha256": hashlib.sha256(X.F.raw_public("witness")).hexdigest()}


@unittest.skipUnless(POSIX, "the synthetic PR-1 host needs POSIX ownership and modes")
class ReadinessInputTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.X, self.host, self.manifest_sha = self.stack.enter_context(synthetic_host())
        self.pins = fixture_pins(self.X, self.host, self.manifest_sha)

    def tearDown(self):
        self.stack.close()

    def build(self, **kwargs):
        return RI.build(build_inputs(self.X, self.host, self.manifest_sha, **kwargs), environment="test",
                        pins=self.pins)

    def evaluate(self, document, mode="HOLD_RELEASE_ELIGIBILITY"):
        from lilith_authority_root import verifier as V
        owner = V.parse_verifier_inputs(document)
        return V.evaluate(mode, owner, root=self.host.root, owner_uid=self.X.UID, owner_gid=self.X.GID,
                          health=self.X.health_p0, run=self.X.fake_systemctl())

    def roundtrip(self, raw):
        return RI.read_envelope(io.BytesIO(raw), expected_sha256=hashlib.sha256(raw).hexdigest(), environment="test")

    def test_build_is_deterministic_and_the_release_parser_accepts_it(self):
        first, report = self.build()
        self.assertEqual(first, self.build()[0])
        self.assertTrue(first.endswith(b"\n") and first.count(b"\n") == 1)
        document = self.roundtrip(first)
        self.assertEqual(RI.document_digest(document), report["inputsSha256"])
        self.assertEqual(set(document), {"inputType", "schemaVersion", "environment", "releaseSha",
                                         "attestedManifestSha256", "reviewedRuntimeDigests", "pinnedCurrentSha256",
                                         "firstPreflightCurrent", "kActPublication", "kWitPublication", "proofs",
                                         "activation", "snapshotInventory", "offHostMaterial"})
        self.assertIs(report["readinessEvaluated"], False)

    def test_the_real_verifier_is_not_ready_for_exactly_the_known_gaps(self):
        result = self.evaluate(self.roundtrip(self.build()[0]))
        self.assertEqual(result.status, "NOT_READY")
        failing = {name: outcome.reason for name, outcome in result.checks.items() if outcome.status != "PASS"}
        self.assertEqual(failing, {
            "E07_SIGNER_CUSTODY_DENIAL": "PROOF_MISSING:OS_DENIAL",
            "E18_OFFHOST_REPRODUCTION_INPUTS": "OFFHOST_MATERIAL_UNAVAILABLE",
            "E19_ACTIVATION_DARK": "ACTIVATION_NOT_DARK",
            "E20_SNAPSHOT_INVENTORY": "SNAPSHOT_INVENTORY_ABSENT_PR2",
            "E21_OFFHOST_REGISTER": "OFFHOST_REGISTER_ABSENT_PR3",
            "E22_SECRET_HYGIENE": "PROOF_MISSING:SECRET_HYGIENE",
            "E23_PRESERVATION_SET": "PROOF_MISSING:PRESERVATION_SET"})
        self.assertTrue(result.readiness.ready)          # root HOLD_RELEASE_ELIGIBILITY READY != package READY

    def test_pr2_and_pr3_tool_outputs_close_e18_e20_e21_and_nothing_else(self):
        document = inventory(evidence=I2.LIVE_OBSERVATION, carried=("C-4",))
        digest = I2.classify(document, environment="test", expected_keys=KEYS)["inventoryDigest"]
        snapshot = I2.package_input(document, acceptance(digest), environment="test", expected_keys=KEYS,
                                    not_before=T0, required_carried_debts=("C-4",))
        assembled = M3.assemble(pr3_inputs(self.X, self.host), environment="test",
                                expected=pr3_expected(self.X, self.host, self.manifest_sha))
        material = M3.package_input(assembled, confirmation(assembled["candidateDigest"]), environment="test")
        raw, report = self.build(snapshot=snapshot, material=material)
        result = self.evaluate(self.roundtrip(raw))
        failing = {name for name, outcome in result.checks.items() if outcome.status != "PASS"}
        self.assertEqual(failing, {"E07_SIGNER_CUSTODY_DENIAL", "E19_ACTIVATION_DARK", "E22_SECRET_HYGIENE",
                                   "E23_PRESERVATION_SET"})
        self.assertEqual(M3.offhost_reproduction(material, result.package), [])
        self.assertEqual(report["expectedNotReady"], ["E19_ACTIVATION_DARK:ACTIVATION_NOT_DARK",
                                                      "PROOF_MISSING:OS_DENIAL", "PROOF_MISSING:PRESERVATION_SET",
                                                      "PROOF_MISSING:SECRET_HYGIENE"])

    def test_unmapped_proofs_are_refused_never_admitted(self):
        for name in ("OS_DENIAL", "SECRET_HYGIENE", "PRESERVATION_SET"):
            proofs = {name: {**self.X.proof(name), "producer": "anything", "observedAt": T1,
                             "evidenceSha256": H(name)}}
            with self.subTest(name=name), self.assertRaises(RI.Refused) as caught:
                self.build(proofs=proofs)
            self.assertEqual(caught.exception.reason, "PROOF_PRODUCER_UNMAPPED")
        proofs = {"SIGNER_DENIAL": {**mapped_proof(self.X, "SIGNER_DENIAL"), "producer": "scripts/other.py"}}
        with self.assertRaises(RI.Refused) as caught:
            self.build(proofs=proofs)
        self.assertEqual(caught.exception.reason, "PROOF_PRODUCER_MISMATCH")

    def test_fail_values_pass_through_and_stale_evidence_is_refused(self):
        proofs = {n: mapped_proof(self.X, n) for n in ("BROKER_DENIAL", "BROKER_PRESERVATION")}
        proofs["BROKER_PRESERVATION"]["result"] = "FAIL"
        result = self.evaluate(self.roundtrip(self.build(proofs=proofs)[0]))
        self.assertEqual(result.checks["E09_BROKER_DENIAL_PRESERVATION"].reason,
                         "PROOF_NOT_PASS:BROKER_PRESERVATION")
        stale = {"SIGNER_DENIAL": {**mapped_proof(self.X, "SIGNER_DENIAL"), "observedAt": "2026-10-11T00:00:00Z"}}
        with self.assertRaises(RI.Refused) as caught:
            self.build(proofs=stale)
        self.assertEqual(caught.exception.reason, "INPUT_STALE")

    def test_activation_is_the_complete_host_line_passed_verbatim(self):
        raw, _report = self.build()
        self.assertEqual(self.roundtrip(raw)["activation"]["line"], REAL_HOST_ACTIVATION)
        for stdout, exit_code in ((PA.ACTIVATION_DARK_LINE + "\n", 1), (REAL_HOST_ACTIVATION + "\n", 0),
                                  (REAL_HOST_ACTIVATION, 1), ("ACTIVATION=ACCEPTED {}\n", 1)):
            activation = {"stdout": stdout, "exitCode": exit_code, "b1cUnchanged": True, "observedAt": T1,
                          "evidenceSha256": H("a")}
            with self.subTest(stdout=stdout, exit_code=exit_code), self.assertRaises(RI.Refused):
                self.build(activation=activation)

    def test_known_defect_e19_rejects_the_complete_host_line(self):
        """Pins the PR #185-class mismatch in the release judge (record §8). A fix must change this test."""
        self.assertEqual(PA.ACTIVATION_DARK_LINE, "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT")
        self.assertNotEqual(PA.ACTIVATION_DARK_LINE, RI.HOST_ACTIVATION_DARK_LINE)
        self.assertTrue(RI.HOST_ACTIVATION_DARK_LINE.startswith(PA.ACTIVATION_DARK_LINE + " "))
        dev = (ROOT / "scripts/dev_deployer/lilith_activation_verify.py").read_text(encoding="utf-8")
        self.assertIn('print(f"ACTIVATION=NOT_ACCEPTED reason={exc.reason} advisoryConfigEnabled={advisory}")', dev)

    def test_publications_and_current_must_be_the_pinned_ones(self):
        cases = {
            "KACT_PUBLICATION_NOT_RECORD": dict(kActPublication={"bytes": b64u(self.X.PB.publication_bytes(
                self.X.PB.S2))}),
            "KWIT_FINGERPRINT_MISMATCH": dict(kWitPublication={"bytes": b64u(SC.canonical_publication_bytes(
                self.X.witness_publication("other")))}),
            "RELEASE_NOT_RECORD": dict(release={"releaseSha": "0" * 40, "attestedManifestSha256": self.manifest_sha,
                                                "reviewedRuntimeDigests": None}),
        }
        for reason, override in cases.items():
            with self.subTest(reason=reason), self.assertRaises(RI.Refused) as caught:
                self.build(**override)
            self.assertEqual(caught.exception.reason, reason)
        current = {**self.X.current_document(self.host), "sha256": H("other"), "observedAt": T1,
                   "evidenceSha256": H("c")}
        with self.assertRaises(RI.Refused) as caught:
            self.build(current=current)
        self.assertEqual(caught.exception.reason, "CURRENT_SHA256_NOT_PINNED")

    def test_envelope_reader_is_exact(self):
        raw, report = self.build()
        digest = hashlib.sha256(raw).hexdigest()
        mutations = {
            "ENVELOPE_DIGEST_MISMATCH": (raw, H("other")),
            "ENVELOPE_NOT_CANONICAL": (json.dumps(json.loads(raw), indent=1).encode() + b"\n", None),
            "ENVELOPE_SIZE": (b"", None),
        }
        for reason, (body, expected) in mutations.items():
            with self.subTest(reason=reason), self.assertRaises(RI.Refused) as caught:
                RI.read_envelope(io.BytesIO(body), expected_sha256=expected or hashlib.sha256(body).hexdigest(),
                                 environment="test")
            self.assertEqual(caught.exception.reason, reason)
        envelope = json.loads(raw)
        envelope["inputs"]["releaseSha"] = "1" * 40
        tampered = RI.envelope_bytes(envelope)
        with self.assertRaises(RI.Refused) as caught:
            RI.read_envelope(tampered, expected_sha256=hashlib.sha256(tampered).hexdigest(), environment="test")
        self.assertEqual(caught.exception.reason, "INPUTS_DIGEST_MISMATCH")
        with self.assertRaises(RI.Refused) as caught:
            RI.read_envelope(raw, expected_sha256=digest, environment="dev")
        self.assertEqual(caught.exception.reason, "ENVELOPE_ENVIRONMENT_MISMATCH")
        self.assertEqual(report["envelopeSha256"], digest)


# --------------------------------------------------------------- source guards ---

class SourceGuardTests(unittest.TestCase):
    SOURCES = ("mb12_pr2_inventory.py", "mb12_pr3_material.py", "mb12_readiness_inputs.py")

    def test_no_host_contact_no_secret_access_no_subprocess(self):
        for name in self.SOURCES:
            source = (TOOLS / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                for needle in ("import subprocess", "import socket", "plink", "gcloud", "systemctl", "/run/credentials",
                               "/etc/credstore", "os.system", "urllib", "requests", "open("):
                    self.assertFalse(needle in source, needle)

    def test_release_judge_and_release_tree_untouched(self):
        import release_file_set  # services/authority-dev
        pinned = getattr(release_file_set, "SHARED_HASHES", {})
        path = "services/owner-memory-control/lilith_owner_memory/pr1_acceptance.py"
        if path in pinned:
            digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            self.assertEqual(digest, pinned[path])
        for name in self.SOURCES:
            self.assertFalse(any(name in key for key in pinned), name)

    def test_unmapped_proof_names_are_exactly_the_recorded_gaps(self):
        self.assertEqual(tuple(RI.PROPOSED_PROOF_PRODUCERS), PA.REQUIRED_PROOFS)
        self.assertEqual({n for n, p in RI.PROPOSED_PROOF_PRODUCERS.items() if p is None},
                         {"OS_DENIAL", "SECRET_HYGIENE", "PRESERVATION_SET"})
        for producer in {p for p in RI.PROPOSED_PROOF_PRODUCERS.values() if p}:
            self.assertTrue((ROOT / producer.split(":")[0]).is_file(), producer)


if __name__ == "__main__":
    unittest.main()
