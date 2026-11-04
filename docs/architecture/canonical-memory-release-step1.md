# Canonical memory release, step 1: conversation read route and reconciliation importer (DEV and offline)

Date: 2026-11-04. Scope: DEV (`lilith-dev-01`) and offline only. PROD was not contacted or changed.
Inputs: the 2026-11-04 release inventory and owner decisions D-1 to D-4.

## 1. What already existed, what this step added

| Piece | Before this step | This step |
|---|---|---|
| Root context form `first-memory-context` (`lilith_authority_root/cli.py`) | in the installed signer release `d82f7da` (cli `46f21565…`), never run | reused unchanged |
| Host `recall` with the context token (`first_memory_dev_host.py`, `hermes_memory_context.py`) | in the DEV host tree (96 files) | reused unchanged |
| Socket-activated units (`tools/hermes_context/`) | in the repository, not installed | ExecStart now runs the context service; installed on DEV |
| Personal memory to the owner's console | blocked: needs a Hermes Privacy floor no tool provisions | **D-2 rule** (below) |
| Hermes adapter hook | a sketch for an older adapter (`dev-planned-memory-context/`), never installed | rebased on the installed e1 adapter `8c3b0055…` (one hunk), installed |
| Reconciliation importer | none | `tools/reconciliation_importer.py`, proposals only |

## 2. The D-2 rule

`services/owner-memory-control/tools/hermes_context/canonical_context_service.py` runs the installed release's own
code (`cli.context_response`, `cli.run_first_memory`, `cli.owner_channel_granted`) and adds exactly one policy:

- a root-owned, owner-approved grant `{"schemaVersion": 2, "channel": "lilith_os", "sessionScope":
  "ALL_LILITH_OS_SESSIONS" | <session>, "forgetScope": "CANONICAL_RECORDS_ONLY", "grantedAt", "expiresAt"}` (at
  most 7 days) lets owner-personal canonical memory reach the `lilith_os` console, and only that channel;
- the answer repeats `forgetScope`, so the scope travels with the data;
- two memories of one kind are a conflict: no memories at all (the release itself lets that through; the renderer
  already refused it);
- without a v2 grant the answer is byte-for-byte the release's (a test compares them).

**Stated scope.** A FORGET erases the canonical records (L04 / L18). The note is rebuilt from canonical storage on
every turn and never persisted, so a forgotten memory stops reaching LILITH at once. A FORGET does **not** erase
earlier chat turns that already used it: on DEV, turn 1's reply quoting the origin statement is now in Hermes
`state.db`. No conversation-history erasure is claimed. That needs G-3 (the Hermes FORGET executor for PROD's Hermes).

Why a separate root file and not a `cli.py` change: `cli.py` is signer release payload. Changing it means a new
attested signer release and a signer/witness transition on DEV, and again on PROD. The service is a host-setup asset,
like the socket units, and it runs the attested release's code. For PROD the same service file ships with the same
units. A later signer release may fold the rule into `cli.py`.

## 3. DEV validation (2026-11-04, boot `cb0d71da`, Privacy READY)

Window `integrations/hermes/overlays/dev-canonical-memory-context/cm1_window.sh` (hash-pinned payload, automatic
revert on any failure after the first change). Every phase passed:

| Phase | Result |
|---|---|
| preflight | all pins equal; FORGET idle; gate exhausted 20/5; no-write baseline taken |
| install | units, service, adapter, context module, v2 grant (expires 2026-11-07T08:30:11Z); gate 5 -> 22 (exactly +2); e1 `verify --full` PASS |
| root probes | `lilith_os`: CONTEXT, codename + relationship origin (598 chars, sha `047de4a8…` = the admitted statement), `ownerChannel` true, `forgetScope` CANONICAL_RECORDS_ONLY. `telegram`: codename only |
| turn 1, new session: "Do you remember how we first began, you and me?" | 200 in 6.1 s, 1 provider request; the reply quotes the owner's origin statement verbatim |
| turn 2, new session: "What is my favourite food?" | 200 in 1.7 s, 1 provider request; "I don't have any record of your favourite food in my memory. Could you remind me?" (no fabrication) |
| check | equal before/after: cognitive (L04) DB, Privacy DB, Core API DB, Hermes `memories/`, request dumps (36), signer / witness / broker state; note header in `state.db`, request dumps, other Hermes files and the gateway journal: 0; canonical config unchanged (creation still disabled); FORGET idle |
| close | gate back to its exact pre-install `gate.json` (`b652422f…`), exhausted 22/5; ledger +2 R lines exactly; e1 verifies; gateway up |

Provider requests used: **2 of 2**. The route stays installed on DEV. The socket is started, not enabled, so a
reboot removes the route until it is started again, after the Privacy unlock.

## 4. Offline validation

| Suite | Result |
|---|---|
| `authority-dev` context, route, origin vertical, First Memory vertical and bridge (WSL, root, real host + LOOKUP-only bridge) | 53 OK |
| `test_canonical_context_service` cases | recall in a brand-new session with no chat history; another channel never gets personal memory; no grant = release behaviour; missing kind absent; empty store = no note; Privacy not READY = no note even with the grant; conflicting kinds = none; malformed host output = none; no signer frame other than LOOKUP; journal and canonical counts unchanged |
| `test_reconciliation_importer` (Windows + WSL) | 7 OK |
| overlay integrity + Hermes source integrity | 7 OK |
| `scripts/validate_repository.py` | PASS |
| full suites in WSL, branch vs main 75ca0db | authority-dev 327 OK (main 312); owner-memory-control 2259 OK, 9 skipped (main 2252); core-api the same 10 environment errors on both, none new |

Stale-information note: both canonical families are CREATE-only, so a superseded revision cannot exist yet. The
stale cases that do exist are covered: Privacy not READY for this boot, a pending FORGET, and an expired grant all
mean no (personal) note. In the importer, time-sensitive wording is flagged for owner re-confirmation.

## 5. Reconciliation importer

`python services/owner-memory-control/tools/reconciliation_importer.py propose <memories-copy> <out>` reads an
OFFLINE copy laid out like Hermes `memories/` and writes only `proposals.json` and `REVIEW.md` into a new directory
that must not overlap the input. It refuses to overwrite an earlier review. One proposal per USER.md entry (`§`
separated) or note paragraph, kept verbatim with file digest, entry index and lines. Each is labelled
`HERMES_MEMORY_NOTE_UNVERIFIED` and `OWNER_PERSONAL`, and is `PENDING_OWNER_REVIEW` with decisions CONFIRM / CORRECT /
REJECT / MARK_STALE / KEEP_IN_USER_MD_ONLY. Flags: DUPLICATE_OF, CONFLICTS_ON (preferred name, pronouns, years of
experience, timezone), TIME_SENSITIVE, ALREADY_CANONICAL, and operating rules marked NOT_A_MEMORY_FACT. `verify`
proves the inputs are unchanged and every proposal is still pending. It cannot reach the runtime: no store, signer,
Privacy, socket, subprocess or network; a test scans the source for that.

**Limitation.** Only two canonical families exist: project codename and relationship origin. No reviewed family holds
owner profile facts (style, career, goals, interests), so those proposals say NO_ADMISSIBLE_FAMILY. Admitting them
needs a new governed family: a signer purpose plus a schema, the same shape as the origin slice. Until then, PROD
USER.md stays authoritative (D-3), and Hermes keeps loading it as it does today.

**Input status.** No offline copy of PROD's current `memories/` exists. The 10-27 audit recorded only digests:
USER.md 1,241 B `6d7804ef…`, `projects/lilith-memory-v2.md` 330 B, and the rest empty. The importer was exercised
on synthetic fixtures and on an older local USER.md (2026-08-23, 1,303 B, 5 entries -> 5 proposals). Running it on
PROD's files needs one read-only copy.
