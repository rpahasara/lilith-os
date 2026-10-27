#!/usr/bin/env bash
# F8 package build, stage 2 (local WSL): add the DEV home payload, F8 config/unit/scripts, the expected-dist list and
# the manifest; produce a deterministic tarball.
set -Eeuo pipefail
W=/root/f8hd; IN=$W/in; P=$W/build/pkg; T=$W/build/tmp; F=$W/pkgfiles
REL_ID=f293e72-f8r1
echo "$REL_ID" > $P/RELEASE_ID
rm -rf $P/home $P/systemd $P/bin $P/tests && mkdir -p $P/home $P/tests
rm -rf $T/home && mkdir -p $T/home && tar -xf $IN/hermes-home-dev.tar -C $T/home
(cd $T/home/hermes-home-dev && sha256sum -c --quiet <(sed 's/ \*/  /' $IN/hermes-home-dev.sha256 | grep -v -e '/config.yaml$' -e '/router.yaml$')) && echo "home payload = F7 hashes OK"
cp -a $T/home/hermes-home-dev/lilith_router $T/home/hermes-home-dev/plugins $P/home/
rm -f $P/home/lilith_router/router.yaml
cp $F/home/config.yaml $F/home/router.yaml $P/home/
cp -a $F/systemd $F/bin $P/
cp $IN/test_f7_offline.py $P/tests/
# G-4 reruns the accepted F7 suite unchanged, so it gets F7's own config (the F8 deltas are gated by verify/smoke).
mkdir -p $P/tests/f7-home && cp $T/home/hermes-home-dev/config.yaml $T/home/hermes-home-dev/lilith_router/router.yaml $P/tests/f7-home/
find $P -name __pycache__ -prune -exec rm -rf {} +
sed -i 's/\r$//' $P/bin/*.sh $P/bin/*.py $P/systemd/* $P/home/*.yaml
chmod 0755 $P/bin/*.sh
# Expected dists: resolve exactly as install.sh does, into a throwaway venv.
export UV_NO_CONFIG=1 UV_OFFLINE=1 UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never
rm -rf $T/trial && $P/uv/uv venv -q --python $P/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11 --no-project $T/trial
$P/uv/uv pip install -q --python $T/trial/bin/python --no-index --find-links $P/wheelhouse --require-hashes --no-deps -r $P/requirements.locked.txt
cp -a $P/src $T/trial-src && $P/uv/uv pip install -q --python $T/trial/bin/python --no-index --find-links $P/buildbackend --no-deps -e $T/trial-src
$P/uv/uv pip list --python $T/trial/bin/python --format freeze | LC_ALL=C sort > $P/EXPECTED-DISTS.txt
rm -rf $T/trial $T/trial-src
wc -l < $P/EXPECTED-DISTS.txt
(cd $P && find . -type f ! -name MANIFEST.sha256 -print | sed 's|^\./||' | LC_ALL=C sort | xargs -d '\n' sha256sum > MANIFEST.sha256)
wc -l < $P/MANIFEST.sha256
mkdir -p $W/out && rm -f $W/out/*
tar --sort=name --mtime='2026-10-23 00:00:00Z' --owner=0 --group=0 --numeric-owner --pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \
  -C $W/build --transform "s|^pkg|hermes-gateway-dev-$REL_ID|" -cf - pkg | gzip -9n > $W/out/hermes-gateway-dev-$REL_ID.tar.gz
(cd $W/out && sha256sum hermes-gateway-dev-$REL_ID.tar.gz | tee hermes-gateway-dev-$REL_ID.tar.gz.sha256)
du -sh $W/out/*.tar.gz $P
echo STAGE2_DONE
