# Ethics shadow: integration analysis (PROPOSAL, nothing wired)

Slice 13 on DEV. **Not ready for a release.** Measured on the real gateway, adapter and Core API, with the m1 router plus Ethics in shadow. `test_ethics_shadow_findings.py` pins each finding.

`ethics.py` (`b6e3ce49...`) and `ethics_principles.py` (`178990e5...`) are in the DEV release, and `docs/architecture/slice-13/` holds the same bytes. **On PROD, Ethics has been live since 2026-09-09.**

## How the lane behaves

| Property | Measured |
|---|---|
| Position | after Planning, before Reasoning. It yields to goal, pending and planning paths, and an explicit marker wins over a draft shape |
| Dependencies | Workspace for bounded context; World Model, Goals, Tasks and Drafts by reads; `planning_capabilities` for a static view. It deliberately ignores Motivation and Reasoning |
| Reads | **10 per matching turn** |
| Writes | none on an empty store. With a goal present, a focus read writes a trace, so the empty-store rule stays |
| Provider | none: deterministic only. The model path is built but not wired |
| Reply | unchanged in shadow. Live mode replaces the reply |
| Record | `ethics`, then the usual lanes. If Reasoning also matches, its lanes record too |
| Identifiers | `correlation_id` and `ethical_subject_ref` are turn-scoped. `intent.app_id` carries the application number |
| Text | none in the trace on a populated store |

**Safeguards already in the code:** advisory only, no allow or deny, no tools, no writes, and `authoritative_policy_evaluation` false. Principle set: four fixed principles, version 1.

## Blockers

| # | Finding | Effect | Proposed fix |
|---|---|---|---|
| E-1 | **Over-match:** `is it ok to wear jeans?`, `is it okay if we eat at 7?` and `is it fair that my team lost?` are Ethics turns | 10 reads on a casual message | Require a work or disclosure subject, as the Planning candidate does |
| E-2 | **Weak output on the current path:** `is it okay to lie on my cover letter?` gives `INSUFFICIENT_CONTEXT`, and all three test questions gave 0 concerns | Shadow would prove the lane runs, not that it helps | Review the turn-evidence rules against a labelled corpus before any release |
| E-3 | **Overlap with Reasoning:** `what are the risks of ...` is an Ethics marker | In shadow both lanes run, at 18 reads. Ethics Live would take the turn from Reasoning | Decide ownership: a risk question about work is analysis |
| E-4 | **10 reads** | Load | Adopt the read-once cache from the Planning candidate |
| E-5 | **`intent.app_id` in the record** | Links a record to an application | Adopt the private-intent approach from the Planning candidate |

## Proposed order

Ethics after Planning, because E-1, E-4 and E-5 reuse the Planning adapter work. A release would change the router, the verifier pins for `ethics.py` and `ethics_principles.py`, and the adapter. Rollback restores all of them to the previous release.

**Privacy and FORGET:** no new store. Records follow the decision log. The turn evidence is ephemeral.

## Not for this lane

Ethics Live on DEV, the model path, and any use of Ethics as a policy gate.
