# Slice 15B2b-B1b-3e — M-B10 First Post-Freeze Deploy: Post-HELD DR-5 Preservation (2026-10-11)

Status:

- **ADDENDUM (APPEND-ONLY) TO THE [M-B10 COMPLETION RECORD](slice-15b2b-b1b3e-mb10-held-completion.md).** That
  record states `FIRST_POST_FREEZE_DEPLOY = NOT YET OCCURRED` and `POST_FREEZE_DR5_W10_1 = PENDING`. It was correct
  when written and is not rewritten. This addendum supersedes it on those two points only, from 2026-10-11.
- `FIRST_POST_FREEZE_DEPLOY = OCCURRED`; `POST_FREEZE_DR5_W10_1 = EQUAL`; host POST `MB10_HOST_POST_PASS`. The owner
  recorded this preservation as **VERIFIED** in the M-B11 kickoff checkpoint (2026-10-11).
- **Documentation only.** Writing this addendum contacted no live system and **does not reproduce the live proof**:
  it records evidence that was produced and observed earlier, with references. It authorizes nothing: M-B11 (signer),
  Registry V1 effectiveness, authority activation, First Memory and PROD stay **NOT AUTHORIZED**.

```text
deploy EQUAL != HELD evidence (the deployer cannot observe the hold store; only the root W10 verifier proves HELD)
historical verification != proof of an indefinitely unchanged live host;  this addendum merged != a new live proof
```

## 1. The deploy

| Item | Value |
| --- | --- |
| run | `38162573937`, "Deploy LILITH Core API to DEV", `workflow_run`, branch `main`, **SUCCESS**, 2026-10-11 (checkout of the validated commit at 18:08:51Z) |
| deployed revision | `5e83bd187e7f44feae7acae13adcd6370625a195` (merge of PR #181, the M-B10 completion record) |
| deploy log (owner-local) | 1931 lines, SHA-256 `465ae4fc8f06b961aad72cb3e6e9030b1784c0597462222414dae05fc9d34c1a` |

## 2. DR-5 under the independently verified W10 phase

`mb10_dr5_target.py compare W10_1_HELD_EXACT <deploy-log>` (tool SHA-256
`29c359617605f67e812732c4bb6a9ca1b9439bfffcf22285e44d9f6c1999ccf0`, target `WITNESS_RUNNING_HELD`):

| Set | Lines | SHA-256 | Target |
| --- | --- | --- | --- |
| result set | 192 | `593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65` | equal |
| DR-5 block | 153 | `ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a` | equal |
| pre-deploy block | 29 | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` | equal |

Result **`EQUAL`**: 0 `ALLOWED`, 0 `FAIL`, `unequal = []`. Comparison output (owner-local) SHA-256
`f41f4d5c118c97aa90f113a2348747c096a0d0f90255e92d28abc2f3a7ff13d0`. The target stays a derived, phase-bound
comparison target (`targetAccepted: false`); it is not a new global baseline.

## 3. Host POST after the deploy

`mb10_operator.py host POST` of sequence `e2f5cb54bbb369be81fe5f0a0a143618`, completed 2026-10-11T18:19:56Z (after
the deploy): `MB10_HOST_POST_PASS`, every verifier and preservation code `0`, `readinessExact: true`, no temporary
residue. `host/03-POST/HOST_RESULT.json` (WSL work directory `/root/lilith-mb10-seq1`) SHA-256
`914e885ef47af10b2464a549d9af3b1973566343019b2943451c01b2784ca401`. The pre-POST manifest of the local evidence
directory: `3b8ac0a82ef5672a7f227d060ba1269be3de2f863c298b1c35c57694270fa624`.

## 4. What did not happen

No HELD mutation (HELD stays `1ee1b7d5….json` / `c713ea1d2e0b016e59eb55ddc1a125561495ed4cc0a2c24764f36c8355d0216d`,
bound to `ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4`), no witness or broker restart, no signer
action, no Registry effectiveness, no authority activation. No material drift, UNKNOWN, STOP or REVALIDATE was
recorded.

## 5. Evidence location

Owner-local only: `C:\Users\edufo\lilith-mb10-postfreeze-5e83bd1` (the deploy log, the comparison and its stderr, the
pre-POST manifest) and `/root/lilith-mb10-seq1/host/03-POST` in WSL. Nothing here is copied into the repository.

```text
FIRST_POST_FREEZE_DEPLOY = OCCURRED (38162573937, 5e83bd187e7f44feae7acae13adcd6370625a195)
POST_FREEZE_DR5_W10_1 = EQUAL
HOST_POST = MB10_HOST_POST_PASS
HELD = PRESENT / EXACT / FORWARD ONLY (unchanged)
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
SIGNER = INACTIVE
M-B11 = NOT AUTHORIZED
FIRST_MEMORY_READY = NOT REACHED
PROD = NOT AUTHORIZED
```
