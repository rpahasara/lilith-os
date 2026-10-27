#!/usr/bin/env bash
# F8r2 WSL DEV-MIRROR (local test environment only; refuses to run on lilith-dev-01).
# Reproduces the pre-existing lilith-dev-01 state that F8 must not disturb:
#   - accounts: lilith-memory-broker, lilith-authority-dev, lilith-recovery-witness, group lilith-memory-ipc,
#     the synthetic routine deployer sa_112096412008414111981 (DEV uid 3826947836), lilith (already present)
#   - stand-in broker / authority / witness services with DEV's exact unit, socket and drop-in definitions (from the
#     2026-10-23 read-only DEV preflight), ExecStart replaced by a stand-in accept loop, LoadCredentialEncrypted
#     replaced by SetCredential (no real credential exists anywhere in this mirror)
#   - the real Core API (main b9eb32c bundle file set) under DEV's unit text, paths and user
#   - every DR-5 ladder / PR-1 / custody / credstore / later-state object with DEV's owner and mode
#   - the deployer's exact sudoers rule, fixed helper and pinned controls (scripts/dev_deployer)
# Every created path / account / unit is appended to $MAN for mirror_teardown.sh.
set -Eeuo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo "refused on lilith-dev-01"; exit 1; }
R=${1:?usage: mirror_setup.sh <repo-export-dir> <uv>}; UV=${2:?}
MAN=/root/f8r2/mirror.manifest; : > "${MAN}"
rec() { echo "$*" >> "${MAN}"; }
mkd() { local p=$1 o=$2 m=$3; [[ -e $p ]] || rec "path $p"; install -d -o "${o%%:*}" -g "${o##*:}" -m "$m" "$p"; }
put() { local p=$1 o=$2 m=$3; [[ -e $p ]] || rec "path $p"; cat > "$p"; chown "$o" "$p"; chmod "$m" "$p"; }
STANDIN='import os, select, socket
n = int(os.environ.get("LISTEN_FDS", "0"))
socks = [socket.socket(fileno=3 + i) for i in range(n)]
while True:
    for s in select.select(socks, [], [])[0] if socks else select.select([], [], [], 3600)[0]:
        c, _ = s.accept(); c.close()'
echo "--- accounts"
getent group lilith-memory-ipc >/dev/null || { groupadd --system lilith-memory-ipc; rec "group lilith-memory-ipc"; }
for u in lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
  id "$u" >/dev/null 2>&1 || { useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$u"; rec "user $u"; }
done
id sa_112096412008414111981 >/dev/null 2>&1 || { useradd -l -u 3826947836 -U -m -s /bin/bash sa_112096412008414111981; rec "user sa_112096412008414111981"; }
echo "--- deployer boundary (repo scripts/dev_deployer, exact rule)"
mkd /usr/local/lib/lilith-dev-deploy root:root 0755
install -o root -g root -m 0644 "$R/scripts/dev_deployer/effective_sudo_proof.sh" /usr/local/lib/lilith-dev-deploy/effective_sudo_proof.sh
install -o root -g root -m 0644 "$R/scripts/verify_core_api_bundle.py" /usr/local/lib/lilith-dev-deploy/verify_core_api_bundle.py
install -o root -g root -m 0644 "$R/scripts/run_core_api_dev_durability_probe.py" /usr/local/lib/lilith-dev-deploy/run_core_api_dev_durability_probe.py
[[ -e /usr/local/sbin/lilith-dev-deploy ]] || rec "path /usr/local/sbin/lilith-dev-deploy"
install -o root -g root -m 0755 "$R/scripts/dev_deployer/lilith-dev-deploy" /usr/local/sbin/lilith-dev-deploy
sed "s/@DEPLOYER@/sa_112096412008414111981/g" "$R/scripts/dev_deployer/sudoers-lilith-dev-deployer.in" > /tmp/f8r2-sudoers
visudo -cf /tmp/f8r2-sudoers >/dev/null
[[ -e /etc/sudoers.d/lilith-dev-deployer ]] || rec "path /etc/sudoers.d/lilith-dev-deployer"
install -o root -g root -m 0440 /tmp/f8r2-sudoers /etc/sudoers.d/lilith-dev-deployer; rm -f /tmp/f8r2-sudoers; visudo -c >/dev/null
mkd /etc/needrestart root:root 0755; mkd /etc/needrestart/conf.d root:root 0755
put /etc/needrestart/conf.d/lilith-authority-sensitive.conf root:root 0644 <<'EOF'
$nrconf{override_rc}{qr(^lilith-memory-broker\.service$)} = 0;
$nrconf{override_rc}{qr(^lilith-authority-dev\.service$)} = 0;
$nrconf{override_rc}{qr(^lilith-recovery-witness\.service$)} = 0;
EOF
echo "--- authority ladder L1b.1..L1c.3 + PR-1 P1A-5..P1A-9 (DEV owners/modes)"
REL=129f2bed617334be61dcac5204cd409946a7a566
mkd /opt/lilith-authority-dev root:root 0755; mkd /opt/lilith-authority-dev/releases root:root 0755
mkd /opt/lilith-authority-dev/releases/$REL root:root 0755
printf '%s\n' "${STANDIN}" | put /opt/lilith-authority-dev/releases/$REL/standin.py root:root 0644
[[ -L /opt/lilith-authority-dev/current ]] || { ln -s releases/$REL /opt/lilith-authority-dev/current; rec "path /opt/lilith-authority-dev/current"; }
for c in lilith-authority-keygen-dev lilith-authority-ledger-dev lilith-authority-hold-dev lilith-authority-verify-dev \
         lilith-authority-recovery-dev lilith-recovery-witness-owner-dev; do
  printf '#!/bin/sh\necho "F8r2 mirror stand-in: not a real CLI" >&2\nexit 64\n' | put /usr/local/sbin/$c root:root 0755
done
mkd /etc/lilith-authority-custody root:root 0700; mkd /etc/lilith-authority-custody/prepared root:root 0700; mkd /etc/lilith-authority-custody/retired root:root 0700
for d in "" /trust /registry /owner /hold; do mkd /etc/lilith-authority-dev$d root:root 0755; done
echo "stand-in" | put /etc/lilith-authority-dev/INSTALLED root:root 0644
mkd /etc/lilith-recovery-witness root:root 0700; mkd /etc/lilith-recovery-witness/credentials root:root 0700
echo "F8r2 MIRROR STAND-IN - NOT A CREDENTIAL" | put /etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred root:root 0600
mkd /var/lib/lilith-authority-custody root:root 0700; mkd /var/lib/lilith-authority-custody/holds root:root 0700
# Pre-existing on WSL with DEV's exact owner/mode (root 0700, root 0400): only a stand-in blob is added.
echo "F8r2 MIRROR STAND-IN - NOT A CREDENTIAL" | put /etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred root:root 0600
mkd /var/lib/lilith-authority-dev lilith-authority-dev:lilith-authority-dev 0700
: | put /var/lib/lilith-authority-dev/authority_ledger.db lilith-authority-dev:lilith-authority-dev 0600
mkd /var/lib/lilith-recovery-witness lilith-recovery-witness:lilith-recovery-witness 0700
echo "--- broker"
mkd /opt/lilith-memory-broker root:root 0755; mkd /opt/lilith-memory-broker/current root:root 0755
printf '%s\n' "${STANDIN}" | put /opt/lilith-memory-broker/current/standin.py root:root 0644
mkd /etc/lilith-memory-broker root:root 0755
mkd /opt/lilith-stage3-a2-final-v1 root:root 0555; mkd /opt/lilith-trusted-controls root:root 0755
mkd /etc/lilith-os-dev root:root 0755; mkd /etc/lilith-os-dev/activation root:root 0755
printf '{"activeCapabilities":[],"canonicalLtmEnabled":false,"schemaVersion":1}\n' | put /etc/lilith-os-dev/canonical-runtime.json root:lilith 0640
echo "--- tmpfiles (runtime dirs for the sockets)"
printf 'd /run/lilith-authority-dev 0700 root root -\n' | put /etc/tmpfiles.d/lilith-authority-dev.conf root:root 0644
printf 'd /run/lilith-recovery-witness 0710 root lilith-authority-dev -\n' | put /etc/tmpfiles.d/lilith-recovery-witness.conf root:root 0644
printf 'd /run/lilith-memory 0710 root lilith-memory-ipc -\n' | put /etc/tmpfiles.d/lilith-memory-broker.conf root:root 0644
systemd-tmpfiles --create /etc/tmpfiles.d/lilith-authority-dev.conf /etc/tmpfiles.d/lilith-recovery-witness.conf /etc/tmpfiles.d/lilith-memory-broker.conf
rec "path /run/lilith-authority-dev"; rec "path /run/lilith-recovery-witness"; rec "path /run/lilith-memory"
echo "--- units (DEV text; stand-in ExecStart; SetCredential instead of LoadCredentialEncrypted)"
SD=/etc/systemd/system
put $SD/lilith-memory-broker.socket root:root 0644 <<'EOF'
[Unit]
Description=LILITH synthetic Memory Broker socket (DEV only)
Requires=systemd-tmpfiles-setup.service
After=systemd-tmpfiles-setup.service
AssertPathIsDirectory=/run/lilith-memory
[Socket]
ListenStream=/run/lilith-memory/owner.sock
Accept=no
Service=lilith-memory-broker.service
SocketUser=lilith-memory-broker
SocketGroup=lilith-memory-ipc
SocketMode=0660
DirectoryMode=0710
FlushPending=yes
RemoveOnStop=yes
Backlog=16
TriggerLimitIntervalSec=60
TriggerLimitBurst=3
[Install]
WantedBy=sockets.target
EOF
put $SD/lilith-memory-broker.service root:root 0644 <<'EOF'
[Unit]
Description=LILITH synthetic Memory Broker (DEV only) [F8r2 WSL mirror stand-in]
Requires=lilith-memory-broker.socket
After=lilith-memory-broker.socket
StartLimitIntervalSec=60
StartLimitBurst=3
[Service]
Type=simple
User=lilith-memory-broker
Group=lilith-memory-broker
WorkingDirectory=/opt/lilith-memory-broker/current
Environment=LILITH_ENV=dev
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONNOUSERSITE=1
ExecStart=/usr/bin/python3 -B /opt/lilith-memory-broker/current/standin.py
StateDirectory=lilith-memory-broker
StateDirectoryMode=0700
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictNamespaces=yes
LockPersonality=yes
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies=AF_UNIX
IPAddressDeny=any
ReadOnlyPaths=/opt/lilith-memory-broker /etc/lilith-memory-broker
ReadWritePaths=/var/lib/lilith-memory-broker
Restart=on-failure
RestartSec=5s
TimeoutStartSec=15s
TimeoutStopSec=10s
EOF
rec "path /var/lib/lilith-memory-broker"
put $SD/lilith-authority-dev.socket root:root 0644 <<'EOF'
[Unit]
Description=LILITH DEV_SYNTHETIC authority signer owner socket (DEV only, root-only)
Requires=systemd-tmpfiles-setup.service
After=systemd-tmpfiles-setup.service
AssertPathIsDirectory=/run/lilith-authority-dev
[Socket]
ListenStream=/run/lilith-authority-dev/owner.sock
Accept=no
Service=lilith-authority-dev.service
SocketUser=root
SocketGroup=root
SocketMode=0600
DirectoryMode=0700
FlushPending=yes
RemoveOnStop=yes
Backlog=16
TriggerLimitIntervalSec=60
TriggerLimitBurst=3
EOF
mkd $SD/lilith-authority-dev.socket.d root:root 0755
printf '[Unit]\nStopWhenUnneeded=yes\nRefuseManualStart=yes\n' | put $SD/lilith-authority-dev.socket.d/10-no-reactivation.conf root:root 0644
put $SD/lilith-authority-dev.service root:root 0644 <<'EOF'
[Unit]
Description=LILITH DEV_SYNTHETIC OWNER_ACTOR authority signer (DEV only) [F8r2 WSL mirror stand-in]
Requires=lilith-authority-dev.socket
After=lilith-authority-dev.socket
StartLimitIntervalSec=60
StartLimitBurst=3
[Service]
Type=simple
User=lilith-authority-dev
Group=lilith-authority-dev
WorkingDirectory=/opt/lilith-authority-dev/current
Environment=LILITH_ENV=dev
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONNOUSERSITE=1
ExecStart=/usr/bin/python3 -B /opt/lilith-authority-dev/current/standin.py
SetCredential=owner-actor-signing-key:F8r2-MIRROR-STAND-IN-NOT-A-KEY
StateDirectory=lilith-authority-dev
StateDirectoryMode=0700
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictNamespaces=yes
LockPersonality=yes
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies=AF_UNIX
IPAddressDeny=any
ReadOnlyPaths=/opt/lilith-authority-dev /etc/lilith-authority-dev /var/lib/lilith-recovery-witness
ReadWritePaths=/var/lib/lilith-authority-dev
InaccessiblePaths=/etc/credstore.encrypted /etc/lilith-authority-custody /var/lib/lilith-authority-custody /etc/lilith-recovery-witness /etc/lilith-memory-broker /var/lib/lilith-memory-broker /etc/lilith-os-dev
Restart=on-failure
RestartSec=5s
TimeoutStartSec=15s
TimeoutStopSec=10s
EOF
mkd $SD/lilith-authority-dev.service.d root:root 0755
printf '[Service]\nRestart=no\n' | put $SD/lilith-authority-dev.service.d/10-no-implicit-restart.conf root:root 0644
for kind in owner signer; do
  if [[ $kind == owner ]]; then SU=root; SG=root; SM=0600; FD=owner; DESC="owner socket (DEV only, root-only)"
  else SU=lilith-recovery-witness; SG=lilith-authority-dev; SM=0660; FD=signer; DESC="signer socket (DEV only, authority signer peer only)"; fi
  put $SD/lilith-recovery-witness-$kind.socket root:root 0644 <<EOF
[Unit]
Description=LILITH DEV_SYNTHETIC recovery witness ${DESC}
Requires=systemd-tmpfiles-setup.service
After=systemd-tmpfiles-setup.service
AssertPathIsDirectory=/run/lilith-recovery-witness
[Socket]
ListenStream=/run/lilith-recovery-witness/${kind}.sock
Accept=no
Service=lilith-recovery-witness.service
FileDescriptorName=${FD}
SocketUser=${SU}
SocketGroup=${SG}
SocketMode=${SM}
DirectoryMode=0710
FlushPending=yes
RemoveOnStop=yes
Backlog=16
TriggerLimitIntervalSec=60
TriggerLimitBurst=3
EOF
  mkd $SD/lilith-recovery-witness-$kind.socket.d root:root 0755
  printf '[Unit]\nStopWhenUnneeded=yes\nRefuseManualStart=yes\n' | put $SD/lilith-recovery-witness-$kind.socket.d/10-no-reactivation.conf root:root 0644
done
put $SD/lilith-recovery-witness.service root:root 0644 <<'EOF'
[Unit]
Description=LILITH DEV_SYNTHETIC RecoveryWitnessV2 service (DEV only) [F8r2 WSL mirror stand-in]
Requires=lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket
After=lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket
StartLimitIntervalSec=60
StartLimitBurst=3
[Service]
Type=simple
User=lilith-recovery-witness
Group=lilith-recovery-witness
Sockets=lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket
WorkingDirectory=/opt/lilith-authority-dev/current
Environment=LILITH_ENV=dev
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONNOUSERSITE=1
ExecStart=/usr/bin/python3 -B /opt/lilith-authority-dev/current/standin.py
SetCredential=recovery-witness-signing-key:F8r2-MIRROR-STAND-IN-NOT-A-KEY
UMask=0027
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
PrivateNetwork=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictNamespaces=yes
LockPersonality=yes
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies=AF_UNIX
IPAddressDeny=any
ReadOnlyPaths=/opt/lilith-authority-dev /etc/lilith-authority-dev
ReadWritePaths=/var/lib/lilith-recovery-witness
InaccessiblePaths=/etc/lilith-recovery-witness /etc/credstore.encrypted /etc/lilith-authority-custody /var/lib/lilith-authority-custody -/var/lib/lilith-authority-dev /etc/lilith-memory-broker /var/lib/lilith-memory-broker /etc/lilith-os-dev
Restart=on-failure
RestartSec=5s
TimeoutStartSec=15s
TimeoutStopSec=10s
EOF
mkd $SD/lilith-recovery-witness.service.d root:root 0755
printf '[Service]\nRestart=no\n' | put $SD/lilith-recovery-witness.service.d/10-no-implicit-restart.conf root:root 0644
put $SD/lilith-stage3-a2-final.service root:root 0644 <<'EOF'
[Unit]
Description=LILITH DEV synthetic Stage-III A2 fixed one-shot final controller [F8r2 WSL mirror stand-in, never started]
After=network-online.target
StartLimitIntervalSec=infinity
StartLimitBurst=1
[Service]
Type=exec
User=root
Group=root
WorkingDirectory=/
ExecStart=/bin/false
Restart=no
EOF
echo "--- Core API (main b9eb32c file set, DEV unit text)"
CORE=/home/lilith/.hermes/lilith-os-dev; CSHA=b9eb32c2e1756b23f5d1f28fa0c2e3b9a1ab35e6
rm -f "${CORE}/data/SENTINEL" "${CORE}/data/lilith-dev.db"   # leftovers of the f8r1 simulation (sim-owned)
mkd ${CORE}/releases lilith:lilith 0700; mkd ${CORE}/releases/${CSHA} lilith:lilith 0700; mkd ${CORE}/api lilith:lilith 0700
cp "$R/services/core-api/app.py" "$R/services/core-api/requirements.txt" ${CORE}/releases/${CSHA}/
mkdir -p ${CORE}/releases/${CSHA}/lilith_memory ${CORE}/releases/${CSHA}/tests
cp "$R"/services/core-api/lilith_memory/*.py ${CORE}/releases/${CSHA}/lilith_memory/
cp "$R/services/core-api/tests/test_goal_executive.py" "$R/services/core-api/tests/test_canonical_runtime.py" ${CORE}/releases/${CSHA}/tests/
chown -R lilith:lilith ${CORE}/releases
[[ -L ${CORE}/current ]] || { ln -s ${CORE}/releases/${CSHA} ${CORE}/current; chown -h lilith:lilith ${CORE}/current; rec "path ${CORE}/current"; }
if [[ ! -x ${CORE}/api-venv/bin/python ]]; then
  rec "path ${CORE}/api-venv"
  UV_NO_CONFIG=1 "${UV}" venv -q --python /usr/bin/python3 --seed ${CORE}/api-venv
  UV_NO_CONFIG=1 UV_CACHE_DIR=/root/f8r2/uv-cache "${UV}" pip install -q --python ${CORE}/api-venv/bin/python -r ${CORE}/releases/${CSHA}/requirements.txt
  chown -R lilith:lilith ${CORE}/api-venv
fi
put $SD/lilith-os-api-dev.service root:root 0644 <<'EOF'
[Unit]
Description=LILITH OS Core API DEV
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=lilith
Group=lilith
Environment="HOME=/home/lilith"
Environment="LILITH_HOME=/home/lilith"
Environment="HERMES_HOME=/home/lilith/.hermes-dev"
Environment="LILITH_DATA_DIR=/home/lilith/.hermes/lilith-os-dev/data"
Environment="LILITH_DB_PATH=/home/lilith/.hermes/lilith-os-dev/data/lilith-dev.db"
Environment="LILITH_ENV=dev"
Environment="LILITH_COGNITIVE_DB_PATH=/home/lilith/.hermes/lilith-os-dev/data/cognitive_memory.dev.db"
Environment="LILITH_PRIVACY_DB_PATH=/home/lilith/.hermes/lilith-os-dev/data/privacy_governance.dev.db"
Environment="LILITH_CANONICAL_CONFIG_FILE=/etc/lilith-os-dev/canonical-runtime.json"
WorkingDirectory=/home/lilith/.hermes/lilith-os-dev/current
ExecStart=/home/lilith/.hermes/lilith-os-dev/api-venv/bin/uvicorn app:app --host 0.0.0.0 --port 8765
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
echo "--- start (DEV: all four running)"
for u in lilith-memory-broker lilith-authority-dev lilith-recovery-witness lilith-os-api-dev lilith-stage3-a2-final; do rec "unit $u"; done
systemctl daemon-reload
systemctl enable --now lilith-os-api-dev.service lilith-memory-broker.socket >/dev/null 2>&1
systemctl start lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service
sleep 4
for u in lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
  printf '%-28s %s\n' "$u" "$(systemctl show $u -p ActiveState,SubState,MainPID --value | tr '\n' ' ')"; done
curl -s -m 5 http://127.0.0.1:8765/health; echo
echo "F8R2_MIRROR_READY"
