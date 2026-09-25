# Slice 15B2b-B1c — Routine DEV Deployer Authority Acceptance Record

**Status:** COMPLETE / ACCEPTED. **Evidence date:** 2026-09-25 UTC.
**Scope:** a historical acceptance record for the routine DEV deployment
authority boundary. It is not an activation instruction, not a Stage-III
authorization, and not a claim of live canonical memory. Design and owner
runbook: [slice15b2b-b1c-dev-deployer-authority.md](slice15b2b-b1c-dev-deployer-authority.md).

## Three distinct states

| State | Acceptance finding |
| --- | --- |
| **SOURCE ACCEPTED** | PR [#62](https://github.com/rpahasara/lilith-os/pull/62), "15B2b-B1c: Complete constrained DEV deployment proof", merged at `a86110cd55e6255ae45d2b697bb7ce940932442b` on top of PR [#61](https://github.com/rpahasara/lilith-os/pull/61) (`b9aae0f693825b64fc203a4c85ec51cd47e58f19`). |
| **DEV PROVEN** | [Run 36179649106](https://github.com/rpahasara/lilith-os/actions/runs/36179649106) of "Deploy LILITH Core API to DEV" deployed exactly `a86110cd55e6255ae45d2b697bb7ce940932442b` end to end under the constrained identity and passed every in-run authority proof. The owner's cloud and DEV gates then passed. |
| **PROD UNTOUCHED** | No B1c change touched `services/core-api/**`, so PROD `deploy.yml` did not run. PROD runtime was not accessed. The legacy PROD identity's project-wide authority remains open debt (below). |

## What B1c means

Before B1c, the routine GitHub deployer held project-wide
`roles/compute.osAdminLogin`: `google-sudoers` and `(ALL) NOPASSWD: ALL` on
DEV and PROD. Any workflow on `refs/heads/main` could federate to it. The DEV
workflow ran uploaded code with `sudo bash` and `sudo python3` and logged into
PROD. The DEV API user `lilith` could rewrite its canonical activation
configuration.

B1c is accepted because routine DEV deployment no longer depends on broad
administrator authority. One real deployment proved the complete path:

identity → constrained federation → real OS Login principal → exact sudo
authority → fixed root-owned deploy helper → exact-SHA deployment → health
verification → federation denial proof.

Activation authority, broker authority, owner authority, Stage-III authority
and PROD authority remain outside routine DEV deployment. Owner break-glass
(the owner's local gcloud/IAP session) remains present and separate from
GitHub automation.

The accepted invariants are unchanged and now structurally enforced where B1c
reaches:

- model proposal ≠ authority;
- execution ≠ verification;
- memory ≠ truth;
- **deployment ≠ activation**.

Model, application, or runtime behavior is not authority evidence.
Replaceable DEV code may imitate canonical behavior, but canonical activation
is ACCEPTED only through the owner-installed, isolated verifier
`/usr/local/sbin/lilith-activation-verify` over an owner-signed grant. The
application identity cannot mint that grant. No signer and no grant are
installed; every observation below is `ACTIVATION=NOT_ACCEPTED`.

## Source and merge

Protected main after acceptance is `a86110cd55e6255ae45d2b697bb7ce940932442b`.
PR #61 carried the authority cut: DEV-only identity, fixed helper, sudo rule,
activation verifier and root-owned activation, broker validation on the
runner, and PROD removed from routine DEV. PR #62 completed the proof on real
infrastructure. It preserved these commits:

| Commit | Change |
| --- | --- |
| `963b141` | Fix DEV deploy helper cwd and EXIT-trap state (15B2b-B1c) |
| `5216381` | Keep sandbox variables and stubs across env -i in helper test harness |
| `fbf37e0` | Judge post-deploy federation and PROD denial by HTTP status (15B2b-B1c) |
| `bfdcc10` | Consume piped request body in federation proof curl stub |

## Final real DEV deployment

Run 36179649106 (`workflow_run`, attempt 1, head
`a86110cd55e6255ae45d2b697bb7ce940932442b`) concluded **success**. In one
execution it proved the following.

**OIDC claims** (recorded before authentication):

- `repository` = `rpahasara/lilith-os`
- `ref` = `refs/heads/main`
- `event_name` = `workflow_run`
- `workflow_ref` = `rpahasara/lilith-os/.github/workflows/deploy-dev.yml@refs/heads/main`
- `job_workflow_ref` = `rpahasara/lilith-os/.github/workflows/deploy-dev.yml@refs/heads/main`

**Real OS Login principal:** `sa_112096412008414111981`
(`uid=3826947836`, no supplementary groups).

**Effective sudo, before any deploy action:**
`SUDO_EFFECTIVE_PROOF=PASS user=sa_112096412008414111981 mode=self`.

**Denials:** the routine deployer was denied (28 `DENIED`, zero
`ALLOWED(unexpected)`):

- generic sudo/root;
- `sudo bash` and `sudo python3`;
- broker restart and `sudo -u lilith`;
- writes to protected broker paths, systemd units and sudoers;
- reads of broker state, configuration and identity data;
- Stage-III authorization data and Stage-III guard/state;
- `owner.sock`;
- `/home/lilith`;
- writes to the activation authority paths, the activation verifier and the
  deploy helper.

**Activation during deployment:**
`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`.

**Deployment:** the fixed helper completed its sequence and printed
`--- DEV DEPLOYMENT COMPLETE ---`:

1. bounded stdin payload;
2. unpack, verification, tests and install as `lilith`;
3. atomic switch;
4. durability probe prepare;
5. restart of `lilith-os-api-dev.service` only;
6. probe verify in the new process.

The durability probe reported `CLEANUP_COMPLETE`, health returned
`status=ok`, and the readback showed
`candidateSha=a86110cd55e6255ae45d2b697bb7ce940932442b`.

## Federation boundary

The post-deploy proof judged each HTTP status explicitly. Expected denials
count as evidence; grants, unexpected statuses, malformed bodies and
transport errors fail.

| Check | Result |
| --- | --- |
| `DEV_IDENTITY_MINT` | PASS, HTTP 200, token issued (never printed) |
| `LEGACY_PRIVILEGED_MINT` | PASS, HTTP 403, `PERMISSION_DENIED` / `IAM_PERMISSION_DENIED` |
| `PROD_COMPUTE` (`lilith-01` osLogin/osAdminLogin/setMetadata) | PASS, HTTP 403, permission denied (`forbidden`) |
| `PROD_IAP` (`lilith-01` tunnel) | PASS, HTTP 200, `granted=[]` |
| `PROD_SA` (`lilith-vm` actAs/getAccessToken) | PASS, HTTP 200, `granted=[]` |

`FEDERATION_BOUNDARY=PASS`. The routine DEV identity can obtain its own
intended identity. Through the tested paths, it cannot obtain the legacy
privileged identity or useful PROD permissions.

## Live helper and authority boundary

- `/usr/local/sbin/lilith-dev-deploy` is `root:root 0755`, SHA-256
  `85b260a29f29c182d7da867c25a1e9406fc713591e217eaa927031696e8755b8`
  (identical to the source at `a86110c`).
- The deployer has exactly the rendered sudo rule for the fixed helper:
  `deploy <sha>` and `status`. It has no general root.
- The activation verifier and activation authority stay root-controlled. The
  authority directory `/etc/lilith-os-dev/activation` contains no signer and
  no grant.
- `lilith` cannot modify the deploy helper, its library, the activation
  verifier, `/etc/lilith-os-dev`, `/etc/lilith-os-dev/activation`,
  `canonical-runtime.json` (`root:lilith 0640`), or sudoers.

## Final owner gates

The gates are owner-run and read-only. They are kept outside the repository.

**Cloud gate** `b1c_premerge_gate_cloud.sh`, SHA-256
`893aa79b7719dd6fa7e86967f947a4eaf8551711767f049cd16657d2eb064a9c`:
`CLOUD_GATE=PASS`.

- **New DEV deployer:**
  `github-lilith-dev-deployer@lilith-agent-260823-27389.iam.gserviceaccount.com`,
  uniqueId `112096412008414111981`.
- **Project-level authority:** exactly one custom role,
  `projects/lilith-agent-260823-27389/roles/lilithDevComputeProjectsGet`,
  containing exactly `compute.projects.get`. This is the documented
  contingency, because instance-scoped roles cannot grant project reads.
- **DEV VM `lilith-dev-01`:** instance-level `roles/compute.osLogin` only; no
  `osAdminLogin`.
- **DEV IAP:** tunnel access only.
- **DEV service account:** actAs on `lilith-dev-vm` only.
- **PROD:** no new-deployer binding on the `lilith-01` instance, on the PROD
  IAP tunnel, or on `lilith-vm`.
- **New-deployer federation:** only
  `rpahasara/lilith-os/.github/workflows/deploy-dev.yml@refs/heads/main`.
- **Legacy privileged identity federation:** only
  `rpahasara/lilith-os/.github/workflows/deploy.yml@refs/heads/main`.
- **Provider condition:** unchanged; `attribute.workflow_ref` is mapped.
- **Owner break-glass:** present and separate.

**DEV gate** `b1c_premerge_gate_dev.sh`, SHA-256
`8a7c3b2a43946a66cf19f50dba701f005d4e62a0e422146338fb0874c5459ce7`:
`DEV_GATE=PASS`.

- Effective sudo: `SUDO_EFFECTIVE_PROOF=PASS user=sa_112096412008414111981 mode=owner`.
- Activation, owner-invoked: `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`.
- Activation, `lilith`-invoked: `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`.

## Broker and Stage-III preservation

The broker's accepted selector remains
`817a83e44cec8965479fd97fc30b7a0b3ae49ab2`. The broker and socket are active,
`owner.sock` is listening, and the selector is unchanged.

Stage III was **not** retried, armed or altered by B1c:

- no A2 arm and no A2 guard;
- the controller remains failed;
- the phase journal remains `INTENT` only;
- the authorization is preserved and not consumed;
- the final-attempt record is unchanged.

## Known residual debt — not a B1c failure

**`CROSS_ENVIRONMENT_PROD_AUTHORITY_DEBT` remains OPEN.** The legacy PROD
deployer `github-lilith-deployer@lilith-agent-260823-27389.iam.gserviceaccount.com`
still holds project-level:

- `roles/compute.osAdminLogin`
- `roles/compute.viewer`
- `roles/iap.tunnelResourceAccessor`

It also keeps actAs on both VM service accounts. Its federation is narrowed to
`deploy.yml` on main, so routine DEV automation cannot obtain it. However, the
PROD workflow's identity could still reach DEV as root. This debt is known,
recorded, and deliberately outside B1c acceptance: scoping it would change PROD
login authority, which cannot be verified without a PROD run. Because of it,
this record does **not** claim complete Level 2 root isolation of DEV. B1c
satisfies the B1a requirement that routine deployer root be replaced; it does
not retire every root-capable identity.

## What B1c does not establish

- No canonical activation. No signer and no grant exist.
- No real canonical memory, owner-control interface or production canonical
  capability.
- No Stage-III result. A2 remains deferred and unproven.
- No change to PROD runtime or its darkness.
- No resolution of the cross-environment PROD authority debt.
- The broker-validation workflows (`memory-broker-dev-*`) lost GitHub
  federation by design. Broker install, recovery and forensics are owner
  break-glass.

## Recovery

- **Helper or DEV release failure:** the helper rolls back the release link
  on any failure after the switch, and restarts only if it had already
  restarted. Owner break-glass can reinstall a reviewed helper by its exact
  hash.
- **IAM/WIF:** every B1c cutover change has a specific, separately recorded
  rollback in the design record's runbook.
- **Activation:** never activate a capability, grant or signer as a recovery
  shortcut. Activation is a separate owner ceremony.

## Next boundary

The planning records name what follows, but do not authorize it:

- **B1d.** B1a's threat model says the deployer "remains root-capable until
  B1b/B1c/B1d". B1d is not otherwise specified in the repository.
- **Slice 15B2b-B — Owner Memory Control.** Named by the
  [15B2b-A acceptance record](slice-15b2b-a-acceptance-record.md) as the next
  boundary, to remain inactive with no real value.
- **Slice 15B2b-C.** May later consider an explicitly owner-chosen First
  Memory, only after those gates pass.
- **Stage III A2** remains deferred and requires its own explicit
  justification.

None of these is started by this record.
