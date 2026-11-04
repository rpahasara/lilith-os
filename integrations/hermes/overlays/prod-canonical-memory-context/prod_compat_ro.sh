set -u
# PROD read-only compatibility check for the canonical-memory release (P3; PREPARED, NOT RUN). lilith-01 only.
# Reads hashes, counts and states; prints no message text, no key, no token, no personal memory. Writes nothing.
# Each line is `CHECK <name> <PASS|FAIL|INFO> <detail>`; the last line is `PROD_COMPAT_<PASS|FAIL> <failures>`.
H=/home/lilith/.hermes
LR=$H/lilith_router
F=0
c() { if [ "$2" = "$3" ]; then echo "CHECK $1 PASS ${2:0:16}"; else echo "CHECK $1 FAIL got=${2:0:16} want=${3:0:16}"; F=$((F+1)); fi; }
sh_() { sudo -n sha256sum "$1" 2>/dev/null | cut -c1-64; }
absent() { if sudo -n test -e "$2"; then echo "CHECK $1 FAIL present $2"; F=$((F+1)); else echo "CHECK $1 PASS absent"; fi; }
[ "$(hostname -s)" = lilith-01 ] || { echo "PROD_COMPAT_FAIL wrong-host"; exit 2; }
echo "HOST lilith-01 T $(date -u +%FT%TZ) BOOT $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
# 1. The exact bases the prepared overlay patches (Cutover 2 as deployed).
c router_gateway_integration "$(sh_ $LR/gateway_integration.py)" 99fe90649e316ef992db7c05575c19eafe56e703d505f44f39c5577903fe9587
c router_social_lean "$(sh_ $LR/social_lean.py)" 5c4c2d1fb113d53c43f34f7611c635a62209f2b41d74457887c835e540f6e410
c router_config "$(sh_ $LR/config.py)" 69e839ad2d48d1de805687a4f3f42fa85d0c24f8e3adaada88ede5087dc6df56
# Recorded only (prefix): the console adapter (expected 39fa27b9), Core API app (53dfae2a), Hermes run.py (31fef97d).
echo "CHECK lilith_os_adapter INFO $(sh_ $H/plugins/lilith_os/adapter.py | cut -c1-16)"
echo "CHECK core_api_app INFO $(sh_ $H/lilith-os/api/app.py | cut -c1-16)"
echo "CHECK hermes_run INFO $(sh_ $(readlink -f $H/hermes-agent)/gateway/run.py | cut -c1-16)"
# 2. The canonical-memory feature is not present (default OFF).
absent router_canonical_memory_module $LR/canonical_memory.py
absent router_canonical_memory_settings $LR/canonical_memory.json
absent deployment_selection /etc/lilith-authority-dev/deployment.json
absent authority_release /opt/lilith-authority-dev
absent context_socket /run/lilith-first-memory-context.sock
absent owner_channel_grant /etc/lilith-first-memory-dev/hermes-owner-channel.json
# 3. The PROD stores the release migrates later: their present shape (counts only).
sudo -n -u lilith python3 -I - <<'PY'
import sqlite3
for name, table in (("cognitive_memory.db", "memory_item"), ("cognitive_memory.db", "memory_admission"),
                    ("privacy_governance.db", None), ("lilith.db", None)):
    path = "/home/lilith/.hermes/lilith-os/data/" + name
    try:
        c = sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=5)
        tables = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
        n = c.execute('select count(*) from "%s"' % table).fetchone()[0] if table and table in tables else "-"
        ok = c.execute("pragma integrity_check").fetchone()[0]
        print("CHECK db_%s INFO tables=%d %s=%s integrity=%s" % (name, len(tables), table or "rows", n, ok))
    except Exception as e:
        print("CHECK db_%s FAIL %s" % (name, type(e).__name__))
PY
# 4. Telegram routing prerequisites: an owner allowlist exists (count only; the id itself is not printed).
N=$(sudo -n grep -cE "^\s*(allowed_users|allowed_user_ids|allow_from)\s*:" $H/config.yaml 2>/dev/null)
echo "CHECK telegram_allowlist_keys INFO count=${N:-0}"
# 5. Services that must stay untouched.
for u in hermes-gateway lilith-os-api; do echo "CHECK unit_$u INFO $(systemctl show $u -p ActiveState -p MainPID -p NRestarts | LC_ALL=C sort | paste -sd' ')"; done
echo "CHECK disk_root INFO free_mb=$(df -Pm / | awk 'NR==2{print $4}')"
[ "$F" = 0 ] && echo "PROD_COMPAT_PASS 0" || echo "PROD_COMPAT_FAIL $F"
