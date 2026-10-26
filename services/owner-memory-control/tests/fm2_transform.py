"""TEST-ONLY: the exact transform that moves the accepted FM-1 stage tool and operator to the FM-2 contract.

`fm2_release_stages.py` and `fm2_operator.py` are the FM-1 tools (`fm1_release_stages.py`, `fm1_operator.py`, both
byte-unchanged) with their own module docstring, every `FM1` / `fm1` / `FM-1` name moved to FM-2, and exactly the
block replacements below. The test proves the FM-2 bodies equal this transform of the FM-1 bodies, so reviewing FM-2
means reviewing this table.
"""

from __future__ import annotations

BODY_MARKER = "\nfrom __future__ import annotations\n"
RENAMES = (("FM1", "FM2"), ("fm1", "fm2"), ("FM-1", "FM-2"))

# (old block after RENAMES, new block): each old block occurs exactly once.
STAGES_BLOCKS = (
    ("# The incarnations this transition ends: the E-23 owner-accepted replacements (record trackb-e23-completion §3).\n"
     "ENDING_SIGNER_INCARNATION = (\"639a814da4dc4d338cef37565e14e2c0\", \"281830\")\n"
     "ENDING_WITNESS_INCARNATION = (\"86ba4cc2d0864119bba502f5f4ccd14e\", \"281470\")\n",
     "# The incarnations this transition ends: the FM-1 owner-accepted replacements (record\n"
     "# personal-memory-fm2-dev-activation §2; the witness also first-memory-fm1-release-transition §5).\n"
     "ENDING_SIGNER_INCARNATION = (\"5e439b2dfd434367a14ac5870b9a6316\", \"298274\")\n"
     "ENDING_WITNESS_INCARNATION = (\"efa7040c6ad94de69bfeadd496ba1ac3\", \"294978\")\n"),
    ("V1 with the E-23 and the FM-2 added members, bound\n",
     "V1 with the E-23 and the FM-1 added members, bound\n"),
    ("    I.EXPECTED_PATHS = saved | frozenset(E23.PAYLOAD_ADDED) | frozenset(FM2.PAYLOAD_ADDED)\n",
     "    I.EXPECTED_PATHS = saved | frozenset(E23.PAYLOAD_ADDED) | frozenset(FM2.LAYOUT_ADDED)\n"),
    ("`new_payload_pins`): 10 changed, 2 added, none removed.",
     "`new_payload_pins`): 2 changed, none added or removed."),
)

OPERATOR_BLOCKS = (
    ("    CONTRACT: \"749bd4ee2721682733adf95ee9b670bf86a9671b91370eb6da56f832caf0270b\",\n"
     "    STAGES: \"7bb29f88cab4e91484e2a8b373491099f0a5a5197562b29da25a2f4a76d73779\",\n",
     "    CONTRACT: \"fe2e5fb80f1a5706fca0e591f515b8af11fd191fe240ef58aa05adce2075b584\",\n"
     "    STAGES: \"15a2594fb08b043645693d0e36abbb405a48dedc9fbf7eb3e43d828ebea866aa\",\n"),
    ("import fm2_signer_upgrade as FM2  # noqa: E402  (this transition's contract)\n",
     "import fm1_signer_upgrade as FM1  # noqa: E402  (the installed release's contract: OLD and the layout v3 members)\n"
     "import fm2_signer_upgrade as FM2  # noqa: E402  (this transition's contract)\n"),
    ("CONTRACT = T + \"fm2_signer_upgrade.py\"\n",
     "FM1_CONTRACT = T + \"fm1_signer_upgrade.py\"\n"
     "CONTRACT = T + \"fm2_signer_upgrade.py\"\n"),
    ("    E23OP.OPERATOR: \"b84ca602c6b49b39396639686275128ad2e39580a1fa1eaf62a70ef83b7a9fdf\",\n",
     "    E23OP.OPERATOR: \"b84ca602c6b49b39396639686275128ad2e39580a1fa1eaf62a70ef83b7a9fdf\",\n"
     "    FM1_CONTRACT: \"749bd4ee2721682733adf95ee9b670bf86a9671b91370eb6da56f832caf0270b\",\n"),
    ("# host reads, signer rule, K-PAN and anchor facts) and the FM-2 contract, under the system interpreter.\n"
     "STAGES_BUNDLE = (*E23OP.STAGES_BUNDLE, CONTRACT, STAGES)\n",
     "# host reads, signer rule, K-PAN and anchor facts), the FM-1 contract it builds on and the FM-2 contract, under the\n"
     "# system interpreter.\n"
     "STAGES_BUNDLE = (*E23OP.STAGES_BUNDLE, FM1_CONTRACT, CONTRACT, STAGES)\n"),
    ("# Owner-adjudicated STOP records (docs/architecture/first-memory-fm2-release-transition.md §4, PROPOSED until merged):\n"
     "# step -> SHA-256 of its exact consumed `STEP.json`. Such a step counts as reached for the step chain ONLY; it never\n"
     "# re-runs, and the next step's own fresh gate must still read its post-phase. The 2026-10-26 STAGE STOP was the local\n"
     "# plink exit crash (0xC0000005) on the post-status read; the remote stage reported F1 and a clean re-read is F1. The\n"
     "# 2026-10-26 WITNESS_START STOP was the same crash (§5): a clean independent re-read is F5, byte-identical.\n"
     "ADJUDICATED_STEPS = {\"STAGE\": \"b82b4a5b94451313b84818860a5b8d0e06fc4815c275966c8b35d252f5e7fb4e\",\n"
     "                     \"WITNESS_START\": \"61e7624d971c1e5eddfd15b46a0ebfcbe0a17245c68eff8385d0a5555d62c2fa\"}\n",
     "# Owner-adjudicated STOP records: step -> SHA-256 of its exact consumed `STEP.json` (the FM-1 mechanism). FM-2 starts\n"
     "# with none; the known local plink exit crash on a post-status read is handled by the re-read rule below.\n"
     "ADJUDICATED_STEPS: dict[str, str] = {}\n"),
    ("# the remote command completed (record §5).",
     "# the remote command completed (FM-1 record §5)."),
    ("        for module, path in ((E23OP, E23OP.OPERATOR), (FM2, CONTRACT), (S, STAGES)):\n",
     "        for module, path in ((E23OP, E23OP.OPERATOR), (FM1, FM1_CONTRACT), (FM2, CONTRACT), (S, STAGES)):\n"),
    ("        \"\"\"F0: OLD only, the E-23 accepted signer and witness,",
     "        \"\"\"F0: OLD only, the FM-1 accepted signer and witness,"),
    ("            reasons.append(\"NOT_THE_E23_ACCEPTED_INCARNATIONS\")\n",
     "            reasons.append(\"NOT_THE_FM1_ACCEPTED_INCARNATIONS\")\n"),
)


def transform(body: str, blocks) -> str:
    for old, new in RENAMES:
        body = body.replace(old, new)
    for old, new in blocks:
        assert body.count(old) == 1, old
        body = body.replace(old, new)
    return body


def body(source: str) -> str:
    """Everything after the module docstring (each tool's own docstring is reviewed on its own)."""
    assert source.count(BODY_MARKER) == 1
    return source[source.index(BODY_MARKER):]
