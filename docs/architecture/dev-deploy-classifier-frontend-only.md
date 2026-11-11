# DEV deployment classifier: frontend-only lane

Status: **Proposed** (2026-11-11). Control change to `scripts/classify_dev_deployment.py`; it needs owner review and authorization before merge.

## Problem

`.github/workflows/deploy-dev.yml` ("Deploy LILITH Core API to DEV") runs after every successful *Repository validation* on `main`. It classifies the complete effective diff with the candidate's own `scripts/classify_dev_deployment.py`. Before this change, only an exact list of control/broker paths, and brand-new preserved Hermes files, classified as `CONTROL_ONLY_NO_DEPLOY`. Every other path, including every Next.js frontend file, was `DEPLOY_REQUIRED`.

As a result, a frontend-only merge caused a same-code redeploy and restart of the DEV Core API (`lilith-os-api-dev.service`). Measured on Experience V2 RC1 (#426): `MODE=DEPLOY_REQUIRED` for 38 frontend, test and docs paths.

## What the DEV deployment actually consumes (audit)

| Surface | Contents | Frontend files? |
|---|---|---|
| Core API bundle (`scripts/build_core_api_bundle.py`) | `services/core-api/app.py`, `requirements.txt`, `tests/test_goal_executive.py`, `tests/test_canonical_runtime.py`, `services/core-api/lilith_memory/*.py` | **No.** `_sources()` resolves every member under `services/core-api/`. `services/core-api/tests/test_deployment_bundle.py` already asserts frontend `public/assets` are excluded. |
| DEV deploy workflow steps | classifier, bundle builder, `validate_repository.py`, broker controls and tests, the fixed root-owned DEV helper over IAP, health and federation proofs | **No.** No step references `src/`, `package.json`, `npm`, Node or `.next`. |
| PROD deploy workflow (`deploy.yml`, manual) | its own fixed helpers | **No** frontend references. |
| CI (`ci.yml`) | `npm ci`, `npm audit`, `npm run build`, `npm run test:core` | Yes. CI is where the frontend is validated, and it runs **before** `deploy-dev.yml` can start (`workflow_run` on success). |
| DEV host | Core API bundle, DEV helper, broker and authority services | The frontend is not installed on DEV. The owner runs it locally behind the IAP tunnel. |
| Backend code referencing frontend paths | `services/core-api/app.py` has comments naming `src/lib/world/*.ts` (wire-shape mirrors). Other hits are unrelated temp `package.json` names in owner-control tooling. | Nothing reads frontend files. |

**Server-side frontend code.** The Next.js route handlers under `src/app/api/**`, plus the modules they import (`src/lib/core-api-credentials.ts`, `src/lib/conversation/owner-capture-auth.ts`), run on the Next server with the Core API service tokens and the owner-capture gate. They are not deployed to DEV either, but they are the web app's privileged boundary, so they are deliberately **excluded** from this lane and keep the full path. The same applies to any `route.*`, `middleware.ts`, `proxy.ts` or `instrumentation*.ts` entry point, and to anything at the `src/` root.

**Client command core.** `src/lib/command/core/**` is browser code. It holds no credential and cannot grant approval. Approval-gated writes are enforced server-side by the Core API (Slice 4 fingerprint freeze, Slice 5 policy engine) behind the proxy's write token.

## Rule (`is_frontend_only`)

A diff entry qualifies only when **all** of the following hold:

- **File type and mode:** it is a regular, non-executable file (`100644`), either added (`000000 → 100644`) or modified with no mode change (`100644 → 100644`). Deletions, mode changes, the executable bit, symlinks and submodules take full deployment. This is in addition to the classifier's existing global checks.
- **Path:** one of the following:
  - an exact frontend tooling path: `package.json`, `package-lock.json`, `scripts/run-core-self-test.mjs`, `scripts/self-test-next-server-shim.mjs`, `scripts/scan-prod-bundle.mjs`, `scripts/test-stubs/next-link.tsx`, `scripts/test-stubs/next-navigation.ts`; or
  - a `.ts`, `.tsx` or `.css` file under `src/app/`, `src/components/`, `src/hooks/` or `src/lib/`, **except**:
    - any `api` directory segment under `src/app/`;
    - the route, middleware, proxy and instrumentation entry points;
    - the two server-only modules listed above;
    - dot-files; or
  - a Markdown file **directly** in `docs/roadmap/`.

The outcome is the existing `CONTROL_ONLY_NO_DEPLOY` mode. That keeps the workflow's existing control-only validation and the **read-only** routine-deployer boundary proof (`DEV_MUTATION=NONE`) unchanged.

The existing combination rules are unchanged:
- **Mixed with deploy-required paths:** any non-qualifying path in the same diff makes the whole diff `DEPLOY_REQUIRED`, for example a frontend file plus `services/core-api/**`, workflows, deploy scripts, unknown files or broker runtime.
- **Mixed with broker paths:** a frontend file plus a broker-candidate path is a lane mismatch, which gives `DEPLOY_REQUIRED`.
- **Fail-closed parsing:** empty, malformed, renamed and noncanonical diffs still fail closed.

**Not included (add later only with their own review):** `public/**` (avatar and static assets), root build config (`next.config.ts`, `tsconfig.json`, `postcss.config.mjs`), `src/app/favicon.ico`, other `docs/**`, and any other `scripts/**`.

## Evidence

- `scripts/test_classify_dev_deployment.py` (run by CI) covers:
  - qualifying frontend diffs;
  - the full RC1 path list;
  - negative and adversarial cases: server routes, credential and auth modules, entry points, sibling prefixes, wrong extensions, dot-files, nested roadmap files, mode, symlink, submodule and deletion tricks, mixed Core API, workflow, broker and unknown paths;
  - a real-merge classification;
  - a structural guard that every `@/` module transitively imported by a server route is excluded from the lane;
  - a guard that no deployment workflow references the frontend.
- **RC1 (#426):** the complete effective diff (38 entries) classifies as `CONTROL_ONLY_NO_DEPLOY` with this classifier.
- **Core API changes:** a change to `services/core-api/app.py` or `lilith_memory/*.py`, alone or mixed with frontend files, still classifies as `DEPLOY_REQUIRED`.
