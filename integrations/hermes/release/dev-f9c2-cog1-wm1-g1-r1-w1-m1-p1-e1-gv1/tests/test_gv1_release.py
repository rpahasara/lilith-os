"""Offline acceptance contract for f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1 (the e1 release with the empty-goal-store rule
replaced by what it protects). TEST_ONLY; throwaway DBs and temp dirs; nothing leaves the process.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1/tests -p "test_*.py"

Portable tests cover the goal-store rule and every runtime-check outcome (helpers patched). FullHostTest and
RealProcessTest need Linux as root (run them in a disposable WSL/VM): they build an e1-shaped host and a real process.
"""
from __future__ import annotations

import contextlib
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import yaml

GV1 = Path(__file__).resolve().parents[1]
REPO = GV1.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
E1 = REL / "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1"
F9C2 = REL / "dev-f9c2"
COG1 = REL / "dev-f9c2-cog1"
O = REPO / "integrations" / "hermes" / "overlays"
APP_PY = REPO / "services" / "core-api" / "app.py"
sys.path.insert(0, str(COG1 / "tests"))

import test_cog1_release as C  # noqa: E402  (load_verifier, run_verifier, assemble_dev_cognition, constants)

GV1_TEMPLATE = GV1 / "templates" / "bin" / "verify_release.py.tmpl"
E1_TEMPLATE = E1 / "templates" / "bin" / "verify_release.py.tmpl"
E1_ROUTER = E1 / "home" / "router.yaml"
INSTALLER = GV1 / "bin" / "install_gv1.sh"
DELTA = json.loads((GV1 / "RELEASE-DELTA.json").read_text(encoding="utf-8"))
LINUX_ROOT = sys.platform.startswith("linux") and hasattr(os, "geteuid") and os.geteuid() == 0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def kinds(codes) -> set[str]:
    return {c.split(" ", 1)[0] for c in codes}


def make_store(path: Path, goals=(), traces=(), module=None, drop=None) -> Path:
    """A goal store with the Core API's exact columns. goals: lifecycle states; traces: kinds."""
    schema = (module or V).GOAL_SCHEMA
    con = sqlite3.connect(path)
    for table, cols in schema.items():
        if table == drop:
            continue
        con.execute(f'CREATE TABLE "{table}" ({", ".join(cols)})')
    for i, state in enumerate(goals):
        con.execute('INSERT INTO goal (goal_id, type, title, source, owner, lifecycle_state, priority, created_at, updated_at) '
                    'VALUES (?,?,?,?,?,?,?,?,?)', (f"g.test-only-{i}", "commitment.once", "TEST_ONLY never read",
                                                   "SCHEDULED", "user", state, "NORMAL", "a", "a"))
    for i, kind in enumerate(traces):
        con.execute("INSERT INTO goal_trace (correlation_id, goal_id, at, kind, source) VALUES (?,?,?,?,?)",
                    (f"c{i}", "g.test-only-0", "a", kind, "SCHEDULED"))
    con.commit()
    con.close()
    return path


DEV_GOALS = ("COMPLETED", "COMPLETED", "FAILED", "FAILED", "CANCELLED", "CANCELLED")   # the six 2026-11-09 TEST_ONLY goals
DEV_TRACES = ("transition",) * 20

_TMP = Path(tempfile.mkdtemp(prefix="gv1-mod-"))
V = C.load_verifier(GV1_TEMPLATE, _TMP)
VE1 = C.load_verifier(E1_TEMPLATE, _TMP)


class ReleaseDefinitionTest(unittest.TestCase):
    def test_identity_base_and_members(self):
        self.assertEqual((GV1 / "RELEASE_ID").read_bytes(), b"f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1\n")
        self.assertEqual(DELTA["release"], "f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1")
        self.assertEqual(DELTA["base_release"], (E1 / "RELEASE_ID").read_text().strip())
        self.assertEqual(set(DELTA["members"]), {"RELEASE_ID", "bin/verify_release.py"})
        self.assertEqual(DELTA["members"]["RELEASE_ID"]["sha256"], sha(GV1 / "RELEASE_ID"))
        self.assertEqual(DELTA["members"]["RELEASE_ID"]["from"], sha(E1 / "RELEASE_ID"))
        v = DELTA["members"]["bin/verify_release.py"]
        self.assertEqual((v["template_sha256"], v["base_template_sha256"]), (sha(GV1_TEMPLATE), sha(E1_TEMPLATE)))
        self.assertEqual(v["base_template_sha256"], "f1086cacc440d84850b30b033b23120e41f34919d2761ddb2e867761eb3b65d5")
        self.assertEqual(DELTA["unchanged"]["home/router.yaml"], sha(E1_ROUTER))

    def test_installer_pins_exactly_the_reviewed_bytes(self):
        text = INSTALLER.read_text(encoding="utf-8")
        pins = dict(re.findall(r"\[([A-Za-z0-9_.]+)\]=([0-9a-f]{64})", text))
        self.assertEqual(pins, {"verify_release.gv1.py.tmpl": sha(GV1_TEMPLATE), "verify_release.e1.py.tmpl": sha(E1_TEMPLATE),
                                "router.e1.yaml": sha(E1_ROUTER), "RELEASE_ID": sha(GV1 / "RELEASE_ID")})
        self.assertIn("OLD_ID=" + (E1 / "RELEASE_ID").read_text().strip(), text)
        self.assertIn("NEW_ID=" + (GV1 / "RELEASE_ID").read_text().strip(), text)
        for gone in ("put_router", "put_code", "rm -rf", "systemctl start", "systemctl restart", "DELETE", "UPDATE "):
            self.assertNotIn(gone, text, gone)                      # no home change, no deletion, no start

    def test_verifier_change_is_confined_to_the_goal_rule(self):
        a = E1_TEMPLATE.read_text(encoding="utf-8").splitlines()
        b = GV1_TEMPLATE.read_text(encoding="utf-8").splitlines()
        removed = [l[1:] for l in difflib.unified_diff(a, b, lineterm="", n=0) if l.startswith("-") and not l.startswith("---")]
        code = [l.strip() for l in removed if l.strip() and not l.strip().startswith("#")]
        self.assertEqual(code, ['def check_cognition_schema() -> None:',
                                '"""The goal and drafts tables exist with exactly their columns, and the goal store is empty. Read-only (mode=ro)."""',
                                'return fail("GOAL_DB_MISSING")',
                                "if conn.execute('SELECT COUNT(*) FROM \"goal\"').fetchone()[0] != 0:",
                                'fail("GOAL_STORE_NOT_EMPTY")',
                                'check_cognition_schema()'])
        self.assertEqual("\n".join(b).count(C.PLACEHOLDER), "\n".join(a).count(C.PLACEHOLDER))
        for name in ("LANES_OFF", "SHADOW_LANES", "ROUTER_KEYS", "GOAL_SCHEMA", "REQUIRED_DENY", "GATE_CONFIG",
                     "WORLD_CONTEXT_ADAPTER_SHA256", "ETHICS_SHA256", "PLANNING_SHA256", "MOTIVATION_SHA256",
                     "WORKSPACE_SHA256", "ETHICS_PRINCIPLES_SHA256", "PROD_WORKING_MEMORY_SHA256"):
            self.assertEqual(getattr(V, name), getattr(VE1, name), name)

    def test_the_deployed_core_api_passes_the_guard_and_main_still_has_it(self):
        self.assertEqual(sha(APP_PY), "44200ce9cf16392fdca8d847f950b2af7c355799a7cc01389bd3d816f064b6cc")   # DEV, 2026-11-10
        self.assertEqual(V.focus_guard_problems(APP_PY.read_text(encoding="utf-8")), [])

    def test_no_credential_material(self):
        for p in GV1.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                text = p.read_text(encoding="utf-8")
                for marker in ("gsk" + "_", "PRIVATE" + " KEY", "BEGIN" + " OPENSSH", "Bearer" + " "):
                    self.assertNotIn(marker, text, p.name)


class GoalStoreRuleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gv1-db-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_rule(self, module=V, **store):
        db = store.pop("path", None) or make_store(self.tmp / f"d{len(list(self.tmp.iterdir()))}.db", module=module, **store)
        module.GOAL_DB = db
        module.failures = []
        ok = module.check_cognition_schema()
        return ok, list(module.failures)

    def test_empty_store(self):
        self.assertEqual(self.run_rule(), (True, []))

    def test_terminal_only_goals_pass_and_e1_refused_them(self):
        self.assertEqual(self.run_rule(goals=DEV_GOALS, traces=DEV_TRACES), (True, []))
        _, e1 = self.run_rule(VE1, goals=DEV_GOALS, traces=DEV_TRACES)
        self.assertEqual(e1, ["GOAL_STORE_NOT_EMPTY"])                          # exactly DEV's refusal today

    def test_active_and_pending_goals_refuse(self):
        self.assertEqual(self.run_rule(goals=("ACTIVE",)), (False, ["GOAL_FOCUS_CANDIDATE ACTIVE 1"]))
        self.assertEqual(self.run_rule(goals=("PENDING", "PENDING") + DEV_GOALS), (False, ["GOAL_FOCUS_CANDIDATE PENDING 2"]))

    def test_unknown_and_non_terminal_states_refuse_conservatively(self):
        for state, label in (("BLOCKED", "BLOCKED"), ("SUSPENDED", "SUSPENDED"), (None, "NULL"), ("", "<non-identifier>"),
                             ("completed", "completed"), ("DONE; DROP TABLE goal", "<non-identifier>"),
                             ("TEST_ONLY secret free text", "<non-identifier>")):
            with self.subTest(state=state):
                self.assertEqual(self.run_rule(goals=(state, "COMPLETED")), (False, [f"GOAL_STATE_NOT_TERMINAL {label} 1"]))

    def test_existing_arbitration_traces_refuse(self):
        self.assertEqual(self.run_rule(goals=DEV_GOALS, traces=DEV_TRACES + ("arbitration",)),
                         (False, ["GOAL_ARBITRATION_TRACE_PRESENT 1"]))
        self.assertEqual(self.run_rule(traces=("arbitration", "arbitration")), (False, ["GOAL_ARBITRATION_TRACE_PRESENT 2"]))

    def test_unknown_trace_kinds_refuse(self):
        self.assertEqual(self.run_rule(traces=("transition", "focus_read")), (False, ["GOAL_TRACE_KIND_UNKNOWN focus_read 1"]))

    def test_schema_and_db_failures_still_refuse(self):
        self.assertEqual(self.run_rule(drop="drafts"), (False, ["COGNITION_SCHEMA_NOT_BOOTSTRAPPED drafts"]))
        self.assertEqual(self.run_rule(path=self.tmp / "missing.db"), (False, ["GOAL_DB_MISSING"]))
        (self.tmp / "junk.db").write_bytes(b"not a database" * 100)
        self.assertEqual(self.run_rule(path=self.tmp / "junk.db"), (False, ["GOAL_DB_UNREADABLE"]))
        con = sqlite3.connect(self.tmp / "bad.db")
        con.execute("CREATE TABLE goal (goal_id)"); con.execute("CREATE TABLE goal_trace (id)"); con.execute("CREATE TABLE drafts (draft_id)")
        con.commit(); con.close()
        ok, codes = self.run_rule(path=self.tmp / "bad.db")
        self.assertFalse(ok)
        self.assertEqual(kinds(codes), {"COGNITION_SCHEMA_MISMATCH"})

    def test_the_rule_never_writes(self):
        db = make_store(self.tmp / "ro.db", goals=DEV_GOALS + ("ACTIVE",), traces=DEV_TRACES + ("arbitration",))
        before = sha(db)
        self.run_rule(path=db)
        self.assertEqual(sha(db), before)


class FakeRuntime:
    """Stands in for systemctl, /proc and the Core API so every runtime outcome is reachable offline."""

    def __init__(self, tmp: Path, db: Path, app_source: str | None = None):
        self.root = tmp / "lilith-os-dev"
        self.rel = self.root / "releases" / ("e" * 40)
        self.rel.mkdir(parents=True)
        (self.rel / "app.py").write_text(app_source if app_source is not None else APP_PY.read_text(encoding="utf-8"),
                                         encoding="utf-8")
        self.db = db
        self.show = {"ActiveState": "active", "MainPID": "4242",
                     "Environment": 'HOME=/home/lilith LILITH_DB_PATH=%s LILITH_OS_FOCUS_READ_ONLY=1 "X=a b"' % db}
        self.env = {"LILITH_OS_FOCUS_READ_ONLY": "1", "LILITH_DB_PATH": str(db), "LILITH_OS_TRUST_LOOPBACK": "1"}
        self.argv = [str(self.root / "api-venv/bin/python"), str(self.root / "api-venv/bin/uvicorn"), "app:app",
                     "--host", "0.0.0.0", "--port", "8765"]
        self.cwd = self.rel
        self.started = time.time() + 5
        self.http = lambda: (200, json.dumps({"focus": None, "candidates": [], "arbitration": {"winner": None}}).encode())
        self.calls = 0
        self.proc_error = None
        self.shows = None

    def patch(self, module):
        def proc(pid, name):
            if self.proc_error:
                raise self.proc_error
            if name == "environ":
                return b"\0".join(f"{k}={v}".encode() for k, v in self.env.items()) + b"\0"
            if name == "cmdline":
                return b"\0".join(a.encode() for a in self.argv) + b"\0"
            raise OSError(name)

        def http(url, timeout):
            self.calls += 1
            return self.http()

        def unit_show():
            return self.shows.pop(0) if self.shows else self.show

        stack = contextlib.ExitStack()
        for name, value in (("_unit_show", unit_show), ("_proc", proc), ("_proc_link", lambda pid, n: self.cwd),
                            ("_proc_start_epoch", lambda pid: self.started), ("_http_get", http),
                            ("CORE_API_ROOT", self.root), ("CORE_API_WAIT_S", 0.3), ("GOAL_DB", self.db)):
            stack.enter_context(mock.patch.object(module, name, value))
        stack.enter_context(mock.patch.object(module.time, "sleep", lambda s: None))
        return stack


class RuntimeCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gv1-rt-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = make_store(self.tmp / "lilith-dev.db", goals=DEV_GOALS, traces=DEV_TRACES)
        self.rt = FakeRuntime(self.tmp, self.db)

    def codes(self):
        V.failures = []
        with self.rt.patch(V):
            V.check_focus_read_only()
        return list(V.failures)

    def test_intended_dev_configuration_passes_with_one_focus_read_and_no_write(self):
        before = sha(self.db)
        self.assertEqual(self.codes(), [])
        self.assertEqual(self.rt.calls, 1)
        self.assertEqual(sha(self.db), before)

    def test_core_api_not_running_or_unknown_refuses(self):
        for show in ({"ActiveState": "failed", "MainPID": "0"}, {"ActiveState": "active", "MainPID": "0"},
                     {"ActiveState": "activating", "MainPID": "4242"}, {}):
            with self.subTest(show=show):
                self.rt.show = show
                self.assertEqual(kinds(self.codes()), {"CORE_API_NOT_RUNNING"})
                self.assertEqual(self.rt.calls, 0)

    def test_waits_for_a_core_api_that_is_still_starting(self):
        good = dict(self.rt.show)
        self.rt.shows = [{"ActiveState": "activating", "MainPID": "0"}, {"ActiveState": "inactive", "MainPID": "0"}, good]
        self.assertEqual(self.codes(), [])

    def test_flag_missing_or_disabled_refuses_before_any_focus_read(self):
        for value in (None, "0", "", "true", "1 "):
            with self.subTest(value=value):
                self.rt.env = {k: v for k, v in self.rt.env.items() if k != V.FOCUS_FLAG}
                if value is not None:
                    self.rt.env[V.FOCUS_FLAG] = value
                self.rt.calls = 0
                self.assertIn("FOCUS_READ_ONLY_NOT_IN_EFFECT", self.codes())
                self.assertEqual(self.rt.calls, 0)

    def test_flag_only_in_the_running_process_is_not_enough(self):
        self.rt.show = dict(self.rt.show, Environment="HOME=/home/lilith")
        self.assertEqual(self.codes(), ["FOCUS_READ_ONLY_NOT_PERSISTENT"])
        self.assertEqual(self.rt.calls, 0)

    def test_core_api_reading_another_db_refuses(self):
        self.rt.env["LILITH_DB_PATH"] = str(self.tmp / "other.db")
        self.assertEqual(self.codes(), ["CORE_API_DB_MISMATCH"])

    def test_wrong_process_identity_refuses(self):
        for change in ({"argv": ["/usr/bin/python3", "-m", "http.server"]},
                       {"argv": ["/x/python", "/tmp/uvicorn", "app:app"]},
                       {"cwd": self.tmp}):
            with self.subTest(change=change):
                rt = FakeRuntime(Path(tempfile.mkdtemp(dir=self.tmp)), self.db)
                for k, v in change.items():
                    setattr(rt, k, v)
                self.rt = rt
                self.assertEqual(self.codes(), ["CORE_API_IDENTITY"])

    def test_code_that_ignores_the_flag_refuses(self):
        src = APP_PY.read_text(encoding="utf-8")
        guard = 'if _os.getenv("LILITH_OS_FOCUS_READ_ONLY") != "1":'
        self.assertEqual(src.count(guard), 1)
        cases = {
            "unguarded": (src.replace(guard, "if True:"), "FOCUS_GUARD_MISSING"),
            "other-flag": (src.replace(guard, 'if _os.getenv("LILITH_OS_FOCUS_READ_ONLY_X") != "1":'), "FOCUS_GUARD_MISSING"),
            "inverted": (src.replace(guard, 'if _os.getenv("LILITH_OS_FOCUS_READ_ONLY") == "1":'), "FOCUS_GUARD_MISSING"),
            "called-elsewhere": (src + "\n\ndef other_read():\n    _record_focus_trace(None, None)\n", "FOCUS_TRACE_CALLED_ELSEWHERE"),
            "other-writer": (src + '\n\ndef sneaky(conn):\n    _goal_trace_insert(conn, "c", None, "arbitration", "x")\n',
                             "ARBITRATION_WRITER_UNEXPECTED"),
            "no-focus-route": (src.replace("def goal_focus(", "def goal_focus_v2("), "FOCUS_GUARD_NOT_FOUND"),
            "unparseable": (src + "\ndef (:\n", "FOCUS_GUARD_UNPARSEABLE"),
        }
        for name, (code_src, want) in cases.items():
            with self.subTest(case=name):
                self.rt = FakeRuntime(Path(tempfile.mkdtemp(dir=self.tmp)), self.db, code_src)
                self.assertIn(want, self.codes())
                self.assertEqual(self.rt.calls, 0)

    def test_code_replaced_after_the_process_started_refuses(self):
        self.rt.started = time.time() - 3600
        self.assertEqual(self.codes(), ["CORE_API_CODE_CHANGED_SINCE_START"])

    def test_missing_code_or_unreadable_runtime_refuses(self):
        (self.rt.rel / "app.py").unlink()
        self.assertEqual(self.codes(), ["CORE_API_CODE_UNREADABLE"])
        self.rt.proc_error = PermissionError("environ")
        self.assertEqual(self.codes(), ["CORE_API_RUNTIME_UNREADABLE"])

    def test_unreachable_core_api_refuses(self):
        def refuse():
            raise urllib.error.URLError("refused")
        self.rt.http = refuse
        self.assertEqual(self.codes(), ["CORE_API_UNREACHABLE"])

    def test_unexpected_answers_refuse(self):
        for answer, want in (((401, b""), "CORE_API_FOCUS_STATUS 401"), ((500, b""), "CORE_API_FOCUS_STATUS 500"),
                             ((200, b"<html>"), "CORE_API_FOCUS_UNPARSEABLE"),
                             ((200, b'{"focus": {"goalId": "g"}, "arbitration": {"winner": "g"}}'), "FOCUS_HAS_WINNER")):
            with self.subTest(answer=answer):
                self.rt.http = lambda a=answer: a
                self.assertEqual(self.codes(), [want])

    def test_a_focus_read_that_writes_is_caught(self):
        def writing_read():
            con = sqlite3.connect(self.db)
            con.execute("INSERT INTO goal_trace (correlation_id, at, kind) VALUES ('g_arb_x', 'a', 'arbitration')")
            con.commit(); con.close()
            return 200, b'{"focus": null, "arbitration": {"winner": null}}'
        self.rt.http = writing_read
        self.assertEqual(self.codes(), ["FOCUS_READ_WROTE_TRACE"])

    def test_store_refusal_skips_the_focus_read(self):
        called = []
        V.GOAL_DB = make_store(self.tmp / "cand.db", goals=("ACTIVE",))
        V.failures = []
        with mock.patch.object(V, "check_focus_read_only", lambda: called.append(1)):
            if V.check_cognition_schema():
                V.check_focus_read_only()
        self.assertEqual((V.failures, called), (["GOAL_FOCUS_CANDIDATE ACTIVE 1"], []))


@unittest.skipUnless(LINUX_ROOT, "needs Linux as root (disposable WSL/VM)")
class FullHostTest(unittest.TestCase):
    """The whole verifier on an e1-shaped host: gv1 passes outright where e1 refuses only GOAL_STORE_NOT_EMPTY (DEV's
    state), and release-integrity and restart failures still refuse."""

    def setUp(self):
        os.umask(0o022)
        self.tmp = Path(tempfile.mkdtemp(prefix="gv1-host-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        r = self.root = self.tmp / "h"
        home = r / "home"
        assert C.assemble_dev_cognition.assemble(home) == []
        (home / "router.yaml").unlink()
        lr = home / "lilith_router"
        shutil.copy(E1_ROUTER, lr / "router.yaml")
        for src, name in ((O / "dev-ethics-hardening/lilith_router/world_context.py", "world_context.py"),
                          (O / "dev-ethics-hardening/lilith_router/ethics.py", "ethics.py"),
                          (REPO / "docs/architecture/slice-13/ethics_principles.py", "ethics_principles.py"),
                          (O / "dev-planning-hardening/lilith_router/planning.py", "planning.py"),
                          (O / "dev-workspace-private-trace/lilith_router/workspace.py", "workspace.py"),
                          (O / "dev-motivation-private-trace/lilith_router/motivation.py", "motivation.py")):
            shutil.copy(src, lr / name)
        config = (F9C2 / "templates" / "home" / "config.yaml.tmpl").read_text(encoding="utf-8")
        (home / "config.yaml").write_text(config.replace(C.PLACEHOLDER, C.TEST_TOKEN), encoding="utf-8")
        os.chmod(home / "config.yaml", 0o640)
        (home / ".env").write_text("LILITH_OS_PORT=9901\nLILITH_OS_TOKEN=" + "ab" * 32 + "\n", encoding="utf-8")
        os.chmod(home / ".env", 0o640)
        for d in C.RO_STUBS:
            (home / d).mkdir()
        (home / "cron").mkdir()
        (home / "cron" / "jobs.json").write_text('{"jobs": []}\n', encoding="utf-8")
        self.release = r / "opt" / "releases" / "f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1"
        (self.release / "bin").mkdir(parents=True)
        (self.release / "bin" / "verify_release.py").write_text("# TEST_ONLY rendered verifier stand-in\n", encoding="utf-8")
        (self.release / "RELEASE.sha256").write_text(
            f"{sha(self.release / 'bin' / 'verify_release.py')}  bin/verify_release.py\n", encoding="utf-8")
        os.symlink("releases/" + self.release.name, r / "opt" / "current")
        (r / "etc-gateway").mkdir()
        self.critical = r / "etc-gateway" / "critical.sha256"
        pinned = [home / "config.yaml", lr / "router.yaml", lr / "world_context.py"]
        self.critical.write_text("".join(f"{sha(p)}  {str(p).lstrip('/')}\n" for p in pinned), encoding="utf-8")
        (r / "etc-gate" / "credentials").mkdir(parents=True)
        os.chmod(r / "etc-gate" / "credentials", 0o700)
        gate = (F9C2 / "templates" / "gate" / "gate.json.tmpl").read_text(encoding="utf-8")
        (r / "etc-gate" / "gate.json").write_text(gate.replace(C.PLACEHOLDER, C.TEST_TOKEN), encoding="utf-8")
        for p in [r, *r.rglob("*")]:                     # as installed: nothing group/other writable
            if not p.is_symlink():
                os.chmod(p, p.stat().st_mode & ~0o022)
        self.db = make_store(self.tmp / "lilith-dev.db", goals=DEV_GOALS, traces=DEV_TRACES)
        self.rt = FakeRuntime(self.tmp, self.db)

    def run_main(self, module, full=False):
        module.BASE, module.HH = self.root / "opt", self.root / "home"
        module.ETC, module.GATE_ETC = self.root / "etc-gateway", self.root / "etc-gate"
        module.GOAL_DB = self.db
        module.failures = []
        out = io.StringIO()
        with self.rt.patch(module) if module is V else contextlib.nullcontext(), contextlib.redirect_stdout(out):
            rc = module.main(["--full"] if full else ["--pre-start"])
        return rc, out.getvalue().strip().splitlines()

    def test_gv1_passes_the_dev_shaped_host_and_e1_refuses_only_the_goal_rule(self):
        self.assertEqual(self.run_main(V, full=True), (0, [f"F8_VERIFY_PASS full {self.release.name}"]))
        self.assertEqual(self.run_main(VE1, full=True), (1, ["F8_VERIFY_FAIL GOAL_STORE_NOT_EMPTY"]))

    def test_release_integrity_failures_still_refuse(self):
        (self.release / "bin" / "verify_release.py").write_text("# TEST_ONLY tampered\n", encoding="utf-8")
        rc, out = self.run_main(V, full=True)
        self.assertEqual(rc, 1)
        self.assertTrue(any(l.startswith("F8_VERIFY_FAIL HASH_MISMATCH") and "verify_release.py" in l for l in out), out)

    def test_restart_verification_refuses_a_changed_pinned_file(self):
        router = self.root / "home" / "lilith_router" / "router.yaml"
        router.write_text(router.read_text(encoding="utf-8") + "\n# TEST_ONLY\n", encoding="utf-8")
        rc, out = self.run_main(V)
        self.assertEqual(rc, 1)
        self.assertTrue(any("HASH_MISMATCH" in l and "router.yaml" in l for l in out), out)

    def test_restart_with_the_core_api_down_refuses(self):
        self.rt.show = {"ActiveState": "inactive", "MainPID": "0"}
        self.assertEqual(self.run_main(V), (1, ["F8_VERIFY_FAIL CORE_API_NOT_RUNNING inactive"]))

    def test_restart_after_a_goal_became_active_refuses(self):
        con = sqlite3.connect(self.db)
        con.execute("UPDATE goal SET lifecycle_state='ACTIVE' WHERE goal_id='g.test-only-0'")
        con.commit(); con.close()
        self.assertEqual(self.run_main(V), (1, ["F8_VERIFY_FAIL GOAL_FOCUS_CANDIDATE ACTIVE 1"]))
        self.assertEqual(self.rt.calls, 0)

    def test_current_must_still_be_a_release(self):
        os.unlink(self.root / "opt" / "current")
        os.symlink(str(self.tmp), self.root / "opt" / "current")
        rc, out = self.run_main(V)
        self.assertEqual(rc, 1)
        self.assertIn("CURRENT_NOT_A_RELEASE", kinds(l.removeprefix("F8_VERIFY_FAIL ") for l in out))


FAKE_API = r'''
import json, os, sqlite3, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
DB = os.environ["LILITH_DB_PATH"]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        c = sqlite3.connect(DB)
        cands = c.execute("SELECT goal_id FROM goal WHERE lifecycle_state IN ('ACTIVE','PENDING') ORDER BY goal_id").fetchall()
        winner = cands[0][0] if cands else None
        last = c.execute("SELECT arbitration_winner FROM goal_trace WHERE kind='arbitration' ORDER BY id DESC LIMIT 1").fetchone()
        if os.environ.get("LILITH_OS_FOCUS_READ_ONLY") != "1" and winner != (last[0] if last else None):
            c.execute("INSERT INTO goal_trace (correlation_id, at, kind, arbitration_winner) VALUES ('g_arb','a','arbitration',?)", (winner,))
            c.commit()
        c.close()
        body = json.dumps({"focus": None if winner is None else {"goalId": winner}, "arbitration": {"winner": winner}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
srv = HTTPServer(("127.0.0.1", 0), H)
print(srv.server_address[1], flush=True)
srv.serve_forever()
'''


@unittest.skipUnless(LINUX_ROOT, "needs Linux as root (disposable WSL/VM)")
class RealProcessTest(unittest.TestCase):
    """Real /proc reads of a real process laid out like the DEV Core API, and a real HTTP focus read."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gv1-proc-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = make_store(self.tmp / "lilith-dev.db", goals=DEV_GOALS, traces=DEV_TRACES)
        self.root = self.tmp / "lilith-os-dev"
        self.rel = self.root / "releases" / ("e" * 40)
        self.rel.mkdir(parents=True)
        shutil.copy(APP_PY, self.rel / "app.py")
        os.utime(self.rel / "app.py", (time.time() - 60, time.time() - 60))
        (self.root / "api-venv" / "bin").mkdir(parents=True)
        (self.root / "api-venv" / "bin" / "uvicorn").write_text(FAKE_API, encoding="utf-8")

    def start(self, env_extra):
        env = {"PATH": "/usr/bin:/bin", "LILITH_DB_PATH": str(self.db), **env_extra}
        p = subprocess.Popen([sys.executable, str(self.root / "api-venv/bin/uvicorn"), "app:app", "--port", "0"],
                             cwd=self.rel, env=env, stdout=subprocess.PIPE, text=True)
        self.addCleanup(p.wait)
        self.addCleanup(p.kill)
        port = int(p.stdout.readline())
        return p, port

    def check(self, pid, port, unit_env="LILITH_OS_FOCUS_READ_ONLY=1"):
        V.failures = []
        with mock.patch.multiple(V, CORE_API_ROOT=self.root, GOAL_DB=self.db, CORE_API_WAIT_S=1.0,
                                 CORE_API_FOCUS_URL=f"http://127.0.0.1:{port}/os/goals/focus",
                                 _unit_show=lambda: {"ActiveState": "active", "MainPID": str(pid), "Environment": unit_env}):
            V.check_focus_read_only()
        return list(V.failures)

    def test_real_process_with_the_flag_passes_and_writes_nothing(self):
        p, port = self.start({"LILITH_OS_FOCUS_READ_ONLY": "1"})
        before = sha(self.db)
        self.assertEqual(self.check(p.pid, port), [])
        self.assertEqual(sha(self.db), before)

    def test_real_process_without_the_flag_refuses_before_reading(self):
        p, port = self.start({})
        before = sha(self.db)
        self.assertEqual(self.check(p.pid, port), ["FOCUS_READ_ONLY_NOT_IN_EFFECT"])
        self.assertEqual(sha(self.db), before)

    def test_stopped_process_refuses(self):
        p, port = self.start({"LILITH_OS_FOCUS_READ_ONLY": "1"})
        p.kill(); p.wait()
        self.assertEqual(self.check(p.pid, port), ["CORE_API_RUNTIME_UNREADABLE"])


if __name__ == "__main__":
    unittest.main()
