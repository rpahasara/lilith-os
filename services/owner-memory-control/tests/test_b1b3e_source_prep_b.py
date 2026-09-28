"""15B2b-B1b-3e Source Prep B tests: successor custody and compromise recovery (TEST-ONLY).

Covers SW-1, SW-2 (the owner-side contracts), and SW-9: successor identity and
burned ordinals, `SuccessorCeremonyRecordV1` anti-substitution,
`CeremonyHoldV1` (including INITIAL_CUSTODY), HOLD_RELEASE_ELIGIBILITY vs
FULL_READINESS, the compromise-epoch rule, the SW-9 order, the narrow C-4
gate, forward-only custody, predecessor destruction, and the crash matrices.

No real key, credential, witness, registry, ledger, or authority is used.
No test touches a real custody path.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control",
             ROOT / "services/owner-memory-control/tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import synthetic_authority as SA  # noqa: E402
import synthetic_b1b3e as F  # noqa: E402
import synthetic_b1b3e_prep_a as P  # noqa: E402
import synthetic_b1b3e_prep_b as B  # noqa: E402
from lilith_authority_signer import synthetic_witness_store as WS  # noqa: E402
from lilith_authority_signer import synthetic_witness_v2 as W2  # noqa: E402
from lilith_owner_memory import authority_contracts as A  # noqa: E402
from lilith_owner_memory import authority_verifier as AV  # noqa: E402
from lilith_owner_memory import rotation_contracts as RC  # noqa: E402
from lilith_owner_memory import successor_custody as SC  # noqa: E402
from lilith_owner_memory import successor_readiness as SR  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402

POSIX = os.name == "posix"
ELIGIBILITY, FULL = SR.HOLD_RELEASE_ELIGIBILITY, SR.FULL_READINESS


def check(result, name):
    return result.checks[name]


def reasons(result) -> dict[str, str | None]:
    return {name: outcome.reason for name, outcome in result.checks.items() if outcome.status != WR.PASS}


def ledger_only(scenario: B.PrepBScenario, challenge: str = "c9") -> None:
    """Append one ledger-only witness entry (no head change)."""
    scenario.ledger = scenario.ledger.prepare(challenge, scenario.ledger.ledger_epoch,
                                              ready=F.seeded_ready(scenario.ledger))
    scenario.record_ledger()


def rotated_released(scenario: B.PrepBScenario | None = None) -> dict:
    scenario = scenario or B.rotated()
    return B.hold(state=SC.RELEASED, witness=scenario.digests["successorHead"])


def kcr_hold(scenario: B.PrepBScenario, *, state: str = SC.HELD, successor: str | None = B.S2,
             witness: str | None = None) -> dict:
    digest = witness or (scenario.digests["successorHead"] if state == SC.RELEASED else scenario.digests["holdEngaged"])
    return B.hold(kind=SC.KEY_COMPROMISE_RECOVERY, state=state, successor=successor, witness=digest)


# ------------------------------------------------------ successor identity ---

class SuccessorIdentityTests(unittest.TestCase):
    def test_closed_derivation_and_bounds(self):
        identity = SC.successor_identity(2)
        self.assertEqual((identity.key_id, identity.ceremony_id),
                         ("test-only.dev-synthetic.actor.b1b3e.2", "dev-synthetic.owner-actor.successor.2"))
        self.assertEqual(SC.successor_identity(9999).key_id, "test-only.dev-synthetic.actor.b1b3e.9999")
        self.assertEqual(SC.successor_identity(2), SC.successor_identity(2))  # deterministic
        self.assertNotEqual(SC.successor_identity(2).key_id, SC.successor_identity(3).key_id)
        self.assertNotEqual(SC.successor_identity(2).ceremony_id, SC.successor_identity(3).ceremony_id)
        for bad in (0, 1, 10000, -2, 2.0, "2", True, None):
            with self.assertRaises(Exception, msg=repr(bad)):
                SC.successor_identity(bad)
        self.assertNotEqual(SC.successor_identity(2).key_id, SC.INITIAL_KEY_ID)

    def test_inverse_is_strict(self):
        self.assertEqual(SC.successor_ordinal_of_key_id(B.S2), 2)
        self.assertEqual(SC.successor_ordinal_of_ceremony_id(B.C3), 3)
        for bad in (SC.INITIAL_KEY_ID, SC.SUCCESSOR_KEY_ID_PREFIX + "02", SC.SUCCESSOR_KEY_ID_PREFIX + "1",
                    SC.SUCCESSOR_KEY_ID_PREFIX + "10000", SC.SUCCESSOR_KEY_ID_PREFIX + "٢", None, 2):
            self.assertIsNone(SC.successor_ordinal_of_key_id(bad), bad)

    def test_initial_ceremony_id_is_deterministic_from_fixed_context(self):
        self.assertEqual(SC.initial_ceremony_id("dev", SC.INITIAL_KEY_ID),
                         "dev.initial-custody.test-only.dev-synthetic.actor.b1b3d.1")
        self.assertEqual(SC.initial_ceremony_id("dev", SC.INITIAL_KEY_ID),
                         SC.initial_ceremony_id("dev", SC.INITIAL_KEY_ID))
        self.assertNotEqual(SC.initial_ceremony_id("dev", SC.INITIAL_KEY_ID), B.INITIAL_CEREMONY)
        with self.assertRaises(Exception):
            SC.initial_ceremony_id("staging", SC.INITIAL_KEY_ID)

    def test_fixed_names_are_five_distinct_identifiers(self):
        profile = SC.DEV_SYNTHETIC_CUSTODY_PROFILE
        self.assertEqual(profile.credential_name, "owner-actor-signing-key")
        self.assertEqual(profile.current_path, "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred")
        self.assertEqual(profile.prepared_path,
                         "/etc/lilith-authority-custody/prepared/lilith-authority-dev.owner-actor.cred")
        self.assertEqual(profile.retired_path,
                         "/etc/lilith-authority-custody/retired/lilith-authority-dev.owner-actor.cred")
        self.assertEqual(profile.current_path, WR.DEV_SYNTHETIC_SLOT_CONTRACT.current_slot_path)
        self.assertEqual(profile.credential_name, WR.DEV_SYNTHETIC_SLOT_CONTRACT.credential_name)
        identifiers = {profile.credential_name, B.S2, B.C2, SC.PREPARED, SC.PREPARED_PATH}
        self.assertEqual(len(identifiers), 5)
        self.assertNotIn("2", profile.credential_name)  # the ordinal never enters the runtime name

    def test_profile_is_dev_synthetic_only(self):
        self.assertTrue(SC.is_dev_synthetic(SC.DEV_SYNTHETIC_CUSTODY_PROFILE))
        self.assertTrue(SC.is_dev_synthetic(B.PROFILE))  # the TEST-only stand-in environment
        for bad in (dataclasses.replace(SC.DEV_SYNTHETIC_CUSTODY_PROFILE, environment="prod"),
                    dataclasses.replace(SC.DEV_SYNTHETIC_CUSTODY_PROFILE, profile="PROD"),
                    dataclasses.replace(SC.DEV_SYNTHETIC_CUSTODY_PROFILE, prepared_path="/tmp/x"),
                    dataclasses.replace(SC.DEV_SYNTHETIC_CUSTODY_PROFILE, signing_domain=A.PRIVACY),
                    dataclasses.replace(SC.DEV_SYNTHETIC_CUSTODY_PROFILE, credential_name="owner-actor-signing-key-2"),
                    None):
            self.assertFalse(SC.is_dev_synthetic(bad), bad)


# ------------------------------------------------- ceremony record (RR-27) ---

class CeremonyRecordTests(unittest.TestCase):
    def verify(self, record=None, pub=None, release=B.RELEASE_SHA, prepared=None, profile=B.PROFILE):
        return SC.verify_successor_ceremony_record(
            record=B.ceremony_record() if record is None else record,
            publication_bytes=B.publication_bytes(B.S2) if pub is None else pub,
            reviewed_release_sha=release, observed_prepared_blob_sha256=prepared, profile=profile)

    def test_record_binds_publication_blob_and_release(self):
        record = B.ceremony_record()
        self.assertEqual(set(record), SC.CEREMONY_RECORD_FIELDS)
        self.assertEqual(record["createdForRole"], "PREPARED")
        self.assertEqual(record["publicationDigest"], hashlib.sha256(B.publication_bytes(B.S2)).hexdigest())
        self.assertEqual(record["credentialBlobSha256"], B.BLOB[B.S2])
        self.assertEqual((record["ceremonyId"], record["successorOrdinal"], record["keyId"]), (B.C2, 2, B.S2))
        result = self.verify(prepared=B.BLOB[B.S2])
        self.assertTrue(result.verified, result.reason)
        self.assertIs(result.facts["authorityGranted"], False)
        self.assertIs(result.facts["makesKeyCurrent"], False)
        self.assertIs(SC.SuccessorCeremonyRecordV1.authority_granted, False)
        self.assertNotIn("environment", record)  # verified from the bound publication instead

    def test_anti_substitution_matrix(self):
        s3_record = B.ceremony_record(B.S3)
        stale = B.ceremony_record(blob=B.OTHER_BLOB)
        cases = {
            "old publication + new blob": (dict(prepared=B.OTHER_BLOB), "PREPARED_BLOB_MISMATCH"),
            "new publication + old blob": (dict(pub=B.publication_bytes(B.S2, blob=B.OTHER_BLOB)),
                                           "PUBLICATION_DIGEST_MISMATCH"),
            "right keyId, wrong ceremony record": (dict(record={**B.ceremony_record(), "ceremonyId": B.C3}),
                                                   "CEREMONY_ID_MISMATCH"),
            "right ceremonyId, wrong ordinal": (dict(record={**B.ceremony_record(), "successorOrdinal": 3}),
                                                "CEREMONY_ID_MISMATCH"),
            "right keyId, record of another ordinal": (dict(record={**s3_record, "keyId": B.S2}),
                                                       "KEY_ID_MISMATCH"),
            "right blob/publication, wrong release": (dict(release=B.OTHER_RELEASE_SHA), "REVIEWED_RELEASE_MISMATCH"),
            "right release, wrong publication digest": (dict(record={**B.ceremony_record(),
                                                                      "publicationDigest": "0" * 64}),
                                                        "PUBLICATION_DIGEST_MISMATCH"),
            "prepared successor from another environment": (
                dict(record=None, pub=B.publication_bytes(B.S2, environment="dev")), "PUBLICATION_DIGEST_MISMATCH"),
            "stale prepared blob from an abandoned ceremony": (dict(record=stale, prepared=B.BLOB[B.S2]),
                                                                "PUBLICATION_DIGEST_MISMATCH"),
            "record blob != publication blob": (dict(record={**B.ceremony_record(), "credentialBlobSha256":
                                                             B.OTHER_BLOB}), "CREDENTIAL_BLOB_MISMATCH"),
            "publication written to CURRENT": (dict(pub=B.publication_bytes(B.S2, credential_path=SC.CURRENT_PATH)),
                                               "PUBLICATION_DIGEST_MISMATCH"),
            "release unobserved": (dict(release=None), "REVIEWED_RELEASE_UNOBSERVED"),
            "created for CURRENT": (dict(record={**B.ceremony_record(), "createdForRole": "CURRENT"}),
                                    "CREATED_FOR_ROLE_INVALID"),
            "unknown record version": (dict(record={**B.ceremony_record(), "schemaVersion": 2}),
                                       "UNSUPPORTED_SCHEMA_VERSION"),
            "non-canonical publication": (dict(pub=B.publication_bytes(B.S2).rstrip(b"\n")),
                                          "PUBLICATION_NOT_CANONICAL"),
            "missing record": (dict(record=False), "CEREMONY_RECORD_MISSING"),
        }
        for name, (overrides, expected) in cases.items():
            with self.subTest(name):
                if overrides.get("record") is False:
                    result = SC.verify_successor_ceremony_record(
                        record=None, publication_bytes=B.publication_bytes(B.S2), reviewed_release_sha=B.RELEASE_SHA,
                        profile=B.PROFILE)
                else:
                    record = overrides.pop("record", None)
                    if record is None and "pub" in overrides and "environment" in name:
                        record = SC.SuccessorCeremonyRecordV1(
                            B.C2, 2, B.S2, SC.publication_digest(B.publication_bytes(B.S2)), B.BLOB[B.S2],
                            B.RELEASE_SHA).to_dict()
                    result = self.verify(record=record, **overrides)
                self.assertFalse(result.verified)
                self.assertEqual(result.reason, expected)
        # The environment and path checks, when the digest does match:
        for publication, reason in ((B.publication_bytes(B.S2, environment="dev"), "PUBLICATION_PROFILE_MISMATCH"),
                                    (B.publication_bytes(B.S2, credential_path=SC.CURRENT_PATH),
                                     "PUBLICATION_CREDENTIAL_PATH_MISMATCH")):
            record = {**B.ceremony_record(), "publicationDigest": SC.publication_digest(publication)}
            self.assertEqual(self.verify(record=record, pub=publication).reason, reason)
        with self.assertRaises(Exception):
            B.ceremony_record(B.P0)  # the initial K-ACT has no successor record

    def test_publication_v1_is_unchanged(self):
        value = B.publication(B.S2)
        self.assertEqual(set(value), {"publicationType", "schemaVersion", "profile", "publicVerificationMaterial",
                                      "custodyEvidence"})
        self.assertEqual(value["schemaVersion"], RC.KEY_PUBLICATION_SCHEMA_VERSION)
        self.assertEqual(RC.KeyPublicationV1.from_dict(value).key_id, B.S2)
        self.assertEqual(value["custodyEvidence"]["credentialName"], "owner-actor-signing-key")


# ----------------------------------------------- burned ordinals (anti-reuse) ---

class CeremonyRegisterTests(unittest.TestCase):
    def test_ordinals_are_burned_even_if_abandoned(self):
        register = B.ceremony_register(B.ceremony_record())
        self.assertTrue(SC.check_ordinal_unburned(register, 3, profile=B.PROFILE).ok)
        self.assertEqual(SC.check_ordinal_unburned(register, 2, profile=B.PROFILE).reason, "ORDINAL_BURNED")
        reused = B.ceremony_record(blob=B.OTHER_BLOB)  # same ordinal, freshly generated blob
        self.assertEqual(SC.register_successor_ceremony(register, reused, profile=B.PROFILE).reason, "ORDINAL_BURNED")
        self.assertEqual(SC.verify_registered_ceremony(register, reused, profile=B.PROFILE).reason,
                         "ORDINAL_MATERIAL_MISMATCH")
        self.assertTrue(SC.verify_registered_ceremony(register, B.ceremony_record(), profile=B.PROFILE).ok)
        self.assertEqual(SC.verify_registered_ceremony(register, B.ceremony_record(B.S3), profile=B.PROFILE).reason,
                         "CEREMONY_NOT_REGISTERED")
        self.assertEqual(SC.verify_registered_ceremony(None, B.ceremony_record(), profile=B.PROFILE).reason,
                         "REGISTER_MISSING")

    def test_register_rejects_duplicates_and_non_derived_rows(self):
        record = B.ceremony_record()
        entry = {k: record[k] for k in ("successorOrdinal", "keyId", "ceremonyId", "publicationDigest",
                                        "credentialBlobSha256")}
        s3 = B.ceremony_record(B.S3)
        other = {k: s3[k] for k in entry}
        base = SC.empty_ceremony_register(B.ENV)
        cases = {
            "duplicate ordinal": [entry, dict(entry)],
            "keyId under another ordinal": [{**other, "keyId": B.S2}],
            "ceremonyId under another ordinal": [{**other, "ceremonyId": B.C2}],
            "same material twice": [entry, {**other, "credentialBlobSha256": entry["credentialBlobSha256"]}],
        }
        expected = {"duplicate ordinal": "REGISTER_ORDINAL_DUPLICATED",
                    "keyId under another ordinal": "REGISTER_ENTRY_NOT_DERIVED",
                    "ceremonyId under another ordinal": "REGISTER_ENTRY_NOT_DERIVED",
                    "same material twice": "REGISTER_MATERIAL_DUPLICATED"}
        for name, rows in cases.items():
            with self.subTest(name):
                result = SC.check_ordinal_unburned({**base, "ceremonies": rows}, 5, profile=B.PROFILE)
                self.assertEqual(result.reason, expected[name])
        self.assertEqual(SC.check_ordinal_unburned({**base, "environment": "prod"}, 5, profile=B.PROFILE).reason,
                         "REGISTER_ENVIRONMENT_MISMATCH")
        # A record claiming a registered keyId under another ordinal is refused.
        register = B.ceremony_register(record)
        claim = {**s3, "keyId": B.S2}
        self.assertEqual(SC.verify_registered_ceremony(register, claim, profile=B.PROFILE).reason,
                         "KEY_ID_ORDINAL_CONFLICT")
        claim = {**s3, "ceremonyId": B.C2}
        self.assertEqual(SC.verify_registered_ceremony(register, claim, profile=B.PROFILE).reason,
                         "CEREMONY_ID_ORDINAL_CONFLICT")
        self.assertEqual(SC.register_successor_ceremony(register, {**s3, "credentialBlobSha256":
                                                                    record["credentialBlobSha256"],
                                                                    "publicationDigest": record["publicationDigest"]},
                                                        profile=B.PROFILE).reason, "MATERIAL_ALREADY_REGISTERED")
        self.assertIs(SC.SuccessorCeremonyRegisterV1.authority_granted, False)


# ------------------------------------------------------ CeremonyHoldV1 ---

class CeremonyHoldContractTests(unittest.TestCase):
    D = "a" * 64

    def parse(self, value):
        return SC.parse_ceremony_hold(value, profile=B.PROFILE)

    def test_every_valid_state_and_kind_parses(self):
        for kind in (SC.ROTATION, SC.KEY_COMPROMISE_RECOVERY):
            for state in (SC.HELD, SC.RELEASED):
                hold, reason = self.parse(B.hold(kind=kind, state=state, witness=self.D))
                self.assertIsNone(reason, (kind, state))
                self.assertEqual((hold.transition_kind, hold.state), (kind, state))
                self.assertIs(hold.authority_granted, False)
        for state in (SC.HELD, SC.RELEASED):
            hold, reason = self.parse(B.initial_hold(state=state, witness=self.D))
            self.assertIsNone(reason, state)
        hold, reason = self.parse(B.hold(ceremony=B.C2 + SC.CUSTODY_DEBT_SUFFIX, witness=self.D))
        self.assertIsNone(reason)
        self.assertTrue(hold.custody_debt)
        self.assertEqual(SC.CeremonyHoldV1.from_dict(hold.to_dict(), profile=B.PROFILE), hold)
        self.assertNotIn("createdAt", hold.to_dict())

    def test_fail_closed_parsing(self):
        good = B.hold(witness=self.D)
        cases = {
            "missing": (None, "HOLD_MISSING"),
            "not a mapping": ([], "HOLD_MALFORMED"),
            "unknown version": ({**good, "schemaVersion": 2}, "HOLD_UNSUPPORTED_VERSION"),
            "unknown protocol": ({**good, "protocol": "LILITH_HOLD"}, "HOLD_UNSUPPORTED_VERSION"),
            "extra field": ({**good, "createdAt": "2026-09-27T00:00:00Z"}, "HOLD_MALFORMED"),
            "missing field": ({k: v for k, v in good.items() if k != "reason"}, "HOLD_MALFORMED"),
            "unknown state": ({**good, "state": "ABSENT"}, "HOLD_STATE_UNKNOWN"),
            "unknown kind": ({**good, "transitionKind": "ROUTINE_ROTATION"}, "HOLD_TRANSITION_KIND_UNKNOWN"),
            "unknown reason": ({**good, "reason": "BECAUSE"}, "HOLD_REASON_UNKNOWN"),
            "reason/state mismatch": ({**good, "reason": SC.OWNER_RELEASE_AFTER_ELIGIBILITY},
                                      "HOLD_REASON_STATE_MISMATCH"),
            "other environment": ({**good, "environment": "prod"}, "HOLD_ENVIRONMENT_MISMATCH"),
            "bad digest": ({**good, "observedWitnessDigest": "x"}, "HOLD_MALFORMED"),
            "null predecessor, rotation": (B.hold(predecessor=None, witness=self.D), "HOLD_PREDECESSOR_REQUIRED"),
            "null predecessor, recovery": (B.hold(kind=SC.KEY_COMPROMISE_RECOVERY, predecessor=None, witness=self.D),
                                           "HOLD_PREDECESSOR_REQUIRED"),
            "initial with predecessor": ({**B.initial_hold(witness=self.D), "expectedPredecessorKeyId": B.S2},
                                         "HOLD_INITIAL_PREDECESSOR_NOT_NULL"),
            "initial successor not K-ACT": ({**B.initial_hold(witness=self.D), "expectedSuccessorKeyId": B.S2},
                                            "HOLD_INITIAL_SUCCESSOR_MISMATCH"),
            "initial arbitrary ceremony": ({**B.initial_hold(witness=self.D), "ceremonyId": "initial.by-hand"},
                                           "HOLD_INITIAL_CEREMONY_MISMATCH"),
            "arbitrary ceremony": (B.hold(ceremony="rotation-by-hand", witness=self.D), "HOLD_CEREMONY_NOT_DERIVED"),
            "successor not derived": (B.hold(successor=B.S3, witness=self.D), "HOLD_SUCCESSOR_NOT_DERIVED"),
            "released without successor": (B.hold(state=SC.RELEASED, successor=None, witness=self.D),
                                           "HOLD_SUCCESSOR_REQUIRED"),
            "predecessor is successor": (B.hold(predecessor=B.S2, witness=self.D), "HOLD_PREDECESSOR_IS_SUCCESSOR"),
            "initial debt": ({**B.initial_hold(witness=self.D), "ceremonyId": B.INITIAL_CEREMONY
                              + SC.CUSTODY_DEBT_SUFFIX}, "HOLD_INITIAL_CEREMONY_MISMATCH"),
        }
        for name, (value, expected) in cases.items():
            with self.subTest(name):
                hold, reason = self.parse(value)
                self.assertIsNone(hold)
                self.assertEqual(reason, expected)
        hold, reason = self.parse(B.hold(successor=None, witness=self.D))
        self.assertIsNone(reason)  # an unknown successor is valid only while HELD before preparation

    def test_lifecycle_is_missing_held_released_only(self):
        held, released = B.hold(witness=self.D), B.hold(state=SC.RELEASED, witness="b" * 64)
        rule = lambda old, new: SC.hold_transition_reason(old, new, profile=B.PROFILE)  # noqa: E731
        self.assertIsNone(rule(None, held))
        self.assertEqual(rule(None, released), "HOLD_MUST_START_HELD")  # missing -> RELEASED
        self.assertIsNone(rule(held, released))
        self.assertEqual(rule(released, held), "HOLD_ALREADY_RELEASED")  # RELEASED -> HELD
        self.assertEqual(rule(released, {**released, "observedWitnessDigest": "c" * 64}), "HOLD_ALREADY_RELEASED")
        self.assertIsNone(rule(released, released))  # an identical re-assertion is a no-op
        self.assertIsNone(rule(B.hold(successor=None, witness=self.D), held))  # fill the successor once
        self.assertEqual(rule(held, B.hold(predecessor=B.S3, witness=self.D)), "HOLD_BINDING_CHANGED")
        self.assertEqual(rule(held, {**held, "observedWitnessDigest": "c" * 64}), "HOLD_BINDING_CHANGED")
        self.assertEqual(rule(held, B.hold(kind=SC.KEY_COMPROMISE_RECOVERY, witness=self.D)), "HOLD_BINDING_CHANGED")
        self.assertEqual(rule(held, {**held, "state": "OPEN"}), "HOLD_PROPOSED_INVALID")
        self.assertEqual(rule({**held, "schemaVersion": 9}, held), "HOLD_PREVIOUS_INVALID")
        # A new ceremony (a new deterministic identity) starts again from HELD.
        debt = B.hold(ceremony=B.C2 + SC.CUSTODY_DEBT_SUFFIX, witness="b" * 64)
        self.assertIsNone(rule(released, debt))
        self.assertEqual(rule(released, {**debt, "state": SC.RELEASED,
                                         "reason": SC.OWNER_RELEASE_AFTER_ELIGIBILITY}), "HOLD_MUST_START_HELD")
        initial = B.initial_hold(witness=self.D)
        self.assertIsNone(rule(None, initial))
        self.assertEqual(rule(None, B.initial_hold(state=SC.RELEASED, witness=self.D)), "HOLD_MUST_START_HELD")


# ----------------------------------------------------- INITIAL_CUSTODY (RR-30) ---

class InitialCustodyTests(unittest.TestCase):
    def setUp(self):
        self.s = B.PrepBScenario()
        self.genesis = self.s.digests["genesis"]

    def readiness(self, mode, hold_value, **overrides):
        return self.s.readiness(mode, key_id=B.P0, phase=WR.STEADY, hold_value=hold_value, **overrides)

    def test_eligibility_with_held_genesis_hold(self):
        result = self.readiness(ELIGIBILITY, B.initial_hold(witness=self.genesis))
        self.assertTrue(result.ready, result.reasons)
        self.assertTrue(result.facts["holdReleaseEligible"])
        self.assertFalse(result.facts["successorCurrent"])
        self.assertFalse(result.facts["issuanceReady"])
        self.assertEqual(result.facts["keyTransition"]["kind"], SC.INITIAL_CUSTODY)
        self.assertIsNone(result.facts["keyTransition"]["predecessorKeyId"])
        self.assertIs(result.facts["authorityGranted"], False)

    def test_full_readiness_needs_the_matching_released_hold(self):
        held = self.readiness(FULL, B.initial_hold(witness=self.genesis))
        self.assertFalse(held.ready)
        self.assertEqual(reasons(held), {"CEREMONY_HOLD": "CEREMONY_HOLD_HELD"})
        released = self.readiness(FULL, B.initial_hold(state=SC.RELEASED, witness=self.genesis))
        self.assertTrue(released.ready, released.reasons)
        self.assertTrue(released.facts["successorCurrent"])
        # A later ledger-only entry with the genesis registry head is still bound.
        ledger_only(self.s)
        later = self.readiness(FULL, B.initial_hold(state=SC.RELEASED, witness=self.s.head.digest))
        self.assertTrue(later.ready, later.reasons)
        still_genesis = self.readiness(FULL, B.initial_hold(state=SC.RELEASED, witness=self.genesis))
        self.assertTrue(still_genesis.ready, still_genesis.reasons)

    def test_initial_hold_failures(self):
        cases = {
            "missing": (ELIGIBILITY, None, "HOLD_MISSING"),
            "malformed": (ELIGIBILITY, "MALFORMED", "HOLD_UNSUPPORTED_VERSION"),
            "HELD not at genesis": (ELIGIBILITY, None, "HOLD_WITNESS_NOT_GENESIS"),
            "RELEASED for another witness": (FULL, B.initial_hold(state=SC.RELEASED, witness="f" * 64),
                                             "HOLD_WITNESS_NOT_IN_CHAIN"),
            "RELEASED in eligibility": (ELIGIBILITY, B.initial_hold(state=SC.RELEASED, witness=self.genesis),
                                        "HOLD_NOT_HELD"),
            "rotation hold at genesis": (ELIGIBILITY, B.hold(witness=self.genesis), "HOLD_MISSING"),
        }
        ledger_only(self.s)
        cases["HELD not at genesis"] = (ELIGIBILITY, B.initial_hold(witness=self.s.head.digest),
                                        "HOLD_WITNESS_NOT_GENESIS")
        for name, (mode, value, expected) in cases.items():
            with self.subTest(name):
                if value == "MALFORMED":
                    store = SC.HoldStoreObservationV1((WR.StoreEntryV1(
                        SC.hold_record_name(B.INITIAL_CEREMONY), WR.REGULAR, WR.document_bytes({"state": "HELD"})),))
                    result = self.s.readiness(mode, key_id=B.P0, phase=WR.STEADY, store_value=store)
                else:
                    result = self.readiness(mode, value)
                self.assertFalse(result.ready)
                self.assertEqual(check(result, "CEREMONY_HOLD").reason, expected)

    def test_initial_key_and_provenance(self):
        # A released hold for another key is refused at parse time.
        other = {**B.initial_hold(state=SC.RELEASED, witness=self.genesis), "expectedSuccessorKeyId": B.S2}
        self.assertEqual(check(self.readiness(FULL, other), "CEREMONY_HOLD").reason, "HOLD_INITIAL_SUCCESSOR_MISMATCH")
        released = B.initial_hold(state=SC.RELEASED, witness=self.genesis)
        unexpected = self.readiness(FULL, released, record=B.ceremony_record())
        self.assertEqual(check(unexpected, "CEREMONY_PROVENANCE").reason, "CEREMONY_RECORD_UNEXPECTED")
        prepared_path = self.readiness(FULL, released, pub=B.publication_bytes(B.P0, credential_path=SC.PREPARED_PATH))
        self.assertEqual(check(prepared_path, "CEREMONY_PROVENANCE").reason, "PUBLICATION_CREDENTIAL_PATH_MISMATCH")
        # Existence of the older credential never grandfathers a release.
        self.assertEqual(check(self.readiness(FULL, None), "CEREMONY_HOLD").reason, "HOLD_MISSING")
        self.assertIsNone(SC.hold_transition_reason(None, B.initial_hold(witness=self.genesis), profile=B.PROFILE))
        self.assertEqual(SC.hold_transition_reason(None, released, profile=B.PROFILE), "HOLD_MUST_START_HELD")


# ------------------------------------------------------ routine rotation ---

class RotationReadinessTests(unittest.TestCase):
    def setUp(self):
        self.s = B.rotated()

    def test_eligibility_then_release_then_full(self):
        held = B.hold(witness=self.s.digests["holdEngaged"])
        eligible = self.s.readiness(ELIGIBILITY, hold_value=held)
        self.assertTrue(eligible.ready, eligible.reasons)
        full_held = self.s.readiness(FULL, hold_value=held)
        self.assertEqual(reasons(full_held), {"CEREMONY_HOLD": "CEREMONY_HOLD_HELD"})  # S_ACTIVATED != S_CURRENT
        released = rotated_released(self.s)
        self.assertIsNone(SC.hold_transition_reason(held, released, profile=B.PROFILE))
        full = self.s.readiness(FULL, hold_value=released)
        self.assertTrue(full.ready, full.reasons)
        self.assertTrue(full.facts["successorCurrent"])
        self.assertEqual(full.facts["keyTransition"], {"kind": SC.ROTATION, "predecessorKeyId": B.P0,
                                                       "successorKeyId": B.S2, "ceremonyId": B.C2})
        transition = full.facts["authorityKeyTransition"]
        self.assertIs(transition["authorityGranted"], False)
        self.assertIs(transition["authorityProof"], False)
        self.assertEqual(transition["predecessorMaterial"], "RETAINED")
        again = self.s.readiness(FULL, hold_value=released)
        self.assertEqual(again.facts["authorityKeyTransition"], transition)  # reproducible, no signature root

    def test_release_record_bound_to_other_state_fails(self):
        s = self.s
        cases = {
            "released for witness A, readiness at B": (FULL, B.hold(state=SC.RELEASED,
                                                                    witness=s.digests["holdEngaged"]),
                                                       "HOLD_WITNESS_HEAD_MISMATCH"),
            "HELD engaged after the transition": (ELIGIBILITY, B.hold(witness=s.digests["successorHead"]),
                                                  "HOLD_ENGAGED_AFTER_TRANSITION"),
            "predecessor mismatch": (FULL, {**rotated_released(s), "expectedPredecessorKeyId": B.S3},
                                     "HOLD_PREDECESSOR_MISMATCH"),
            "ceremony mismatch": (FULL, B.hold(state=SC.RELEASED, ceremony=B.C3, successor=B.S3,
                                               witness=s.digests["successorHead"]), "HOLD_MISSING"),
            "kind mismatch": (FULL, B.hold(kind=SC.KEY_COMPROMISE_RECOVERY, state=SC.RELEASED,
                                           witness=s.digests["successorHead"]), "HOLD_TRANSITION_KIND_MISMATCH"),
            "witness not in chain": (FULL, B.hold(state=SC.RELEASED, witness="e" * 64), "HOLD_WITNESS_NOT_IN_CHAIN"),
            "missing hold": (FULL, None, "HOLD_MISSING"),
        }
        for name, (mode, value, expected) in cases.items():
            with self.subTest(name):
                result = s.readiness(mode, hold_value=value)
                self.assertFalse(result.ready)
                self.assertEqual(check(result, "CEREMONY_HOLD").reason, expected)

    def test_provenance_is_required(self):
        released = rotated_released(self.s)
        cases = {
            "no ceremony record": (dict(record=None), "CEREMONY_RECORD_MISSING"),
            "unregistered ceremony": (dict(register=B.ceremony_register()), "CEREMONY_NOT_REGISTERED"),
            "no register": (dict(register=None), "REGISTER_MISSING"),
            "unreviewed release": (dict(release=B.OTHER_RELEASE_SHA), "REVIEWED_RELEASE_MISMATCH"),
            "record for another ordinal": (dict(record=B.ceremony_record(B.S3), register=B.ceremony_register(
                B.ceremony_record(B.S3))), "PUBLICATION_DIGEST_MISMATCH"),
        }
        for name, (overrides, expected) in cases.items():
            with self.subTest(name):
                result = self.s.readiness(FULL, hold_value=released, **overrides)
                self.assertEqual(check(result, "CEREMONY_PROVENANCE").reason, expected)
        mismatched = self.s.readiness(FULL, hold_value=released, pub=B.publication_bytes(B.S2, machineId="1" * 32),
                                      publication=B.publication(B.S2))
        self.assertEqual(check(mismatched, "PUBLICATION_BYTES").reason, "PUBLICATION_BYTES_MISMATCH")

    def test_retained_or_loaded_predecessor_never_ready(self):
        released = rotated_released(self.s)
        loaded_p = self.s.readiness(FULL, hold_value=released, health_value=B.health(B.P0))
        self.assertEqual(check(loaded_p, "LOADED_KEY_BINDING").reason, "HEALTH_FINGERPRINT_MISMATCH")
        p_in_current = self.s.readiness(FULL, hold_value=released, blob=B.BLOB[B.P0],
                                        inventory_value=B.inventory(current=B.BLOB[B.P0], retired=B.BLOB[B.S2]))
        self.assertEqual(check(p_in_current, "LOADED_KEY_BINDING").reason, "BLOB_HASH_MISMATCH")
        restored_p = self.s.readiness(FULL, hold_value=released, key_id=B.P0, record=None, register=None,
                                      inventory_value=B.inventory(current=B.BLOB[B.P0], retired=B.BLOB[B.S2]))
        self.assertFalse(restored_p.ready)
        self.assertIn(check(restored_p, "LOADED_KEY_BINDING").reason, {"PUBLICATION_SCOPE_MISMATCH",
                                                                       "PUBLICATION_KEY_MISMATCH"})
        # S loaded before the witness advanced: the head still names P0.
        early = B.PrepBScenario()
        s_first = early.readiness(ELIGIBILITY, hold_value=B.hold(witness=early.digests["genesis"]))
        self.assertFalse(s_first.ready)
        self.assertEqual(check(s_first, "LOADED_KEY_BINDING").reason, "PUBLICATION_SCOPE_MISMATCH")

    def test_second_rotation_uses_a_new_ceremony(self):
        s = self.s
        engaged = s.head.digest
        s.publish(s.issue_head_advance(B.rot3(), reason=SR.SUCCESSOR_ROTATION, authorization_id="rhaa.prep-b-rot-2"),
                  B.rot3())
        s.activate(B.S3)
        record = B.ceremony_record(B.S3)
        register = B.ceremony_register(B.ceremony_record(), record)
        hold = B.hold(state=SC.RELEASED, ceremony=B.C3, predecessor=B.S2, successor=B.S3, witness=s.head.digest)
        result = s.readiness(FULL, key_id=B.S3, hold_value=hold, record=record, register=register,
                             inventory_value=B.inventory(current=B.BLOB[B.S3], retired=B.BLOB[B.S2]))
        self.assertTrue(result.ready, result.reasons)
        old = s.readiness(FULL, key_id=B.S3, hold_value=rotated_released(s), record=record, register=register,
                          inventory_value=B.inventory(current=B.BLOB[B.S3], retired=B.BLOB[B.S2]))
        self.assertEqual(check(old, "CEREMONY_HOLD").reason, "HOLD_MISSING")
        both = s.readiness(FULL, key_id=B.S3, holds=(rotated_released(s), hold), record=record, register=register,
                           inventory_value=B.inventory(current=B.BLOB[B.S3], retired=B.BLOB[B.S2]))
        self.assertTrue(both.ready, both.reasons)  # earlier RELEASED ceremonies are history only
        self.assertNotEqual(engaged, s.head.digest)


# ----------------------------------------------- compromise-epoch rule (§10.3) ---

class CompromiseEpochRuleTests(unittest.TestCase):
    def mistaken(self) -> B.PrepBScenario:
        s = B.PrepBScenario().mark()
        s.publish(s.issue_head_advance(B.mistaken3(), reason=SR.SUCCESSOR_ROTATION,
                                       authorization_id="rhaa.prep-b-mistake-1"), B.mistaken3())
        s.activate(B.S2)
        return s

    def test_owner_signed_same_epoch_successor_never_ready(self):
        s = self.mistaken()
        self.assertEqual(s.head.current_recovery_epoch, B.EG)  # the witness executed it
        for mode, value in ((ELIGIBILITY, kcr_hold(s)), (FULL, kcr_hold(s, state=SC.RELEASED,
                                                                         witness=s.head.digest)),
                            (FULL, B.hold(state=SC.RELEASED, witness=s.head.digest))):
            result = s.readiness(mode, hold_value=value)
            self.assertFalse(result.ready)
            self.assertEqual(check(result, "COMPROMISE_EPOCH").reason, SR.COMPROMISE_EPOCH_ADVANCE_REQUIRED)
            self.assertEqual(check(result, "KEY_TRANSITION").reason, "TRANSITION_SAME_EPOCH_AFTER_MARKING")
        # Every Prep A check alone would pass: the rule is what refuses it.
        base = WR.evaluate_witness_readiness(s.readiness_inputs(hold_value=None).base)
        self.assertTrue(base.ready, base.reasons)

    def test_rule_clears_only_on_the_key_compromise_advance(self):
        marked = B.PrepBScenario().mark()
        self.assertEqual(SR.compromise_epoch_reason(marked.history())[0], SR.COMPROMISE_EPOCH_ADVANCE_REQUIRED)
        recovered = B.recovered()
        self.assertEqual(SR.compromise_epoch_reason(recovered.history()), (None, None))
        wrong = B.PrepBScenario().mark()
        wrong.recover(reason="OPERATOR_RECOVERY")
        reason, detail = SR.compromise_epoch_reason(wrong.history())
        self.assertEqual(reason, SR.COMPROMISE_EPOCH_ADVANCE_REQUIRED)
        self.assertIn("ADVANCE_REASON_OPERATOR_RECOVERY", detail)
        result = wrong.readiness(FULL, hold_value=kcr_hold(wrong, state=SC.RELEASED))
        self.assertFalse(result.ready)
        self.assertEqual(check(result, "COMPROMISE_EPOCH").reason, SR.COMPROMISE_EPOCH_ADVANCE_REQUIRED)
        self.assertEqual(check(result, "KEY_TRANSITION").reason, "EPOCH_ADVANCE_REASON_UNSUPPORTED")

    def test_rule_is_recomputed_not_latched(self):
        marked = B.PrepBScenario().mark()
        first = SR.compromise_epoch_reason(marked.history())
        self.assertEqual(first, SR.compromise_epoch_reason(marked.history()))
        marked.recover()
        self.assertEqual(SR.compromise_epoch_reason(marked.history()), (None, None))  # cleared by history only

    def test_non_current_marking_is_in_epoch_only(self):
        s = B.rotated()
        s.publish(s.issue_head_advance(B.mark_noncurrent3(), reason=SR.COMPROMISE_MARKING,
                                       authorization_id="rhaa.prep-b-noncurrent-1"), B.mark_noncurrent3())
        s.activate(B.S2)
        history = s.history()
        self.assertEqual(SR.compromise_epoch_reason(history), (None, None))
        self.assertTrue(history.head_registry.keys[B.P0].compromised)
        result = s.readiness(FULL, hold_value=B.hold(state=SC.RELEASED, witness=s.head.digest))
        self.assertEqual(check(result, "COMPROMISE_EPOCH").status, WR.PASS)
        self.assertEqual(check(result, "KEY_TRANSITION").status, WR.PASS)
        self.assertEqual(result.facts["governingCeremony"]["kind"], SC.REGISTRY_MAINTENANCE)
        # The earlier rotation release governs nothing at the new head.
        stale = s.readiness(FULL, hold_value=rotated_released(s))
        self.assertEqual(check(stale, "CEREMONY_HOLD").reason, "HOLD_MISSING")


# ----------------------------------------------- SW-9 recovery sequence ---

class CompromiseRecoveryTests(unittest.TestCase):
    def evaluate(self, scenario, predecessor=B.P0):
        return SR.evaluate_compromise_recovery(scenario.history(), predecessor_key_id=predecessor)

    def test_accepted_order_marking_then_epoch_advance(self):
        s = B.PrepBScenario()
        self.assertEqual(self.evaluate(s).phase, SR.RECOVERY_NOT_STARTED)
        s.mark()
        marked = self.evaluate(s)
        self.assertEqual((marked.phase, marked.reason), (SR.RECOVERY_MARKED, None))
        s.recover()
        done = self.evaluate(s)
        self.assertEqual((done.phase, done.reason), (SR.RECOVERY_EPOCH_ADVANCED, None))
        self.assertEqual(done.facts["successorKeyId"], B.S2)
        self.assertLess(done.facts["markingWitnessVersion"], done.facts["epochAdvanceWitnessVersion"])
        self.assertIs(done.facts["authorityGranted"], False)
        full = s.readiness(FULL, hold_value=kcr_hold(s, state=SC.RELEASED))
        self.assertTrue(full.ready, full.reasons)
        self.assertEqual(full.facts["keyTransition"]["kind"], SC.KEY_COMPROMISE_RECOVERY)
        self.assertEqual(full.facts["keyTransition"]["predecessorKeyId"], B.P0)
        self.assertEqual(s.history().head_registry.keys[B.P0].revocation_reason, "COMPROMISED")

    def test_all_old_key_evidence_stays_key_compromised(self):
        s = B.recovered()
        unsigned = SA.owner_evidence_unsigned(keyId=B.P0, registryVersion=1, recoveryEpoch=B.EG.to_dict(),
                                              policyVersion=B.POLICY, issuedAt="2026-09-26T12:00:00Z")
        evidence = {**unsigned, "signature": SA.b64(B.private(B.P0).sign(A.owner_evidence_signing_bytes(unsigned)))}
        for registry, epoch, version in ((B.mark2(), B.EG, 2), (B.rec3(), B.EN, 3)):
            context = A.AuthorityVerificationContextV1(
                environment=B.ENV, purpose=A.HISTORICAL_VERIFICATION, registry_root=F.root(),
                trusted_minimum_registry_version=version, expected_recovery_epoch=epoch, policy_version=B.POLICY)
            result = AV.verify_owner_evidence(context=context, registry=registry, evidence=evidence,
                                              expectation=SA.owner_expectation())
            self.assertEqual(result.reason, "KEY_COMPROMISED")
        self.assertTrue(s.history().head_registry.keys[B.P0].compromised)

    def test_out_of_order_sequences_are_refused(self):
        rotated = B.rotated()
        self.assertEqual(self.evaluate(rotated).reason, "SUCCESSOR_BEFORE_MARKING")
        rotated.publish(rotated.issue_head_advance(B.mark_noncurrent3(), reason=SR.COMPROMISE_MARKING,
                                                   authorization_id="rhaa.prep-b-noncurrent-1"), B.mark_noncurrent3())
        self.assertEqual(self.evaluate(rotated).reason, "MARKING_NOT_CURRENT_KEY")
        mistaken = CompromiseEpochRuleTests().mistaken()
        self.assertEqual(self.evaluate(mistaken).reason, "SAME_EPOCH_SUCCESSOR_AFTER_MARKING")
        wrong = B.PrepBScenario().mark()
        wrong.recover(reason="OPERATOR_RECOVERY")
        self.assertEqual(self.evaluate(wrong).reason, "WRONG_EPOCH_ADVANCE_REASON")
        combined = B.PrepBScenario()
        authorization = combined.issue_epoch_advance(B.combined2(), authorization_id="eaa.prep-b-combined-1")
        combined.adopt(authorization, B.combined2())
        combined.execute_epoch_advance(authorization, B.combined2())
        self.assertEqual(self.evaluate(combined).reason, "EPOCH_ADVANCE_WITHOUT_MARKING")
        result = combined.readiness(FULL, hold_value=kcr_hold(combined, state=SC.RELEASED, witness=combined.head.digest))
        self.assertFalse(result.ready)
        self.assertEqual(check(result, "KEY_TRANSITION").reason, "EPOCH_ADVANCE_WITHOUT_MARKING")
        self.assertEqual(self.evaluate(B.recovered(), predecessor="test-only.dev-synthetic.actor.b1b3d.0").reason,
                         "PREDECESSOR_NEVER_CURRENT")

    def test_marking_must_name_the_current_key_and_no_successor(self):
        s = B.PrepBScenario()
        wrong_key = B.registry(2, [B.key(B.P0, version=1), B.key(B.S5, version=2, created=B.T_CUT, **B.COMPROMISED)])
        # Marking a key that was never current (published directly compromised) while P0 stays current.
        s.publish(s.issue_head_advance(wrong_key, reason=SR.COMPROMISE_MARKING, authorization_id="rhaa.wrong-key"),
                  wrong_key)
        result = self.evaluate(s)
        self.assertEqual((result.phase, result.reason), (SR.RECOVERY_NOT_STARTED, "WRONG_MARKING_KEY"))
        with_successor = B.PrepBScenario()
        target = B.registry(2, [B.key(B.P0, version=1, **B.COMPROMISED), B.key(B.S2, version=2, created=B.T_CUT)])
        with_successor.publish(with_successor.issue_head_advance(target, reason=SR.COMPROMISE_MARKING,
                                                                 authorization_id="rhaa.with-successor"), target)
        self.assertEqual(self.evaluate(with_successor).reason, "MARKING_INCLUDES_SUCCESSOR")
        self.assertEqual(SR.compromise_epoch_reason(with_successor.history())[0], SR.COMPROMISE_EPOCH_ADVANCE_REQUIRED)
        admin = B.PrepBScenario()
        admin.publish(admin.issue_head_advance(B.mark2(), reason="ADMINISTRATIVE_REVOCATION",
                                               authorization_id="rhaa.admin"), B.mark2())
        self.assertEqual(self.evaluate(admin).reason, "MARKING_REASON_INVALID")
        self.assertEqual(SR.compromise_epoch_reason(admin.history())[0], SR.COMPROMISE_EPOCH_ADVANCE_REQUIRED)

    def test_stale_skipped_and_replayed_history_fails_closed(self):
        s = B.PrepBScenario().mark()
        stale = B.PrepBScenario().mark()
        stale.storage.plant(WS.STATE, WR.POINTER_NAME, stale.storage.read(WR.CHAIN_DIRECTORY, "1.json"))
        history, reason, detail = SR.verify_history(store=stale.context(), witness_store=stale.observation(),
                                                    head_registries=tuple(stale.registries))
        self.assertEqual((history, reason, detail), (None, "HISTORY_WITNESS_NOT_CONSISTENT", WR.POINTER_BEHIND_BY_ONE))
        skipped = B.PrepBScenario().mark()
        name = WR.retained_authorization_name("rhaa.prep-b-marking-1")
        skipped.storage.drop(WR.AUTHORIZATION_DIRECTORY, name)
        history, reason, detail = SR.verify_history(store=skipped.context(), witness_store=skipped.observation(),
                                                    head_registries=tuple(skipped.registries))
        self.assertEqual((reason, detail), ("HISTORY_WITNESS_NOT_CONSISTENT", WR.AUTHORIZATION_HISTORY_INVALID))
        unregistered = SR.verify_history(store=s.context(owner_register=P.owner_register({}, s.heads)),
                                         witness_store=s.observation(), head_registries=tuple(s.registries))
        self.assertEqual(unregistered[1], "HISTORY_WITNESS_NOT_CONSISTENT")
        gate = s.gate(SR.ADVANCE_EPOCH, kcr_hold(s), witness_store=stale.observation(), store=stale.context())
        self.assertEqual(gate.reason, "HISTORY_NOT_VERIFIED")
        replayed = F.epoch_authorization(s.head, B.rec3(), authorizationId="rhaa.prep-b-marking-1",
                                         reason=SR.KEY_COMPROMISE, successorRecoveryEpoch=B.EN.to_dict())
        self.assertEqual(s.gate(SR.ADVANCE_EPOCH, kcr_hold(s), epoch_authorization=replayed).reason,
                         "AUTHORIZATION_CONSUMED")


# ------------------------------------------------ narrow C-4 gate (RR-28) ---

class RecoveryGateTests(unittest.TestCase):
    DENIED = ("ISSUE", "PREPARE", "CONSUME", "RESERVE", "CONFIRM", "ABANDON", "REGISTRY_VIEW", "SIGN",
              "SIGN_OWNER_EVIDENCE", "SIGN_REGISTRY", "SIGN_PRIVACY", "RESERVE_EVIDENCE", "CONSUME_EVIDENCE",
              "ADMIN", "GENESIS", "EXPIRE", "CANCEL", "advance_epoch", "", None, 7)

    def setUp(self):
        self.s = B.PrepBScenario().mark()
        self.target = B.rec3()
        self.eaa = F.epoch_authorization(self.s.head, self.target, authorizationId="eaa.prep-b-recovery-1",
                                         reason=SR.KEY_COMPROMISE, successorRecoveryEpoch=B.EN.to_dict(),
                                         nonce=F.nonce("prep-b eaa.prep-b-recovery-1"))

    def test_only_the_allowlisted_recovery_operation_passes(self):
        permitted = self.s.gate(SR.ADVANCE_EPOCH, kcr_hold(self.s), epoch_authorization=self.eaa)
        self.assertTrue(permitted.permitted, permitted.reason)
        for flag in ("authorityGranted", "signingPermitted", "issuancePermitted", "evidenceReservationPermitted"):
            self.assertIs(permitted.facts[flag], False, flag)
        for operation in self.DENIED:
            with self.subTest(operation=operation):
                result = self.s.gate(operation, kcr_hold(self.s), epoch_authorization=self.eaa)
                self.assertFalse(result.permitted)
                self.assertEqual(result.reason, "OPERATION_NOT_ALLOWLISTED")
        for operation in (SR.VOID_CHALLENGE, SR.QUARANTINE_USE):
            self.assertEqual(self.s.gate(operation, kcr_hold(self.s)).reason, "RECOVERY_PHASE_MISMATCH")

    def test_quarantine_after_the_witness_committed_the_advance(self):
        s = B.PrepBScenario().mark()
        s.recover(stop_after="execution")
        for operation in (SR.VOID_CHALLENGE, SR.QUARANTINE_USE):
            result = s.gate(operation, kcr_hold(s))
            self.assertTrue(result.permitted, (operation, result.reason))
            self.assertIs(result.facts["signingPermitted"], False)
        self.assertEqual(s.gate(SR.ADVANCE_EPOCH, kcr_hold(s), epoch_authorization=self.eaa).reason,
                         "RECOVERY_PHASE_MISMATCH")
        self.assertEqual(s.gate(SR.QUARANTINE_USE, kcr_hold(s, successor=B.S3.replace("3", "4"))).reason,
                         "HOLD_INVALID")
        # The signer's normal issuance readiness is still NOT_READY while P is loaded.
        loaded_p = s.readiness(ELIGIBILITY, hold_value=kcr_hold(s), key_id=B.P0, record=None, register=None,
                               inventory_value=B.inventory(current=B.BLOB[B.P0]), phase=WR.STEADY)
        self.assertFalse(loaded_p.ready)

    def test_gate_requires_the_exact_hold_phase_and_authorization(self):
        s, eaa = self.s, self.eaa
        cases = {
            "no hold": (dict(hold_value=None), "HOLD_INVALID"),
            "released hold": (dict(hold_value=kcr_hold(s, state=SC.RELEASED, witness=s.head.digest)), "HOLD_NOT_HELD"),
            "rotation hold": (dict(hold_value=B.hold(witness=s.digests["holdEngaged"])),
                              "HOLD_NOT_COMPROMISE_RECOVERY"),
            "custody-debt hold": (dict(hold_value=B.hold(kind=SC.KEY_COMPROMISE_RECOVERY,
                                                         ceremony=B.C2 + SC.CUSTODY_DEBT_SUFFIX,
                                                         witness=s.head.digest)), "HOLD_NOT_COMPROMISE_RECOVERY"),
            "wrong predecessor": (dict(hold_value={**kcr_hold(s), "expectedPredecessorKeyId": B.S3}),
                                  "RECOVERY_SEQUENCE_INVALID"),
            "missing epoch authorization": (dict(epoch_authorization=None), "EPOCH_AUTHORIZATION_MISSING"),
            "wrong epoch reason": (dict(epoch_authorization=F.epoch_authorization(
                s.head, self.target, reason="OPERATOR_RECOVERY", successorRecoveryEpoch=B.EN.to_dict())),
                "EPOCH_AUTHORIZATION_REASON_INVALID"),
            "authorization for another witness": (dict(epoch_authorization=F.epoch_authorization(
                RC.RecoveryWitnessV2.from_verified_dict(s.genesis), self.target, reason=SR.KEY_COMPROMISE,
                successorRecoveryEpoch=B.EN.to_dict())), "EPOCH_AUTHORIZATION_NOT_BOUND_TO_HEAD"),
            "unsigned authorization": (dict(epoch_authorization={**eaa, "signature": None}),
                                       "EPOCH_AUTHORIZATION_NOT_VERIFIED"),
            "prod profile": (dict(profile=dataclasses.replace(B.PROFILE, environment="prod")),
                             "PROFILE_NOT_DEV_SYNTHETIC"),
            "other profile": (dict(profile=dataclasses.replace(B.PROFILE, prepared_path="/tmp/p")),
                              "PROFILE_NOT_DEV_SYNTHETIC"),
        }
        for name, (overrides, expected) in cases.items():
            with self.subTest(name):
                hold_value = overrides.pop("hold_value", kcr_hold(s))
                overrides.setdefault("epoch_authorization", eaa)
                result = s.gate(SR.ADVANCE_EPOCH, hold_value, **overrides)
                self.assertFalse(result.permitted)
                self.assertEqual(result.reason, expected)
        genesis = B.PrepBScenario()
        early = genesis.gate(SR.ADVANCE_EPOCH, kcr_hold(genesis, witness=genesis.digests["genesis"]),
                             epoch_authorization=eaa)
        self.assertEqual((early.reason, early.detail), ("RECOVERY_PHASE_MISMATCH", SR.RECOVERY_NOT_STARTED))

    def test_adoption_is_journalled_once(self):
        s = B.PrepBScenario().mark()
        authorization = s.recover(stop_after="adoption")
        result = s.gate(SR.ADVANCE_EPOCH, kcr_hold(s), epoch_authorization=authorization,
                        ledger_observation=W2.observe_authority_recovery_ledger(s.ledger))
        self.assertEqual(result.reason, "ADOPTION_ALREADY_JOURNALLED")

    def test_gate_is_not_wired_into_any_signer(self):
        # B1b-3e PR-1S (S-10): the gate is wired into the signer ONLY through `recovery.py` (C-4 recovery ops);
        # root tooling may evaluate readiness; nothing in core-api or the memory broker reaches it.
        wired = sorted(path.name for path in (ROOT / "services/authority-dev/lilith_authority_dev").rglob("*.py")
                       if "successor_readiness" in path.read_text(encoding="utf-8"))
        self.assertEqual(wired, ["recovery.py"])
        for tree in ("services/core-api", "services/memory-broker"):
            for path in (ROOT / tree).rglob("*.py"):
                if ".venv" not in path.parts:
                    self.assertNotIn("successor_readiness", path.read_text(encoding="utf-8", errors="ignore"), path)
        credential = (ROOT / "services/authority-dev/lilith_authority_dev/server.py").read_text(encoding="utf-8")
        self.assertIn("CREDENTIAL_ABSENT", credential)  # no credential-less signer mode


# -------------------------------------------------- custody (RR-26, SW-1) ---

class CustodyObservationTests(unittest.TestCase):
    def test_phases_and_roles(self):
        c = B.ceremony()
        states = {
            SC.PREDECESSOR_STEADY: B.custody(current=c.predecessor_blob_sha256),
            SC.STATE_A_PREPARED: B.custody(current=c.predecessor_blob_sha256, prepared=c.successor_blob_sha256),
            SC.STATE_B_VACATED: B.custody(current=None, prepared=c.successor_blob_sha256,
                                          retired=c.predecessor_blob_sha256),
            SC.STATE_C_INSTALLED: B.custody(current=c.successor_blob_sha256, retired=c.predecessor_blob_sha256),
            SC.SUCCESSOR_STEADY: B.custody(current=c.successor_blob_sha256),
        }
        for state, observation in states.items():
            result = SC.custody_state(observation, c)
            self.assertEqual(result.state, state, result.reason)
            self.assertIs(result.facts["authorityGranted"], False)
            self.assertLessEqual(result.facts["loadableBlobs"], 1)

    def test_custody_facts_fail_closed(self):
        c = B.ceremony()
        p, s = c.predecessor_blob_sha256, c.successor_blob_sha256
        cases = {
            "filesystem mismatch": (B.custody(current=p, prepared=s, devices={SC.CURRENT: 7, SC.PREPARED: 8,
                                                                               SC.RETIRED: 7}),
                                    "CUSTODY_FILESYSTEM_MISMATCH"),
            "filesystem unproven": (B.custody(current=p, devices={SC.CURRENT: 7, SC.PREPARED: None, SC.RETIRED: 7}),
                                    "SAME_FILESYSTEM_UNPROVEN"),
            "custody root missing": (B.custody(current=p, root=SC.CustodyRootFactsV1(WR.ABSENT)),
                                     "CUSTODY_ROOT_MISSING"),
            "custody root symlink": (B.custody(current=p, root=SC.CustodyRootFactsV1(WR.SYMLINK)),
                                     "CUSTODY_ROOT_NOT_DIRECTORY"),
            "custody root mode": (B.custody(current=p, root=SC.CustodyRootFactsV1(WR.DIRECTORY, 0, 0, 0o755,
                                                                                  SC.CUSTODY_ROOT_NAMES)),
                                  "CUSTODY_ROOT_CUSTODY"),
            "custody root extra entry": (B.custody(current=p, root=SC.CustodyRootFactsV1(
                WR.DIRECTORY, 0, 0, 0o700, ("abandoned", "prepared", "retired"))), "CUSTODY_ROOT_UNEXPECTED_ENTRY"),
            "extra prepared blob": (B.custody(current=p, prepared=s, extra={WR.PREPARED: (B.slot(B.OTHER_BLOB,
                                                                                                name="next.cred"),)}),
                                    "CUSTODY_SLOT_NAME_UNEXPECTED"),
            "symlink in retired": (B.custody(current=s, retired=None, extra={WR.RETIRED: (
                B.slot(None, kind=WR.SYMLINK),)}), "CUSTODY_INVENTORY_NOT_VERIFIED"),
            "second credstore blob": (B.custody(current=p, extra={WR.CREDSTORE: (B.slot(B.OTHER_BLOB,
                                                                                        name="other.cred"),)}),
                                      "CUSTODY_INVENTORY_NOT_VERIFIED"),
            "duplicate blob": (B.custody(current=p, prepared=p), "CUSTODY_INVENTORY_NOT_VERIFIED"),
            "wrong prepared blob": (B.custody(current=p, prepared=B.OTHER_BLOB), "WRONG_SUCCESSOR_BLOB"),
            "wrong retired blob": (B.custody(current=s, retired=B.OTHER_BLOB), "WRONG_PREDECESSOR_BLOB"),
            "wrong current blob": (B.custody(current=B.OTHER_BLOB, prepared=s), "WRONG_PREDECESSOR_BLOB"),
            "all three slots": (B.custody(current=p, prepared=s, retired=B.OTHER_BLOB), "CUSTODY_PHASE_UNRECOGNIZED"),
            "nothing loadable, nothing staged": (B.custody(current=None), "CUSTODY_PHASE_UNRECOGNIZED"),
        }
        for name, (observation, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(SC.custody_state(observation, c).reason, expected)
        missing = B.custody(current=p)
        locations = tuple(loc if loc.role != WR.RETIRED else WR.CredentialLocationObservationV1(WR.RETIRED, WR.ABSENT)
                          for loc in missing.inventory.locations)
        absent = dataclasses.replace(missing, inventory=WR.CredentialInventoryObservationV1(locations))
        self.assertEqual(SC.observe_custody(absent).reason, "CUSTODY_DIRECTORY_MISSING")

    def test_forward_only_transition_table(self):
        rule = SC.custody_transition_reason
        self.assertIsNone(rule(SC.PREDECESSOR_STEADY, SC.STATE_A_PREPARED, authority_ponr_passed=False))
        self.assertIsNone(rule(SC.STATE_A_PREPARED, SC.PREDECESSOR_STEADY, authority_ponr_passed=False))  # abandon
        for source, target in ((SC.STATE_A_PREPARED, SC.STATE_B_VACATED), (SC.STATE_B_VACATED, SC.STATE_C_INSTALLED),
                               (SC.STATE_C_INSTALLED, SC.SUCCESSOR_STEADY)):
            self.assertIsNone(rule(source, target, authority_ponr_passed=True))
            self.assertEqual(rule(source, target, authority_ponr_passed=False), "AUTHORITY_PONR_NOT_REACHED")
        self.assertEqual(rule(SC.STATE_B_VACATED, SC.STATE_A_PREPARED, authority_ponr_passed=True),
                         "PREDECESSOR_RESTORE_FORBIDDEN")
        self.assertEqual(rule(SC.STATE_C_INSTALLED, SC.STATE_A_PREPARED, authority_ponr_passed=True),
                         "PREDECESSOR_RESTORE_FORBIDDEN")
        self.assertEqual(rule(SC.STATE_A_PREPARED, SC.PREDECESSOR_STEADY, authority_ponr_passed=True),
                         "PREDECESSOR_RESTORE_FORBIDDEN")
        self.assertEqual(rule(SC.STATE_C_INSTALLED, SC.STATE_B_VACATED, authority_ponr_passed=True),
                         "CUSTODY_TRANSITION_NOT_DEFINED")
        self.assertEqual(rule(SC.STATE_A_PREPARED, SC.STATE_C_INSTALLED, authority_ponr_passed=True),
                         "CUSTODY_TRANSITION_NOT_DEFINED")
        self.assertEqual(rule(SC.PREDECESSOR_STEADY, SC.STATE_A_PREPARED, authority_ponr_passed=True),
                         "AUTHORITY_PONR_ALREADY_PASSED")

    def test_prepare_leaves_current_byte_identical(self):
        c = B.ceremony()
        before = B.custody(current=c.predecessor_blob_sha256)
        after = B.custody(current=c.predecessor_blob_sha256, prepared=c.successor_blob_sha256)
        facts = (1, 2, 0o100600, 0, 0, 128, c.predecessor_blob_sha256)
        result = SC.verify_preparation(before=before, after=after, ceremony=c, current_facts_before=facts,
                                       current_facts_after=facts)
        self.assertTrue(result.verified, result.reason)
        self.assertIs(result.facts["retiredWritten"], False)
        self.assertEqual(SC.verify_preparation(before=before, after=dataclasses.replace(after, current_identity=(7, 101)),
                                               ceremony=c).reason, "CURRENT_CHANGED")
        self.assertEqual(SC.verify_preparation(before=before, after=after, ceremony=c, current_facts_before=facts,
                                               current_facts_after=facts[:-1] + ("0" * 64,)).detail, "KEYGEN_FACTS")
        self.assertEqual(SC.verify_preparation(before=before, after=B.custody(current=B.OTHER_BLOB,
                                                                              prepared=c.successor_blob_sha256),
                                               ceremony=c).reason, "WRONG_PREDECESSOR_BLOB")
        self.assertEqual(SC.verify_preparation(before=before, after=before, ceremony=c).reason, "PREPARED_NOT_CREATED")
        with_retired = B.custody(current=None, prepared=c.successor_blob_sha256, retired=c.predecessor_blob_sha256)
        self.assertEqual(SC.verify_preparation(before=before, after=with_retired, ceremony=c).reason,
                         "PREPARED_NOT_CREATED")


class CustodyAuthorizationTests(unittest.TestCase):
    def authorize(self, scenario, step, observation, hold_value, register=None, c=None):
        return SR.authorize_custody_step(step=step, custody=observation, ceremony=c or B.ceremony(), hold=hold_value,
                                         store=scenario.context(), witness_store=scenario.observation(),
                                         head_registries=tuple(scenario.registries),
                                         ceremony_register=register if register is not None
                                         else B.ceremony_register(), profile=B.PROFILE)

    def test_rotation_forward_cutover(self):
        c = B.ceremony()
        genesis = B.PrepBScenario()
        held = B.hold(witness=genesis.digests["genesis"])
        prepare = self.authorize(genesis, SC.PREPARE, B.custody(current=c.predecessor_blob_sha256), held)
        self.assertTrue(prepare.planned, prepare.reason)
        self.assertEqual(prepare.operation, ("KEYGEN", "successor", "2"))
        burned = self.authorize(genesis, SC.PREPARE, B.custody(current=c.predecessor_blob_sha256), held,
                                register=B.ceremony_register(B.ceremony_record()))
        self.assertEqual(burned.reason, "ORDINAL_BURNED")
        a = B.custody(current=c.predecessor_blob_sha256, prepared=c.successor_blob_sha256)
        self.assertEqual(self.authorize(genesis, SC.VACATE, a, held).reason, "AUTHORITY_PONR_NOT_REACHED")
        abandon = self.authorize(genesis, SC.ABANDON, a, held)
        self.assertEqual(abandon.operation, ("UNLINK", SC.PREPARED_PATH))
        s = B.rotated()
        vacate = self.authorize(s, SC.VACATE, a, held)
        self.assertTrue(vacate.planned, vacate.reason)
        self.assertEqual(vacate.operation, ("RENAME", SC.CURRENT_PATH, SC.RETIRED_PATH))
        self.assertEqual(self.authorize(s, SC.ABANDON, a, held).reason, "PREDECESSOR_RESTORE_FORBIDDEN")
        b = B.custody(current=None, prepared=c.successor_blob_sha256, retired=c.predecessor_blob_sha256)
        install = self.authorize(s, SC.INSTALL, b, held)
        self.assertEqual(install.operation, ("RENAME", SC.PREPARED_PATH, SC.CURRENT_PATH))
        self.assertEqual(install.expected_sha256, c.successor_blob_sha256)
        self.assertEqual(self.authorize(s, SC.VACATE, b, held).reason, "CUSTODY_STATE_NOT_FROM_STATE")
        self.assertEqual(self.authorize(s, SC.INSTALL, a, held).reason, "CUSTODY_STATE_NOT_FROM_STATE")

    def test_custody_step_needs_hold_and_authority(self):
        c = B.ceremony()
        s = B.rotated()
        a = B.custody(current=c.predecessor_blob_sha256, prepared=c.successor_blob_sha256)
        held = B.hold(witness=s.digests["holdEngaged"])
        cases = {
            "no hold": (None, "HOLD_MISSING"),
            "released hold": (rotated_released(s), "HOLD_NOT_HELD"),
            "other ceremony": (B.hold(ceremony=B.C3, successor=B.S3, witness=s.digests["holdEngaged"]),
                               "HOLD_CEREMONY_MISMATCH"),
            "other predecessor": ({**held, "expectedPredecessorKeyId": B.S3}, "HOLD_CEREMONY_MISMATCH"),
        }
        for name, (value, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(self.authorize(s, SC.VACATE, a, value).reason, expected)
        mismatch = B.custody(current=c.predecessor_blob_sha256, prepared=c.successor_blob_sha256,
                             devices={SC.CURRENT: 1, SC.PREPARED: 2, SC.RETIRED: 1})
        self.assertEqual(self.authorize(s, SC.VACATE, mismatch, held).reason, "CUSTODY_FILESYSTEM_MISMATCH")
        wrong = B.custody(current=c.predecessor_blob_sha256, prepared=B.OTHER_BLOB)
        self.assertEqual(self.authorize(s, SC.VACATE, wrong, held).reason, "WRONG_SUCCESSOR_BLOB")
        stale = B.rotated()
        stale.storage.plant(WS.STATE, WR.POINTER_NAME, stale.storage.read(WR.CHAIN_DIRECTORY, "1.json"))
        self.assertEqual(self.authorize(stale, SC.VACATE, a, held).reason, "HISTORY_NOT_VERIFIED")

    def test_compromise_recovery_prepares_only_after_the_marking(self):
        c = B.ceremony()
        genesis = B.PrepBScenario()
        held = kcr_hold(genesis, witness=genesis.digests["genesis"])
        steady = B.custody(current=c.predecessor_blob_sha256)
        self.assertEqual(self.authorize(genesis, SC.PREPARE, steady, held).reason, "COMPROMISE_MARKING_NOT_COMMITTED")
        marked = genesis.mark()
        self.assertTrue(self.authorize(marked, SC.PREPARE, steady, held).planned)
        a = B.custody(current=c.predecessor_blob_sha256, prepared=c.successor_blob_sha256)
        self.assertEqual(self.authorize(marked, SC.VACATE, a, held).reason, "AUTHORITY_PONR_NOT_REACHED")
        marked.recover()
        self.assertTrue(self.authorize(marked, SC.VACATE, a, held).planned)


# ---------------------------------------- predecessor destruction (RR-29, §13) ---

class DestructionTests(unittest.TestCase):
    def setUp(self):
        self.s = B.rotated()
        self.c = B.ceremony()
        self.installed = B.custody(current=self.c.successor_blob_sha256, retired=self.c.predecessor_blob_sha256)
        self.steady = B.custody(current=self.c.successor_blob_sha256)

    def full(self, **overrides):
        if "holds" not in overrides:
            overrides.setdefault("hold_value", rotated_released(self.s))
        return self.s.readiness(FULL, **overrides)

    def evidence(self, **overrides):
        value = dict(before=B.slot(self.c.predecessor_blob_sha256), unlink_succeeded=True, directory_fsynced=True,
                     after_lookup=WR.ABSENT, after=self.steady)
        value.update(overrides)
        return SC.DestructionObservationV1(**value)

    def test_destruction_is_denied_before_s_current(self):
        eligible = self.s.readiness(ELIGIBILITY, hold_value=B.hold(witness=self.s.digests["holdEngaged"]))
        self.assertTrue(eligible.ready)
        denied = SR.verify_destruction_order(readiness=eligible, custody=self.installed, ceremony=self.c,
                                             profile=B.PROFILE)
        self.assertEqual(denied.reason, "DESTRUCTION_BEFORE_S_CURRENT")
        held = self.full(hold_value=B.hold(witness=self.s.digests["holdEngaged"]))
        self.assertEqual(SR.verify_destruction_order(readiness=held, custody=self.installed, ceremony=self.c,
                                                     profile=B.PROFILE).reason, "DESTRUCTION_BEFORE_S_CURRENT")
        genesis = B.PrepBScenario()
        initial = genesis.readiness(FULL, key_id=B.P0, phase=WR.STEADY,
                                    hold_value=B.initial_hold(state=SC.RELEASED, witness=genesis.digests["genesis"]))
        self.assertTrue(initial.ready)
        self.assertEqual(SR.verify_destruction_order(readiness=initial, custody=self.installed, ceremony=self.c,
                                                     profile=B.PROFILE).reason, "DESTRUCTION_CEREMONY_MISMATCH")

    def test_destruction_after_s_current(self):
        full = self.full()
        self.assertTrue(full.ready, full.reasons)
        order = SR.verify_destruction_order(readiness=full, custody=self.installed, ceremony=self.c, profile=B.PROFILE)
        self.assertTrue(order.permitted, order.reason)
        self.assertEqual(order.plan.operation, ("UNLINK", SC.RETIRED_PATH))
        self.assertIs(order.facts["rollbackToPredecessorPermitted"], False)
        wrong = B.custody(current=self.c.successor_blob_sha256, retired=B.OTHER_BLOB)
        self.assertEqual(SR.verify_destruction_order(readiness=full, custody=wrong, ceremony=self.c,
                                                     profile=B.PROFILE).reason, "PREDECESSOR_NOT_RETIRED")
        steady = SR.verify_destruction_order(readiness=full, custody=self.steady, ceremony=self.c, profile=B.PROFILE)
        self.assertEqual(steady.reason, "PREDECESSOR_NOT_RETIRED")
        other = SC.CustodyCeremonyV1(B.C2, B.P0, B.BLOB[B.P0], B.S2, B.OTHER_BLOB)
        self.assertEqual(SR.verify_destruction_order(readiness=full, custody=self.installed, ceremony=other,
                                                     profile=B.PROFILE).reason, "PREDECESSOR_NOT_RETIRED")

    def test_destruction_evidence(self):
        digest = self.full().facts["readinessDigest"]
        done = SC.evaluate_destruction_evidence(self.evidence(), self.c, readiness_digest=digest)
        self.assertTrue(done.destroyed, done.reason)
        self.assertEqual(done.record["mediaZeroization"], "NOT_CLAIMED")
        self.assertIs(done.record["predecessorMaterialDestroyedFromActiveCustody"], True)
        self.assertIs(done.record["authorityGranted"], False)
        self.assertEqual(done.facts["revocationEffect"], "NONE")  # destruction != revocation
        cases = {
            "no before observation": (dict(before=None), "RETIRED_BLOB_NOT_OBSERVED_BEFORE"),
            "wrong mode before": (dict(before=B.slot(self.c.predecessor_blob_sha256, mode=0o644)),
                                  "RETIRED_BLOB_CUSTODY_BEFORE"),
            "hash mismatch before unlink": (dict(before=B.slot(B.OTHER_BLOB)), "RETIRED_BLOB_HASH_MISMATCH"),
            "unlink failed": (dict(unlink_succeeded=False), "UNLINK_NOT_CONFIRMED"),
            "directory not fsynced": (dict(directory_fsynced=False), "DIRECTORY_FSYNC_NOT_CONFIRMED"),
            "still present": (dict(after_lookup=WR.REGULAR), "RETIRED_BLOB_STILL_PRESENT"),
            "inventory not steady": (dict(after=self.installed), "STEADY_INVENTORY_NOT_VERIFIED"),
            "steady but not S": (dict(after=B.custody(current=self.c.predecessor_blob_sha256)),
                                 "STEADY_CURRENT_NOT_SUCCESSOR"),
        }
        for name, (overrides, expected) in cases.items():
            with self.subTest(name):
                outcome = SC.evaluate_destruction_evidence(self.evidence(**overrides), self.c, readiness_digest=digest)
                self.assertFalse(outcome.destroyed)
                self.assertEqual(outcome.reason, expected)
                self.assertEqual(outcome.facts["custodyClass"], SC.KNOWN_CUSTODY_DEBT)
                self.assertTrue(outcome.facts["availabilityHoldRequired"])
                self.assertIs(outcome.facts["authorityRollbackPermitted"], False)
                self.assertIs(outcome.facts["predecessorRestorePermitted"], False)

    def test_destruction_failure_after_s_current(self):
        full = self.full()
        failed = SC.evaluate_destruction_evidence(self.evidence(unlink_succeeded=False), self.c,
                                                  readiness_digest=full.facts["readinessDigest"])
        debt = SR.destruction_failure_outcome(failed, ceremony=self.c, transition_kind=SC.ROTATION,
                                              head_witness_digest=self.s.head.digest, profile=B.PROFILE)
        self.assertEqual(debt["ceremonyId"], B.C2 + SC.CUSTODY_DEBT_SUFFIX)
        self.assertEqual(debt["state"], SC.HELD)
        self.assertIsNone(SC.hold_transition_reason(rotated_released(self.s), debt, profile=B.PROFILE))
        # Issuance fails closed; the authority head is untouched; S stays current.
        blocked = self.full(holds=(rotated_released(self.s), debt))
        self.assertEqual(reasons(blocked), {"CEREMONY_HOLD": "CEREMONY_HOLD_HELD"})
        self.assertEqual(blocked.facts["headCurrentKeyId"], B.S2)
        self.assertEqual(self.s.history().head.registry_head, RC.registry_head(B.rot2()))
        # Owner retry: eligibility under the debt hold plus the ceremony's own release.
        retry = self.s.readiness(ELIGIBILITY, holds=(rotated_released(self.s), debt))
        self.assertTrue(retry.ready, retry.reasons)
        order = SR.verify_destruction_order(readiness=retry, custody=self.installed, ceremony=self.c,
                                            profile=B.PROFILE)
        self.assertTrue(order.permitted, order.reason)
        debt_alone = self.s.readiness(ELIGIBILITY, holds=(debt,))
        self.assertEqual(check(debt_alone, "CEREMONY_HOLD").reason, "HOLD_DEBT_WITHOUT_RELEASED_CEREMONY")
        self.assertFalse(SR.verify_destruction_order(readiness=debt_alone, custody=self.installed, ceremony=self.c,
                                                     profile=B.PROFILE).permitted)
        # The debt hold releases only once destruction is complete.
        debt_released = {**debt, "state": SC.RELEASED, "reason": SC.OWNER_RELEASE_AFTER_ELIGIBILITY}
        self.assertIsNone(SC.hold_store_transition_reason(
            SC.hold_store(rotated_released(self.s), debt), SC.hold_store(rotated_released(self.s), debt_released),
            profile=B.PROFILE))
        open_debt = self.full(holds=(rotated_released(self.s), debt_released))
        self.assertEqual(check(open_debt, "CEREMONY_HOLD").reason, "HOLD_CUSTODY_DEBT_OPEN")
        closed = self.full(holds=(rotated_released(self.s), debt_released), phase=WR.STEADY)
        self.assertTrue(closed.ready, closed.reasons)
        self.assertEqual(closed.facts["authorityKeyTransition"]["predecessorMaterial"],
                         "DESTROYED_FROM_ACTIVE_CUSTODY")
        with self.assertRaises(ValueError):
            SR.destruction_failure_outcome(SC.evaluate_destruction_evidence(
                self.evidence(), self.c, readiness_digest=full.facts["readinessDigest"]), ceremony=self.c,
                transition_kind=SC.ROTATION, head_witness_digest=self.s.head.digest, profile=B.PROFILE)


@unittest.skipUnless(POSIX, "real rename / fsync / unlink semantics are POSIX")
class TempCustodyExecutionTests(unittest.TestCase):
    """The complete forward ladder on a real temporary custody tree."""

    def test_a_b_c_then_logical_destruction(self):
        s, c = B.rotated(), SC.CustodyCeremonyV1(B.C2, B.P0, "", B.S2, "")
        with tempfile.TemporaryDirectory() as directory:
            tree = B.TempCustody(directory)
            p_bytes, s_bytes = b"TEST_ONLY predecessor ciphertext", b"TEST_ONLY successor ciphertext"
            c = dataclasses.replace(c, predecessor_blob_sha256=hashlib.sha256(p_bytes).hexdigest(),
                                    successor_blob_sha256=hashlib.sha256(s_bytes).hexdigest())
            tree.write(SC.CURRENT_PATH, p_bytes)
            before = tree.observe()
            self.assertEqual(SC.custody_state(before, c).state, SC.PREDECESSOR_STEADY)
            tree.write(SC.PREPARED_PATH, s_bytes)  # what `successor 2` writes
            after = tree.observe()
            self.assertTrue(SC.verify_preparation(before=before, after=after, ceremony=c).verified)
            held = B.hold(witness=s.digests["holdEngaged"])
            authorize = lambda step: SR.authorize_custody_step(  # noqa: E731
                step=step, custody=tree.observe(), ceremony=c, hold=held, store=s.context(),
                witness_store=s.observation(), head_registries=tuple(s.registries), profile=B.PROFILE)
            tree.execute(authorize(SC.VACATE))
            self.assertEqual(SC.custody_state(tree.observe(), c).state, SC.STATE_B_VACATED)
            self.assertFalse(os.path.lexists(tree.path(SC.CURRENT_PATH)))  # fail-safe: nothing loadable
            self.assertEqual(authorize(SC.VACATE).reason, "CUSTODY_STATE_NOT_FROM_STATE")
            tree.execute(authorize(SC.INSTALL))
            self.assertEqual(SC.custody_state(tree.observe(), c).state, SC.STATE_C_INSTALLED)
            with open(tree.path(SC.CURRENT_PATH), "rb") as handle:
                self.assertEqual(handle.read(), s_bytes)
            # S_CURRENT (FULL readiness, with S's real hashes) then destruction.
            record = B.ceremony_record(blob=c.successor_blob_sha256)
            full = s.readiness(FULL, hold_value=rotated_released(s), pub=B.publication_bytes(
                B.S2, blob=c.successor_blob_sha256), record=record, register=B.ceremony_register(record),
                blob=c.successor_blob_sha256, inventory_value=tree.observe().inventory)
            self.assertTrue(full.ready, full.reasons)
            order = SR.verify_destruction_order(readiness=full, custody=tree.observe(), ceremony=c, profile=B.PROFILE)
            self.assertTrue(order.permitted, order.reason)
            before_unlink = [e for loc in tree.observe().inventory.locations if loc.role == WR.RETIRED
                             for e in loc.entries][0]
            tree.execute(order.plan)
            evidence = SC.DestructionObservationV1(
                before=before_unlink, unlink_succeeded=True,
                directory_fsynced=("fsync_dir", os.path.dirname(SC.RETIRED_PATH)) in tree.log,
                after_lookup=WR.ABSENT if not os.path.lexists(tree.path(SC.RETIRED_PATH)) else WR.REGULAR,
                after=tree.observe())
            outcome = SC.evaluate_destruction_evidence(evidence, c, readiness_digest=full.facts["readinessDigest"])
            self.assertTrue(outcome.destroyed, outcome.reason)
            # Every rename and unlink is followed by an fsync of each directory it touched.
            self.assertEqual([entry[0] for entry in tree.log], ["rename", "fsync_dir", "fsync_dir", "rename",
                                                                "fsync_dir", "fsync_dir", "unlink", "fsync_dir"])

    def test_temp_tree_same_filesystem_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = B.TempCustody(directory)
            tree.write(SC.CURRENT_PATH, b"TEST_ONLY p")
            observation = tree.observe()
            self.assertIsNone(SC.same_filesystem_reason(observation))
            os.symlink(tree.path(SC.CURRENT_PATH), tree.path(SC.PREPARED_PATH))
            c = SC.CustodyCeremonyV1(B.C2, B.P0, hashlib.sha256(b"TEST_ONLY p").hexdigest(), B.S2, "0" * 64)
            self.assertEqual(SC.custody_state(tree.observe(), c).reason, "CUSTODY_INVENTORY_NOT_VERIFIED")


# ----------------------------------------------------------- crash matrix ---

class CrashMatrixTests(unittest.TestCase):
    """Design §11 rows 1-12 (SW-9) and the routine-rotation rows (§4.1)."""

    def assert_not_ready(self, result, check_name=None, reason=None):
        self.assertFalse(result.ready)
        self.assertFalse(result.facts["issuanceReady"])
        if check_name:
            self.assertEqual(check(result, check_name).reason, reason, result.reasons)

    def test_sw9_rows(self):
        c = B.ceremony()
        p, s_blob = c.predecessor_blob_sha256, c.successor_blob_sha256
        # 1. hold engaged, nothing prepared: head names P0; custody steady; nothing can move.
        h = B.PrepBScenario()
        held = kcr_hold(h, witness=h.digests["genesis"])
        row1 = h.readiness(FULL, key_id=B.P0, phase=WR.STEADY, hold_value=held, record=None, register=None)
        self.assert_not_ready(row1, "CEREMONY_HOLD", "HOLD_MISSING")
        row1e = h.readiness(ELIGIBILITY, key_id=B.P0, phase=WR.STEADY, hold_value=held, record=None, register=None)
        self.assert_not_ready(row1e, "CEREMONY_HOLD", "HOLD_MISSING")
        self.assertEqual(SC.custody_state(B.custody(current=p), c).state, SC.PREDECESSOR_STEADY)
        # 2. successor prepared, marking not yet done: S is KEY_UNKNOWN to the head.
        row2 = h.readiness(ELIGIBILITY, hold_value=held, phase=WR.SUCCESSOR_PREPARED,
                           inventory_value=B.inventory(current=p, prepared=s_blob))
        self.assert_not_ready(row2)
        self.assertEqual(check(row2, "LOADED_KEY_BINDING").reason, "PUBLICATION_SCOPE_MISMATCH")
        # 3. marking signed, RHAA absent: staged registry is not the head.
        h.registries.append(B.mark2())
        self.assertEqual(h.gate(SR.ADVANCE_EPOCH, held, epoch_authorization=None).reason, "RECOVERY_PHASE_MISMATCH")
        h.registries.pop()
        # 4. marking committed; EAA exists; ledger adopted; witness not advanced.
        m = B.PrepBScenario().mark()
        authorization = m.recover(stop_after="adoption")
        row4 = m.readiness(ELIGIBILITY, hold_value=kcr_hold(m), key_id=B.P0, record=None, register=None,
                           phase=WR.STEADY, inventory_value=B.inventory(current=p))
        self.assert_not_ready(row4, "AUTHORITY_LEDGER_POSITION", "LEDGER_EPOCH_AHEAD_OF_WITNESS")
        self.assertEqual(check(row4, "SINGLE_CURRENT_KEY").reason, "NO_CURRENT_ISSUANCE_KEY")
        self.assertEqual(m.gate(SR.ADVANCE_EPOCH, kcr_hold(m), epoch_authorization=authorization,
                                ledger_observation=W2.observe_authority_recovery_ledger(m.ledger)).reason,
                         "ADOPTION_ALREADY_JOURNALLED")
        m.execute_epoch_advance(authorization, B.rec3())  # the witness executes THE SAME EAA
        m.quarantine()
        m.digests["successorHead"] = m.head.digest
        # 5. epoch advance committed; custody still P0 (state A): binding refuses P0.
        row5 = m.readiness(FULL, hold_value=kcr_hold(m, state=SC.RELEASED), blob=p, health_value=B.health(B.P0),
                           phase=WR.SUCCESSOR_PREPARED, inventory_value=B.inventory(current=p, prepared=s_blob))
        self.assert_not_ready(row5, "LOADED_KEY_BINDING", "BLOB_HASH_MISMATCH")
        self.assertEqual(SC.custody_transition_reason(SC.STATE_A_PREPARED, SC.PREDECESSOR_STEADY,
                                                      authority_ponr_passed=True), "PREDECESSOR_RESTORE_FORBIDDEN")
        self._rows_6_to_12(m, kcr_hold(m, state=SC.RELEASED), kcr_hold(m), SC.KEY_COMPROMISE_RECOVERY)

    def test_routine_rotation_rows(self):
        s = B.rotated()
        self._rows_6_to_12(s, rotated_released(s), B.hold(witness=s.digests["holdEngaged"]), SC.ROTATION)

    def _rows_6_to_12(self, s, released, held, kind):
        c = B.ceremony()
        p, s_blob = c.predecessor_blob_sha256, c.successor_blob_sha256
        # 6. P -> RETIRED, S not installed: nothing loadable; forward install only.
        row6 = s.readiness(FULL, hold_value=released, phase=WR.CUTOVER_VACATED,
                           inventory_value=B.inventory(current=None, prepared=s_blob, retired=p))
        self.assert_not_ready(row6, "CREDENTIAL_INVENTORY", "CREDENTIAL_INVENTORY_PHASE_NOT_READY")
        self.assertEqual(SC.custody_transition_reason(SC.STATE_B_VACATED, SC.STATE_A_PREPARED,
                                                      authority_ponr_passed=True), "PREDECESSOR_RESTORE_FORBIDDEN")
        # 7. S installed, signer not started: no HEALTH.
        row7 = s.readiness(ELIGIBILITY, hold_value=held, health_value={})
        self.assert_not_ready(row7)
        self.assertEqual(check(row7, "LOADED_KEY_BINDING").status, WR.FAIL)
        # 8. HEALTH reports the predecessor.
        self.assert_not_ready(s.readiness(FULL, hold_value=released, health_value=B.health(B.P0)),
                              "LOADED_KEY_BINDING", "HEALTH_FINGERPRINT_MISMATCH")
        # 9. HEALTH reports S but the independent binding fails.
        self.assert_not_ready(s.readiness(FULL, hold_value=released, blob=B.OTHER_BLOB,
                                          inventory_value=B.inventory(current=B.OTHER_BLOB, retired=p)),
                              "LOADED_KEY_BINDING", "BLOB_HASH_MISMATCH")
        # 10. S_CURRENT with P retained: ready; destruction is the mandatory next step.
        row10 = s.readiness(FULL, hold_value=released)
        self.assertTrue(row10.ready, row10.reasons)
        installed = B.custody(current=s_blob, retired=p)
        self.assertTrue(SR.verify_destruction_order(readiness=row10, custody=installed, ceremony=c,
                                                    profile=B.PROFILE).permitted)
        # 11. crash during destruction: known custody debt, head unchanged, no rollback.
        outcome = SC.evaluate_destruction_evidence(SC.DestructionObservationV1(
            before=B.slot(p), unlink_succeeded=True, directory_fsynced=False, after_lookup=WR.REGULAR,
            after=installed), c, readiness_digest=row10.facts["readinessDigest"])
        self.assertEqual((outcome.status, outcome.facts["custodyClass"]),
                         (SC.DESTRUCTION_INCOMPLETE, SC.KNOWN_CUSTODY_DEBT))
        debt = SR.destruction_failure_outcome(outcome, ceremony=c, transition_kind=kind,
                                              head_witness_digest=s.head.digest, profile=B.PROFILE)
        self.assert_not_ready(s.readiness(FULL, holds=(released, debt)), "CEREMONY_HOLD", "CEREMONY_HOLD_HELD")
        self.assertEqual(s.history().head.digest, s.head.digest)
        # 12a. credential-only restore of P after S_CURRENT: the binding refuses it.
        self.assert_not_ready(s.readiness(FULL, hold_value=released, blob=p, health_value=B.health(B.P0),
                                          inventory_value=B.inventory(current=p)), "LOADED_KEY_BINDING",
                              "BLOB_HASH_MISMATCH")
        # 12b. whole-host snapshot (chain + pointer + registries + ledger) restored: NOT DETECTED.
        snapshot = B.PrepBScenario()
        restored = snapshot.readiness(FULL, key_id=B.P0, phase=WR.STEADY, record=None, register=None,
                                      hold_value=B.initial_hold(state=SC.RELEASED,
                                                                witness=snapshot.digests["genesis"]))
        self.assertTrue(restored.ready)  # the unresolved nonclaim, pinned
        self.assertIs(restored.facts["wholeHostRollbackProtected"], False)


class CompatibilityTests(unittest.TestCase):
    def test_prep_a_evaluator_and_goldens_are_unchanged(self):
        self.assertIn("CEREMONY_HOLD", WR.READINESS_CHECKS)
        self.assertEqual(SR.SUCCESSOR_READINESS_CHECKS[-1], "CEREMONY_HOLD")
        self.assertEqual(set(SR.SUCCESSOR_READINESS_CHECKS) - set(WR.READINESS_CHECKS),
                         {"PUBLICATION_BYTES", "KEY_TRANSITION", "COMPROMISE_EPOCH", "CEREMONY_PROVENANCE"})
        for name in ("b1b3e_golden.json", "b1b3e_prep_a_golden.json", "authority_b1b3a_golden.json",
                     "b1b3c_golden.json"):
            self.assertTrue((Path(__file__).with_name(name)).is_file(), name)
        self.assertEqual(RC.HEAD_ADVANCE_REASONS, frozenset({"SUCCESSOR_ROTATION", "ADMINISTRATIVE_REVOCATION",
                                                             "COMPROMISE_MARKING"}))
        self.assertIn("KEY_COMPROMISE", RC.EPOCH_ADVANCE_REASONS)

    def test_prep_a_boolean_hold_is_superseded(self):
        s = B.rotated()
        inputs = s.readiness_inputs(hold_value=None)
        self.assertFalse(inputs.base.hold_present)  # the Prep A boolean says "no hold"
        result = SR.evaluate_successor_readiness(inputs, mode=FULL)
        self.assertEqual(check(result, "CEREMONY_HOLD").reason, "HOLD_MISSING")  # absence never releases
        forced = SR.evaluate_successor_readiness(dataclasses.replace(
            inputs, base=dataclasses.replace(inputs.base, hold_present=True),
            hold_store=SC.hold_store(rotated_released(s))), mode=FULL)
        self.assertTrue(forced.ready, forced.reasons)  # the boolean is ignored either way

    def test_new_modules_are_pure(self):
        for module in (SC, SR):
            source = Path(module.__file__).read_text(encoding="utf-8")
            for needle in ("import os", "open(", "subprocess", "socket", "urllib", "sqlite", ".sign(",
                           "Ed25519PrivateKey"):
                self.assertNotIn(needle, source, (module.__name__, needle))

    def test_malformed_readiness_inputs(self):
        result = SR.evaluate_successor_readiness(object(), mode=FULL)
        self.assertFalse(result.ready)
        self.assertEqual(SR.evaluate_successor_readiness(B.rotated().readiness_inputs(), mode="S_CURRENT").status,
                         WR.NOT_READY)
        prod = dataclasses.replace(B.rotated().readiness_inputs(hold_value=None),
                                   profile=dataclasses.replace(B.PROFILE, environment="prod"))
        self.assertEqual(check(SR.evaluate_successor_readiness(prod, mode=FULL), "CEREMONY_HOLD").reason,
                         "PROFILE_NOT_DEV_SYNTHETIC")


# ------------------------------------------- custody-debt dominance (audit) ---

class CustodyDebtDominanceTests(unittest.TestCase):
    """historical RELEASED hold != permission to ignore a newer fail-safe hold."""

    def setUp(self):
        self.s = B.rotated()
        self.released = rotated_released(self.s)
        self.debt = B.hold(ceremony=B.C2 + SC.CUSTODY_DEBT_SUFFIX, witness=self.s.head.digest)

    def full(self, *holds, **overrides):
        return self.s.readiness(FULL, holds=holds, **overrides)

    def test_debt_held_dominates_the_original_release(self):
        self.assertTrue(self.full(self.released).ready)
        dominated = self.full(self.released, self.debt)
        self.assertFalse(dominated.ready)
        self.assertEqual(reasons(dominated), {"CEREMONY_HOLD": "CEREMONY_HOLD_HELD"})
        self.assertEqual(dominated.facts["hold"]["ceremonyId"], B.C2 + SC.CUSTODY_DEBT_SUFFIX)
        self.assertEqual(self.full(self.debt, self.released).checks["CEREMONY_HOLD"].reason, "CEREMONY_HOLD_HELD")
        self.assertIs(SC.CeremonyHoldV1.authority_granted, False)  # custody-debt hold != authority

    def test_debt_record_cannot_be_dropped_forked_or_rewound(self):
        both = SC.hold_store(self.released, self.debt)
        self.assertEqual(SC.hold_store_transition_reason(both, SC.hold_store(self.released), profile=B.PROFILE),
                         "HOLD_RECORD_REMOVED")  # absence is never a release
        self.assertEqual(SC.hold_store_transition_reason(
            both, SC.hold_store({**self.released, "state": SC.HELD, "reason": SC.ROTATION_IN_PROGRESS,
                                 "observedWitnessDigest": self.s.digests["holdEngaged"]}, self.debt),
            profile=B.PROFILE), "HOLD_ALREADY_RELEASED")  # no RELEASED -> HELD on the original ceremony
        debt_released = {**self.debt, "state": SC.RELEASED, "reason": SC.OWNER_RELEASE_AFTER_ELIGIBILITY}
        self.assertIsNone(SC.hold_store_transition_reason(both, SC.hold_store(self.released, debt_released),
                                                          profile=B.PROFILE))
        self.assertEqual(SC.hold_store_transition_reason(SC.hold_store(self.released),
                                                         SC.hold_store(self.released, debt_released),
                                                         profile=B.PROFILE), "HOLD_MUST_START_HELD")
        # One deterministic name per ceremony: a second (forked) debt record cannot coexist.
        fork = WR.StoreEntryV1("f" * 64 + ".json", WR.REGULAR, SC.hold_record_bytes(
            {**self.debt, "observedWitnessDigest": self.s.digests["holdEngaged"]}))
        forked = SC.HoldStoreObservationV1(both.entries + (fork,))
        self.assertEqual(SC.parse_hold_store(forked, profile=B.PROFILE)[1], "HOLD_STORE_NAME_MISMATCH")
        twice = SC.HoldStoreObservationV1(both.entries + (both.entries[1],))
        self.assertEqual(SC.parse_hold_store(twice, profile=B.PROFILE)[1], "HOLD_STORE_ENTRY_INVALID")
        result = self.s.readiness(FULL, store_value=forked)
        self.assertEqual(check(result, "CEREMONY_HOLD").reason, "HOLD_STORE_NAME_MISMATCH")

    def test_debt_binding_and_store_hygiene(self):
        cases = {
            "debt without the original release": ((self.debt,), "HOLD_DEBT_WITHOUT_RELEASED_CEREMONY"),

            "debt with a custody reason": ((self.released, {**self.debt, "reason": SC.ROTATION_IN_PROGRESS}),
                                           "HOLD_REASON_STATE_MISMATCH"),
            "another ceremony still HELD": ((self.released, B.hold(ceremony=B.C3, predecessor=B.S2, successor=B.S3,
                                                                   witness=self.s.head.digest)),
                                            "HOLD_SET_OTHER_HELD"),
            "empty store": ((), "HOLD_MISSING"),
        }
        for name, (holds, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(check(self.full(*holds), "CEREMONY_HOLD").reason, expected)
        # Retry-eligibility binding of the governing debt hold.
        for name, (debt, expected) in {
                "debt for another predecessor": ({**self.debt, "expectedPredecessorKeyId": B.S3},
                                                 "HOLD_PREDECESSOR_MISMATCH"),
                "debt at an earlier head": ({**self.debt, "observedWitnessDigest": self.s.digests["holdEngaged"]},
                                            "HOLD_WITNESS_HEAD_MISMATCH")}.items():
            with self.subTest(name):
                result = self.s.readiness(ELIGIBILITY, holds=(self.released, debt))
                self.assertEqual(check(result, "CEREMONY_HOLD").reason, expected)
        for store, expected in ((None, "HOLD_STORE_UNOBSERVED"),
                                (SC.HoldStoreObservationV1((WR.StoreEntryV1(SC.hold_record_name(B.C2), WR.SYMLINK),)),
                                 "HOLD_STORE_ENTRY_INVALID"),
                                (SC.HoldStoreObservationV1((WR.StoreEntryV1(SC.hold_record_name(B.C2), WR.REGULAR,
                                                                            json.dumps(self.released).encode()),)),
                                 "HOLD_STORE_ENTRY_INVALID")):
            with self.subTest(store=expected):
                self.assertEqual(check(self.s.readiness(FULL, store_value=store), "CEREMONY_HOLD").reason, expected)


# --------------------------------------------- RR-31 REGISTRY_MAINTENANCE ---

class RegistryMaintenanceTests(unittest.TestCase):
    AUTH = "rhaa.prep-b-noncurrent-1"

    def maintained(self) -> B.PrepBScenario:
        s = B.rotated()
        s.digests["priorHead"] = s.head.digest
        s.publish(s.issue_head_advance(B.mark_noncurrent3(), reason=SR.COMPROMISE_MARKING, authorization_id=self.AUTH),
                  B.mark_noncurrent3())
        s.activate(B.S2)
        return s

    def ceremony(self, authorization_id: str = AUTH, key_id: str = B.S2) -> str:
        return SC.registry_maintenance_ceremony_id(environment=B.ENV, current_key_id=key_id,
                                                   prior_head=RC.registry_head(B.rot2()),
                                                   target_head=RC.registry_head(B.mark_noncurrent3()),
                                                   authorization_id=authorization_id)

    def maint(self, s, *, state=SC.HELD, witness=None, ceremony=None, key=B.S2):
        return B.hold(kind=SC.REGISTRY_MAINTENANCE, state=state, ceremony=ceremony or self.ceremony(),
                      predecessor=key, successor=key, witness=witness or s.head.digest)

    def test_same_key_new_head_needs_a_fresh_cycle(self):
        s = self.maintained()
        stale = s.readiness(FULL, holds=(rotated_released(s),))
        self.assertEqual(reasons(stale), {"CEREMONY_HOLD": "HOLD_MISSING"})  # no new hold -> NOT_READY
        self.assertEqual(stale.facts["governingCeremony"], {"kind": SC.REGISTRY_MAINTENANCE,
                                                            "ceremonyId": self.ceremony()})
        self.assertEqual(stale.facts["keyTransition"]["kind"], SC.ROTATION)  # the base is unchanged
        for witness in (s.digests["priorHead"], s.head.digest):
            held = s.readiness(ELIGIBILITY, holds=(rotated_released(s), self.maint(s, witness=witness)))
            self.assertTrue(held.ready, held.reasons)
        released = self.maint(s, state=SC.RELEASED)
        self.assertIsNone(SC.hold_transition_reason(self.maint(s), released, profile=B.PROFILE))
        full = s.readiness(FULL, holds=(rotated_released(s), released))
        self.assertTrue(full.ready, full.reasons)
        self.assertEqual(full.facts["authorityKeyTransition"]["kind"], SC.REGISTRY_MAINTENANCE)
        self.assertIs(full.facts["authorityKeyTransition"]["authorityGranted"], False)
        held_full = s.readiness(FULL, holds=(rotated_released(s), self.maint(s)))
        self.assertEqual(check(held_full, "CEREMONY_HOLD").reason, "CEREMONY_HOLD_HELD")

    def test_maintenance_hold_binds_exactly_one_change(self):
        s = self.maintained()
        cases = {
            "released for the prior head": (self.maint(s, state=SC.RELEASED, witness=s.digests["priorHead"]),
                                            "HOLD_WITNESS_HEAD_MISMATCH"),
            "hold for another change": (self.maint(s, state=SC.RELEASED, ceremony=self.ceremony("rhaa.other")),
                                        "HOLD_MISSING"),
            "different current key": (self.maint(s, state=SC.RELEASED, key=B.P0), "HOLD_PREDECESSOR_MISMATCH"),
        }
        for name, (value, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(check(s.readiness(FULL, holds=(rotated_released(s), value)), "CEREMONY_HOLD").reason,
                                 expected)
        changed = {**self.maint(s), "expectedSuccessorKeyId": B.S3}
        self.assertEqual(SC.parse_ceremony_hold(changed, profile=B.PROFILE)[1], "HOLD_MAINTENANCE_KEY_CHANGED")
        for ceremony in ("test.registry-maintenance.by-hand", self.ceremony() + SC.CUSTODY_DEBT_SUFFIX,
                         "dev" + self.ceremony()[len(B.ENV):]):
            self.assertEqual(SC.parse_ceremony_hold({**self.maint(s), "ceremonyId": ceremony}, profile=B.PROFILE)[1],
                             "HOLD_CEREMONY_NOT_DERIVED", ceremony)
        self.assertEqual(SC.parse_ceremony_hold({**self.maint(s), "expectedPredecessorKeyId": None},
                                                profile=B.PROFILE)[1], "HOLD_PREDECESSOR_REQUIRED")

    def test_key_changing_and_epoch_changing_transitions_are_not_maintenance(self):
        rotated = B.rotated()
        rotation_change = SC.registry_maintenance_ceremony_id(
            environment=B.ENV, current_key_id=B.S2, prior_head=RC.registry_head(B.g1()),
            target_head=RC.registry_head(B.rot2()), authorization_id="rhaa.prep-b-rotation-1")
        hold = B.hold(kind=SC.REGISTRY_MAINTENANCE, state=SC.RELEASED, ceremony=rotation_change, predecessor=B.S2,
                      successor=B.S2, witness=rotated.head.digest)
        result = rotated.readiness(FULL, holds=(hold,))
        self.assertEqual(check(result, "CEREMONY_HOLD").reason, "HOLD_MISSING")
        self.assertEqual(result.facts["governingCeremony"]["kind"], SC.ROTATION)
        recovered = B.recovered()
        epoch_change = SC.registry_maintenance_ceremony_id(
            environment=B.ENV, current_key_id=B.S2, prior_head=RC.registry_head(B.mark2()),
            target_head=RC.registry_head(B.rec3()), authorization_id="eaa.prep-b-recovery-1")
        hold = B.hold(kind=SC.REGISTRY_MAINTENANCE, state=SC.RELEASED, ceremony=epoch_change, predecessor=B.S2,
                      successor=B.S2, witness=recovered.head.digest)
        result = recovered.readiness(FULL, holds=(hold,))
        self.assertEqual(check(result, "CEREMONY_HOLD").reason, "HOLD_MISSING")
        self.assertEqual(result.facts["governingCeremony"]["kind"], SC.KEY_COMPROMISE_RECOVERY)

    def test_registry_authorization_is_still_independently_required(self):
        s = self.maintained()
        s.storage.drop(WR.AUTHORIZATION_DIRECTORY, WR.retained_authorization_name(self.AUTH))
        result = s.readiness(FULL, holds=(rotated_released(s), self.maint(s, state=SC.RELEASED)))
        self.assertFalse(result.ready)
        self.assertEqual(check(result, "KEY_TRANSITION").reason, "HISTORY_WITNESS_NOT_CONSISTENT")
        self.assertEqual(check(result, "CEREMONY_HOLD").status, WR.NOT_EVALUATED)

    def test_maintenance_after_initial_custody(self):
        s = B.PrepBScenario()
        prior = RC.registry_head(s.registry)
        target = B.registry(2, [B.key(B.P0, version=1),
                                B.key(B.S5, version=2, created=B.T_CUT, revokedAt=B.T_CUT, revocationReason="ROUTINE")])
        s.publish(s.issue_head_advance(target, reason="ADMINISTRATIVE_REVOCATION", authorization_id="rhaa.admin-1"),
                  target)
        s.activate(B.P0)
        initial = B.initial_hold(state=SC.RELEASED, witness=s.digests["genesis"])
        self.assertEqual(reasons(s.readiness(FULL, key_id=B.P0, phase=WR.STEADY, holds=(initial,))),
                         {"CEREMONY_HOLD": "HOLD_MISSING"})
        ceremony = SC.registry_maintenance_ceremony_id(environment=B.ENV, current_key_id=B.P0, prior_head=prior,
                                                       target_head=RC.registry_head(target),
                                                       authorization_id="rhaa.admin-1")
        maint = B.hold(kind=SC.REGISTRY_MAINTENANCE, state=SC.RELEASED, ceremony=ceremony, predecessor=B.P0,
                       successor=B.P0, witness=s.head.digest)
        result = s.readiness(FULL, key_id=B.P0, phase=WR.STEADY, holds=(initial, maint))
        self.assertTrue(result.ready, result.reasons)
        self.assertEqual(result.facts["keyTransition"]["kind"], SC.INITIAL_CUSTODY)


# ------------------------------------- RR-32 other epoch reasons fail closed ---

class UnsupportedEpochReasonTests(unittest.TestCase):
    def advanced(self, reason: str) -> B.PrepBScenario:
        s = B.PrepBScenario()
        target = B.registry(2, [B.key(B.P0, version=1, retiredAt=B.T_REC),
                                B.key(B.S2, version=2, epoch=B.EN, created=B.T_REC)], epoch=B.EN)
        authorization = s.issue_epoch_advance(target, reason=reason, authorization_id="eaa.prep-b-" + reason.lower())
        s.adopt(authorization, target)
        s.execute_epoch_advance(authorization, target)
        s.quarantine()
        return s

    def test_every_other_reason_is_unsupported_for_every_hold_kind(self):
        for reason in sorted(RC.EPOCH_ADVANCE_REASONS - {SR.KEY_COMPROMISE}):
            s = self.advanced(reason)
            head = s.head.digest
            candidates = {
                SC.ROTATION: B.hold(state=SC.RELEASED, witness=head),
                SC.KEY_COMPROMISE_RECOVERY: B.hold(kind=SC.KEY_COMPROMISE_RECOVERY, state=SC.RELEASED, witness=head),
                SC.INITIAL_CUSTODY: B.initial_hold(state=SC.RELEASED, witness=head),
                SC.REGISTRY_MAINTENANCE: B.hold(kind=SC.REGISTRY_MAINTENANCE, state=SC.RELEASED, predecessor=B.S2,
                                                ceremony=SC.registry_maintenance_ceremony_id(
                                                    environment=B.ENV, current_key_id=B.S2,
                                                    prior_head=RC.registry_head(B.g1()),
                                                    target_head=s.head.registry_head,
                                                    authorization_id="eaa.prep-b-" + reason.lower()),
                                                witness=head),
            }
            for kind, value in candidates.items():
                with self.subTest(reason=reason, kind=kind):
                    result = s.readiness(FULL, holds=(value,))
                    self.assertFalse(result.ready)
                    self.assertEqual(check(result, "KEY_TRANSITION").reason, "EPOCH_ADVANCE_REASON_UNSUPPORTED")
                    self.assertEqual(check(result, "CEREMONY_HOLD").status, WR.NOT_EVALUATED)
            self.assertEqual(SR.derive_key_transition(s.history(), profile=B.PROFILE)[1:],
                             ("EPOCH_ADVANCE_REASON_UNSUPPORTED", reason))
        for name in ("EPOCH_ADVANCE", "RECOVERY", "ROUTINE_ROTATION"):
            self.assertNotIn(name, SC.TRANSITION_KINDS)


# ------------------------------------------------ environment isolation ---

class EnvironmentIsolationTests(unittest.TestCase):
    DEV = SC.DEV_SYNTHETIC_CUSTODY_PROFILE

    def test_no_environment_is_mapped_onto_another(self):
        for module in (SC, SR):
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertNotIn('"test"', source, module.__name__)
            self.assertNotIn("'test'", source, module.__name__)
        self.assertEqual(SC.custody_profile("dev"), self.DEV)
        self.assertEqual(B.PROFILE.environment, "test")
        with self.assertRaises(Exception):
            SC.custody_profile("prod")
        self.assertFalse(SC.is_dev_synthetic(dataclasses.replace(self.DEV, environment="staging")))

    def test_hold_records_bind_the_exact_expected_environment(self):
        test_hold = B.hold(witness="a" * 64)
        self.assertIsNotNone(SC.parse_ceremony_hold(test_hold, profile=B.PROFILE)[0])        # TEST accepts test
        self.assertEqual(SC.parse_ceremony_hold(test_hold, profile=self.DEV)[1], "HOLD_ENVIRONMENT_MISMATCH")
        dev_hold = {**test_hold, "environment": "dev"}
        self.assertIsNotNone(SC.parse_ceremony_hold(dev_hold, profile=self.DEV)[0])
        self.assertEqual(SC.parse_ceremony_hold(dev_hold, profile=B.PROFILE)[1], "HOLD_ENVIRONMENT_MISMATCH")
        self.assertNotEqual(SC.initial_ceremony_id("dev", SC.INITIAL_KEY_ID), B.INITIAL_CEREMONY)
        dev_initial = {**B.initial_hold(witness="a" * 64), "environment": "dev"}
        self.assertEqual(SC.parse_ceremony_hold(dev_initial, profile=self.DEV)[1], "HOLD_INITIAL_CEREMONY_MISMATCH")
        self.assertEqual(SC.parse_hold_store(SC.hold_store(test_hold), profile=self.DEV)[1],
                         "HOLD_ENVIRONMENT_MISMATCH")

    def test_records_and_readiness_are_environment_exact(self):
        record = B.ceremony_record()
        publication = B.publication_bytes(B.S2)
        self.assertTrue(SC.verify_successor_ceremony_record(record=record, publication_bytes=publication,
                                                            reviewed_release_sha=B.RELEASE_SHA,
                                                            profile=B.PROFILE).verified)
        self.assertEqual(SC.verify_successor_ceremony_record(record=record, publication_bytes=publication,
                                                             reviewed_release_sha=B.RELEASE_SHA,
                                                             profile=self.DEV).reason, "PUBLICATION_PROFILE_MISMATCH")
        self.assertEqual(SC.check_ordinal_unburned(B.ceremony_register(record), 3, profile=self.DEV).reason,
                         "REGISTER_ENVIRONMENT_MISMATCH")
        s = B.rotated()
        inputs = dataclasses.replace(s.readiness_inputs(hold_value=rotated_released(s)), profile=self.DEV)
        result = SR.evaluate_successor_readiness(inputs, mode=FULL)
        self.assertFalse(result.ready)
        self.assertEqual(check(result, "CEREMONY_HOLD").reason, "PROFILE_NOT_DEV_SYNTHETIC")
        gate = s.gate(SR.ADVANCE_EPOCH, kcr_hold(s), profile=self.DEV)
        self.assertEqual(gate.reason, "PROFILE_NOT_DEV_SYNTHETIC")
        custody = SR.authorize_custody_step(step=SC.VACATE, custody=B.custody(current=B.BLOB[B.P0],
                                                                                prepared=B.BLOB[B.S2]),
                                            ceremony=B.ceremony(), hold=B.hold(witness=s.digests["holdEngaged"]),
                                            store=s.context(), witness_store=s.observation(),
                                            head_registries=tuple(s.registries), profile=self.DEV)
        self.assertEqual(custody.reason, "PROFILE_NOT_DEV_SYNTHETIC")


if __name__ == "__main__":
    unittest.main()
