"""F9-B source patch (conversation-logging privacy). LOCAL build input only; never run on DEV.

    python3 -I patch_f9b.py <f8r4 built pkg dir> <overrides dir already holding the F9-A outputs>

Applies on top of F9-A (its run.py output is the base for run.py). Hash-verified bases, exact count-checked
replacements; any mismatch aborts before anything is written. Writes into the same overrides dir:
  src/gateway/run.py                 inbound-message log: sizes instead of message / reply text
  src/agent/turn_context.py          conversation-turn log: size instead of message text
  src/agent/agent_runtime_helpers.py request debug dumps are content-free (roles/sizes, no text, no error bodies)
  profiles/operate/config.yaml       F9-A onboarding "off" also in the OPERATE profile (it replaces config.yaml)
Diagnostics kept: platform, chat/session ids, model/provider, history length, message sizes, reason, error
type/status/code, timings. SOUL.md, personality, Router V2 and memory governance are not touched.
"""
import hashlib
import sys
from pathlib import Path

F8, O = Path(sys.argv[1]), Path(sys.argv[2])
BASES = {
    "src/gateway/run.py": (O, "f0c234bf36927c88bda69cf23f9f0483b298433bde035cac47b871fcaca2ed1b"),      # F9-A output
    "src/agent/turn_context.py": (F8, "24f2f5429ed21c276e59af0f010f311caa83b389cd92521aac34971e872d9a6c"),
    "src/agent/agent_runtime_helpers.py": (F8, "9b088972cd0d7d9f6cedb50ae739ddfe71e50c99f3140ea36b7d5379e1c176b1"),
    "profiles/operate/config.yaml": (F8, "e8fd4f25b67ab7d86719bef8491fabb0045d4b86fca9c6da0906481e2eba0c98"),
}


def rep(text: str, old: str, new: str, count: int, where: str) -> str:
    n = text.count(old)
    if n != count:
        raise SystemExit(f"F9B_PATCH_FAIL {where}: expected {count} occurrence(s), found {n}: {old[:70]!r}")
    return text.replace(old, new)


files = {}
for rel, (root, sha) in BASES.items():
    data = (root / rel).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha:
        raise SystemExit(f"F9B_PATCH_FAIL base hash {rel}")
    files[rel] = data.decode("utf-8")

# --- gateway/run.py: inbound-message log (gateway.log is INFO regardless of logging.level) ---------------------------
rel = "src/gateway/run.py"
files[rel] = rep(
    files[rel],
    "        _msg_preview = (event.text or \"\")[:80].replace(\"\\n\", \" \")\n"
    "        _reply_id = getattr(event, \"reply_to_message_id\", None)\n"
    "        _reply_txt = (getattr(event, \"reply_to_text\", None) or \"\")[:80].replace(\"\\n\", \" \")\n"
    "        logger.info(\n"
    "            \"inbound message: platform=%s user=%s chat=%s msg=%r reply_to_id=%s reply_to_text=%r\",\n"
    "            _platform_name, source.user_name or source.user_id or \"unknown\",\n"
    "            source.chat_id or \"unknown\", _msg_preview, _reply_id, _reply_txt,\n"
    "        )\n",
    "        # F9-B (LILITH DEV): no message text in the operating logs. gateway.log is written at INFO whatever\n"
    "        # logging.level says, so the sizes replace the previews here rather than relying on the log level.\n"
    "        _reply_id = getattr(event, \"reply_to_message_id\", None)\n"
    "        logger.info(\n"
    "            \"inbound message: platform=%s user=%s chat=%s msg_chars=%d reply_to_id=%s reply_to_chars=%d\",\n"
    "            _platform_name, source.user_name or source.user_id or \"unknown\",\n"
    "            source.chat_id or \"unknown\", len(event.text or \"\"), _reply_id,\n"
    "            len(getattr(event, \"reply_to_text\", None) or \"\"),\n"
    "        )\n",
    1, rel)

# --- agent/turn_context.py: conversation-turn log ---------------------------------------------------------------------
rel = "src/agent/turn_context.py"
files[rel] = rep(
    files[rel],
    "    # Log conversation turn start for debugging/observability.\n"
    "    _preview_text = summarize_user_message_for_log(user_message)\n"
    "    _msg_preview = (_preview_text[:80] + \"...\") if len(_preview_text) > 80 else _preview_text\n"
    "    _msg_preview = _msg_preview.replace(\"\\n\", \" \")\n"
    "    logger.info(\n"
    "        \"conversation turn: session=%s model=%s provider=%s platform=%s history=%d msg=%r\",\n"
    "        agent.session_id or \"none\", agent.model, agent.provider or \"unknown\",\n"
    "        agent.platform or \"unknown\", len(conversation_history or []),\n"
    "        _msg_preview,\n"
    "    )\n",
    "    # Log conversation turn start for debugging/observability. F9-B (LILITH DEV): the message size, not its text.\n"
    "    logger.info(\n"
    "        \"conversation turn: session=%s model=%s provider=%s platform=%s history=%d msg_chars=%d\",\n"
    "        agent.session_id or \"none\", agent.model, agent.provider or \"unknown\",\n"
    "        agent.platform or \"unknown\", len(conversation_history or []),\n"
    "        len(summarize_user_message_for_log(user_message)),\n"
    "    )\n",
    1, rel)

# --- agent/agent_runtime_helpers.py: content-free request debug dumps --------------------------------------------------
rel = "src/agent/agent_runtime_helpers.py"
t = files[rel]
t = rep(t, "def dump_api_request_debug(\n",
        "_DUMP_SAFE_STR_KEYS = (\"model\", \"reasoning_effort\", \"service_tier\")\n"
        "_DUMP_SAFE_ERROR_KEYS = (\"type\", \"status_code\", \"request_id\", \"code\", \"param\", \"response_status\")\n"
        "\n"
        "\n"
        "def _content_free_request_dump(payload: Dict[str, Any]) -> Dict[str, Any]:\n"
        "    \"\"\"F9-B (LILITH DEV): a request debug dump without conversation content.\n"
        "\n"
        "    Keeps what diagnoses a failed call (reason, endpoint, model and scalar\n"
        "    parameters, message roles and sizes, tool names, error type/status/code)\n"
        "    and drops message text, structured parameters and provider error bodies,\n"
        "    which can echo the request.\n"
        "    \"\"\"\n"
        "    def _size(value) -> int:\n"
        "        if isinstance(value, list):\n"
        "            return sum(_size(v.get(\"text\", \"\") if isinstance(v, dict) else v) for v in value)\n"
        "        return 0 if value is None else len(value if isinstance(value, str) else str(value))\n"
        "\n"
        "    out = dict(payload)\n"
        "    request = dict(out.get(\"request\") or {})\n"
        "    safe: Dict[str, Any] = {}\n"
        "    for key, value in (request.get(\"body\") or {}).items():\n"
        "        if key in (\"messages\", \"input\") and isinstance(value, list):\n"
        "            safe[key] = [{\"role\": m.get(\"role\"), \"chars\": _size(m.get(\"content\"))} if isinstance(m, dict)\n"
        "                         else {\"chars\": _size(m)} for m in value]\n"
        "        elif key == \"tools\" and isinstance(value, list):\n"
        "            safe[key] = [((t.get(\"function\") or {}).get(\"name\") or t.get(\"name\")) if isinstance(t, dict) else None\n"
        "                         for t in value]\n"
        "        elif value is None or isinstance(value, (bool, int, float)):\n"
        "            safe[key] = value\n"
        "        elif key in _DUMP_SAFE_STR_KEYS and isinstance(value, str):\n"
        "            safe[key] = value\n"
        "        else:\n"
        "            safe[key] = f\"<{type(value).__name__} omitted>\"\n"
        "    request[\"body\"] = safe\n"
        "    out[\"request\"] = request\n"
        "    if isinstance(out.get(\"error\"), dict):\n"
        "        out[\"error\"] = {k: v for k, v in out[\"error\"].items()\n"
        "                        if k in _DUMP_SAFE_ERROR_KEYS and (v is None or isinstance(v, (str, int, float, bool)))}\n"
        "    out[\"content_free\"] = True\n"
        "    return out\n"
        "\n"
        "\n"
        "def dump_api_request_debug(\n",
        1, rel)
t = rep(t, "        timestamp = datetime.now().strftime(\"%Y%m%d_%H%M%S_%f\")\n",
        "        dump_payload = _content_free_request_dump(dump_payload)   # F9-B: before anything is written or printed\n"
        "        timestamp = datetime.now().strftime(\"%Y%m%d_%H%M%S_%f\")\n",
        1, rel)
files[rel] = t

# --- OPERATE profile config: keep the F9-A onboarding setting when the profile is applied ---------------------------
rel = "profiles/operate/config.yaml"
files[rel] = rep(
    files[rel],
    "memory:\n"
    "  memory_enabled: false\n"
    "  user_profile_enabled: false\n"
    "  nudge_interval: 0\n",
    "memory:\n"
    "  memory_enabled: false\n"
    "  user_profile_enabled: false\n"
    "  nudge_interval: 0\n"
    "\n"
    "# F9-A D-1 (kept by F9-B: apply_profile.sh operate REPLACES config.yaml with this file). QUOTED on purpose: YAML\n"
    "# reads a bare `off` as boolean false, which Hermes treats as unknown -> \"ask\".\n"
    "onboarding:\n"
    "  profile_build: \"off\"\n",
    1, rel)

for rel, text in files.items():
    dst = O / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8", newline="\n")
    print(f"{hashlib.sha256(text.encode('utf-8')).hexdigest()}  {rel}")
print("F9B_PATCH_OK")
