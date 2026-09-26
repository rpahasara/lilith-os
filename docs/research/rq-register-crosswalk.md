# REPO ↔ MASTER Research Question Crosswalk

Status: **RECONCILIATION RECORD — primary-source pass (2026-09-26).** Built
from the archived
[Master v1.1](source-material/originals/LILITH_Architecture_and_Research_Master_v1.1.pdf)
(RQ-001–RQ-121) and the in-repo
[register](research-question-register.md) (RQ-001–RQ-050). **Neither register
is renumbered, reworded, or overwritten.** No new number is assigned.

## Namespaces

| Namespace | Range | Canonical source | First known | Notes |
| --- | --- | --- | --- | --- |
| `REPO:RQ-NNN` | 001–050 | `docs/research/research-question-register.md` | commit `1eee09b`, 2026-09-13 19:29 +0530 | Cited by ADR-0001–0004 and the roadmap; CI enforces unique sequential rows |
| `MASTER:RQ-NNN` | 001–121 | Master v1.0 (2026-09-14, archived) and v1.1 (2026-09-14, archived) | Master v1.0 PDF created 2026-09-14 10:59 +0500 | v1.0 and v1.1 use identical numbers and titles; RQ-001–100 carried from the missing *LILITH Research Question & Architecture Problem Register*, RQ-101–120 from the missing *Frontier Research Extensions*, RQ-121 synthesized in the Master task |

No third numbered RQ namespace appears in any archived source (Infrastructure
v1.0/v1.1/v1.1.1, OS Architecture v0.1, Project Roadmap, Cognitive
Architecture V1, Engineering Journal contain no RQ numbers). Other ID families
seen — Roadmap `M1–M5`, `B01–B14`, `D01–D08`; threat model `T-01–T-24`;
negative results `N-01…` — are not research-question namespaces. Whether the
missing original Problem Register used a different numbering is **UNKNOWN**;
Master v1.0 says it preserved that register's "original RQ-001 through RQ-100
wording, domains and status labels".

**RQ-122 or higher:** none in any archived source or in the repository.

## Relationship classes

| Class | Meaning |
| --- | --- |
| EXACT MATCH | Same question in effectively identical wording. **Not used**: no pair has identical wording. |
| SEMANTIC MATCH | Same research problem, different wording or scope framing. |
| PARTIAL OVERLAP | One question covers a substantial part (often a listed subquestion) of the other. |
| RELATED | Adjacent problem; evidence for one informs the other. |
| NO MATCH | No counterpart in the other register. |
| CONFLICTING NUMBER | The same number names different questions in the two registers. |
| UNKNOWN | Cannot be decided from available sources (used only for missing originals). |

## Summary

- **Number conflicts:** for 49 of the 50 shared numbers (002–050) the REPO and
  MASTER questions differ. Only RQ-001 agrees (SEMANTIC MATCH). Never cite a
  bare `RQ-NNN` across the two.
- **MASTER → REPO:** 35 MASTER questions have a REPO semantic match; 26 more
  have at least a partial overlap; 39 are only related; **21 have no REPO
  counterpart**: MASTER:RQ-042, 043, 045, 056, 057, 058, 061, 066, 073, 087,
  088, 089, 093, 098, 099, 100, 102, 109, 112, 120, 121.
- **REPO → MASTER:** 35 REPO questions have a MASTER semantic match; 13 have
  partial overlap only (REPO:RQ-002, 003, 005, 006, 007, 016, 017, 025, 039,
  041, 043, 046, 047); REPO:RQ-032 is only related; **REPO:RQ-049 (backup and
  disaster recovery vs identity continuity) has no MASTER question** (the
  private Infrastructure v1.1 recovery inventory, a PRIVATE HISTORICAL SOURCE,
  covers the operational side).
- **Verification of earlier examples** (reported in the first pass from the
  brief, now checked against the archived Master): MASTER:RQ-003 ↔ REPO:RQ-009
  ✔ SEMANTIC MATCH; MASTER:RQ-005 ↔ REPO:RQ-011 ✔; MASTER:RQ-007 ↔ REPO:RQ-013
  ✔; MASTER:RQ-009 ↔ REPO:RQ-015 ✔; MASTER:RQ-036 ("Could malicious external
  content become long-term memory?") ✔ has no REPO question (RELATED to
  REPO:RQ-015, REPO:RQ-047 and threat T-08).

## Findings about the two registers

1. **Common ancestry (INFERRED).** REPO:RQ-001–050 cover the MASTER:RQ-001–050
   topics in largely the same order, grouped into themes, with several MASTER
   subquestions promoted to separate REPO questions (for example, MASTER:RQ-001's
   subquestion "Can an old LILITH state be restored without effectively
   creating another instance?" ≈ REPO:RQ-003; MASTER:RQ-002's leases and
   duplicate-action subquestions ≈ REPO:RQ-005 and REPO:RQ-008). This pattern
   supports — but does not prove — that the REPO register was condensed from
   the same original Problem Register that the Master preserves. The Problem
   Register itself is missing, so this cannot be confirmed.
2. **Chronology.** The REPO register (2026-09-13) predates Master v1.0
   (2026-09-14). Master v1.0 lists the repository "research register" among its
   evidence but does not adopt its numbering.
3. **Coverage gap.** The REPO register omits most of MASTER:RQ-051–121 (devices,
   voice, Hsin, time, workers, multi-user, security workers, platform scale,
   frontier extensions, affect). Relationship, narrative identity, anti-goals
   and affective continuity have no REPO question.
4. **v1.0 → v1.1 changes.** All 121 titles are identical. Only
   MASTER:RQ-100's status changed (v1.0 `RECOMMENDED / RESEARCH` → v1.1 "Not
   specified in original register; overarching RESEARCH question"), and
   RQ-101–120 bodies were rewritten to remove novelty assertions (v1.0 text
   included phrases such as "Your unique angle" and "Novelty: This is
   meta-research"; v1.0 headed them "DeepSeek-inspired extensions"). v1.1 says
   it restored fuller RQ-001–100 detail that v1.0 had flattened. No question was
   dropped or renumbered between v1.0 and v1.1.

## MASTER → REPO (all 121)

| MASTER | Title (Master v1.1) | Master source status | REPO relationship(s) | Number relationship |
| --- | --- | --- | --- | --- |
| MASTER:RQ-001 | What fundamentally makes LILITH "LILITH"? | RESEARCH | REPO:RQ-001 SEMANTIC MATCH; REPO:RQ-002 PARTIAL OVERLAP; REPO:RQ-003 PARTIAL OVERLAP | same number = SEMANTIC MATCH |
| MASTER:RQ-002 | How can one identity operate through multiple runtimes? | PARTIAL / RESEARCH | REPO:RQ-004 SEMANTIC MATCH; REPO:RQ-005 PARTIAL OVERLAP; REPO:RQ-006 PARTIAL OVERLAP; REPO:RQ-008 PARTIAL OVERLAP | CONFLICTING NUMBER (REPO:RQ-002 is a different question) |
| MASTER:RQ-003 | What deserves to become memory? | DESIGNED | REPO:RQ-009 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-003 is a different question) |
| MASTER:RQ-004 | How does memory evolve? | RESEARCH | REPO:RQ-010 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-004 is a different question) |
| MASTER:RQ-005 | How should LILITH forget? | RESEARCH | REPO:RQ-011 SEMANTIC MATCH; REPO:RQ-016 PARTIAL OVERLAP | CONFLICTING NUMBER (REPO:RQ-005 is a different question) |
| MASTER:RQ-006 | What happens when memories disagree? | DESIGNED / RESEARCH | REPO:RQ-012 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-006 is a different question) |
| MASTER:RQ-007 | How does LILITH know why she believes something? | PARTIAL | REPO:RQ-013 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-007 is a different question) |
| MASTER:RQ-008 | Which memories should enter cognition? | DESIGNED | REPO:RQ-014 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-008 is a different question) |
| MASTER:RQ-009 | How do we stop inference becoming false memory? | DESIGNED | REPO:RQ-015 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-009 is a different question) |
| MASTER:RQ-010 | What exactly is a long-running goal? | DESIGNED | REPO:RQ-018 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-010 is a different question) |
| MASTER:RQ-011 | What happens when two goals conflict? | RESEARCH | REPO:RQ-019 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-011 is a different question) |
| MASTER:RQ-012 | How does LILITH know when a goal is no longer relevant? | DESIGNED | REPO:RQ-020 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-012 is a different question) |
| MASTER:RQ-013 | When should LILITH use deterministic logic vs LLM planning? | PARTIAL | REPO:RQ-021 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-013 is a different question) |
| MASTER:RQ-014 | When should LILITH abandon or modify a plan? | DESIGNED | REPO:RQ-022 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-014 is a different question) |
| MASTER:RQ-015 | How does LILITH know when her own reasoning is unreliable? | RESEARCH | REPO:RQ-023 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-015 is a different question) |
| MASTER:RQ-016 | Which model should reason about which problem? | DESIGNED | REPO:RQ-024 SEMANTIC MATCH; REPO:RQ-007 PARTIAL OVERLAP | CONFLICTING NUMBER (REPO:RQ-016 is a different question) |
| MASTER:RQ-017 | What happens when a new model changes LILITH's personality or judgment? | RESEARCH | REPO:RQ-045 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-017 is a different question) |
| MASTER:RQ-018 | How does LILITH know what she is allowed to do? | PARTIAL / TARGET | REPO:RQ-026 RELATED | CONFLICTING NUMBER (REPO:RQ-018 is a different question) |
| MASTER:RQ-019 | How should action risk be calculated? | RESEARCH | REPO:RQ-026 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-019 is a different question) |
| MASTER:RQ-020 | Can LILITH learn that an action is safer than initially believed? | DESIGNED | REPO:RQ-027 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-020 is a different question) |
| MASTER:RQ-021 | How do we guarantee the approved action is exactly the executed action? | architectural foundation planned/impleme… | REPO:RQ-028 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-021 is a different question) |
| MASTER:RQ-022 | How long should approval remain valid? | RESEARCH | REPO:RQ-029 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-022 is a different question) |
| MASTER:RQ-023 | What if reality changes after approval but before execution? | DESIGNED | REPO:RQ-029 PARTIAL OVERLAP | CONFLICTING NUMBER (REPO:RQ-023 is a different question) |
| MASTER:RQ-024 | Can the user approve classes of future actions? | RESEARCH | REPO:RQ-031 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-024 is a different question) |
| MASTER:RQ-025 | What happens at 3 AM when production is down? | RESEARCH | REPO:RQ-030 SEMANTIC MATCH; REPO:RQ-032 RELATED | CONFLICTING NUMBER (REPO:RQ-025 is a different question) |
| MASTER:RQ-026 | How do we prevent duplicate actions? | PARTIAL | REPO:RQ-008 SEMANTIC MATCH; REPO:RQ-039 PARTIAL OVERLAP | CONFLICTING NUMBER (REPO:RQ-026 is a different question) |
| MASTER:RQ-027 | What happens if an API times out after the action may have succeeded? | DESIGNED | REPO:RQ-033 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-027 is a different question) |
| MASTER:RQ-028 | How do we know an action truly succeeded? | PARTIAL | REPO:RQ-034 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-028 is a different question) |
| MASTER:RQ-029 | Can the same component that executes fairly verify itself? | RESEARCH | REPO:RQ-035 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-029 is a different question) |
| MASTER:RQ-030 | What's more dangerous: false failure or false success? | RESEARCH | REPO:RQ-037 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-030 is a different question) |
| MASTER:RQ-031 | How much evidence is enough? | DESIGNED | REPO:RQ-036 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-031 is a different question) |
| MASTER:RQ-032 | Can every conclusion be traced back to evidence? | DESIGNED | REPO:RQ-038 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-032 is a different question) |
| MASTER:RQ-033 | Are all data sources equally trustworthy? | RESEARCH | REPO:RQ-013 RELATED; REPO:RQ-010 RELATED | CONFLICTING NUMBER (REPO:RQ-033 is a different question) |
| MASTER:RQ-034 | When does valid information become too stale to use? | PARTIAL | REPO:RQ-013 RELATED; REPO:RQ-011 RELATED | CONFLICTING NUMBER (REPO:RQ-034 is a different question) |
| MASTER:RQ-035 | How does LILITH distinguish data from authority? | DESIGNED | REPO:RQ-047 PARTIAL OVERLAP | CONFLICTING NUMBER (REPO:RQ-035 is a different question) |
| MASTER:RQ-036 | Could malicious external content become long-term memory? | RESEARCH | REPO:RQ-015 RELATED; REPO:RQ-047 RELATED | CONFLICTING NUMBER (REPO:RQ-036 is a different question) |
| MASTER:RQ-037 | What if a tool returns malicious instructions? | DESIGNED | REPO:RQ-047 PARTIAL OVERLAP | CONFLICTING NUMBER (REPO:RQ-037 is a different question) |
| MASTER:RQ-038 | How do we let LILITH use credentials without giving models raw secrets? | DESIGNED | REPO:RQ-048 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-038 is a different question) |
| MASTER:RQ-039 | Should every worker have every capability? | DESIGNED | REPO:RQ-025 PARTIAL OVERLAP | CONFLICTING NUMBER (REPO:RQ-039 is a different question) |
| MASTER:RQ-040 | When does a problem deserve its own worker? | RESEARCH | REPO:RQ-025 RELATED | CONFLICTING NUMBER (REPO:RQ-040 is a different question) |
| MASTER:RQ-041 | How does the Core choose the correct worker? | DESIGNED | REPO:RQ-025 RELATED; REPO:RQ-024 RELATED | CONFLICTING NUMBER (REPO:RQ-041 is a different question) |
| MASTER:RQ-042 | What happens when workers disagree? | RESEARCH | NO MATCH | CONFLICTING NUMBER (REPO:RQ-042 is a different question) |
| MASTER:RQ-043 | Should workers earn reputation? | OPEN | NO MATCH | CONFLICTING NUMBER (REPO:RQ-043 is a different question) |
| MASTER:RQ-044 | What can legitimately wake LILITH without user interaction? | DESIGNED | REPO:RQ-040 RELATED | CONFLICTING NUMBER (REPO:RQ-044 is a different question) |
| MASTER:RQ-045 | How do we prevent one automation from recursively triggering another? | RESEARCH | NO MATCH | CONFLICTING NUMBER (REPO:RQ-045 is a different question) |
| MASTER:RQ-046 | How do old automations become dangerous? | DESIGNED | REPO:RQ-020 RELATED | CONFLICTING NUMBER (REPO:RQ-046 is a different question) |
| MASTER:RQ-047 | What information is worth proactively surfacing? | DESIGNED | REPO:RQ-040 PARTIAL OVERLAP; REPO:RQ-041 PARTIAL OVERLAP | CONFLICTING NUMBER (REPO:RQ-047 is a different question) |
| MASTER:RQ-048 | When should LILITH interrupt the user? | RESEARCH | REPO:RQ-040 SEMANTIC MATCH | CONFLICTING NUMBER (REPO:RQ-048 is a different question) |
| MASTER:RQ-049 | How does LILITH avoid becoming annoying? | RESEARCH | REPO:RQ-040 RELATED | CONFLICTING NUMBER (REPO:RQ-049 is a different question) |
| MASTER:RQ-050 | How does LILITH know whether now is a bad time? | OPEN | REPO:RQ-040 PARTIAL OVERLAP | CONFLICTING NUMBER (REPO:RQ-050 is a different question) |
| MASTER:RQ-051 | How does one task move between Windows, Android and web? | FOUNDATION | REPO:RQ-004 RELATED | no REPO question with this number |
| MASTER:RQ-052 | Which device should execute? | DESIGNED | REPO:RQ-024 RELATED | no REPO question with this number |
| MASTER:RQ-053 | What happens when a client is offline? | RESEARCH | REPO:RQ-006 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-054 | How are concurrent legitimate edits resolved? | RESEARCH | REPO:RQ-005 PARTIAL OVERLAP; REPO:RQ-012 RELATED | no REPO question with this number |
| MASTER:RQ-055 | How do we ensure phone-LILITH and desktop-LILITH feel like the same entity? | RESEARCH | REPO:RQ-043 PARTIAL OVERLAP; REPO:RQ-044 RELATED | no REPO question with this number |
| MASTER:RQ-056 | When does LILITH know the user finished speaking? | future | NO MATCH | no REPO question with this number |
| MASTER:RQ-057 | How can spoken LILITH remain the same personality without sounding like text read aloud? | PARTIAL | NO MATCH | no REPO question with this number |
| MASTER:RQ-058 | How much internal state should Hsin expose? | PARTIAL | NO MATCH | no REPO question with this number |
| MASTER:RQ-059 | Should Hsin visually communicate uncertainty? | DESIGNED | REPO:RQ-043 RELATED | no REPO question with this number |
| MASTER:RQ-060 | How far should personality/emotion go without misleading the user? | RESEARCH / PRODUCT PHILOSOPHY | REPO:RQ-041 RELATED; REPO:RQ-043 RELATED | no REPO question with this number |
| MASTER:RQ-061 | How should LILITH reason about time? | PARTIAL | NO MATCH | no REPO question with this number |
| MASTER:RQ-062 | How does a task survive hours/days/process restarts? | FOUNDATION | REPO:RQ-018 RELATED; REPO:RQ-033 RELATED | no REPO question with this number |
| MASTER:RQ-063 | How does LILITH know exactly where to resume? | DESIGNED | REPO:RQ-022 RELATED | no REPO question with this number |
| MASTER:RQ-064 | What does cancellation mean if something already changed? | PARTIAL | REPO:RQ-033 RELATED | no REPO question with this number |
| MASTER:RQ-065 | How does LILITH undo partial workflows? | RESEARCH | REPO:RQ-039 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-066 | How does LILITH avoid spending stupid amounts on models/tools? | FUTURE | NO MATCH | no REPO question with this number |
| MASTER:RQ-067 | When should LILITH think longer? | RESEARCH | REPO:RQ-024 RELATED | no REPO question with this number |
| MASTER:RQ-068 | How do we know LILITH is actually improving? | MAJOR RESEARCH AREA | REPO:RQ-044 SEMANTIC MATCH | no REPO question with this number |
| MASTER:RQ-069 | How can we evaluate autonomy before granting authority? | PLANNED | REPO:RQ-050 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-070 | How does LILITH earn more authority? | DESIGNED | REPO:RQ-050 SEMANTIC MATCH | no REPO question with this number |
| MASTER:RQ-071 | Can authority be reduced again? | RESEARCH | REPO:RQ-050 RELATED | no REPO question with this number |
| MASTER:RQ-072 | How do we prevent a software update from silently changing LILITH's behavior? | immediate work | REPO:RQ-045 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-073 | How do we prevent future code from bypassing our boundaries? | PLANNED | NO MATCH | no REPO question with this number |
| MASTER:RQ-074 | How do we debug an autonomous cognitive system? | TARGET | REPO:RQ-046 RELATED | no REPO question with this number |
| MASTER:RQ-075 | How much should LILITH explain why she acted? | DESIGNED | REPO:RQ-038 RELATED; REPO:RQ-013 RELATED | no REPO question with this number |
| MASTER:RQ-076 | How long do we retain evidence? | RESEARCH | REPO:RQ-046 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-077 | What information may leave the device? | FUTURE | REPO:RQ-017 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-078 | Which reasoning should happen locally? | RESEARCH | REPO:RQ-017 RELATED | no REPO question with this number |
| MASTER:RQ-079 | What's the minimum context required for each capability? | DESIGNED | REPO:RQ-014 PARTIAL OVERLAP; REPO:RQ-017 RELATED | no REPO question with this number |
| MASTER:RQ-080 | What should happen when the user says LILITH was wrong? | RESEARCH | REPO:RQ-042 SEMANTIC MATCH | no REPO question with this number |
| MASTER:RQ-081 | Should LILITH infer preferences from repeated behavior? | RESEARCH | REPO:RQ-042 PARTIAL OVERLAP; REPO:RQ-027 RELATED | no REPO question with this number |
| MASTER:RQ-082 | How should personality adapt over years? | DEEP RESEARCH | REPO:RQ-002 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-083 | How do we measure whether LILITH has drifted away from herself? | RESEARCH | REPO:RQ-045 PARTIAL OVERLAP; REPO:RQ-002 RELATED; REPO:RQ-044 RELATED | no REPO question with this number |
| MASTER:RQ-084 | How does LILITH avoid developing a false model of the user? | RESEARCH | REPO:RQ-015 RELATED; REPO:RQ-012 RELATED | no REPO question with this number |
| MASTER:RQ-085 | Could memory cause LILITH to interpret everything through old beliefs? | OPEN | REPO:RQ-012 RELATED | no REPO question with this number |
| MASTER:RQ-086 | How much personal memory should specialist workers receive? | DESIGNED | REPO:RQ-017 PARTIAL OVERLAP; REPO:RQ-025 RELATED | no REPO question with this number |
| MASTER:RQ-087 | What happens when another person interacts with LILITH? | FUTURE | NO MATCH | no REPO question with this number |
| MASTER:RQ-088 | Can another human approve actions? | FUTURE | NO MATCH | no REPO question with this number |
| MASTER:RQ-089 | How do we build pentest/SOC workers without turning LILITH into an unrestricted offensive agent? | FUTURE | NO MATCH | no REPO question with this number |
| MASTER:RQ-090 | How much security containment should LILITH perform automatically? | DEEP FUTURE | REPO:RQ-032 RELATED | no REPO question with this number |
| MASTER:RQ-091 | How do security workers separate vulnerability evidence from speculation? | FUTURE | REPO:RQ-015 RELATED | no REPO question with this number |
| MASTER:RQ-092 | What happens when an external API changes semantics? | FUTURE | REPO:RQ-034 RELATED | no REPO question with this number |
| MASTER:RQ-093 | How does LILITH know a capability is trustworthy right now? | emerging | NO MATCH | no REPO question with this number |
| MASTER:RQ-094 | What should LILITH do when only some information is available? | principle demonstrated | REPO:RQ-013 RELATED | no REPO question with this number |
| MASTER:RQ-095 | How do simulations remain visibly separate from reality? | architectural principle | REPO:RQ-015 RELATED | no REPO question with this number |
| MASTER:RQ-096 | How do we prevent UI/personality from making LILITH appear more capable than she is? | PRODUCT/ETHICS | REPO:RQ-043 RELATED | no REPO question with this number |
| MASTER:RQ-097 | Which components should be intentionally replaceable? | architecture review item | REPO:RQ-001 RELATED; REPO:RQ-007 RELATED | no REPO question with this number |
| MASTER:RQ-098 | When does current architecture stop being appropriate? | FUTURE | NO MATCH | no REPO question with this number |
| MASTER:RQ-099 | What reliability level should LILITH target? | FUTURE | NO MATCH | no REPO question with this number |
| MASTER:RQ-100 | The Big Research Question | Not specified in original register | NO MATCH | no REPO question with this number |
| MASTER:RQ-101 | Memory Economics (Memory That Pays Rent) | RECOMMENDED / RESEARCH | REPO:RQ-011 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-102 | Counterfactual Memory (The Negative Space) | RECOMMENDED / RESEARCH | NO MATCH | no REPO question with this number |
| MASTER:RQ-103 | Adversarial Memory (Memory That Argues With Itself) | RECOMMENDED / RESEARCH | REPO:RQ-012 RELATED | no REPO question with this number |
| MASTER:RQ-104 | Identity Versioning (Git for the Self) | RECOMMENDED / RESEARCH | REPO:RQ-002 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-105 | The Relationship as a First-Class Entity | RECOMMENDED / RESEARCH | REPO:RQ-043 RELATED | no REPO question with this number |
| MASTER:RQ-106 | Dream Cycles (Offline Consolidation and Simulation) | RECOMMENDED / RESEARCH | REPO:RQ-010 RELATED | no REPO question with this number |
| MASTER:RQ-107 | Memory as a Graph, Not a List | RECOMMENDED / RESEARCH | REPO:RQ-038 RELATED | no REPO question with this number |
| MASTER:RQ-108 | The Permission Gradient (Beyond Binary Approval) | RECOMMENDED / RESEARCH | REPO:RQ-026 PARTIAL OVERLAP; REPO:RQ-031 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-109 | Temporal Contracts (Promises About Time) | RECOMMENDED / RESEARCH | NO MATCH | no REPO question with this number |
| MASTER:RQ-110 | The Uncertainty Ledger | RECOMMENDED / RESEARCH | REPO:RQ-023 RELATED | no REPO question with this number |
| MASTER:RQ-111 | Preference Archaeology | RECOMMENDED / RESEARCH | REPO:RQ-042 RELATED | no REPO question with this number |
| MASTER:RQ-112 | The Anti-Goal (What LILITH Should Never Become) | RECOMMENDED / RESEARCH | NO MATCH | no REPO question with this number |
| MASTER:RQ-113 | Cognitive Load Balancing | RECOMMENDED / RESEARCH | REPO:RQ-024 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-114 | The Explanation Contract | RECOMMENDED / RESEARCH | REPO:RQ-013 RELATED; REPO:RQ-038 RELATED | no REPO question with this number |
| MASTER:RQ-115 | The Forgetfulness Contract | RECOMMENDED / RESEARCH | REPO:RQ-016 PARTIAL OVERLAP; REPO:RQ-011 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-116 | The "What Would I Need to Know?" Reflex | RECOMMENDED / RESEARCH | REPO:RQ-023 RELATED | no REPO question with this number |
| MASTER:RQ-117 | The Memory Immune System | RECOMMENDED / RESEARCH | REPO:RQ-015 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-118 | The Preference/Policy Separation | RECOMMENDED / RESEARCH | REPO:RQ-027 PARTIAL OVERLAP | no REPO question with this number |
| MASTER:RQ-119 | The Narrative Identity Layer | RECOMMENDED / RESEARCH | REPO:RQ-001 RELATED | no REPO question with this number |
| MASTER:RQ-120 | The Research Question Register as a Living Artifact | RECOMMENDED / RESEARCH | NO MATCH | no REPO question with this number |
| MASTER:RQ-121 | Affective Continuity - Can LILITH develop persistent, causally meaningful affective states without falsely claiming subjective experience or creating welfare risk? | ADDITION / RESEARCH | NO MATCH | no REPO question with this number |

## REPO → MASTER (all 50)

| REPO | Topic (REPO register, abridged) | REPO historical status | MASTER relationship(s) |
| --- | --- | --- | --- |
| REPO:RQ-001 | What fundamentally makes LILITH the same LILITH after components are replaced? | RESEARCH | MASTER:RQ-001 SEMANTIC MATCH; MASTER:RQ-097 RELATED; MASTER:RQ-119 RELATED |
| REPO:RQ-002 | How much identity change is evolution versus replacement? | UNKNOWN | MASTER:RQ-001 PARTIAL OVERLAP; MASTER:RQ-082 PARTIAL OVERLAP; MASTER:RQ-104 PARTIAL OVERLAP; MASTER:RQ-083 RELATED |
| REPO:RQ-003 | Can an old state be restored without creating a competing identity? | RESEARCH | MASTER:RQ-001 PARTIAL OVERLAP |
| REPO:RQ-004 | How can one identity operate across Hermes, local, and cloud runtimes? | DESIGNED | MASTER:RQ-002 SEMANTIC MATCH; MASTER:RQ-051 RELATED |
| REPO:RQ-005 | Does multi-runtime execution require a leader, leases, or capability-level owner… | RESEARCH | MASTER:RQ-002 PARTIAL OVERLAP; MASTER:RQ-054 PARTIAL OVERLAP |
| REPO:RQ-006 | What should an offline runtime be allowed to do? | UNKNOWN | MASTER:RQ-002 PARTIAL OVERLAP; MASTER:RQ-053 PARTIAL OVERLAP |
| REPO:RQ-007 | How are model and runtime behavioral differences normalized? | RESEARCH | MASTER:RQ-016 PARTIAL OVERLAP; MASTER:RQ-097 RELATED |
| REPO:RQ-008 | How are duplicated cross-runtime external actions prevented? | DESIGNED | MASTER:RQ-026 SEMANTIC MATCH; MASTER:RQ-002 PARTIAL OVERLAP |
| REPO:RQ-009 | What deserves to become durable memory? | DESIGNED | MASTER:RQ-003 SEMANTIC MATCH |
| REPO:RQ-010 | When should episodic observations consolidate into semantic knowledge? | RESEARCH | MASTER:RQ-004 SEMANTIC MATCH; MASTER:RQ-033 RELATED; MASTER:RQ-106 RELATED |
| REPO:RQ-011 | How should memory decay, archive, or be forgotten? | RESEARCH | MASTER:RQ-005 SEMANTIC MATCH; MASTER:RQ-101 PARTIAL OVERLAP; MASTER:RQ-115 PARTIAL OVERLAP; MASTER:RQ-034 RELATED |
| REPO:RQ-012 | How should contradictory memories coexist and resolve? | DESIGNED | MASTER:RQ-006 SEMANTIC MATCH; MASTER:RQ-054 RELATED; MASTER:RQ-084 RELATED; MASTER:RQ-085 RELATED; MASTER:RQ-103 RELATED |
| REPO:RQ-013 | How does LILITH know why it believes a claim? | PARTIAL | MASTER:RQ-007 SEMANTIC MATCH; MASTER:RQ-033 RELATED; MASTER:RQ-034 RELATED; MASTER:RQ-075 RELATED; MASTER:RQ-094 RELATED; MASTER:RQ-114 RELATED |
| REPO:RQ-014 | Which memories should enter cognition for a task? | RESEARCH | MASTER:RQ-008 SEMANTIC MATCH; MASTER:RQ-079 PARTIAL OVERLAP |
| REPO:RQ-015 | How is inference prevented from becoming false memory? | DESIGNED | MASTER:RQ-009 SEMANTIC MATCH; MASTER:RQ-117 PARTIAL OVERLAP; MASTER:RQ-036 RELATED; MASTER:RQ-084 RELATED; MASTER:RQ-091 RELATED; MASTER:RQ-095 RELATED |
| REPO:RQ-016 | What does complete deletion require across derived data and backups? | UNKNOWN | MASTER:RQ-005 PARTIAL OVERLAP; MASTER:RQ-115 PARTIAL OVERLAP |
| REPO:RQ-017 | How is sensitive memory routed across models and runtimes? | RESEARCH | MASTER:RQ-077 PARTIAL OVERLAP; MASTER:RQ-086 PARTIAL OVERLAP; MASTER:RQ-078 RELATED; MASTER:RQ-079 RELATED |
| REPO:RQ-018 | What distinguishes a conversation, task, workflow, project, goal, routine, and a… | DESIGNED | MASTER:RQ-010 SEMANTIC MATCH; MASTER:RQ-062 RELATED |
| REPO:RQ-019 | How should conflicting goals be prioritized? | RESEARCH | MASTER:RQ-011 SEMANTIC MATCH |
| REPO:RQ-020 | How does LILITH detect stale or abandoned goals? | DESIGNED | MASTER:RQ-012 SEMANTIC MATCH; MASTER:RQ-046 RELATED |
| REPO:RQ-021 | When should deterministic playbooks replace model planning? | PARTIAL | MASTER:RQ-013 SEMANTIC MATCH |
| REPO:RQ-022 | When should a plan continue, replan, pause, or stop? | DESIGNED | MASTER:RQ-014 SEMANTIC MATCH; MASTER:RQ-063 RELATED |
| REPO:RQ-023 | How does LILITH recognize unreliable reasoning? | RESEARCH | MASTER:RQ-015 SEMANTIC MATCH; MASTER:RQ-110 RELATED; MASTER:RQ-116 RELATED |
| REPO:RQ-024 | Which runtime/model should handle a task? | DESIGNED | MASTER:RQ-016 SEMANTIC MATCH; MASTER:RQ-113 PARTIAL OVERLAP; MASTER:RQ-041 RELATED; MASTER:RQ-052 RELATED; MASTER:RQ-067 RELATED |
| REPO:RQ-025 | How is worker delegation bounded and supervised? | RESEARCH | MASTER:RQ-039 PARTIAL OVERLAP; MASTER:RQ-040 RELATED; MASTER:RQ-041 RELATED; MASTER:RQ-086 RELATED |
| REPO:RQ-026 | How should contextual action risk be calculated? | RESEARCH | MASTER:RQ-019 SEMANTIC MATCH; MASTER:RQ-108 PARTIAL OVERLAP; MASTER:RQ-018 RELATED |
| REPO:RQ-027 | Can experience safely reduce friction for repeatedly approved actions? | DESIGNED | MASTER:RQ-020 SEMANTIC MATCH; MASTER:RQ-118 PARTIAL OVERLAP; MASTER:RQ-081 RELATED |
| REPO:RQ-028 | How is approval bound to exactly what executes? | DESIGNED | MASTER:RQ-021 SEMANTIC MATCH |
| REPO:RQ-029 | How long should approval remain valid when reality changes? | RESEARCH | MASTER:RQ-022 SEMANTIC MATCH; MASTER:RQ-023 PARTIAL OVERLAP |
| REPO:RQ-030 | What happens when a high-urgency event requires authority and the user is unavai… | RESEARCH | MASTER:RQ-025 SEMANTIC MATCH |
| REPO:RQ-031 | What future actions can be safely predelegated? | RESEARCH | MASTER:RQ-024 SEMANTIC MATCH; MASTER:RQ-108 PARTIAL OVERLAP |
| REPO:RQ-032 | Which actions must remain nondelegable? | UNKNOWN | MASTER:RQ-025 RELATED; MASTER:RQ-090 RELATED |
| REPO:RQ-033 | What should happen when a call times out after it may have succeeded? | DESIGNED | MASTER:RQ-027 SEMANTIC MATCH; MASTER:RQ-062 RELATED; MASTER:RQ-064 RELATED |
| REPO:RQ-034 | How is goal success distinguished from execution success? | PARTIAL | MASTER:RQ-028 SEMANTIC MATCH; MASTER:RQ-092 RELATED |
| REPO:RQ-035 | When must verification be independent from execution? | RESEARCH | MASTER:RQ-029 SEMANTIC MATCH |
| REPO:RQ-036 | How much evidence is sufficient? | DESIGNED | MASTER:RQ-031 SEMANTIC MATCH |
| REPO:RQ-037 | How are false PASS, false FAIL, partial, and unknown outcomes measured? | RESEARCH | MASTER:RQ-030 SEMANTIC MATCH |
| REPO:RQ-038 | How is a conclusion traced back through derived facts to observations? | DESIGNED | MASTER:RQ-032 SEMANTIC MATCH; MASTER:RQ-075 RELATED; MASTER:RQ-107 RELATED; MASTER:RQ-114 RELATED |
| REPO:RQ-039 | What compensating strategies work when an external system lacks idempotency? | RESEARCH | MASTER:RQ-026 PARTIAL OVERLAP; MASTER:RQ-065 PARTIAL OVERLAP |
| REPO:RQ-040 | When should LILITH interrupt rather than wait? | RESEARCH | MASTER:RQ-048 SEMANTIC MATCH; MASTER:RQ-047 PARTIAL OVERLAP; MASTER:RQ-050 PARTIAL OVERLAP; MASTER:RQ-044 RELATED; MASTER:RQ-049 RELATED |
| REPO:RQ-041 | How can proactivity avoid becoming surveillance or manipulation? | RESEARCH | MASTER:RQ-047 PARTIAL OVERLAP; MASTER:RQ-060 RELATED |
| REPO:RQ-042 | How should correction change future behavior without overgeneralizing? | UNKNOWN | MASTER:RQ-080 SEMANTIC MATCH; MASTER:RQ-081 PARTIAL OVERLAP; MASTER:RQ-111 RELATED |
| REPO:RQ-043 | What makes continuity feel trustworthy to the user? | RESEARCH | MASTER:RQ-055 PARTIAL OVERLAP; MASTER:RQ-059 RELATED; MASTER:RQ-060 RELATED; MASTER:RQ-096 RELATED; MASTER:RQ-105 RELATED |
| REPO:RQ-044 | How do we measure continuity, identity consistency, verification quality, and in… | RESEARCH | MASTER:RQ-068 SEMANTIC MATCH; MASTER:RQ-055 RELATED; MASTER:RQ-083 RELATED |
| REPO:RQ-045 | How are model upgrades prevented from silently changing identity or judgment? | DESIGNED | MASTER:RQ-017 SEMANTIC MATCH; MASTER:RQ-072 PARTIAL OVERLAP; MASTER:RQ-083 PARTIAL OVERLAP |
| REPO:RQ-046 | What observability supports accountability without leaking personal data? | RESEARCH | MASTER:RQ-076 PARTIAL OVERLAP; MASTER:RQ-074 RELATED |
| REPO:RQ-047 | How resilient is policy to direct and indirect prompt injection? | RESEARCH | MASTER:RQ-035 PARTIAL OVERLAP; MASTER:RQ-037 PARTIAL OVERLAP; MASTER:RQ-036 RELATED |
| REPO:RQ-048 | How are secrets isolated from models, logs, workers, and clients? | DESIGNED | MASTER:RQ-038 SEMANTIC MATCH |
| REPO:RQ-049 | How are backups, migrations, and disaster recovery reconciled with identity cont… | UNKNOWN | NO MATCH |
| REPO:RQ-050 | When is LILITH safe enough to advance an autonomy level? | RESEARCH | MASTER:RQ-070 SEMANTIC MATCH; MASTER:RQ-069 PARTIAL OVERLAP; MASTER:RQ-071 RELATED |

REPO topics are abridged from the register; the register row is authoritative.
Master statuses are the v1.1 "Source status" labels, truncated at the first
semicolon; they are historical labels, not current evidence.
