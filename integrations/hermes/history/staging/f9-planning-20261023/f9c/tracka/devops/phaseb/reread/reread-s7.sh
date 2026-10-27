set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || exit 1
RUN=/var/tmp/f8/f9c2-run
echo "worker running: $(pgrep -fc 'bash /var/tmp/f8/f9c2-run/s7-worker.sh')"
sha256sum $RUN/s7-worker.out $RUN/s7-worker.sh $RUN/d2-forget.json /var/lib/hermes-forget/receipts/*.json /var/lib/hermes-forget/epochs/epochs.log /var/backups/hermes-gateway-dev/FORGET-TOMBSTONES/*.json | sed 's#  .*/#  #'
grep -c '^OK ' $RUN/s7-worker.out; grep -c STEP_FAIL $RUN/s7-worker.out; tail -1 $RUN/s7-worker.out
echo "gateway $(systemctl show hermes-gateway-dev -p MainPID,ActiveState,NRestarts --value | paste -sd/) intent=$(ls /var/lib/hermes-forget/intent | wc -l) marker=$([[ -e /var/lib/hermes-forget/in-progress ]] && echo present || echo absent)"
