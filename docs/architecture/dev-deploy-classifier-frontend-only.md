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

**Server-boundary guard.** The classifier stays path-based. `server_boundary_violations` in `scripts/test_classify_dev_deployment.py` runs in CI on every PR, before `deploy-dev.yml` can run. It fails if the lane would admit either of the following:

- **Code that runs on the Next server**, plus everything it loads. Server code means:
  - route, middleware, proxy and instrumentation entry points;
  - files with a file-level or inline `"use server"` directive (server actions);
  - files importing `server-only`, `next/headers` or `next/cache`.

  "Everything it loads" follows static imports, `export … from` re-exports, side-effect imports, literal dynamic `import()` and `require()`, through both `@/` and relative paths.
- **Code that touches privileged material**, plus every module that imports it, transitively. Privileged code means:
  - the listed server modules;
  - any reader of a non-public `process.env` secret, meaning anything other than `NEXT_PUBLIC_*` or `NODE_ENV`;
  - the entry points above.

  This catches a server component, a page or a test that loads credentials or routes.

Non-literal dynamic imports and unresolvable relative imports in server code also fail the guard. A new server helper, server action or secret reader therefore fails CI until its path is listed explicitly in `FRONTEND_SERVER_PATHS`.

The guard's first run found one real case: `src/lib/conversation/self-test.ts` loads the conversation server routes to test the owner-capture gate. It is now listed, so it keeps the full path.

## Rule (`is_frontend_only`)

A diff entry qualifies only when **all** of the following hold:

- **File type and mode:** it is a regular, non-executable file (`100644`), either added (`000000 → 100644`) or modified with no mode change (`100644 → 100644`). Deletions, mode changes, the executable bit, symlinks and submodules take full deployment. This is in addition to the classifier's existing global checks.
- **Path:** one of the following:
  - an exact frontend tooling path: `package.json`, `package-lock.json`, `scripts/run-core-self-test.mjs`, `scripts/self-test-next-server-shim.mjs`, `scripts/scan-prod-bundle.mjs`, `scripts/test-stubs/next-link.tsx`, `scripts/test-stubs/next-navigation.ts`; or
  - a `.ts`, `.tsx` or `.css` file under `src/app/`, `src/components/`, `src/hooks/` or `src/lib/`, **except**:
    - any `api` directory segment under `src/app/`;
    - the route, middleware, proxy and instrumentation entry points;
    - the listed server modules (`core-api-credentials.ts`, `owner-capture-auth.ts`, `conversation/self-test.ts`);
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
  - the server-boundary guard on the real repository (no violations), plus 15 synthetic gap cases, each of which it must catch:
    - relative imports;
    - `export *` and named re-exports;
    - side-effect imports;
    - literal dynamic `import()` and `require()`;
    - middleware outside `src/app`;
    - a server component importing credentials;
    - a transitive importer of credentials;
    - a test importing a route;
    - file-level and inline `"use server"`;
    - `server-only` and `next/headers`;
    - a secret-env reader and its importer.

    It also has negative controls (client code, `NEXT_PUBLIC_*`, `NODE_ENV`, packages) and checks that non-literal and unresolved imports fail;
  - a guard that no deployment workflow references the frontend.
- **RC1 (#426):** the complete effective diff (38 entries) classifies as `CONTROL_ONLY_NO_DEPLOY` with this classifier.
- **Core API changes:** a change to `services/core-api/app.py` or `lilith_memory/*.py`, alone or mixed with frontend files, still classifies as `DEPLOY_REQUIRED`.
