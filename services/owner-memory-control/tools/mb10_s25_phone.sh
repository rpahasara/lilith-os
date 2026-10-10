# 15B2b-B1b-3e M-B10: S25 (Termux) owner-local READ-ONLY observation (OD-M10-5). Record:
# docs/architecture/slice-15b2b-b1b3e-mb10-held-package.md §5.2.
#
# Owner-run ONLY, locally in Termux, by hand. No SSH, no ADB, no network. It WRITES NO OWNER RECORD: it never
# appends, initializes, repairs or deletes anything in Replica B, acceptance store B or P-B. Its only writes are its
# own new evidence directory under $HOME/lilith-pkgc.
#
# Before sourcing, the owner checks this file by hand against the value the laptop showed:
#   sha256sum mb10_s25_phone.sh
# Then, in the SAME Termux session, the owner TYPES BY HAND (never pasted from a message):
#   MB10_SEQUENCE        the M-B10 sequence id (D1)
#   PKGC_BUNDLE_SHA256   the accepted Package C S25 bundle (already verified and extracted under $HOME/lilith-pkgc)
# and runs exactly one stage per M-B10 sequence:
#
#   . ./mb10_s25_phone.sh
#   mb10_s25_pre
#
# It reuses the accepted Package C bundle and the proven, NON-CUSTODY A views extracted by C3 / C4B
# ($HOME/lilith-pkgc/views/a and views/s); the laptop eligibility binds their trees to the live laptop copies.

MB10_ENV=dev
MB10_PROFILE=DEV_SYNTHETIC
MB10_W="$HOME/lilith-pkgc"
MB10_RB="$HOME/lilith-owner-offline-dev-synthetic-01"
MB10_PB="$HOME/lilith-genesis-pin-dev-synthetic"
MB10_SB="$HOME/lilith-owner-acceptance-offline-dev-synthetic-01"

mb10_stop() { echo "STOP: $*"; return 1; }
mb10_json() { python -B -c 'import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2], {"d": d}))' "$@"; }
mb10_tree() {
  python -B -c 'import hashlib, os, sys
r = sys.argv[1]; lines = []
for d, _, fs in os.walk(r):
    for f in fs:
        p = os.path.join(d, f)
        assert not os.path.islink(p)
        lines.append(os.path.relpath(p, r).replace(os.sep, "/") + "=" + hashlib.sha256(open(p, "rb").read()).hexdigest() + "\n")
print(hashlib.sha256("".join(sorted(lines)).encode()).hexdigest())' "$1"
}
mb10_only() {   # the single file name in a directory, or STOP
  local n; n="$(ls -A "$1" | wc -l)"
  [ "$n" = 1 ] || { echo "MULTIPLE_OR_NONE"; return 1; }
  ls -A "$1"
}

mb10_s25_pre() {
  local lines=() e b av sv rf sf
  case "$MB10_SEQUENCE" in ([0-9a-f]*) ;; (*) mb10_stop "MB10_SEQUENCE not typed"; return 1;; esac
  [ "${#MB10_SEQUENCE}" = 32 ] || { mb10_stop "MB10_SEQUENCE is not 32 hex characters"; return 1; }
  [ -n "$PKGC_BUNDLE_SHA256" ] || { mb10_stop "PKGC_BUNDLE_SHA256 not typed"; return 1; }
  python -B -c 'from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as K
k = K.from_private_bytes(bytes(32)); s = k.sign(b"mb10"); k.public_key().verify(s, b"mb10")' \
    || { mb10_stop "cryptography Ed25519 self-test failed"; return 1; }
  cd "$MB10_W" || { mb10_stop "no Package C staging"; return 1; }
  echo "$PKGC_BUNDLE_SHA256  $HOME/storage/downloads/lilith-pkgc-bundle.tar" | sha256sum -c --quiet - || { mb10_stop "bundle tar hash"; return 1; }
  b="$(ls -d "$MB10_W"/bundle/lilith-pkgc-*)"
  (cd "$b" && sha256sum -c --quiet SHA256SUMS) || { mb10_stop "bundle SHA256SUMS"; return 1; }
  av="$MB10_W/views/a/lilith-pkgc-replica-a/replica-a"
  sv="$MB10_W/views/s/lilith-pkgc-store-a/store-a"
  (cd "$MB10_W/views/a/lilith-pkgc-replica-a" && sha256sum -c --quiet SHA256SUMS) || { mb10_stop "A-view SHA256SUMS"; return 1; }
  (cd "$MB10_W/views/s/lilith-pkgc-store-a" && sha256sum -c --quiet SHA256SUMS) || { mb10_stop "store view SHA256SUMS"; return 1; }
  export PYTHONPATH="$b/vendor:$b/src/core-api:$b/src/owner-memory-control"
  export PYTHONDONTWRITEBYTECODE=1
  e="$MB10_W/evidence-MB10_PRE-$MB10_SEQUENCE"
  mkdir -m 700 "$e" || { mb10_stop "this sequence's observation already ran"; return 1; }
  T() { python -B -m lilith_owner_memory.owner_freshness_tool "$@"; }
  local world=(--trust "$b/binding/trust-inputs.json" --chain "$b/binding/chain-export.json"
               --environment "$MB10_ENV" --profile "$MB10_PROFILE")
  T inspect-chain "${world[@]}" > "$e/inspect-chain.json" || { mb10_stop "inspect-chain"; return 1; }
  T verify-replica --replica "$MB10_RB" > "$e/verify-replica-b.json" || { mb10_stop "Replica B does not verify"; return 1; }
  T verify-acceptance-store --store "$MB10_SB" > "$e/verify-store-b.json" || { mb10_stop "store B does not verify"; return 1; }
  T classify --replica "$MB10_RB" --replica "$av" "${world[@]}" > "$e/classify.json"
  T classify-acceptance --replica "$MB10_RB" --replica "$av" --store "$MB10_SB" --store "$sv" \
    --pin "$MB10_PB/genesis-pin.json" > "$e/classify-acceptance.json"
  rf="$(mb10_only "$MB10_RB/records")" || { mb10_stop "Replica B records are not exactly one file"; return 1; }
  sf="$(mb10_only "$MB10_SB/envelopes")" || { mb10_stop "store B envelopes are not exactly one file"; return 1; }
  lines+=("MB10_S25_STAGE=MB10_PRE" "MB10_SEQUENCE=$MB10_SEQUENCE" "BUNDLE_SHA256=$PKGC_BUNDLE_SHA256" "BUNDLE_VERIFIED"
          "CRYPTOGRAPHY_ED25519_SELFTEST=PASS"
          "CHAIN_AUTHENTICITY=$(mb10_json "$e/inspect-chain.json" 'd["authenticity"]')"
          "CHAIN_ENTRIES=$(mb10_json "$e/inspect-chain.json" 'd.get("entries")')"
          "CHAIN_GENESIS=$(mb10_json "$e/inspect-chain.json" 'd.get("genesisWitnessDigest")')"
          "A_VIEW_TREE_SHA256=$(mb10_tree "$av")" "A_STORE_VIEW_TREE_SHA256=$(mb10_tree "$sv")"
          "REPLICA_B_MANIFEST_SHA256=$(sha256sum < "$MB10_RB/REPLICA.json" | cut -d' ' -f1)"
          "REPLICA_B_LISTING=$(ls -A "$MB10_RB" | LC_ALL=C sort | tr '\n' ' ' | sed 's/ $//')"
          "REPLICA_B_RECORDS=$(mb10_json "$e/verify-replica-b.json" 'd.get("records")')"
          "REPLICA_B_HEAD=$(mb10_json "$e/verify-replica-b.json" 'd.get("headDigest")')"
          "REPLICA_B_FILE=$rf" "REPLICA_B_FILE_SHA256=$(sha256sum < "$MB10_RB/records/$rf" | cut -d' ' -f1)"
          "STORE_B=$(mb10_json "$e/verify-store-b.json" 'd.get("status")')"
          "STORE_B_MANIFEST_SHA256=$(sha256sum < "$MB10_SB/ACCEPTANCE.json" | cut -d' ' -f1)"
          "STORE_B_LISTING=$(ls -A "$MB10_SB" | LC_ALL=C sort | tr '\n' ' ' | sed 's/ $//')"
          "STORE_B_ENVELOPES=$(mb10_json "$e/verify-store-b.json" 'd.get("envelopes")')"
          "STORE_B_FILE=$sf" "STORE_B_FILE_SHA256=$(sha256sum < "$MB10_SB/envelopes/$sf" | cut -d' ' -f1)"
          "PENDING=$(find "$MB10_RB" "$MB10_SB" -name '*pending*' | wc -l | tr -d ' ')"
          "FRESHNESS=$(mb10_json "$e/classify.json" 'd.get("authenticity") + ":" + d.get("freshness")')"
          "ACCEPTANCE=$(mb10_json "$e/classify-acceptance.json" 'd.get("state")')")
  printf '%s\n' "${lines[@]}" > "$e/RESULT_BLOCK.txt"
  cat "$e/RESULT_BLOCK.txt"
  echo "RESULT_BLOCK_SHA256=$(sha256sum < "$e/RESULT_BLOCK.txt" | cut -d' ' -f1)"
  sha256sum "$e"/* > "$MB10_W/evidence-MB10_PRE-$MB10_SEQUENCE.sha256"
}
