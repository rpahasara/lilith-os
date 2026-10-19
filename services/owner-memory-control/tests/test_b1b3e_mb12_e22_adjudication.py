"""15B2b-B1b-3e M-B12: the E-22 owner risk adjudication (OD-M12-10), control-side admission and release judge.

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb2-proof-producers.md §17.
The REAL adjudication object, its pins and the release constants are checked for consistency. The admission and the
judge are exercised with TEST_ONLY adjudications built the same way from the real producer, the real ceremony table
and the genuine journal FAIL restatement; raw owner evidence is never in this repository. Nothing contacts DEV.
"""

from __future__ import annotations

import base64
import contextlib
import copy
import dataclasses
import hashlib
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
for _path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", Path(__file__).resolve().parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import test_b1b3e_mb12_prb2_proof_producers as P2  # noqa: E402
from test_b1b3e_mb12_prb2_proof_producers import PA, PS, RI, SH, T1  # noqa: E402,F401

from lilith_owner_memory import successor_custody as SC  # noqa: E402

H = T1.H
HYGIENE = RI.SECRET_HYGIENE_SCOPE.split(":")[0]
SESSIONS = (("3837", 1790493545688402), ("3845", 1790493771742151), ("3850", 1790493936317730))


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def attribution(*, verdict="UNKNOWN", session="3837", header_entries=713649) -> bytes:
    """A TEST_ONLY attribution transcript of the real form: 12 matches in boot 24d1771d, three sudo sessions."""
    lines = [f"JOURNAL: entries={header_entries} bytes=1 sha256={H('journal')} boots=3"]
    n = 0
    for name, at in SESSIONS:
        name = session if name == "3837" else name
        for field, offset in (("MESSAGE", 0), ("_CMDLINE", 0), ("_CMDLINE", 1), ("_CMDLINE", 2)):
            n += 1
            lines.append(f"MATCH: n={n} class=PEM_PRIVATE_KEY boot=24d1771de1b54e5f816dda08ad8b367a "
                         f"realtimeUs={at + offset} field={field} unit=session-{name}.scope identifier=sudo kind=TEXT "
                         f"role=OTHER verdict={verdict} inField=1")
    lines += ["COUNTS: class=PEM_PRIVATE_KEY stream=12 inField=12 boundary=0",
              "SUMMARY: COMPLETE_PEM_BLOCK=0 HEADER_OR_COMMAND_TEXT=0 UNKNOWN=12",
              "JOURNAL_MARKER_ATTRIBUTION=COMPLETE matches=12"]
    return ("\n".join(lines) + "\n").encode("ascii")


def journal_variant(*, count=12, last=1790672449937963) -> bytes:
    raw = P2.REAL_JOURNAL_FAIL.replace(b"count=12", f"count={count}".encode())
    return raw.replace(b"lastRealtimeUs=1790672449937963 entries=380255",
                       f"lastRealtimeUs={last} entries=380255".encode())


@contextlib.contextmanager
def proved(journal=P2.REAL_JOURNAL_FAIL, *, scope_case=None):
    """(transcript, scope bytes) of one real-table `prove` over TEST_ONLY items and the given journal transcript."""
    case = scope_case or P2.SecretScopeTests("test_the_real_scope_fails_closed_today")
    case.setUp()
    try:
        raw_scope = case.scope(ceremonies=SH.CEREMONIES, journal=journal,
                               no_transcript=tuple(SH.TRANSCRIPT_NOT_RETAINED))
        _ok, transcript = P2.capture(SH.prove, raw_scope, read=case.read)
        yield transcript, raw_scope
    finally:
        case.tearDown()


def body_sha(raw: bytes) -> str:
    lines = raw.decode("ascii")[:-1].split("\n")
    return hashlib.sha256("".join(line + "\n" for line in lines[1:-1]).encode("ascii")).hexdigest()


def test_adjudication(transcript: bytes, **changes):
    """A TEST_ONLY adjudication of the real form, approving this synthetic transcript body and attribution."""
    value = copy.deepcopy(dict(RI.E22_ADJUDICATION_V1))
    value["decision"] = "TEST_ONLY"
    value["approvedBodySha256"] = body_sha(transcript)
    lines = attribution().decode("ascii")[:-1].split("\n")
    value["attribution"] = {"bodySha256": hashlib.sha256("".join(line + "\n" for line in lines[1:]).encode()).hexdigest(),
                            "matches": 12}
    value.update(changes)
    return value


def item(adjudication_sha: str, scope: bytes, journal: bytes = P2.REAL_JOURNAL_FAIL, attr: bytes | None = None,
         **changes):
    value = {"adjudicationSha256": adjudication_sha, "scope": b64u(scope), "journalTranscript": b64u(journal),
             "attributionTranscript": b64u(attribution() if attr is None else attr),
             "observedAt": T1.T1, "evidenceSha256": H("e22 evidence")}
    value.update(changes)
    return value


class RealAdjudicationTests(unittest.TestCase):
    """The real OD-M12-10 object, both pins and the release constants agree; nothing is effective yet on DEV."""

    def test_object_digest_and_pins_agree(self):
        digest = RI.adjudication_digest(RI.E22_ADJUDICATION_V1)
        self.assertEqual(digest, RI.E22_ADJUDICATION_SHA256)
        self.assertEqual(dict(RI.DEV_ACCEPTED_E22_ADJUDICATIONS), dict(PA.ACCEPTED_E22_ADJUDICATIONS))
        self.assertEqual(list(PA.ACCEPTED_E22_ADJUDICATIONS), [digest])
        self.assertEqual(PA.ACCEPTED_E22_ADJUDICATIONS[digest],
                         "56e71df1b7bf5c599c7d3f09edd5b12a37cf642c63d715b2f823f2ff92242c5a")    # owner record

    def test_object_is_the_narrow_historical_scope(self):
        spec = RI.E22_ADJUDICATION_V1
        self.assertEqual(spec["failures"], list(P2.OD_M12_9_FAILURES))
        self.assertEqual(tuple(spec["failures"]), PA.E22_ADJUDICATED_FAILURES)
        self.assertEqual((spec["environment"], spec["custodyProfile"], spec["keyId"]),
                         ("dev", "DEV_SYNTHETIC", "test-only.dev-synthetic.actor.b1b3d.1"))
        self.assertEqual(spec["keyId"], SC.INITIAL_KEY_ID)
        self.assertEqual((PA.E22_ADJUDICATION_ENVIRONMENT, PA.E22_ADJUDICATION_KEY_ID), ("dev", SC.INITIAL_KEY_ID))
        self.assertEqual(spec["producerSha256"], RI.PRODUCER_SCRIPT_SHA256[HYGIENE])
        self.assertEqual(spec["journal"], {"bootLine": P2.REAL_JOURNAL_FAIL.decode().split("\n")[1],
                                           "markers": [["PEM_PRIVATE_KEY", 12]]})
        evidence = spec["evidence"]
        self.assertEqual(evidence["journalTranscriptSha256"], P2.REAL_JOURNAL_FAIL_SHA256)
        self.assertEqual((evidence["proofTranscriptSha256"], evidence["scopeSha256"], evidence["proofEvidenceSums"]),
                         ("46a3c6414e6cf52d73cef5a2d768d9dae11134dee359eba6a9edc4a778f774fc",
                          "cd073c96adfcddbe644c40b522239670ab37f622c73c18fb797940cbdf023feb",
                          "b355f75a2d93a4a46fec5fc9f425d9ae09a68ec9373b40d70515301484440788"))
        for text in ("JOURNAL_SECRET_SCAN=FAIL stands", "not a clean scan", "no other key"):
            self.assertTrue(any(text in claim for claim in spec["nonclaims"]), text)
        self.assertIn("NOT a clean scan", PA.E22_ADJUDICATION_NONCLAIM)

    def test_effective_on_dev_only_for_the_pinned_post_v7_fail(self):
        # After E-22 V7 the release judge is installed and exactly one SECRET_HYGIENE transcript is owner-pinned: the
        # post-V7 `prove` FAIL (record slice-15b2b-b1b3e-e22-completion.md §7). DEV trust stays non-overridable.
        self.assertEqual(RI.DEV_ACCEPTED_PROOF_TRANSCRIPTS["SECRET_HYGIENE"],
                         frozenset({"bb97c6a69a00911ffce554edf1f7e71cf6fd7c1b2b5ebcc1e7e0bb1ccd3081cc"}))
        self.assertEqual(dict(RI.DEV_ACCEPTED_E22_ADJUDICATIONS), {RI.E22_ADJUDICATION_SHA256:
                         "56e71df1b7bf5c599c7d3f09edd5b12a37cf642c63d715b2f823f2ff92242c5a"})
        with self.assertRaises(RI.Refused) as caught:
            RI.trust_for("dev", RI.ReadinessTrustV1({}, T1.T0, {}, None, None, {H("x"): H("y")}))
        self.assertEqual(caught.exception.reason, "DEV_TRUST_NOT_OVERRIDABLE")


@unittest.skipUnless(P2.POSIX, "the producer's journal forms import POSIX-only")
class AdmissionTests(unittest.TestCase):
    """Control side: only the exact approved failure evidence, under a merged (here TEST) owner pin."""

    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.transcript, self.scope = stack.enter_context(proved())
        self.spec = test_adjudication(self.transcript)
        self.sha = RI.adjudication_digest(self.spec)
        stack.enter_context(mock.patch.object(RI, "E22_ADJUDICATION_V1", self.spec))
        stack.enter_context(mock.patch.object(RI, "E22_ADJUDICATION_SHA256", self.sha))
        stack.enter_context(mock.patch.object(PA, "E22_ADJUDICATION_ENVIRONMENT", "test"))
        self.trust = RI.ReadinessTrustV1({}, T1.T0, {"SECRET_HYGIENE": frozenset({H_(self.transcript)})}, None, None,
                                         {self.sha: H("TEST owner record")})

    def admit(self, value=None, *, transcript=None, trust=None, environment="test", exit_code=1):
        transcript = self.transcript if transcript is None else transcript
        trust = trust or dataclasses.replace(
            self.trust, accepted_proof_transcripts={"SECRET_HYGIENE": frozenset({H_(transcript)})})
        proof_item = P2.item(transcript, exit_code)
        admitted = RI.admit_proof("SECRET_HYGIENE", proof_item, trust)
        return RI.admit_e22_adjudication(value or item(self.sha, self.scope), proof_item, admitted, trust,
                                         environment=environment)

    def refused(self, reason, *args, **kwargs):
        with self.assertRaises(RI.Refused) as caught:
            self.admit(*args, **kwargs)
        self.assertEqual(caught.exception.reason, reason, caught.exception.detail)

    def test_the_exact_evidence_is_admitted_and_stays_fail(self):
        self.assertTrue(self.transcript.endswith(f"SECRET_HYGIENE_PROOF=FAIL scope={H_(self.scope)}\n".encode()))
        self.assertEqual([line for line in self.transcript.decode().splitlines() if line.startswith("FAIL: ")],
                         list(P2.OD_M12_9_FAILURES))
        self.assertEqual(self.admit(), PA.E22_ADJUDICATION_DETAIL_PREFIX + self.sha)
        # A later attribution's header (journal totals) may differ; its matches may not.
        self.assertEqual(self.admit(item(self.sha, self.scope, attr=attribution(header_entries=999999))),
                         PA.E22_ADJUDICATION_DETAIL_PREFIX + self.sha)

    def test_four_matching_lines_alone_never_qualify(self):
        # Same four FAIL lines, a different item set: the approved body differs.
        case = P2.SecretScopeTests("test_the_real_scope_fails_closed_today")
        case.setUp()
        try:
            other_scope = case.scope(ceremonies=SH.CEREMONIES, no_transcript=("B1B3D-L2b",),
                                     journal=P2.REAL_JOURNAL_FAIL, leak=b" other bytes")
            _ok, other = P2.capture(SH.prove, other_scope, read=case.read)
        finally:
            case.tearDown()
        self.assertEqual([l for l in other.decode().splitlines() if l.startswith("FAIL: ")], list(P2.OD_M12_9_FAILURES))
        self.refused("E22_TRANSCRIPT_BODY_MISMATCH", item(self.sha, other_scope), transcript=other)

    def test_changed_transcript_digest_or_extra_failure_is_refused(self):
        extra = self.transcript.replace(b"FAIL: CEREMONY_WINDOW", b"FAIL: PRIVATE_MATERIAL_MARKER M-B1 TRANSCRIPT "
                                        b"class=PEM_PRIVATE_KEY count=1\nFAIL: CEREMONY_WINDOW", 1)
        self.refused("E22_FAILURE_SET_MISMATCH", transcript=extra)
        changed = self.transcript.replace(b"COVERED: M-B11", b"COVERED: M-B11 ", 1)
        with self.assertRaises(RI.Refused):
            self.admit(transcript=changed)                       # the producer contract or the body refuses it
        # The transcript the owner pinned under OD-M12-6 is not this one.
        stranger = dataclasses.replace(self.trust, accepted_proof_transcripts={"SECRET_HYGIENE": frozenset({H("x")})})
        self.refused("PROOF_PROVENANCE_NOT_ESTABLISHED", trust=stranger)

    def test_altered_journal_or_attribution_is_refused(self):
        self.refused("E22_ATTRIBUTION_MISMATCH", item(self.sha, self.scope, attr=attribution(verdict="LITERAL")))
        self.refused("E22_ATTRIBUTION_MISMATCH", item(self.sha, self.scope, attr=attribution(session="9999")))
        self.refused("E22_ATTRIBUTION_FORM", item(self.sha, self.scope, attr=b"MATCH: n=1\n"))
        self.refused("E22_JOURNAL_NOT_THE_SCOPE_JOURNAL", item(self.sha, self.scope, journal=journal_variant()
                                                               + b"\n"))
        self.refused("E22_SCOPE_NOT_THE_PROVED_SCOPE", item(self.sha, self.scope + b" "))
        # A journal whose boot 24d1771d interval changed (rotation, another boot) gives the same body: still refused.
        moved = journal_variant(last=1790672449937000)
        with proved(moved) as (transcript, scope):
            self.assertEqual(body_sha(transcript), body_sha(self.transcript))
            self.refused("E22_JOURNAL_BOOT_MISMATCH", item(self.sha, scope, journal=moved), transcript=transcript)
        # A thirteenth marker changes the FAIL set.
        with proved(journal_variant(count=13)) as (transcript, scope):
            self.refused("E22_FAILURE_SET_MISMATCH", item(self.sha, scope, journal=journal_variant(count=13)),
                         transcript=transcript)

    def test_missing_or_broader_owner_trust_and_malformed_input_are_refused(self):
        self.refused("E22_ADJUDICATION_NOT_ACCEPTED", trust=dataclasses.replace(
            self.trust, accepted_proof_transcripts={"SECRET_HYGIENE": frozenset({H_(self.transcript)})},
            accepted_e22_adjudications={}))
        self.refused("E22_ADJUDICATION_UNKNOWN", item(H("another adjudication"), self.scope))
        self.refused("INPUT_MALFORMED", {**item(self.sha, self.scope), "extra": 1})
        self.refused("INPUT_MALFORMED", item("not-hex", self.scope))
        missing = item(self.sha, self.scope)
        del missing["attributionTranscript"]
        self.refused("INPUT_MALFORMED", missing)
        with mock.patch.dict(RI.E22_ADJUDICATION_V1, {"producerSha256": H("another producer")}):
            sha = RI.adjudication_digest(RI.E22_ADJUDICATION_V1)
            with mock.patch.object(RI, "E22_ADJUDICATION_SHA256", sha):
                trust = dataclasses.replace(self.trust, accepted_e22_adjudications={sha: H("owner")})
                self.refused("E22_PRODUCER_CHANGED", item(sha, self.scope), trust=dataclasses.replace(
                    trust, accepted_proof_transcripts={"SECRET_HYGIENE": frozenset({H_(self.transcript)})}))

    def test_outside_dev_synthetic_is_refused(self):
        for environment in ("dev", "prod", "staging"):            # patched constant here is "test"
            with self.subTest(environment=environment):
                self.refused("E22_ADJUDICATION_OUT_OF_SCOPE", environment=environment)
        with mock.patch.object(PA, "E22_ADJUDICATION_ENVIRONMENT", "dev"):
            self.refused("E22_ADJUDICATION_OUT_OF_SCOPE", environment="test")


def H_(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def judge_inputs(*, environment="dev", detail="ADJ", result=PA.FAIL, profile=None, other_fail=False):
    """Minimal PR-1 inputs: only the proofs vary (every other check is NOT_READY for its own reasons)."""
    proofs = {name: PA.ExternalProofV1(name, PA.PASS, H(name), PA.REQUIRED_DEPLOYER_MATURITY
                                       if name == "DEPLOYER_DENIAL" else None) for name in PA.REQUIRED_PROOFS}
    adjudication = next(iter(PA.ACCEPTED_E22_ADJUDICATIONS))
    proofs["SECRET_HYGIENE"] = PA.ExternalProofV1(
        "SECRET_HYGIENE", result, H("hygiene"),
        None if detail is None else (PA.E22_ADJUDICATION_DETAIL_PREFIX + adjudication if detail == "ADJ" else detail))
    if other_fail:
        proofs["OS_DENIAL"] = PA.ExternalProofV1("OS_DENIAL", PA.FAIL, H("os"))
    return PA.Pr1AcceptanceInputsV1(
        environment=environment, readiness=None, release_sha=None, installed_release=None,
        attested_manifest_sha256=None, host_targets={}, reviewed_runtime_digests=None, current_first_preflight=None,
        current_now=None, pinned_current_sha256=None, unit_states=(), witness_publication=None, witness_anchor=None,
        proofs=proofs, activation=None, profile=profile or SC.DEV_SYNTHETIC_CUSTODY_PROFILE)


class ReleaseJudgeTests(unittest.TestCase):
    """Release side: OWNER_RISK_ADJUDICATED only for a genuine FAIL naming a pinned adjudication, DEV_SYNTHETIC only."""

    def e22(self, **kwargs):
        result = PA.evaluate_pr1_acceptance(judge_inputs(**kwargs), mode="HOLD_RELEASE_ELIGIBILITY")
        return result, result.checks["E22_SECRET_HYGIENE"]

    def test_the_pinned_adjudication_is_a_distinct_status_never_pass(self):
        result, outcome = self.e22()
        adjudication = next(iter(PA.ACCEPTED_E22_ADJUDICATIONS))
        self.assertEqual((outcome.status, outcome.reason), (PA.OWNER_RISK_ADJUDICATED, adjudication))
        self.assertNotEqual(outcome.status, PA.PASS)
        self.assertEqual(result.package["checks"]["E22_SECRET_HYGIENE"], [PA.OWNER_RISK_ADJUDICATED, adjudication])
        self.assertFalse(any(reason.startswith("E22_") for reason in result.reasons))
        evidence = result.package["evidence"]["secretHygieneAdjudication"]
        self.assertEqual(evidence["failures"], list(PA.E22_ADJUDICATED_FAILURES))
        self.assertEqual((evidence["adjudicationSha256"], evidence["ownerRecordSha256"], evidence["transcriptSha256"]),
                         (adjudication, PA.ACCEPTED_E22_ADJUDICATIONS[adjudication], H("hygiene")))
        self.assertIn(PA.E22_ADJUDICATION_NONCLAIM, result.package["nonclaims"])
        self.assertEqual(result.package_digest, PA.package_digest(result.package))
        # A plain FAIL and a PASS give other packages; the adjudication is visible in the digest.
        plain, _ = self.e22(detail=None)
        self.assertNotEqual(plain.package_digest, result.package_digest)
        self.assertNotIn(PA.E22_ADJUDICATION_NONCLAIM, plain.package["nonclaims"])

    def test_everything_else_stays_as_before(self):
        _r, outcome = self.e22(detail=None)
        self.assertEqual((outcome.status, outcome.reason), (PA.FAIL, "PROOF_NOT_PASS:SECRET_HYGIENE"))
        _r, outcome = self.e22(detail=None, result=PA.PASS)
        self.assertEqual(outcome.status, PA.PASS)
        for kwargs, reason in ((dict(result=PA.PASS), "E22_ADJUDICATION_NOT_FOR_FAIL"),
                               (dict(detail="OWNER_RISK_ADJUDICATION=" + H("unpinned")), "E22_ADJUDICATION_NOT_ACCEPTED"),
                               (dict(detail="OWNER_RISK_ADJUDICATION=XYZ"), "E22_ADJUDICATION_MALFORMED"),
                               (dict(detail="anything else"), "E22_ADJUDICATION_MALFORMED"),
                               (dict(environment="prod"), "E22_ADJUDICATION_OUT_OF_SCOPE"),
                               (dict(environment="test"), "E22_ADJUDICATION_OUT_OF_SCOPE"),
                               (dict(profile=dataclasses.replace(SC.DEV_SYNTHETIC_CUSTODY_PROFILE, environment="prod")),
                                "E22_ADJUDICATION_OUT_OF_SCOPE"),
                               (dict(profile=dataclasses.replace(SC.DEV_SYNTHETIC_CUSTODY_PROFILE,
                                                                 initial_key_id="test-only.other")),
                                "E22_ADJUDICATION_OUT_OF_SCOPE")):
            with self.subTest(**{k: str(v)[:40] for k, v in kwargs.items()}):
                result, outcome = self.e22(**kwargs)
                self.assertEqual((outcome.status, outcome.reason), (PA.FAIL, reason))
                self.assertNotIn("secretHygieneAdjudication", result.package["evidence"])

    def test_no_unrelated_fail_is_excused(self):
        result, outcome = self.e22(other_fail=True)
        self.assertEqual(outcome.status, PA.OWNER_RISK_ADJUDICATED)
        self.assertEqual(result.status, PA.NOT_READY)
        self.assertIn("E07_SIGNER_CUSTODY_DENIAL:PROOF_NOT_PASS:OS_DENIAL", result.reasons)
        self.assertEqual(PA.release_decision(result.package_digest, result).reason, "PACKAGE_NOT_READY")


@unittest.skipUnless(P2.POSIX, "the synthetic PR-1 host needs POSIX ownership and modes")
class EndToEndAdjudicationTests(unittest.TestCase):
    def test_builder_verifier_and_judge_carry_the_adjudication_to_ready(self):
        """TEST host, TEST trust and a TEST adjudication: READY with E-22 OWNER_RISK_ADJUDICATED, never PASS."""
        with proved() as (hygiene, scope):
            spec = test_adjudication(hygiene)
        sha = RI.adjudication_digest(spec)
        transcripts = dict(T1.transcripts())
        transcripts["OS_DENIAL"] = (P2.OS.expected_pass(P2.OS.DROPINS_NONE), 0)
        transcripts["SECRET_HYGIENE"] = (hygiene, 1)
        transcripts["PRESERVATION_SET"] = (P2.capture(PS.compare, P2.BASELINE, P2.LATER, accepted=P2.ACCEPTED)[1], 0)

        def preservation_only(real):
            def patched(relative):
                module = real(relative)
                if relative.endswith("mb12_preservation_set_proof.py"):
                    module.ACCEPTED_BASELINES = P2.ACCEPTED
                return module
            return patched

        with T1.synthetic_host() as (X, host, manifest_sha), \
                mock.patch.object(RI, "_producer_module", side_effect=preservation_only(RI._producer_module)), \
                mock.patch.object(RI, "E22_ADJUDICATION_V1", spec), mock.patch.object(RI, "E22_ADJUDICATION_SHA256", sha), \
                mock.patch.object(PA, "E22_ADJUDICATION_ENVIRONMENT", X.ENV), \
                mock.patch.dict(PA.ACCEPTED_E22_ADJUDICATIONS, {sha: H("TEST owner record")}, clear=True):
            case = T1.ReadinessInputTests("test_build_is_deterministic_and_the_release_parser_accepts_it")
            case.X, case.host, case.manifest_sha = X, host, manifest_sha
            case.pins = T1.fixture_pins(X, host, manifest_sha)
            pr2, pr3, t2, t3 = case.pr2_pr3()
            accepted = {name: frozenset({H_(raw)}) for name, (raw, _e) in transcripts.items()}
            trust = RI.ReadinessTrustV1(case.pins, T1.T0, accepted, t2, t3, {sha: H("TEST owner record")})
            proofs = {name: P2.item(raw, exit_code) for name, (raw, exit_code) in transcripts.items()}
            inputs = T1.build_inputs(X, host, manifest_sha, proofs=proofs, pr2=pr2, pr3=pr3)
            inputs[RI.E22_BUILD_FIELD] = item(sha, scope)
            raw, report = RI.build(inputs, environment=X.ENV, trust=trust)
            self.assertEqual(report["expectedNotReady"], [])
            result = case.evaluate(case.roundtrip(raw))
            failing = {n: o.reason for n, o in result.checks.items() if o.status != "PASS"}
            self.assertEqual(failing, {"E22_SECRET_HYGIENE": sha})
            self.assertEqual(result.checks["E22_SECRET_HYGIENE"].status, PA.OWNER_RISK_ADJUDICATED)
            self.assertEqual(result.status, "READY")
            self.assertEqual(result.package["checks"]["E22_SECRET_HYGIENE"], [PA.OWNER_RISK_ADJUDICATED, sha])
            self.assertEqual(PA.release_decision(result.package_digest, result).status, PA.RELEASE_PERMITTED)
            # Without the adjudication input the same evidence is NOT_READY on E-22 alone.
            del inputs[RI.E22_BUILD_FIELD]
            plain = case.evaluate(case.roundtrip(RI.build(inputs, environment=X.ENV, trust=trust)[0]))
            self.assertEqual(plain.reasons, ("E22_SECRET_HYGIENE:PROOF_NOT_PASS:SECRET_HYGIENE",))
            self.assertEqual(PA.release_decision(result.package_digest, plain).reason, "PACKAGE_NOT_READY")


if __name__ == "__main__":
    unittest.main()
