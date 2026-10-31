"""Runs the e1 window once, in order, and returns to p1 on failure. Local; run from scripts/.

    python -B drive_e1.py --execute      runs the window; start it detached (RUNBOOK.md)
    python -B drive_e1.py --status       reads the local journal only; never touches the host

Rules, each pinned by tests/test_drive_e1.py:
- A step is judged by its output, never its exit code: the SDK plink can crash on exit after a complete run.
- No step ever runs twice, and the window never starts twice: raw/drive.started is created exclusively and never removed.
- One driver at a time: raw/drive.lock is held for the life of the process, so the OS frees it however the process ends.
- raw/drive.journal is flushed to disk before and after each step. The result line is written last, so no result line means the run did not finish.
- P0, or S1 aborting before the stop: nothing changed, so no rollback.
- Any later failure: R1, R2, R3, R4, each once.
- Lost transport (no verdict line): read status_ro.sh once. A pass marker means the step passed. A window script still running, or a gate that is not active, means HOLD:
  stop and report, because acting then would be improvising. Otherwise the step failed, so roll back.
- A failed rollback step stops at once and reports: the gateway stays as it is.
- A driver that dies has no rollback: it lives in this process. --status then says INTERRUPTED and names the open step. Nothing resumes by itself.
Result lines: DRIVE_COMPLETE, DRIVE_NOCHANGE, DRIVE_RETURNED_TO_P1, DRIVE_ROLLBACK_FAILED, DRIVE_HOLD.
"""
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "raw"
PASS, FAIL, LOST = "PASS", "FAIL", "LOST"
STEPS = (("p0", "p0_e1.sh", r"^P0_E1 PASS", r"^P0_E1 (FAIL|ABORTED)", None),
         ("s1", "s1_stop_p1.sh", r"^S1_STOP_P1 PASS", r"^S1_STOP(_P1 FAIL|_ABORTED)", "s1.pass"),
         ("s2", "s2_transfer_e1.sh", r"^CHUNK1 OK", r"^(CHUNK MISMATCH|S1_NOT_PASSED|STAGING_DIR_EXISTS|WRONG_HOST)", None),
         ("s2b", "s2b_transfer_e1.sh", r"^CHUNK OK", r"^(CHUNK MISMATCH|CHUNK1_NOT_IN_PLACE|WRONG_HOST)", None),
         ("s3", "s3_install_e1.sh", r"^S3_INSTALL_E1 PASS", r"^S3_(INSTALL_E1 FAIL|ABORTED)", "s3.pass"),
         ("s4", "s4_start_e1.sh", r"^S4_START_E1 PASS", r"^S4_(START_E1 FAIL|START_ABORTED|ABORTED)", "s4.pass"),
         ("s5", "s5_post_verify_ro.sh", r"^S5_POST_VERIFY PASS", r"^S5_POST_VERIFY FAIL", "s5.pass"),
         ("s6", "s6_shadow_test.sh", r"^S6_SHADOW_TEST PASS", r"^S6_(SHADOW_TEST FAIL|STOPPED)", "s6.pass"),
         ("s7", "s7_final_ro.sh", r"^S7_FINAL_VERIFY PASS", r"^S7_FINAL_VERIFY FAIL", None))
ROLLBACK = (("r1", "r1_stop.sh", r"^R1_RETURN_STOP PASS", r"^R1_(RETURN_STOP FAIL|ABORTED)", "r1.pass"),
            ("r2", "r2_revert.sh", r"^R2_RETURN_REVERT PASS", r"^R2_(RETURN_REVERT FAIL|ABORTED)", "r2.pass"),
            ("r3", "r3_start_p1.sh", r"^R3_RETURN_START_P1 PASS", r"^R3_(RETURN_START_P1 FAIL|START_ABORTED|ABORTED)", "r3.pass"),
            ("r4", "r4_final_ro.sh", r"^R4_FINAL_VERIFY PASS", r"^R4_FINAL_VERIFY FAIL", None))


class Journal:
    """Append-only, flushed to disk on every line. A power cut loses at most the line being written."""

    def __init__(self, path):
        self.file = open(path, "a", encoding="ascii")

    def line(self, text):
        self.file.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), text))
        self.file.flush()
        os.fsync(self.file.fileno())


def lock(path):
    """An OS lock on an open file: None if another driver holds it. Freed by the OS when this process ends, however it ends."""
    handle = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def status(raw=RAW):
    """What the local record says. Reads only; changes nothing here or on the host."""
    started, journal = raw / "drive.started", raw / "drive.journal"
    if not started.exists():
        return "NOT_STARTED", None
    lines = journal.read_text(encoding="ascii").splitlines() if journal.exists() else []
    results = [l.split()[2] for l in lines if " RESULT " in l]
    if results:
        return "FINISHED", results[-1]
    held = lock(raw / "drive.lock")
    if held is None:
        return "RUNNING", _open_step(lines)
    held.close()
    return "INTERRUPTED", _open_step(lines)


def _open_step(lines):
    begun = [l.split()[2] for l in lines if " BEGIN " in l]
    ended = [l.split()[2] for l in lines if " END " in l]
    return begun[-1] if begun and len(begun) > len(ended) else None


def real_run(name, script):
    subprocess.run([sys.executable, "-B", "dread.py", name, script], cwd=HERE)
    path = RAW / (name + ".out")
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def verdict(out, good, bad):
    if re.search(good, out, re.M):
        return PASS
    if re.search(bad, out, re.M):
        return FAIL
    return LOST


def probe(run):
    text = run("status_probe", "status_ro.sh")
    gate = re.search(r"^GATE .*ActiveState=(\w+)", text, re.M)
    running = re.search(r"^WINDOW_SCRIPTS_RUNNING (\d+)", text, re.M)
    return {"text": text, "complete": bool(gate and running), "markers": text, "gate_active": bool(gate) and gate.group(1) == "active", "running": int(running.group(1)) if running else 0}


def settle(run, status, marker):
    """A lost verdict: PASS, FAIL or HOLD, from the one read-only probe."""
    p = probe(run)
    if not p["complete"] or p["running"] or not p["gate_active"]:
        return "HOLD"
    return PASS if marker and (marker + "@") in p["markers"] else FAIL


def rollback(run, say):
    for name, script, good, bad, marker in ROLLBACK:
        status = verdict(run(name, script), good, bad)
        if status == LOST:
            status = settle(run, status, marker)
        say(f"STEP {name} {status}")
        if status == "HOLD":
            return "DRIVE_HOLD"
        if status != PASS:
            return "DRIVE_ROLLBACK_FAILED"
    return "DRIVE_RETURNED_TO_P1"


def drive(run, say=print):
    for name, script, good, bad, marker in STEPS:
        out = run(name, script)
        status = verdict(out, good, bad)
        if status == LOST:
            status = settle(run, status, marker)
        say(f"STEP {name} {status}")
        if status == PASS:
            continue
        if status == "HOLD":
            return "DRIVE_HOLD"
        if name == "p0" or (name == "s1" and re.search(r"^S1_STOP_ABORTED", out, re.M)):
            return "DRIVE_NOCHANGE"
        return rollback(run, say)
    return "DRIVE_COMPLETE"


def journaled(run, journal):
    def step(name, script):
        journal.line("BEGIN " + name)
        out = run(name, script)
        journal.line("END %s %s" % (name, hashlib.sha256(out.encode("utf-8", "replace")).hexdigest()[:16]))
        return out
    return step


def execute(run, raw=RAW, say=print):
    """The whole run: one driver, one window, one journal. Returns the result line, or DRIVE_REFUSED_* with nothing done."""
    raw.mkdir(exist_ok=True)
    held = lock(raw / "drive.lock")
    if held is None:
        return "DRIVE_REFUSED_RUNNING"
    try:
        fd = os.open(raw / "drive.started", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        held.close()
        return "DRIVE_REFUSED_ALREADY_STARTED"
    os.write(fd, ("pid %d\n" % os.getpid()).encode("ascii"))
    os.fsync(fd)
    os.close(fd)
    journal = Journal(raw / "drive.journal")
    journal.line("START pid %d" % os.getpid())
    def noted(line):
        journal.line(line)
        say(line)
    result = drive(journaled(run, journal), noted)
    journal.line("RESULT " + result)
    held.close()
    return result


def main():
    if "--status" in sys.argv:
        state, detail = status()
        print("DRIVE_STATUS", state, detail or "-")
        return 0
    got = hashlib.sha256((HERE.parent / "SHA256SUMS").read_bytes()).hexdigest()
    if "--execute" not in sys.argv:
        print("PLAN ONLY. Steps:", [s[0] for s in STEPS], "rollback:", [s[0] for s in ROLLBACK], "manifest", got)
        return 0
    if got != MANIFEST_APPROVED():
        print("DRIVE_REFUSED manifest", got)
        return 3
    result = execute(real_run)
    print(result)
    return 0 if result == "DRIVE_COMPLETE" else 1


def MANIFEST_APPROVED():
    """The owner's approved digest. It is written only when the owner approves this exact manifest; without it nothing runs."""
    try:
        return (HERE.parent / "APPROVED_MANIFEST").read_text(encoding="ascii").strip()
    except OSError:
        return None


if __name__ == "__main__":
    sys.exit(main())
