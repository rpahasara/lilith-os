#!/usr/bin/env bash
# MIRROR ONLY: F9-B review diffs (F9-A -> F9-B and F8r4 -> F9-B), evidence archive, inventories.
set -u
[[ $(hostname) != lilith-dev-01 ]] || exit 1
O=/root/f9b/review; rm -rf $O; mkdir -p $O
F8=/root/f8r4/build/pkg; A=/root/f9a/build/pkg; N=/root/f9b/build/pkg
for f in src/gateway/run.py src/agent/turn_context.py src/agent/agent_runtime_helpers.py profiles/operate/config.yaml; do
  diff -u --label "f9a1/$f" --label "f9b1/$f" $A/$f $N/$f >> $O/F9B-SOURCE-vs-F9A.diff; done
for f in src/gateway/run.py src/agent/turn_context.py src/agent/agent_runtime_helpers.py home/lilith_router/gateway_integration.py home/config.yaml profiles/operate/config.yaml tests/test_f7_offline.py; do
  diff -u --label "f8r4/$f" --label "f9b1/$f" $F8/$f $N/$f >> $O/F9B-SOURCE-vs-F8R4.diff; done
cp $N/tests/test_f9b_offline.py $O/; cp /root/f9b/out/*.sha256 $O/; cp $N/MANIFEST.sha256 $O/MANIFEST-f9b1.sha256
cp /root/f9b/ev/inventory-hermes-home.txt /root/f9b/ev/inventory-backups.txt $O/
tar -C /root/f9b -czf $O/f9b-rehearsal-evidence.tgz f9b-rehearsal.tsv rehearse.log build1.log build2.log ev
(cd $O && sha256sum * > SHA256SUMS && cat SHA256SUMS)
echo "changed lines vs F9-A: $(grep -c '^[-+][^-+]' $O/F9B-SOURCE-vs-F9A.diff)"
