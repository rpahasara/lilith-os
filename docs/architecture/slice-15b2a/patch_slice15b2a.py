#!/usr/bin/env python3
"""Install Slice 15B2a foundations into staged or production source trees.

This patcher is deterministic and idempotent.  It never edits config values,
MEMORY.md, USER.md, World, gateway routing, API routes, frontend files, or
systemd units.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


MARKER = "Slice 15B2a canonical memory authority foundations"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def replace_first(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count < 1:
        raise RuntimeError(f"{label}: anchor is unavailable")
    return text.replace(old, new, 1)


def replace_exact_count(
    text: str, old: str, new: str, expected: int, label: str
) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} anchors, found {count}")
    return text.replace(old, new)


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".slice15b2a.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def backup(path: Path, suffix: str | None) -> None:
    if suffix:
        target = path.with_name(path.name + ".bak." + suffix)
        if not target.exists():
            shutil.copy2(path, target)


def patch_policy(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    block = f'''\n\n# {MARKER}.\n# This is a narrow extension of the existing Policy owner.  The capability is\n# metadata-only in 15B2a: no production memory tuple is active and callers\n# cannot supply a decision value.\nCANONICAL_MEMORY_POLICY_CAPABILITIES = {{\n    "canonical_memory.project_codename.mutate": {{\n+        "impactClass": "INTERNAL_WRITE",\n+        "productionActive": False,\n+        "policyVersion": "canonical-memory-policy-v1",\n+    }}\n+}}\n+\n+\n+def canonical_memory_policy_store(*args, **kwargs):\n+    """Construct the Policy-owned durable decision store lazily."""\n+    from .canonical_authority import MemoryPolicyStore\n+\n+    return MemoryPolicyStore(*args, **kwargs)\n+'''.replace("\n+", "\n")
    write_atomic(path, text + block)


def patch_learning_store(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    old = "KNOWN_COGNITIVE_TABLES = ALLOWED_TABLES | PROPOSAL_TABLES | SHARED_L04_TABLES\n"
    new = old + f'''\n# {MARKER}: additive owner tables are recognized but never writable by L18 V1.\n+try:\n+    from .slice15b2a_migration import COGNITIVE_15B2A_TABLES as _SLICE15B2A_TABLES\n+except ImportError:  # older isolated Slice 15A/15B1 fixtures\n+    _SLICE15B2A_TABLES = frozenset()\n+KNOWN_COGNITIVE_TABLES = KNOWN_COGNITIVE_TABLES | _SLICE15B2A_TABLES\n'''.replace("\n+", "\n")
    write_atomic(path, replace_once(text, old, new, path.name))


def patch_memory_store(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    old = "ALL_15B1_TABLES = L18_CORE_TABLES | {\"learning_proposal\"} | MEMORY_TABLES\n"
    new = old + f'''\n# {MARKER}: these remain externally owned and outside the L04 V1 authorizer.\n+try:\n+    from .slice15b2a_migration import COGNITIVE_15B2A_TABLES as _SLICE15B2A_TABLES\n+except ImportError:  # older isolated Slice 15B1 fixture\n+    _SLICE15B2A_TABLES = frozenset()\n+ALL_15B1_TABLES = ALL_15B1_TABLES | _SLICE15B2A_TABLES\n'''.replace("\n+", "\n")
    write_atomic(path, replace_once(text, old, new, path.name))


def patch_write_approval(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    anchor = "def stage_write(subsystem: str, payload: Dict[str, Any],\n                *, summary: str, origin: str) -> Dict[str, Any]:\n"
    replacement = anchor + f'''    # {MARKER}: staging itself is a persistence boundary.\n+    try:\n+        from tools.legacy_canonical_containment import check_legacy_payload\n+        containment = check_legacy_payload(payload)\n+    except Exception:\n+        marker = payload.get("legacyContainment") if isinstance(payload, dict) else None\n+        if isinstance(marker, dict) and marker.get("recognizedCanonicalAction") is True:\n+            return {{"id": "", "blocked": True, "failure_code": "LEGACY_CONTAINMENT_NOT_READY", "subsystem": subsystem}}\n+        containment = None\n+    if containment is not None and not containment.allowed:\n+        return {{\n+            "id": "", "blocked": True,\n+            "failure_code": containment.failure_code,\n+            "subsystem": subsystem,\n+        }}\n'''.replace("\n+", "\n")
    write_atomic(path, replace_once(text, anchor, replacement, path.name))


def patch_memory_tool(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    helper_anchor = "class MemoryStore:\n"
    helper = f'''# {MARKER}.\n+def _legacy_containment_refusal(payload: Any) -> Optional[Dict[str, Any]]:\n+    try:\n+        from tools.legacy_canonical_containment import check_legacy_payload\n+        decision = check_legacy_payload(payload)\n+    except Exception:\n+        marker = payload.get("legacyContainment") if isinstance(payload, dict) else None\n+        if isinstance(marker, dict) and marker.get("recognizedCanonicalAction") is True:\n+            return {{"success": False, "done": True, "error": "LEGACY_CONTAINMENT_NOT_READY", "failure_code": "LEGACY_CONTAINMENT_NOT_READY"}}\n+        return None\n+    if decision.allowed:\n+        return None\n+    return {{\n+        "success": False, "done": True,\n+        "error": decision.failure_code, "failure_code": decision.failure_code,\n+    }}\n+\n+\n+class MemoryStore:\n'''.replace("\n+", "\n")
    text = replace_once(text, helper_anchor, helper, path.name)
    text = replace_once(
        text,
        "        content = content.strip()\n        if not content:\n",
        "        content = content.strip()\n        refusal = _legacy_containment_refusal({\"action\": \"add\", \"target\": target, \"content\": content})\n        if refusal:\n            return refusal\n        if not content:\n",
        path.name + ":add",
    )
    text = replace_once(
        text,
        "        old_text = old_text.strip()\n        new_content = new_content.strip()\n        if not old_text:\n",
        "        old_text = old_text.strip()\n        new_content = new_content.strip()\n        refusal = _legacy_containment_refusal({\"action\": \"replace\", \"target\": target, \"old_text\": old_text, \"content\": new_content})\n        if refusal:\n            return refusal\n        if not old_text:\n",
        path.name + ":replace",
    )
    text = replace_once(
        text,
        "        if not operations:\n            return {\"success\": False, \"error\": \"operations list is empty.\"}\n",
        "        refusal = _legacy_containment_refusal({\"action\": \"batch\", \"target\": target, \"operations\": operations})\n        if refusal:\n            return refusal\n        if not operations:\n            return {\"success\": False, \"error\": \"operations list is empty.\"}\n",
        path.name + ":batch",
    )
    text = replace_once(
        text,
        "    if action not in {\"add\", \"replace\", \"remove\"}:\n        return None\n\n    try:\n        from tools import write_approval as wa\n",
        "    if action not in {\"add\", \"replace\", \"remove\"}:\n        return None\n\n    refusal = _legacy_containment_refusal({\"action\": action, \"target\": target, \"content\": content, \"old_text\": old_text})\n    if refusal:\n        return json.dumps(refusal, ensure_ascii=False)\n\n    try:\n        from tools import write_approval as wa\n",
        path.name + ":single-gate",
    )
    text = replace_once(
        text,
        "    try:\n        from tools import write_approval as wa\n    except Exception:\n        return None\n\n    label = \"user profile\" if target == \"user\" else \"memory\"\n",
        "    refusal = _legacy_containment_refusal({\"action\": \"batch\", \"target\": target, \"operations\": operations})\n    if refusal:\n        return json.dumps(refusal, ensure_ascii=False)\n    try:\n        from tools import write_approval as wa\n    except Exception:\n        return None\n\n    label = \"user profile\" if target == \"user\" else \"memory\"\n",
        path.name + ":batch-gate",
    )
    text = replace_exact_count(
        text,
        "    return json.dumps(\n        {\"success\": True, \"staged\": True, \"pending_id\": record[\"id\"],\n         \"message\": decision.message},\n        ensure_ascii=False,\n    )\n",
        "    if record.get(\"blocked\"):\n        return json.dumps({\"success\": False, \"done\": True, \"error\": record.get(\"failure_code\"), \"failure_code\": record.get(\"failure_code\")}, ensure_ascii=False)\n    return json.dumps(\n        {\"success\": True, \"staged\": True, \"pending_id\": record[\"id\"],\n         \"message\": decision.message},\n        ensure_ascii=False,\n    )\n",
        2,
        path.name + ":staging-results",
    )
    replay_anchor = "    action = payload.get(\"action\")\n    target = payload.get(\"target\", \"memory\")\n"
    replay_new = "    refusal = _legacy_containment_refusal(payload)\n    if refusal:\n        return refusal\n" + replay_anchor
    text = replace_once(text, replay_anchor, replay_new, path.name + ":replay")
    write_atomic(path, text)


def patch_skill_manager(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    replay_anchor = '''def apply_skill_pending(payload: Dict[str, Any]) -> str:
    """Replay a staged skill write, bypassing the gate. Returns the tool result
    JSON string. Called by the /skills approve handler.
    """
    token = _skill_gate_bypass.set(True)
'''
    replay_new = '''def apply_skill_pending(payload: Dict[str, Any]) -> str:
    """Replay a staged skill write, bypassing the approval gate only."""
    refusal = _legacy_containment_guard(payload)
    if refusal:
        return json.dumps(refusal, ensure_ascii=False)
    token = _skill_gate_bypass.set(True)
'''
    if MARKER in text:
        if replay_new in text:
            return
        write_atomic(
            path,
            replace_once(text, replay_anchor, replay_new, path.name + ":replay"),
        )
        return
    anchor = "# =============================================================================\n# Core actions\n# =============================================================================\n\n\n"
    helper = anchor + f'''# {MARKER}.\n+def _legacy_containment_guard(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:\n+    try:\n+        from tools.legacy_canonical_containment import check_legacy_payload\n+        decision = check_legacy_payload(payload)\n+    except Exception:\n+        marker = payload.get("legacyContainment") if isinstance(payload, dict) else None\n+        if isinstance(marker, dict) and marker.get("recognizedCanonicalAction") is True:\n+            return {{"success": False, "error": "LEGACY_CONTAINMENT_NOT_READY", "failure_code": "LEGACY_CONTAINMENT_NOT_READY"}}\n+        return None\n+    if decision.allowed:\n+        return None\n+    return {{\n+        "success": False, "error": decision.failure_code,\n+        "failure_code": decision.failure_code,\n+    }}\n+\n+\n'''.replace("\n+", "\n")
    text = replace_once(text, anchor, helper, path.name)
    inserts = (
        (
            "def _create_skill(name: str, content: str, category: str = None) -> Dict[str, Any]:\n    \"\"\"Create a new user skill with SKILL.md content.\"\"\"\n",
            "def _create_skill(name: str, content: str, category: str = None) -> Dict[str, Any]:\n    \"\"\"Create a new user skill with SKILL.md content.\"\"\"\n    refusal = _legacy_containment_guard({\"action\": \"create\", \"name\": name, \"content\": content})\n    if refusal:\n        return refusal\n",
            "create",
        ),
        (
            "def _edit_skill(name: str, content: str) -> Dict[str, Any]:\n    \"\"\"Replace the SKILL.md of any existing skill (full rewrite).\"\"\"\n",
            "def _edit_skill(name: str, content: str) -> Dict[str, Any]:\n    \"\"\"Replace the SKILL.md of any existing skill (full rewrite).\"\"\"\n    refusal = _legacy_containment_guard({\"action\": \"edit\", \"name\": name, \"content\": content})\n    if refusal:\n        return refusal\n",
            "edit",
        ),
        (
            "    if not old_string:\n        return {\"success\": False, \"error\": \"old_string is required for 'patch'.\"}\n",
            "    refusal = _legacy_containment_guard({\"action\": \"patch\", \"name\": name, \"old_string\": old_string, \"new_string\": new_string, \"file_path\": file_path})\n    if refusal:\n        return refusal\n    if not old_string:\n        return {\"success\": False, \"error\": \"old_string is required for 'patch'.\"}\n",
            "patch",
        ),
        (
            "def _write_file(name: str, file_path: str, file_content: str) -> Dict[str, Any]:\n    \"\"\"Add or overwrite a supporting file within any skill directory.\"\"\"\n",
            "def _write_file(name: str, file_path: str, file_content: str) -> Dict[str, Any]:\n    \"\"\"Add or overwrite a supporting file within any skill directory.\"\"\"\n    refusal = _legacy_containment_guard({\"action\": \"write_file\", \"name\": name, \"file_path\": file_path, \"file_content\": file_content})\n    if refusal:\n        return refusal\n",
            "write-file",
        ),
    )
    for old, new, label in inserts:
        text = replace_once(text, old, new, path.name + ":" + label)
    gate_anchor = '''    if action not in {"create", "edit", "patch", "delete", "write_file", "remove_file"}:\n        return None\n    if _skill_gate_bypass.get():\n        return None\n'''
    gate_new = '''    if action not in {"create", "edit", "patch", "delete", "write_file", "remove_file"}:\n        return None\n    containment_payload = {"action": action, "name": name, **payload_kwargs}\n    refusal = _legacy_containment_guard(containment_payload)\n    if refusal:\n        return json.dumps(refusal, ensure_ascii=False)\n    if _skill_gate_bypass.get():\n        return None\n'''
    text = replace_once(text, gate_anchor, gate_new, path.name + ":gate")
    stage_anchor = '''    record = wa.stage_write(wa.SKILLS, payload, summary=gist, origin=wa.current_origin())\n    return json.dumps(\n        {"success": True, "staged": True, "pending_id": record["id"],\n'''
    stage_new = '''    record = wa.stage_write(wa.SKILLS, payload, summary=gist, origin=wa.current_origin())\n    if record.get("blocked"):\n        return json.dumps({"success": False, "error": record.get("failure_code"), "failure_code": record.get("failure_code")}, ensure_ascii=False)\n    return json.dumps(\n        {"success": True, "staged": True, "pending_id": record["id"],\n'''
    text = replace_once(text, stage_anchor, stage_new, path.name + ":stage")
    text = replace_once(text, replay_anchor, replay_new, path.name + ":replay")
    write_atomic(path, text)


def patch_background_review(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    anchor = '''    if review_run is not None and review_run.cancel_requested.is_set():\n        finish_background_review_run(agent, review_run)\n        return\n\n    # Local import to avoid a hard circular dep at module load.\n'''
    replacement = f'''    if review_run is not None and review_run.cancel_requested.is_set():\n        finish_background_review_run(agent, review_run)\n        return\n\n    # {MARKER}: strip typed memory-lane turns before prompt construction.\n    try:\n        from tools.legacy_canonical_containment import filter_background_review_messages\n        messages_snapshot = filter_background_review_messages(messages_snapshot)\n    except Exception:\n        # Fail closed for a typed memory-lane turn even if containment import fails.\n        def _recognized_memory_lane(message):\n            if not isinstance(message, dict):\n                return False\n            containers = (message, message.get("metadata"))\n            for container in containers:\n                marker = container.get("legacyContainment") if isinstance(container, dict) else None\n                if isinstance(marker, dict) and marker.get("recognizedCanonicalAction") is True:\n                    return True\n            return False\n        messages_snapshot = [m for m in messages_snapshot if not _recognized_memory_lane(m)]\n\n    # Local import to avoid a hard circular dep at module load.\n'''
    write_atomic(path, replace_once(text, anchor, replacement, path.name))


def patch_social_presence_test(path: Path) -> None:
    """Advance the Slice 14 protected Policy hash after its authorized extension."""
    text = path.read_text(encoding="utf-8")
    old = (
        'ROUTER / "policy.py": '
        '"3eca1aec75716b8a862330f225f29a4c616f807251a88a02ee41417ed2592e1f",'
    )
    new = (
        'ROUTER / "policy.py": '
        '"54db43909d8b066fe96e50be1897167c76f568a071522433f630f7f4345a74db",'
    )
    if new in text:
        return
    write_atomic(path, replace_once(text, old, new, path.name + ":policy-hash"))


def install_modules(source: Path, router_root: Path, hermes_root: Path) -> None:
    for name in (
        "canonical_contracts.py",
        "canonical_authority.py",
        "learning_v2.py",
        "memory_v2.py",
        "privacy_governance.py",
        "slice15b2a_migration.py",
    ):
        shutil.copy2(source / name, router_root / name)
    shutil.copy2(
        source / "legacy_canonical_containment.py",
        hermes_root / "tools" / "legacy_canonical_containment.py",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--router-root", type=Path, required=True)
    parser.add_argument("--hermes-root", type=Path, required=True)
    parser.add_argument("--backup-suffix")
    args = parser.parse_args()
    router = args.router_root.resolve()
    hermes = args.hermes_root.resolve()
    targets = (
        router / "policy.py",
        router / "learning_store.py",
        router / "memory_store.py",
        hermes / "tools" / "write_approval.py",
        hermes / "tools" / "memory_tool.py",
        hermes / "tools" / "skill_manager_tool.py",
        hermes / "agent" / "background_review.py",
        router / "tests" / "test_social_presence.py",
    )
    for target in targets:
        if not target.is_file():
            raise RuntimeError(f"required target missing: {target}")
        backup(target, args.backup_suffix)
    install_modules(Path(__file__).resolve().parent, router, hermes)
    patch_policy(router / "policy.py")
    patch_learning_store(router / "learning_store.py")
    patch_memory_store(router / "memory_store.py")
    patch_write_approval(hermes / "tools" / "write_approval.py")
    patch_memory_tool(hermes / "tools" / "memory_tool.py")
    patch_skill_manager(hermes / "tools" / "skill_manager_tool.py")
    patch_background_review(hermes / "agent" / "background_review.py")
    patch_social_presence_test(router / "tests" / "test_social_presence.py")


if __name__ == "__main__":
    main()
