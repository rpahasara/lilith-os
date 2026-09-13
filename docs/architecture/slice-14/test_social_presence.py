"""Slice 14 Social Cognition + Presence contract tests (offline, deterministic)."""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import re
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lilith_router import config as router_config
from lilith_router import gateway_integration as gateway
from lilith_router import presence_contract as presence
from lilith_router import social_cognition as social


HERE = Path(__file__).resolve()
ROUTER = HERE.parents[1]
BUILD_ROOT = HERE.parents[2]

PROTECTED_HASHES = {
    ROUTER / "policy.py": "3eca1aec75716b8a862330f225f29a4c616f807251a88a02ee41417ed2592e1f",
    ROUTER / "social_guard.py": "edbc7eec6dc9e2b73463e3a65d563486f31eb2e2f894d75cdc7b370dcf55033e",
    ROUTER / "world_context.py": "46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104",
    BUILD_ROOT / "SOUL.md": "d082db5aa1a8745460c1c3a3edebaf6fcd196336f5e1a5e8ef7108303bda5ccd",
    BUILD_ROOT / "hermes-agent" / "gateway" / "run.py": "2774eee5e585d80cbb45f5865f2718832c2ec86fdfddf8ead1f781e9b21c2553",
    BUILD_ROOT / "hermes-agent" / "hermes_cli" / "personality.py": "520cf5dbcda99247e39fecf520eac897d270e28dd26908a5c1686131a0d5f6b0",
}
ENFORCE_REPLY_HASH = "ef91937b02ac6b6bbf642dcd8c50ef2773177f6e7e9dcc0bb2a0967dbd7473eb"
PROTECTED_ARCHIVE_MEMBERS = {
    BUILD_ROOT / "SOUL.md": "SOUL.md",
    BUILD_ROOT / "hermes-agent" / "gateway" / "run.py": "hermes-agent/gateway/run.py",
    BUILD_ROOT / "hermes-agent" / "hermes_cli" / "personality.py": "hermes-agent/hermes_cli/personality.py",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function_hash(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        item for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    block = "".join(source.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])
    return hashlib.sha256(block.encode("utf-8")).hexdigest()


def build(message: str, channel: str = "lilith_os", correlation: str = "sc.test"):
    social_input = social.build_social_input(message, correlation, channel)
    snapshot = social.build_social_context(social_input)
    hint = presence.derive_presence_hint(snapshot)
    return social_input, snapshot, hint


def roles(snapshot):
    return [p for p in snapshot["participants"] if p["participantKind"] == "THIRD_PARTY"]


def cue_types(snapshot):
    return {cue["cueType"] for cue in snapshot["socialCues"]}


class TestSocialTurnEvidence(unittest.TestCase):
    def test_social_input_separates_session_actor_from_turn_owner(self):
        social_input, _, _ = build("hello")
        actor = social_input["sessionActor"]
        evidence = social_input["socialTurnEvidence"]
        self.assertEqual(actor["participantKind"], "CURRENT_TURN_SENDER")
        self.assertEqual(actor["identityStatus"], "SESSION_BOUND")
        self.assertEqual(actor["bindingType"], "CURRENT_TURN_SENDER_BINDING")
        self.assertEqual(evidence["sourceOwner"], "TURN")
        self.assertNotIn(actor["actorRef"], evidence["sourceRefs"])
        self.assertNotIn("CURRENT_USER", json.dumps(social_input))

    def test_turn_evidence_has_no_router_metadata(self):
        social_input, _, _ = build("my manager said hello", channel="telegram")
        evidence = social_input["socialTurnEvidence"]
        self.assertNotIn("channel", evidence)
        self.assertNotIn("sessionActor", evidence)
        self.assertNotIn("session", json.dumps(evidence).lower())

    def test_literal_role_requires_direct_source_range(self):
        message = "I spoke with my manager today."
        social_input, _, _ = build(message)
        role_item = next(
            item for item in social_input["socialTurnEvidence"]["evidenceItems"]
            if item["evidenceType"] == social.E_ROLE
        )
        span = role_item["sourceRange"]
        self.assertEqual(message[span["start"]:span["endExclusive"]], "manager")
        broken = copy.deepcopy(social_input["socialTurnEvidence"])
        broken["evidenceItems"][0]["sourceRange"] = {"start": 0, "endExclusive": 1}
        with self.assertRaises(social.SocialValidationError):
            social.validate_social_turn_evidence(broken, message)

    def test_evidence_is_bounded(self):
        message = " ".join(["my manager"] * 20)
        evidence = social.build_social_turn_evidence(message, "sc.bound")
        self.assertLessEqual(len(evidence["evidenceItems"]), 8)

    def test_only_approved_evidence_types_are_emitted(self):
        message = (
            "No, that's my sister, not my coworker. Reply formally, then write casually. "
            "Make this funny. Can you reassure me? I'm frustrated. This bug is trolling me 😂"
        )
        evidence = social.build_social_turn_evidence(message, "sc.types")
        emitted = {item["evidenceType"] for item in evidence["evidenceItems"]}
        self.assertTrue(emitted.issubset(social._EVIDENCE_TYPES))
        for removed in (
            "EXPLICIT_BREVITY_REQUEST", "EXPLICIT_DETAIL_REQUEST", "EXPLICIT_WARMTH_REQUEST",
            "THANKS", "APOLOGY", "CASUAL_ADDRESS", "THIRD_PARTY_REFERENCE",
        ):
            self.assertNotIn(removed, emitted)


class TestParticipantsAndAudience(unittest.TestCase):
    def test_manager_recipient_is_professional(self):
        _, snapshot, hint = build("Help me write a message to my manager.")
        manager = roles(snapshot)[0]
        self.assertEqual(manager["literalRoleLabel"], "manager")
        self.assertEqual(manager["identityStatus"], "ROLE_ONLY")
        self.assertEqual(snapshot["audienceContext"]["audienceRef"], manager["participantRef"])
        self.assertEqual(snapshot["audienceContext"]["audienceContextClass"], "PROFESSIONAL")
        self.assertEqual(hint["formalityHint"], "PROFESSIONAL")

    def test_recruiter_recipient_is_professional(self):
        _, snapshot, _ = build("What should I say to the recruiter?")
        self.assertEqual(roles(snapshot)[0]["literalRoleLabel"], "recruiter")
        self.assertEqual(snapshot["audienceContext"]["audienceContextClass"], "PROFESSIONAL")

    def test_incidental_manager_is_not_audience(self):
        _, snapshot, hint = build("My manager broke production 😂")
        self.assertEqual(roles(snapshot)[0]["literalRoleLabel"], "manager")
        self.assertNotIn("audienceContext", snapshot)
        self.assertEqual(hint["formalityHint"], "NEUTRAL")

    def test_incoming_manager_message_is_not_audience(self):
        _, snapshot, hint = build("I got a message from my manager.")
        self.assertEqual(roles(snapshot)[0]["literalRoleLabel"], "manager")
        self.assertNotIn("audienceContext", snapshot)
        self.assertEqual(hint["formalityHint"], "NEUTRAL")

    def test_partner_is_literal_and_unclassified(self):
        _, snapshot, _ = build("My partner said this.")
        partner = roles(snapshot)[0]
        self.assertEqual(partner["literalRoleLabel"], "partner")
        self.assertEqual(partner["participantKind"], "THIRD_PARTY")
        self.assertEqual(partner["identityStatus"], "ROLE_ONLY")
        encoded = json.dumps(snapshot)
        self.assertNotIn("relationship", encoded.lower())
        self.assertNotIn('"PERSONAL"', encoded)
        self.assertNotIn('"PROFESSIONAL"', json.dumps(partner))

    def test_ambiguous_recipient_syntax_remains_unspecified(self):
        _, snapshot, hint = build("Could this go to my manager?")
        self.assertNotIn("audienceContext", snapshot)
        self.assertEqual(hint["formalityHint"], "NEUTRAL")

    def test_assistant_self_is_not_emitted_without_consumer(self):
        _, snapshot, _ = build("What would you say to my manager?")
        self.assertNotIn("ASSISTANT_SELF", {p["participantKind"] for p in snapshot["participants"]})

    def test_only_exact_professional_whitelist(self):
        self.assertEqual(social._PROFESSIONAL_ROLES, frozenset({"manager", "recruiter"}))


class TestCuesAndPresence(unittest.TestCase):
    def test_explicit_difficulty_is_narrow_supportive_cue(self):
        _, snapshot, hint = build("I'm frustrated with this issue.")
        self.assertEqual(cue_types(snapshot), {"EXPLICIT_DIFFICULTY_SELF_REPORT"})
        self.assertEqual(hint["socialTone"], "SUPPORTIVE")
        encoded = json.dumps(snapshot).lower()
        self.assertNotIn('"emotion"', encoded)
        self.assertNotIn('"mood"', encoded)
        self.assertNotIn("user_asserted_affect", encoded)

    def test_explicit_support_is_supportive(self):
        _, snapshot, hint = build("Can you reassure me about this?")
        self.assertEqual(cue_types(snapshot), {"EXPLICIT_SUPPORT_REQUEST"})
        self.assertEqual(hint["socialTone"], "SUPPORTIVE")

    def test_explicit_humor_permits_playfulness_without_text(self):
        social_input, snapshot, hint = build("Make this funny.")
        self.assertEqual(cue_types(snapshot), {"EXPLICIT_HUMOR_REQUEST"})
        self.assertEqual(hint["playfulness"], "PERMITTED")
        self.assertNotIn("final_response", social_input)
        self.assertNotIn("final_response", snapshot)
        self.assertNotIn("final_response", hint)

    def test_playful_context_requires_combined_evidence(self):
        _, snapshot, hint = build("Bro, this bug is trolling me 😂")
        self.assertIn("PLAYFUL_CONTEXT_CUE", cue_types(snapshot))
        self.assertEqual(hint["playfulness"], "PERMITTED")
        _, lexical_only, lexical_hint = build("Bro, this bug is trolling me", correlation="sc.lex")
        self.assertNotIn("PLAYFUL_CONTEXT_CUE", cue_types(lexical_only))
        self.assertEqual(lexical_hint["playfulness"], "RESTRAINED")
        _, emoji_only, emoji_hint = build("That happened 😂", correlation="sc.emoji")
        self.assertNotIn("PLAYFUL_CONTEXT_CUE", cue_types(emoji_only))
        self.assertEqual(emoji_hint["playfulness"], "RESTRAINED")

    def test_wtf_has_no_affect_or_playfulness(self):
        _, snapshot, hint = build("wtf")
        self.assertEqual(snapshot["socialCues"], [])
        self.assertEqual(hint["socialTone"], "NEUTRAL")
        self.assertEqual(hint["playfulness"], "RESTRAINED")
        self.assertNotIn("angry", json.dumps(snapshot).lower())

    def test_formality_constraints_have_presence_consumers(self):
        _, formal, formal_hint = build("Reply formally.")
        self.assertEqual(formal["explicitInteractionConstraints"][0]["value"], "PROFESSIONAL")
        self.assertEqual(formal_hint["formalityHint"], "PROFESSIONAL")
        _, casual, casual_hint = build("Reply casually.", correlation="sc.casual")
        self.assertEqual(casual["explicitInteractionConstraints"][0]["value"], "CASUAL")
        self.assertEqual(casual_hint["formalityHint"], "NEUTRAL")

    def test_contradictory_formality_is_observable_and_unresolved(self):
        _, snapshot, hint = build("Reply formally but write casually.")
        self.assertEqual(snapshot["conflicts"][0]["conflictType"], "CONTRADICTORY_FORMALITY_REQUESTS")
        self.assertEqual(snapshot["informationNeeded"][0]["code"], "FORMALITY_REQUEST_UNCLEAR")
        self.assertEqual(hint["formalityHint"], "NEUTRAL")

    def test_current_turn_role_correction_has_no_world_semantics(self):
        _, snapshot, _ = build("No, that's my sister, not my coworker.")
        self.assertEqual([p["literalRoleLabel"] for p in roles(snapshot)], ["sister"])
        self.assertIn("USER_CORRECTION", cue_types(snapshot))
        self.assertEqual(snapshot["conflicts"][0]["conflictType"], "CURRENT_TURN_ROLE_CORRECTION")
        encoded = json.dumps(snapshot)
        self.assertNotIn("WORLD", encoded)
        self.assertNotIn("reconciliation", encoded.lower())

    def test_supportive_and_professional_are_orthogonal(self):
        _, snapshot, hint = build("I'm frustrated. Help me write a message to my manager.")
        self.assertEqual(snapshot["audienceContext"]["audienceContextClass"], "PROFESSIONAL")
        self.assertEqual(hint["socialTone"], "SUPPORTIVE")
        self.assertEqual(hint["formalityHint"], "PROFESSIONAL")
        self.assertEqual(hint["playfulness"], "RESTRAINED")
        self.assertNotIn("interactionStance", hint)

    def test_presence_defaults_use_no_source_refs(self):
        _, _, hint = build("hello")
        self.assertEqual(hint["sourceRefs"], [])

    def test_presence_provenance_is_exactly_causal(self):
        _, snapshot, hint = build("I'm frustrated. Help me write a message to my manager.")
        expected = set()
        expected.update(next(c for c in snapshot["socialCues"] if c["cueType"] == social.C_DIFFICULTY)["sourceRefs"])
        expected.update(snapshot["audienceContext"]["sourceRefs"])
        self.assertEqual(set(hint["sourceRefs"]), expected)

    def test_presence_rejects_duplicate_provenance(self):
        _, snapshot, hint = build("I'm frustrated.")
        broken = copy.deepcopy(hint)
        broken["sourceRefs"].append(broken["sourceRefs"][0])
        with self.assertRaises(presence.PresenceValidationError):
            presence.validate_presence_hint(broken, snapshot)


class TestClosedSchemas(unittest.TestCase):
    def test_turn_only_runtime_schema_has_no_world_fields(self):
        _, snapshot, _ = build("my manager said hello")
        encoded = json.dumps(snapshot)
        for forbidden in ("WORLD_REFERENCED", "worldReferences", "epistemic", "lifecycle"):
            self.assertNotIn(forbidden, encoded)
        self.assertEqual(snapshot["sourceAvailability"], "TURN_ONLY_BY_DESIGN")

    def test_no_relationship_affect_personality_or_action_state(self):
        _, snapshot, hint = build("my partner said this")
        encoded = json.dumps({"snapshot": snapshot, "hint": hint}).lower()
        for forbidden in (
            "relationship", "trust", "familiarity", "closeness", "friendship",
            "emotion", "mood", "sentiment", "valence", "arousal", "personality",
            "goal", "task", "draft", "execution",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_presence_has_exact_semantic_fields_and_no_warm(self):
        _, _, hint = build("hello")
        self.assertEqual(set(hint), {
            "schemaVersion", "correlationId", "socialSemanticFingerprint",
            "socialTone", "formalityHint", "playfulness", "sourceRefs",
        })
        self.assertNotEqual(hint["socialTone"], "WARM")
        broken = dict(hint, socialTone="WARM")
        _, snapshot, _ = build("hello", correlation="sc.warm")
        broken["correlationId"] = "sc.warm"
        broken["socialSemanticFingerprint"] = snapshot["socialSemanticFingerprint"]
        with self.assertRaises(presence.PresenceValidationError):
            presence.validate_presence_hint(broken, snapshot)

    def test_presence_rejects_renderer_controls(self):
        _, snapshot, hint = build("hello")
        for field in (
            "emotion", "affect", "animation", "pose", "bone", "blendshape",
            "camera", "gaze", "timing", "intensity", "energy", "responsePhase",
        ):
            broken = copy.deepcopy(hint)
            broken[field] = "x"
            with self.assertRaises(presence.PresenceValidationError, msg=field):
                presence.validate_presence_hint(broken, snapshot)

    def test_social_validator_rejects_forbidden_meaning(self):
        _, snapshot, _ = build("hello")
        mutations = (
            ("emotion", "angry"), ("relationshipClass", "PERSONAL"),
            ("worldReferences", []), ("personalityProfile", {}),
            ("final_response", "changed"), ("goals", []),
        )
        for field, value in mutations:
            broken = copy.deepcopy(snapshot)
            broken[field] = value
            with self.assertRaises(social.SocialValidationError, msg=field):
                social.validate_social_context(broken)

    def test_social_validator_rejects_current_user_and_world_referenced(self):
        _, snapshot, _ = build("hello")
        for value in ("CURRENT_USER", "WORLD_REFERENCED"):
            broken = copy.deepcopy(snapshot)
            broken["participants"][0]["participantKind"] = value
            with self.assertRaises(social.SocialValidationError):
                social.validate_social_context(broken)

    def test_social_validator_rejects_unsupported_professional_audience(self):
        _, snapshot, _ = build("reply to my sister")
        self.assertEqual(snapshot["audienceContext"]["audienceContextClass"], "UNSPECIFIED")
        broken = copy.deepcopy(snapshot)
        broken["audienceContext"]["audienceContextClass"] = "PROFESSIONAL"
        with self.assertRaises(social.SocialValidationError):
            social.validate_social_context(broken)

    def test_social_validator_rejects_verbosity(self):
        _, snapshot, _ = build("hello")
        broken = copy.deepcopy(snapshot)
        broken["explicitInteractionConstraints"] = [{
            "dimension": "VERBOSITY", "value": "BRIEF",
            "sourceRefs": [snapshot["turnRef"]],
        }]
        broken["socialSemanticFingerprint"] = social.semantic_fingerprint(broken)
        with self.assertRaises(social.SocialValidationError):
            social.validate_social_context(broken)

    def test_validator_does_not_repair(self):
        _, snapshot, _ = build("hello")
        broken = copy.deepcopy(snapshot)
        broken["participants"][0]["identityStatus"] = "AUTHENTICATED"
        before = copy.deepcopy(broken)
        with self.assertRaises(social.SocialValidationError):
            social.validate_social_context(broken)
        self.assertEqual(broken, before)


class TestFingerprintAndTrace(unittest.TestCase):
    def test_home_telegram_semantic_parity(self):
        _, home, home_hint = build("Help me write a message to my manager.", "lilith_os", "sc.home")
        _, telegram, telegram_hint = build("Help me write a message to my manager.", "telegram", "sc.tg")
        self.assertEqual(home["socialSemanticFingerprint"], telegram["socialSemanticFingerprint"])
        self.assertNotEqual(home["channel"], telegram["channel"])
        self.assertNotEqual(home["turnRef"], telegram["turnRef"])
        self.assertEqual(
            [(p["participantKind"], p["identityStatus"], p.get("literalRoleLabel")) for p in home["participants"]],
            [(p["participantKind"], p["identityStatus"], p.get("literalRoleLabel")) for p in telegram["participants"]],
        )
        self.assertEqual(home["audienceContext"]["audienceContextClass"], telegram["audienceContext"]["audienceContextClass"])
        self.assertEqual(cue_types(home), cue_types(telegram))
        self.assertEqual(
            (home_hint["socialTone"], home_hint["formalityHint"], home_hint["playfulness"]),
            (telegram_hint["socialTone"], telegram_hint["formalityHint"], telegram_hint["playfulness"]),
        )

    def test_fingerprint_excludes_offsets_and_reference_ids(self):
        _, first, _ = build("my manager said this", correlation="sc.one")
        _, second, _ = build("please note that my manager said this", channel="telegram", correlation="sc.two")
        self.assertEqual(first["socialSemanticFingerprint"], second["socialSemanticFingerprint"])

    def test_trace_omits_raw_text_roles_names_and_source_ranges(self):
        raw = "Help Alice write a message to my manager at alice@example.com"
        _, snapshot, hint = build(raw)
        trace = social.build_trace(snapshot, hint, duration_ms=3)
        encoded = json.dumps(trace).lower()
        for forbidden in ("alice", "manager", "example.com", "sourcerange", raw.lower()):
            self.assertNotIn(forbidden, encoded)
        self.assertEqual(trace["lane"], "social_cognition")

    def test_trace_is_non_cot_and_bounded(self):
        _, snapshot, hint = build("Make this funny.")
        trace = social.build_trace(snapshot, hint, duration_ms=1)
        encoded = json.dumps(trace).lower()
        for forbidden in ("chain-of-thought", "scratchpad", "reasoning", "analysis"):
            self.assertNotIn(forbidden, encoded)


class TestAuthorityAndSideEffects(unittest.TestCase):
    def test_new_modules_import_no_world_memory_tools_connectors_or_db(self):
        for module in (social, presence):
            tree = ast.parse(inspect.getsource(module))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            for forbidden in (
                "requests", "sqlite3", "gateway", "run_agent", "world_context", "social_guard",
                "policy", "memory", "tools", "connectors",
            ):
                self.assertNotIn(forbidden, imported)

    def test_no_personality_or_interaction_style_runtime_owner(self):
        classes = set()
        for module in (social, presence):
            tree = ast.parse(inspect.getsource(module))
            classes.update(node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
        self.assertNotIn("PersonalityProfile", classes)
        self.assertNotIn("InteractionStyle", classes)

    def test_outputs_have_no_prompt_or_final_response(self):
        values = build("Make this funny for my manager.")
        encoded = json.dumps(values).lower()
        self.assertNotIn('"prompt"', encoded)
        self.assertNotIn('"final_response"', encoded)

    def test_protected_files_match_starting_hashes(self):
        for path, expected in PROTECTED_HASHES.items():
            if path.exists():
                actual = sha256(path)
            else:
                archive_path = BUILD_ROOT / "protected-source.tgz"
                member = PROTECTED_ARCHIVE_MEMBERS.get(path)
                self.assertTrue(archive_path.exists() and member, path)
                with tarfile.open(archive_path, "r:gz") as archive:
                    payload = archive.extractfile(member).read()
                actual = hashlib.sha256(payload).hexdigest()
            self.assertEqual(actual, expected, path)

    def test_enforce_reply_function_is_byte_identical(self):
        self.assertEqual(function_hash(ROUTER / "gateway_integration.py", "enforce_reply"), ENFORCE_REPLY_HASH)

    def test_run_keeps_load_soul_identity_true(self):
        text = (BUILD_ROOT / "hermes-agent" / "gateway" / "run.py").read_text(encoding="utf-8")
        self.assertIn("load_soul_identity=True", text)

    def test_slice13_turn_evidence_owner_file_is_unchanged(self):
        self.assertEqual(sha256(ROUTER / "world_context.py"), PROTECTED_HASHES[ROUTER / "world_context.py"])

    def test_config_uses_unambiguous_shadow_names(self):
        config_text = (ROUTER / "config.py").read_text(encoding="utf-8")
        yaml_text = (ROUTER / "router.yaml").read_text(encoding="utf-8")
        self.assertIn("social_cognition_enabled", config_text)
        self.assertIn("social_cognition_mode", config_text)
        self.assertIn("social_cognition_enabled: true", yaml_text)
        self.assertIn("social_cognition_mode: shadow", yaml_text)
        self.assertIsNone(re.search(r"(?m)^social_enabled\s*:", yaml_text))
        self.assertIsNone(re.search(r"(?m)^social_mode\s*:", yaml_text))

    def test_config_enables_only_shadow_on_existing_cognitive_channels(self):
        cfg = router_config.RouterConfig(
            social_cognition_enabled=True,
            social_cognition_mode="shadow",
            cognitive_channels=["lilith_os", "telegram"],
        )
        self.assertTrue(cfg.social_cognition_is_active("lilith_os", "home"))
        self.assertTrue(cfg.social_cognition_is_active("telegram", "42"))
        self.assertFalse(cfg.social_cognition_is_active("discord", "42"))
        cfg.social_cognition_mode = "live"
        self.assertFalse(cfg.social_cognition_is_active("lilith_os", "home"))
        cfg.social_cognition_mode = "future-mode"
        self.assertFalse(cfg.social_cognition_is_active("lilith_os", "home"))

    def test_observer_failure_is_fail_open_and_trace_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "decisions.log"

            class Config:
                def social_cognition_is_active(self, platform, chat_id):
                    return True

                def resolved_log_path(self):
                    return trace_path

            raw = "private user text for my manager at alice@example.com"
            with mock.patch.object(
                social, "build_social_input", side_effect=RuntimeError("private failure detail")
            ):
                result = gateway._observe_social_cognition(
                    Config(), "lilith_os", "home", "lilith_os:home", raw
                )
            self.assertIsNone(result)
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace["validation_status"], "INVALID")
            self.assertEqual(trace["fallback_reason"], "RuntimeError")
            encoded = json.dumps(trace).lower()
            for forbidden in (raw.lower(), "manager", "alice", "example.com", "failure detail"):
                self.assertNotIn(forbidden, encoded)

    def test_observer_is_before_existing_lanes_and_cannot_override(self):
        text = (ROUTER / "gateway_integration.py").read_text(encoding="utf-8")
        start = text.index("# -- Slice 14 social cognition observer")
        end = text.index("# -- end Slice 14 social cognition observer --")
        planning = text.index("# -- Slice 12 planning lane")
        block = text[start:end]
        self.assertLess(start, planning)
        for forbidden in (
            "final_response", "turn_route =", "combined_ephemeral =", "return {",
            "_social_guard", "_policy", "load_soul_identity",
        ):
            self.assertNotIn(forbidden, block)


if __name__ == "__main__":
    unittest.main()
