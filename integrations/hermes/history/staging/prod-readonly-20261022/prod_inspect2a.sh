#!/usr/bin/env bash
# STRICTLY READ-ONLY pass 2a on lilith-01 (owner-approved): install metadata, installed versions and a sha256
# manifest only. No file contents are exported. Nothing is written on the host.
set -u
export PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0
H=/home/lilith/.hermes
HA=$H/hermes-agent
R=$H/lilith_router
L() { sudo -n -u lilith "$@"; }
cd /tmp || exit 1
echo "== INSTALL METADATA"
echo -n ".install_method: "; L cat "$HA/.install_method"; echo
echo -n ".python-version: "; L cat "$HA/.python-version"; echo
L cat "$HA/.bytecode-fingerprint" 2>/dev/null | head -c 120; echo
for b in uv; do printf '%s: ' "$b"; L bash -lc "command -v $b" 2>/dev/null || echo none; done
L sha256sum "$HA/uv.lock" "$HA/pyproject.toml" "$HA/package-lock.json" 2>&1 | sed "s#$HA/##"
echo "-- installed dists (from venv metadata, name==version)"
L "$HA/venv/bin/python" - <<'PY' 2>&1 | head -400
import importlib.metadata as m
for d in sorted(m.distributions(), key=lambda d: (d.metadata.get("Name") or "").lower()):
    print(f"{d.metadata.get('Name')}=={d.version}")
PY
echo "== ROUTER SUBDIRS (names only)"
for d in tools _patched checkpoints; do echo "-- $d"; L ls -la "$R/$d" 2>&1 | awk 'NR>3{print $5, $9}'; done
echo "== SHA256 MANIFEST"
echo "-- hermes-agent modified/new (current)"
L sha256sum "$HA/gateway/run.py" "$HA/agent/background_review.py" "$HA/tools/memory_tool.py" \
  "$HA/tools/skill_manager_tool.py" "$HA/tools/write_approval.py" "$HA/tools/legacy_canonical_containment.py" \
  "$HA/hermes_cli/personality.py" 2>&1 | sed "s#$HA/##"
echo "-- hermes-agent HEAD versions of modified files"
for f in gateway/run.py agent/background_review.py tools/memory_tool.py tools/skill_manager_tool.py tools/write_approval.py; do
  printf '%s  HEAD:%s\n' "$(L git -C "$HA" --no-optional-locks show "HEAD:$f" | sha256sum | cut -d' ' -f1)" "$f"
done
echo "-- run.py backups"; L sha256sum "$HA"/gateway/run.py.bak.* 2>&1 | sed "s#$HA/##"
echo "-- lilith_router (current .py/.yaml, tests)"
L bash -c "cd '$R' && sha256sum *.py router.yaml tests/*.py" 2>&1
echo "-- plugins"; L bash -c "cd '$H/plugins' && sha256sum lilith_os/* model-providers/groq/*" 2>&1
echo "-- config + unit"; L sha256sum "$H/config.yaml" 2>&1 | sed "s#$H/##"; sha256sum /etc/systemd/system/hermes-gateway.service
echo "== DONE"
