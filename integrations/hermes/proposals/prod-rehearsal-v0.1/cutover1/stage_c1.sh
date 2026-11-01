set -u
# Places the guest files, root-owned, after checking each digest (PREPARED, NOT APPROVED, NOT RUN). Runs nothing else.
#   sudo -n bash /tmp/c1-stage_c1.sh <guest_c1.sh sha256> <live_compare.py sha256> <rehearsal_compare.py sha256>
ROOT=${C1_ROOT:-}
IN=${ROOT}/var/tmp/c1
T=${ROOT}/tmp
check() { [ "$(sha256sum "${T}/c1-$1" | cut -c1-64)" = "$2" ] || { echo "STAGE_FAILED $1"; exit 1; }; }
check guest_c1.sh "${1:-}"
check live_compare.py "${2:-}"
check rehearsal_compare.py "${3:-}"
install -d -m 0755 "${IN}"
for f in guest_c1.sh live_compare.py rehearsal_compare.py; do
  install -o "${C1_OWNER:-root}" -g "${C1_OWNER:-root}" -m 0644 "${T}/c1-${f}" "${IN}/${f}" && rm -f "${T}/c1-${f}"
done
rm -f "${T}/c1-stage_c1.sh"
echo STAGED
