"""15B2b-B1b-3e M-B12 PR-B1: PR-2 inventory, PR-3 material and readiness-input tooling (TEST-ONLY, synthetic).

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb1-prerequisite-tooling.md. No live system: the PR-2 documents are
synthetic, the PR-3 bytes are the TEST_ONLY Prep B / PR-1S fixture identities, the proof transcripts are synthetic
producer-shaped bytes, and the end-to-end checks run the release's root verifier over the synthetic `Pr1Host`
(environment `test`, never `dev`). TEST trust objects stand in for merged owner-record pins; DEV trust is the
repository's own (empty) pins and is never overridable.

The `Forgery*` classes are regressions for the five blockers of the PR #186 owner review: each uses the exact input
that the reviewed head `64df007` accepted.
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
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, ROOT / "services/authority-dev", ROOT / "services/authority-dev/tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mb12_pr2_inventory as I2  # noqa: E402
import mb12_pr3_material as M3  # noqa: E402
import mb12_readiness_inputs as RI  # noqa: E402
from lilith_owner_memory import burned_identities as BI  # noqa: E402
from lilith_owner_memory import pr1_acceptance as PA  # noqa: E402
from lilith_owner_memory import successor_custody as SC  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402

POSIX = os.name == "posix"
H = lambda label: hashlib.sha256(label.encode()).hexdigest()  # noqa: E731
KEYS = {"K_ACT": H("synthetic k-act"), "K_WIT": H("synthetic k-wit")}
T0, T1, T2 = "2026-10-12T10:00:00Z", "2026-10-12T10:30:00Z", "2026-10-12T11:00:00Z"
REAL_HOST_ACTIVATION = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false"
OWNER_RECORD = H("owner record")
OWNER_CONFIRMATION = H("owner confirmation")
OD_M12_3_CUTOFF = "2026-10-14T18:27:00Z"          # OD-M12-3, owner-accepted 2026-10-15 (after deploy 38614708729)


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


# ----------------------------------------------------------------- PR-2 inventory ---

def inventory(*, artefacts=(), evidence=I2.SYNTHETIC_FIXTURE, environment="test", carried=(), window=(T0, T1),
              **listing_overrides):
    counts = {kind: 0 for kind in I2.ARTEFACT_KINDS}
    for artefact in artefacts:
        counts[artefact["kind"]] += 1
    listings = []
    for kind in I2.LISTING_KINDS:
        item = {"kind": kind, "complete": True, "count": counts.get(kind, 0), "listingSha256": H(kind)}
        item.update(listing_overrides.get(kind, {}))
        listings.append(item)
    return {"inventoryType": I2.INVENTORY_TYPE, "schemaVersion": 1, "environment": environment,
            "evidenceClass": evidence, "window": {"startedAt": window[0], "endedAt": window[1]},
            "keys": [{"role": "K_ACT", "publicKeySha256": KEYS["K_ACT"], "sealedUnder": "HOST_KEY"},
                     {"role": "K_WIT", "publicKeySha256": KEYS["K_WIT"], "sealedUnder": "HOST_KEY"},
                     {"role": "HOST_KEY", "publicKeySha256": None, "sealedUnder": None}],
            "listings": listings, "artefacts": list(artefacts),
            "carriedDebts": [{"name": name, "role": "K_WIT", "recordSha256": H(name)} for name in carried],
            "privateEvidenceSha256": H("private evidence")}


def artefact(name, material, *, location=I2.INSIDE, access=I2.KNOWN, debt=None, kind="DISK_SNAPSHOTS"):
    return {"artefactId": name, "kind": kind, "material": list(material), "location": location,
            "accessHistory": access, "debtName": debt}


def acceptance(digest, *, environment="test", at=T2, record=OWNER_RECORD):
    return {"acceptanceType": I2.ACCEPTANCE_TYPE, "schemaVersion": 1, "environment": environment,
            "acceptedInventoryDigest": digest, "acceptanceRecordSha256": record, "acceptedAt": at}


def pr2_trust(*digests, not_before=T0, carried=("C-4",)):
    """A TEST stand-in for a merged owner record pinning each digest."""
    return I2.Pr2TrustV1(dict(KEYS), not_before, {digest: OWNER_RECORD for digest in digests}, carried)


def live_inventory(**kwargs):
    kwargs.setdefault("carried", ("C-4",))
    document = inventory(evidence=I2.LIVE_OBSERVATION, **kwargs)
    return document, I2.inventory_digest(document)


# OD-M12-6 (owner-accepted 2026-10-16): the only DEV proof transcripts an owner record has established.
# E-20 (owner-accepted 2026-10-17): the only DEV PR-2 inventory an owner record has established.
E20_ACCEPTED_INVENTORIES = {"61d9268613c13354c0184a30909a21f4cd2f8db20424bcb10f6f2e51168d46cf":
                            "6a3dd81b80453b805ac46ae058dd4ea56c22c32855909a82ec5027b8ee894682"}
OD_M12_6_TRANSCRIPTS = {
    "SIGNER_DENIAL": frozenset({"92dcb9aa87a40244ef02a38901f319491197b82e31fb064f6e356a57a9ec32c1"}),
    "BROKER_DENIAL": frozenset({"92dcb9aa87a40244ef02a38901f319491197b82e31fb064f6e356a57a9ec32c1"}),
    "OS_DENIAL": frozenset({"3cb0e744abda6a2540ad56a25e4ad1b144449833af296756eb37b0c21bd29b4a"}),
    "BROKER_PRESERVATION": frozenset({"79387fe7d1db1e7eab0d8e508991656ba195d284cefac3889ffff9595f221c40"}),
    "PRESERVATION_SET": frozenset({"4692f3bae979aca82782a66605a3235939420223aa7841a931ad9a473f1e863e"}),
}

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
        self.assertEqual(report["keyClasses"]["K_WIT"], "KNOWN_CUSTODY_DEBT")
        self.assertIn("DEBT_NOT_NAMED:a", report["reasons"])
        outside = [artefact("a", ["K_ACT_CIPHERTEXT"]), artefact("b", ["HOST_KEY_SECRET"], location=I2.OUTSIDE)]
        report = self.classify(inventory(artefacts=outside))
        self.assertEqual(set(report["keyClasses"].values()), {"EXPOSED_PRIVATE_MATERIAL"})
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
        for mutate, reason in ((lambda d: d["keys"][0].update(sealedUnder=None), "INVENTORY_KEY_RELATIONSHIP"),
                               (lambda d: d["keys"][1].update(publicKeySha256=H("other")),
                                "INVENTORY_KEY_IDENTITY_MISMATCH"),
                               (lambda d: d.update(keys=d["keys"][:2]), "INVENTORY_KEYS_NOT_EXACT")):
            document = inventory()
            mutate(document)
            with self.subTest(reason=reason), self.assertRaises(I2.Refused) as caught:
                self.classify(document)
            self.assertEqual(caught.exception.reason, reason)
        self.assertEqual(I2.DEV_KEY_IDENTITIES["K_ACT"], RI.DEV_PINS["kActPublicKeySha256"])
        self.assertEqual(I2.DEV_KEY_IDENTITIES["K_WIT"], RI.DEV_PINS["kWitPublicKeySha256"])

    def test_stale_window_and_carried_debts(self):
        with self.assertRaises(I2.Refused) as caught:
            self.classify(inventory(), not_before=T1)
        self.assertEqual(caught.exception.reason, "INVENTORY_STALE")
        self.assertIn("CARRIED_DEBT_MISSING:C-4",
                      self.classify(inventory(), required_carried_debts=("C-4",))["reasons"])
        report = self.classify(inventory(carried=("C-4",)), required_carried_debts=("C-4",))
        self.assertEqual((report["classification"], report["namedDebts"]), ("PASS", ["C-4"]))

    def test_established_owner_acceptance_gives_the_e20_input(self):
        document, digest = live_inventory()
        value = I2.package_input(document, acceptance(digest), environment="test", trust=pr2_trust(digest))
        self.assertEqual(value, {"status": "ACCEPTED", "recordSha256": digest, "artefactClasses": ["NO_SNAPSHOTS"],
                                 "namedDebts": ["C-4"]})
        self.assertIsNone(PA._snapshot_reason(PA.SnapshotInventoryResultV1(
            value["status"], value["recordSha256"], tuple(value["artefactClasses"]), tuple(value["namedDebts"]))))

    def test_acceptance_document_checks(self):
        document, digest = live_inventory()
        for owner, reason in ((None, "OWNER_ACCEPTANCE_ABSENT"),
                              (acceptance(H("other")), "OWNER_ACCEPTANCE_DIGEST_MISMATCH"),
                              (acceptance(digest, at=T0), "OWNER_ACCEPTANCE_BEFORE_WINDOW_END"),
                              (dict(acceptance(digest), schemaVersion=True), "OWNER_ACCEPTANCE_MALFORMED")):
            with self.subTest(reason=reason), self.assertRaises(I2.Refused) as caught:
                I2.package_input(document, owner, environment="test", trust=pr2_trust(digest))
            self.assertEqual(caught.exception.reason, reason)

    def test_synthetic_or_failing_inventories_are_never_package_inputs(self):
        document = inventory()
        digest = I2.inventory_digest(document)
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest), environment="test", trust=pr2_trust(digest, carried=()))
        self.assertEqual(caught.exception.reason, "SYNTHETIC_FIXTURE_NOT_PACKAGE_INPUT")
        document, digest = live_inventory(artefacts=[artefact("s", ["K_ACT_CIPHERTEXT"], access=I2.UNKNOWN)])
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest), environment="test", trust=pr2_trust(digest))
        self.assertEqual(caught.exception.reason, "INVENTORY_CLASSIFICATION_FAIL")

    def test_digest_is_domain_separated_and_content_bound(self):
        document = inventory()
        digest = I2.inventory_digest(document)
        self.assertNotEqual(digest, hashlib.sha256(json.dumps(document).encode()).hexdigest())
        changed = copy.deepcopy(document)
        changed["privateEvidenceSha256"] = H("x")
        self.assertNotEqual(I2.inventory_digest(changed), digest)


class ForgeryPr2Tests(unittest.TestCase):
    """Blockers 1 (PR-2 half), 3, 4, 5 and the minor finding."""

    def test_blocker1_a_caller_made_acceptance_is_not_established(self):
        document, digest = live_inventory()                      # accepted at 64df007 with any acceptance document
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest), environment="test", trust=pr2_trust())
        self.assertEqual(caught.exception.reason, "OWNER_ACCEPTANCE_NOT_ESTABLISHED")
        with self.assertRaises(I2.Refused) as caught:              # pinned digest, different record
            I2.package_input(document, acceptance(digest, record=H("forged record")), environment="test",
                             trust=pr2_trust(digest))
        self.assertEqual(caught.exception.reason, "OWNER_ACCEPTANCE_NOT_ESTABLISHED")
        self.assertEqual(dict(I2.DEV_ACCEPTED_INVENTORIES), E20_ACCEPTED_INVENTORIES)

    def test_blocker3_not_before_and_expected_keys_are_required(self):
        document, digest = live_inventory()
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest), environment="test")
        self.assertEqual(caught.exception.reason, "TRUST_REQUIRED")
        for trust, reason in ((I2.Pr2TrustV1(dict(KEYS), None, {digest: OWNER_RECORD}, ("C-4",)),
                               "INVENTORY_MALFORMED"),
                              (I2.Pr2TrustV1(None, T0, {digest: OWNER_RECORD}, ("C-4",)), "TRUST_MALFORMED"),
                              (I2.Pr2TrustV1({"K_ACT": KEYS["K_ACT"]}, T0, {digest: OWNER_RECORD}, ("C-4",)),
                               "TRUST_MALFORMED")):
            with self.subTest(reason=reason), self.assertRaises(I2.Refused) as caught:
                I2.package_input(document, acceptance(digest), environment="test", trust=trust)
            self.assertEqual(caught.exception.reason, reason)
        rogue = copy.deepcopy(document)                         # accepted at 64df007 with expected_keys=None
        rogue["keys"][0]["publicKeySha256"] = H("rogue")
        rogue_digest = I2.inventory_digest(rogue)
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(rogue, acceptance(rogue_digest), environment="test", trust=pr2_trust(rogue_digest))
        self.assertEqual(caught.exception.reason, "INVENTORY_KEY_IDENTITY_MISMATCH")

    def test_blocker3_dev_trust_is_pinned_and_not_overridable(self):
        document, digest = live_inventory(environment="dev")
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest, environment="dev"), environment="dev",
                             trust=pr2_trust(digest))
        self.assertEqual(caught.exception.reason, "DEV_TRUST_NOT_OVERRIDABLE")
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest, environment="dev"), environment="dev")
        self.assertEqual(caught.exception.reason, "INVENTORY_STALE")         # OD-M12-3 accepted: 2026-10-12 < cutoff
        self.assertEqual(I2.DEV_FRESHNESS_NOT_BEFORE, OD_M12_3_CUTOFF)

    def test_blocker4_admin_create_calls_without_artefacts_are_unknown_provenance(self):
        document, digest = live_inventory(ADMIN_ACTIVITY_CREATE_CALLS={"count": 3})   # NO_SNAPSHOTS at 64df007
        report = I2.classify(document, environment="test", expected_keys=KEYS)
        self.assertEqual(report["classification"], "FAIL")
        self.assertEqual(report["artefactClasses"], ["UNKNOWN_PROVENANCE"])
        self.assertEqual(set(report["keyClasses"].values()), {"UNKNOWN_PROVENANCE"})
        self.assertIn("ADMIN_ACTIVITY_CREATE_CALLS_UNEXPLAINED:3", report["reasons"])
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest), environment="test", trust=pr2_trust(digest))
        self.assertEqual(caught.exception.reason, "INVENTORY_CLASSIFICATION_FAIL")

    def test_blocker5_inventory_before_the_accepted_cutoff_is_stale(self):
        document, digest = live_inventory(window=("2016-01-01T00:00:00Z", "2036-01-01T00:00:00Z"))
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest, at="2036-01-01T00:00:00Z"), environment="test",
                             trust=pr2_trust(digest))
        self.assertEqual(caught.exception.reason, "INVENTORY_STALE")

    def test_minor_empty_material_is_refused(self):
        with self.assertRaises(I2.Refused) as caught:              # SAFE_RETAINED_CIPHERTEXT at 64df007
            I2.classify(inventory(artefacts=[artefact("s", [])]), environment="test", expected_keys=KEYS)
        self.assertEqual(caught.exception.reason, "INVENTORY_ARTEFACT_MATERIAL_EMPTY")


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


def confirmation(digest, environment="test", record=OWNER_CONFIRMATION):
    return {"confirmationType": M3.CONFIRMATION_TYPE, "schemaVersion": 1, "environment": environment,
            "confirmedCandidateDigest": digest, "confirmationRecordSha256": record, "confirmedAt": T2}


@unittest.skipUnless(POSIX, "the synthetic PR-1 host needs POSIX ownership and modes")
class Pr3MaterialTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.X, self.host, self.manifest_sha = self.stack.enter_context(synthetic_host())
        self.expected = pr3_expected(self.X, self.host, self.manifest_sha)

    def tearDown(self):
        self.stack.close()

    def trust(self, *digests, expected=None):
        return M3.Pr3TrustV1(expected or self.expected, {digest: OWNER_CONFIRMATION for digest in digests})

    def assemble(self, trust=None, **overrides):
        return M3.assemble(pr3_inputs(self.X, self.host, **overrides), environment="test",
                           trust=trust or self.trust())

    def test_candidate_equals_the_release_fixture_material(self):
        assembled = self.assemble()
        self.assertEqual(assembled["candidate"]["material"],
                         self.X.offhost_material(self.host, manifest_sha256=self.manifest_sha))
        self.assertEqual((assembled["ownerConfirmed"], assembled["pr3FullMaterialAccepted"]), (False, False))
        material = assembled["candidate"]["material"]
        self.assertEqual((material["authorizationIds"], material["burnedOrdinals"]), ([], []))

    def test_every_owner_input_must_be_the_recorded_one(self):
        from lilith_authority_host import paths as P
        register = json.loads(self.host.path(P.AUTHORIZATION_REGISTER_COPY).read_bytes())
        with_authorization = dict(register, authorizations=[
            {"authorizationId": "test-only.authorization.1", "kind": "REGISTRY_HEAD_ADVANCE",
             "authorizationSha256": H("authorization")}])
        cases = {
            "KACT_PUBLICATION_NOT_RECORD": dict(kActPublication=self.X.PB.publication_bytes(self.X.PB.S2)),
            "KWIT_FINGERPRINT_MISMATCH": dict(kWitPublication=SC.canonical_publication_bytes(
                self.X.witness_publication("other"))),
            "GENESIS_PIN_MISMATCH": dict(genesisPin=WR.document_bytes(WR.OwnerGenesisPinV1("test", H("p")).to_dict())),
            "AUTHORIZATION_REGISTER_COPY_MISMATCH": dict(authorizationRegister=WR.document_bytes(with_authorization)),
            "REGISTRY_INVALID": dict(registry=b"{}"),
            "CEREMONY_REGISTER_INVALID": dict(ceremonyRegister=b'{"a":1,"a":2}'),   # duplicate keys
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
            self.assemble(trust=self.trust(expected=expected), authorizationRegister=with_authorization)
        self.assertEqual(caught.exception.reason, "AUTHORIZATION_LIST_NOT_EMPTY_AT_PR1")
        burned = {"registerType": SC.CEREMONY_REGISTER_TYPE, "schemaVersion": 1, "environment": "test",
                  "ceremonies": [{"successorOrdinal": 1, "keyId": "x"}]}
        with self.assertRaises(M3.Refused) as caught:
            self.assemble(ceremonyRegister=json.dumps(burned).encode())
        self.assertEqual(caught.exception.reason, "CEREMONY_REGISTER_INVALID")

    def test_burned_identities_are_refused(self):
        witness = hashlib.sha256(self.X.F.raw_public("witness")).hexdigest()
        with mock.patch.object(BI, "BURNED_PUBLIC_KEY_SHA256", frozenset({witness})), \
                self.assertRaises(M3.Refused) as caught:
            self.assemble()
        self.assertEqual((caught.exception.reason, caught.exception.detail),
                         (BI.BURNED_REHEARSAL_IDENTITY, f"publicKeySha256:{witness}"))

    def test_established_confirmation_gives_the_e21_input(self):
        digest = self.assemble()["candidateDigest"]
        material = M3.package_input(pr3_inputs(self.X, self.host), confirmation(digest), environment="test",
                                    trust=self.trust(digest))
        self.assertEqual(material, self.X.offhost_material(self.host, manifest_sha256=self.manifest_sha))
        for owner, reason in ((None, "OWNER_CONFIRMATION_ABSENT"),
                              (confirmation(H("other")), "OWNER_CONFIRMATION_DIGEST_MISMATCH")):
            with self.subTest(reason=reason), self.assertRaises(M3.Refused) as caught:
                M3.package_input(pr3_inputs(self.X, self.host), owner, environment="test", trust=self.trust(digest))
            self.assertEqual(caught.exception.reason, reason)
        synthetic = pr3_inputs(self.X, self.host, evidence=M3.SYNTHETIC_FIXTURE)
        synthetic_digest = M3.assemble(synthetic, environment="test", trust=self.trust())["candidateDigest"]
        with self.assertRaises(M3.Refused) as caught:
            M3.package_input(synthetic, confirmation(synthetic_digest), environment="test",
                             trust=self.trust(synthetic_digest))
        self.assertEqual(caught.exception.reason, "SYNTHETIC_FIXTURE_NOT_PACKAGE_INPUT")

    def test_blocker1_a_caller_made_confirmation_is_not_established(self):
        digest = self.assemble()["candidateDigest"]          # accepted at 64df007 with any confirmation document
        for trust, record in ((self.trust(), OWNER_CONFIRMATION), (self.trust(digest), H("forged record"))):
            with self.subTest(record=record), self.assertRaises(M3.Refused) as caught:
                M3.package_input(pr3_inputs(self.X, self.host), confirmation(digest, record=record),
                                 environment="test", trust=trust)
            self.assertEqual(caught.exception.reason, "OWNER_CONFIRMATION_NOT_ESTABLISHED")
        with self.assertRaises(M3.Refused) as caught:
            M3.trust_for("dev", self.trust(digest))
        self.assertEqual(caught.exception.reason, "DEV_TRUST_NOT_OVERRIDABLE")
        with self.assertRaises(M3.Refused) as caught:
            M3.package_input(pr3_inputs(self.X, self.host), confirmation(digest), environment="test")
        self.assertEqual(caught.exception.reason, "TRUST_REQUIRED")
        self.assertEqual(dict(M3.DEV_ACCEPTED_CANDIDATES), {})

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
                            ("releaseManifestSha256", "slice-15b2b-b1b3e-e19-completion-record.md")):
            with self.subTest(key=key):
                self.assertIn(M3.DEV_EXPECTED[key], (records / record).read_text(encoding="utf-8"))


# ---------------------------------------------------------- readiness inputs ---

DR5_PASS = b"DENIED: synthetic row\nPR1_AUTHORITY_BOUNDARY maturity=P1A-9\nAUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3\n"
BROKER_PASS = b'{"BROKER_PRESERVATION":"PASS","failures":[],"operation":"READ_ONLY_BROKER_PRESERVATION"}\n'
BROKER_FAIL = (b'{"BROKER_PRESERVATION":"FAIL","failures":["BASELINE_CANDIDATE_CHANGED"],'
               b'"operation":"READ_ONLY_BROKER_PRESERVATION"}\n')


def transcripts():
    """Synthetic producer-shaped transcripts (name -> (bytes, exit)) for the four mapped proofs."""
    custody = RI.expected_custody_denial_pass("P1B-12")
    return {"SIGNER_DENIAL": (custody, 0), "BROKER_DENIAL": (custody, 0), "DEPLOYER_DENIAL": (DR5_PASS, 0),
            "BROKER_PRESERVATION": (BROKER_PASS, 0)}


def proof_item(raw, exit_code, at=T1):
    return {"transcript": b64u(raw), "exitCode": exit_code, "observedAt": at, "evidenceSha256": H("evidence")}


def build_inputs(X, host, manifest_sha, *, proofs=None, pr2=None, pr3=None, activation=None, **overrides):
    current = X.current_document(host)
    value = {
        "buildType": RI.BUILD_TYPE, "schemaVersion": 1, "environment": X.ENV,
        "window": {"notBefore": T0, "notAfter": T2},
        "release": {"releaseSha": X.RELEASE_SHA, "attestedManifestSha256": manifest_sha,
                    "reviewedRuntimeDigests": None},
        "current": {**current, "observedAt": T1, "evidenceSha256": H("current")},
        "kActPublication": {"bytes": b64u(X.PB.publication_bytes(X.P0))},
        "kWitPublication": {"bytes": b64u(SC.canonical_publication_bytes(X.witness_publication()))},
        "proofs": proofs if proofs is not None else {name: proof_item(*t) for name, t in transcripts().items()},
        "activation": activation or {"stdout": REAL_HOST_ACTIVATION + "\n", "exitCode": 1, "b1cUnchanged": True,
                                     "observedAt": T1, "evidenceSha256": H("activation")},
        "pr2": pr2, "pr3": pr3,
    }
    value.update(overrides)
    return value


def fixture_pins(X, host, manifest_sha):
    return {"releaseSha": X.RELEASE_SHA, "attestedManifestSha256": manifest_sha,
            "pinnedCurrentSha256": X.PB.BLOB[X.P0],
            "kActPublicationFileSha256": hashlib.sha256(X.PB.publication_bytes(X.P0)).hexdigest(),
            "kActPublicKeySha256": X.PB.health(X.P0)["publicKeySha256"],
            "kWitPublicKeySha256": hashlib.sha256(X.F.raw_public("witness")).hexdigest()}


def accepted_transcripts(names=None):
    chosen = transcripts() if names is None else {n: t for n, t in transcripts().items() if n in names}
    return {name: frozenset({hashlib.sha256(raw).hexdigest()}) for name, (raw, _exit) in chosen.items()}


@unittest.skipUnless(POSIX, "the synthetic PR-1 host needs POSIX ownership and modes")
class ReadinessInputTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.X, self.host, self.manifest_sha = self.stack.enter_context(synthetic_host())
        self.pins = fixture_pins(self.X, self.host, self.manifest_sha)

    def tearDown(self):
        self.stack.close()

    def trust(self, *, transcripts_=None, pr2=None, pr3=None, not_before=T0):
        return RI.ReadinessTrustV1(self.pins, not_before,
                                   accepted_transcripts() if transcripts_ is None else transcripts_, pr2, pr3)

    def build(self, trust=None, **kwargs):
        return RI.build(build_inputs(self.X, self.host, self.manifest_sha, **kwargs), environment="test",
                        trust=trust or self.trust())

    def refused(self, reason, **kwargs):
        with self.assertRaises(RI.Refused) as caught:
            self.build(**kwargs)
        self.assertEqual(caught.exception.reason, reason)

    def evaluate(self, document, mode="HOLD_RELEASE_ELIGIBILITY", health=None):
        from lilith_authority_root import verifier as V
        owner = V.parse_verifier_inputs(document)
        return V.evaluate(mode, owner, root=self.host.root, owner_uid=self.X.UID, owner_gid=self.X.GID,
                          health=health or self.X.health_p0, run=self.X.fake_systemctl())

    def roundtrip(self, raw):
        return RI.read_envelope(io.BytesIO(raw), expected_sha256=hashlib.sha256(raw).hexdigest(), environment="test")

    def pr2_pr3(self):
        document, digest = live_inventory()
        pr2 = {"inventory": document, "acceptance": acceptance(digest)}
        expected = pr3_expected(self.X, self.host, self.manifest_sha)
        candidate = M3.assemble(pr3_inputs(self.X, self.host), environment="test",
                                trust=M3.Pr3TrustV1(expected, {}))["candidateDigest"]
        pr3 = {"inputs": pr3_inputs(self.X, self.host), "confirmation": confirmation(candidate)}
        return pr2, pr3, pr2_trust(digest), M3.Pr3TrustV1(expected, {candidate: OWNER_CONFIRMATION})

    def test_build_is_deterministic_and_the_release_parser_accepts_it(self):
        first, report = self.build()
        self.assertEqual(first, self.build()[0])
        self.assertTrue(first.endswith(b"\n") and first.count(b"\n") == 1)
        document = self.roundtrip(first)
        self.assertEqual(RI.document_digest(document), report["inputsSha256"])
        self.assertEqual(document["proofs"]["DEPLOYER_DENIAL"]["detail"], PA.REQUIRED_DEPLOYER_MATURITY)
        self.assertIs(report["readinessEvaluated"], False)

    def test_the_real_verifier_is_not_ready_for_exactly_the_known_gaps(self):
        result = self.evaluate(self.roundtrip(self.build()[0]))
        failing = {name: outcome.reason for name, outcome in result.checks.items() if outcome.status != "PASS"}
        self.assertEqual(failing, {
            "E07_SIGNER_CUSTODY_DENIAL": "PROOF_MISSING:OS_DENIAL",
            "E18_OFFHOST_REPRODUCTION_INPUTS": "OFFHOST_MATERIAL_UNAVAILABLE",
            "E20_SNAPSHOT_INVENTORY": "SNAPSHOT_INVENTORY_ABSENT_PR2",
            "E21_OFFHOST_REGISTER": "OFFHOST_REGISTER_ABSENT_PR3",
            "E22_SECRET_HYGIENE": "PROOF_MISSING:SECRET_HYGIENE",
            "E23_PRESERVATION_SET": "PROOF_MISSING:PRESERVATION_SET"})
        self.assertTrue(result.readiness.ready)          # root HOLD_RELEASE_ELIGIBILITY READY != package READY

    def test_established_pr2_and_pr3_close_e18_e20_e21_and_nothing_else(self):
        pr2, pr3, t2, t3 = self.pr2_pr3()
        raw, report = self.build(trust=self.trust(pr2=t2, pr3=t3), pr2=pr2, pr3=pr3)
        result = self.evaluate(self.roundtrip(raw))
        failing = {name for name, outcome in result.checks.items() if outcome.status != "PASS"}
        self.assertEqual(failing, {"E07_SIGNER_CUSTODY_DENIAL", "E22_SECRET_HYGIENE", "E23_PRESERVATION_SET"})
        material = self.roundtrip(raw)["offHostMaterial"]
        self.assertEqual(M3.offhost_reproduction(material, result.package), [])
        # The synthetic release is not aee323e, so the corrected judge's E-19 is not an expected gap here.
        self.assertEqual(report["expectedNotReady"], ["PROOF_MISSING:OS_DENIAL", "PROOF_MISSING:PRESERVATION_SET",
                                                      "PROOF_MISSING:SECRET_HYGIENE"])
        self.assertEqual(report["knownPackageDefects"], [])

    def test_a_verified_fail_transcript_passes_through_as_fail(self):
        names = {"BROKER_DENIAL", "BROKER_PRESERVATION"}
        accepted = {**accepted_transcripts(names), "BROKER_PRESERVATION": frozenset({hashlib.sha256(
            BROKER_FAIL).hexdigest()})}
        proofs = {"BROKER_DENIAL": proof_item(*transcripts()["BROKER_DENIAL"]),
                  "BROKER_PRESERVATION": proof_item(BROKER_FAIL, 2)}
        raw, report = self.build(trust=self.trust(transcripts_=accepted), proofs=proofs)
        self.assertEqual(self.evaluate(self.roundtrip(raw)).checks["E09_BROKER_DENIAL_PRESERVATION"].reason,
                         "PROOF_NOT_PASS:BROKER_PRESERVATION")
        self.assertIn("PROOF_NOT_PASS:BROKER_PRESERVATION", report["expectedNotReady"])

    def test_activation_is_the_complete_host_line_passed_verbatim(self):
        self.assertEqual(self.roundtrip(self.build()[0])["activation"]["line"], REAL_HOST_ACTIVATION)
        for stdout, exit_code in (("ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT\n", 1),
                                  (REAL_HOST_ACTIVATION + "\n", 0),
                                  (REAL_HOST_ACTIVATION, 1), ("ACTIVATION=ACCEPTED {}\n", 1)):
            activation = {"stdout": stdout, "exitCode": exit_code, "b1cUnchanged": True, "observedAt": T1,
                          "evidenceSha256": H("a")}
            with self.subTest(stdout=stdout, exit_code=exit_code), self.assertRaises(RI.Refused):
                self.build(activation=activation)

    def test_e19_judge_is_corrected_in_source_and_the_defect_scoped_to_aee323e(self):
        """Record §8 defect, corrected in source by the E-19 release-maintenance slice. aee323e carried the 3-field
        judge; E-19 U5 retired it, and the pinned DEV release (ba943e1) carries the corrected judge."""
        self.assertEqual(PA.ACTIVATION_DARK_LINE, RI.HOST_ACTIVATION_DARK_LINE)
        self.assertEqual(RI.E19_DEFECTIVE_RELEASES, frozenset({"aee323e94412accbe321bc84eae78c5b8cf95afc"}))
        self.assertNotIn(RI.DEV_PINS["releaseSha"], RI.E19_DEFECTIVE_RELEASES)
        dev = (ROOT / "scripts/dev_deployer/lilith_activation_verify.py").read_text(encoding="utf-8")
        self.assertIn('print(f"ACTIVATION=NOT_ACCEPTED reason={exc.reason} advisoryConfigEnabled={advisory}")', dev)

    def test_publications_and_current_must_be_the_pinned_ones(self):
        self.refused("KACT_PUBLICATION_NOT_RECORD",
                     kActPublication={"bytes": b64u(self.X.PB.publication_bytes(self.X.PB.S2))})
        self.refused("KWIT_FINGERPRINT_MISMATCH", kWitPublication={"bytes": b64u(SC.canonical_publication_bytes(
            self.X.witness_publication("other")))})
        self.refused("RELEASE_NOT_RECORD", release={"releaseSha": "0" * 40, "attestedManifestSha256": self.manifest_sha,
                                                    "reviewedRuntimeDigests": None})
        current = {**self.X.current_document(self.host), "sha256": H("other"), "observedAt": T1,
                   "evidenceSha256": H("c")}
        self.refused("CURRENT_SHA256_NOT_PINNED", current=current)

    def test_envelope_reader_is_exact(self):
        raw, report = self.build()
        digest = hashlib.sha256(raw).hexdigest()
        sha = lambda body: hashlib.sha256(body).hexdigest()  # noqa: E731
        cases = {
            "ENVELOPE_DIGEST_MISMATCH": (raw, H("other")),
            "ENVELOPE_NOT_CANONICAL": (json.dumps(json.loads(raw), indent=1).encode() + b"\n", None),
            "ENVELOPE_SIZE": (b"", None),
        }
        for label, body in (("no LF", raw[:-1]), ("CRLF", raw[:-1] + b"\r\n"), ("two LF", raw + b"\n")):
            cases[f"ENVELOPE_NOT_CANONICAL ({label})"] = (body, None)
        cases["ENVELOPE_MALFORMED"] = (b"\xef\xbb\xbf" + raw, None)
        cases["ENVELOPE_DUPLICATE_KEY"] = (raw.replace(b'{"envelopeType"', b'{"environment":"test","envelopeType"',
                                                       1), None)
        cases["ENVELOPE_SIZE (oversize)"] = (raw + b" " * RI.MAX_ENVELOPE, None)
        for label, (body, expected) in cases.items():
            with self.subTest(label=label), self.assertRaises(RI.Refused) as caught:
                RI.read_envelope(io.BytesIO(body), expected_sha256=expected or sha(body), environment="test")
            self.assertEqual(caught.exception.reason, label.split(" ")[0])
        envelope = json.loads(raw)
        envelope["inputs"]["releaseSha"] = "1" * 40
        tampered = RI.envelope_bytes(envelope)
        with self.assertRaises(RI.Refused) as caught:
            RI.read_envelope(tampered, expected_sha256=sha(tampered), environment="test")
        self.assertEqual(caught.exception.reason, "INPUTS_DIGEST_MISMATCH")
        with self.assertRaises(RI.Refused) as caught:
            RI.read_envelope(raw, expected_sha256=digest, environment="dev")
        self.assertEqual(caught.exception.reason, "ENVELOPE_ENVIRONMENT_MISMATCH")
        self.assertEqual(report["envelopeSha256"], digest)

    def test_stopped_signer_synthetic_observation_is_not_an_entry_gate(self):
        """Recorded observation only (record §9): fixture proofs for all seven names and the 3-field activation line,
        signer HEALTH unavailable. Real stopped-signer inputs differ (E-07, E-09, E-19, E-22, E-23); no gate uses this."""
        import pr1s_fixtures as XX

        def stopped():
            raise OSError("signer stopped: no HEALTH")
        document = XX.verifier_inputs(self.host, manifest_sha256=self.manifest_sha, with_pr2=True, with_pr3=True)
        result = self.evaluate(document, health=stopped)
        failing = {name: outcome.reason for name, outcome in result.checks.items() if outcome.status != "PASS"}
        self.assertEqual(failing, {"E03_HEALTH_FINGERPRINT": "LOADED_KEY_BINDING:BINDING_INPUT_MISSING",
                                   "E06_UNIT_CREDENTIAL_MAPPING": "LOADED_KEY_BINDING:BINDING_INPUT_MISSING",
                                   "E17_READINESS": "READINESS_NOT_READY"})
        self.assertEqual(list(result.readiness.reasons), ["LOADED_KEY_BINDING:BINDING_INPUT_MISSING"])

    # ------------------------------------------------ forgery regressions ---

    def test_blocker1_package_objects_are_not_build_inputs(self):
        forged_pr2 = {"status": "ACCEPTED", "recordSha256": H("never inventoried"),   # E-20 PASS at 64df007
                      "artefactClasses": ["NO_SNAPSHOTS"], "namedDebts": []}
        forged_pr3 = self.X.offhost_material(self.host, manifest_sha256=self.manifest_sha)
        for field, value in (("snapshotInventory", forged_pr2), ("offHostMaterial", forged_pr3)):
            inputs = build_inputs(self.X, self.host, self.manifest_sha)
            inputs[field] = value
            with self.subTest(field=field), self.assertRaises(RI.Refused) as caught:
                RI.build(inputs, environment="test", trust=self.trust())
            self.assertEqual((caught.exception.reason, caught.exception.detail), ("INPUT_MALFORMED", "build"))
        for field, value in (("pr2", forged_pr2), ("pr3", forged_pr3)):
            with self.subTest(field=field), self.assertRaises(RI.Refused) as caught:
                self.build(**{field: value})
            self.assertEqual(caught.exception.reason, "INPUT_MALFORMED")

    def test_blocker1_unestablished_acceptance_and_confirmation_are_refused(self):
        pr2, pr3, t2, t3 = self.pr2_pr3()
        unpinned2 = pr2_trust()
        unpinned3 = M3.Pr3TrustV1(t3.expected, {})
        self.refused("PR2_OWNER_ACCEPTANCE_NOT_ESTABLISHED", trust=self.trust(pr2=unpinned2), pr2=pr2)
        self.refused("PR3_OWNER_CONFIRMATION_NOT_ESTABLISHED", trust=self.trust(pr3=unpinned3), pr3=pr3)
        self.refused("PR2_TRUST_REQUIRED", pr2=pr2)
        self.refused("PR3_TRUST_REQUIRED", pr3=pr3)

    def test_blocker2_self_asserted_proofs_are_refused(self):
        legacy = {"SIGNER_DENIAL": {"result": "PASS", "transcriptSha256": H("no transcript exists"), "detail": None,
                                    "producer": RI.CUSTODY_DENIAL, "observedAt": T1,
                                    "evidenceSha256": H("e")}}           # admitted at 64df007
        self.refused("INPUT_MALFORMED", proofs=legacy)
        handwritten = b"AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-12\n"
        self.refused("TRANSCRIPT_CONTRACT", proofs={"SIGNER_DENIAL": proof_item(handwritten, 0)},
                     trust=self.trust(transcripts_={"SIGNER_DENIAL": frozenset({hashlib.sha256(
                         handwritten).hexdigest()})}))
        exact = RI.expected_custody_denial_pass("P1B-12")
        self.refused("TRANSCRIPT_CONTRACT", proofs={"SIGNER_DENIAL": proof_item(exact, 1)})
        self.refused("TRANSCRIPT_CONTRACT", proofs={"SIGNER_DENIAL": proof_item(exact.replace(b"DENIED", b"FAIL: x",
                                                                                              1), 0)})
        self.refused("PROOF_PROVENANCE_NOT_ESTABLISHED", proofs={"SIGNER_DENIAL": proof_item(exact, 0)},
                     trust=self.trust(transcripts_={}))
        self.refused("TRANSCRIPT_CONTRACT", proofs={"DEPLOYER_DENIAL": proof_item(DR5_PASS, 1)})
        self.refused("TRANSCRIPT_CONTRACT", proofs={"BROKER_PRESERVATION": proof_item(BROKER_PASS, 2)})
        self.refused("TRANSCRIPT_CONTRACT",
                     proofs={"BROKER_PRESERVATION": proof_item(BROKER_PASS.replace(b'":"', b'": "', 1), 0)})
        for name in ("OS_DENIAL", "SECRET_HYGIENE", "PRESERVATION_SET"):
            with self.subTest(name=name):
                self.refused("TRANSCRIPT_CONTRACT", proofs={name: proof_item(b"PASS\n", 0)})

    def test_blocker2_custody_transcript_is_rebuilt_from_the_pinned_script(self):
        exact = RI.expected_custody_denial_pass("P1B-12").decode("ascii").splitlines()
        self.assertEqual(exact[-1], "AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-12")
        self.assertEqual(sum(line.startswith("DENIED: signer-namespace ") for line in exact), 9)
        self.assertFalse(any(line.startswith(("DEFERRED_UNTIL_PHASE", "FAIL")) for line in exact))
        with mock.patch.dict(RI.PRODUCER_SCRIPT_SHA256, {"scripts/authority_custody_denial_proof.py": H("other")}):
            with self.assertRaises(RI.Refused) as caught:
                RI.expected_custody_denial_pass("P1B-12")
        self.assertEqual(caught.exception.reason, "PRODUCER_SCRIPT_NOT_PINNED")
        self.assertEqual(dict(RI.DEV_ACCEPTED_PROOF_TRANSCRIPTS), OD_M12_6_TRANSCRIPTS)

    def test_blocker5_caller_window_cannot_reach_before_the_cutoff(self):
        wide = {"notBefore": "2016-01-01T00:00:00Z", "notAfter": "2036-01-01T00:00:00Z"}   # accepted at 64df007
        old = {**{n: proof_item(*t) for n, t in transcripts().items()},
               "SIGNER_DENIAL": proof_item(*transcripts()["SIGNER_DENIAL"], at="2017-01-01T00:00:00Z")}
        self.refused("WINDOW_BEFORE_FRESHNESS_CUTOFF", window=wide, proofs=old)
        self.refused("INPUT_STALE", proofs=old)
        document, digest = live_inventory(window=("2016-01-01T00:00:00Z", "2016-01-02T00:00:00Z"))
        stale_pr2 = {"inventory": document, "acceptance": acceptance(digest)}
        self.refused("PR2_INVENTORY_STALE", trust=self.trust(pr2=pr2_trust(digest)), pr2=stale_pr2)

    def test_dev_builds_are_refused_until_the_owner_pins_exist(self):
        inputs = build_inputs(self.X, self.host, self.manifest_sha, environment="dev")
        with self.assertRaises(RI.Refused) as caught:
            RI.build(inputs, environment="dev")
        self.assertEqual(caught.exception.reason, "WINDOW_BEFORE_FRESHNESS_CUTOFF")   # OD-M12-3 accepted
        with self.assertRaises(RI.Refused) as caught:
            RI.build(inputs, environment="dev", trust=self.trust())
        self.assertEqual(caught.exception.reason, "DEV_TRUST_NOT_OVERRIDABLE")
        with self.assertRaises(RI.Refused) as caught:
            RI.build(build_inputs(self.X, self.host, self.manifest_sha), environment="test")
        self.assertEqual(caught.exception.reason, "TRUST_REQUIRED")


# ------------------------------------------------- OD-M12-3: the accepted DEV freshness cutoff ---
BEFORE_CUTOFF = "2026-10-14T18:26:59Z"
AFTER_CUTOFF, LATER = "2026-10-14T19:00:00Z", "2026-10-14T20:00:00Z"


def shifted_inputs(X, host, manifest_sha, *, not_before, at, environment=None):
    """`build_inputs` with every observation at `at` inside the window [`not_before`, LATER]."""
    value = build_inputs(X, host, manifest_sha, proofs={n: proof_item(*t, at=at) for n, t in transcripts().items()})
    value["window"] = {"notBefore": not_before, "notAfter": LATER}
    value["current"] = {**value["current"], "observedAt": at}
    value["activation"] = {**value["activation"], "observedAt": at}
    if environment is not None:
        value["environment"] = environment
    return value


class OdM12_3CutoffTests(unittest.TestCase):
    def test_one_cutoff_shared_by_the_dev_trusts_and_never_redeclared(self):
        self.assertEqual(I2.DEV_FRESHNESS_NOT_BEFORE, OD_M12_3_CUTOFF)
        self.assertEqual(I2.dev_trust().not_before, OD_M12_3_CUTOFF)
        self.assertEqual(RI.trust_for("dev", None).not_before, OD_M12_3_CUTOFF)
        for name in ("mb12_readiness_inputs.py", "mb12_pr3_material.py"):
            self.assertNotIn(OD_M12_3_CUTOFF, (TOOLS / name).read_text(encoding="utf-8"), name)

    def test_pr2_freshness_boundary(self):
        def report(start):
            document = inventory(window=(start, LATER))
            return I2.classify(document, environment="test", expected_keys=KEYS, not_before=OD_M12_3_CUTOFF)
        with self.assertRaises(I2.Refused) as caught:
            report(BEFORE_CUTOFF)
        self.assertEqual(caught.exception.reason, "INVENTORY_STALE")
        for start in (OD_M12_3_CUTOFF, AFTER_CUTOFF):                    # at or after: evaluated, not refused as stale
            self.assertEqual(report(start)["classification"], "PASS", start)

    def test_dev_pr2_is_never_accepted_without_a_pinned_owner_acceptance_or_from_a_fixture(self):
        document, _ = live_inventory(environment="dev", window=(AFTER_CUTOFF, LATER))
        for key in document["keys"]:                                     # the pinned DEV public identities
            if key["role"] in I2.DEV_KEY_IDENTITIES:
                key["publicKeySha256"] = I2.DEV_KEY_IDENTITIES[key["role"]]
        digest = I2.inventory_digest(document)
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest, environment="dev", at=LATER), environment="dev")
        self.assertEqual(caught.exception.reason, "OWNER_ACCEPTANCE_NOT_ESTABLISHED")    # fresh, but not pinned
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, None, environment="dev")
        self.assertEqual(caught.exception.reason, "OWNER_ACCEPTANCE_ABSENT")
        fixture = inventory(environment="dev", window=(AFTER_CUTOFF, LATER), carried=("C-4",))
        fixture["keys"] = [dict(key) for key in document["keys"]]
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(fixture, acceptance(I2.inventory_digest(fixture), environment="dev", at=LATER),
                             environment="dev")
        self.assertEqual(caught.exception.reason, "SYNTHETIC_FIXTURE_NOT_PACKAGE_INPUT")

    def test_a_caller_cannot_override_the_dev_trust_or_its_cutoff(self):
        document, digest = live_inventory(environment="dev", window=(BEFORE_CUTOFF, LATER))
        permissive = pr2_trust(digest, not_before="2000-01-01T00:00:00Z")
        with self.assertRaises(I2.Refused) as caught:
            I2.package_input(document, acceptance(digest, environment="dev", at=LATER), environment="dev",
                             trust=permissive)
        self.assertEqual(caught.exception.reason, "DEV_TRUST_NOT_OVERRIDABLE")
        with self.assertRaises(RI.Refused) as caught:
            RI.trust_for("dev", RI.ReadinessTrustV1({}, "2000-01-01T00:00:00Z", {}, None, None))
        self.assertEqual(caught.exception.reason, "DEV_TRUST_NOT_OVERRIDABLE")


@unittest.skipUnless(POSIX, "the synthetic PR-1 host needs POSIX ownership and modes")
class OdM12_3ReadinessTests(ReadinessInputTests):
    def build_at(self, trust=None, *, not_before, at, environment=None):
        inputs = shifted_inputs(self.X, self.host, self.manifest_sha, not_before=not_before, at=at,
                                environment=environment)
        return RI.build(inputs, environment=environment or inputs["environment"], trust=trust)

    def test_readiness_window_and_observations_against_the_cutoff(self):
        trust = self.trust(not_before=OD_M12_3_CUTOFF)
        with self.assertRaises(RI.Refused) as caught:
            self.build_at(trust, not_before=BEFORE_CUTOFF, at=AFTER_CUTOFF)
        self.assertEqual(caught.exception.reason, "WINDOW_BEFORE_FRESHNESS_CUTOFF")
        with self.assertRaises(RI.Refused) as caught:
            self.build_at(trust, not_before=OD_M12_3_CUTOFF, at=BEFORE_CUTOFF)
        self.assertEqual(caught.exception.reason, "INPUT_STALE")
        for lower in (OD_M12_3_CUTOFF, AFTER_CUTOFF):                     # at or after: admitted to evaluation
            envelope, _report = self.build_at(trust, not_before=lower, at=AFTER_CUTOFF)
            document = RI.read_envelope(envelope, expected_sha256=hashlib.sha256(envelope).hexdigest(),
                                        environment=self.X.ENV)
            self.assertIsInstance(document, dict, lower)

    def test_missing_proof_provenance_never_becomes_accepted(self):
        trust = self.trust(transcripts_={}, not_before=OD_M12_3_CUTOFF)
        with self.assertRaises(RI.Refused) as caught:
            self.build_at(trust, not_before=OD_M12_3_CUTOFF, at=AFTER_CUTOFF)
        self.assertEqual(caught.exception.reason, "PROOF_PROVENANCE_NOT_ESTABLISHED")

    def test_synthetic_evidence_is_never_authentic_dev_evidence(self):
        # Fresh, well-formed synthetic inputs under the pinned DEV trust: refused on a DEV record pin, never by
        # freshness, never an envelope.
        with self.assertRaises(RI.Refused) as caught:
            self.build_at(None, not_before=OD_M12_3_CUTOFF, at=AFTER_CUTOFF, environment="dev")
        self.assertIn(caught.exception.reason, ("RELEASE_NOT_RECORD", "MANIFEST_NOT_RECORD", "CURRENT_SHA256_NOT_PINNED",
                                                "KACT_PUBLICATION_NOT_RECORD", "PROOF_PROVENANCE_NOT_ESTABLISHED"))


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
        pinned = release_file_set.SHARED_HASHES
        path = "services/owner-memory-control/lilith_owner_memory/pr1_acceptance.py"
        self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), pinned[path])
        # e0928854 (aee323e) -> the E-19 correction (test_b1b3e_e19_release_maintenance pins the exact edits).
        self.assertEqual(pinned[path], "0d2e6ccabf916425a1dfa7dc587bfcb3d7a232eb6c52c5cd938d573199715cff")
        for name in self.SOURCES:
            self.assertFalse(any(name in key for key in pinned), name)

    def test_dev_trust_pins_are_empty_until_owner_records_exist(self):
        self.assertEqual(I2.DEV_FRESHNESS_NOT_BEFORE, OD_M12_3_CUTOFF)          # OD-M12-3, owner-accepted 2026-10-15
        self.assertEqual(dict(I2.DEV_ACCEPTED_INVENTORIES), E20_ACCEPTED_INVENTORIES)
        self.assertEqual(dict(M3.DEV_ACCEPTED_CANDIDATES), {})
        self.assertEqual(dict(RI.DEV_ACCEPTED_PROOF_TRANSCRIPTS), OD_M12_6_TRANSCRIPTS)

    def test_proof_producers_are_the_recorded_mapping_and_pinned_scripts(self):
        self.assertEqual(tuple(RI.PROPOSED_PROOF_PRODUCERS), PA.REQUIRED_PROOFS)
        self.assertEqual({n for n, p in RI.PROPOSED_PROOF_PRODUCERS.items() if p is None}, set())   # PR-B2
        for relative, digest in RI.PRODUCER_SCRIPT_SHA256.items():
            with self.subTest(relative=relative):
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), digest)
        self.assertEqual(set(RI.CONTRACTS), {p for p in RI.PROPOSED_PROOF_PRODUCERS.values() if p})


if __name__ == "__main__":
    unittest.main()
