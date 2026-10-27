#!/usr/bin/env bash
# STRICTLY READ-ONLY pass 2 on lilith-01 (owner-approved): metadata, sha256 manifest, and a sanitized source export
# streamed to stdout. Nothing is written on the host. Excludes logs, CURRENT_STATE.md, backups, caches, keys,
# .env values, state.db, memories and SOUL.md.
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
echo "== GIT DIFF HEAD (local patch to upstream)"
echo "@@BEGIN_DIFF@@"
L git -C "$HA" --no-optional-locks diff HEAD --binary
echo "@@END_DIFF@@"
echo "== SANITIZED EXPORT (tar.gz base64)"
SAN=$(cat <<'PY'
import re, sys, yaml
SENSITIVE = re.compile(r"(token|secret|password|passwd|api[_-]?key|apikey|auth|credential|cookie|webhook|client_id|private)", re.I)
def walk(v, key=""):
    if isinstance(v, dict):
        return {k: (("<redacted>" if SENSITIVE.search(str(k)) and not isinstance(val, (dict, list, bool)) else walk(val, k))) for k, val in v.items()}
    if isinstance(v, list):
        return [walk(x, key) for x in v]
    if isinstance(v, str):
        if re.search(r"\d{15,}", v) or re.search(r"[A-Za-z0-9_\-]{32,}", v) or "@" in v:
            return re.sub(r"\d{15,}", "<id-redacted>", re.sub(r"[A-Za-z0-9_\-]{32,}", "<long-value-redacted>", re.sub(r"\S+@\S+", "<email-redacted>", v)))
    if isinstance(v, int) and not isinstance(v, bool) and v >= 10**14:
        return "<id-redacted>"
    return v
print(yaml.safe_dump(walk(yaml.safe_load(sys.stdin)), sort_keys=False, allow_unicode=True))
PY
)
STAGE_LIST=$(L bash -c "cd '$H' && ls lilith_router/*.py lilith_router/tests/*.py plugins/lilith_os/plugin.yaml plugins/lilith_os/__init__.py plugins/lilith_os/adapter.py plugins/model-providers/groq/plugin.yaml plugins/model-providers/groq/__init__.py hermes-agent/tools/legacy_canonical_containment.py")
echo "@@BEGIN_TAR@@"
{
  L tar -C "$H" -cf - $STAGE_LIST
} | python3 - "$SAN" <<'PY'
import io, sys, tarfile, base64, subprocess
san_code = sys.argv[1]
raw = sys.stdin.buffer.read()
out = io.BytesIO()
with tarfile.open(fileobj=io.BytesIO(raw)) as src, tarfile.open(fileobj=out, mode="w:gz") as dst:
    for m in src.getmembers():
        data = src.extractfile(m).read() if m.isfile() else None
        dst.addfile(m, io.BytesIO(data) if data is not None else None)
    for name in ("lilith_router/router.yaml", "config.yaml"):
        r = subprocess.run(["sudo", "-n", "-u", "lilith", "/home/lilith/.hermes/hermes-agent/venv/bin/python", "-c", san_code],
                           input=subprocess.run(["sudo", "-n", "-u", "lilith", "cat", "/home/lilith/.hermes/" + name],
                                                capture_output=True).stdout, capture_output=True)
        body = r.stdout if r.returncode == 0 else ("SANITIZE_FAILED: " + r.stderr.decode()[:200]).encode()
        info = tarfile.TarInfo("sanitized/" + name.replace("/", "__"))
        info.size = len(body)
        dst.addfile(info, io.BytesIO(body))
sys.stdout.write(base64.b64encode(out.getvalue()).decode())
PY
echo
echo "@@END_TAR@@"
echo "== DONE"
