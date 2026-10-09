# 15B2b-B1b-3e Package C: S25 (Termux) owner-local commands. Record:
# docs/architecture/slice-15b2b-b1b3e-pkgc-record1-envelope-package.md §8.
#
# Owner-run ONLY, locally in Termux, by hand. No SSH, no ADB, no network. Source this file from the verified bundle
# directory, then run exactly ONE stage function per owner act:
#
#   . ./pkgc_s25_phone.sh
#   pkgc_c1        # C1: read-only gate (no write except the staging evidence directory)
#   pkgc_c3        # C3 go only: APPEND_RECORD_1_REPLICA_B (owner record write)
#   pkgc_c4b_pre   # after the C4B gate: read-only proof that copy B is absent (no write)
#   pkgc_c4b       # C4B go only: init store B + APPEND_ENVELOPE_1_COPY_B (owner record write)
#
# The A view and the store A view are NON-CUSTODY, read-only comparison inputs. They live only under
# $HOME/lilith-pkgc/views, never at or under a replica or acceptance-store root, and are never written.
#
# Before a stage, the owner TYPES BY HAND the values the laptop showed (never pasted from a message):
#   PKGC_BUNDLE_SHA256        every stage
#   PKGC_AVIEW_TAR_SHA256     C3, C4B_PRE, C4B   (the T2 Replica A view tar)
#   PKGC_RECORD_DIGEST        C3, C4B_PRE, C4B   (C3: repeated to the canonical tool as --confirm-digest)
#   PKGC_STORE_TAR_SHA256     C4B                (the T3 store A view + package tar)
#   PKGC_ENVELOPE_DIGEST      C4B                (repeated to the canonical tool as --confirm-digest)
#
# Every "STOP" ends the function before any later step. A STOP is never retried by deleting anything. Each owner
# record write is behind a noclobber one-attempt marker: a second run of the same stage refuses.

PKGC_ENV=dev
PKGC_PROFILE=DEV_SYNTHETIC
PKGC_W="$HOME/lilith-pkgc"
PKGC_RB="$HOME/lilith-owner-offline-dev-synthetic-01"
PKGC_PB="$HOME/lilith-genesis-pin-dev-synthetic"
PKGC_SB="$HOME/lilith-owner-acceptance-offline-dev-synthetic-01"
PKGC_RB_ID=owner-offline-dev-synthetic-01

pkgc_stop() { echo "STOP: $*"; return 1; }
pkgc_json() { python -B -c 'import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2], {"d": d}))' "$@"; }
pkgc_tree() {
  python -B -c 'import hashlib, os, sys
r = sys.argv[1]; lines = []
for d, _, fs in os.walk(r):
    for f in fs:
        p = os.path.join(d, f)
        assert not os.path.islink(p)
        lines.append(os.path.relpath(p, r).replace(os.sep, "/") + "=" + hashlib.sha256(open(p, "rb").read()).hexdigest() + "\n")
print(hashlib.sha256("".join(sorted(lines)).encode()).hexdigest())' "$1"
}

# ---- G0 + bundle: run at the start of every stage (read-only) ----
pkgc_common() {
  local stage="$1"
  PKGC_LINES=()
  [ -n "$PKGC_BUNDLE_SHA256" ] || { pkgc_stop "PKGC_BUNDLE_SHA256 not typed"; return 1; }
  python -B -c 'import sys, cryptography as c; m = int(c.__version__.split(".")[0]); sys.exit(0 if 2 <= m < 52 and m != 35 else 1)' \
    || { pkgc_stop "cryptography missing or unsupported (install is a separate owner decision)"; return 1; }
  python -B -c 'from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as K
k = K.from_private_bytes(bytes(32)); s = k.sign(b"pkgc"); k.public_key().verify(s, b"pkgc")' \
    || { pkgc_stop "cryptography Ed25519 self-test failed"; return 1; }
  [ -d "$PKGC_W" ] || mkdir -m 700 "$PKGC_W"
  cd "$PKGC_W" || return 1
  if [ ! -d bundle ]; then
    echo "$PKGC_BUNDLE_SHA256  $HOME/storage/downloads/lilith-pkgc-bundle.tar" | sha256sum -c - || { pkgc_stop "bundle tar hash"; return 1; }
    mkdir -m 700 bundle && tar -xf "$HOME/storage/downloads/lilith-pkgc-bundle.tar" -C bundle || return 1
  fi
  PKGC_B="$(ls -d "$PKGC_W"/bundle/lilith-pkgc-*)"
  (cd "$PKGC_B" && sha256sum -c --quiet SHA256SUMS) || { pkgc_stop "bundle SHA256SUMS"; return 1; }
  export PYTHONPATH="$PKGC_B/vendor:$PKGC_B/src/core-api:$PKGC_B/src/owner-memory-control"
  export PYTHONDONTWRITEBYTECODE=1
  PKGC_E="$PKGC_W/evidence-$stage"
  mkdir -m 700 "$PKGC_E" || { pkgc_stop "evidence-$stage exists: this stage already ran"; return 1; }
  PKGC_WORLD=(--trust "$PKGC_B/binding/trust-inputs.json" --chain "$PKGC_B/binding/chain-export.json"
              --environment "$PKGC_ENV" --profile "$PKGC_PROFILE")
  PKGC_LINES+=("PKGC_S25_STAGE=$stage" "BUNDLE_SHA256=$PKGC_BUNDLE_SHA256" "BUNDLE_VERIFIED"
               "CRYPTOGRAPHY_ED25519_SELFTEST=PASS")
  [ "$(ls -A "$PKGC_PB" | LC_ALL=C sort | tr '\n' ' ')" = "authorization-register.json genesis-pin.json pin-record.json " ] \
    || { pkgc_stop "P-B is not exactly the three Package A files"; return 1; }
  cmp "$PKGC_PB/genesis-pin.json" "$PKGC_B/binding/genesis-pin.json" || { pkgc_stop "P-B pin != bound pin"; return 1; }
  PKGC_LINES+=("PB_PIN_SHA256=$(sha256sum < "$PKGC_PB/genesis-pin.json" | cut -d' ' -f1)"
               "PB_REGISTER_SHA256=$(sha256sum < "$PKGC_PB/authorization-register.json" | cut -d' ' -f1)"
               "PB_PIN_RECORD_SHA256=$(sha256sum < "$PKGC_PB/pin-record.json" | cut -d' ' -f1)")
  T() { python -B -m lilith_owner_memory.owner_freshness_tool "$@"; }
  T inspect-chain "${PKGC_WORLD[@]}" > "$PKGC_E/inspect-chain.json"
  PKGC_LINES+=("CHAIN_AUTHENTICITY=$(pkgc_json "$PKGC_E/inspect-chain.json" 'd["authenticity"]')"
               "CHAIN_ENTRIES=$(pkgc_json "$PKGC_E/inspect-chain.json" 'd.get("entries")')"
               "CHAIN_GENESIS=$(pkgc_json "$PKGC_E/inspect-chain.json" 'd.get("genesisWitnessDigest")')"
               "REPLICA_B_MANIFEST_SHA256=$(sha256sum < "$PKGC_RB/REPLICA.json" | cut -d' ' -f1)")
}

pkgc_aview() {   # T2: the Replica A view (read-only peer input; never a replica of custody)
  [ -n "$PKGC_AVIEW_TAR_SHA256" ] && [ -n "$PKGC_RECORD_DIGEST" ] || { pkgc_stop "values not typed"; return 1; }
  if [ ! -d "$PKGC_W/views/a" ]; then
    echo "$PKGC_AVIEW_TAR_SHA256  $HOME/storage/downloads/lilith-pkgc-replica-a.tar" | sha256sum -c - || { pkgc_stop "A-view tar hash"; return 1; }
    mkdir -p -m 700 "$PKGC_W/views/a" && tar -xf "$HOME/storage/downloads/lilith-pkgc-replica-a.tar" -C "$PKGC_W/views/a" || return 1
    (cd "$PKGC_W/views/a/lilith-pkgc-replica-a" && sha256sum -c --quiet SHA256SUMS) || { pkgc_stop "A-view SHA256SUMS"; return 1; }
  fi
  PKGC_AV="$PKGC_W/views/a/lilith-pkgc-replica-a/replica-a"
  PKGC_LINES+=("A_VIEW_TREE_SHA256=$(pkgc_tree "$PKGC_AV")")
}

pkgc_finish() {
  printf '%s\n' "${PKGC_LINES[@]}" > "$PKGC_E/RESULT_BLOCK.txt"
  cat "$PKGC_E/RESULT_BLOCK.txt"
  echo "RESULT_BLOCK_SHA256=$(sha256sum < "$PKGC_E/RESULT_BLOCK.txt" | cut -d' ' -f1)"
  sha256sum "$PKGC_E"/* > "$PKGC_W/evidence-$1.sha256"
}

# ---- C1: read-only gate ----
pkgc_c1() {
  pkgc_common C1 || return 1
  T verify-replica --replica "$PKGC_RB" > "$PKGC_E/verify-replica-b.json" || { pkgc_stop "Replica B does not verify"; return 1; }
  PKGC_LINES+=("REPLICA_B_RECORDS=$(pkgc_json "$PKGC_E/verify-replica-b.json" 'd["records"]')"
               "REPLICA_B_HEAD=$(pkgc_json "$PKGC_E/verify-replica-b.json" 'd["headDigest"] or "null"')"
               "ACCEPTANCE_STORE_B=$([ -e "$PKGC_SB" ] && echo PRESENT || echo ABSENT)")
  pkgc_finish C1
}

# ---- C3: APPEND_RECORD_1_REPLICA_B (only under the C3 go) ----
pkgc_c3() {
  pkgc_common C3 || return 1
  pkgc_aview || return 1
  T verify-replica --replica "$PKGC_RB" > "$PKGC_E/pre-verify-replica-b.json" || { pkgc_stop "Replica B does not verify"; return 1; }
  [ "$(pkgc_json "$PKGC_E/pre-verify-replica-b.json" 'd["records"]')" = 0 ] || { pkgc_stop "Replica B is not empty"; return 1; }
  T propose-genesis "${PKGC_WORLD[@]}" --pin "$PKGC_PB/genesis-pin.json" --out "$PKGC_E/candidate.json" > "$PKGC_E/propose.json" \
    || { pkgc_stop "propose-genesis refused"; return 1; }
  [ "$(pkgc_json "$PKGC_E/propose.json" 'd["recordDigest"]')" = "$PKGC_RECORD_DIGEST" ] || { pkgc_stop "candidate digest != typed record digest"; return 1; }
  ( set -C; : > "$PKGC_W/attempt-C3" ) 2>/dev/null || { pkgc_stop "C3 attempt already consumed"; return 1; }
  # ---- the ONE owner record write of C3 ----
  T append --replica "$PKGC_RB" --peer "$PKGC_AV" --candidate "$PKGC_E/candidate.json" "${PKGC_WORLD[@]}" \
    --pin "$PKGC_PB/genesis-pin.json" --confirm-digest "$PKGC_RECORD_DIGEST" > "$PKGC_E/append.json"
  echo "append exit $?" > "$PKGC_E/append.rc"
  T verify-replica --replica "$PKGC_RB" > "$PKGC_E/verify-replica-b.json"
  T compare-replicas --replica "$PKGC_RB" --replica "$PKGC_AV" > "$PKGC_E/compare.json"
  T classify --replica "$PKGC_RB" --replica "$PKGC_AV" "${PKGC_WORLD[@]}" > "$PKGC_E/classify.json"
  PKGC_LINES+=("APPEND=$(pkgc_json "$PKGC_E/append.json" 'd.get("status")')"
               "REPLICATION=$(pkgc_json "$PKGC_E/append.json" 'd.get("replication")')"
               "RECORD_DIGEST=$(pkgc_json "$PKGC_E/append.json" 'd.get("recordDigest")')"
               "REPLICA_B_RECORDS=$(pkgc_json "$PKGC_E/verify-replica-b.json" 'd.get("records")')"
               "REPLICA_B_HEAD=$(pkgc_json "$PKGC_E/verify-replica-b.json" 'd.get("headDigest")')"
               "REPLICA_B_FILE=$(ls "$PKGC_RB/records" | tr '\n' ' ' | sed 's/ $//')"
               "COMPARE=$(pkgc_json "$PKGC_E/compare.json" 'd.get("status")')"
               "FRESHNESS=$(pkgc_json "$PKGC_E/classify.json" 'd.get("authenticity") + ":" + d.get("freshness")')"
               "ACCEPTANCE_STORE_B=$([ -e "$PKGC_SB" ] && echo PRESENT || echo ABSENT)")
  pkgc_finish C3
}

# ---- C4B_PRE: read-only proof after the C4B gate (copy B absent; Replica B = record 1; CURRENT) ----
pkgc_c4b_pre() {
  pkgc_common C4B_PRE || return 1
  pkgc_aview || return 1
  T verify-replica --replica "$PKGC_RB" > "$PKGC_E/verify-replica-b.json" || { pkgc_stop "Replica B does not verify"; return 1; }
  T classify --replica "$PKGC_RB" --replica "$PKGC_AV" "${PKGC_WORLD[@]}" > "$PKGC_E/classify.json"
  PKGC_LINES+=("REPLICA_B_RECORDS=$(pkgc_json "$PKGC_E/verify-replica-b.json" 'd.get("records")')"
               "REPLICA_B_HEAD=$(pkgc_json "$PKGC_E/verify-replica-b.json" 'd.get("headDigest")')"
               "FRESHNESS=$(pkgc_json "$PKGC_E/classify.json" 'd.get("authenticity") + ":" + d.get("freshness")')"
               "ACCEPTANCE_STORE_B=$([ -e "$PKGC_SB" ] && echo PRESENT || echo ABSENT)")
  pkgc_finish C4B_PRE
}

# ---- C4B: init store B + APPEND_ENVELOPE_1_COPY_B (only under the C4B go) ----
pkgc_c4b() {
  pkgc_common C4B || return 1
  pkgc_aview || return 1
  [ -n "$PKGC_STORE_TAR_SHA256" ] && [ -n "$PKGC_ENVELOPE_DIGEST" ] || { pkgc_stop "values not typed"; return 1; }
  if [ ! -d "$PKGC_W/views/s" ]; then
    echo "$PKGC_STORE_TAR_SHA256  $HOME/storage/downloads/lilith-pkgc-store-a.tar" | sha256sum -c - || { pkgc_stop "store view tar hash"; return 1; }
    mkdir -p -m 700 "$PKGC_W/views/s" && tar -xf "$HOME/storage/downloads/lilith-pkgc-store-a.tar" -C "$PKGC_W/views/s" || return 1
    (cd "$PKGC_W/views/s/lilith-pkgc-store-a" && sha256sum -c --quiet SHA256SUMS) || { pkgc_stop "store view SHA256SUMS"; return 1; }
  fi
  PKGC_SV="$PKGC_W/views/s/lilith-pkgc-store-a/store-a"
  PKGC_PKG="$PKGC_W/views/s/lilith-pkgc-store-a/package.json"
  PKGC_LINES+=("A_STORE_VIEW_TREE_SHA256=$(pkgc_tree "$PKGC_SV")")
  T verify-replica --replica "$PKGC_RB" > "$PKGC_E/verify-replica-b.json" || { pkgc_stop "Replica B does not verify"; return 1; }
  T classify --replica "$PKGC_RB" --replica "$PKGC_AV" "${PKGC_WORLD[@]}" > "$PKGC_E/classify.json"
  [ "$(pkgc_json "$PKGC_E/classify.json" 'd.get("authenticity") + ":" + d.get("freshness")')" = "AUTHENTIC:CURRENT" ] \
    || { pkgc_stop "freshness is not AUTHENTIC + CURRENT"; return 1; }
  [ ! -e "$PKGC_SB" ] || { pkgc_stop "store B already exists"; return 1; }
  ( set -C; : > "$PKGC_W/attempt-C4B" ) 2>/dev/null || { pkgc_stop "C4B attempt already consumed"; return 1; }
  T init-acceptance-store --store "$PKGC_SB" --custody-copy-id "$PKGC_RB_ID" --environment "$PKGC_ENV" \
    --profile "$PKGC_PROFILE" > "$PKGC_E/init-store.json" || { pkgc_stop "init-acceptance-store refused"; return 1; }
  T propose-envelope --replica "$PKGC_RB" --replica "$PKGC_AV" --store "$PKGC_SB" --store "$PKGC_SV" \
    --package "$PKGC_PKG" --out "$PKGC_E/envelope-candidate.json" > "$PKGC_E/propose-envelope.json" \
    || { pkgc_stop "propose-envelope refused"; return 1; }
  [ "$(pkgc_json "$PKGC_E/propose-envelope.json" 'd["envelopeDigest"]')" = "$PKGC_ENVELOPE_DIGEST" ] \
    || { pkgc_stop "envelope digest != typed envelope digest"; return 1; }
  # ---- the ONE owner record write of C4 copy B ----
  T append-envelope --replica "$PKGC_RB" --replica "$PKGC_AV" "${PKGC_WORLD[@]}" --pin "$PKGC_PB/genesis-pin.json" \
    --store "$PKGC_SB" --peer-store "$PKGC_SV" --candidate "$PKGC_E/envelope-candidate.json" \
    --confirm-digest "$PKGC_ENVELOPE_DIGEST" > "$PKGC_E/append-envelope.json"
  echo "append-envelope exit $?" > "$PKGC_E/append-envelope.rc"
  T classify-acceptance --replica "$PKGC_RB" --replica "$PKGC_AV" --store "$PKGC_SB" --store "$PKGC_SV" \
    --pin "$PKGC_PB/genesis-pin.json" > "$PKGC_E/classify-acceptance.json"
  PKGC_LINES+=("REPLICA_B_RECORDS=$(pkgc_json "$PKGC_E/verify-replica-b.json" 'd.get("records")')"
               "REPLICA_B_HEAD=$(pkgc_json "$PKGC_E/verify-replica-b.json" 'd.get("headDigest")')"
               "FRESHNESS=$(pkgc_json "$PKGC_E/classify.json" 'd.get("authenticity") + ":" + d.get("freshness")')"
               "STORE_B=$(pkgc_json "$PKGC_E/init-store.json" 'd.get("status")')"
               "STORE_B_MANIFEST_SHA256=$(sha256sum < "$PKGC_SB/ACCEPTANCE.json" | cut -d' ' -f1)"
               "APPEND_ENVELOPE=$(pkgc_json "$PKGC_E/append-envelope.json" 'd.get("status")')"
               "REPLICATION=$(pkgc_json "$PKGC_E/append-envelope.json" 'd.get("replication")')"
               "ENVELOPE_DIGEST=$(pkgc_json "$PKGC_E/append-envelope.json" 'd.get("envelopeDigest")')"
               "ACCEPTANCE=$(pkgc_json "$PKGC_E/classify-acceptance.json" 'd.get("state")')")
  pkgc_finish C4B
}
