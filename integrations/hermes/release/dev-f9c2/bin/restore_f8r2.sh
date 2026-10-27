#!/usr/bin/env bash
# F8r4 rollback R-3 (root): return lilith-dev-01 to the owner-accepted F8r2 Phase A installation.
#   sudo bash bin/restore_f8r2.sh /var/backups/hermes-gateway-dev/f8r2-preserved-<ts>
# Pre-condition: f8r4 already removed with its own R-2 (no F8 path present; HERMES_HOME = memories only).
# MOVES the preserved F8r2 files back (exact bytes, owners, modes, runtime state), proves them against the
# preservation inventory, reloads systemd only under the C-3 guard with protected-service parity, then starts the
# F8r2 gateway. Never deletes; touches only the F8r2 allowlisted paths.
set -Eeuo pipefail
umask 077
P=${1:?usage: restore_f8r2.sh <f8r2-preserved-dir>}
[[ $(id -u) -eq 0 ]] || { echo "not root" >&2; exit 1; }
if [[ ${F8_SIM:-} == 1 ]]; then [[ $(hostname) != lilith-dev-01 ]] || exit 1; else [[ $(hostname) == lilith-dev-01 ]] || { echo "wrong host" >&2; exit 1; }; fi
die() { echo "F8_RESTORE_FAIL $*" >&2; exit 1; }
(cd "$P" && sha256sum --quiet -c SHA256SUMS) || die "preservation record integrity"
Q=$(sed -n 's/^quarantine=//p' "$P/record"); RSHA=$(sed -n 's/^release_sha=//p' "$P/record")
# F9-C: after any completed Hermes erasure epoch, conversation history captured before it is never restored
# (fail closed before anything is moved). Code/config-only restore with an empty conversation store is a separate,
# reviewed procedure (F9 upgrade scripts), not this script.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD_PY="${HERE}/../python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11"
if [[ -e /var/lib/hermes-forget/epochs/epochs.log ]]; then
  "${GUARD_PY}" -I -B "${HERE}/hermes_restore_guard.py" check "$P" "${Q}"     || die "F8_RESTORE_CONVERSATION_SUPPRESSED (Hermes erasure epoch; see hermes_restore_guard.py)"
fi
HH=/home/lilith/.hermes-dev; SD=/etc/systemd/system
for f in /opt/hermes-gateway-dev /etc/hermes-gateway-dev /etc/hermes-provider-gate-dev ${SD}/hermes-gateway-dev.service \
         ${SD}/hermes-provider-gate-dev.service /etc/systemd/journald@hermes-gateway-dev.conf; do
  [[ ! -e $f ]] || die "F8 path still present: $f (run the f8r4 R-2 first)"
done
[[ $(ls -A "${HH}") == memories ]] || die "HERMES_HOME not clean"
EXISTING_UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
state() { for u in ${EXISTING_UNITS}; do printf '%s ' "$u"; for k in ActiveState SubState MainPID InvocationID NRestarts; do printf '%s ' "$(systemctl show "$u" -p $k --value)"; done; echo; done; }
pending() { systemctl list-units --all --no-legend --plain | awk '{print $1}' \
  | grep -v -E '^(hermes-gateway-dev|hermes-provider-gate-dev|systemd-journald(-varlink)?@hermes-gateway-dev)' \
  | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done || true; }
for _ in $(seq 1 30); do [[ $(systemctl list-jobs --no-legend | wc -l) -eq 0 ]] && break; sleep 2; done
[[ -z $(pending) && $(systemctl list-jobs --no-legend | wc -l) -eq 0 ]] || die "C-3: other units pending / jobs queued"
mv "${Q}/opt/hermes-gateway-dev" /opt/hermes-gateway-dev
for f in "${Q}"/etc/*; do
  case "$(basename "$f")" in
    journald@hermes-gateway-dev.conf) mv "$f" /etc/systemd/ ;;
    hermes-gateway-dev) mv "$f" /etc/hermes-gateway-dev ;;
    hermes-gateway-dev*.service|hermes-gateway-dev*.timer|hermes-gateway-dev*.d) mv "$f" "${SD}/" ;;
    *) die "unexpected quarantined item $(basename "$f")" ;;
  esac
done
shopt -s dotglob nullglob
for f in "${Q}"/hermes-dev/*; do mv "$f" "${HH}/"; done
J=$(ls -d "${Q}"/*.hermes-gateway-dev 2>/dev/null | head -1 || true)
[[ -n ${J} && ! -e /var/log/journal/$(basename "${J}") ]] && mv "${J}" /var/log/journal/
# F8r2's accepted rollback ends with `chmod -R go-rwx` on its quarantine: re-apply every recorded owner and mode from
# the preservation inventory (content is never touched), then prove the result identical below.
while IFS=$'\t' read -r type owner mode _size rest; do
  path=${rest#*  }
  [[ -e ${path} || -L ${path} ]] || die "inventory path missing after restore: ${path}"
  chown -h "${owner}" "${path}"
  [[ ${type} == l ]] || chmod "${mode}" "${path}"
done < "$P/f8r2-inventory.txt"
REL=$(readlink -f /opt/hermes-gateway-dev/current)
[[ $(sha256sum < "${REL}/RELEASE.sha256" | cut -c1-64) == "${RSHA}" ]] || die "restored RELEASE.sha256 differs"
# Inventory line (TAB-separated, path LAST so paths with spaces stay intact):
#   <type> TAB <uid:gid> TAB <mode> TAB <size|-> TAB <sha256|->  <path>
inv() { for p in "$@"; do [[ -e $p || -L $p ]] || continue
          find "$p" -xdev \( -type f -printf '%y\t%U:%G\t%m\t%s\t' -exec sha256sum {} \; \) \
                -o \( ! -type f -printf '%y\t%U:%G\t%m\t-\t-  %p\n' \) ; done; }
inv /opt/hermes-gateway-dev /etc/hermes-gateway-dev ${SD}/hermes-gateway-dev.service ${SD}/hermes-gateway-dev-retention.service \
    ${SD}/hermes-gateway-dev-retention.timer /etc/systemd/journald@hermes-gateway-dev.conf "${HH}" 2>/dev/null \
  | LC_ALL=C sort -t$'\t' -k5 > "$P/restored-inventory.txt"
diff -u "$P/f8r2-inventory.txt" "$P/restored-inventory.txt" > "$P/inventory.diff" || die "restored files differ from the preservation inventory (see $P/inventory.diff)"
before=$(state); systemctl daemon-reload; after=$(state)
[[ "${before}" == "${after}" ]] || die "PROTECTED_SERVICE_STATE_CHANGED_ACROSS_RELOAD"
"${REL}/venv/bin/python" -I -B "${REL}/bin/verify_release.py" --full || die "f8r2 verify --full after restore"
systemctl start hermes-gateway-dev
for _ in $(seq 1 45); do ss -Hltn 'sport = :9901' | grep -q . && break; sleep 2; done
ss -Hltn 'sport = :9901' | grep -q . || die "f8r2 gateway not listening"
echo "F8R2_RESTORED $(basename "${REL}") files=$(grep -c $'^f\t' "$P/restored-inventory.txt") (inventory identical)"
