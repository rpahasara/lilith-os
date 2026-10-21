"""Identity V1 draft (TEST-only): identity profile, golden vectors and First Memory identity binding (FM-07 / ID-02).

Synthetic fixtures only; no real LILITH identity is created.

- GoldenVectorTests: profile and charter digests (independently recomputed).
- ComparisonOnlyTests: the private binding comparator. COMPARISON ONLY: these prove the comparison rules, not
  that any memory is identity-bound.
- GenuineV2Tests: the public entry point composed with REAL V2 verification of a synthetic L04 admission. These are
  the established integration behaviours: every path fails closed. A positive end-to-end binding is deferred to
  FM-02, because no existing memory class can carry a binding inside its admitted value.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import unittest
from pathlib import Path

import rfc8785

import synthetic_b1b3b as T  # puts the core-api package on sys.path
import synthetic_identity as SI
from lilith_memory import learning_v2  # noqa: E402
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import identity_profile as IP

GOLDEN = json.loads((Path(__file__).resolve().parent / "identity_profile_v1_golden.json").read_text(encoding="utf-8"))


def compare(binding, ctx=None):
    """Reason from the private comparator, or None when the binding equals the trusted profile (comparison only)."""
    try:
        IP._compare_binding(binding, ctx or SI.context())
    except IP._Reject as rejected:
        return rejected.reason
    return None


class GoldenVectorTests(unittest.TestCase):
    def test_charter_and_profile_digests_match_the_golden_vectors(self):
        p = SI.profile()
        self.assertEqual(IP.charter_digest(SI.SYNTHETIC_CHARTER_BYTES), GOLDEN["charterDigest"])
        self.assertEqual(p.canonical_bytes().decode("utf-8"), GOLDEN["profileCanonical"])
        self.assertEqual(p.digest(), GOLDEN["profileDigest"])
        self.assertEqual(p.binding(), GOLDEN["binding"])
        self.assertEqual(SI.SYNTHETIC_IDENTITY_ID, GOLDEN["lilithIdentityId"])

    def test_independent_recomputation_with_hashlib_and_rfc8785(self):
        charter = hashlib.sha256(b"LILITH_IDENTITY_CHARTER_V1\x00" + SI.SYNTHETIC_CHARTER_BYTES).hexdigest()
        fields = {"protocol": "lilith.identity.profile", "schemaVersion": 1, "environment": "test",
                  "lilithIdentityId": SI.SYNTHETIC_IDENTITY_ID,
                  "charter": {"charterVersion": SI.SYNTHETIC_CHARTER_VERSION, "charterDigest": charter}}
        profile = hashlib.sha256(b"LILITH_IDENTITY_PROFILE_V1\x00" + rfc8785.dumps(fields)).hexdigest()
        self.assertEqual((charter, profile), (GOLDEN["charterDigest"], GOLDEN["profileDigest"]))

    def test_any_change_changes_the_digest(self):
        base = SI.profile().digest()
        self.assertNotEqual(IP.charter_digest(SI.SYNTHETIC_CHARTER_BYTES + b" "), GOLDEN["charterDigest"])
        for override in ({"environment": "dev"}, {"charter_version": "1.0.1-test"},
                         {"charter_digest": "0" * 64}, {"lilith_identity_id": "lid1." + "0" * 32}):
            with self.subTest(override=override):
                self.assertNotEqual(SI.profile(**override).digest(), base)

    def test_profile_fields_are_validated(self):
        for override in ({"environment": "staging"}, {"lilith_identity_id": "LID1." + "a" * 32},
                         {"lilith_identity_id": "lid1." + "a" * 31}, {"charter_version": "v1"},
                         {"charter_digest": "A" * 64}):
            with self.subTest(override=override), self.assertRaises(IP.IdentityContractViolation):
                SI.profile(**override)


class ComparisonOnlyTests(unittest.TestCase):
    """COMPARISON ONLY. The private comparator, without admission. Not end-to-end identity-binding acceptance."""

    def test_exact_binding_compares_equal(self):
        self.assertIsNone(compare(SI.profile().binding()))

    def test_missing_binding_and_identity_cues_never_substitute(self):
        self.assertEqual(compare(None), "IDENTITY_BINDING_MISSING")
        for cue in ("I am LILITH", SI.SOUL_DIGEST, SI.MODEL, SI.HOST, {"selfReport": "I am LILITH"}, []):
            with self.subTest(cue=cue):
                self.assertEqual(compare(cue), "IDENTITY_BINDING_MALFORMED")

    def test_malformed_bindings_are_refused(self):
        good = SI.profile().binding()
        for binding in ({**good, "soulDigest": SI.SOUL_DIGEST}, {k: v for k, v in good.items() if k != "charterDigest"},
                        {**good, "lilithIdentityId": 1}):
            with self.subTest(binding=binding):
                self.assertEqual(compare(binding), "IDENTITY_BINDING_MALFORMED")

    def test_owner_authority_host_model_and_soul_cues_are_not_identity_ids(self):
        good = SI.profile().binding()
        for cue in (SI.OWNER_ID, "owner.synthetic.v1", "test-only.registry-root-1", SI.WITNESS_GENESIS,
                    SI.REGISTER_HEAD, SI.SOUL_DIGEST, SI.HOST, SI.MODEL, SI.RUNTIME, str(SI.SA.EPOCH.counter)):
            with self.subTest(cue=cue):
                self.assertEqual(compare({**good, "lilithIdentityId": cue}), "IDENTITY_ID_INVALID")

    def test_known_value_collisions_are_refused_but_prove_no_independence(self):
        good = SI.profile().binding()
        for known in (SI.WITNESS_GENESIS, SI.REGISTER_HEAD, SI.SOUL_DIGEST, SI.SA.EPOCH.random):
            with self.subTest(known=known[:12]):
                self.assertEqual(compare({**good, "lilithIdentityId": "lid1." + known[:32]}),
                                 "IDENTITY_ID_KNOWN_VALUE_COLLISION")
        # A short or non-hex known value never collides spuriously.
        self.assertEqual(IP.known_value_collisions(SI.SYNTHETIC_IDENTITY_ID, {"1", "lid", SI.HOST, SI.MODEL}), [])
        # Not a proof of independent generation: an ID derived from the owner ID passes the collision check.
        derived = "lid1." + hashlib.sha256(SI.OWNER_ID.encode()).hexdigest()[:32]
        self.assertEqual(IP.known_value_collisions(derived, SI.KNOWN_VALUES), [])

    def test_altered_identity_profile_or_charter_is_refused(self):
        good = SI.profile().binding()
        cases = {
            "IDENTITY_BINDING_MISMATCH": [{**good, "lilithIdentityId": "lid1." + "b" * 32},
                                          {**good, "identityProfileDigest": "0" * 64}],
            "CHARTER_MISMATCH": [{**good, "charterDigest": IP.charter_digest(b"another charter")},
                                 {**good, "charterVersion": "1.0.1-test"}],
        }
        for reason, bindings in cases.items():
            for binding in bindings:
                with self.subTest(reason=reason, binding=binding):
                    self.assertEqual(compare(binding), reason)

    def test_environment_and_trusted_profile_collision(self):
        self.assertEqual(compare(SI.profile().binding(), SI.context(environment="dev")), "IDENTITY_ENVIRONMENT_MISMATCH")
        with self.assertRaises(IP.IdentityContractViolation):
            SI.context(known_values=SI.KNOWN_VALUES | {SI.SYNTHETIC_IDENTITY_ID})


class GenuineV2Tests(unittest.TestCase):
    """Established integration behaviour: the entry point runs REAL V2 verification of a synthetic L04 admission."""

    def setUp(self):
        self.flow = T.Flow()
        self.addCleanup(self.flow.l04.close)
        _action, self.proposal, self.proof, self.evidence = self.flow.create("SYNTH-IDENTITY", "identity.v1")
        self.assertEqual(self.flow.adapter.admit(self.flow.request(self.proposal, self.proof, self.evidence)).status,
                         T.AD.L04_ADMITTED)
        self.v2_inputs = self.flow.acceptance_kwargs(self.proof, self.evidence, self.proposal)
        read = self.flow.read()
        self.assertEqual(read.status, V2.ACCEPTED_MEMORY)
        self.admitted_value = read.row["normalized_value_json"]

    def bind(self, admitted_value, **replace):
        return IP.verify_identity_bound_memory_v1(admitted_value=admitted_value, identity_context=SI.context(),
                                                  **{**self.v2_inputs, **replace})

    def test_existing_class_admission_fails_closed_without_a_binding(self):
        before = self.flow.l04.counts()
        result = self.bind(self.admitted_value)
        self.assertEqual((result.status, result.reason), (IP.IDENTITY_NOT_BOUND, "IDENTITY_BINDING_MISSING"))
        self.assertIs(result.facts["authorizesAdmission"], False)
        self.assertIs(result.facts["truthClaim"], False)
        self.assertEqual(self.flow.l04.counts(), before)                          # nothing admitted or written
        self.assertEqual(V2.verify_accepted_memory_v2(**self.v2_inputs).status, V2.ACCEPTED_MEMORY)  # unchanged

    def test_a_caller_packet_cannot_stand_in_for_the_admitted_value(self):
        self.assertEqual(self.bind(SI.candidate_value()).reason, "ADMITTED_VALUE_MISMATCH")

    def test_an_edited_stored_value_is_refused(self):
        edited = json.loads(self.admitted_value)
        edited[IP.BINDING_FIELD] = SI.profile().binding()
        edited = json.dumps(edited, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        self.assertEqual(self.bind(edited).reason, "ADMITTED_VALUE_MISMATCH")
        self.assertEqual(self.bind(self.admitted_value + " ").reason, "ADMITTED_VALUE_MISMATCH")
        self.assertEqual(self.bind("é" + self.admitted_value).reason, "ADMITTED_VALUE_MISMATCH")

    def test_missing_admitted_value_is_refused(self):
        for value in (None, b"bytes", {"codename": "SYNTH-IDENTITY"}):
            with self.subTest(value=value):
                self.assertEqual(self.bind(value).reason, "ADMITTED_VALUE_UNAVAILABLE")

    def test_failed_v2_verification_cannot_be_rescued_by_any_value(self):
        for replace in ({"link": None}, {"evidence_use": None}, {"admission": None}):
            with self.subTest(replace=sorted(replace)):
                result = self.bind(SI.candidate_value(), **replace)
                self.assertEqual((result.status, result.reason), (IP.IDENTITY_NOT_BOUND, "ACCEPTED_MEMORY_REQUIRED"))
                self.assertIsNotNone(result.detail)                          # the genuine V2 refusal reason

    def test_a_forged_v2_result_cannot_be_supplied(self):
        self.assertNotIn("accepted", inspect.signature(IP.verify_identity_bound_memory_v1).parameters)
        forged = V2.V2ResultV1(V2.ACCEPTED_MEMORY, None, None, {"truthClaim": False, "payloadDigest": "0" * 64})
        with self.assertRaises(TypeError):
            self.bind(self.admitted_value, accepted=forged)

    def test_no_existing_class_can_carry_a_binding_so_positive_end_to_end_is_deferred_to_fm02(self):
        with self.assertRaises(learning_v2.LearningV2Error):
            learning_v2.normalize_project_codename({"codename": "SYNTH-IDENTITY",
                                                    IP.BINDING_FIELD: SI.profile().binding()})


class PurityTests(unittest.TestCase):
    def test_module_is_pure_and_has_no_independent_payload_rule(self):
        source = inspect.getsource(IP)
        for forbidden in ("sqlite3", "open(", "socket", "subprocess", "os.environ", "canonical_store",
                          "l04_v2_adapter", "lilith_authority_signer", "lilith_memory_broker", "urllib", "requests",
                          "packet_payload_digest"):
            self.assertNotIn(forbidden, source, forbidden)


if __name__ == "__main__":
    unittest.main()
