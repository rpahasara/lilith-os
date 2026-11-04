set -u
# PROD read-only integration audit for canonical memory (PREPARED, NOT RUN; one separate owner approval). lilith-01 only.
# Record: docs/architecture/canonical-memory-prod-integration-plan.md §6. Reads metadata, hashes, counts, versions and
# schema TEXT only; prints no message text, memory content, key, token, credential or Telegram id. Writes nothing.
# Lines are `A <section> <name> <value>`; the last line is `PROD_INTEGRATION_AUDIT_DONE`.
H=/home/lilith/.hermes
LR=$H/lilith_router
D=$H/lilith-os/data
sh_() { sudo -n sha256sum "$1" 2>/dev/null | cut -c1-64; }
a() { echo "A $1 $2 $3"; }
[ "$(hostname -s)" = lilith-01 ] || { echo "PROD_INTEGRATION_AUDIT_REFUSED wrong-host"; exit 2; }
a host time "$(date -u +%FT%TZ)"
a host boot "$(cut -c1-8 /proc/sys/kernel/random/boot_id)"
a host machine_id_sha256 "$(sha256sum < /etc/machine-id | cut -c1-64)"   # the raw id is read only in the pin step
a host os "$(. /etc/os-release && echo "$ID-$VERSION_ID")"
a host kernel "$(uname -r)"
a host system_python "$(/usr/bin/python3 -V 2>&1 | tr ' ' '-')"
a host glibc "$(ldd --version 2>&1 | head -1 | awk '{print $NF}')"
a host nproc "$(nproc)"
a host mem_mb "$(free -m | awk '/^Mem:/{print "total="$2",available="$7}')"
a host disk_mb "$(df -Pm / | awk 'NR==2{print "used="$3",free="$4}')"
# 1. Lilith identity and router files (hash only).
for f in SOUL.md memories/USER.md memories/MEMORY.md config.yaml lilith_router/router.yaml; do
  a identity "$f" "$(sh_ $H/$f)"; done
for f in gateway_integration social_lean config state classifier policy social_guard world_context; do
  a router "$f.py" "$(sh_ $LR/$f.py)"; done
a router canonical_memory_module "$(sudo -n test -e $LR/canonical_memory.py && echo PRESENT || echo absent)"
a hermes run_py "$(sh_ $(readlink -f $H/hermes-agent)/gateway/run.py)"
a hermes commit "$(sudo -n -u lilith git -C $H/hermes-agent rev-parse HEAD 2>/dev/null)"
a hermes venv_python "$(sudo -n $H/hermes-agent/venv/bin/python -V 2>&1 | tr ' ' '-')"
a console adapter "$(sh_ $H/plugins/lilith_os/adapter.py)"
a core_api app_py "$(sh_ $H/lilith-os/api/app.py)"
# 2. Stores (shape only: tables, row counts, integrity, schema text digest; WAL size decides immutable vs ro).
sudo -n -u lilith python3 -I - "$D" "$H" <<'PY'
import hashlib, os, sqlite3, sys
d, h = sys.argv[1], sys.argv[2]
for path in (d + "/cognitive_memory.db", d + "/privacy_governance.db", d + "/lilith.db", h + "/state.db"):
    name = os.path.basename(path)
    if not os.path.exists(path):
        print("A store %s absent" % name); continue
    wal = path + "-wal"
    walsize = os.path.getsize(wal) if os.path.exists(wal) else 0
    mode = "ro&immutable=1" if walsize == 0 else "ro"
    try:
        c = sqlite3.connect("file:%s?mode=%s" % (path, mode), uri=True, timeout=5)
        rows = c.execute("select type, name, coalesce(sql,'') from sqlite_master order by type, name").fetchall()
        schema = hashlib.sha256("\n".join("%s|%s|%s" % r for r in rows).encode()).hexdigest()
        tables = [r[1] for r in rows if r[0] == "table"]
        counts = ",".join("%s=%d" % (t, c.execute('select count(*) from "%s"' % t).fetchone()[0]) for t in tables)
        print("A store %s bytes=%d wal=%d schema_sha256=%s integrity=%s" % (
            name, os.path.getsize(path), walsize, schema, c.execute("pragma quick_check").fetchone()[0]))
        print("A store_counts %s %s" % (name, counts))
    except Exception as e:
        print("A store %s ERROR %s" % (name, type(e).__name__))
PY
for k in actor_authority.key privacy_authority.key; do
  a secret_meta "$k" "$(sudo -n stat -c '%s:%a:%U' $D/$k 2>/dev/null || echo absent)"; done   # metadata only
# 3. Canonical-memory components that must be absent before the inert install.
for p in /etc/lilith-authority-dev /opt/lilith-authority-dev /opt/lilith-first-memory-dev /etc/lilith-first-memory-dev \
         /usr/local/lib/lilith-canonical-context /var/lib/lilith-authority-dev /run/lilith-privacy-fresh; do
  a absent "$p" "$(sudo -n test -e $p && echo PRESENT || echo absent)"; done
for n in lilith-authority lilith-witness lilith-broker lilith-forget; do
  a principal "$n" "$(getent passwd $n >/dev/null && echo user || echo no-user) $(getent group $n >/dev/null && echo group || echo no-group)"; done
for id in 985 995; do a uid_gid_in_use "$id" "$(getent passwd $id | cut -d: -f1)/$(getent group $id | cut -d: -f1)"; done
# 4. Services and channels (state only).
for u in hermes-gateway lilith-os-api lilith-morning-brief-watcher.timer lilith-career-watcher.timer lilith-meeting-prep-watcher.timer lilith-gmail-watcher.timer; do
  a unit "$u" "$(systemctl show $u -p ActiveState -p SubState -p MainPID -p NRestarts --value 2>/dev/null | paste -sd'|')"; done
a unit failed "$(systemctl list-units --state=failed --no-legend --plain | awk '{print $1}' | paste -sd,)"
a channels telegram_allowlist_keys "$(sudo -n grep -cE '^\s*(allowed_users|allowed_user_ids|allow_from)\s*:' $H/config.yaml 2>/dev/null || echo 0)"
# 5. Recovery: snapshot schedule attachment is read from the workstation (gcloud), not here.
a recovery unattended_upgrades "$(systemctl is-enabled unattended-upgrades 2>/dev/null)"
echo PROD_INTEGRATION_AUDIT_DONE
