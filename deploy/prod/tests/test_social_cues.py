"""Social Cognition contextual clues (owner review 2026-11-06): laughter / emoji / plain mood words / everyday
corrections are noticed as CLUES, several can co-exist (mixed signals), technical and polite chat stays quiet,
and every snapshot still passes the lane's own strict validation."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "deploy/prod"))
from lilith_router import social_cognition as sc  # noqa: E402

P, D, C, S, H = sc.E_PLAYFUL, sc.E_DIFFICULTY, sc.E_CORRECTION, sc.E_SUPPORT, sc.E_HUMOR


def cues(message):
    inp = sc.build_social_input(message, "sc.test", "telegram")
    snap = sc.build_social_context(inp)                       # runs validate_social_context
    return {c["cueType"] for c in snap["socialCues"]}, snap


class SocialCueTests(unittest.TestCase):
    def test_playful_and_warm_clues(self):
        for msg in ("Hey Lilith ❤️ I've decided to call my weekend coding sessions \"Starlight Sessions\" haha",
                    "lol you are such a cutie", "Good morning Lilith 🌸 missed you", "hahaha okay fine 😏",
                    "hehe thank you"):
            with self.subTest(msg=msg):
                self.assertIn(P, cues(msg)[0])

    def test_plain_difficulty_clues(self):
        for msg in ("ugh today was rough, I am so tired", "I'm really stressed about the interview",
                    "long day at work", "feeling kinda down tonight", "this is killing me"):
            with self.subTest(msg=msg):
                self.assertIn(D, cues(msg)[0])

    def test_mixed_signals_keep_both_clues(self):
        found, _ = cues("ugh this bug is killing me lol")
        self.assertEqual(found & {P, D}, {P, D})                # frustration told with a joke: both, neither wins
        found, _ = cues("rough day haha but I'm okay ❤️")
        self.assertEqual(found & {P, D}, {P, D})

    def test_everyday_corrections(self):
        for msg in ("no, that's wrong, I meant the other one", "actually, use port 8080 instead",
                    "that's not what I asked", "you misunderstood me", "nope, Tuesday not Monday"):
            with self.subTest(msg=msg):
                found, snap = cues(msg)
                self.assertIn(C, found)
                self.assertNotIn("CURRENT_TURN_ROLE_CORRECTION", {c["conflictType"] for c in snap["conflicts"]})

    def test_role_swap_correction_still_a_role_conflict(self):
        found, snap = cues("No, my recruiter, not my manager")
        self.assertIn(C, found)
        self.assertIn("CURRENT_TURN_ROLE_CORRECTION", {c["conflictType"] for c in snap["conflicts"]})

    def test_support_requests(self):
        for msg in ("can you cheer me up", "I need a hug", "could you reassure me"):
            with self.subTest(msg=msg):
                self.assertIn(S, cues(msg)[0])

    def test_quiet_when_there_is_no_clue(self):
        for msg in ("How do I configure an nginx reverse proxy?", "no worries, take your time", "no problem at all",
                    "nah it is fine", "no, I am fine thanks", "What's the status of my job applications?",
                    "Run the tests again please", "I prefer three short sections"):
            with self.subTest(msg=msg):
                self.assertEqual(cues(msg)[0], set())

    def test_explicit_requests_still_work(self):
        self.assertIn(H, cues("make it funny please")[0])
        _, snap = cues("my manager wants a status email, keep it formal")
        self.assertEqual([c["value"] for c in snap["explicitInteractionConstraints"]], ["PROFESSIONAL"])

    def test_evidence_is_grounded_in_the_text(self):
        msg = "ugh this bug is killing me lol"
        ev = sc.build_social_turn_evidence(msg, "sc.g")
        for item in ev["evidenceItems"]:
            r = item["sourceRange"]
            self.assertTrue(msg[r["start"]:r["endExclusive"]].strip())   # every clue points at real characters


if __name__ == "__main__":
    unittest.main()
