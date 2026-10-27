#!/usr/bin/env bash
# Remove ONLY what mirror_setup.sh recorded (WSL test environment; refuses on lilith-dev-01).
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo "refused on lilith-dev-01"; exit 1; }
MAN=/root/f8r2/mirror.manifest
units=$(awk '$1=="unit"{print $2}' "$MAN")
for u in ${units}; do systemctl disable --now "$u.service" >/dev/null 2>&1; done
systemctl disable --now lilith-memory-broker.socket lilith-authority-dev.socket lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket >/dev/null 2>&1
SD=/etc/systemd/system
rm -rf $SD/lilith-memory-broker.{service,socket} $SD/lilith-authority-dev.{service,socket} $SD/lilith-authority-dev.{service,socket}.d \
  $SD/lilith-recovery-witness.service $SD/lilith-recovery-witness.service.d $SD/lilith-recovery-witness-{owner,signer}.socket \
  $SD/lilith-recovery-witness-{owner,signer}.socket.d $SD/lilith-stage3-a2-final.service $SD/lilith-os-api-dev.service
systemctl daemon-reload
tac "$MAN" | awk '$1=="path"{print $2}' | while read -r p; do rm -rf --one-file-system -- "$p"; done
for u in $(awk '$1=="user"{print $2}' "$MAN"); do userdel -r "$u" 2>/dev/null || userdel "$u"; done
for g in $(awk '$1=="group"{print $2}' "$MAN"); do groupdel "$g"; done
echo "F8R2_MIRROR_REMOVED"
