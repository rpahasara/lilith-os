"""F9-A source patch (owner decisions D-1 option B, D-2). LOCAL build input only; never run on DEV.

    python3 -I patch_f9a.py <f8r4 built pkg dir> <out overrides dir>

Reads the four F8r4 base files (hash-verified), applies exact, count-checked replacements and writes the patched
copies under <out>/{src/gateway/run.py, home/lilith_router/gateway_integration.py, home/config.yaml,
tests/test_f7_offline.py}. Any base-hash or snippet mismatch aborts without writing anything.

D-1 (B): onboarding.profile_build: off in the DEV config, AND no first-contact sidecar note at all for lilith_os turns
         (neither the profile-build directive nor the plain intro note). SOUL.md / personality code are not touched.
D-2:     the Router decision log carries no message text: every `preview` field is replaced by non-content metadata
         (a random per-record event_id, message length in characters and lines). No hash of message text is logged.
"""
import hashlib
import sys
from pathlib import Path

BASE, OUT = Path(sys.argv[1]), Path(sys.argv[2])
BASE_SHA = {
    "src/gateway/run.py": "2774eee5e585d80cbb45f5865f2718832c2ec86fdfddf8ead1f781e9b21c2553",
    "home/lilith_router/gateway_integration.py": "aef313140372497775b23b482a40c4f72a32de4a00506ad307ba1c541b6b9641",
    "home/config.yaml": "f6c43a07312757367eb1d47547ee683702b21c8fe0a6e68fb8353c5b79676256",
    "tests/test_f7_offline.py": "fd1610cb8a3b861b38fc1f91e3b30d3753efb826e5cc6539743f4f114da5f10a",
}


def rep(text: str, old: str, new: str, count: int, where: str) -> str:
    n = text.count(old)
    if n != count:
        raise SystemExit(f"F9A_PATCH_FAIL {where}: expected {count} occurrence(s), found {n}: {old[:70]!r}")
    return text.replace(old, new)


files = {}
for rel, sha in BASE_SHA.items():
    data = (BASE / rel).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha:
        raise SystemExit(f"F9A_PATCH_FAIL base hash {rel}")
    files[rel] = data.decode("utf-8")

# --- D-1 (B): gateway/run.py ---------------------------------------------------------------------------------------
rel = "src/gateway/run.py"
files[rel] = rep(
    files[rel],
    "        if not history and not await self.async_session_store.has_any_sessions():\n"
    "            # Default first-contact note: a brief self-introduction.\n",
    "        # F9-A (LILITH DEV): no first-contact sidecar note on the lilith_os console. LILITH's persona (SOUL.md) owns\n"
    "        # how she introduces herself, and anything learned about the owner belongs to LILITH's governed First Memory,\n"
    "        # never to a Hermes profile flow. Checked before has_any_sessions() so an emptied store cannot re-arm it.\n"
    "        if (\n"
    "            not history\n"
    "            and getattr(source.platform, \"value\", source.platform) != \"lilith_os\"\n"
    "            and not await self.async_session_store.has_any_sessions()\n"
    "        ):\n"
    "            # Default first-contact note: a brief self-introduction.\n",
    1, rel)

# --- D-1 (B): DEV config --------------------------------------------------------------------------------------------
rel = "home/config.yaml"
files[rel] = rep(
    files[rel],
    "# No Hermes personal memory, user profile or memory nudges on DEV.\n"
    "memory:\n"
    "  memory_enabled: false\n"
    "  user_profile_enabled: false\n"
    "  nudge_interval: 0\n",
    "# No Hermes personal memory, user profile or memory nudges on DEV.\n"
    "memory:\n"
    "  memory_enabled: false\n"
    "  user_profile_enabled: false\n"
    "  nudge_interval: 0\n"
    "\n"
    "# F9-A D-1: no Hermes profile-build onboarding (upstream default \"ask\" injects a hidden first-message directive to\n"
    "# collect the user's name/work/preferences and save them with the memory tool). It is NOT gated by the memory\n"
    "# switches above. LILITH's governed First Memory is the only route to anything durable about the owner.\n"
    "# QUOTED on purpose: YAML reads a bare `off` as boolean false, which Hermes treats as unknown -> \"ask\".\n"
    "onboarding:\n"
    "  profile_build: \"off\"\n",
    1, rel)

# --- D-2: Router decision log ---------------------------------------------------------------------------------------
rel = "home/lilith_router/gateway_integration.py"
t = files[rel]
t = rep(t, "import json\nimport logging\nimport time\n", "import json\nimport logging\nimport time\nimport uuid\n", 1, rel)
t = rep(t,
        "def _log_decision(cfg, platform, chat_id, decision, live, message) -> None:\n"
        "    \"\"\"Append one JSON line describing the routing decision. Never raises.\n"
        "\n"
        "    No secrets are logged. A short message preview (≤60 chars) is included for\n"
        "    auditing — consistent with the gateway's own inbound-message logging.\n"
        "    \"\"\"\n",
        "def _message_meta(message) -> dict:\n"
        "    \"\"\"Non-content audit metadata for a decision record (F9-A D-2).\n"
        "\n"
        "    No message text and no hash of it: a random per-record event id plus the\n"
        "    message length in characters and lines.\n"
        "    \"\"\"\n"
        "    text = message or \"\"\n"
        "    return {\"event_id\": uuid.uuid4().hex, \"msg_chars\": len(text), \"msg_lines\": len(text.splitlines())}\n"
        "\n"
        "\n"
        "def _log_decision(cfg, platform, chat_id, decision, live, message) -> None:\n"
        "    \"\"\"Append one JSON line describing the routing decision. Never raises.\n"
        "\n"
        "    No secrets and no message text are logged (F9-A D-2): only the decision\n"
        "    and non-content metadata from :func:`_message_meta`.\n"
        "    \"\"\"\n",
        1, rel)
t = rep(t, "            \"preview\": (message or \"\")[:60].replace(\"\\n\", \" \"),\n",
        "            **_message_meta(message),\n", 5, rel)
t = rep(t, "            \"preview\": \" \".join(((message or \"\")[:60]).splitlines()),\n",
        "            **_message_meta(message),\n", 3, rel)
if "preview" in t.split("def _log_social_cognition", 1)[0].replace("progress/preview", ""):
    raise SystemExit(f"F9A_PATCH_FAIL {rel}: a preview reference remains")
files[rel] = t

# --- F7 suite: the persistence test now asserts the absence of message text -----------------------------------------
rel = "tests/test_f7_offline.py"
files[rel] = rep(
    files[rel],
    "    def test_shadow_mode_never_overrides_and_logs_a_preview(self):\n"
    "        for message in (\"TEST_ONLY hey how are you 😊\", \"TEST_ONLY why is my kubernetes pod pending?\"):\n"
    "            self.assertIsNone(self.route(message))\n"
    "        log = (HERMES_HOME / \"lilith_router\" / \"decisions.log\").read_text(encoding=\"utf-8\").splitlines()\n"
    "        last = json.loads(log[-1])\n"
    "        self.assertEqual((last[\"platform\"], last[\"mode\"], last[\"live\"]), (\"lilith_os\", \"technical\", False))\n"
    "        self.assertTrue(last[\"preview\"].startswith(\"TEST_ONLY why is my\"))            # persistence finding\n",
    "    def test_shadow_mode_never_overrides_and_logs_no_message_text(self):\n"
    "        for message in (\"TEST_ONLY hey how are you 😊\", \"TEST_ONLY why is my kubernetes pod pending?\"):\n"
    "            self.assertIsNone(self.route(message))\n"
    "        raw = (HERMES_HOME / \"lilith_router\" / \"decisions.log\").read_text(encoding=\"utf-8\")\n"
    "        last = json.loads(raw.splitlines()[-1])\n"
    "        self.assertEqual((last[\"platform\"], last[\"mode\"], last[\"live\"]), (\"lilith_os\", \"technical\", False))\n"
    "        self.assertNotIn(\"preview\", last)                                              # F9-A D-2\n"
    "        self.assertEqual(last[\"msg_chars\"], len(\"TEST_ONLY why is my kubernetes pod pending?\"))\n"
    "        self.assertNotIn(\"kubernetes\", raw)\n",
    1, rel)

for rel, text in files.items():
    dst = OUT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8", newline="\n")
    print(f"{hashlib.sha256(text.encode('utf-8')).hexdigest()}  {rel}")
print("F9A_PATCH_OK")
