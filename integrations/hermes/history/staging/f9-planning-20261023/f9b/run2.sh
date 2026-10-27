#!/usr/bin/env bash
# MIRROR ONLY: re-run the F9-B rehearsal on the already-built candidate (no rebuild); print its table.
set -u
[[ $(hostname) != lilith-dev-01 ]] || exit 1
cd /root/f9b/src && sed -i 's/\r$//' f9b-rehearse.sh && bash -n f9b-rehearse.sh || exit 1
sha256sum f9b-rehearse.sh; cat /root/f9b/out/*.sha256
bash f9b-rehearse.sh > /root/f9b/rehearse.log 2>&1; echo "rc=$?"
cut -c1-400 /root/f9b/f9b-rehearsal.tsv
tail -1 /root/f9b/rehearse.log
