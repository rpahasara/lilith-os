#!/usr/bin/env bash
# MIRROR ONLY: produce review diffs (F8r4 base -> F9-A) and an evidence archive for the local staging folder.
set -u
[[ $(hostname) != lilith-dev-01 ]] || exit 1
O=/root/f9a/review; rm -rf $O; mkdir -p $O
B=/root/f8r4/build/pkg; N=/root/f9a/build/pkg
for f in src/gateway/run.py home/lilith_router/gateway_integration.py home/config.yaml tests/test_f7_offline.py; do
  diff -u --label "f8r4/$f" --label "f9a1/$f" $B/$f $N/$f >> $O/F9A-SOURCE.diff; done
cp $N/tests/test_f9a_offline.py $O/
cp /root/f9a/out/*.sha256 $O/
cp $N/MANIFEST.sha256 $O/MANIFEST-f9a1.sha256
tar -C /root/f9a -czf $O/f9a-rehearsal-evidence.tgz f9a-rehearsal.tsv rehearse.log build1.log build2.log ev
(cd $O && sha256sum * > SHA256SUMS && cat SHA256SUMS)
grep -c '^[-+][^-+]' $O/F9A-SOURCE.diff
