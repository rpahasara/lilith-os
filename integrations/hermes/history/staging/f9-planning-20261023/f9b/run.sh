#!/usr/bin/env bash
# MIRROR ONLY: build the F9-B candidate twice (reproducibility), then run the F9-B rehearsal on it.
set -u
[[ $(hostname) != lilith-dev-01 ]] || exit 1
cd /root/f9b/src && sed -i 's/\r$//' ./*.sh ./*.py && bash -n f9b-rehearse.sh && bash -n build-f9b.sh || exit 1
python3 -m py_compile patch_f9b.py test_f9b_offline.py && rm -rf __pycache__ || exit 1
sha256sum patch_f9a.py patch_f9b.py test_f9a_offline.py test_f9b_offline.py build-f9b.sh f9b-rehearse.sh
bash build-f9b.sh > /root/f9b/build1.log 2>&1 || { echo BUILD1_FAIL; tail -8 /root/f9b/build1.log; exit 1; }
s1=$(cut -c1-64 /root/f9b/out/hermes-gateway-dev-f293e72-f9b1.tar.gz.sha256)
bash build-f9b.sh > /root/f9b/build2.log 2>&1 || { echo BUILD2_FAIL; tail -8 /root/f9b/build2.log; exit 1; }
s2=$(cut -c1-64 /root/f9b/out/hermes-gateway-dev-f293e72-f9b1.tar.gz.sha256)
echo "build1=$s1"; echo "build2=$s2"; [[ $s1 == "$s2" ]] && echo REPRODUCIBLE || echo NOT_REPRODUCIBLE
grep -E '^(F9-A override|dists=|PATHSET|CHANGED [^p])|^[0-9a-f]{64}  (src|home|tests|profiles)/' /root/f9b/build2.log
bash f9b-rehearse.sh > /root/f9b/rehearse.log 2>&1; echo "rc=$?"
cut -c1-400 /root/f9b/f9b-rehearsal.tsv
tail -1 /root/f9b/rehearse.log
