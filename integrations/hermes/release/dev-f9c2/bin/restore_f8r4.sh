#!/usr/bin/env bash
# F9 rollback R-3 (root): return lilith-dev-01 to the owner-accepted F8r4 Phase B installation.
#   sudo bash bin/restore_f8r4.sh /var/backups/hermes-gateway-dev/f8r4-preserved-<ts>
# Pre-condition: f9c already removed with its own R-2 (bin/rollback.sh remove: no F8/F9 path present; HERMES_HOME =
# memories only), and no FORGET pending (no intent, no erasure marker).
# MOVES the preserved F8r4 files back (exact bytes, owners, modes, runtime state, provider gate incl. its key) and
# proves them against the preservation inventory. After a completed Hermes erasure epoch (a FORGET ran after the
# preservation), the executor has already purged the conversation-bearing copies inside the quarantine: those paths
# (and only those) may then be absent or differ, the restore guard must find no surviving pre-epoch conversation item,
# and the restored F8r4 starts with an EMPTY conversation store. Everything else must be identical.
# C-3-guarded reload with protected-service parity, F8r4 verify --full, then the F8r4 gateway is started. Never deletes.
set -Eeuo pipefail
umask 077
P=${1:?usage: restore_f8r4.sh <f8r4-preserved-dir>}
[[ $(id -u) -eq 0 ]] || { echo "not root" >&2; exit 1; }
if [[ ${F8_SIM:-} == 1 ]]; then [[ $(hostname) != lilith-dev-01 ]] || exit 1; else [[ $(hostname) == lilith-dev-01 ]] || { echo "wrong host" >&2; exit 1; }; fi
die() { echo "F9_RESTORE_FAIL $*" >&2; exit 1; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${HERE}/../python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11"
(cd "$P" && sha256sum --quiet -c SHA256SUMS) || die "preservation record integrity"
Q=$(sed -n 's/^quarantine=//p' "$P/record"); RSHA=$(sed -n 's/^release_sha=//p' "$P/record"); AT=$(sed -n 's/^preserved_at=//p' "$P/record")
[[ -d $Q && -n $RSHA && -n $AT ]] || die "preservation record incomplete"
HH=/home/lilith/.hermes-dev; SD=/etc/systemd/system
for f in /opt/hermes-gateway-dev /etc/hermes-gateway-dev /etc/hermes-provider-gate-dev ${SD}/hermes-gateway-dev.service \
         ${SD}/hermes-provider-gate-dev.service /etc/systemd/journald@hermes-gateway-dev.conf ${SD}/hermes-gateway-dev.service.d \
         /var/lib/private/hermes-provider-gate-dev /var/lib/hermes-provider-gate-dev /etc/hermes-forget \
         ${SD}/hermes-forget-executor.service ${SD}/hermes-forget-hold.path ${SD}/hermes-forget.path; do
  [[ ! -e $f && ! -L $f ]] || die "F8/F9 path still present: $f (run the f9c R-2 first)"
done
[[ $(ls -A "${HH}") == memories ]] || die "HERMES_HOME not clean"
shopt -s nullglob; pending=(/var/lib/hermes-forget/intent/*.intent); shopt -u nullglob
[[ -e /var/lib/hermes-forget/in-progress ]] && pending+=(/var/lib/hermes-forget/in-progress)
[[ ${#pending[@]} -eq 0 ]] || die "FORGET pending (${pending[*]}): finish or cancel it before any restore"
ERASED=0
if [[ -e /var/lib/hermes-forget/epochs/epochs.log ]]; then
  "${PY}" -I -B "${HERE}/hermes_restore_guard.py" check "$P" "$Q" || die "F8_RESTORE_CONVERSATION_SUPPRESSED (pre-epoch conversation copy survives in the quarantine)"
  ERASED=$("${PY}" -I -B - "${HERE}" "${AT}" <<'PY'
import sys
from datetime import datetime, timezone
sys.path.insert(0, sys.argv[1])
import hermes_forget_executor as X
at = datetime.strptime(sys.argv[2], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp()
epochs = X.read_epochs(X.Path("/var/lib/hermes-forget/epochs/epochs.log"))
print(int(any(datetime.fromisoformat(e["at"].replace("Z", "+00:00")).timestamp() > at for e in epochs)))
PY
)
fi
EXISTING_UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
state() { for u in ${EXISTING_UNITS}; do printf '%s ' "$u"; for k in ActiveState SubState MainPID InvocationID NRestarts; do printf '%s ' "$(systemctl show "$u" -p $k --value)"; done; echo; done; }
pending_reload() { systemctl list-units --all --no-legend --plain | awk '{print $1}' \
  | grep -v -E '^(hermes-gateway-dev|hermes-provider-gate-dev|hermes-forget|systemd-journald(-varlink)?@hermes-gateway-dev)' \
  | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done || true; }
for _ in $(seq 1 30); do [[ $(systemctl list-jobs --no-legend | wc -l) -eq 0 ]] && break; sleep 2; done
[[ -z $(pending_reload) && $(systemctl list-jobs --no-legend | wc -l) -eq 0 ]] || die "C-3: other units pending / jobs queued"

mv "${Q}/opt/hermes-gateway-dev" /opt/hermes-gateway-dev
for f in "${Q}"/etc/*; do
  case "$(basename "$f")" in
    journald@hermes-gateway-dev.conf) mv "$f" /etc/systemd/ ;;
    hermes-gateway-dev) mv "$f" /etc/hermes-gateway-dev ;;
    hermes-provider-gate-dev) mv "$f" /etc/hermes-provider-gate-dev ;;
    hermes-gateway-dev*.service|hermes-gateway-dev*.timer|hermes-gateway-dev*.d|hermes-provider-gate-dev.service|hermes-provider-gate-dev.service.d) mv "$f" "${SD}/" ;;
    *) die "unexpected quarantined item $(basename "$f")" ;;
  esac
done
[[ -e ${Q}/var-lib/private-hermes-provider-gate-dev ]] && mv "${Q}/var-lib/private-hermes-provider-gate-dev" /var/lib/private/hermes-provider-gate-dev
[[ -e ${Q}/var-lib/lib-hermes-provider-gate-dev || -L ${Q}/var-lib/lib-hermes-provider-gate-dev ]] && mv "${Q}/var-lib/lib-hermes-provider-gate-dev" /var/lib/hermes-provider-gate-dev
shopt -s dotglob nullglob
for f in "${Q}"/hermes-dev/*; do mv "$f" "${HH}/"; done
shopt -u dotglob nullglob
J=$(ls -d "${Q}"/*.hermes-gateway-dev 2>/dev/null | head -1 || true)
[[ -n ${J} && ! -e /var/log/journal/$(basename "${J}") ]] && mv "${J}" /var/log/journal/

# Owners/modes from the inventory (F8r4's R-2 ends with chmod -R go-rwx on its quarantine), then the exact proof.
"${PY}" -I -B - "${HERE}" "$P/f8r4-inventory.txt" "${ERASED}" "$P" <<'PY' || die "restored files differ from the preservation inventory (see $P/inventory.diff)"
import os, subprocess, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import hermes_forget_executor as X
inventory, erased, out = Path(sys.argv[2]), sys.argv[3] == "1", Path(sys.argv[4])

def conversation(path):
    return X._conversation_rel(Path(path).parts) is not None

def parse(text):
    rows = {}
    for line in text.splitlines():
        typ, owner, mode, _size, rest = line.split("\t", 4)
        rows[rest.split("  ", 1)[1]] = line
    return rows

want = parse(inventory.read_text())
for path, line in sorted(want.items()):
    typ, owner, mode = line.split("\t")[:3]
    if not os.path.lexists(path):
        if erased and conversation(path):
            continue                                    # purged by the FORGET executor after the preservation
        raise SystemExit(f"inventory path missing after restore: {path}")
    uid, gid = (int(x) for x in owner.split(":"))
    os.lchown(path, uid, gid)
    if typ != "l":
        os.chmod(path, int(mode, 8))
roots = sorted({"/opt/hermes-gateway-dev", "/etc/hermes-gateway-dev", "/etc/hermes-provider-gate-dev",
                "/var/lib/hermes-provider-gate-dev", "/var/lib/private/hermes-provider-gate-dev", "/home/lilith/.hermes-dev",
                "/etc/systemd/system/hermes-gateway-dev.service", "/etc/systemd/system/hermes-gateway-dev-retention.service",
                "/etc/systemd/system/hermes-gateway-dev-retention.timer", "/etc/systemd/system/hermes-provider-gate-dev.service",
                "/etc/systemd/journald@hermes-gateway-dev.conf"})
lines = []
for root in roots:
    if not os.path.lexists(root):
        continue
    res = subprocess.run(["find", root, "-xdev", "(", "-type", "f", "-printf", "%y\t%U:%G\t%m\t%s\t", "-exec", "sha256sum",
                          "{}", ";", ")", "-o", "(", "!", "-type", "f", "-printf", "%y\t%U:%G\t%m\t-\t-  %p\n", ")"],
                         capture_output=True, text=True, check=True)
    lines += res.stdout.splitlines()
have = parse("\n".join(lines))
keep = lambda rows: {p: l for p, l in rows.items() if not (erased and conversation(p))}
diff = sorted(set(keep(want).items()) ^ set(keep(have).items()))
(out / "restored-inventory.txt").write_text("\n".join(sorted(have.values(), key=lambda l: l.split("  ", 1)[1])) + "\n")
(out / "inventory.diff").write_text("\n".join(f"{'-' if (p, l) in keep(want).items() else '+'} {l}" for p, l in diff) + "\n")
skipped = sum(1 for p in want if erased and conversation(p))
print(f"inventory: {len(keep(want))} non-conversation entries identical; conversation entries exempt={skipped} (erased={int(erased)})")
raise SystemExit(1 if diff else 0)
PY
REL=$(readlink -f /opt/hermes-gateway-dev/current)
[[ $(sha256sum < "${REL}/RELEASE.sha256" | cut -c1-64) == "${RSHA}" ]] || die "restored RELEASE.sha256 differs"
before=$(state); systemctl daemon-reload; after=$(state)
[[ "${before}" == "${after}" ]] || die "PROTECTED_SERVICE_STATE_CHANGED_ACROSS_RELOAD"
"${REL}/venv/bin/python" -I -B "${REL}/bin/verify_release.py" --full || die "f8r4 verify --full after restore"
systemctl start hermes-gateway-dev
for _ in $(seq 1 45); do ss -Hltn 'sport = :9901' | grep -q . && break; sleep 2; done
ss -Hltn 'sport = :9901' | grep -q . || die "f8r4 gateway not listening"
echo "F8R4_RESTORED $(basename "${REL}") erased_after_preservation=${ERASED} (non-conversation inventory identical)"
