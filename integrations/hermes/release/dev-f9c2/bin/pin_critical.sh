#!/usr/bin/env bash
# Write /etc/hermes-gateway-dev/critical.sha256 (root 0600): the set re-hashed by ExecStartPre on every start.
# Shared by install.sh and apply_profile.sh. Root only.
set -Eeuo pipefail
REL=$(readlink -f /opt/hermes-gateway-dev/current 2>/dev/null || true)
[[ -n ${REL} && -d ${REL} ]] || REL=${1:?release dir}
HH=/home/lilith/.hermes-dev; SD=/etc/systemd/system
{ for f in gateway/run.py agent/background_review.py tools/memory_tool.py tools/skill_manager_tool.py \
           tools/write_approval.py tools/legacy_canonical_containment.py; do echo "${REL}/src/${f}"; done
  echo "${REL}/bin/verify_release.py"; echo "${REL}/bin/provider_gate.py"; echo "${HH}/config.yaml"
  echo "/etc/hermes-provider-gate-dev/gate.json"
  for f in "${SD}/hermes-gateway-dev.service" "${SD}/hermes-gateway-dev-retention.service" \
           "${SD}/hermes-gateway-dev-retention.timer" "${SD}/hermes-provider-gate-dev.service" \
           /etc/systemd/journald@hermes-gateway-dev.conf; do echo "$f"; done
  find "${SD}" -maxdepth 2 -path "${SD}/hermes-*-dev*.service.d/*" -type f | LC_ALL=C sort
  find "${HH}/lilith_router" "${HH}/plugins" -type f ! -path '*/__pycache__/*' | LC_ALL=C sort
} | sed 's|^/||' | (cd / && xargs -r sha256sum) > /etc/hermes-gateway-dev/critical.sha256.tmp
chmod 0600 /etc/hermes-gateway-dev/critical.sha256.tmp
mv -f /etc/hermes-gateway-dev/critical.sha256.tmp /etc/hermes-gateway-dev/critical.sha256
echo "critical set pinned: $(wc -l < /etc/hermes-gateway-dev/critical.sha256) files"
