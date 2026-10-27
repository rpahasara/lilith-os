"""Tests for the social-response guard — the 9 required failure modes + valid.

Run:  python -m lilith_router.tests.test_social_guard
Pure/offline (a fake regenerator stands in for the gpt-5.6-sol one-shot).
Exits non-zero on any failure.
"""

from __future__ import annotations

import sys

from lilith_router import social_guard as sg


def run():
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))
        print(f"[{'ok ' if cond else 'FAIL'}] {name}")

    FAKE = lambda user, recent: "hey you 🙂 missed you too"  # noqa: E731

    # 1) empty response
    check("1 empty content -> EMPTY", sg.classify_failure({"choices": [{"message": {"content": "   "}}]}) == sg.EMPTY)
    check("1 empty -> regenerates clean", sg.enforce_social_reply("   ", regenerator=FAKE) == "hey you 🙂 missed you too")

    # 2) null content
    check("2 null content -> NULL", sg.classify_failure({"choices": [{"message": {"content": None}}]}) == sg.NULL)
    check("2 null top-level -> NULL", sg.classify_failure(None) == sg.NULL)

    # 3) missing choices
    check("3 missing choices -> NO_CHOICES", sg.classify_failure({"choices": []}) == sg.NO_CHOICES)
    check("3 no choices key -> NO_CHOICES", sg.classify_failure({"id": "x"}) == sg.NO_CHOICES)

    # 4) <think> leakage (with real content after)
    think = {"choices": [{"message": {"content": "<think>plan the reply</think> hey, i missed you too 🙂"}}]}
    check("4 <think> leak -> THINK_LEAK", sg.classify_failure(think) == sg.THINK_LEAK)
    check("4 clean strips <think>", sg.clean("<think>plan</think> hey there") == "hey there")

    # 5) reasoning-only response (nothing left after strip)
    ro = {"choices": [{"message": {"content": "<think>she seems sad; be gentle</think>"}}]}
    check("5 reasoning-only -> REASONING_ONLY", sg.classify_failure(ro) == sg.REASONING_ONLY)
    check("5 reasoning-only -> regenerates", sg.enforce_social_reply("<think>only reasoning</think>", regenerator=FAKE) == "hey you 🙂 missed you too")

    # 6) timeout
    check("6 timeout -> TIMEOUT", sg.classify_failure(error=TimeoutError("read timed out")) == sg.TIMEOUT)

    # 7) HTTP 429
    check("7 429 -> RATE_LIMIT", sg.classify_failure(status=429) == sg.RATE_LIMIT)

    # 8) HTTP 5xx
    check("8 500 -> SERVER_ERROR", sg.classify_failure(status=503) == sg.SERVER_ERROR)

    # 9) normal valid social response
    ok = {"choices": [{"message": {"content": "aw i missed you too, how was your day? 🙂"}}]}
    check("9 valid -> None (no failure)", sg.classify_failure(ok) is None)
    check("9 valid passes through unchanged",
          sg.enforce_social_reply("aw i missed you too 🙂", regenerator=FAKE) == "aw i missed you too 🙂")

    # Bonus: free-form internal-analysis / technical-persona leakage
    leaky = "aw i've just been waiting in the cloud by my server rack thinking about you"
    check("+ leakage detected", sg.is_leaky(leaky) is True)
    check("+ leaky -> regenerates clean", sg.enforce_social_reply(leaky, regenerator=FAKE) == "hey you 🙂 missed you too")
    check("+ 'as an AI' detected", sg.is_leaky("As an AI, i don't have feelings but...") is True)
    check("+ provider exception -> EXCEPTION", sg.classify_failure(error=ValueError("bad json")) == sg.EXCEPTION)

    def _boom(user, recent):
        raise RuntimeError("regen down")
    # Leaky input + failing regenerator -> fail-safe returns cleaned original
    # (still non-empty, so the user always receives a reply).
    check("+ regenerator failure -> cleaned original (fail-safe)",
          sg.enforce_social_reply("just chilling in the cloud", regenerator=_boom) == "just chilling in the cloud")

    # ── Behavioral social guards (A disclaimer / B pet-name / C menu) ─────────
    # A clean regenerated reply with no pet name, no disclaimer, no menu. Uses
    # the legacy (user, recent) signature to also confirm back-compat.
    CLEAN = lambda user, recent: "aw, come here — that sounds like a lot 🙂"  # noqa: E731

    PREV = "there you are, handsome."   # previous delivered social reply

    # 1) relational "do you care?" + disclaimer -> reject (regenerates).
    disc = "not in the human sense — i don't have feelings, but i care about you."
    check("G1 relational + disclaimer -> flagged",
          "disclaimer" in sg.social_violations(disc, "do you actually care about me or are you just saying that?")[0])
    check("G1 relational + disclaimer -> regenerated",
          sg.enforce_social_reply(disc,
                                   user_message="do you actually care about me or are you just saying that?",
                                   regenerator=CLEAN) == "aw, come here — that sounds like a lot 🙂")

    # 2) explicit "are you conscious?" + disclaimer -> allow (passthrough).
    check("G2 explicit ontology question -> recognized",
          sg._asks_ontology("wait, are you actually conscious?") is True)
    check("G2 ontology + disclaimer -> passthrough",
          sg.enforce_social_reply(disc, user_message="wait, are you actually conscious?",
                                   regenerator=CLEAN) == disc)

    # 3) adjacent "handsome" repetition -> reject (regenerates).
    rep = "hey handsome, how was your day?"
    check("G3 adjacent 'handsome' -> flagged",
          "pet_repeat" in sg.social_violations(rep, "", PREV)[0])
    check("G3 adjacent 'handsome' -> regenerated",
          sg.enforce_social_reply(rep, last_reply=PREV, regenerator=CLEAN) == "aw, come here — that sounds like a lot 🙂")

    # 4) different pet name -> allow (passthrough).
    diff = "hey gorgeous, how was your day?"
    check("G4 different pet name -> not flagged",
          "pet_repeat" not in sg.social_violations(diff, "", PREV)[0])
    check("G4 different pet name -> passthrough",
          sg.enforce_social_reply(diff, last_reply=PREV, regenerator=CLEAN) == diff)

    # 5) no pet name -> allow (passthrough).
    none = "hey, how was your day?"
    check("G5 no pet name -> not flagged",
          "pet_repeat" not in sg.social_violations(none, "", PREV)[0])
    check("G5 no pet name -> passthrough",
          sg.enforce_social_reply(none, last_reply=PREV, regenerator=CLEAN) == none)

    # 6) explicit menu response -> reject (regenerates).
    menu = "do you want to vent about it, or would you rather i distract you?"
    check("G6 menu -> flagged", "menu" in sg.social_violations(menu, "")[0])
    check("G6 menu -> regenerated",
          sg.enforce_social_reply(menu, regenerator=CLEAN) == "aw, come here — that sounds like a lot 🙂")

    # 7) natural single-response emotional reply -> allow (passthrough).
    nat = "that sounds like a brutal day. come here, i've got you."
    check("G7 natural reply -> no violations", sg.social_violations(nat, "")[0] == [])
    check("G7 natural reply -> passthrough",
          sg.enforce_social_reply(nat, regenerator=CLEAN) == nat)

    failed = [n for n, ok_ in checks if not ok_]
    print()
    if failed:
        print(f"{len(failed)}/{len(checks)} FAILED: {failed}")
        return 1
    print(f"All {len(checks)} social-guard checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
