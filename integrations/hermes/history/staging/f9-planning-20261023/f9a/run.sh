#!/usr/bin/env bash
# MIRROR ONLY: build the F9-A candidate TWICE (reproducibility check), then run the F9-A rehearsal on it.
set -u
[[ $(hostname) != lilith-dev-01 ]] || exit 1
cd /root/f9a/src-f9a && sed -i 's/\r$//' ./*.sh ./*.py && bash -n f9a-rehearse.sh && bash -n build-f9a.sh || exit 1
sha256sum patch_f9a.py test_f9a_offline.py build-f9a.sh f9a-rehearse.sh
bash build-f9a.sh > /root/f9a/build1.log 2>&1 || { echo BUILD1_FAIL; tail -5 /root/f9a/build1.log; exit 1; }
s1=$(cut -c1-64 /root/f9a/out/hermes-gateway-dev-f293e72-f9a1.tar.gz.sha256)
bash build-f9a.sh > /root/f9a/build2.log 2>&1 || { echo BUILD2_FAIL; tail -5 /root/f9a/build2.log; exit 1; }
s2=$(cut -c1-64 /root/f9a/out/hermes-gateway-dev-f293e72-f9a1.tar.gz.sha256)
echo "build1=$s1"; echo "build2=$s2"; [[ $s1 == "$s2" ]] && echo REPRODUCIBLE || echo NOT_REPRODUCIBLE
grep -E '^(F9-A override|dists=|PATHSET|CHANGED [^p])' /root/f9a/build2.log
echo "stdlib pyc differing from F8r4: $(grep -c '^CHANGED python/' /root/f9a/build2.log)"
bash f9a-rehearse.sh > /root/f9a/rehearse.log 2>&1; echo "rc=$?"
cut -c1-360 /root/f9a/f9a-rehearsal.tsv
tail -1 /root/f9a/rehearse.log
