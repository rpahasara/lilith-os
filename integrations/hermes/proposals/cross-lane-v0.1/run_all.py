"""Runs every offline suite that bears on the seven lanes and prints one table. TEST_ONLY; no host, no network, no model.

    python -B integrations/hermes/proposals/cross-lane-v0.1/run_all.py [more suite paths]

A suite counts only from unittest's own summary, so a pass, a skip and an expected failure stay separate. Exit 0 only if every suite ran and none failed.
The shell simulations need root in a sandbox, so they run on their own: sim_install_e1.sh and the package's window_sim_e1.sh.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
H = "integrations/hermes/"
REL = H + "release/"
P1 = REL + "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1/tests/"
SUITES = (("Cross-lane, seven lanes", H + "proposals/cross-lane-v0.1/test_seven_lanes.py"),
          ("Ethics detection, privacy, corpora", H + "overlays/dev-ethics-hardening/tests/test_ethics_hardening.py"),
          ("e1 release contract", H + "proposals/ethics-shadow-v0.1/test_e1_release.py"),
          ("e1 startup verifier negatives", H + "proposals/ethics-shadow-v0.1/test_e1_verifier.py"),
          ("e1 driver", H + "proposals/ethics-shadow-v0.1/package/test_drive_e1.py"),
          ("Planning compatibility, p1 release", P1 + "test_p1_release.py"),
          ("Planning lane", P1 + "test_p1_planning.py"),
          ("p1 installer contract", P1 + "test_p1_installer.py"))


def run(path):
    out = subprocess.run([sys.executable, "-B", str(REPO / path)], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = out.stdout + out.stderr
    ran = re.search(r"^Ran (\d+) tests?", text, re.M)
    tail = re.search(r"^(OK|FAILED)\b(.*)$", text, re.M)
    if not ran or not tail:
        return None
    detail = tail.group(2)
    count = lambda word: int((re.search(word + r"=(\d+)", detail) or [0, 0])[1])
    failed, errors, skipped, expected = count("failures"), count("errors"), count("skipped"), count("expected failures")
    return int(ran.group(1)), failed + errors, skipped, expected


def main():
    bad = 0
    print("%-40s %5s %5s %5s %5s %5s" % ("suite", "ran", "pass", "fail", "skip", "xfail"))
    for name, path in SUITES + tuple(("extra", p) for p in sys.argv[1:]):
        result = run(path)
        if result is None:
            bad += 1
            print("%-40s DID NOT REPORT" % name)
            continue
        ran, failed, skipped, expected = result
        bad += bool(failed)
        print("%-40s %5d %5d %5d %5d %5d" % (name, ran, ran - failed - skipped - expected, failed, skipped, expected))
    print("ALL_SUITES_PASS" if not bad else "SUITES_FAILED %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
