# -*- coding: utf-8 -*-
"""Offline unit tests for the Slice 7.2 World-Model-first cognitive context.

Run:  python -m lilith_router.tests.test_world_context
No network, no secrets. Exits non-zero on any failure. All HTTP is monkeypatched.
"""
from __future__ import annotations

import sys

from lilith_router import world_context as wc

_failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        _failures.append(name)


# ── canned World Model data ─────────────────────────────────────────────────

def _belief(eid, pred, val, life="ACTIVE", epi="OBSERVED", conf=0.9, tier="high",
            basis="observed+2corrob", src="LIVE_CONNECTOR", sid="career-events"):
    return {
        "key": "career.application:%s:%s" % (eid, pred),
        "entity_type": "career.application", "entity_id": str(eid),
        "predicate": pred, "value": val,
        "lifecycle_state": life, "epistemic_state": epi,
        "confidence": {"value": conf, "tier": tier, "basis": basis},
        "provenance": [{"source_class": src, "source_id": sid, "freshness": "fresh"}],
    }


def _world(beliefs, conflicted=0, stale=0):
    return {"beliefs": beliefs,
            "meta": {"total": len(beliefs), "conflicted": conflicted, "stale": stale,
                     "last_reconciled_at": "2026-09-07T23:13:57+05:30"}}


def _install_fake(world_by_query=None, apps=None, tasks=None, drafts=None,
                  post_result=("ok",)):
    """Monkeypatch wc._get_json / wc._post_draft with canned data."""
    world_by_query = world_by_query or {}

    def fake_get(path, timeout=wc._GET_TIMEOUT):
        if path.startswith("/os/world"):
            # crude query parse: entity_id present?
            if "entity_id=" in path:
                eid = path.split("entity_id=")[1].split("&")[0]
                return world_by_query.get(("id", eid), world_by_query.get("all"))
            if "entity_type=career.application" in path:
                return world_by_query.get("career", world_by_query.get("all"))
            return world_by_query.get("all")
        if path.startswith("/career/applications"):
            return {"applications": apps or []}
        if path.startswith("/os/tasks"):
            return {"tasks": tasks or []}
        if path.startswith("/os/drafts"):
            return {"drafts": drafts or []}
        return None

    wc._get_json = fake_get
    if post_result == ("ok",):
        def fake_post(payload):
            return {"draft": {"draftId": payload["draftId"], "kind": payload["kind"],
                              "status": "created", "target": payload["target"],
                              "subject": payload["subject"], "body": payload["body"]},
                    "created": True}
        wc._post_draft = fake_post
    else:
        wc._post_draft = lambda payload: post_result


# ── intent detection ────────────────────────────────────────────────────────

def test_intent():
    i = wc.detect_intent("Create a follow-up draft for application 14, but do not send it")
    check("07 create-draft verb -> durable draft intent", i["draft"] and i["app_id"] == "14" and not i["example_only"])

    i = wc.detect_intent("write me an example follow-up email")
    check("08 example-email verb -> NOT a durable draft", not i["draft"] and i["example_only"])

    i = wc.detect_intent("What tasks or approvals are pending right now?")
    check("09a pending question detected", i["pending"])

    i = wc.detect_intent("Tell me what you currently believe about my job applications, "
                         "and distinguish confirmed facts, observations, conflicts, and unknowns")
    check("01a belief question detected (no id)", i["belief"] and i["app_id"] is None)

    i = wc.detect_intent("What do you know about application 14, and where did that information come from?")
    check("02a belief+provenance question detected (id 14)", i["belief"] and i["app_id"] == "14")


# ── World-Model-first grounding ─────────────────────────────────────────────

def test_world_sufficient():
    _install_fake(world_by_query={"career": _world([
        _belief(14, "company", "Type B"),
        _belief(14, "role", "Security Engineer (Cloud & AI Focus)"),
    ])})
    intent = wc.detect_intent("what do you currently believe about my job applications?")
    suffix, action = wc.build_grounding("what do you currently believe about my job applications?",
                                        "lilith_os:home", intent, do_write=True)
    check("01 world-first policy present", "World-Model-first" in suffix and "do NOT search" in suffix)
    check("01 beliefs injected (sufficient -> no rummage needed)", "WORLD MODEL BELIEFS" in suffix and "Type B" in suffix)
    check("06 provenance preserved", "LIVE_CONNECTOR" in suffix and "career-events" in suffix)
    check("01 no draft side effect on a read", action is None)


def test_unknown():
    _install_fake(world_by_query={("id", "99"): _world([]), "all": _world([])})
    intent = wc.detect_intent("what is my follow-up status for application 99?")
    suffix, _ = wc.build_grounding("what is my follow-up status for application 99?",
                                   "telegram:123", intent, do_write=True)
    check("03 UNKNOWN focus -> no beliefs recorded", "no beliefs are recorded" in suffix)
    check("03 UNKNOWN policy present", "UNKNOWN:" in suffix and "not known" in suffix)


def test_stale():
    _install_fake(world_by_query={("id", "14"): _world(
        [_belief(14, "last_activity", "2026-08-24", life="STALE")], stale=1)})
    intent = {"any": True, "belief": True, "draft": False, "pending": False,
              "example_only": False, "app_id": "14"}
    suffix, _ = wc.build_grounding("belief about 14", "lilith_os:home", intent, do_write=False)
    check("04 STALE surfaced in belief + meta", "lifecycle=STALE" in suffix and "stale=1" in suffix)
    check("04 STALE policy present", "STALE:" in suffix)


def test_conflicted():
    _install_fake(world_by_query={("id", "14"): _world(
        [_belief(14, "company", "Type B", life="CONFLICTED")], conflicted=1)})
    intent = {"any": True, "belief": True, "draft": False, "pending": False,
              "example_only": False, "app_id": "14"}
    suffix, _ = wc.build_grounding("belief about 14", "lilith_os:home", intent, do_write=False)
    check("05 CONFLICTED surfaced", "lifecycle=CONFLICTED" in suffix and "conflicted=1" in suffix)
    _norm = " ".join(suffix.split())
    check("05 CONFLICTED policy (expose both) present",
          "CONFLICTED:" in suffix and "competing evidence" in _norm and "do not silently choose" in _norm)


def test_topk():
    many = [_belief(i, "p%d" % i, "v%d" % i) for i in range(20)]
    world = _world(many)
    block, total = wc.build_belief_block(world, focus_entity_id=None, topk=wc.TOPK)
    check("06 bounded top-k = 12 lines", block.count("\n- ") == wc.TOPK)
    check("06 top-k header shows 12 of 20", "showing 12 of 20" in block and total == 20)


def test_pending():
    _install_fake(
        tasks=[{"taskId": "t1", "title": "Draft an application follow-up",
                "status": "waiting_for_approval", "approvalState": "required"},
               {"taskId": "t2", "title": "done", "status": "succeeded", "approvalState": "approved"}],
        drafts=[{"draftId": "d.os2.14.abc", "kind": "career_followup", "status": "created",
                 "target": {"type": "application", "id": "14"}, "subject": "Following up"}],
    )
    block = wc.build_pending_block()
    check("10 pending from durable tasks", "TASK t1" in block and "waiting_for_approval" in block)
    check("10 terminal task excluded", "t2" not in block)
    check("10 created draft listed as durable pending", "DRAFT d.os2.14.abc" in block and "UNSENT" in block)
    check("10 pending sourced from durable stores only", "/os/tasks and /os/drafts" in block)


def test_draft_create_durable():
    _install_fake(apps=[{"id": "14", "company": "Type B", "role_title": "Security Engineer (Cloud & AI Focus)"}])
    intent = wc.detect_intent("Create a follow-up draft for application 14, but do not send it")
    suffix, action = wc.build_grounding("Create a follow-up draft for application 14, but do not send it",
                                        "lilith_os:home", intent, do_write=True)
    check("11 create-draft -> DURABLE ACTION RESULT", "DURABLE ACTION RESULT" in suffix and "UNSENT" in suffix)
    check("11 durable draft returned (id targets app 14)",
          action is not None and str(action.get("draftId", "")).startswith("d.os2.14.")
          and (action.get("target") or {}).get("id") == "14")
    check("11 no send claim allowed", "Do not claim it was sent" in suffix and "NOT emailed or sent" in suffix)


def test_no_prose_persistence():
    _install_fake(apps=[{"id": "14", "company": "Type B", "role_title": "Sec Eng"}], post_result=None)
    intent = wc.detect_intent("save a follow-up draft for application 14")
    suffix, action = wc.build_grounding("save a follow-up draft for application 14",
                                        "lilith_os:home", intent, do_write=True)
    check("12 write not confirmed -> do NOT claim saved", "could not save the draft" in suffix and "do NOT claim it was saved" in suffix)
    check("12 no fabricated durable object", action is None)


def test_transport_parity():
    world = {"career": _world([_belief(14, "company", "Type B")])}
    _install_fake(world_by_query=world)
    msg = "what do you know about my applications?"
    intent_a = wc.detect_intent(msg)
    intent_b = wc.detect_intent(msg)
    check("13 detect_intent transport-agnostic", intent_a == intent_b)
    s_home, _ = wc.build_grounding(msg, "lilith_os:home", wc.detect_intent(msg), do_write=True)
    s_tele, _ = wc.build_grounding(msg, "telegram:999", wc.detect_intent(msg), do_write=True)
    check("13 Home and Telegram get identical belief grounding", s_home == s_tele)


# ── Slice 7.3 deterministic de-dup ──────────────────────────────────────────

def _followup(did, app="14", status="created", kind="career_followup"):
    return {"draftId": did, "kind": kind, "status": status,
            "target": {"type": "application", "id": app},
            "subject": "Following up", "body": "Hello, following up."}


def _track_posts(existing_drafts, apps=None):
    """Install fakes; return a list that records every _post_draft call."""
    posts = []
    _install_fake(apps=apps or [{"id": "14", "company": "Type B", "role_title": "Sec Eng"},
                                {"id": "15", "company": "Zone24X7", "role_title": "DevOps"}],
                  drafts=existing_drafts)
    def rec(payload):
        posts.append(payload)
        return {"draft": {"draftId": payload["draftId"], "kind": payload["kind"],
                          "status": "created", "target": payload["target"],
                          "subject": payload["subject"], "body": payload["body"]},
                "created": True}
    wc._post_draft = rec
    return posts


def _draft_intent(app_id):
    return {"any": True, "belief": False, "draft": True, "pending": False,
            "example_only": False, "app_id": app_id}


def test_dedup_reuse_single():
    posts = _track_posts([_followup("d.os2.14.aaa")])
    suffix, action = wc.build_grounding("create a follow-up draft for application 14",
                                        "lilith_os:home", _draft_intent("14"), do_write=True, dedup=True)
    check("D1 reuse: no new draft created (0 posts)", len(posts) == 0)
    check("D1 reuse: existing id reported", action is not None and action.get("draftId") == "d.os2.14.aaa" and "existing draft reused" in suffix)


def test_dedup_home_then_telegram():
    # First request: no existing -> creates.
    posts1 = _track_posts([])
    _s1, a1 = wc.build_grounding("create a follow-up draft for application 14",
                                 "lilith_os:home", _draft_intent("14"), do_write=True, dedup=True)
    # Second request from Telegram: the created draft now exists -> reuse, no 2nd post.
    posts2 = _track_posts([_followup("d.os2.14.aaa")])
    _s2, a2 = wc.build_grounding("create a follow-up draft for application 14",
                                 "telegram:999", _draft_intent("14"), do_write=True, dedup=True)
    check("D2 Home creates once", len(posts1) == 1 and a1 is not None)
    check("D2 Telegram reuses (no 2nd draft)", len(posts2) == 0 and a2 is not None and a2.get("draftId") == "d.os2.14.aaa")


def test_dedup_repeated_identical():
    posts = _track_posts([_followup("d.os2.14.aaa")])
    for _ in range(3):
        wc.build_grounding("create a follow-up draft for application 14",
                           "lilith_os:home", _draft_intent("14"), do_write=True, dedup=True)
    check("D3 repeated identical -> still no new draft", len(posts) == 0)


def test_dedup_different_app():
    posts = _track_posts([_followup("d.os2.14.aaa", app="14")])
    _s, a = wc.build_grounding("create a follow-up draft for application 15",
                               "lilith_os:home", _draft_intent("15"), do_write=True, dedup=True)
    check("D4 different app -> new draft created", len(posts) == 1 and (a or {}).get("target", {}).get("id") == "15")


def test_dedup_different_kind():
    posts = _track_posts([_followup("d.os2.14.note", kind="career_note")])
    _s, a = wc.build_grounding("create a follow-up draft for application 14",
                               "lilith_os:home", _draft_intent("14"), do_write=True, dedup=True)
    check("D5 different kind (note) does not block follow-up -> new draft", len(posts) == 1)


def test_dedup_discarded_ignored():
    posts = _track_posts([_followup("d.os2.14.old", status="discarded")])
    _s, a = wc.build_grounding("create a follow-up draft for application 14",
                               "lilith_os:home", _draft_intent("14"), do_write=True, dedup=True)
    check("D6 discarded/resolved draft does not block -> new draft", len(posts) == 1)


def test_dedup_multiple_reconcile():
    posts = _track_posts([_followup("d.os2.14.aaa"), _followup("d.os2.14.bbb")])
    suffix, action = wc.build_grounding("create a follow-up draft for application 14",
                                        "lilith_os:home", _draft_intent("14"), do_write=True, dedup=True)
    check("D7 multiple duplicates -> no new draft", len(posts) == 0 and action is None)
    check("D7 surfaces reconciliation + both ids", "DUPLICATE DRAFTS EXIST" in suffix and "d.os2.14.aaa" in suffix and "d.os2.14.bbb" in suffix)


def test_dedup_disabled_creates():
    posts = _track_posts([_followup("d.os2.14.aaa")])
    _s, a = wc.build_grounding("create a follow-up draft for application 14",
                               "lilith_os:home", _draft_intent("14"), do_write=True, dedup=False)
    check("D8 dedup disabled -> pre-7.3 always-create behaviour", len(posts) == 1)


def main():
    test_intent()
    test_world_sufficient()
    test_unknown()
    test_stale()
    test_conflicted()
    test_topk()
    test_pending()
    test_draft_create_durable()
    test_no_prose_persistence()
    test_transport_parity()
    test_dedup_reuse_single()
    test_dedup_home_then_telegram()
    test_dedup_repeated_identical()
    test_dedup_different_app()
    test_dedup_different_kind()
    test_dedup_discarded_ignored()
    test_dedup_multiple_reconcile()
    test_dedup_disabled_creates()
    print()
    if _failures:
        print("FAILURES: %d -> %s" % (len(_failures), ", ".join(_failures)))
        sys.exit(1)
    print("ALL WORLD-CONTEXT TESTS PASSED")


if __name__ == "__main__":
    main()
