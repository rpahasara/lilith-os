"""How far the deployed Reasoning detector over-matches and under-matches. Descriptive, not a quality bar: it pins today's result.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/tests -p "test_r1_detector_corpus.py"

The corpus is synthetic and written by the same author as this test, so the rates are a floor to review, not a measurement of
real traffic. A shadow match costs one log record on r1, but up to five Core API reads once Workspace runs inside this lane.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
_spec = importlib.util.spec_from_file_location(
    "prod_world_context", REPO / "integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py")
WC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(WC)

ANALYTIC = [                                 # a person asking for analysis of their own work state
    "why can't you send the follow up for application 14?",
    "why is application 9 stuck?",
    "what is blocking the offer?",
    "what's stopping this from moving?",
    "what are my options for application 14?",
    "what should we do about the rejection?",
    "how should we proceed with the recruiter?",
    "what are the next steps for application 3?",
    "what information is missing to resolve this?",
    "what would settle this question?",
    "what's missing from this application?",
    "how confident are you about that?",
    "what is unclear about the job description?",
    "what are the unknowns here?",
    "analyze what this rejection means",
    "assess my chances at application 21",
    "evaluate these two offers",
    "what does this mean for my timeline?",
    "what do you make of the recruiter's reply?",
    "interpret this feedback from the interviewer",
    "what could we do differently next time?",
    "which option looks strongest to you?",
    "should I accept or wait for the other offer?",
    "pros and cons of taking this role?",
    "what are the risks of declining?",
]
CASUAL = [                                   # ordinary conversation with no analytic request
    "what next on the playlist?",
    "i'm not sure what to eat tonight",
    "not sure if i'll go out",
    "that song is by an unknown artist",
    "an unknown number called me",
    "next steps of the dance are hard",
    "the movie's implications were wild lol",
    "my teacher will assess us on friday",
    "they evaluate the cake at the fair",
    "can you interpret my dream about cats?",
    "what's missing from this soup?",
    "what's stopping you from smiling?",
    "why can't you be more fun?",
    "what should i do this weekend?",
    "what can you do?",
    "what do we do for dinner?",
    "what next?",
    "i feel uncertain about my haircut",
    "hey how are you",
    "good morning",
    "tell me a joke",
    "thanks, that was great",
    "i love this weather",
    "who won the match?",
    "what time is it?",
]
# Pinned from a run of the deployed detector, so that any change to it shows up here.
ANALYTIC_MISSED = {
    "what do you make of the recruiter's reply?",
    "which option looks strongest to you?",
    "should I accept or wait for the other offer?",
    "pros and cons of taking this role?",
    "what are the risks of declining?",
}
CASUAL_MATCHED = {
    "what next on the playlist?",
    "i'm not sure what to eat tonight",
    "not sure if i'll go out",
    "that song is by an unknown artist",
    "an unknown number called me",
    "next steps of the dance are hard",
    "the movie's implications were wild lol",
    "my teacher will assess us on friday",
    "they evaluate the cake at the fair",
    "can you interpret my dream about cats?",
    "what's missing from this soup?",
    "what's stopping you from smiling?",
    "why can't you be more fun?",
    "what should i do this weekend?",
    "what can you do?",
    "what do we do for dinner?",
    "what next?",
    "i feel uncertain about my haircut",
}


class DetectorCorpus(unittest.TestCase):
    def test_the_measured_split_is_pinned(self):
        missed = {m for m in ANALYTIC if not WC.detect_reasoning_intent(m)["any"]}
        matched = {m for m in CASUAL if WC.detect_reasoning_intent(m)["any"]}
        print(f"\nR1_DETECTOR analytic {len(ANALYTIC) - len(missed)}/{len(ANALYTIC)} casual_matched {len(matched)}/{len(CASUAL)}")
        self.assertEqual(missed, ANALYTIC_MISSED)
        self.assertEqual(matched, CASUAL_MATCHED)

    def test_a_match_carries_no_message_text(self):
        for m in ANALYTIC + CASUAL:
            d = WC.detect_reasoning_intent(m)
            self.assertEqual(set(d), {"any", "mode", "app_id", "subtype"})
            self.assertTrue(d["app_id"] is None or d["app_id"].isdigit())


if __name__ == "__main__":
    unittest.main()
