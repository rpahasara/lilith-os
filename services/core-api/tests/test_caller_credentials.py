# -*- coding: utf-8 -*-
"""Every Command Center proxy must carry the Core API credential before enforcement, and none may reach the browser. TEST_ONLY; reads source only."""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
API = REPO / "src" / "app" / "api" / "lilith"
HELPER = REPO / "src" / "lib" / "core-api-credentials.ts"
WRITES = {"drafts/route.ts", "drafts/[draftId]/route.ts", "tasks/route.ts", "tasks/[taskId]/route.ts"}
READS = {"conversation/route.ts", "conversation/evidence/route.ts", "[...path]/route.ts"}


class Proxies(unittest.TestCase):
    def test_every_route_that_calls_the_core_api_is_listed(self):
        found = {p.relative_to(API).as_posix() for p in API.rglob("route.ts") if "fetch(" in p.read_text(encoding="utf-8")}
        self.assertEqual(found, WRITES | READS)

    def test_each_upstream_call_sends_the_credential(self):
        for name in WRITES | READS:
            source = (API / name).read_text(encoding="utf-8")
            self.assertIn('from "@/lib/core-api-credentials"', source, name)
            self.assertIn("...coreApiHeaders(", source, name)

    def test_write_routes_ask_for_the_write_credential(self):
        for name in WRITES:
            source = (API / name).read_text(encoding="utf-8")
            if re.search(r'method: "(POST|PATCH|DELETE|PUT)"|method:', source):
                self.assertIn("coreApiHeaders(true)", source, name)

    def test_no_token_is_public(self):
        source = HELPER.read_text(encoding="utf-8")
        self.assertNotIn("process.env.NEXT_PUBLIC", source)
        for path in (REPO / "src").rglob("*.ts*"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"NEXT_PUBLIC_[A-Z_]*TOKEN", path.name)

    def test_the_helper_is_imported_only_by_server_routes(self):
        for path in (REPO / "src").rglob("*.ts*"):
            if path == HELPER:
                continue
            if "core-api-credentials" in path.read_text(encoding="utf-8"):
                self.assertTrue(path.is_relative_to(API) and path.name == "route.ts", path)

    def test_the_header_names_match_the_core_api(self):
        app = (REPO / "services" / "core-api" / "app.py").read_text(encoding="utf-8").lower()
        helper = HELPER.read_text(encoding="utf-8")
        self.assertIn('headers.get("x-lilith-os-read")', app)
        self.assertIn("x_lilith_os_write: str = _header(default=none)", app)   # FastAPI maps this to the header below
        self.assertIn("x-lilith-os-read", helper)
        self.assertIn("x-lilith-os-write", helper)


if __name__ == "__main__":
    unittest.main()
