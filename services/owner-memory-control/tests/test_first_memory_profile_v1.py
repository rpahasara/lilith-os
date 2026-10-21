"""FM-02 First Memory semantic profile (TEST-only draft): `OWNER_DIRECTED_FIRST_INTERACTION`.

Synthetic fixtures only; no real conversation, identity or memory exists or is admitted.

- NormalizationTests: determinism, the existing L04 encoding (ASCII canonical JSON, ASCII SHA-256), Unicode safety.
- EvidenceTests: exact transcript digest, event time and verbatim quotations; tampering and altered dialogue fail.
- ClaimTests: no accepted status, truth certification, authority, firstness or admission time in the value.
- IdentityTests: the binding inside the value, compared with the trusted Identity V1 profile. COMPARISON ONLY.
- GenuineChainTests: the unchanged L04 V2 / V2 verifier / Identity V1 chain refuses this class today, so no positive
  end-to-end admission or identity binding exists without the accepted-contract change in the FM-02 report.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import unittest

import synthetic_b1b3b as T  # puts the core-api package on sys.path
import synthetic_first_memory as SF
import synthetic_identity as SI
from lilith_memory import canonical_contracts as C
from lilith_memory import learning_v2
from lilith_memory import memory_v2
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import first_memory_profile as FM
from lilith_owner_memory import identity_profile as IP

# Golden payloadDigest of the synthetic fixture value (guards silent encoding drift).
GOLDEN_PAYLOAD_DIGEST = "76e433fe8ba27e6ff6d728f3dea9d2d2c2a75f01f84deefd67116c00cefc55c6"


def reason(fn, *args):
    try:
        fn(*args)
    except FM.FirstMemoryContractViolation as exc:
        return str(exc)
    return None


def normalize_reason(value):
    return reason(FM.normalize_first_interaction_episode, value)


def evidence_reason(canonical, evidence=None):
    return reason(FM.verify_episode_evidence, canonical, SF.transcript_bytes() if evidence is None else evidence)


class NormalizationTests(unittest.TestCase):
    def test_class_tuple_fits_the_existing_l04_identifier_rules(self):
        C.FrozenMemoryActionV1(schema_version=1, actor_ref_id="actor.local-owner.v1", operation=C.CREATE,
                               memory_class=FM.MEMORY_CLASS, subject_namespace=FM.SUBJECT_NAMESPACE,
                               subject_key=FM.SUBJECT_KEY, value_schema=FM.VALUE_SCHEMA, payload_digest="0" * 64,
                               expected_active_revision_id=None, restore_revision_id=None,
                               purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL).validate()

    def test_deterministic_and_idempotent_under_the_existing_l04_encoding(self):
        canonical, digest = FM.normalize_first_interaction_episode(SF.value())
        reordered = dict(reversed(list(SF.value().items())))
        reordered["quotations"] = list(reversed(reordered["quotations"]))
        self.assertEqual(FM.normalize_first_interaction_episode(reordered), (canonical, digest))
        self.assertEqual(FM.normalize_first_interaction_episode(json.loads(canonical)), (canonical, digest))
        self.assertEqual(canonical, C.canonical_json(json.loads(canonical)))        # the L04 canonical form
        self.assertEqual(digest, hashlib.sha256(canonical.encode("ascii")).hexdigest())  # the L04 payload rule
        self.assertTrue(canonical.isascii())
        self.assertEqual(digest, GOLDEN_PAYLOAD_DIGEST)

    def test_unicode_dialogue_round_trips_exactly(self):
        canonical = SF.canonical()
        texts = [q["text"] for q in json.loads(canonical)["quotations"]]
        self.assertEqual(texts, [SF.OPENING_OWNER, SF.OPENING_LILITH, SF.CLOSING_LILITH, SF.CLOSING_OWNER])
        self.assertIn("\\u200d", canonical)                                          # ZWJ kept, escaped
        self.assertIn("\\ufe0f", canonical)                                          # variation selector kept
        self.assertIn("\\ud83d\\ude0a", canonical)                                   # non-BMP as an escape pair

    def test_evidence_is_preserved_exactly_whatever_its_language(self):
        """No language rule here: English-only replies are a runtime conversation policy, not a memory rule."""
        turns = list(SF.TURNS)
        turns[2] = (FM.OWNER, turns[2][1], "TEST_ONLY bonjour \u2014 \u3053\u3093\u306b\u3061\u306f \u0393\u03b5\u03b9\u03ac")
        evidence = SF.transcript_bytes(turns=turns)
        text = turns[2][2]
        quotes = [SF.quotation(FM.OPENING, 0), dict(SF.quotation(FM.OPENING, 1)),
                  {"position": FM.OPENING, "turnIndex": 2, "speaker": FM.OWNER, "start": 0, "end": len(text),
                   "text": text}, SF.quotation(FM.CLOSING, 4)]
        canonical = SF.canonical(evidence=evidence, quotations=quotes)
        self.assertIsNone(evidence_reason(canonical, evidence))
        self.assertEqual(json.loads(canonical)["quotations"][2]["text"], text)

    def test_text_is_refused_never_repaired(self):
        cases = {
            "e\u0301 decomposed": "TEXT_NOT_NFC",
            "bidi \u202e override": "TEXT_PROHIBITED_CHARACTER",
            "isolate \u2066x\u2069": "TEXT_PROHIBITED_CHARACTER",
            "carriage\rreturn": "TEXT_PROHIBITED_CHARACTER",
            "nul\x00": "TEXT_PROHIBITED_CHARACTER",
            "line\u2028sep": "TEXT_PROHIBITED_CHARACTER",
            "lone \ud800": "TEXT_PROHIBITED_CHARACTER",
            "private \ue000": "TEXT_PROHIBITED_CHARACTER",
            "unassigned \u0378": "TEXT_PROHIBITED_CHARACTER",
            "tag \U000e0041": "TEXT_PROHIBITED_CHARACTER",
        }
        for text, expected in cases.items():
            with self.subTest(text=ascii(text)):
                quotes = [SF.quotation(FM.OPENING, 0, end=len(text), text=text), SF.quotation(FM.CLOSING, 4)]
                self.assertEqual(normalize_reason(SF.value(quotations=quotes)), expected)
        padded = " " + SF.OPENING_OWNER
        quotes = [SF.quotation(FM.OPENING, 0, end=len(padded), text=padded), SF.quotation(FM.CLOSING, 4)]
        canonical = FM.normalize_first_interaction_episode(SF.value(quotations=quotes))[0]
        self.assertEqual(json.loads(canonical)["quotations"][0]["text"], padded)       # whitespace not trimmed

    def test_structure_is_closed(self):
        v = SF.value()
        cases = [
            (dict(v, schemaVersion=True), "VALUE_SCHEMA_UNSUPPORTED"),
            (dict(v, valueSchema="HomelabCodenameV1"), "VALUE_SCHEMA_UNSUPPORTED"),
            (dict(v, truthBasis="USER_ASSERTED"), "TRUTH_BASIS_UNSUPPORTED"),
            (dict(v, access={"consumerScope": "ANY_CONSUMER"}), "ACCESS_UNSUPPORTED"),
            (dict(v, retention={"mode": "FOREVER", "erasureAuthority": C.PRIVACY_GOVERNANCE_AUTHORITY_V1}),
             "RETENTION_UNSUPPORTED"),
            (dict(v, eventTime={"startedAt": "2026-11-01T18:00:00+05:30", "endedAt": v["eventTime"]["endedAt"]}),
             "EVENT_TIME_MALFORMED"),
            (dict(v, eventTime={"startedAt": "2026-11-01T18:00:00.5Z", "endedAt": "2026-11-01T18:00:00.25Z"}),
             "EVENT_TIME_ORDER_INVALID"),
            (dict(v, transcript=dict(v["transcript"], turnCount=1)), "TRANSCRIPT_REF_MALFORMED"),
            (dict(v, transcript=dict(v["transcript"], sha256="A" * 64)), "TRANSCRIPT_REF_MALFORMED"),
            (dict(v, quotations=v["quotations"][:1]), "QUOTATIONS_MALFORMED"),
            (dict(v, quotations=[SF.quotation(FM.OPENING, 0), SF.quotation(FM.OPENING, 1)]), "QUOTATION_ORDER_INVALID"),
            (dict(v, quotations=[SF.quotation(FM.CLOSING, 0), SF.quotation(FM.OPENING, 4)]), "QUOTATION_ORDER_INVALID"),
            (dict(v, quotations=[SF.quotation(FM.OPENING, 0), SF.quotation(FM.OPENING, 0), SF.quotation(FM.CLOSING, 4)]),
             "QUOTATION_DUPLICATE"),
            (dict(v, quotations=[SF.quotation(FM.OPENING, 0, end=3), dict(SF.quotation(FM.CLOSING, 4), turnIndex=5)]),
             "QUOTATION_MALFORMED"),                                                   # beyond turnCount
            (dict(v, quotations=[SF.quotation(FM.OPENING, 0), dict(SF.quotation(FM.CLOSING, 4), start=False)]),
             "QUOTATION_MALFORMED"),
            (dict(v, quotations=[dict(SF.quotation(FM.OPENING, 0), end=1), SF.quotation(FM.CLOSING, 4)]),
             "QUOTATION_OFFSETS_INVALID"),
            (dict(v, quotations=[dict(SF.quotation(FM.OPENING, 0), speaker="SYSTEM"), SF.quotation(FM.CLOSING, 4)]),
             "QUOTATION_MALFORMED"),
        ]
        for bad, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(normalize_reason(bad), expected)
        missing = dict(v)
        del missing["transcript"]
        self.assertEqual(normalize_reason(missing), "VALUE_FIELDS_INVALID")


class EvidenceTests(unittest.TestCase):
    def test_the_exact_transcript_supports_the_value(self):
        facts = FM.verify_episode_evidence(SF.canonical(), SF.transcript_bytes())
        self.assertEqual(facts["payloadDigest"], FM.normalize_first_interaction_episode(SF.value())[1])
        self.assertIs(facts["truthClaim"], False)
        self.assertIs(facts["authorizesAdmission"], False)

    def test_awkward_reply_is_kept_and_a_corrected_one_is_refused(self):
        self.assertIn("moring", json.loads(SF.canonical())["quotations"][1]["text"])
        corrected = SF.OPENING_LILITH.replace("moring", "morning")
        quotes = [SF.quotation(FM.OPENING, 0), SF.quotation(FM.OPENING, 1, end=len(corrected), text=corrected),
                  SF.quotation(FM.CLOSING, 4)]
        self.assertEqual(evidence_reason(SF.canonical(quotations=quotes)), "QUOTATION_NOT_VERBATIM")

    def test_altered_dialogue_and_misattribution_are_refused(self):
        sub = SF.OPENING_LILITH[10:30]
        cases = [
            ([SF.quotation(FM.OPENING, 1, start=10, end=30, text=sub.upper()), SF.quotation(FM.CLOSING, 4)],
             "QUOTATION_NOT_VERBATIM"),
            ([SF.quotation(FM.OPENING, 1, start=11, end=31, text=sub), SF.quotation(FM.CLOSING, 4)],
             "QUOTATION_NOT_VERBATIM"),
            ([SF.quotation(FM.OPENING, 1, speaker=FM.OWNER), SF.quotation(FM.CLOSING, 4)],     # LILITH's words
             "QUOTATION_SPEAKER_MISMATCH"),                                                    # given to the owner
        ]
        for quotes, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(evidence_reason(SF.canonical(quotations=quotes)), expected)
        exact = [SF.quotation(FM.OPENING, 1, start=10, end=30), SF.quotation(FM.CLOSING, 4)]
        self.assertIsNone(evidence_reason(SF.canonical(quotations=exact)))                # exact excerpt is fine

    def test_tampered_or_missing_transcript_is_refused(self):
        canonical = SF.canonical()
        evidence = SF.transcript_bytes()
        self.assertEqual(evidence_reason(canonical, b""), "TRANSCRIPT_DIGEST_MISMATCH")
        self.assertEqual(reason(FM.verify_episode_evidence, canonical, None), "TRANSCRIPT_DIGEST_MISMATCH")
        self.assertEqual(evidence_reason(canonical, evidence + b"\n"), "TRANSCRIPT_DIGEST_MISMATCH")
        edited = evidence.replace("moring".encode(), "morning".encode())
        self.assertEqual(evidence_reason(canonical, edited), "TRANSCRIPT_DIGEST_MISMATCH")
        # Even a value re-pointed at an edited transcript cannot quote words that were not said.
        self.assertEqual(evidence_reason(SF.canonical(evidence=edited), edited), "QUOTATION_NOT_VERBATIM")

    def test_event_time_and_turn_count_must_match_the_transcript(self):
        v = SF.value()
        late = SF.canonical(eventTime={"startedAt": "2026-11-01T18:00:01Z", "endedAt": v["eventTime"]["endedAt"]})
        self.assertEqual(evidence_reason(late), "EVENT_TIME_MISMATCH")
        self.assertEqual(evidence_reason(SF.canonical(transcript=dict(v["transcript"], turnCount=6))),
                         "TURN_COUNT_MISMATCH")

    def test_malformed_transcript_evidence_is_refused(self):
        turns = list(SF.TURNS)
        bad = {
            "duplicate key": SF.transcript_bytes()[:-2] + b', "schema": "x"}',
            "out of order": SF.transcript_bytes(turns=[turns[1], turns[0], *turns[2:]]),
            "unknown speaker": SF.transcript_bytes(turns=[("SYSTEM", *turns[0][1:]), *turns[1:]]),
            "owner only": SF.transcript_bytes(turns=[(FM.OWNER, *t[1:]) for t in turns]),
            "not utf-8": b"\xff" + SF.transcript_bytes(),
        }
        for label, evidence in bad.items():
            with self.subTest(label=label):
                got = evidence_reason(SF.canonical(evidence=evidence), evidence)
                self.assertIn(got, {"TRANSCRIPT_MALFORMED", "TRANSCRIPT_NOT_OWNER_LILITH_DIALOGUE"})

    def test_a_non_canonical_value_string_is_refused(self):
        canonical = SF.canonical()
        self.assertEqual(evidence_reason(canonical + " "), "VALUE_NOT_CANONICAL")
        self.assertEqual(evidence_reason(json.dumps(json.loads(canonical), ensure_ascii=False, sort_keys=True,
                                                    separators=(",", ":"))), "VALUE_NOT_CANONICAL")


class ClaimTests(unittest.TestCase):
    def test_no_status_truth_authority_firstness_or_admission_time_can_be_written(self):
        for key, val in (("status", "ACCEPTED"), ("accepted", True), ("truthCertified", True),
                         ("authority", "OWNER"), ("isFirst", True), ("firstness", 1), ("admittedAt", "2026-11-01T18:03:00Z"),
                         ("ownerOrigin", "statement"), ("genesis", "evidence"), ("payloadDigest", "0" * 64)):
            with self.subTest(key=key):
                self.assertEqual(normalize_reason(SF.value(**{key: val})), "VALUE_FIELDS_INVALID")
        quote = dict(SF.quotation(FM.OPENING, 0), verified=True)
        self.assertEqual(normalize_reason(SF.value(quotations=[quote, SF.quotation(FM.CLOSING, 4)])),
                         "QUOTATION_MALFORMED")

    def test_module_is_pure_and_admits_nothing(self):
        source = inspect.getsource(FM)
        for forbidden in ("sqlite3", "open(", "socket", "subprocess", "os.environ", "canonical_store",
                          "l04_v2_adapter", "lilith_authority_signer", "lilith_memory_broker", "urllib", "requests",
                          "def admit", "ACCEPTED_MEMORY", "rfc8785", "sign("):
            self.assertNotIn(forbidden, source, forbidden)


class IdentityTests(unittest.TestCase):
    """COMPARISON ONLY: the binding inside the canonical value against the trusted profile. Not identity-bound memory."""

    def compare(self, canonical, ctx=None):
        try:
            IP._compare_binding(json.loads(canonical)[IP.BINDING_FIELD], ctx or SI.context())
        except IP._Reject as rejected:
            return rejected.reason
        return None

    def test_binding_lives_inside_the_admitted_value_and_matches_the_trusted_profile(self):
        canonical = SF.canonical()
        self.assertEqual(json.loads(canonical)[IP.BINDING_FIELD], SI.profile().binding())
        self.assertIsNone(self.compare(canonical))

    def test_incorrect_identity_is_refused(self):
        other = SI.profile(lilith_identity_id="lid1." + "0" * 31 + "1").binding()
        self.assertEqual(self.compare(SF.canonical(identityBinding=other)), "IDENTITY_BINDING_MISMATCH")
        wrong_charter = SI.profile(charter_digest="f" * 64).binding()
        self.assertEqual(self.compare(SF.canonical(identityBinding=wrong_charter)), "CHARTER_MISMATCH")
        dev = SI.context(environment="dev")
        self.assertEqual(self.compare(SF.canonical(), dev), "IDENTITY_ENVIRONMENT_MISMATCH")

    def test_malformed_or_missing_binding_never_normalizes(self):
        good = SI.profile().binding()
        for bad in (None, {}, dict(good, extra="x"), dict(good, lilithIdentityId="lid1.XYZ"),
                    dict(good, identityProfileDigest="0" * 63), {k: v for k, v in good.items() if k != "charterDigest"}):
            with self.subTest(bad=bad):
                self.assertEqual(normalize_reason(SF.value(identityBinding=bad)), "IDENTITY_BINDING_MALFORMED")


class GenuineChainTests(unittest.TestCase):
    """The unchanged chain, exercised as is. Every path refuses FM-02 today."""

    def test_l04_value_normalizer_refuses_the_fm02_value(self):
        with self.assertRaises(learning_v2.LearningV2Error):
            learning_v2.normalize_project_codename(json.loads(SF.canonical()))
        self.assertEqual(learning_v2.VALUE_SCHEMA, "HomelabCodenameV1")
        self.assertEqual(learning_v2.V2_PROPOSAL_FAMILY, "OWNER_DIRECTED_PROJECT_CODENAME_V1")

    def test_l04_has_no_autobiographical_purpose_or_capability(self):
        self.assertEqual(C.VALID_PURPOSES, frozenset({C.LONG_TERM_PERSONAL_PROJECT_RECALL}))
        with self.assertRaises(ValueError):
            memory_v2.CanonicalTupleRegistry([memory_v2.MemoryTuplePolicyV1(
                FM.MEMORY_CLASS, FM.SUBJECT_NAMESPACE, FM.SUBJECT_KEY, FM.VALUE_SCHEMA,
                "canonical_memory.autobiographical_episode.create", True, True)])

    def test_fm02_value_cannot_stand_in_for_a_genuinely_accepted_memory(self):
        flow = T.Flow()
        self.addCleanup(flow.l04.close)
        _action, proposal, proof, evidence = flow.create("SYNTH-FM02", "fm02.v1")
        self.assertEqual(flow.adapter.admit(flow.request(proposal, proof, evidence)).status, T.AD.L04_ADMITTED)
        v2_inputs = flow.acceptance_kwargs(proof, evidence, proposal)
        self.assertEqual(V2.verify_accepted_memory_v2(**v2_inputs).status, V2.ACCEPTED_MEMORY)
        before = flow.l04.counts()
        result = IP.verify_identity_bound_memory_v1(admitted_value=SF.canonical(), identity_context=SI.context(),
                                                    **v2_inputs)
        self.assertEqual((result.status, result.reason), (IP.IDENTITY_NOT_BOUND, "ADMITTED_VALUE_MISMATCH"))
        self.assertIs(result.facts["authorizesAdmission"], False)
        self.assertEqual(flow.l04.counts(), before)

    def test_the_value_already_meets_the_identity_v1_admitted_value_rule(self):
        """What Identity V1 would check after a genuine admission: ASCII bytes hash to the payloadDigest and the
        parsed value carries `identityBinding`. Shown on the canonical value only, NOT end-to-end."""
        canonical, digest = FM.normalize_first_interaction_episode(SF.value())
        self.assertEqual(hashlib.sha256(canonical.encode("ascii")).hexdigest(), digest)
        self.assertIn(IP.BINDING_FIELD, json.loads(canonical))


if __name__ == "__main__":
    unittest.main()
