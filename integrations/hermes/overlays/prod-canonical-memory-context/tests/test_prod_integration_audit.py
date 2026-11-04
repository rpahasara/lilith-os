"""OFFLINE: the prepared PROD integration audit (`prod_integration_audit_ro.sh`) is read-only and content-free.

Record: docs/architecture/canonical-memory-prod-integration-plan.md §6. Nothing here contacts PROD: the checks are
static, plus a bash syntax check when bash is available.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "prod_integration_audit_ro.sh"
ROOT = HERE.parents[4]
PLAN = ROOT / "docs/architecture/canonical-memory-prod-integration-plan.md"


def code_lines() -> list[str]:
    return [line for line in SCRIPT.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")]


class AuditScriptTests(unittest.TestCase):
    def test_refuses_any_host_but_prod_before_reading_anything(self):
        lines = [l for l in code_lines() if l.strip()]
        guard = next(i for i, l in enumerate(lines) if "hostname -s" in l)
        first_read = next(i for i, l in enumerate(lines) if l.startswith("a ") or "sha256sum" in l and "()" not in l)
        self.assertLess(guard, first_read)
        self.assertIn("= lilith-01 ]", lines[guard])
        self.assertIn("exit 2", lines[guard])

    def test_no_write_restart_or_mutation_command(self):
        text = "\n".join(code_lines())
        forbidden = (r"\brm\b", r"\bmv\b", r"\bcp\b", r"\btee\b", r"\bdd\b", r"\binstall\b", r"\bchmod\b", r"\bchown\b",
                     r"\btouch\b", r"\bmkdir\b", r"\bln\b", r"\bsed -i", r"systemctl (start|stop|restart|reload|enable|"
                     r"disable|daemon-reload|kill|mask)", r"\bkill\b", r"\bgit (checkout|reset|pull|commit|stash)",
                     r"\bpip\b", r"\bapt", r"\bcurl\b", r"\bwget\b", r"\bgcloud\b", r"(?<![0-9&|])>(?!&)(?!\s*/dev/null)\s*[/$\w]")
        for pattern in forbidden:
            self.assertIsNone(re.search(pattern, text), pattern)

    def test_sqlite_is_opened_read_only_and_never_written(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('mode=%s" % (path, mode)', text)
        self.assertIn('"ro&immutable=1" if walsize == 0 else "ro"', text)
        for verb in ("insert ", "update ", "delete ", "drop ", "alter ", "vacuum", "create ", "replace "):
            self.assertNotIn(verb, text.lower().replace("coalesce(sql", ""), verb)

    def test_content_free_no_secret_message_or_memory_text_is_printed(self):
        text = "\n".join(code_lines())
        self.assertNotRegex(text, r"\bcat\b")                       # no file content at all
        self.assertNotRegex(text, r"\b(head|tail|less|more|strings|xxd|od)\b(?! -1)")
        self.assertNotIn("select * ", text.lower())
        self.assertNotRegex(text, r"select (content|text|message|value|body)")
        # the two secret files are touched by stat only; the machine id is printed only as a SHA-256
        for line in code_lines():
            if ".key" in line or "actor_authority" in line:
                self.assertRegex(line, r"stat -c|for k in")
        self.assertIn("sha256sum < /etc/machine-id", text)
        self.assertNotRegex(text, r"(?<!< )/etc/machine-id(?!\s*\|)")
        self.assertIn("grep -cE", text)                             # the Telegram allowlist: a count only

    def test_ends_with_the_done_marker(self):
        self.assertEqual(code_lines()[-1].strip(), "echo PROD_INTEGRATION_AUDIT_DONE")

    def test_bash_syntax(self):
        bash = shutil.which("bash")
        if bash is None or subprocess.run([bash, "-c", "true"], capture_output=True).returncode != 0:
            self.skipTest("no working bash")
        result = subprocess.run([bash, "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class PlanRecordTests(unittest.TestCase):
    def test_the_plan_names_the_pins_it_depends_on(self):
        plan = PLAN.read_text(encoding="utf-8")
        for value in ("88a1168bd41797109772ffce7df7352c1ae40e4c", "072001af671feca6564906d3d685f89bfc608f9d595aed58bae0f72a25777684",
                      "53ae457b8b907e12282ed468da0387620b7a376a46ab1c450709b67540b43c07",
                      "4db8bb58da3fbdef80fb550c74709bb3ea62c605afadec56aa96b28d2568ca8b",
                      "99fe90649e316ef992db7c05575c19eafe56e703d505f44f39c5577903fe9587"):
            self.assertIn(value, plan)

    def test_the_audit_is_prepared_not_run(self):
        self.assertIn("PREPARED, NOT RUN", SCRIPT.read_text(encoding="utf-8").splitlines()[1])


if __name__ == "__main__":
    unittest.main()
