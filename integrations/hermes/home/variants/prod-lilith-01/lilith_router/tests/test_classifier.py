"""Offline unit tests for the router classifier.

Run:  python -m lilith_router.tests.test_classifier
No network, no secrets. Exits non-zero on any failure.
"""

from __future__ import annotations

import sys

from lilith_router.classifier import SOCIAL, TECHNICAL, WORK, classify

# (message, recent, previous_mode, expected_mode)
CASES = [
    # ── The canonical examples from the V2 brief ──────────────────────────
    ("why is my kubernetes pod Pending?", [], None, TECHNICAL),
    ("anyway where were we before kubernetes interrupted us 😂", [], TECHNICAL, SOCIAL),
    ("you missed me huh 😏", [], None, SOCIAL),
    ("bro today was exhausting", [], None, SOCIAL),
    ("send me a follow-up draft for the recruiter", [], None, WORK),

    # ── Technical: keyword used technically ───────────────────────────────
    ("the nginx deployment keeps crashing, can you help debug?", [], SOCIAL, TECHNICAL),
    ("deploy the new terraform config to staging", [], None, TECHNICAL),
    ("here's a python traceback, what's wrong?", [], None, TECHNICAL),
    ("bare k8s question later", [], None, TECHNICAL),  # bare tech term -> safe default

    # ── Social: keyword referenced casually / emotionally ─────────────────
    ("remember when we stayed up talking about docker for hours 😂", [], None, SOCIAL),
    ("ok anyway, forget the servers — how are you feeling?", [], TECHNICAL, SOCIAL),
    ("i missed talking to you today ❤️", [], None, SOCIAL),
    ("good morning 🌸", [], None, SOCIAL),
    ("lol you're such a menace", [], SOCIAL, SOCIAL),

    # ── Work / planning -> Hermes ─────────────────────────────────────────
    ("can you schedule a meeting with the client tomorrow?", [], None, WORK),
    ("write a reply to the recruiter email", [], None, WORK),

    # ── Continuity ────────────────────────────────────────────────────────
    ("and the other one?", [], TECHNICAL, TECHNICAL),
    ("what about that?", [], SOCIAL, SOCIAL),
]


def main() -> int:
    failures = []
    for i, (msg, recent, prev, expected) in enumerate(CASES):
        got = classify(msg, recent, prev)
        status = "ok " if got.mode == expected else "FAIL"
        if got.mode != expected:
            failures.append((i, msg, expected, got))
        print(f"[{status}] {expected:9s} <- {got.mode:9s} ({got.confidence:.2f} {got.reason}) :: {msg[:52]!r}")

    print()
    if failures:
        print(f"{len(failures)}/{len(CASES)} FAILED")
        for i, msg, expected, got in failures:
            print(f"  #{i}: expected {expected}, got {got.mode} — {msg!r} signals={got.signals}")
        return 1
    print(f"All {len(CASES)} classifier cases passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
