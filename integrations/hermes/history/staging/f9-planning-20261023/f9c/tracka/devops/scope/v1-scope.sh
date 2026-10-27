STEP=v1-scope
# READ-ONLY F8r2 backup scope verification. Writes only its own output under /var/tmp/f8/f9c2-run and a private
# /dev/shm scratch dir (removed at exit). Never prints message content: only counts, classes, hashes.
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST $(hostname)"; exit 1; }
[[ $(id -u) -eq 0 ]] || { echo "NOT ROOT"; exit 1; }
RUN=/var/tmp/f8/f9c2-run; [[ -d $RUN ]] || { echo "NO RUN DIR"; exit 1; }
exec > >(tee -a "$RUN/${STEP}.out") 2>&1
HH=/home/lilith/.hermes-dev; B=/var/backups/hermes-gateway-dev; R=/opt/hermes-gateway-dev/current
PY=$R/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11
SCR=$(mktemp -d /dev/shm/f9scope.XXXXXX); chmod 700 "$SCR"; trap 'rm -rf "$SCR"; echo "scratch removed: $([[ -e $SCR ]] && echo NO || echo yes)"' EXIT
echo "=== ${STEP} $(date -u +%Y-%m-%dT%H:%M:%SZ) boot=$(cut -c1-8 /proc/sys/kernel/random/boot_id)"
treesum() { (cd "$B" && { find "$@" -xdev -type f -print0 | sort -z | xargs -0 sha256sum; find "$@" -xdev -type l -printf '%p -> %l\n' | sort; \
  find "$@" -xdev -printf '%p %m %U %G %s\n' | sort; } | sha256sum | cut -c1-64); }
T0=$(treesum rollback-20261023T123157Z upgrade-pre-20261023T123016Z)
echo "--- A. backup root top level"
for e in "$B"/*; do printf '  %-44s %s files=%s bytes=%s mtime=%s\n' "${e#$B/}" "$(stat -c '%U:%G %a %F' "$e")" \
  "$(find "$e" -xdev -type f | wc -l)" "$(du -sb "$e" | cut -f1)" "$(stat -c %y "$e" | cut -c1-19)"; done
echo "  upgrade-pre contents:"; (cd $B/upgrade-pre-20261023T123016Z && find . -maxdepth 2 | sort | sed 's/^/    /')
echo "--- B. executor scan_backups items (same code as the FORGET BACKUPS phase)"
$PY -I -B - "$R/bin" "$B" <<'PY'
import sys, collections
sys.path.insert(0, sys.argv[1]); import hermes_forget_executor as X
root = X.Path(sys.argv[2]); items = X.scan_backups(root)
c = collections.Counter((str(i.path.relative_to(root)).split("/")[0], i.kind) for i in items)
for (t, k), n in sorted(c.items()): print(f"  {t} {k} x{n}")
print("  total", len(items))
for i in items:
    rel = str(i.path.relative_to(root)); top = rel.split("/")[0]
    if top.startswith(("rollback-20261023T123157Z", "upgrade-pre-20261023T123016Z")):
        print(f"    {i.kind:24} {i.size:>9} {i.sha256[:16]} {rel.split('/',1)[1] if '/' in rel else rel}{('!'+i.member) if i.member else ''}")
PY
echo "--- C/D. content classification (private RAM copies; originals untouched)"
JD=$(find $B/rollback-20261023T123157Z -xdev -type d -name '*.hermes-gateway-dev' | head -1)
JF="$SCR/journal-copy.txt"; [[ -n $JD ]] && journalctl --directory="$JD" -o short-iso-precise --no-pager > "$JF" 2>/dev/null
echo "  journal copy: dir=${JD#$B/} files=$(find "$JD" -type f | wc -l) entries=$(wc -l < "$JF") first=$(head -1 "$JF" | cut -c1-26) last=$(tail -1 "$JF" | cut -c1-26)"
$PY -I -B - "$B" "$SCR" "$JF" <<'PY'
import sys, os, re, tarfile, shutil, sqlite3, hashlib, collections, json
B, SCR, JF = sys.argv[1:4]
SMOKE = {"F8-SYNTHETIC hello, this is an infrastructure smoke test. Reply with one short sentence.",
         "F8-SYNTHETIC relay check", "F8-SYNTHETIC ping"}
SLASH = {"/update", "/tools enable terminal", "/skills install demo", "/model --global x", "/cron list",
         "/reload", "/restart", "/yolo", "/sethome"}
def ucls(t):
    t = (t or "").strip()
    if t in SMOKE: return "smoke-exact"
    if t in SLASH: return "slash-allowlisted"
    if t.startswith("F8-SYNTHETIC UI check"): return "g10-ui"
    if "F8-SYNTHETIC" in t: return "F8-SYNTHETIC-other"
    return "UNMATCHED"
def acls(t):
    l = (t or "").lower()
    for k in ("provider authentication failed", "admin-only", "unknown command"):
        if k in l: return k
    return "OTHER" if l.strip() else "empty"
def db_report(label, d):
    con = sqlite3.connect(os.path.join(d, "state.db")); q = lambda s, *a: con.execute(s, a).fetchall()
    ntab = len(q("select name from sqlite_master where type='table'"))
    print(f"  [{label}] integrity={q('pragma integrity_check')[0][0]} tables={ntab}")
    cols = [r[1] for r in q("pragma table_info(sessions)")]
    pick = [c for c in ("id", "source", "user_id", "chat_id", "started_at", "message_count") if c in cols]
    for r in q(f"select {','.join(pick)} from sessions order by started_at"):
        r = dict(zip(pick, r)); uid = r.pop("user_id", None)
        r["user_id_sha"] = hashlib.sha256(str(uid).encode()).hexdigest()[:12]; print("    session", r)
    mc = [r[1] for r in q("pragma table_info(messages)")]
    tcol = "timestamp" if "timestamp" in mc else None
    rows = q(f"select role, content{','+tcol if tcol else ''} from messages")
    print(f"    messages={len(rows)} by_role={dict(collections.Counter(r[0] for r in rows))}")
    print("    user classes", dict(collections.Counter(ucls(r[1]) for r in rows if r[0] == "user")))
    print("    assistant classes", dict(collections.Counter(acls(r[1]) for r in rows if r[0] == "assistant")))
    if tcol: ts = [r[2] for r in rows if r[2] is not None]; print("    msg ts range", min(ts) if ts else None, max(ts) if ts else None)
    for t in ("delivery_obligations",):
        if q("select 1 from sqlite_master where name=?", t): print(f"    {t} rows={q(f'select count(*) from {t}')[0][0]}")
    con.close()
TXT = re.compile(r"(?i)(inbound|message|msg=|text=|content|prompt|reply)")
def text_report(name, data):
    lines = data.decode("utf-8", "replace").splitlines(); syn = sum("F8-SYNTHETIC" in l for l in lines)
    mb = [l for l in lines if TXT.search(l) and "F8-SYNTHETIC" not in l and not any(s in l for s in SLASH)]
    osha = hashlib.sha256(chr(10).join(mb).encode()).hexdigest()[:12] if mb else "-"
    print(f"    {name}: lines={len(lines)} F8-SYNTHETIC={syn} other_message_shaped={len(mb)} other_sha={osha}")
    return mb
shapes = collections.Counter()
def shape(l): return re.sub(r"[0-9]", "9", re.sub(r"'[^']*'|\"[^\"]*\"", "<Q>", l))[:70]
# rollback quarantine (F8r2 R-1 output)
rb = os.path.join(B, "rollback-20261023T123157Z")
for dp, dn, fn in os.walk(rb):
    if dp.endswith(".hermes-gateway-dev"): dn[:] = []; continue
    if "state.db" in fn:
        d = os.path.join(SCR, "rb"); os.makedirs(d)
        for f in fn:
            if f.startswith("state.db"): shutil.copy2(os.path.join(dp, f), d)
        print(f"  rollback state.db dir={os.path.relpath(dp, B)}"); db_report("rollback-20261023T123157Z", d)
print("  rollback text files (HERMES_HOME conversation paths):")
for dp, dn, fn in os.walk(rb):
    if dp.endswith(".hermes-gateway-dev"): dn[:] = []; continue
    rel = os.path.relpath(dp, rb)
    if re.search(r"(^|/)\.?hermes-dev/(logs|sessions|pending_messages|runtime|state|gateway|cache|audio_cache|image_cache)", rel) or fn and any(f in ("channel_directory.json", "gateway_state.json") for f in fn):
        for f in sorted(fn):
            if f.startswith("state.db"): continue
            for l in text_report(os.path.join(rel, f), open(os.path.join(dp, f), "rb").read()): shapes[shape(l)] += 1
# upgrade-pre tar (F8r4 G-1)
for dp, dn, fn in os.walk(os.path.join(B, "upgrade-pre-20261023T123016Z")):
    for f in fn:
        if not f.endswith((".tar", ".tar.gz", ".tgz")): continue
        p = os.path.join(dp, f); d = os.path.join(SCR, "up"); os.makedirs(d, exist_ok=True)
        print(f"  tar {os.path.relpath(p, B)} sha={hashlib.sha256(open(p,'rb').read()).hexdigest()[:16]}")
        with tarfile.open(p) as tar:
            for m in tar:
                if not m.isfile(): continue
                base = m.name.rsplit("/", 1)[-1]
                if base.startswith("state.db"): open(os.path.join(d, base), "wb").write(tar.extractfile(m).read())
                elif re.search(r"hermes-dev/(logs|sessions|pending_messages|runtime|state|gateway|cache|audio_cache|image_cache)/|channel_directory.json|gateway_state.json", m.name):
                    for l in text_report(m.name, tar.extractfile(m).read()): shapes[shape(l)] += 1
        if os.path.exists(os.path.join(d, "state.db")): db_report("upgrade-pre-20261023T123016Z", d)
print("  journal copy:");
for l in text_report("journal-copy", open(JF, "rb").read()): shapes[shape(l)] += 1
print("  distinct shapes of non-F8-SYNTHETIC message-shaped lines (quoted text masked):")
for s, n in shapes.most_common(25): print(f"    x{n} {s}")
PY
echo "--- E. Core API conversation requests during F8r2 lifetime (2026-10-23 08:00-12:32 UTC)"
journalctl -u lilith-os-api-dev --since "2026-10-23 08:00:00" --until "2026-10-23 12:32:00" -o cat --no-pager 2>/dev/null > "$SCR/api.txt"
echo "  api journal lines=$(wc -l < $SCR/api.txt) conversation_lines=$(grep -c '/os/conversation' $SCR/api.txt)"
journalctl -u lilith-os-api-dev --since "2026-10-23 08:00:00" --until "2026-10-23 12:32:00" -o short-iso --no-pager 2>/dev/null \
  | grep '/os/conversation' | grep -oE '^[0-9T:+-]+|[0-9.]+:[0-9]+ - "[A-Z]+ /os/conversation[^"]*" [0-9]+' | paste - - | sed 's/^/   req /'
grep '/os/conversation' "$SCR/api.txt" | grep -oE '^[^ ]+ - |[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+' | sed 's/:[0-9]*$//' | sort | uniq -c | sed 's/^/   src /'
echo "--- F. live FORGET targets"
python3 - "$HH/state.db" <<'PY'
import sqlite3, sys, collections
c = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True)
print("  live state.db sessions", c.execute("select count(*) from sessions").fetchone()[0], "sources", sorted({r[0] for r in c.execute("select source from sessions")}),
      "messages", dict(collections.Counter(r[0] for r in c.execute("select role from messages"))),
      "user rows w/o F9C2-DEV-CANARY", c.execute("select count(*) from messages where role='user' and content not like '%F9C2-DEV-CANARY%'").fetchone()[0])
PY
for d in logs sessions pending_messages runtime state gateway cache audio_cache image_cache; do [[ -d $HH/$d ]] && printf '  live %s files=%s\n' $d "$(find $HH/$d -type f | wc -l)"; done
journalctl --namespace=hermes-gateway-dev -o short-iso --no-pager 2>/dev/null > "$SCR/lj.txt"
echo "  live namespace journal entries=$(wc -l < $SCR/lj.txt) first=$(head -1 $SCR/lj.txt | cut -c1-25) F8-SYNTHETIC=$(grep -c F8-SYNTHETIC $SCR/lj.txt) CANARY=$(grep -c F9C2-DEV-CANARY $SCR/lj.txt)"
echo "--- G. other conversation-bearing copies on host (outside the FORGET target set)"
find / -xdev \( -path /proc -o -path /sys -o -path /dev \) -prune -o \( -name 'state.db*' -o -name '*.hermes-gateway-dev' \) -print 2>/dev/null | grep -v "^$B/" | grep -v "^$HH/" | grep -v "^$SCR" | sed 's/^/  name-hit /'
grep -rlaE 'F8-SYNTHETIC|F9C2-DEV-CANARY' /var/backups /var/tmp /var/lib /var/log /home /root /tmp /srv /opt 2>/dev/null | grep -v "^$B/" | grep -v "^$HH/" | grep -v "^$SCR" | sed 's/^/  marker-hit /' | head -60
T1=$(treesum rollback-20261023T123157Z upgrade-pre-20261023T123016Z)
echo "--- H. backups tree digest before=$T0 after=$T1 $([[ $T0 == "$T1" ]] && echo UNCHANGED || echo CHANGED)"
echo "V1_SCOPE_DONE"
