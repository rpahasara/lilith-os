#!/usr/bin/env bash
# Offline rehearsal of review_window.sh. TEST_ONLY. Root on a disposable Linux machine (never a LILITH host):
#   sudo bash rehearse_review_window.sh <bundle-dir>
# <bundle-dir> holds review_window.sh, candidate.py (#412's owner_memory_review.py) and live/ (main's
# owner_memory_review.py, owner_memory_snapshot.py, owner_memory_sync.py, commitment_sync.py).
# Re-executes in private mount + hostname namespaces (hostname vmi3753642, the PROD host) with overlays on /etc /home /root /var.
# A stand-in scheduler (as lilith) really runs owner_memory_snapshot.py (runpy import of the review script) and the
# exact import commitment_sync.py does, writing ok/error into a PROD-shaped cron/jobs.json. Prints PASS/FAIL per case.
set -Eeuo pipefail
B=$(readlink -f "${1:?bundle dir}")
if [[ -z ${RVREH_INNER:-} ]]; then
  [[ $(id -u) -eq 0 && $(hostname) != lilith-* && $(hostname) != vmi3753642 ]] || { echo "root on a non-lilith host only"; exit 2; }
  exec env RVREH_INNER=1 unshare -m -u --propagation private bash "$0" "$B"
fi
hostname vmi3753642
W=$(mktemp -d /tmp/rvreh.XXXXXX)
for d in etc home root var; do mkdir -p "$W/ov/$d/u" "$W/ov/$d/w"; mount -t overlay overlay -o "lowerdir=/$d,upperdir=$W/ov/$d/u,workdir=$W/ov/$d/w" "/$d"; done
mount -t tmpfs -o mode=0755 tmpfs /run
FAILS=0; OUT=; RC=0
pass() { echo "PASS $*"; }; fail() { echo "FAIL $*"; FAILS=$((FAILS + 1)); }
check() { if eval "$2"; then pass "$1"; else fail "$1"; echo "$OUT" | tail -6 | sed 's/^/    > /'; fi; }
run() { set +e; OUT=$("$@" 2>&1); RC=$?; set -e; }

id lilith >/dev/null 2>&1 || useradd --create-home --home-dir /home/lilith lilith
H=/home/lilith/.hermes; D=$H/scripts
install -d -o lilith -g lilith -m 0700 "$H" "$D" "$H/cron" "$H/memories" "$H/lilith_router" "$H/hermes-agent" "$H/hermes-agent/venv" "$H/hermes-agent/venv/bin"
ln -s /usr/bin/python3 "$H/hermes-agent/venv/bin/python"
for f in owner_memory_review.py owner_memory_snapshot.py owner_memory_sync.py commitment_sync.py; do install -o lilith -g lilith -m 0644 "$B/live/$f" "$D/$f"; done
printf 'model:\n  default: x\n_config_version: 7\ntimezone: Asia/Colombo\n' > "$W/config.yaml"; install -o lilith -g lilith -m 0600 "$W/config.yaml" "$H/config.yaml"
echo '{"schemaVersion": 1, "enabled": true, "ownerTelegramUserIds": ["111"]}' > "$W/cm.json"; install -o lilith -g lilith -m 0644 "$W/cm.json" "$H/lilith_router/canonical_memory.json"
echo "TEST_ONLY prefers tea." > "$W/u.md"; install -o lilith -g lilith -m 0600 "$W/u.md" "$H/memories/USER.md"
runuser -u lilith -- python3 -I - "$H/state.db" <<'PY'
import sqlite3, sys, time
c = sqlite3.connect(sys.argv[1]); now = time.time()
c.executescript("CREATE TABLE sessions (id TEXT, source TEXT, user_id TEXT, chat_id TEXT, chat_type TEXT);"
                "CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, timestamp REAL, active INTEGER);")
c.executemany("INSERT INTO sessions VALUES (?,?,?,?,?)", [("dm", "telegram", "111", "111", "dm"), ("grp", "telegram", "111", "-5", "group")])
c.executemany("INSERT INTO messages (session_id, role, content, timestamp, active) VALUES (?,?,?,?,1)",
              [("dm", "user", "TEST_ONLY I passed the exam yesterday", now - 3 * 3600), ("dm", "assistant", "TEST_ONLY nice", now - 3 * 3600 + 5),
               ("dm", "user", "TEST_ONLY moving next week", now - 600), ("grp", "user", "TEST_ONLY group text", now - 500)])
c.commit()
PY
runuser -u lilith -- python3 -I -c '
import json
j = [{"id": "e161234245f3", "name": "lilith-nightly-memory-review", "enabled": True, "schedule": {"kind": "cron", "expr": "0 22 * * *"},
      "script": "owner_memory_review.py", "next_run_at": "2026-11-12T22:00:00+05:30", "last_run_at": "2026-11-11T22:00:40+05:30", "last_status": "ok"},
     {"id": "f56407e4cef8", "name": "lilith-memory-proposal-snapshot", "enabled": True, "schedule": {"kind": "cron", "expr": "*/10 * * * *"},
      "script": "owner_memory_snapshot.py", "next_run_at": None, "last_run_at": None, "last_status": "ok"},
     {"id": "5365cfb456d4", "name": "lilith-commitment-sync", "enabled": True, "schedule": {"kind": "cron", "expr": "* * * * *"},
      "script": "commitment_sync.py", "next_run_at": None, "last_run_at": None, "last_status": "ok"}]
json.dump({"jobs": j}, open("/home/lilith/.hermes/cron/jobs.json", "w"))'
chmod 0600 "$H/cron/jobs.json"
cat > /tmp/sched.py <<'PY'
import datetime as dt, json, os, subprocess, sys, time
H = "/home/lilith/.hermes"; D = H + "/scripts"; P = H + "/cron/jobs.json"
while True:
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).isoformat()
    snap = subprocess.run([sys.executable, "-I", D + "/owner_memory_snapshot.py"], capture_output=True, env={"HERMES_HOME": H, "LILITH_OS_API_URL": "http://127.0.0.1:9", "PATH": "/usr/bin:/bin"}).returncode
    sync = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r); from owner_memory_review import owner_discord_dms, owner_ids" % D],
                          capture_output=True).returncode
    d = json.load(open(P))
    for j in d["jobs"]:
        if os.path.exists("/tmp/sched.freeze"):
            continue
        if j["id"] == "f56407e4cef8": j.update(last_run_at=now, last_status="ok" if snap == 0 else "error")
        if j["id"] == "5365cfb456d4": j.update(last_run_at=now, last_status="ok" if sync == 0 else "error")
    t = P + ".tmp"; json.dump(d, open(t, "w")); os.replace(t, P)
    time.sleep(2)
PY
chmod 0644 /tmp/sched.py
runuser -u lilith -- python3 -I /tmp/sched.py >/dev/null 2>&1 &
SCHED=$!; trap 'kill $SCHED 2>/dev/null' EXIT
cat > /tmp/systemctl <<'SH'
#!/bin/sh
[ "$1 $2" = "is-active hermes-gateway" ] && { echo active; exit 0; }
echo "rehearsal systemctl refused: $*" >&2; exit 1
SH
chmod 0755 /tmp/systemctl; mount --bind /tmp/systemctl /usr/bin/systemctl
sleep 3
export REVIEW_SIM=1
RW="bash $B/review_window.sh"; CAND=$B/candidate.py
live() { sha256sum < "$D/owner_memory_review.py" | cut -c1-64; }
LIVE=$(sha256sum < "$B/live/owner_memory_review.py" | cut -c1-64); NEW=$(sha256sum < "$CAND" | cut -c1-64)
lastbk() { ls -1d /var/backups/lilith-review/2* 2>/dev/null | tail -1; }

run $RW precheck "$CAND"; check "precheck PASS on the PROD-shaped host" '[[ $RC -eq 0 && $OUT == *REVIEW_PRECHECK_PASS* ]]'
run env REVIEW_SIM_CLOCK=16:15 $RW precheck "$CAND"; check "precheck refuses in the 16:00-17:00Z review blackout" '[[ $RC -eq 1 && $OUT == *blackout* ]]'
cp "$CAND" "$W/bad.py"; echo "# TEST_ONLY" >> "$W/bad.py"; run $RW precheck "$W/bad.py"
check "precheck refuses a candidate that is not #412" '[[ $RC -eq 1 && $OUT == *"not the #412 file"* ]]'
cp -p "$D/owner_memory_review.py" "$W/live.bak"; echo "# TEST_ONLY" >> "$D/owner_memory_review.py"; run $RW precheck "$CAND"; cp -p "$W/live.bak" "$D/owner_memory_review.py"
check "precheck refuses an unexpected live review script" '[[ $RC -eq 1 && $OUT == *"neither the inventoried one"* ]]'
cp -p "$D/commitment_sync.py" "$W/cs.bak"; echo "# TEST_ONLY" >> "$D/commitment_sync.py"; run $RW precheck "$CAND"; cp -p "$W/cs.bak" "$D/commitment_sync.py"
check "precheck refuses a changed dependant" '[[ $RC -eq 1 && $OUT == *"dependant commitment_sync.py changed"* ]]'
cp -p "$H/config.yaml" "$W/cfg.bak"; printf 'model:\n  default: x\n' > "$H/config.yaml"; run $RW precheck "$CAND"; cp -p "$W/cfg.bak" "$H/config.yaml"
check "precheck refuses when Hermes is not on Asia/Colombo" '[[ $RC -eq 1 && $OUT == *"not Asia/Colombo"* ]]'
check "  (live file untouched by the refusals)" '[[ $(live) == "$LIVE" ]]'

for at in before_swap after_swap; do
  run env REVIEW_SIM_FAIL_AT=$at $RW install "$CAND"
  check "install fails at $at: previous file restored exactly and importing" '[[ $RC -eq 1 && $OUT == *REVIEW_FAIL_RESTORED* && $(live) == "$LIVE" && $(stat -c "%U:%G %a" $D/owner_memory_review.py) == "lilith:lilith 644" ]]'
done
run $RW install "$CAND"; BK=$(lastbk)
check "install succeeds: #412 in place (lilith 0644), import check shows zone Asia/Colombo" '[[ $RC -eq 0 && $OUT == *REVIEW_INSTALLED* && $OUT == *"zone Asia/Colombo"* && $(live) == "$NEW" && $(stat -c "%U:%G %a" $D/owner_memory_review.py) == "lilith:lilith 644" ]]'
check "  backup root 0700/0600 holds the exact previous file; lilith cannot read it" '[[ $(stat -c "%U %a" $BK) == "root 700" && $(stat -c "%U %a" $BK/owner_memory_review.py) == "root 600" && $(sha256sum < $BK/owner_memory_review.py | cut -c1-64) == "$LIVE" ]] && ! runuser -u lilith -- cat $BK/owner_memory_review.py >/dev/null 2>&1'
run $RW install "$CAND"; check "a second install refuses" '[[ $RC -eq 1 && $OUT == *"already installed"* ]]'
sleep 5
run $RW verify; check "verify PASS: file, imports, the real snapshot job ran ok with the new file" '[[ $RC -eq 0 && $OUT == *"REVIEW_VERIFY PASS"* ]]'
run $RW verify --dry-run
check "verify --dry-run: counts only, zone header, day markers, owner lines only from the owner DM" '[[ $RC -eq 0 && $OUT == *"zone_header True"* && $OUT == *"owner_lines 2"* && $OUT == *"guidance_dates True"* && $OUT != *TEST_ONLY* ]]'
touch /tmp/sched.freeze; runuser -u lilith -- python3 -I -c 'import json; p="/home/lilith/.hermes/cron/jobs.json"; d=json.load(open(p)); [j.update(last_status="error") for j in d["jobs"] if j["id"]=="f56407e4cef8"]; json.dump(d, open(p,"w"))'
run $RW verify; check "verify exits nonzero when the snapshot job reports an error" '[[ $RC -ne 0 && $OUT == *"FAIL R3"* ]]'
rm -f /tmp/sched.freeze; sleep 5
cp -p "$BK/owner_memory_review.py" "$W/bk.bak"; echo "# TEST_ONLY" >> "$BK/owner_memory_review.py"
run $RW rollback "$BK"; check "rollback with a tampered backup -> REVIEW_ESCALATE (exit 3), #412 file left in place" '[[ $RC -eq 3 && $OUT == *REVIEW_ESCALATE* && $(live) == "$NEW" ]]'
cp -p "$W/bk.bak" "$BK/owner_memory_review.py"
run $RW rollback "$BK"; check "rollback restores the exact previous file and it imports" '[[ $RC -eq 0 && $OUT == *REVIEW_ROLLED_BACK* && $(live) == "$LIVE" ]]'
sleep 5
run $RW verify; check "verify after rollback FAILs R1 (the old file is live), nonzero" '[[ $RC -ne 0 && $OUT == *"FAIL R1"* && $OUT == *"PASS R3"* ]]'
run $RW install "$CAND"; check "install again after rollback succeeds" '[[ $RC -eq 0 && $(live) == "$NEW" ]]'
echo "REHEARSAL_RESULT $([[ $FAILS -eq 0 ]] && echo PASS || echo "FAIL ($FAILS)")"
exit $FAILS
