# Slice 15B2b-B1b-3e — M-B1 Sequence Continuity: Owner Decision

Status:

- **`MB1_SEQUENCE_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_HANDOFF`**
  (owner decision, 2026-10-06). It defines "same continuous sequence" for
  the DEV_SYNTHETIC M-B1 procedure, and resolves the continuity gaps G-A …
  G-E of the
  [M-B1 handoff preflight](slice-15b2b-b1b3e-mb1-handoff-preflight.md) (§3).
- It refines the
  [carry-forward owner decision (B)](slice-15b2b-b1b3e-mb1-eligibility-carry-forward-owner-decision.md),
  which stays in force.
- **Governance semantics only.** It introduces no bridge token, nonce,
  signed artifact, handoff file, implementation or runtime mechanism. No
  code, script, bundle or workflow changed.
- **It authorizes nothing.** It does not authorize the runbook in §4, the
  M-B1 go, M-B1 / K-ROOT generation, K-WIT, registry / genesis mutation or
  First Memory. Owner freshness is `FRESHNESS=UNKNOWN`. No live system was
  contacted.

```text
continuity defined != sequence authorized != PR1B_ELIGIBLE != M-B1 go != K-ROOT generated
```

| Field | Value |
| --- | --- |
| Control `main` at the decision | `4c38ddc464458df0c912d668d2558259dab2c7b5` (merge of PR #147) |
| Latest DEV deployment supplied as context | workflow run `37417296089` (not verified in this pass) |

## 1. Owner decision (verbatim)

> I adopt `MB1_SEQUENCE_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_HANDOFF`.
>
> For the DEV_SYNTHETIC M-B1 procedure, “same continuous sequence” means one
> explicitly owner-authorized, owner-attended governance sequence. It is not tied
> to a Python process, shell, terminal, Claude session, network connection, host,
> or physical device.
>
> The required transition from laptop to S25, including the accepted MTP transfer,
> unplugging the phone, enabling airplane mode, and continuing manually in Termux,
> does not by itself break continuity.
>
> There is no wall-clock TTL. A finite delay alone does not end the sequence.
>
> Laptop lock or sleep, terminal closure, shell exit, Claude session end, or
> transient laptop network loss do not by themselves end the sequence, provided
> they do not cause or conceal a stop condition, relevant drift, reboot, process
> replacement, deployment, loss of custody, or other uncertainty about required
> current evidence. If such uncertainty arises, the sequence ends and must restart
> from fresh eligibility.
>
> After fresh DR-5 has been established, merges to `main`, manual deployments,
> and other actions capable of changing the relevant DEV deployment state are
> frozen until M-B1 completes or the sequence aborts.
>
> DEV-side conditions do not need to be actively re-polled after `PR1B_ELIGIBLE`
> solely for the laptop-to-S25 handoff. However, no B-5 §9 stop condition or
> G-1…G-9 invalidator may be known, suspected, or become uncertain. If one occurs
> or its absence becomes uncertain, the sequence ends; eligibility is not reusable.
>
> The accepted owner-run phone/Replica-B/custody block must be repeated inside the
> same future M-B1 sequence before the final Condition 3 and `CHECK_ELIGIBILITY`.
>
> After the fresh final Condition 3, `CHECK_ELIGIBILITY` is called exactly once.
> It must return `PR1B_ELIGIBLE`.
>
> Only after that result may I issue the separate M-B1 go statement. That go must
> name the accepted script and bundle pins and is scoped to exactly one invocation
> of the pinned M-B1 procedure within that same sequence.
>
> The go authorizes M-B1, which is `GENERATE_K_ROOT`. At C0, my explicit
> `GENERATE` confirmation is the act that permits K-ROOT generation.
>
> If G0, G1, T1, or any other script `STOP:` occurs before C0, no K-ROOT is
> generated, the sequence ends, and the go cannot be reused. If a STOP occurs
> after K1, failed-candidate custody rules apply and there is still no retry under
> the same sequence/go.
>
> Any explicit owner pause, suspension, abandonment, or end of the ceremony; any
> B-5 §9 stop; any G-1…G-9 invalidator; any unreviewed deployment after the DR-5
> freeze; relevant reboot or dependency drift; loss of phone custody; unexpected
> remote-access state; script/bundle mismatch; or deviation that creates uncertainty
> about the accepted evidence ends the sequence.
>
> When a sequence ends after eligibility but before successful M-B1 completion,
> its `PR1B_ELIGIBLE` result remains historical only and is not reusable for another
> M-B1 attempt.
>
> A fresh PR-2 immediately before `GENERATE_K_WIT` remains mandatory. This M-B1
> continuity decision does not authorize K-WIT, registry/genesis mutation, First
> Memory, or any later bootstrap step.
>
> This decision defines governance semantics only. It introduces no new bridge
> token, nonce, signed artifact, handoff file, implementation, or runtime mechanism.

## 2. Semantics recorded

**What continuity is.**

- Continuity is **governance continuity**: one explicitly owner-authorized,
  owner-attended sequence.
- It is **not** process, shell, terminal, Claude-session, network, host or
  device continuity. This matches the code: the evaluator's state is
  in-process only, and the pinned M-B1 script reads no eligibility state
  (preflight §2).
- The required laptop → S25 transition (accepted MTP transfer, unplug,
  airplane mode, manual Termux) **does not** end the sequence.
- **No wall-clock TTL.** A finite delay alone is not termination.

**Not intrinsic terminators.** Laptop lock or sleep, terminal closure,
shell exit, Claude session end and transient laptop network loss do not by
themselves end the sequence. **If one of them causes or conceals** a stop
condition, relevant drift, a reboot, process replacement, a deployment,
loss of custody, or other uncertainty about required current evidence,
**the sequence ends** and must restart from fresh eligibility.

**Deploy freeze.** From the moment fresh DR-5 is established until M-B1
completes or the sequence aborts: no merge to `main`, no manual deployment,
and no other action capable of changing the relevant DEV deployment state.

**DEV side after eligibility.** No active re-polling is required solely
for the handoff. No B-5 §9 stop or G-1 … G-9 invalidator may be known,
suspected or uncertain. If one occurs, or its absence becomes uncertain, the
sequence ends and its eligibility is not reusable.

**Eligibility inside the sequence.**

- The accepted owner-run phone / Replica B / custody block (packet refresh
  §2.3–§2.4 procedure) is **repeated inside the sequence, before** the final
  Condition 3 and `CHECK_ELIGIBILITY`.
- The final Condition 3 is fresh.
- `CHECK_ELIGIBILITY` is called **exactly once** and must return
  `PR1B_ELIGIBLE`.

**The go.**

- It is given **only after** that `PR1B_ELIGIBLE` result.
- It must name both accepted pins:

  | Pin | SHA-256 |
  | --- | --- |
  | phone operator script | `09cbc9bee7b58af7bab45bb903c6e10cb51ae6c62b20705be12de274bbe5216b` |
  | M-B1 bundle | `7f07e158aa5a0b3c31ee63e25ae25116c92f26a402bc6924422d7c95e2edc2c1` |

- It is **one-attempt and sequence-scoped**: exactly one invocation of the
  pinned M-B1 procedure, within that same sequence.
- **M-B1 == `GENERATE_K_ROOT`** (P3-5 step 1; package K1).
- **At C0, the owner's explicit `GENERATE` confirmation is the act that
  permits K-ROOT generation** in that invocation.

**STOP semantics.**

- A `STOP:` before C0 (G0, G1, T1 or any other): no K-ROOT is generated, the
  sequence ends, and the go cannot be reused.
- A STOP after K1: [failed-candidate custody](slice-15b2b-b1b3e-mb1-kroot-ceremony-package.md)
  (§6) applies, and there is no retry under the same sequence or go.
- If the sequence ends after eligibility but before successful M-B1
  completion, its `PR1B_ELIGIBLE` result is **historical only**, not reusable
  for another M-B1 attempt.

**Sequence terminators** (any one ends the sequence):

- an explicit owner pause, suspension, abandonment or end of the ceremony;
- any B-5 §9 stop;
- any G-1 … G-9 invalidator;
- any unreviewed deployment after the DR-5 freeze;
- a relevant reboot or dependency drift;
- loss of phone custody;
- an unexpected remote-access state;
- a script or bundle mismatch;
- a deviation that creates uncertainty about the accepted evidence.

**Unchanged.** A fresh PR-2 immediately before `GENERATE_K_WIT` remains
mandatory and separate. This decision authorizes no K-WIT, registry /
genesis mutation, First Memory or later bootstrap step.

## 3. Gap reconciliation

| Gap ([preflight](slice-15b2b-b1b3e-mb1-handoff-preflight.md) §3) | Resolution | State |
| --- | --- | --- |
| G-A continuous-sequence definition | governance continuity; non-terminators and terminators listed (§2) | **RESOLVED** |
| G-B post-eligibility DEV-side treatment | no re-polling for the handoff; any known, suspected or uncertain §9 / G-1 … G-9 ends the sequence | **RESOLVED** |
| G-C deploy freeze | frozen from fresh DR-5 until M-B1 completes or aborts | **RESOLVED** |
| G-D fresh phone-side evidence | the owner-run phone / Replica B / custody block is repeated in the sequence before final Condition 3 | **RESOLVED** |
| G-E owner-attended laptop → S25 bridge | the bridge is owner-attended governance continuity; no artifact | **RESOLVED** |
| go timing and consumption | after `PR1B_ELIGIBLE`; one attempt; consumed by C0 `GENERATE` | **RESOLVED** |

## 4. Resulting future sequence (documentation only; NOT executed, NOT authorized)

| # | Step | Basis |
| --- | --- | --- |
| 0 | the owner explicitly authorizes one continuous M-B1 sequence | this decision |
| 1 | clean, current repository prerequisite checks (clean tree; HEAD = `origin/main`) | carry-forward decision B, step 1 |
| 2 | Condition 1 / current pins: merge-base `1e2eae3`, the 17 bundled sources equal `origin/main`'s, staged tar `7f07e158…` and script `09cbc9be…` | [final pins](slice-15b2b-b1b3e-mb1-final-package-pins.md) §4 |
| 3 | fresh DR-5 through the latest deployment (every deploy since `37356261343`), nothing queued; **the deploy freeze starts** | validity-window trigger (f); packet §11; this decision |
| 4 | evaluator environment / import-only preflight, as needed (no evaluator call) | [Sequence 3](slice-15b2b-b1b3e-pr1b-eligibility-sequence3.md) §3 method |
| 5 | B-5 grant usability; no §9 stop; no G-1 … G-9 | B-5 packet §9; policy §2 |
| 6 | fresh owner-run phone / Replica B / custody block | this decision; packet refresh §2.3–§2.4 |
| 7 | fresh final Condition 3 | [validity-window decision](slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md) |
| 8 | `CHECK_ELIGIBILITY` exactly once; require `PR1B_ELIGIBLE` (otherwise the sequence ends) | carry-forward decision B |
| 9 | the owner gives the one-attempt M-B1 go naming both pins | this decision; packet §12 template |
| 10 | laptop: verify both hashes; MTP transfer; unplug; airplane mode on | [ceremony package](slice-15b2b-b1b3e-mb1-kroot-ceremony-package.md) §3 |
| 11 | S25: script hash check; run; G0 / G1 / T1 | package §3, §5 |
| 12 | C0 `GENERATE` (the owner's permission for K-ROOT generation) | package script C0; this decision |
| 13 | K1 `root-keygen` = `GENERATE_K_ROOT` (M-B1) | package K1; P3-5 step 1 |
| 14 | the accepted export, custody and review flow (public-only export; fingerprint recorded on the phone, E-21) | package §3, §6–§8 |
| 15 | the sequence completes (`RUN_EXIT=0`, `MB1_KROOT_GENERATED`) or aborts; the deploy freeze ends | this decision |

Any terminator in §2 at any step ends the sequence. A fresh PR-2
immediately before `GENERATE_K_WIT` stays a separate, later requirement.

## 5. State

```text
MB1_SEQUENCE_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_HANDOFF
CONTINUITY = GOVERNANCE CONTINUITY (NOT PROCESS / SHELL / TERMINAL / SESSION / NETWORK / HOST / DEVICE)
LAPTOP -> S25 HANDOFF (MTP, UNPLUG, AIRPLANE MODE, TERMUX) DOES NOT END THE SEQUENCE
NO WALL-CLOCK TTL; FINITE DELAY ALONE IS NOT TERMINATION
LAPTOP LOCK / SLEEP / TERMINAL CLOSE / SHELL EXIT / CLAUDE SESSION END / TRANSIENT LAPTOP NETWORK LOSS: NOT INTRINSIC TERMINATORS
UNCERTAINTY ABOUT REQUIRED CURRENT EVIDENCE ENDS THE SEQUENCE
DEPLOY FREEZE FROM FRESH DR-5 UNTIL M-B1 COMPLETES OR ABORTS
NO ACTIVE DEV RE-POLLING REQUIRED FOR THE HANDOFF
KNOWN, SUSPECTED OR UNCERTAIN B-5 §9 STOP OR G-1…G-9 ENDS THE SEQUENCE
OWNER-RUN PHONE / REPLICA B / CUSTODY BLOCK REPEATED IN-SEQUENCE BEFORE FINAL CONDITION 3
FINAL CONDITION 3 FRESH
CHECK_ELIGIBILITY EXACTLY ONCE; PR1B_ELIGIBLE REQUIRED
M-B1 GO ONLY AFTER PR1B_ELIGIBLE
M-B1 GO ONE-ATTEMPT AND SEQUENCE-SCOPED; NAMES BOTH PINS
M-B1 == GENERATE_K_ROOT
C0 GENERATE PERMITS K-ROOT GENERATION IN THAT INVOCATION
STOP BEFORE C0: NO K-ROOT; SEQUENCE ENDS; GO NOT REUSABLE
STOP AFTER K1: FAILED-CANDIDATE CUSTODY; NO RETRY UNDER THE SAME SEQUENCE OR GO
ENDED SEQUENCE: PR1B_ELIGIBLE HISTORICAL ONLY; NOT REUSABLE
FRESH PR-2 IMMEDIATELY BEFORE GENERATE_K_WIT REMAINS MANDATORY AND SEPARATE
NO BRIDGE TOKEN, NONCE, SIGNED ARTIFACT, HANDOFF FILE, RUNTIME STATE OR IMPLEMENTATION
G-A … G-E RESOLVED
RUNBOOK NOT AUTHORIZED; NOT EXECUTED
M-B1 GO STATEMENT NOT GIVEN
M-B1 = NOT AUTHORIZED
KROOT = NOT AUTHORIZED
KWIT = NOT AUTHORIZED
REGISTRY / GENESIS MUTATION = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED
```

> **Later current state (2026-10-06, pointer only; the text above is
> preserved as written).** The owner-authorized M-B1 sequence ran under
> this continuity decision and completed: `CHECK_ELIGIBILITY` returned `PR1B_ELIGIBLE`
> once, the one-attempt M-B1 ran with `RUN_EXIT=0`, and the owner accepted
> M-B1 / `GENERATE_K_ROOT` as completed
> ([M-B1 completion and owner acceptance](slice-15b2b-b1b3e-mb1-kroot-completion.md);
> E-21 `publicKeySha256=cb36daf1…92cf`). K-WIT, registry / genesis, record 1
> and First Memory remain NOT AUTHORIZED.
