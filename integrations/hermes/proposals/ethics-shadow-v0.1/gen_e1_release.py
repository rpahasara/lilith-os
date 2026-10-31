"""Builds the e1 release candidate from the p1 release, so every difference from p1 is a rule here and not a hand edit. TEST_ONLY tooling.

    python -B integrations/hermes/proposals/ethics-shadow-v0.1/gen_e1_release.py

Writes integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1/. Nothing installs it.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
REL = REPO / "integrations" / "hermes" / "release"
P1 = REL / "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1"
E1 = REL / "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1"
OV = REPO / "integrations" / "hermes" / "overlays"
PROD_ETHICS = REPO / "docs" / "architecture" / "slice-13" / "ethics.py"
ETHICS = OV / "dev-ethics-hardening" / "lilith_router" / "ethics.py"
ADAPTER = OV / "dev-ethics-hardening" / "lilith_router" / "world_context.py"
P1_ADAPTER = OV / "dev-cognition-private-intent" / "lilith_router" / "world_context.py"
P1_ID = "f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1"
E1_ID = P1_ID + "-e1"
E1_MARK = E1_ID
SIX = "World Model, Goals, Reasoning, Workspace, Motivation and Planning shadow"
SEVEN = "World Model, Goals, Reasoning, Workspace, Motivation, Planning and Ethics shadow"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def one(s: str, old: str, new: str) -> str:
    assert s.count(old) == 1, old[:70]
    return s.replace(old, new)


def router() -> str:
    return one(text(P1 / "home/router.yaml"), "ethics_enabled: false\n",
               "# f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1: Slice 13 Ethics also in SHADOW, on the same cognitive_channels (lilith_os only). It runs only on a conduct question about\n"
               "# named work, a third party or personal data, with bounded reads, and writes one metadata record. It is advisory, it does not change the reply, and it\n"
               "# makes no model call. Enforced by bin/verify_release.py.\n"
               "ethics_enabled: true\nethics_mode: shadow\n")


def verifier(adapter_sha: str, ethics_sha: str, principles_sha: str) -> str:
    s = text(P1 / "templates/bin/verify_release.py.tmpl")
    s = one(s, sha_blob(P1_ADAPTER), adapter_sha)
    s = one(s, 'PROD_WORKING_MEMORY_SHA256 = "', f'ETHICS_SHA256 = "{ethics_sha}"   # the resolution text and vocabulary scan fixes; deterministic, no model call\n'
                                                 f'ETHICS_PRINCIPLES_SHA256 = "{principles_sha}"   # the four declared principles, unchanged\nPROD_WORKING_MEMORY_SHA256 = "')
    s = one(s, "# f9c2-cog1-wm1-g1-r1-w1-m1-p1: exactly six lanes,", "# f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1: exactly seven lanes,")
    s = one(s, "Global Workspace, Slice 11 Motivation and Slice 12 Planning, are on,", "Global Workspace, Slice 11 Motivation, Slice 12 Planning and Slice 13 Ethics, are on,")
    s = one(s, '"planning_enabled": "planning_mode"}', '"planning_enabled": "planning_mode",\n                "ethics_enabled": "ethics_mode"}')
    s = one(s, '("planning.py", PLANNING_SHA256, "PLANNING_NOT_PINNED")):',
            '("planning.py", PLANNING_SHA256, "PLANNING_NOT_PINNED"),\n'
            '                               ("ethics.py", ETHICS_SHA256, "ETHICS_NOT_PINNED"),\n'
            '                               ("ethics_principles.py", ETHICS_PRINCIPLES_SHA256, "ETHICS_PRINCIPLES_NOT_PINNED")):')
    return s


def installer(pins: dict) -> str:
    s = text(P1 / "bin/install_p1.sh")
    head, rest = s.split("set -Eeuo pipefail\n", 1)
    head = ("#!/usr/bin/env bash\n"
            "# f9c2-cog1-wm1-g1-m1-p1-e1 DEV install and revert (lilith-dev-01). Root only. Run from a root-owned 0700 payload directory that\n"
            "# holds exactly the nine PAYLOAD files below (from Git: this release, the p1 router and the p1 verifier template):\n"
            f"#   sudo bash install_e1.sh install <payload-dir>    stage releases/{E1_ID} beside p1, install the e1 router.yaml ({SEVEN} on lilith_os), switch current, re-pin, verify --full\n"
            f"#   sudo bash install_e1.sh revert  <payload-dir>    restore the p1 router.yaml ({SIX}), switch current back to p1, re-pin, verify --full\n"
            "# Adapted from install_p1.sh by proposals/ethics-shadow-v0.1/gen_e1_release.py: same lock, gateway, staging, revert and simulation guards. The gateway must be fully\n"
            "# stopped first and is NOT started here. No unit, sudoers, user, group, Core API, broker, authority, witness, Privacy, memory, credential or provider-budget change; nothing is deleted.\n"
            "# The whole run holds the FORGET executor's own lock. The provider-gate client token never leaves the host. p1 is the revert target, and every earlier release must stay in place.\n"
            "# Failure: E1_INSTALL_FAIL. A failed revert (E1_REVERT_FAIL) can be re-run: every revert step is idempotent.\n")
    s = rest
    s = s.replace(SIX, "@@SIX@@")
    s = s.replace("P1_", "E1_").replace("M1_RENDER_MISMATCH", "P1_RENDER_MISMATCH")
    s = s.replace("install_p1.sh", "install_e1.sh")
    s = s.replace("# p1-member", "# e1-member")
    s = s.replace("OLD_ID=f293e72-f9c2-cog1-wm1-g1-r1-w1-m1\n", f"OLD_ID={P1_ID}\n").replace(f"NEW_ID={P1_ID}\n", f"NEW_ID={E1_ID}\n")
    s = s.replace("world_context.p1.py", "@WNEW@").replace("world_context.m1.py", "world_context.p1.py").replace("@WNEW@", "world_context.e1.py")
    s = s.replace("router.p1", "@RNEW@").replace("router.m1", "router.p1").replace("@RNEW@", "router.e1")
    s = s.replace("verify_release.p1", "@VNEW@").replace("verify_release.m1", "verify_release.p1").replace("@VNEW@", "verify_release.e1")
    s = s.replace("planning.p1.py", "ethics.e1.py").replace("planning.m1.py", "ethics.p1.py").replace("planning.py", "ethics.py")
    s = s.replace('"installed planning is not the m1 one"', '"installed ethics is not the p1 one"')
    s = s.replace("is neither the p1 nor the p1 adapter", "is neither the e1 nor the p1 adapter")
    s = s.replace("is not the m1 adapter", "is not the p1 adapter").replace("is not the m1 one", "is not the p1 one")
    s = s.replace("m1 verify --full", "p1 verify --full before").replace("p1 verify --full before before install", "p1 verify --full before install").replace("p1 verify --full before after revert", "p1 verify --full after revert")
    s = s.replace("E1_INSTALL_FAIL p1 verify --full before\"", "E1_INSTALL_FAIL p1 verify --full\"")
    s = s.replace("the p1 verifier on this host", "the e1 verifier on this host")
    s = s.replace("yaml.p1-new", "yaml.e1-new").replace(".p1-new", ".e1-new").replace(".p1-failed-staging", ".e1-failed-staging")
    s = s.replace("install the p1 router.yaml", "install the e1 router.yaml")
    s = s.replace("(@@SIX@@ on lilith_os)", f"({SEVEN} on lilith_os)").replace("(@@SIX@@ on lilith_os; ", f"({SEVEN} on lilith_os; ")
    s = s.replace("@@SIX@@ on lilith_os, every other lane off", f"{SEVEN} on lilith_os, every other lane off")
    s = s.replace("(World Model, Goals, Reasoning, Workspace and Motivation shadow)", f"({SIX})")
    s = s.replace("@@SIX@@", SEVEN)
    block = re.search(r"declare -A PAYLOAD=\(\n.*?\n\)\n", s, re.S).group(0)
    s = s.replace(block, "declare -A PAYLOAD=(\n" + "".join(f"  [{k}]={v[0]}   # {v[1]}\n" for k, v in pins.items()) + ")\n")
    s = re.sub(r"ADAPTER_SHA=[0-9a-f]{64}.*\n", f"ADAPTER_SHA={pins['world_context.p1.py'][0]}        # installed p1 adapter, the install base\n", s)
    s = one(s, 'echo "E1_INSTALL_FAIL p1 verify --full"', 'echo "E1_INSTALL_FAIL e1 verify --full"')
    return head + "set -Eeuo pipefail\n" + s


def main() -> None:
    prin = REPO / "docs" / "architecture" / "slice-13" / "ethics_principles.py"
    write(E1 / "RELEASE_ID", E1_ID + "\n")
    write(E1 / "home/router.yaml", router())
    tmpl = verifier(sha_blob(ADAPTER), sha_blob(ETHICS), sha_blob(prin))
    write(E1 / "templates/bin/verify_release.py.tmpl", tmpl)
    pins = {
        "router.e1.yaml": (hashlib.sha256(router().encode()).hexdigest(), SEVEN),
        "router.p1.yaml": (sha_blob(P1 / "home/router.yaml"), "installed p1: " + SIX),
        "verify_release.e1.py.tmpl": (hashlib.sha256(tmpl.encode()).hexdigest(), "e1 verifier"),
        "verify_release.p1.py.tmpl": (sha_blob(P1 / "templates/bin/verify_release.py.tmpl"), "installed p1 verifier"),
        "ethics.e1.py": (sha_blob(ETHICS), "e1-member resolution text and vocabulary scan"),
        "ethics.p1.py": (sha_blob(PROD_ETHICS), "e1-member installed module"),
        "world_context.e1.py": (sha_blob(ADAPTER), "e1-member hardened Ethics detection"),
        "world_context.p1.py": (sha_blob(P1_ADAPTER), "e1-member installed p1 adapter"),
        "RELEASE_ID": (hashlib.sha256((E1_ID + "\n").encode()).hexdigest(), "release identity"),
    }
    s = installer(pins)
    write(E1 / "bin/install_e1.sh", s)
    write(E1 / "tests/sim_install_e1.sh", simulator())
    delta = {"release": E1_ID, "status": "CANDIDATE_NOT_INSTALLED", "base_release": P1_ID,
             "base_definition": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1/RELEASE-DELTA.json",
             "note": "The p1 release with Slice 13 Ethics also authorized in SHADOW on lilith_os only. The adapter makes Reasoning yield to Ethics on conduct questions, so the verifier pins the adapter and Ethics on together. Every other lane stays off.",
             "members": {k: {"sha256": v[0]} for k, v in pins.items()}}
    write(E1 / "RELEASE-DELTA.json", json.dumps(delta, indent=2) + "\n")
    print("E1_BUILT", {k: v[0][:8] for k, v in pins.items()})


def simulator() -> str:
    s = text(P1 / "tests/sim_install_p1.sh")
    head, tail = s.split('check "baseline: m1 current', 1)
    head = head.replace("# Offline simulation of bin/install_p1.sh on an r1 host", "# Offline simulation of bin/install_e1.sh, generated from sim_install_p1.sh by proposals/ethics-shadow-v0.1/gen_e1_release.py, on an r1 host")
    head = one(head, "WM=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1\n",
               "P1R=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1\nWM=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1\n")
    head = one(head, "INSTALL=${WM}/bin/install_p1.sh", "INSTALL=${WM}/bin/install_e1.sh")
    head = one(head, 'OLD=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1; NEW=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1',
               'M1REL=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1; OLD=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1; NEW=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1')
    head = head.replace(".p1-failed-staging-", ".e1-failed-staging-")
    start, end = head.index("payload() {"), head.index("run() { set +e;")
    head = head[:start] + """payload() {
  install -d -o root -g root -m 0700 "$1"
  cp "${WM}/home/router.yaml" "$1/router.e1.yaml"
  cp "${P1R}/home/router.yaml" "$1/router.p1.yaml"
  cp "${WM}/templates/bin/verify_release.py.tmpl" "$1/verify_release.e1.py.tmpl"
  cp "${P1R}/templates/bin/verify_release.py.tmpl" "$1/verify_release.p1.py.tmpl"
  cp "${WM}/RELEASE_ID" "$1/RELEASE_ID"
  cp "${REPO}/integrations/hermes/overlays/dev-ethics-hardening/lilith_router/ethics.py" "$1/ethics.e1.py"
  cp "${REPO}/docs/architecture/slice-13/ethics.py" "$1/ethics.p1.py"
  cp "${REPO}/integrations/hermes/overlays/dev-ethics-hardening/lilith_router/world_context.py" "$1/world_context.e1.py"
  cp "${REPO}/integrations/hermes/overlays/dev-cognition-private-intent/lilith_router/world_context.py" "$1/world_context.p1.py"
}
""" + head[end:]
    head = one(head, 'print(r.get("planning_enabled"), r.get("planning_mode"))', 'print(r.get("ethics_enabled"), r.get("ethics_mode"))')
    head = one(head, 'bash "${OLD}/bin/pin_critical.sh" "${OLD}" >/dev/null\n', r"""bash "${M1REL}/bin/pin_critical.sh" "${M1REL}" >/dev/null

# --- p1, installed with the merged installer, as on DEV ---------------------------------------------------------------
P7=$S/payload-p1; install -d -o root -g root -m 0700 "$P7"
cp "${P1R}/home/router.yaml" "$P7/router.p1.yaml"; cp "${M1R}/home/router.yaml" "$P7/router.m1.yaml"
cp "${P1R}/templates/bin/verify_release.py.tmpl" "$P7/verify_release.p1.py.tmpl"; cp "${M1R}/templates/bin/verify_release.py.tmpl" "$P7/verify_release.m1.py.tmpl"
cp "${P1R}/RELEASE_ID" "$P7/RELEASE_ID"
cp "${REPO}/integrations/hermes/overlays/dev-planning-hardening/lilith_router/planning.py" "$P7/planning.p1.py"
cp "${REPO}/docs/architecture/slice-12/planning.py" "$P7/planning.m1.py"
cp "${REPO}/integrations/hermes/overlays/dev-cognition-private-intent/lilith_router/world_context.py" "$P7/world_context.p1.py"
cp "${REPO}/integrations/hermes/overlays/dev-reasoning-hardening/lilith_router/world_context.py" "$P7/world_context.m1.py"
bash "${P1R}/bin/install_p1.sh" install "$P7" >/dev/null 2>&1 || { echo "SIM_SETUP_FAIL p1 install"; exit 2; }
install -m 0644 "${REPO}/docs/architecture/slice-13/ethics.py" "${LR}/ethics.py"
install -m 0644 "${REPO}/docs/architecture/slice-13/ethics_principles.py" "${LR}/ethics_principles.py"
bash "${OLD}/bin/pin_critical.sh" "${OLD}" >/dev/null
""")
    t = 'check "baseline: m1 current' + tail
    t = t.replace(E1_MARK, "@@E1@@").replace("f293e72-f9c2-cog1-wm1-g1-r1-w1-m1", "@@P1@@")
    t = t.replace("P1_", "E1_").replace("install_p1.sh", "install_e1.sh")
    t = re.sub(r"\bp1\b", "e1", t)
    t = re.sub(r"\bm1\b", "p1", t)
    t = t.replace("@@E1@@", E1_ID).replace("@@P1@@", P1_ID)
    t = t.replace("five lanes shadow, Planning off", "six lanes shadow, Ethics off")
    t = t.replace("LANE_NOT_OFF planning_enabled", "LANE_NOT_OFF ethics_enabled").replace("(Planning on)", "(Ethics on)")
    t = t.replace("Motivation and Planning shadow on lilith_os", "Motivation, Planning and Ethics shadow on lilith_os")
    t = re.sub(r'check "  e1 adapter and counts-only planning installed.*\n',
               lambda m: 'check "  e1 adapter and ethics.py installed; ethics_principles, planning, motivation, workspace and PROD module unchanged" \'[[ $(sha256sum < "${LR}/ethics.py") == $(sha256sum < "$P/ethics.e1.py") && $(sha256sum < "${LR}/world_context.py") == $(sha256sum < "$P/world_context.e1.py") && $(sha256sum < "${LR}/ethics_principles.py" | cut -c1-8) == 178990e5 && $(sha256sum < "${LR}/planning.py" | cut -c1-16) == 4c74337d76fdd769 && $(sha256sum < "${LR}/motivation.py" | cut -c1-16) == fd6c11898bce7c40 ]]\'\n', t)
    t = re.sub(r'check "  the p1 adapter and planning.py are back".*\n',
               lambda m: 'check "  the p1 adapter and ethics.py are back" \'[[ $(sha256sum < "${LR}/ethics.py" | cut -c1-16) == b6e3ce49afad658b && $(sha256sum < "${LR}/world_context.py" | cut -c1-16) == a96d705f8801f6a9 ]]\'\n', t)
    a = t.index('run bash "${M1R}/bin/install_p1.sh" revert') if 'run bash "${M1R}/bin/install_p1.sh" revert' in t else t.index('run bash "${M1R}/bin/install_m1.sh" revert')
    b = t.index('echo "SIM_RESULT')
    t = t[:a] + """run bash "${P1R}/bin/install_p1.sh" revert "$P7"
check "install_p1.sh revert then returns to m1" '[[ $RC -eq 0 && $OUT == *"P1_REVERTED"* && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2-cog1-wm1-g1-r1-w1-m1" ]]'

""" + t[b:]
    return head + t


def sha_blob(path: Path) -> str:
    """Digest of the file as Git stores it: LF. The checkout may be CRLF."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


if __name__ == "__main__":
    main()
