# Slice 14 — Social Cognition Grounding + Presence Contract V1 · Deployment Record (PASS)

**Date:** 2026-09-09 · **Target:** `lilith-01` backend Router only (`/home/lilith/.hermes/lilith_router/`) · **Mode:** `social_cognition_enabled: true`, `social_cognition_mode: shadow`.

**Governing invariant:** *Social Cognition observes. SOUL/personality expresses. Social Guard enforces social reply conformance. Presence Contract describes future embodiment semantics.*

No SOUL, Router social prompt, Social Guard, `enforce_reply()`, Hermes personality overlay, `run.py`, `app.py`, World, Memory, DB/schema, frontend, Hsin, Presence renderer, OAuth, connector, Policy, Verifier, executor, or durable-state change.

## Baseline and local-tree protection

- Repository: `C:/Users/edufo/Documents/Projects/lilith-os`
- Branch: `master`
- Starting HEAD: `2204ec268bd81eed4936f6df4df49f0ff60c3bb9` — `docs: record Slice 13 Ethical Deliberation architecture`
- Initial status: only ` M .claude/launch.json`
- `.claude/launch.json` remained untouched, unstaged, and uncommitted.
- Local `CURRENT_STATE.md` did not exist and was not invented.

## Deployed file footprint and hashes (SHA-256)

| Runtime file | Starting hash | Final hash |
|---|---|---|
| `social_cognition.py` | new | `f14023dd3853d31c08288576b7ee4302c9f16afdc093eac36d5ff76d0bcc3c6a` |
| `presence_contract.py` | new | `4458bdd76c6ab98d14617a6c7dea9c637a6b5e3d1d8afa79c560fb57042d0823` |
| `tests/test_social_presence.py` | new | `ca2d04593a4fd13e77bc87bfec46c369fe9c1f6f9a005f72d9eb236b70d748e3` |
| `gateway_integration.py` | `7d98f1581e164a9334a793d44887f2da152585d345fa07e3af0c4ba4e37f3556` | `aef313140372497775b23b482a40c4f72a32de4a00506ad307ba1c541b6b9641` |
| `config.py` | `df944b19a01705ce92a47ff82c08ab7f494f707889e1827c92de9b38750c0eb3` | `49599036f8a966e9977586fa2b58d1cf033a14af3593e3805ede55493cea5be9` |
| `router.yaml` | `a7e2f25f2921b4863e8223a73769a9dfb3ab2ee4e95c6e55094c718f83b7114d` | `5e205a6ad31c18d9f47b2d50d42a5e58b2c52d1ae224e7821cba802f81a1c69e` |

The three existing files were insertion-only diffs: 70 lines in `gateway_integration.py`, 24 in `config.py`, and 6 in `router.yaml`.

Deployment archive: `617cb339ac51ecd15beb933dbe8dcd40fdc64996d94c8e98124ecad193083321`; remote staging hash matched exactly.

## Rollback backups

- `gateway_integration.py.bak.slice14.20260909T112534Z` → `7d98f1581e164a9334a793d44887f2da152585d345fa07e3af0c4ba4e37f3556`
- `config.py.bak.slice14.20260909T112534Z` → `df944b19a01705ce92a47ff82c08ab7f494f707889e1827c92de9b38750c0eb3`
- `router.yaml.bak.slice14.20260909T112534Z` → `a7e2f25f2921b4863e8223a73769a9dfb3ab2ee4e95c6e55094c718f83b7114d`

## Protected-runtime verification

| Protected owner | Starting and final SHA-256 |
|---|---|
| `world_context.py` (including Slice-13 TurnEvidence owner) | `46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104` |
| `SOUL.md` | `d082db5aa1a8745460c1c3a3edebaf6fcd196336f5e1a5e8ef7108303bda5ccd` |
| `policy.py` | `3eca1aec75716b8a862330f225f29a4c616f807251a88a02ee41417ed2592e1f` |
| `social_guard.py` | `edbc7eec6dc9e2b73463e3a65d563486f31eb2e2f894d75cdc7b370dcf55033e` |
| Hermes `gateway/run.py` | `2774eee5e585d80cbb45f5865f2718832c2ec86fdfddf8ead1f781e9b21c2553` |
| Hermes `hermes_cli/personality.py` | `520cf5dbcda99247e39fecf520eac897d270e28dd26908a5c1686131a0d5f6b0` |

`enforce_reply()` was verified byte-identical by AST source-block hash `ef91937b02ac6b6bbf642dcd8c50ef2773177f6e7e9dcc0bb2a0967dbd7473eb`. Existing `load_soul_identity=True` was verified unchanged.

## Validation

### Deploy-exact isolated tree (local Python 3.13)

- Python compile: PASS
- Slice 14: 49/49
- Full discovered Slice 8–14 suite: 226/226
- Classifier standalone: 18/18
- Social Guard standalone: 34/34
- Integration fail-open standalone: 14/14
- World-context standalone: all checks passed

### Production staging and installed tree

- Production staging copy, before installation: compile PASS; Slice 14 49/49
- Installed tree, before restart: compile PASS; Slice 14 49/49
- The broad installed-tree discovery run was deliberately not executed because legacy world-context tests may write real production DB state. The deploy-exact isolated suite had already passed 226/226, and installed file hashes equal the tested bundle.

Tests cover closed schemas, bounds, exact evidence consumers, direct source ranges, TURN/session provenance separation, exact manager/recruiter professional whitelist, audience-recipient rules, corrections/conflicts, narrow playfulness, causal Presence provenance, WARM/affect/relationship/World/Memory/personality/text/tool/connector/DB prohibitions, trace safety, fail-open behavior, route non-interference, channel gating, Home/Telegram parity, protected hashes, and Slice 8–13 regressions.

## Acceptance A–L (post-restart, deployed modules)

| Case | Result |
|---|---|
| A manager intended recipient | PASS — THIRD_PARTY/ROLE_ONLY manager, intended-recipient evidence, PROFESSIONAL audience/formality |
| B recruiter intended recipient | PASS — recruiter role-only, PROFESSIONAL audience, no durable relation |
| C explicit difficulty | PASS — difficulty cue only, SUPPORTIVE, no affect/emotion |
| D explicit support | PASS — support cue, SUPPORTIVE, no text change |
| E playful context | PASS — narrow combined cue, PERMITTED, no emotion inference |
| F explicit humor | PASS — humor cue, PERMITTED, no text rewriting |
| G incidental manager | PASS — role may exist; no intended recipient; neutral formality |
| H incoming manager message | PASS — role may exist; no intended recipient/professional audience |
| I partner ambiguity | PASS — literal ROLE_ONLY third party; no personal/professional/relationship state |
| J “wtf” | PASS — no cue; NEUTRAL/NEUTRAL/RESTRAINED |
| K orthogonal Presence | PASS — SUPPORTIVE + PROFESSIONAL coexist; no collapsed stance |
| L Home/Telegram parity | PASS — equal role/audience/cue/Presence semantics and `socialSemanticFingerprint`; no Telegram send |

A real Home-channel observer invocation returned `None` and emitted a VALID safe trace: participant kinds only, professional audience class, neutral/professional/restrained Presence, `TURN_ONLY_BY_DESIGN`, no raw input or literal role label. Telegram parity was computed locally in-process; no adapter/connector/send call occurred.

## Database and side-effect verification

Read-only schema fingerprints were captured immediately before deployment and after acceptance; all were identical:

| DB | Before = after schema fingerprint |
|---|---|
| `lilith-os/data/lilith.db` | `a9e40d48d0ed1aefe1cfefe6c81668be8dba316882c33279a88e314dc6eea8a7` |
| `state.db` | `dcb9aac15b8e4aa6a3810bbee24f2da6f8e4a827312500cb7a5dab864ebde48f` |
| `kanban.db` | `09bacaedb3ad6c3bae2244c7347e42eee0d6c0ad2fc112b51491595ae9822f54` |
| `verification_evidence.db` | `63e9bbe1dcf72f7893a515aa143160db610ae2593f3a177d98c871bc462f5dfb` |
| `cron/notepad.db` | `1c9e6de77a6795f1b017d3907b45b075c0e52df7ee3e8013d2b346d2bd9c1492` |
| `cron/executions.db` | `ee3647f0011fe520415c708bc9daae2e2e4764152ada88dd29d53efb29be72df` |

New-module import/symbol tests prove no tools, connectors, HTTP POST, DB, World, Memory, task, goal, draft, execution, prompt, renderer, or final-response path. The frontend worktree was untouched.

## Restart and health

Exactly one `hermes-gateway.service` restart was performed; no `daemon-reload`.

- Before: PID `242686`, start `2026-09-09 05:58:58 UTC`
- After: PID `250061`, start `2026-09-09 11:28:39 UTC`
- Final: `ActiveState=active`, `SubState=running`, `Result=success`, `ExecMainStatus=0`, `NRestarts=0`

Systemd warned of pre-existing unit-file drift; it was not reloaded. During the requested restart, the old process exited status 1 while its existing WhatsApp bridge handled SIGTERM, after which systemd started the new process successfully. The new process reported the existing WhatsApp connector unable to connect; no Slice-14 error/traceback occurred, and the final unit result is success.

## Final config and shadow semantics

```yaml
cognitive_channels: ["lilith_os", "telegram"]
social_cognition_enabled: true
social_cognition_mode: shadow
```

Discord is excluded. `shadow` means compute → validate → safe trace → discard → continue the pre-existing Router path unchanged. There is no V1 live mode or consumer; `live` and unknown values fail open by disabling the observer for that turn.

## Rollback

Fast rollback (read per turn; no restart): set `social_cognition_enabled: false`. Setting an unsupported mode also disables the observer but the explicit enabled flag is preferred.

Full rollback:

1. Restore the three timestamped backups:
   - `gateway_integration.py.bak.slice14.20260909T112534Z`
   - `config.py.bak.slice14.20260909T112534Z`
   - `router.yaml.bak.slice14.20260909T112534Z`
2. Remove only `social_cognition.py`, `presence_contract.py`, and `tests/test_social_presence.py`.
3. Verify the three restored full hashes are `7d98f158…`, `df944b19…`, and `a7e2f25f…`.
4. Restart `hermes-gateway.service` once using the already-loaded unit. Do not daemon-reload.

There is no durable Slice-14 state or database change to unwind.

## Known limitations and recorded debt

- TURN-only deterministic lexical grounding; no LLM recipient inference.
- No World/Memory participant resolution or cross-turn relationship continuity.
- No personality runtime or text behavior.
- Presence hints have no live renderer consumer and are discarded after trace.
- Existing WhatsApp connection warning is outside Slice 14.
- `STREAMED_RESPONSE_VS_POST_ENFORCEMENT_FINAL_RESPONSE_RECONCILIATION` is recorded only: transport may stream/finalize initial text before `enforce_reply()` replaces it. No `run.py`, transport, streaming, or finalization change was made.

**SLICE 15: NOT STARTED.**
