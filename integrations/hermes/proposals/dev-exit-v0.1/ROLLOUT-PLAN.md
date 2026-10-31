# Production rollout plan (PROPOSAL, nothing approved)

**`MIGRATION-PLAN.md` sets the sequence and what's in Cutover 1.** The acceptance checks and rollback triggers below still apply.

**Goal: upgrade the existing LILITH, keeping her identity and real state.** Not a replacement, and not one big switch: each stage ends at a checkpoint you can stop or return from. **Each stage needs its own owner approval.**

| # | Stage | Done when | Return path | Items |
|---|---|---|---|---|
| 1 | **Final DEV baseline** | e1 accepted (done); one deliberate live return from e1 to p1 and forward again; A3 window read | previous release | A1, A3, A5, A34 |
| 2 | **Security and FORGET hardening** | Auth stages on DEV; FORGET drill with canaries; restore proven | env flip; `open-acknowledged` | A14 to A16, A19 to A21 |
| 3 | **Isolated snapshot rehearsal** | R0 to R9 pass with no unexplained difference | destroy the copy | A2, A7 to A11, A18, A23, A25, A29 to A31 |
| 4 | **Migration candidate review** | One tagged candidate, build reproducible, owner reads the difference from PROD | don't proceed | A9, A10, A26 to A28, A36 |
| 5 | **Backup and rollback readiness on PROD** | Scheduled off-host backups, one real restore test, least privilege. **First PROD change, and it changes no cognition** | ordinary | A17 prep, A22, A24, A32, A33, A35 |
| 6 | **Controlled deployment** | One window: fresh snapshot, schema, Core API, Hermes, lanes per the signed table, FORGET, auth, narrowed firewall and tunnel access | **snapshot taken minutes before; timed in rehearsal** | A17, A21, A37 |
| 7 | **Post-deployment validation** | Identity, data and capability checks below | same snapshot, until the owner closes it | A37, A38 |
| 8 | **Gradual live activation** | Motivation, Planning, Ethics, one at a time, each a window with its own budget | that lane's flag | A4 |
| 9 | **Back to DEV-first advanced work** | See `ADVANCED-ROADMAP.md` | | |

**DEV stops growing after stage 1.** PROD is idle, so there's no traffic to dual-run against, and a long overlap only adds risk.

## Acceptance at stages 6 and 7 (A36, A37)

Fixed and signed **before** the window, so they can't be fitted to the result.

| Check | Pass |
|---|---|
| Fingerprints | `SOUL.md`, `USER.md` unchanged, or changed as signed |
| Data | every store's rows and digests match the pre-window snapshot, except signed changes |
| Identity | fixed prompt set judged by the owner against the rehearsal baseline |
| Memory | one recall of a real, owner-chosen fact |
| Career | one real read |
| FORGET | drill on canaries, every route fired, nothing returns |
| Auth | a stranger gets 401; the owner's turn is grounded |
| Route in | only named IAP accessors reach 8765, and it answers none of them without a credential |
| Provider | budget and fallback as configured; bytes per lane within the rehearsal's numbers |
| Host | no failed units, no unexpected restarts |
| Capabilities | every PRESERVE row passes; every DISABLE row is off |

## Monitoring and rollback triggers (A38)

**Window: 7 days, reviewed daily.** Any of these starts the return, with no discussion in the moment:

- A persona or identity failure on the fixed prompts.
- Any row lost or changed unexpectedly.
- A canary or erased item reappearing.
- Any 401 on a real caller that isn't understood, or grounding silently gone.
- Provider spend over the signed limit, or a fallback not in the plan.
- A write from a GET.
- A failed FORGET.

**Returning after new data has arrived loses that data,** so the plan names how long the snapshot return stays allowed: the proposal is 48 hours, then fix forward.
