# G3 (PREPARED, NOT APPROVED, NOT RUN)

Stages R3 to R9 of `prod-rehearsal-v0.1/REHEARSAL-RUNBOOK.md`, as two approvals, because only the second touches real data.

| Part | Does | Real data? |
|---|---|---|
| **G3-A** `a_prepare.ps1` | Saves the project policy; removes `github-lilith-deployer@`'s project-wide `roles/iap.tunnelResourceAccessor` and `roles/compute.osAdminLogin`; adds and proves the guest DNS guard; dry-runs the whole flow on the synthetic disk | **none** |
| **G3-B** `b_open_and_rehearse.ps1 -ConfirmOpen OPEN-REAL-DATA-G3` | One disk from the snapshot, attached read-only; allow-listed copy; baseline; current code as control; target code; compare; timed rollback | **yes** |

**G3-B refuses** unless G3-A passed, `DECISIONS-SIGNED.txt` exists, the bindings are still gone, the snapshot id matches, the VM is still isolated, and `guest_dns_check.sh` passes **before the disk is created.** The guest checks again before mounting. A reboot clears the guard.

## G3-A failure recovery

The policy is captured, re-parsed from the saved file and checked before any change, and it must read the same twice. After the removals, the live policy must equal the saved one minus exactly those two bindings, and the owner must log in to the VM with `sudo`. **Any later failure, or an exception, adds back exactly those two bindings,** and confirms them. Recovery is refused if a real-data copy exists or can't be ruled out, and that outcome is reported in `a\RESULT.txt`. It only ever adds those two bindings, and never rewrites the policy.

## Effect of G3-A on deployers

**PROD deploys stop working until access is granted again,** which is intended: the workflow is dispatch-only, and none is planned. Cutover 1 grants narrower, `lilith-01`-only access. DEV's deployer uses its own instance-level access and isn't touched. `restore_deployer.ps1` undoes it, and refuses while the real-data copy exists.

## What the rehearsal compares

The old code runs first as a **control** for one 120-second maintenance tick, because Core API has a background thread. The target code must then produce exactly the same result. Any other difference stops it.

## Not done here

**Assembled-prompt comparison is left out of G3:** Cutover 1 touches nothing feeding the persona, so file hashes prove it. It belongs to Cutover 2's rehearsal, with real replies.

Transport loss during G3-B: stop, and read the VM's evidence. It never reruns: `started` refuses.

## After G3

Destroy the copy and working tree under their own approval, within 7 days. The snapshot stays until its retention decision.

## Offline evidence

| Check | Result | Kind |
|---|---|---|
| `tests/run_tests.ps1` | see `tests/run_tests.out` | cloud scripts, scripted `gcloud`, every failure point |
| guest flow | full PASS; a changed row stops it; a second run refuses; no key or `.env` copied | real script, stand-in Core API, WSL |
| Core API on a PROD-shaped store | in #311 | real code |

**The DNS rule itself can't be tested offline:** WSL has no `iptables`. G3-A measures it on the VM: the path must answer first, then direct UDP, direct TCP and the resolver must all fail, with metadata HTTP still working. A read-only check today confirmed that the path answers, and that the VM has `iptables`.

**Not run on the VM:** the guard, the guest flow, or either cloud script. G3-A's dry run proves the first two before real data arrives.
