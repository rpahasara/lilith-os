STEP=v3-residual
# READ-ONLY follow-up: classify delivery_obligations reply rows and the remaining unclassified log/journal lines of the
# two F8r2 backups. Prints classes and masked shapes only (quoted text and words after the logger prefix masked).
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST $(hostname)"; exit 1; }
[[ $(id -u) -eq 0 ]] || { echo "NOT ROOT"; exit 1; }
RUN=/var/tmp/f8/f9c2-run; [[ -d $RUN ]] || { echo "NO RUN DIR"; exit 1; }
exec > >(tee -a "$RUN/${STEP}.out") 2>&1
B=/var/backups/hermes-gateway-dev; R=/opt/hermes-gateway-dev/current
PY=$R/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11
SCR=$(mktemp -d /dev/shm/f9scope.XXXXXX); chmod 700 "$SCR"; trap 'rm -rf "$SCR"; echo "scratch removed: $([[ -e $SCR ]] && echo NO || echo yes)"' EXIT
echo "=== ${STEP} $(date -u +%Y-%m-%dT%H:%M:%SZ)"
H0=$(sha256sum $B/upgrade-pre-20261023T123016Z/hermes-dev-home.tar $B/rollback-20261023T123157Z/hermes-dev/state.db* | sha256sum | cut -c1-16)
(cd $B/upgrade-pre-20261023T123016Z && sha256sum -c --quiet SHA256SUMS && echo "  upgrade-pre SHA256SUMS: OK ($(wc -l < SHA256SUMS) lines)")
JD=$(find $B/rollback-20261023T123157Z -xdev -type d -name '*.hermes-gateway-dev' | head -1)
journalctl --directory="$JD" -o json --no-pager > "$SCR/j.json" 2>/dev/null
cp $B/rollback-20261023T123157Z/hermes-dev/state.db* "$SCR/"
$PY -I -B - "$SCR" "$B/rollback-20261023T123157Z/hermes-dev" <<'PY'
import sys, os, re, sqlite3, json, collections
S, H = sys.argv[1:3]
c = sqlite3.connect(os.path.join(S, "state.db"))
cols = [r[1] for r in c.execute("pragma table_info(delivery_obligations)")]
print("  delivery_obligations columns", cols)
def cls(v):
    if not isinstance(v, str): return type(v).__name__
    l = v.lower()
    for k in ("provider authentication failed", "admin-only", "unknown command"):
        if k in l: return "TEXT:" + k
    return "str(len=%d)" % len(v) if len(v) > 40 else "short:" + re.sub(r"[A-Za-z]", "a", re.sub(r"[0-9]", "9", v))
for row in c.execute("select * from delivery_obligations"):
    print("    row", {k: cls(v) for k, v in zip(cols, row)})
for t in [r[0] for r in c.execute("select name from sqlite_master where type='table'")]:
    n = c.execute(f'select count(*) from "{t}"').fetchone()[0]
    if n: print(f"    nonempty table {t} rows={n}")
SLASH = ("Unrecognized slash command",)
def mask(l): return re.sub(r"\b[a-z]{2,}\b", "w", re.sub(r"'[^']*'|\"[^\"]*\"", "<Q>", re.sub(r"[0-9]", "9", l)))[:150]
for f in ("logs/gateway.log", "logs/agent.log", "logs/errors.log"):
    lines = open(os.path.join(H, f), encoding="utf-8", errors="replace").read().splitlines()
    syn = [l for l in lines if "F8-SYNTHETIC" in l]
    print(f"  {f}: F8-SYNTHETIC lines -> masked logger prefix:", sorted({mask(l.split('F8-SYNTHETIC')[0])[-60:] for l in syn}))
    odd = [l for l in lines if re.search(r"(?i)(inbound|message|msg=|text=|content|prompt|reply)", l) and "F8-SYNTHETIC" not in l and not any(s in l for s in SLASH)]
    for l in odd: print(f"    other: {mask(l)}")
J = [json.loads(x) for x in open(os.path.join(S, "j.json"))]
print("  journal copy entries", len(J), "units", dict(collections.Counter(e.get("_SYSTEMD_UNIT", e.get("UNIT", "?")) for e in J)))
for e in J:
    m = e.get("MESSAGE", "")
    if isinstance(m, list): m = bytes(m).decode("utf-8", "replace")
    print(f"    {e.get('SYSLOG_IDENTIFIER','?')[:28]:28} {mask(m)[:110]}")
PY
echo "  markers in backup root outside the 3 scan-target dirs (not erased by FORGET):"
grep -rlaE 'F8-SYNTHETIC|F9C2-DEV-CANARY|f8b-s[0-9]' $B --exclude-dir=rollback-20261023T123157Z --exclude-dir=upgrade-pre-20261023T123016Z --exclude-dir=rollback-20261025T082553Z 2>/dev/null | sed "s#^$B/#    #"
H1=$(sha256sum $B/upgrade-pre-20261023T123016Z/hermes-dev-home.tar $B/rollback-20261023T123157Z/hermes-dev/state.db* | sha256sum | cut -c1-16)
echo "  originals digest before=$H0 after=$H1 $([[ $H0 == "$H1" ]] && echo UNCHANGED || echo CHANGED)"
echo "V3_DONE"
