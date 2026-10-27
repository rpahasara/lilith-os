#!/usr/bin/env bash
# STRICTLY READ-ONLY provenance/inventory pass on lilith-01 (owner-approved, one-time).
# No writes: git uses --no-optional-locks, pip/python write no bytecode or caches. Never prints secret values.
set -u
export PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 GIT_OPTIONAL_LOCKS=0
H=/home/lilith/.hermes
HA=$H/hermes-agent
L() { sudo -n -u lilith "$@"; }
mask() { sed -E 's#(://)[^/@ ]+@#\1<redacted>@#g; s/((TOKEN|SECRET|KEY|PASS|PASSWORD|CREDENTIAL|AUTH)[A-Za-z0-9_]*=)[^ ]*/\1<redacted>/Ig'; }
echo "== HOST"; hostname
echo "== HERMES-AGENT TOP LEVEL"; L ls -la "$HA" 2>&1 | awk 'NR>1{print $1, $5, $9}'
echo "== GIT"
if L test -e "$HA/.git"; then
  L git -C "$HA" --no-optional-locks rev-parse HEAD 2>&1
  L git -C "$HA" --no-optional-locks describe --tags --always --dirty 2>&1
  L git -C "$HA" --no-optional-locks log -1 --format='%H %cI %s' 2>&1 | cut -c1-200
  L git -C "$HA" --no-optional-locks remote -v 2>&1 | mask
  L git -C "$HA" --no-optional-locks branch --show-current 2>&1
  echo "-- status (porcelain, tracked+untracked, no ignored)"
  L git -C "$HA" --no-optional-locks status --porcelain=v1 --untracked-files=normal 2>&1 | head -80
  echo "-- diff --stat vs HEAD"
  L git -C "$HA" --no-optional-locks diff --stat HEAD 2>&1 | tail -40
else
  echo NO_GIT_DIR
fi
echo "== PACKAGE METADATA"
for f in pyproject.toml setup.py setup.cfg package.json VERSION version.txt; do
  if L test -f "$HA/$f"; then echo "-- $f"; L grep -nE '^\s*(name|version|requires-python|"name"|"version")\s*[=:]' "$HA/$f" 2>&1 | head -8; fi
done
L grep -rhoE '__version__\s*=\s*["'"'"'][^"'"'"']+' "$HA/hermes_cli" 2>/dev/null | head -3
echo "== VENV"
L test -x "$HA/venv/bin/python" && L "$HA/venv/bin/python" -V 2>&1 || echo NO_VENV_PYTHON
echo "-- pip freeze"
L "$HA/venv/bin/python" -m pip freeze --disable-pip-version-check 2>&1 | mask
echo "== GATEWAY BACKUPS"; L ls -la "$HA/gateway/" 2>&1 | grep -E 'run\.py' | awk '{print $5, $6, $7, $8, $9}'
echo "== TOOL/AGENT BACKUPS"; for d in tools agent hermes_cli; do L ls -la "$HA/$d/" 2>&1 | grep -E '\.bak|\.orig' | awk -v d="$d" '{print d"/"$9, $5}'; done
echo "== LILITH_ROUTER LISTING (names, sizes)"; L ls -la "$H/lilith_router" 2>&1 | awk 'NR>1{print $1, $5, $9}'
echo "-- tests"; L ls -la "$H/lilith_router/tests" 2>&1 | awk 'NR>1{print $5, $9}'
echo "== PLUGINS LISTING"; L find "$H/plugins" -maxdepth 3 -printf '%M %s %p\n' 2>&1 | grep -v __pycache__
echo "== HERMES_HOME TOP LEVEL (names only)"; L ls -la "$H" 2>&1 | awk 'NR>1{print $1, $9}'
echo "== ENV KEY NAMES ONLY"
for f in "$H/.env" "$H/groq.env"; do echo "-- $f"; L test -f "$f" && L sed -n 's/^\(export \)\{0,1\}\([A-Za-z0-9_]*\)=.*/\2/p' "$f" | sort -u || echo absent; done
echo "== SYSTEMD UNIT hermes-gateway (Environment values masked)"
systemctl cat hermes-gateway.service 2>&1 | mask | sed -E 's/^(Environment=[A-Za-z0-9_]+=).*/\1<value-redacted>/'
systemctl show hermes-gateway.service -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager
echo "-- gateway RSS/CPU"; P=$(systemctl show hermes-gateway.service -p MainPID --value); [ -n "$P" ] && ps -o pid,rss,vsz,pcpu,etime -p "$P" 2>&1
echo "== DONE"
