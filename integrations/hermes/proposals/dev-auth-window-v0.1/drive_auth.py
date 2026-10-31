"""Runs the DEV auth window one phase at a time. Local; start each phase detached, from scripts/.

    python -B drive_auth.py --phase pre|post|model --execute
    python -B drive_auth.py --status

pre: read-only preflight, then the open drop-in. Then the owner-approved merge deploys the code; that is not a driver step.
post: the enforcement stages, two router turns, a rollback proof, the final check.
model: two model requests, only after post. A failure here is reported and changes nothing.

Rules, each pinned by test_drive_auth.py:
- A step is judged by its output, never its exit code. No step runs twice, and no phase starts twice: raw/drive.<phase>.started is exclusive and never removed.
- One driver at a time: raw/drive.lock. raw/drive.journal is flushed around every step, and the result line is written last.
- pre: a failed preflight changes nothing; a failed drop-in runs RA, which removes it.
- post: a B0 that aborts changes nothing. Any other failure, B0 included, runs RB once: the previous known-good release, as the deploy helper's own rollback would, with the same database.
- The merge is not a driver step: --merge-ready says MERGE_READY only after pre completed. The model phase also needs raw digest in APPROVED_MODEL, written only on the owner's separate approval.
- Lost transport: read status_ro.sh once. A pass marker means the step passed; a window script running, a gate not active or an unreadable status means HOLD. Otherwise failed.
- A failed recovery stops at once. A driver that dies has no recovery: --status says INTERRUPTED, and nothing resumes.
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
PASS, FAIL, LOST, HOLD = "PASS", "FAIL", "LOST", "HOLD"
PHASES = {
    "pre": (("a0", "a0_preflight_ro.sh", "A0_PREFLIGHT", None), ("a1", "a1_dropin_open.sh", "A1_DROPIN", "a1.pass")),
    "post": (("b0", "b0_verify_deploy_ro.sh", "B0_VERIFY", "b0.pass"), ("b1", "b1_tokens.sh", "B1_TOKENS", "b1.pass"), ("b2", "b2_enforce_write.sh", "B2_WRITE", "b2.pass"), ("b3", "b3_enforce_read.sh", "B3_READ", "b3.pass"),
             ("b4", "b4_router_turns.sh", "B4_TURNS", "b4.pass"), ("b5", "b5_rollback_proof.sh", "B5_ROLLBACK", "b5.pass"), ("b6", "b6_final_ro.sh", "B6_FINAL", None)),
    "model": (("m1", "m1_model_turns.sh", "M1_MODEL", "m1.pass"),),
}
RECOVERY = {"a1": ("ra", "ra_remove_dropin.sh", "RA_REMOVE"), "post": ("rb", "rb_restore_previous.sh", "RB_RESTORE")}


class Journal:
    def __init__(self, path):
        self.file = open(path, "a", encoding="ascii")

    def line(self, text):
        self.file.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), text))
        self.file.flush()
        os.fsync(self.file.fileno())


def lock(path):
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
    journal = raw / "drive.journal"
    lines = journal.read_text(encoding="ascii").splitlines() if journal.exists() else []
    results = [l.split()[2:4] for l in lines if " RESULT " in l]
    begun, ended = [l.split()[2] for l in lines if " BEGIN " in l], [l for l in lines if " END " in l]
    started = sorted(p.name for p in raw.glob("drive.*.started")) if raw.exists() else []
    if not started:
        return "NOT_STARTED", None
    if len(results) == len(started):
        return "FINISHED", " ".join(results[-1])
    held = lock(raw / "drive.lock")
    if held is None:
        return "RUNNING", begun[-1] if len(begun) > len(ended) else None
    held.close()
    return "INTERRUPTED", begun[-1] if len(begun) > len(ended) else None


def merge_ready(raw=RAW):
    journal = raw / "drive.journal"
    return journal.exists() and " RESULT pre DRIVE_COMPLETE" in journal.read_text(encoding="ascii")


def real_run(name, script):
    subprocess.run([sys.executable, "-B", "dread.py", name, script], cwd=HERE)
    path = RAW / (name + ".out")
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def verdict(out, tag):
    if re.search(r"^%s PASS" % tag, out, re.M):
        return PASS
    if re.search(r"^(%s FAIL|%s_ABORTED|%s_ABORTED|WRONG_HOST)" % (tag, tag, tag.split("_")[0]), out, re.M):
        return FAIL
    return LOST


def settle(run, marker):
    text = run("status_probe", "status_ro.sh")
    gate = re.search(r"^GATE .*ActiveState=(\w+)", text, re.M)
    running = re.search(r"^WINDOW_SCRIPTS_RUNNING (\d+)", text, re.M)
    if not gate or not running or int(running.group(1)) or gate.group(1) != "active":
        return HOLD
    return PASS if marker and (marker + "@") in text else FAIL


def judge(run, out, tag, marker):
    found = verdict(out, tag)
    return settle(run, marker) if found == LOST else found


def recover(run, say, key):
    name, script, tag = RECOVERY[key]
    found = judge(run, run(name, script), tag, None)
    say(f"STEP {name} {found}")
    if found == HOLD:
        return "DRIVE_HOLD"
    return "DRIVE_RECOVERED" if found == PASS else "DRIVE_RECOVERY_FAILED"


def drive(phase, run, say=print):
    for name, script, tag, marker in PHASES[phase]:
        out = run(name, script)
        found = judge(run, out, tag, marker)
        say(f"STEP {name} {found}")
        if found == PASS:
            continue
        if found == HOLD:
            return "DRIVE_HOLD"
        if name == "m1":
            return "DRIVE_MODEL_FAILED"
        if name == "a0" or (name == "b0" and "B0_ABORTED" in out):
            return "DRIVE_NOCHANGE"
        return recover(run, say, "a1" if phase == "pre" else "post")
    return "DRIVE_COMPLETE"


def execute(phase, run, raw=RAW, say=print):
    raw.mkdir(exist_ok=True)
    held = lock(raw / "drive.lock")
    if held is None:
        return "DRIVE_REFUSED_RUNNING"
    need = {"post": "pre", "model": "post"}.get(phase)
    text = (raw / "drive.journal").read_text(encoding="ascii") if (raw / "drive.journal").exists() else ""
    if need and f" RESULT {need} DRIVE_COMPLETE" not in text:
        held.close()
        return "DRIVE_REFUSED_ORDER"
    try:
        fd = os.open(raw / f"drive.{phase}.started", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        held.close()
        return "DRIVE_REFUSED_ALREADY_STARTED"
    os.close(fd)
    journal = Journal(raw / "drive.journal")
    journal.line(f"START {phase} pid {os.getpid()}")

    def noted(line):
        journal.line(line)
        say(line)

    def step(name, script):
        journal.line("BEGIN " + name)
        out = run(name, script)
        journal.line("END %s %s" % (name, hashlib.sha256(out.encode("utf-8", "replace")).hexdigest()[:16]))
        return out
    result = drive(phase, step, noted)
    journal.line(f"RESULT {phase} {result}")
    held.close()
    return result


def model_approved(digest, root=HERE.parent):
    try:
        return (root / "APPROVED_MODEL").read_text(encoding="ascii").strip() == digest
    except OSError:
        return False


def main():
    if "--status" in sys.argv:
        print("DRIVE_STATUS", *status())
        return 0
    if "--merge-ready" in sys.argv:
        print("MERGE_READY" if merge_ready() else "MERGE_NOT_READY")
        return 0 if merge_ready() else 1
    got = hashlib.sha256((HERE.parent / "SHA256SUMS").read_bytes()).hexdigest()
    phase = sys.argv[sys.argv.index("--phase") + 1] if "--phase" in sys.argv else None
    if "--execute" not in sys.argv or phase not in PHASES:
        print("PLAN ONLY.", {p: [s[0] for s in v] for p, v in PHASES.items()}, "manifest", got)
        return 0
    try:
        approved = (HERE.parent / "APPROVED_MANIFEST").read_text(encoding="ascii").strip()
    except OSError:
        approved = None
    if got != approved:
        print("DRIVE_REFUSED manifest", got)
        return 3
    if phase == "model" and not model_approved(got):
        print("DRIVE_REFUSED model phase not approved")
        return 3
    result = execute(phase, real_run)
    print(result)
    return 0 if result == "DRIVE_COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
