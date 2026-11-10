# P4-1 event-date coverage, and P-4 temporal-quality findings (2026-11-11)

**Status:** tooling prepared and tested offline; **not run on PROD.** `coverage.py` reads proposal text in-process, so
running it needs the owner's separate OK. It prints counts only.

## Measurement plan

- **What it measures:** does the nightly review, with #412 deployed, propose memories dated the way its guidance asks?
- **When:** after #412 is deployed and at least 3 nightly reviews have produced proposals. With n = 0 nothing can be
  concluded; the 2026-11-09 and 2026-11-10 reviews proposed nothing.
- **How:** on `lilith-01`, as `lilith`, `python3 -I coverage.py --since <#412 deploy time>`. It reads
  `GET /os/learning-events?kind=PROPOSED` (one row per proposed item) and prints one JSON object.

| Class | Meaning | Healthy direction |
| --- | --- | --- |
| `event_dated` | an explicit date for when it happened | only where the owner said when |
| `told_on` | "Told LILITH on <date>: …" | most undatable facts end here |
| `relative` | "yesterday", "last week", "recently"… with no date at all | **should fall toward 0** (the guidance resolves or anchors them) |
| `undated` | no date, no relative word | acceptable for timeless facts |
| `preference` | Preference / Boundary lines | dates do not apply |

| Flag | Meaning |
| --- | --- |
| `event_date_equals_review_day` | the event date is the Colombo day the proposal was made. Legitimate if the owner said "today"; it is also what a run-date leak looks like, so each one gets a human look (by approving or rejecting the proposal, not by reading logs) |
| `also_told_on` | both an event date and a told-on date |
| `relative_kept_with_told_on` | the owner's own vague wording kept with the told date (allowed by the guidance) |

**Baseline before #412:** E-8 inventory, 1 of 11 entry texts contained any date. Since the P4-1 guidance was installed
(2026-11-09): 0 proposals.

**Success criterion, proposed:**
- `relative` = 0;
- `fact_items_with_any_date` at least 80 %;
- every `event_date_equals_review_day` traceable to the owner saying "today".

Anything else goes back to the guidance, not to a schema change.

## P-4 temporal-quality audit (read-only; 2026-11-11)

| # | Finding | Evidence | Minimal fix | Status |
| --- | --- | --- | --- | --- |
| T1 | The review input had no conversation dates | source review | said-on markers by owner-local day; four-date guidance | **#412** (rebased onto `cda3d85`; PROD-shaped test added); not deployed |
| T2 | **The timeline renders "stored" dates as UTC days while Hermes now runs in Asia/Colombo** | PROD metadata (approval timestamps only): **3 of 5 approval dates fall on a different day** (6 Nov 18:32–20:40Z = **7 Nov** in Colombo) | `timeline.py`: dates in Hermes' zone (`HERMES_TIMEZONE`, else named UTC); the zone named on the header line | separate PR; shadow lane, not activated |
| T3 | 6 of 11 owner memories (imports) have no approval date | inventory | none: never invent a date; they stay "stored (undated)" | by design |
| T4 | The reply model's USER.md projection carries no dates or lineage | E-8 | the timeline lane provides them; its activation is a separate owner decision | open (shadow) |
| T5 | The agent sees no per-message times in history (`gateway.message_timestamps.enabled: false`) | PROD config | candidate only: enabling it adds a time to each replayed owner message, which affects cost and prompt caching. Measure first with E-8-style arms; do not change config without evidence | **not proposed yet** |
| T6 | Commitment deadlines are shown as raw ISO (`2026-11-12T22:00:00+05:30`) | `commitments.py`, review script | none needed: the offset is explicit; new deadlines carry `+05:30` | no change |
| T7 | The Groq budget day key is UTC (`social_lean.Budget`) | source | none: the provider's daily quota resets in UTC | correct as is |

T1 and T2 must use the **same zone source** (Hermes' setting); both do.

Deploying either one is a separate owner decision, and neither touches canonical memory, the timeline's activation, or
P-5.
