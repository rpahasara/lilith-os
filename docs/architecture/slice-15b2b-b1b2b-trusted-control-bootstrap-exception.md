# B1b-2b trusted-control bootstrap exception

Status: owner-approved, one-time governance transition for PR #30 only. This
record does not authorize Stage-II runtime activation.

## Cause

The accepted Stage-I installation changed DEV from `PRE_B1B2B` to
`POST_STAGE_I`. The then-trusted required DEV validator still required broker
provisioning to be absent. It therefore could not certify the PR that repairs
that validator and introduces trusted control-only classification. The failed
check is a circular trusted-control dependency, not permission for candidate
code to certify its own lifecycle.

## Rejected alternatives

- Destroy or uninstall the accepted Stage-I state to satisfy the legacy gate.
- Let candidate code select a lifecycle profile, expected identity, or hash.
- Report a false successful required check.
- Permanently weaken the ruleset or remove a required context.
- Grant a broad actor, deployment account, or application bypass.

## Bounded transition

PR #30 carries both trusted repairs. Its final reviewed SHA is frozen before
any bypass. The named owner may temporarily receive a pull-request-only
ruleset bypass solely to merge that exact PR and SHA. The bypass is not
natively bound to a PR or SHA; the operator must verify both immediately
before merging, permit no other merge or direct push during the window, then
remove the actor immediately and verify the original ruleset is restored.

Only after restoration may PR #29 be synchronized. Its closed allowlist must
classify it `CONTROL_ONLY_NO_DEPLOY`, all four ordinary required checks must
pass, and the DEV check must report `DEV_MUTATION=NONE`. PR #29 then uses the
normal protected merge path with no bypass.

The PR #30 review and merge record must carry the exact SHA, failed legacy
check, bypass enable/removal times, actor, ruleset before/after, and merge
commit. The PR #29 record must carry its ordinary four-check result and merge
commit. No Stage-II marker, socket, service, probe, assertion, live owner
authority, real credential, or real canonical memory is authorized here.
