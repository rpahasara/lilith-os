"""The Cutover 1 window on lilith-01. Local; start each phase detached, from this directory (PREPARED, NOT APPROVED, NOT RUN). Adapted from the DEV auth driver, which passed its window.

    python -B drive_c1.py --phase preflight|window|return --execute
    python -B drive_c1.py --status

preflight: read-only review of lilith-01. window: baseline, fresh snapshot, tokens, deploy.yml at the exact SHA, enforcement, comparison. return: the app.py return, on the owner's word.

Rules, each pinned by test_drive_c1.py:
- A step is judged by its output, never its exit code. No step runs twice, and no phase starts twice: raw/drive.<phase>.started is exclusive and never removed.
- One driver at a time: raw/drive.lock. raw/drive.journal is flushed around every step, and the result line is written last.
- A failure at or before the snapshot changes nothing. Any later failure runs RB once: the previous code, open, with the same data.
- preflight needs APPROVED_PREPARE. window needs APPROVED_WINDOW, a passed preflight and both signed sheets. Each approval file holds this manifest's digest and is written only on the owner's approval.
- Lost transport: read status once. A pass marker means the step passed; a window script running, a gateway not active or an unreadable status means HOLD. Otherwise failed.
- A failed recovery stops at once. A driver that dies has no recovery: --status says INTERRUPTED, and nothing resumes.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
PASS, FAIL, LOST, HOLD = "PASS", "FAIL", "LOST", "HOLD"
PHASES = {
    "preflight": (("p0", "w0 p0", "W0", "w0.p0.pass"),),
    "window": (("w0", "w0 pre", "W0", "w0.pre.pass"), ("snap", None, "SNAP", None), ("w1", "w1", "W1", "w1.pass"), ("deploy", None, "DEPLOY", None), ("w2", "w2", "W2", "w2.pass"),
               ("w3", "w3", "W3", "w3.pass"), ("w4", "w4", "W4", "w4.pass"), ("w5", "w5", "W5", "w5.pass")),
    "return": (("rb", "rb", "RB_RESTORE", "rb.pass"),),
}
NOCHANGE = ("p0", "w0", "snap")
GCLOUD = os.environ.get("C1_GCLOUD", r"C:\Users\edufo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd")
GH = os.environ.get("C1_GH", "gh")
PROJECT, ZONE, VM, REPO = "lilith-agent-260823-27389", "asia-southeast1-b", "lilith-01", "rpahasara/lilith-os"
TARGET = "75ca0db084ef43f39462e3fe77b2f3fce8f5a0e2"
SNAPSHOT = "lilith-01-cutover1-" + time.strftime("%Y%m%d", time.gmtime())


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


def call(*args, timeout=300):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, ""   # lost transport, judged like any other
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def ssh(stage):
    return call(GCLOUD, "compute", "ssh", VM, "--zone=" + ZONE, "--project=" + PROJECT, "--tunnel-through-iap", "--quiet", "--command=sudo -n bash /var/tmp/c1/guest_c1.sh " + stage, timeout=600)[1]


def snap():
    rc, _ = call(GCLOUD, "compute", "disks", "snapshot", VM, "--zone=" + ZONE, "--project=" + PROJECT, "--snapshot-names=" + SNAPSHOT, "--storage-location=asia", "--format=none", timeout=900)
    if rc:
        return "SNAP FAIL: create rc %d\n" % rc
    rc, out = call(GCLOUD, "compute", "snapshots", "describe", SNAPSHOT, "--project=" + PROJECT, "--format=value(status)")
    return "SNAP PASS %s\n" % SNAPSHOT if out.strip() == "READY" else "SNAP FAIL: status %s\n" % out.strip()[:40]


def deploy(wait=20, limit=90):
    rc, out = call(GH, "api", "repos/%s/commits/main" % REPO, "--jq", ".sha")
    if rc or out.strip() != TARGET:
        return "DEPLOY FAIL: main is not the sealed commit\n"
    rc, out = call(GH, "run", "list", "--repo", REPO, "--workflow", "deploy.yml", "--limit", "1", "--json", "databaseId")
    if rc:
        return "DEPLOY FAIL: run list\n"
    runs = json.loads(out)
    before = runs[0]["databaseId"] if runs else 0
    rc, _ = call(GH, "workflow", "run", "deploy.yml", "--repo", REPO, "--ref", "main", "-f", "approved_main_sha=" + TARGET)
    if rc:
        return "DEPLOY FAIL: dispatch rc %d\n" % rc
    for _ in range(limit):
        time.sleep(wait)
        rc, out = call(GH, "run", "list", "--repo", REPO, "--workflow", "deploy.yml", "--limit", "1", "--json", "databaseId,status,conclusion,headSha")
        runs = json.loads(out) if not rc else []
        if runs and runs[0]["databaseId"] != before and runs[0]["status"] == "completed":
            good = runs[0]["conclusion"] == "success" and runs[0]["headSha"] == TARGET
            return "DEPLOY %s run %s\n" % ("PASS" if good else "FAIL: " + str(runs[0]["conclusion"]), runs[0]["databaseId"])
    return "DEPLOY FAIL: no result\n"


def real_run(name, stage):
    out = {"snap": snap, "deploy": deploy}[name]() if stage is None else ssh(stage)
    RAW.mkdir(exist_ok=True)
    (RAW / (name + ".out")).write_text(out, encoding="utf-8")
    return out


def verdict(out, tag):
    if re.search(r"^%s PASS" % tag, out, re.M):
        return PASS
    if re.search(r"^(%s FAIL|%s_ABORTED|%s_ABORTED|WRONG_HOST)" % (tag, tag, tag.split("_")[0]), out, re.M):
        return FAIL
    return LOST


def settle(run, marker):
    text = run("status_probe", "status")
    gate = re.search(r"^GATE .*ActiveState=(\w+)", text, re.M)
    running = re.search(r"^WINDOW_SCRIPTS_RUNNING (\d+)", text, re.M)
    if not gate or not running or int(running.group(1)) or gate.group(1) != "active":
        return HOLD
    return PASS if marker and (marker + "@") in text else FAIL


def judge(run, out, tag, marker):
    found = verdict(out, tag)
    if found != LOST:
        return found
    return settle(run, marker) if marker else FAIL   # a local step has no host marker: no clear pass is a failure


def recover(run, say):
    found = judge(run, run("rb", "rb"), "RB_RESTORE", "rb.pass")
    say(f"STEP rb {found}")
    if found == HOLD:
        return "DRIVE_HOLD"
    return "DRIVE_RECOVERED" if found == PASS else "DRIVE_RECOVERY_FAILED"


def drive(phase, run, say=print):
    for name, stage, tag, marker in PHASES[phase]:
        found = judge(run, run(name, stage), tag, marker)
        say(f"STEP {name} {found}")
        if found == PASS:
            continue
        if found == HOLD:
            return "DRIVE_HOLD"
        if name in NOCHANGE:
            return "DRIVE_NOCHANGE"
        if phase == "return":
            return "DRIVE_RECOVERY_FAILED"
        return recover(run, say)
    return "DRIVE_COMPLETE"


def execute(phase, run, raw=RAW, say=print):
    raw.mkdir(exist_ok=True)
    held = lock(raw / "drive.lock")
    if held is None:
        return "DRIVE_REFUSED_RUNNING"
    text = (raw / "drive.journal").read_text(encoding="ascii") if (raw / "drive.journal").exists() else ""
    need = {"window": "preflight"}.get(phase)
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

    def step(name, stage):
        journal.line("BEGIN " + name)
        out = run(name, stage)
        journal.line("END %s %s" % (name, hashlib.sha256(out.encode("utf-8", "replace")).hexdigest()[:16]))
        return out
    result = drive(phase, step, noted)
    journal.line(f"RESULT {phase} {result}")
    held.close()
    return result


def approved(phase, digest, root=HERE):
    if phase == "return":
        return True
    name = {"preflight": "APPROVED_PREPARE", "window": "APPROVED_WINDOW"}[phase]
    try:
        ok = (root / name).read_text(encoding="ascii").strip() == digest
    except OSError:
        return False
    return ok and (phase != "window" or all((root / s).exists() for s in ("BASELINE-SIGNED.txt", "ACCEPTANCE-SIGNED.txt")))


def main():
    if "--status" in sys.argv:
        print("DRIVE_STATUS", *status())
        return 0
    got = hashlib.sha256((HERE / "MANIFEST.txt").read_bytes()).hexdigest()
    phase = sys.argv[sys.argv.index("--phase") + 1] if "--phase" in sys.argv else None
    if "--execute" not in sys.argv or phase not in PHASES:
        print("PLAN ONLY.", {p: [s[0] for s in v] for p, v in PHASES.items()}, "manifest", got)
        return 0
    if not approved(phase, got):
        print("DRIVE_REFUSED not approved", got)
        return 3
    result = execute(phase, real_run)
    print(result)
    if phase == "window" and result == "DRIVE_COMPLETE":
        (HERE / "RETURN-WINDOW.txt").write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 48 * 3600)) + "\n", encoding="ascii")
    return 0 if result == "DRIVE_COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
