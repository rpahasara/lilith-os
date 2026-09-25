# 15B2b-B1c: routine DEV deployer authority separation

Status: source complete; live cutover pending owner action.
Base: protected main `8c13fdf74abe14eea4226f8bf387e549886db2b2`.

## Invariant

Routine DEV deployment may replace ordinary DEV Core API code and restart
`lilith-os-api-dev.service`. Neither the deployment identity nor code it may
replace can obtain root; reach Memory Broker authority, state, identities,
units, owner socket or owner-control/synthetic-evidence state; reach Stage III
authorization or state; activate canonical LTM; or obtain PROD authority. An
owner-held break-glass path remains.

## B1c-0 finding (before)

`github-lilith-deployer` held project-wide `roles/compute.osAdminLogin`, so its
POSIX user was in `google-sudoers` with `(ALL) NOPASSWD: ALL` on DEV and PROD.
Its federation admitted any workflow of this repository on `refs/heads/main`.
The routine DEV workflow ran `sudo bash` and `sudo python3` on uploaded code and
logged into PROD `lilith-01` to execute a base64 audit. The DEV API (`lilith`)
could rewrite `canonical-runtime.json`, contradicting deployment != activation.

## Authority cut

Cloud identity:

- New `github-lilith-dev-deployer` (POSIX `sa_112096412008414111981`).
- `roles/compute.osLogin` (non-admin) on instance `lilith-dev-01` only.
- `roles/iap.tunnelResourceAccessor` on the `lilith-dev-01` IAP tunnel resource only.
- `roles/iam.serviceAccountUser` on `lilith-dev-vm` only.
- No project-level binding, no PROD instance/SA binding, no token-creator or
  IAM-mutation role.
- Federated only for the exact claim
  `workflow_ref = rpahasara/lilith-os/.github/workflows/deploy-dev.yml@refs/heads/main`
  (new `attribute.workflow_ref` mapping on the existing provider; the provider
  condition still requires this repository and `refs/heads/main`).
- The legacy privileged identity's federation is narrowed from
  `attribute.repository/rpahasara/lilith-os` to
  `attribute.workflow_ref/.../deploy.yml@refs/heads/main` (PROD workflow only).
  `workflow_ref` names the top-level workflow, so `deploy-dev.yml` cannot reach
  it even by calling another workflow.

Root on DEV: the deployer's only sudo rule is the fixed root-owned helper
`/usr/local/sbin/lilith-dev-deploy` with exactly `deploy <40-hex>` or `status`.
The bundle arrives on stdin; the helper accepts no path, command, interpreter,
unit, or environment. Root only buffers stdin (64 MiB cap), drops to `lilith`,
and restarts `lilith-os-api-dev.service`. Bundle bytes are unpacked, verified,
tested, installed and switched as `lilith`. The verifier and durability probe
are pinned root-owned copies in `/usr/local/lib/lilith-dev-deploy`, not uploads.
Bootstrap (users, packages, unit files) is owner break-glass only.

Activation: `/etc/lilith-os-dev/canonical-runtime.json`, `root:lilith 0640`,
parent `root:root 0755`. `lilith` can read it but cannot write, unlink, rename
or replace it. The service reads it only through `LILITH_CANONICAL_CONFIG_FILE`
in the root-owned unit. The installer only carries forward a dark config, never
enables canonical LTM, and deletes the old lilith-owned file. The durability
probe fails any deploy whose activation file or parent is replaceable.

PROD: the routine DEV workflow no longer logs into PROD. Each deploy asserts,
via `testIamPermissions` only, that the DEV identity has no PROD login, IAP or
service-account permission. PROD darkness remains worth proving, but only as a
future, separately governed read-only identity.

Broker validation: candidate broker tests run on the hosted runner before any
cloud authentication. Accepted-DEV broker snapshot equality needs root and is
now owner break-glass evidence only; `broker_preflight` is removed and the
required `LILITH DEV deployment` status for broker-only changes reflects the
credential-free candidate validation.

Consequence: `memory-broker-dev-first-install`, `-stage2-runtime`,
`-stage3-a2-final` and `-stage3-a2-forensics` lose GitHub federation once the
legacy binding is narrowed. Broker install, recovery and forensics use the
owner's local gcloud/IAP session (break-glass). Stage III remains deferred.

## Evidence built into every routine deploy

- Positive: helper deploy, restart, health, candidate SHA readback, durability
  probe across restart.
- Negative (as the real deployer, on DEV): `sudo -n true`, `sudo bash`,
  `sudo python3`, broker restart and `sudo -u lilith` are denied; no write to
  broker code/config/state/units, sudoers, activation or the helper; no read of
  broker identities/config/state, Stage III authorization/state, `owner.sock`
  or `/home/lilith`.
- Federation: the same OIDC token mints the DEV identity (200) and is refused
  the legacy privileged identity (403).

## Owner cutover runbook (break-glass, local gcloud)

Ordered so the owner is never locked out: new authority first, legacy last.

```bash
P=lilith-agent-260823-27389; Z=asia-southeast1-b; PN=763184673487
NEW=github-lilith-dev-deployer@$P.iam.gserviceaccount.com
OLD=github-lilith-deployer@$P.iam.gserviceaccount.com
POOL=projects/$PN/locations/global/workloadIdentityPools/github-actions
```

1. DEV-scoped grants for the new identity:

```bash
gcloud compute instances add-iam-policy-binding lilith-dev-01 --zone=$Z --project=$P --member=serviceAccount:$NEW --role=roles/compute.osLogin
gcloud iam service-accounts add-iam-policy-binding lilith-dev-vm@$P.iam.gserviceaccount.com --project=$P --member=serviceAccount:$NEW --role=roles/iam.serviceAccountUser
curl -sS -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" -H 'Content-Type: application/json' -d "{\"policy\":{\"bindings\":[{\"role\":\"roles/iap.tunnelResourceAccessor\",\"members\":[\"serviceAccount:$NEW\"]}],\"etag\":\"ACAB\"}}" "https://iap.googleapis.com/v1/projects/$PN/iap_tunnel/zones/$Z/instances/lilith-dev-01:setIamPolicy"
```

2. Exact-workflow federation for the new identity:

```bash
gcloud iam workload-identity-pools providers update-oidc github --workload-identity-pool=github-actions --location=global --project=$P --attribute-mapping=google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.workflow_ref=assertion.workflow_ref
gcloud iam service-accounts add-iam-policy-binding $NEW --project=$P --role=roles/iam.workloadIdentityUser --member="principalSet://iam.googleapis.com/$POOL/attribute.workflow_ref/rpahasara/lilith-os/.github/workflows/deploy-dev.yml@refs/heads/main"
```

3. Install the DEV boundary from the reviewed commit (repository root):

```bash
gcloud compute ssh lilith-dev-01 --zone=$Z --project=$P --tunnel-through-iap --command='umask 077; mkdir /tmp/b1c'
gcloud compute scp --zone=$Z --project=$P --tunnel-through-iap scripts/dev_deployer/lilith-dev-deploy scripts/dev_deployer/sudoers-lilith-dev-deployer.in scripts/dev_deployer/install_dev_deployer_boundary.sh scripts/verify_core_api_bundle.py scripts/run_core_api_dev_durability_probe.py lilith-dev-01:/tmp/b1c/
gcloud compute ssh lilith-dev-01 --zone=$Z --project=$P --tunnel-through-iap --command='sudo bash /tmp/b1c/install_dev_deployer_boundary.sh sa_112096412008414111981 /tmp/b1c; rm -rf /tmp/b1c'
```

4. Narrow the legacy privileged identity to the PROD workflow:

```bash
gcloud iam service-accounts add-iam-policy-binding $OLD --project=$P --role=roles/iam.workloadIdentityUser --member="principalSet://iam.googleapis.com/$POOL/attribute.workflow_ref/rpahasara/lilith-os/.github/workflows/deploy.yml@refs/heads/main"
gcloud iam service-accounts remove-iam-policy-binding $OLD --project=$P --role=roles/iam.workloadIdentityUser --member="principalSet://iam.googleapis.com/$POOL/attribute.repository/rpahasara/lilith-os"
```

5. Merge the B1c PR. The merge is `DEPLOY_REQUIRED` (new paths outside the
   control-only list) and touches nothing under `services/core-api/**`, so PROD
   `deploy.yml` does not run. The first routine run is the positive and negative
   proof.

Contingency: if `gcloud compute ssh` in the first run fails for lack of
`compute.projects.get` (instance-scoped roles do not grant project reads), add a
project-level custom role containing only `compute.projects.get` for the new
identity. Grant nothing broader.

Not in B1c (owner decision): the legacy identity still holds project-wide
`osAdminLogin`, so the PROD workflow could reach DEV. Scoping it to `lilith-01`
would change PROD login authority that cannot be verified without a PROD run.
