#!/usr/bin/env bash
# F9-B LOCAL candidate build (WSL only; refused on lilith-dev-01). = the reviewed F8r4 stage-2 build
# (/root/f8r4/build-stage2-r4.sh) + the hash-checked F9-A overrides (patch_f9a.py) + the F9-B overrides on top
# (patch_f9b.py) + tests/test_f9a_offline.py and tests/test_f9b_offline.py.
# Release id f293e72-f9b1. Output /root/f9b/out. Never installed anywhere by this script.
set -Eeuo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo refused; exit 1; }
REL_ID=f293e72-f9b1
S1=/root/f8hd/build/pkg; IN=/root/f8hd/in; F8=/root/f8r4; W=/root/f9b; A=$W/src; F=$W/pkgfiles; O=$W/overrides
B=$W/build; P=$B/pkg; T=$B/tmp
rm -rf "$F" "$O" "$B"; mkdir -p "$P" "$T"
cp -a "$F8/pkgfiles" "$F"
python3 -I "$A/patch_f9a.py" "$F8/build/pkg" "$O"
python3 -I "$A/patch_f9b.py" "$F8/build/pkg" "$O"
# ---- F8r4 stage 2 (unchanged steps) ----
for d in src python uv wheelhouse buildbackend; do cp -a "$S1/$d" "$P/"; done
cp -a "$S1/requirements.locked.txt" "$P/"
echo "$REL_ID" > "$P/RELEASE_ID"
mkdir -p "$P/home" "$P/tests/f7-home" "$T/home" && tar -xf "$IN/hermes-home-dev.tar" -C "$T/home"
(cd "$T/home/hermes-home-dev" && sha256sum -c --quiet <(sed 's/ \*/  /' "$IN/hermes-home-dev.sha256" | grep -v -e '/config.yaml$' -e '/router.yaml$')) && echo "home payload = F7 hashes OK"
cp -a "$T/home/hermes-home-dev/lilith_router" "$T/home/hermes-home-dev/plugins" "$P/home/"
rm -f "$P/home/lilith_router/router.yaml"
[[ $(sha256sum < "$P/home/plugins/lilith_os/adapter.py" | cut -c1-64) == 76948218a23ed7e9b698ab07bd36a7a8a8d513abca1f02022f85669b0db24f54 ]]
cp "$F/home-overrides/plugins/lilith_os/adapter.py" "$P/home/plugins/lilith_os/adapter.py"
[[ $(sha256sum < "$P/home/plugins/lilith_os/adapter.py" | cut -c1-64) == 8c3b00552d83adb4e7d6c0af5a9aa081cb60d92879dc14db3baf71537ca32a4a ]] && echo "adapter override = reviewed B-4 patch 8c3b0055"
cp "$F/home/config.yaml" "$F/home/router.yaml" "$P/home/"
cp -a "$F/systemd" "$F/bin" "$F/dr5" "$F/gate" "$F/profiles" "$P/"
cp "$IN/test_f7_offline.py" "$P/tests/"
cp "$T/home/hermes-home-dev/config.yaml" "$T/home/hermes-home-dev/lilith_router/router.yaml" "$P/tests/f7-home/"
# ---- F9-A + F9-B overrides (each replaces exactly the F8r4 base file it was derived from) ----
f9() {  # <package path> <expected base sha>
  [[ $(sha256sum < "$P/$1" | cut -c1-64) == "$2" ]] || { echo "F9A_BUILD_FAIL base $1"; exit 1; }
  cp "$O/$1" "$P/$1"; echo "F9-A override $(sha256sum < "$P/$1" | cut -c1-16)  $1"; }
f9 src/gateway/run.py 2774eee5e585d80cbb45f5865f2718832c2ec86fdfddf8ead1f781e9b21c2553
f9 home/lilith_router/gateway_integration.py aef313140372497775b23b482a40c4f72a32de4a00506ad307ba1c541b6b9641
f9 home/config.yaml f6c43a07312757367eb1d47547ee683702b21c8fe0a6e68fb8353c5b79676256
f9 tests/test_f7_offline.py fd1610cb8a3b861b38fc1f91e3b30d3753efb826e5cc6539743f4f114da5f10a
f9 src/agent/turn_context.py 24f2f5429ed21c276e59af0f010f311caa83b389cd92521aac34971e872d9a6c
f9 src/agent/agent_runtime_helpers.py 9b088972cd0d7d9f6cedb50ae739ddfe71e50c99f3140ea36b7d5379e1c176b1
f9 profiles/operate/config.yaml e8fd4f25b67ab7d86719bef8491fabb0045d4b86fca9c6da0906481e2eba0c98
cp "$A/test_f9a_offline.py" "$A/test_f9b_offline.py" "$P/tests/"
# ---- F8r4 stage 2 (unchanged steps) ----
find "$P" -name __pycache__ -prune -exec rm -rf {} +
chmod 0755 "$P"/bin/*.sh
[[ $(sha256sum < "$P/dr5/deployer_authority_boundary_proof.sh" | cut -c1-64) == 9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43 ]]
[[ $(sha256sum < "$P/dr5/expected-dev-block-b9eb32c.txt" | cut -c1-64) == 7fe21378bb97f57aed3a6c60f6fc216e08d646f9da42d9c35feb7509f5468f1c ]]
for f in "$P"/bin/*.sh; do bash -n "$f"; done
for f in "$P"/bin/*.py "$P"/src/gateway/run.py "$P"/src/agent/turn_context.py "$P"/src/agent/agent_runtime_helpers.py "$P"/home/lilith_router/gateway_integration.py "$P"/tests/*.py; do
  "$P/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11" -I -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$f"; done
python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$P/gate/gate.json"
export UV_NO_CONFIG=1 UV_OFFLINE=1 UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never
"$P/uv/uv" venv -q --python "$P/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11" --no-project "$T/trial"
"$P/uv/uv" pip install -q --python "$T/trial/bin/python" --no-index --find-links "$P/wheelhouse" --require-hashes --no-deps -r "$P/requirements.locked.txt"
cp -a "$P/src" "$T/trial-src" && "$P/uv/uv" pip install -q --python "$T/trial/bin/python" --no-index --find-links "$P/buildbackend" --no-deps -e "$T/trial-src"
"$P/uv/uv" pip list --python "$T/trial/bin/python" --format freeze | LC_ALL=C sort > "$P/EXPECTED-DISTS.txt"
rm -rf "$T"
(cd "$P" && find . -type f ! -name MANIFEST.sha256 -print | sed 's|^\./||' | LC_ALL=C sort | xargs -d '\n' sha256sum > MANIFEST.sha256)
mkdir -p "$W/out" && rm -f "$W/out"/*
tar --sort=name --mtime='2026-10-23 00:00:00Z' --owner=0 --group=0 --numeric-owner \
  --pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \
  -C "$B" --transform "s|^pkg|hermes-gateway-dev-$REL_ID|" -cf - pkg | gzip -9n > "$W/out/hermes-gateway-dev-$REL_ID.tar.gz"
(cd "$W/out" && sha256sum "hermes-gateway-dev-$REL_ID.tar.gz" > "hermes-gateway-dev-$REL_ID.tar.gz.sha256")
echo "dists=$(wc -l < "$P/EXPECTED-DISTS.txt") manifest=$(wc -l < "$P/MANIFEST.sha256") manifest_sha=$(sha256sum < "$P/MANIFEST.sha256" | cut -c1-64)"
# Change-set proof: MANIFEST diff vs F8r4 = only the intended paths (+ RELEASE_ID, EXPECTED-DISTS self-name).
diff <(sed 's/^[0-9a-f]*  //' /root/f8r4/build/pkg/MANIFEST.sha256 | sort) <(sed 's/^[0-9a-f]*  //' "$P/MANIFEST.sha256" | sort) | sed 's/^/PATHSET /' || true
join -j 2 <(awk '{print $1, $2}' /root/f8r4/build/pkg/MANIFEST.sha256 | sort -k2) <(awk '{print $1, $2}' "$P/MANIFEST.sha256" | sort -k2) \
  | awk '$2 != $3 {print "CHANGED", $1}'
cat "$W/out/hermes-gateway-dev-$REL_ID.tar.gz.sha256"
