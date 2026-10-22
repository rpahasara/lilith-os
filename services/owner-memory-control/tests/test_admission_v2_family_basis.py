"""admission_v2 family-specific epistemic basis (owner-ratified 2026-10-22, local synthetic only).

The expected epistemic basis derives exclusively from the VERIFIED, action-bound purpose through a closed, read-only
map: codename -> USER_ASSERTED (unchanged), First Interaction -> RECORDED_INTERACTION, unknown -> reject. The stored
admission basis is compared, never trusted, and no caller input selects the expected basis. OwnerEvidenceV2,
admission authorization and digest semantics are unchanged.
"""

from __future__ import annotations

import dataclasses
import inspect
import unittest

import synthetic_b1b3b as T  # puts the core-api package on sys.path
import synthetic_fm02_l04 as FX
from lilith_memory import canonical_contracts as C
from lilith_memory import memory_action_v2 as MA
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import l04_v2_adapter as AD

AUTHORITY_INPUTS = ("owner_context", "authority_context", "action", "challenge_json", "challenge_record",
                    "assertion", "owner_credential", "registry", "evidence")


class BasisCase(unittest.TestCase):
    def admitted(self, flow, *, first: bool):
        self.addCleanup(flow.l04.close)
        if first:
            _action, proposal, proof, evidence = flow.create_fi(nonce="basis.fi")
        else:
            _action, proposal, proof, evidence = flow.create("SYNTH-BASIS", "basis.codename")
        self.assertEqual(flow.adapter.admit(flow.request(proposal, proof, evidence)).status, AD.L04_ADMITTED)
        return flow.acceptance_kwargs(proof, evidence, proposal)

    def with_basis(self, kwargs, basis):
        return dict(kwargs, admission=dict(kwargs["admission"], epistemicBasis=basis))


class ClosedMapTests(unittest.TestCase):
    def test_the_map_is_exact_closed_and_read_only(self):
        self.assertIs(V2.EPISTEMIC_BASIS_BY_PURPOSE, MA.EPISTEMIC_BASIS_BY_PURPOSE)
        self.assertEqual(dict(V2.EPISTEMIC_BASIS_BY_PURPOSE), {
            C.LONG_TERM_PERSONAL_PROJECT_RECALL: "USER_ASSERTED",
            MA.OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION: "RECORDED_INTERACTION"})
        with self.assertRaises(TypeError):
            V2.EPISTEMIC_BASIS_BY_PURPOSE["UNKNOWN_PURPOSE"] = "USER_ASSERTED"
        self.assertEqual((V2.L04_V2_EPISTEMIC_BASIS, V2.L04_V2_ADMISSION_BASIS),
                         ("USER_ASSERTED", "OWNER_DIRECTED_EXACT_ACTION"))        # unchanged public constants

    def test_no_caller_input_selects_the_expected_basis(self):
        for fn in (V2.verify_accepted_memory_v2, V2.check_admission_link, V2.verify_owner_authority):
            with self.subTest(fn=fn.__name__):
                self.assertFalse([p for p in inspect.signature(fn).parameters if "basis" in p.lower()])
        source = inspect.getsource(V2.check_admission_link)
        self.assertIn("EPISTEMIC_BASIS_BY_PURPOSE.get(action.purpose)", source)


class CodenameRegressionTests(BasisCase):
    def test_codename_is_accepted_with_user_asserted_on_both_schemas(self):
        for label, flow in (("schema v1", T.Flow(durable=True)), ("schema v2", FX.FirstInteractionFlow())):
            with self.subTest(schema=label):
                kwargs = self.admitted(flow, first=False)
                result = V2.verify_accepted_memory_v2(**kwargs)
                self.assertEqual((result.status, result.facts["epistemicBasis"]), (V2.ACCEPTED_MEMORY, "USER_ASSERTED"))

    def test_codename_row_with_any_other_basis_is_refused(self):
        kwargs = self.admitted(FX.FirstInteractionFlow(), first=False)
        for basis, reason in (("RECORDED_INTERACTION", "ADMISSION_BINDING_MISMATCH"),
                              ("VERIFIED", "ADMISSION_BINDING_MISMATCH"),
                              ("", "ADMISSION_MALFORMED")):               # refused earlier, by the view parser
            with self.subTest(basis=basis):
                result = V2.verify_accepted_memory_v2(**self.with_basis(kwargs, basis))
                self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, reason))


class FirstInteractionBasisTests(BasisCase):
    def test_first_interaction_is_accepted_only_with_recorded_interaction(self):
        kwargs = self.admitted(FX.FirstInteractionFlow(), first=True)
        result = V2.verify_accepted_memory_v2(**kwargs)
        self.assertEqual((result.status, result.facts["epistemicBasis"]), (V2.ACCEPTED_MEMORY, "RECORDED_INTERACTION"))
        for basis in ("USER_ASSERTED", "VERIFIED"):
            with self.subTest(basis=basis):
                result = V2.verify_accepted_memory_v2(**self.with_basis(kwargs, basis))
                self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, "ADMISSION_BINDING_MISMATCH"))

    def test_a_tampered_stored_basis_is_refused_on_read(self):
        flow = FX.FirstInteractionFlow()
        self.admitted(flow, first=True)
        self.assertEqual(flow.read_fi().status, V2.ACCEPTED_MEMORY)
        conn = flow.l04.raw()
        try:
            trigger = conn.execute("SELECT sql FROM sqlite_master WHERE name='memory_revision_no_update'").fetchone()[0]
            conn.execute("DROP TRIGGER memory_revision_no_update")
            conn.execute("UPDATE memory_revision SET epistemic_basis='USER_ASSERTED'")
            conn.execute(trigger)
            conn.commit()
        finally:
            conn.close()
        read = flow.read_fi()
        self.assertEqual((read.status, read.reason), (V2.NOT_ACCEPTED, "ADMISSION_BINDING_MISMATCH"))


class PurposeBindingTests(BasisCase):
    def test_purpose_comes_only_from_the_verified_action(self):
        kwargs = self.admitted(FX.FirstInteractionFlow(), first=False)
        # An action for the other family is not the owner-signed action: refused before any basis comparison.
        flow = FX.FirstInteractionFlow()
        self.addCleanup(flow.l04.close)
        other, _encoded = flow.l04.fi_action()
        result = V2.verify_accepted_memory_v2(**dict(kwargs, action=other))
        self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, "OWNER_PROOF_REJECTED"))

    def test_an_unknown_purpose_is_rejected(self):
        kwargs = self.admitted(FX.FirstInteractionFlow(), first=False)
        authority = V2.verify_owner_authority(**{k: kwargs[k] for k in AUTHORITY_INPUTS}, expected_evidence_id=None)
        unknown = dataclasses.replace(kwargs["action"], purpose="UNKNOWN_PURPOSE")
        self.assertIsNone(V2.EPISTEMIC_BASIS_BY_PURPOSE.get(unknown.purpose))
        with self.assertRaises((V2.Reject, C.ContractError)):
            V2.check_admission_link(authority, unknown, kwargs["admission"], kwargs["link"])
        result = V2.verify_accepted_memory_v2(**dict(kwargs, action=unknown))
        self.assertEqual(result.status, V2.NOT_ACCEPTED)


if __name__ == "__main__":
    unittest.main()
