#!/usr/bin/env bash
# A0 ONLY (owner-authorized): stage the reviewed amend harness, snapshot every protected artefact, recover request #1's
# reply from a PRIVATE copy of Hermes state (turn1_evidence.py), prove the originals unchanged, budget 1/5 from the
# ledger file, Router V2 decision, DR-5 + observation + service parity. Gateway and gate stay STOPPED. No provider call.
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
R=/opt/hermes-gateway-dev/current; P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r4; B=/var/backups/hermes-gateway-dev
HH=/home/lilith/.hermes-dev; L=/var/lib/private/hermes-provider-gate-dev/ledger.log; DEC=$HH/logs/lilith-router-decisions.log
A=/var/tmp/f8/amend; T=hermes-gateway-dev-f8r4-amend; TGZ_SHA=ed4fe9d6e63c5b73a9e888f9dd099052842f507bcee1a9441276dbe7495539b2
OUT=$B/A0.txt
snap() {  # every artefact A0 must not change: Hermes DB files, ledger, decisions log, full HERMES_HOME listing
  sha256sum $HH/state.db $HH/state.db-wal $HH/state.db-shm $L $DEC 2>&1
  find $HH -printf '%M %u:%g %s %T@ %P\n' | LC_ALL=C sort -k6 | sha256sum | sed 's/-$/HERMES_HOME-listing/'
}
main() {
  echo "== A0 $(date -u +%FT%TZ)"
  local gw gt; gw=$(systemctl show hermes-gateway-dev -p ActiveState --value); gt=$(systemctl show hermes-provider-gate-dev -p ActiveState --value)
  echo "gateway=$gw gate=$gt listeners=[$(ss -Hltn | awk '{print $4}' | grep -E ':(9901|9911)$' | paste -sd' ')]"
  [[ $gw != active && $gt != active ]] || { echo "A0_FAIL gateway or gate running"; return 1; }
  echo "== stage harness"
  [[ ! -e $A ]] || { echo "A0_FAIL $A already exists"; return 1; }
  [[ $(sha256sum < /var/tmp/$T.tgz | cut -c1-64) == "$TGZ_SHA" ]] || { echo "A0_FAIL harness tarball hash"; return 1; }
  install -d -o root -g root -m 0700 $A && mv /var/tmp/$T.tgz $A/ && chown root:root $A/$T.tgz && chmod 0600 $A/$T.tgz
  tar -xzf $A/$T.tgz -C $A --no-same-owner && chmod 0600 $A/*.py $A/SHA256SUMS && chmod 0700 $A/g7r.sh
  (cd $A && sha256sum -c SHA256SUMS) || { echo "A0_FAIL harness hashes"; return 1; }
  ls -la $A
  echo "== snapshot before"; local s0; s0=$(snap); echo "$s0"
  echo "== ledger (read-only)"; cat $L
  local resets used prior; resets=$(grep -c '^RESET' $L)
  used=$(awk '/^RESET/{n=0} /^R /{n++} END{print n}' $L); prior=$(grep '^R ' $L | cut -d' ' -f3)
  echo "budget from ledger: used=$used of 5, remaining=$(( 5 - used )); RESET lines=$resets; prior request=$prior"
  echo "== Router V2 decisions log (read-only)"; echo "lines=$(wc -l < $DEC)"; cut -c1-400 $DEC
  echo "== turn-1 evidence (private copy)"
  $R/venv/bin/python -I -B $A/turn1_evidence.py; local trc=$?
  echo "turn1_evidence rc=$trc; leftover private copies: $(ls -d $A/t1-* 2>/dev/null | wc -l)"
  echo "== snapshot after"; local s1; s1=$(snap); echo "$s1"
  local same=no; [[ "$s0" == "$s1" ]] && same=yes; echo "originals unchanged: $same"
  echo "== gate turn-1 record (journal, read-only)"
  journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager | grep '"decision": "FORWARDED"' | cut -c1-600
  echo "== release + parity"
  $R/venv/bin/python -I -B $R/bin/verify_release.py --full; local vrc=$?
  local G1; G1=$(ls -d $B/upgrade-pre-* | tail -1)
  bash $P/bin/observe_host.sh $B/a0-post >/dev/null; bash $P/bin/compare_observations.sh $G1/observation $B/a0-post; local orc=$?
  bash $P/bin/dr5_check.sh $B/dr5-f8r4-a0.txt > $B/dr5-f8r4-a0.summary 2>&1; local drc=$?; tail -1 $B/dr5-f8r4-a0.summary
  echo "core api health: $(curl -s -m 5 http://127.0.0.1:8765/health)"
  for u in hermes-gateway-dev hermes-provider-gate-dev hermes-gateway-dev-retention.timer lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
    printf '%-36s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
  echo "listeners 9901/9911: [$(ss -Hltn | awk '{print $4}' | grep -E ':(9901|9911)$' | paste -sd' ')]"
  local ok=1
  [[ $trc -eq 0 && $same == yes && $used -eq 1 && $resets -eq 1 && $prior == 0d00769ac01a && $(wc -l < $DEC) -eq 1 ]] || ok=0
  [[ $vrc -eq 0 && $orc -eq 0 && $drc -eq 0 && $(ls -d $A/t1-* 2>/dev/null | wc -l) -eq 0 ]] || ok=0
  [[ $(systemctl show hermes-gateway-dev -p ActiveState --value) != active && $(systemctl show hermes-provider-gate-dev -p ActiveState --value) != active ]] || ok=0
  [[ $ok -eq 1 ]] && echo A0_PASS || { echo A0_FAIL; return 1; }
}
main > $OUT 2>&1; echo "main_rc=$?" >> $OUT
cat $OUT; echo "OUT_SHA $(sha256sum < $OUT | cut -c1-64)"
