#!/usr/bin/env bash
# F8r3 package build, stage 2 (local WSL). Reuses the verified stage-1 inputs unchanged (upstream src + overlay, uv,
# CPython 3.11.16, hash-locked wheelhouse, setuptools); F7 home payload with ONE reviewed override (lilith_os adapter,
# B-4); F8r3 config/gate/units/scripts/profiles; deterministic tarball.
set -Eeuo pipefail
REL_ID=f293e72-f8r3
S1=/root/f8hd/build/pkg; IN=/root/f8hd/in; F=/root/f8r3/pkgfiles; W=/root/f8r3; B=$W/build; P=$B/pkg; T=$B/tmp
rm -rf "$B"; mkdir -p "$P" "$T"
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
find "$P" -name __pycache__ -prune -exec rm -rf {} +
chmod 0755 "$P"/bin/*.sh
[[ $(sha256sum < "$P/dr5/deployer_authority_boundary_proof.sh" | cut -c1-64) == 9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43 ]]
[[ $(sha256sum < "$P/dr5/expected-dev-block-b9eb32c.txt" | cut -c1-64) == 7fe21378bb97f57aed3a6c60f6fc216e08d646f9da42d9c35feb7509f5468f1c ]]
for f in "$P"/bin/*.sh; do bash -n "$f"; done
for f in "$P"/bin/*.py; do "$P/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11" -I -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$f"; done
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
cat "$W/out/hermes-gateway-dev-$REL_ID.tar.gz.sha256"
