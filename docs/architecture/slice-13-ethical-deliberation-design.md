# LILITH Slice 13 — Ethical Deliberation System V1 · Design (corrected & approved)

> **Status:** Phase 1 APPROVED WITH REQUIRED REFINEMENTS (1–34). This record supersedes the Phase-1 report where they conflict, and reflects the implemented + tested design.
> **Layer:** `L09 · Ethical Deliberation` (Tier 5) of `cognitive-architecture-v1.md`.
> **Governing invariant:** **Ethics may deliberate. Policy governs.** Advisory only — no ALLOW/DENY, no execution, no mutation, no approval, no verification.
> **Target:** `lilith-01` backend router only (`~/.hermes/lilith_router/`). Reuses the Slice-9 `run.py` `final_response` short-circuit — **no `run.py`/`app.py`/DB/frontend/Policy/Verifier/executor change.**

---

## 0. Two load-bearing findings (why V1 is shaped as it is)

1. **There is no live Policy service on the Router path.** The authoritative capability-Policy engine / registry / connector fabric / verifier live only in the frontend `RealCommandCore`. On the Router path the router-local `policy.py` is merely the **social-mode prompt text**, not an authorization gate. Ethics therefore sees only the **static, non-authoritative** `planning_capabilities` mirror (`policyCompatibility ∈ KNOWN_PROHIBITED|NO_KNOWN_STATIC_CONFLICT|NOT_EVALUATED`; `runtimeAvailability` always `UNKNOWN`) and must never present it as a Policy decision.
2. **There is no executor on the Router path.** The only reachable state change is `POST /os/drafts` (reversible, idempotent, dedup-guarded, approval-gated in the frontend). No send, no delete, no task materialization, no Verifier. So live Ethics can only ever deliberate over a *hypothetical/proposed* action — never gate a real one. The canonical L09 "ethics can subtract/block" action-gate (`action_proceeds = policy==ALLOW AND ethics.verdict != ABSTAIN …`) is therefore **explicitly deferred** (correction 28); V1 is advisory only and never simulates that gate.

## 1. Operational definition

A bounded, evidence-referenced, per-turn **advisory** process that evaluates exactly one explicit `EthicalSubject` (live: a `USER_INTENT` ethics question; shadow: an existing `PlanSnapshot`) against a **fixed set of four architecture-defined principles**, using only current-turn evidence + Workspace-bounded real source state, and emits typed concerns, explicit value tensions, information-needs and advisory recommendations — never allow/deny, never execution, never mutation.

## 2. Final principle set (correction 6) — `ethics_principles.py`, `principleSetVersion = 1`

Exactly four advisory principles, each with a real evidence-bound trigger:

| principleId | definition | applies to |
|---|---|---|
| `USER_AUTONOMY` | Respect explicit user intent, consent and control over consequential acts. | explicit standing constraint; contemplated action that bypasses the user's confirmation |
| `PRIVACY_MINIMIZATION` | Avoid unnecessary exposure/use of personal data. | a disclosure action + real user-asserted/typed personal-data scope |
| `NON_MALEFICENCE` | Avoid foreseeable unnecessary concrete impact; irreversibility under uncertainty. | a concrete impact class (irreversible deletion / external disclosure) + source-backed uncertainty |
| `PROPORTIONALITY` | Prefer action scope matching the subject scope. | comparable typed subject vs action scope where the action exceeds |

**Rejected/deferred:** TRANSPARENCY (correction 5 — truthfulness is Reasoning/Verifier/World integrity, not an ethical principle; **no `MISLEADING_REPRESENTATION` concern**), FAIRNESS, HUMAN_OVERSIGHT-as-principle (it is a derived outcome), REVERSIBILITY-as-principle (folded into `NON_MALEFICENCE`), generic HARM, cultural/legal/org principles, personal LILITH values. **No principle weights/scores.**

## 3. Current-turn evidence as a real source owner (correction 1)

Ethics never uses raw user text as a `sourceRef`. `world_context.build_turn_evidence` produces an ephemeral `TurnEvidence` with deterministic correlation-bound refs and `sourceOwner = TURN`:

```
TurnEvidence {
  turnRef "turn:<corr>", correlationId, normalizedIntent,
  explicitConstraints[]      { ref "turn:<corr>:constraint:<i>", text, kind }
  referencedTargets[]        { ref "turn:<corr>:target:<i>", targetRef, appId }
  referencedAction?          { ref "turn:<corr>:action", verb, capabilityRef?, impactClass?, bypassConfirmation }
  referencedDataScope[]      { ref "turn:<corr>:data-scope:<i>", assertion, userAsserted, overBroad }
  referencedThirdPartyRoles[]{ ref "turn:<corr>:third-party:<i>", role, identityResolved:false }
  subjectScope / actionScope { kind, targetCount } # for proportionality only
}
```

`sourceOwner ∈ TURN | world | goals | tasks | drafts`. Every concern's `sourceRefs[]` resolves to one of these ephemeral or durable refs (validator-enforced). Identity is **never fabricated** — a third party is a *role* with `identityResolved:false`.

## 4. Subject (corrections 2/27)

Exactly one `EthicalSubject { kind: USER_INTENT|PLAN_SNAPSHOT|ACTION_PROPOSAL, ref, targetAppId?, referencedCapabilityRef? }`. `ref` is `turnRef`/snapshot id — **never raw user text** (raw text lives in `TurnEvidence.normalizedIntent`). **Live V1: `USER_INTENT` only.** `PLAN_SNAPSHOT` shadow-only. `ACTION_PROPOSAL` schema/future, non-live. No multi-subject evaluation.

## 5. Concern taxonomy (corrections 10/11/20) + deterministic triggers

Six types only; each requires an exact evidence trigger:

| concernType | principleRefs | trigger (all evidence-bound) |
|---|---|---|
| `USER_CONSTRAINT_CONFLICT` | USER_AUTONOMY | a standing `explicitConstraint` **and** a `referencedAction` that conflicts with it |
| `EXECUTION_CONSENT_UNCLEAR` | USER_AUTONOMY | `referencedAction.bypassConfirmation == true` (explicit "without asking me" framing). *Absence of approval alone never triggers this* (correction 3) |
| `PRIVACY_EXPOSURE` | PRIVACY_MINIMIZATION | a disclosure `referencedAction` **and** a real `referencedDataScope` (user-asserted or typed personal field) |
| `UNNECESSARY_SCOPE` | PROPORTIONALITY | comparable typed `subjectScope`/`actionScope` where action scope exceeds subject scope |
| `IRREVERSIBILITY_UNDER_UNCERTAINTY` | NON_MALEFICENCE | `referencedAction` irreversible impact class **and** a real STALE/CONFLICTED/UNKNOWN precondition or unknown target |
| `THIRD_PARTY_IMPACT` | NON_MALEFICENCE, USER_AUTONOMY | a `referencedThirdPartyRole` **and** a concrete communication/impact action to it (existence alone is not enough — correction 14) |

**Removed** (corrections 10/11/5): `CONFLICTING_VALUES` (tension owns conflict), `INSUFFICIENT_ETHICAL_CONTEXT` (represented via `informationNeeded` + applicability + outcome), `MISLEADING_REPRESENTATION`, generic HARM, FAIRNESS.

## 6. Principle applicability — three-way (correction 12)

`PrincipleApplicabilityStatus ∈ APPLICABLE | NOT_APPLICABLE | INSUFFICIENT_EVIDENCE`. Missing evidence is **never** silently `NOT_APPLICABLE`: e.g. a disclosure action with unknown data scope → `PRIVACY_MINIMIZATION = INSUFFICIENT_EVIDENCE` + `informationNeeded`, **no fabricated `PRIVACY_EXPOSURE`** (correction 13). A concern is emitted only for a principle whose applicability is `APPLICABLE`.

## 7. No score / no severity / no generic uncertainty (corrections 7/8/12/16)

- **No `importanceClass`** (removed), no numeric or ordinal moral-materiality scale, no aggregate/utility score.
- **No `uncertaintyClass`.** Concerns carry `causeCodes[]` referencing source-owned epistemics: `WORLD_STALE · WORLD_CONFLICTED · TARGET_UNKNOWN · RECIPIENT_UNRESOLVED · DATA_SCOPE_UNKNOWN · CONSTRAINT_CONFLICT · BYPASS_CONFIRMATION_REQUESTED · IRREVERSIBLE_IMPACT · MULTI_TARGET_SCOPE · USER_ASSERTED_PRIVATE_DATA · THIRD_PARTY_ROLE_PRESENT`.

## 8. Outcome model (corrections 18/19)

`outcome ∈ NO_GROUNDED_CONCERN_IDENTIFIED | CONCERNS_IDENTIFIED | HUMAN_REVIEW_RECOMMENDED | INSUFFICIENT_CONTEXT | SKIPPED_KNOWN_PROHIBITION`. **No ALLOW/DENY/SAFE/APPROVED/LEGAL/COMPLIANT.** `NO_GROUNDED_CONCERN_IDENTIFIED` explicitly does **not** mean safe/allowed/good. `SKIPPED_KNOWN_PROHIBITION` carries `prohibitionBasis = STATIC_POLICY_MIRROR`, `authoritativePolicyEvaluation = false` and performs **no** moral balancing (the referenced action's capability is `KNOWN_PROHIBITED` in the static mirror).

## 9. Human review — typed conditions only (correction 9)

`humanReviewRecommended = true` only when a typed condition holds: (a) an `IRREVERSIBILITY_UNDER_UNCERTAINTY` concern exists; (b) an unresolved tension involves a concrete consequential impact; (c) a `THIRD_PARTY_IMPACT` concern exists with the relevant consent/relationship unresolved; (d) context is insufficient for an explicitly consequential/irreversible subject. **No generic risk matrix, no hidden score, no "ask a human just to be safe."**

## 10. Value tension (correction 22)

`EthicalTension { tensionId, principleRefs[], sourceRefs[], description, resolutionStatus }`. Created only when ≥2 **applicable** principles genuinely pull in different directions on the **same** subject/decision with source-backed relevance (e.g. `USER_AUTONOMY` wanting an act vs `NON_MALEFICENCE` flagging its irreversibility). Default `UNRESOLVED`; no universal hierarchy, no precedence/utility score. Never double-represents the same event as both a concern and a tension.

## 11. Schemas (corrections 21/23)

```
EthicalConcern { concernId, concernType, principleRefs[], sourceRefs[], causeCodes[],
                 rationaleSummary, resolutionConditions[], sourceScope?, advisoryOnly:true }
EthicalResult  { schemaVersion, ethicalSnapshotId, subject, outcome, concerns[]≤4,
                 tensions[]≤3, advisoryRecommendations[], informationNeeded[], evidenceRefs[],
                 principleApplicability[], humanReviewRecommended, principleSetVersion,
                 traceMetadata, answer }
```
No `importanceClass`/`uncertaintyClass`/score/weight/Policy verdict/legal verdict. The user-facing `answer` is **rendered deterministically FROM the validated typed result**; persona may shape wording only (correction 23).

## 12. Bounded input (corrections 16/17) — `world_context.build_ethical_input`

Reuses the Slice-12 Workspace-bounded assembly (`select_reasoning_input_m` with `mot_snapshot=None`). **`motivationSummary` and `reasoningResult` are absent from the live `EthicalInput`** — Motivation cannot change ethical correctness; the deterministic live path needs no speculative Reasoning output. Input carries: `ethicalSubject`, `turnEvidence`, `explicitUserConstraints`, bounded `relevantBeliefs/relevantTasks/relevantDrafts` (≤8), `workspaceFocus`, static `capabilityView`, `worldUnavailable`.

## 13. Mechanism (corrections 25/26) — hybrid, deterministic live

Pipeline: `EthicalInput → deterministic principle-applicability → deterministic live concern triggers (OR bounded no-tool LLM candidates, disabled live) → deterministic Grounder (resolve TURN/source refs, attach principle refs, canonicalize concernIds, attach resolution conditions; drop unresolved) → deterministic Validator (schema; principle exists; source refs exist; reject fabricated preference/third party/privacy classification/harm category/Policy-or-legal vocabulary; bound counts; NEVER synthesizes concerns) → EthicalResult → deterministic renderer`. **Live posture: deterministic only** (mirrors Slice 12); the LLM candidate path is built + unit-tested but **not wired live** (`model_call=None`). No-tool boundary when enabled: `enabled_toolsets=[] · skip_memory=True · skip_context_files=True · load_soul_identity=False · max_iterations=1`.

## 14. Router integration (correction 27) — `gateway_integration.py`

A new **ethics lane** after the Slice-12 planning lane and before the Slice-9 reasoning lane, reusing the Slice-9 `run.py` short-circuit (returns `{"final_response", "mode":"ethics"}` in live mode; records `WORK` so social-guard leaves the grounded answer untouched). `detect_ethics_intent` fires on explicit normative/evaluative framings (or `should we/i` + a privacy/third-party/bypass/constraint cue) and **yields** to explicit action (7.2 draft), goal create/query, pending, and planning — so action/plan precedence is preserved. Live subject is `USER_INTENT` only; `PLAN_SNAPSHOT` is evaluated in shadow. Fully fail-open: any failure or non-owning intent → fall through unchanged.

## 15. Persistence / cross-turn (correction 24)

Ephemeral per-turn; no DB; no `/os/ethics`. `ethicalSnapshotId` only — **no `ethicalCaseId`**. No cross-turn "resolved concern" claim without an explicitly supplied prior `EthicalResult` (none in V1).

## 16. Trace (safe, non-CoT)

`decisions.log` lane `"ethics"`: `correlation_id, ethical_subject_kind, ethical_subject_ref, applicable_principles[], concern_types[], concern_count, tension_count, outcome, source_ref_count, human_review_recommended, prohibition_basis, authoritative_policy_evaluation:false, principle_set_version, duration_ms, fallback_reason, ts`. No CoT/scratchpad, no moral monologue, no raw private data.

## 17. Config / files

`ethics_enabled:false`, `ethics_mode:"shadow"`, `ethics_max_concerns:4`, `ethics_max_tensions:3`; channels reuse `cognitive_channels` (`lilith_os`, `telegram`; Discord excluded). Read per-turn (flip without restart). **NEW** `ethics.py`, `ethics_principles.py`, `tests/test_ethics.py`. **EDIT** `world_context.py` (append Slice-13 block), `gateway_integration.py` (ethics lane + `_log_ethics`), `config.py`, `router.yaml`. **No** `app.py`/DB/`run.py`/frontend/Presence/OAuth/connector/Policy/Verifier/executor/`planning.py` change.

## 18. Live acceptance (route-level; no transport)

- **A** "Would it be okay to send this follow-up without asking me first?" → `career.create_followup_draft` (reversible, not prohibited) + `bypassConfirmation` → `EXECUTION_CONSENT_UNCLEAR` (USER_AUTONOMY); no Policy verdict; no send.
- **B** "Should we include all my private application notes in the email?" → user-asserted private data-scope (TURN) + disclosure → `PRIVACY_EXPOSURE`; refs point to TURN; no invented classification; no send.
- **C** "Would it be okay to email the recruiter?" → `mail.send_email` is `KNOWN_PROHIBITED` in the static mirror → `SKIPPED_KNOWN_PROHIBITION`; recruiter recorded as unresolved third-party role; identity **not** fabricated; no auto-consent concern.
- **D** prohibited-action fixture → `SKIPPED_KNOWN_PROHIBITION`, `authoritativePolicyEvaluation=false`, no balancing, no execution.
- **E** irreversible-under-uncertainty fixture → `IRREVERSIBILITY_UNDER_UNCERTAINTY` + `humanReviewRecommended`; no severity score.
- **F** proportionality fixture (comparable typed scopes) → deterministic `UNNECESSARY_SCOPE`; no LLM intuition.
- **G** vague ethics question, no grounded subject/context → `INSUFFICIENT_CONTEXT` + `informationNeeded`; no fabricated concern.

Home/Telegram route-level parity; Discord excluded.

## 19. Rollout / rollback

Design record → `.bak.<TS>` backups (4 edited files) → offline tests green (deploy-exact) → patch as `lilith` → **one** gateway restart → `ethics_mode:shadow` (log only) → inspect trace → `ethics_mode:live` (per-turn, no restart) → Home acceptance A–G → Telegram parity → regressions → `CURRENT_STATE.md` after PASS. **No `daemon-reload`.** Rollback: `ethics_mode:shadow`/`ethics_enabled:false` (no restart), or restore `.bak.<TS>` + remove `ethics*.py`/`tests/test_ethics.py` + one restart. Ephemeral — nothing to unwind.

## 20. Deferred (not V1)

Live wiring of Ethics into a real action gate (L09 subtract/ABSTAIN/ESCALATE); durable ethical-case store; LTM value priors; live LLM concern path; live Plan-advisory attachment; FAIRNESS; generic harm taxonomy; org/legal/cultural/high-stakes sources; consequence estimation; cross-turn lineage; Presence/affect; frontend view.
