"""TEST-ONLY: the exact transform that moves the accepted FM-2 stage tool and operator to the OWNER_PROD P3 contract.

`owner_prod_release_stages.py` and `owner_prod_operator.py` are the FM-2 tools (`fm2_release_stages.py`,
`fm2_operator.py`, both byte-unchanged) with their own module docstring, the three FM-2 module names moved to the P3
modules, every other `FM2` / `fm2` / `FM-2` name moved to P3, and exactly the block replacements below. The test
proves the P3 bodies equal this transform of the FM-2 bodies, so reviewing P3 means reviewing this table.
"""

from __future__ import annotations

BODY_MARKER = "\nfrom __future__ import annotations\n"
RENAMES = (("fm2_signer_upgrade", "owner_prod_signer_upgrade"), ("fm2_release_stages", "owner_prod_release_stages"),
           ("fm2_operator", "owner_prod_operator"), ("FM2", "P3"), ("fm2", "p3"), ("FM-2", "P3"))

# (old block after RENAMES, new block): each old block occurs exactly once.
STAGES_BLOCKS = (
    ("# The incarnations this transition ends: the FM-1 owner-accepted replacements (record\n"
     "# personal-memory-p3-dev-activation §2; the witness also first-memory-fm1-release-transition §5).\n"
     "ENDING_SIGNER_INCARNATION = (\"5e439b2dfd434367a14ac5870b9a6316\", \"298274\")\n"
     "ENDING_WITNESS_INCARNATION = (\"efa7040c6ad94de69bfeadd496ba1ac3\", \"294978\")\n",
     "# The incarnations this transition ends: the FM-2 owner-accepted replacements (record\n"
     "# personal-memory-fm2-dev-activation §7).\n"
     "ENDING_SIGNER_INCARNATION = (\"c32457250aff4155bce1f54f1648945f\", \"309023\")\n"
     "ENDING_WITNESS_INCARNATION = (\"1089ad88e0eb4c55b167a48cdb898aa1\", \"308690\")\n"),
    ("`new_payload_pins`): 2 changed, none added or removed.",
     "`new_payload_pins`): 18 changed, none added or removed."),
)

OPERATOR_BLOCKS = (
    ("    FM1_CONTRACT: \"749bd4ee2721682733adf95ee9b670bf86a9671b91370eb6da56f832caf0270b\",\n"
     "    CONTRACT: \"fe2e5fb80f1a5706fca0e591f515b8af11fd191fe240ef58aa05adce2075b584\",\n"
     "    STAGES: \"15a2594fb08b043645693d0e36abbb405a48dedc9fbf7eb3e43d828ebea866aa\",\n",
     "    FM1_CONTRACT: \"749bd4ee2721682733adf95ee9b670bf86a9671b91370eb6da56f832caf0270b\",\n"
     "    FM2_CONTRACT: \"fe2e5fb80f1a5706fca0e591f515b8af11fd191fe240ef58aa05adce2075b584\",\n"
     "    CONTRACT: \"{contract}\",\n"
     "    STAGES: \"{stages}\",\n"),
    ("import fm1_signer_upgrade as FM1  # noqa: E402  (the installed release's contract: OLD and the layout v3 members)\n"
     "import owner_prod_signer_upgrade as P3  # noqa: E402  (this transition's contract)\n",
     "import fm1_signer_upgrade as FM1  # noqa: E402  (the FM-1 contract: the layout v3 members, through FM-2)\n"
     "import fm2_signer_upgrade as FM2  # noqa: E402  (the installed release's contract: OLD)\n"
     "import owner_prod_signer_upgrade as P3  # noqa: E402  (this transition's contract)\n"),
    ("CONTRACT = T + \"owner_prod_signer_upgrade.py\"\n",
     "FM2_CONTRACT = T + \"fm2_signer_upgrade.py\"\n"
     "CONTRACT = T + \"owner_prod_signer_upgrade.py\"\n"),
    ("# host reads, signer rule, K-PAN and anchor facts), the FM-1 contract it builds on and the P3 contract, under the\n"
     "# system interpreter.\n"
     "STAGES_BUNDLE = (*E23OP.STAGES_BUNDLE, FM1_CONTRACT, CONTRACT, STAGES)\n",
     "# host reads, signer rule, K-PAN and anchor facts), the FM-1 and FM-2 contracts it builds on and the P3 contract,\n"
     "# under the system interpreter.\n"
     "STAGES_BUNDLE = (*E23OP.STAGES_BUNDLE, FM1_CONTRACT, FM2_CONTRACT, CONTRACT, STAGES)\n"),
    ("        for module, path in ((E23OP, E23OP.OPERATOR), (FM1, FM1_CONTRACT), (P3, CONTRACT), (S, STAGES)):\n",
     "        for module, path in ((E23OP, E23OP.OPERATOR), (FM1, FM1_CONTRACT), (FM2, FM2_CONTRACT), (P3, CONTRACT),\n"
     "                             (S, STAGES)):\n"),
    ("        \"\"\"F0: OLD only, the FM-1 accepted signer and witness,",
     "        \"\"\"F0: OLD only, the FM-2 accepted signer and witness,"),
    ("            reasons.append(\"NOT_THE_FM1_ACCEPTED_INCARNATIONS\")\n",
     "            reasons.append(\"NOT_THE_FM2_ACCEPTED_INCARNATIONS\")\n"),
    ("the unchanged witness payload from releases/{new}; exactly one K-WIT",
     "the witness from releases/{new} (its 2 changed members); exactly one K-WIT"),
    ("running the unchanged witness payload from \"",
     "running the P3 witness payload from \""),
)


def transform(body: str, blocks, **values: str) -> str:
    for old, new in RENAMES:
        body = body.replace(old, new)
    for old, new in blocks:
        assert body.count(old) == 1, old
        body = body.replace(old, new.format(**values) if values and "{contract}" in new else new)
    return body


def body(source: str) -> str:
    """Everything after the module docstring (each tool's own docstring is reviewed on its own)."""
    assert source.count(BODY_MARKER) == 1
    return source[source.index(BODY_MARKER):]
