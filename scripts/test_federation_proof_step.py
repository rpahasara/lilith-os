"""15B2b-B1c: the post-deploy federation/PROD denial proof judges HTTP status.

Extracts the exact workflow step script and runs it with stub curl/gcloud.
Expected denials (403) are evidence; grants, unexpected statuses, malformed
bodies and transport failures fail. Tokens are never printed.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/deploy-dev.yml").read_text(encoding="utf-8")
STEP_NAME = "      - name: Prove routine DEV federation cannot obtain PROD or the legacy privileged identity\n"
SECRETS = ("minted-secret-token", "federated-secret-token", "gcloud-secret-token", "oidc-secret-signature")


def step_script() -> str:
    step = WORKFLOW.split(STEP_NAME, 1)[1]
    step = step.split("\n      - name:", 1)[0]
    body = step.split("        run: |\n", 1)[1]
    return textwrap.dedent(body)


CURL_STUB = r'''#!/bin/bash
out=""; url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift ;;
    -d) [ "$2" = "@-" ] && cat > /dev/null; shift ;;  # like curl, consume a piped body
    -w|-H|-X) shift ;;
    http*) url="$1" ;;
  esac
  shift
done
emit() {  # emit <scenario> <kind>
  local s="$1" kind="$2" body code
  if [ "$s" = TRANSPORT ]; then printf 000; exit 7; fi
  code="${s%%:*}"
  case "$s" in
    *:SERVICE_DISABLED) body='{"error":{"code":403,"status":"PERMISSION_DENIED","details":[{"reason":"SERVICE_DISABLED"}]}}' ;;
    *:MALFORMED) body='<html>oops' ;;
    *:GRANTED) body='{"permissions":["compute.instances.osLogin"]}' ;;
    *)
      case "$code:$kind" in
        200:mint) body='{"accessToken":"minted-secret-token","expireTime":"2026-09-26T00:00:00Z"}' ;;
        200:prod) body='{}' ;;
        403:compute) body='{"error":{"code":403,"message":"Required permission","errors":[{"reason":"forbidden"}]}}' ;;
        403:*) body='{"error":{"code":403,"status":"PERMISSION_DENIED","details":[{"reason":"IAM_PERMISSION_DENIED"}]}}' ;;
        *) body="{\"error\":{\"code\":${code}}}" ;;
      esac ;;
  esac
  if [ -n "$out" ]; then printf '%s' "$body" > "$out"; printf '%s' "$code"; else printf '%s' "$body"; fi
}
case "$url" in
  http://oidc.test/*) printf '{"value":"%s"}' "$STUB_JWT" ;;
  https://sts.googleapis.com/*) printf '{"access_token":"federated-secret-token"}' ;;
  *iamcredentials*github-lilith-dev-deployer@*) emit "$STUB_DEV" mint ;;
  *iamcredentials*github-lilith-deployer@*) emit "$STUB_LEGACY" mint ;;
  https://compute.googleapis.com/*) emit "$STUB_COMPUTE" compute ;;
  https://iap.googleapis.com/*) emit "$STUB_IAP" prod ;;
  https://iam.googleapis.com/*) emit "$STUB_SA" prod ;;
  *) echo "unexpected url $url" >&2; exit 99 ;;
esac
'''


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("jq") and shutil.which("bash"),
                     "needs Linux bash and jq")
class FederationProofStepTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "bin").mkdir()
        (base / "bin/curl").write_text(CURL_STUB)
        (base / "bin/gcloud").write_text("#!/bin/bash\necho gcloud-secret-token\n")
        for name in ("curl", "gcloud"):
            (base / "bin" / name).chmod(0o755)
        (base / "step.sh").write_text(step_script())
        self.base = base
        claims = {"repository": "rpahasara/lilith-os", "ref": "refs/heads/main", "event_name": "workflow_run",
                  "workflow_ref": "rpahasara/lilith-os/.github/workflows/deploy-dev.yml@refs/heads/main"}
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        self.jwt = f"eyJhbGciOiJSUzI1NiJ9.{payload}.oidc-secret-signature"

    def tearDown(self):
        self.tmp.cleanup()

    def run_step(self, **scenario):
        values = {"DEV": "200", "LEGACY": "403", "COMPUTE": "403", "IAP": "403", "SA": "403"}
        values.update(scenario)
        env = {
            "PATH": f"{self.base}/bin:/usr/bin:/bin",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-token",
            "ACTIONS_ID_TOKEN_REQUEST_URL": "http://oidc.test/token?v=1",
            "GCP_WIF_PROVIDER": "projects/763184673487/locations/global/workloadIdentityPools/github-actions/providers/github",
            "GCP_DEPLOY_SA": "github-lilith-dev-deployer@lilith-agent-260823-27389.iam.gserviceaccount.com",
            "GCP_LEGACY_PRIVILEGED_SA": "github-lilith-deployer@lilith-agent-260823-27389.iam.gserviceaccount.com",
            "GCP_PROJECT_ID": "lilith-agent-260823-27389",
            "GCP_ZONE": "asia-southeast1-b",
            "GITHUB_STEP_SUMMARY": str(self.base / "summary"),
            "STUB_JWT": self.jwt,
            **{f"STUB_{k}": v for k, v in values.items()},
        }
        result = subprocess.run(["bash", str(self.base / "step.sh")], capture_output=True, text=True,
                                env=env, timeout=60)
        output = result.stdout + result.stderr
        # ::add-mask:: lines register values with the runner's masker; nothing
        # else may carry a token.
        visible = "\n".join(line for line in output.splitlines() if not line.startswith("::add-mask::"))
        for secret in SECRETS:
            self.assertNotIn(secret, visible)
        return result.returncode, output

    def assertPass(self, rc, out):
        self.assertEqual(rc, 0, out)
        self.assertIn("FEDERATION_BOUNDARY=PASS", out)
        self.assertIn("PROD_AUTHORITY=NONE", (self.base / "summary").read_text())

    def assertFail(self, rc, out, *markers):
        self.assertNotEqual(rc, 0, out)
        self.assertIn("FEDERATION_BOUNDARY=FAIL", out)
        self.assertFalse((self.base / "summary").exists() and "PROD_AUTHORITY=NONE" in (self.base / "summary").read_text())
        for marker in markers:
            self.assertIn(marker, out)

    def test_dev_200_legacy_403_prod_403_passes(self):
        rc, out = self.run_step()
        self.assertPass(rc, out)
        self.assertIn("PASS DEV_IDENTITY_MINT kind=mint-allowed http=200 token-issued", out)
        self.assertIn("PASS LEGACY_PRIVILEGED_MINT kind=mint-denied http=403 permission-denied", out)
        self.assertIn("PASS PROD_COMPUTE kind=prod-denied http=403 permission-denied", out)
        self.assertIn('"workflow_ref": "rpahasara/lilith-os/.github/workflows/deploy-dev.yml@refs/heads/main"', out)

    def test_prod_200_with_no_granted_permission_passes(self):
        self.assertPass(*self.run_step(COMPUTE="200", IAP="200", SA="200"))

    def test_legacy_200_fails_loudly(self):
        rc, out = self.run_step(LEGACY="200")
        self.assertFail(rc, out, "FAIL LEGACY_PRIVILEGED_MINT kind=mint-denied http=200 expected-403 LEGACY-IDENTITY-OBTAINED")
        self.assertIn("PROD_SA", out)  # every check still runs and reports

    def test_legacy_unexpected_statuses_fail(self):
        for code in ("401", "404", "429", "500", "503"):
            with self.subTest(code=code):
                self.assertFail(*self.run_step(LEGACY=code), f"FAIL LEGACY_PRIVILEGED_MINT kind=mint-denied http={code}")

    def test_legacy_transport_failure_fails(self):
        self.assertFail(*self.run_step(LEGACY="TRANSPORT"), "FAIL LEGACY_PRIVILEGED_MINT kind=mint-denied http=TRANSPORT transport-failure")

    def test_legacy_non_authorization_403_fails(self):
        self.assertFail(*self.run_step(LEGACY="403:SERVICE_DISABLED"), "non-authorization-403=SERVICE_DISABLED")

    def test_dev_non_200_fails(self):
        for code in ("403", "401", "500", "TRANSPORT"):
            with self.subTest(code=code):
                self.assertFail(*self.run_step(DEV=code), "FAIL DEV_IDENTITY_MINT kind=mint-allowed")

    def test_prod_grant_fails(self):
        self.assertFail(*self.run_step(COMPUTE="200:GRANTED"), 'FAIL PROD_COMPUTE kind=prod-denied http=200 granted=["compute.instances.osLogin"]')

    def test_prod_unexpected_status_malformed_or_transport_fails(self):
        for label, value in (("PROD_IAP", "404"), ("PROD_SA", "500"), ("PROD_COMPUTE", "403:MALFORMED"),
                             ("PROD_IAP", "TRANSPORT"), ("PROD_SA", "403:SERVICE_DISABLED")):
            with self.subTest(label=label, value=value):
                key = {"PROD_COMPUTE": "COMPUTE", "PROD_IAP": "IAP", "PROD_SA": "SA"}[label]
                self.assertFail(*self.run_step(**{key: value}), f"FAIL {label} kind=prod-denied")


class FederationProofStaticTests(unittest.TestCase):
    def test_denial_calls_never_use_curl_fail_flag(self):
        script = step_script()
        denial = script.split("call() {", 1)[1]
        self.assertNotIn("curl -sSf", denial)
        self.assertNotIn("curl -f", denial)
        self.assertIn("code=TRANSPORT", script)
        self.assertIn("-w '%{http_code}'", script)

    def test_all_five_checks_are_wired(self):
        script = step_script()
        for line in ("verdict DEV_IDENTITY_MINT mint-allowed", "verdict LEGACY_PRIVILEGED_MINT mint-denied",
                     "verdict PROD_COMPUTE prod-denied", "verdict PROD_IAP prod-denied", "verdict PROD_SA prod-denied"):
            self.assertIn(line, script)
        self.assertIn("serviceAccounts/${GCP_LEGACY_PRIVILEGED_SA}:generateAccessToken", script)
        self.assertIn("instances/lilith-01/testIamPermissions", script)
        self.assertIn("instances/lilith-01:testIamPermissions", script)
        self.assertIn("serviceAccounts/lilith-vm@${GCP_PROJECT_ID}.iam.gserviceaccount.com:testIamPermissions", script)


if __name__ == "__main__":
    unittest.main()
