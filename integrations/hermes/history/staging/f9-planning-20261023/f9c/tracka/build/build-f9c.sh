#!/usr/bin/env bash
# F9-C Track A LOCAL candidate build (WSL only; refused on lilith-dev-01). = the accepted F9-B package tree
# (/root/f9b/build/pkg, MANIFEST 0fff1dea…, i.e. the reviewed F8r4 stage-2 build + F9-A + F9-B) + the F9-C overlay:
#   bin/   hermes_forget_executor.py, hermes_restore_guard.py, install_f9c.sh, preserve_f8r4.sh, restore_f8r4.sh (new);
#          restore_f8r2.sh (F9-C guard, base 654525bc…), rollback.sh (F9-C units + pending-FORGET refusal, base ebdc8fc4…)
#   systemd/ hermes-forget-{executor,restart,reconcile,hold}.service, hermes-forget{,-hold}.path,
#          hermes-forget-reconcile.timer, hermes-forget.tmpfiles.conf, hermes-gateway-dev.service.d/50-forget.conf
# Release id f293e72-f9c2 (f9c1 + dedicated drill-store binds + bin/f9c_dev_drill.py). Output /root/f9ca/out. Deterministic; never installed anywhere by this script.
set -Eeuo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo refused; exit 1; }
REL_ID=f293e72-f9c2
F9B=/root/f9b/build/pkg; OV=/root/f9ca/tracka/pkgfiles; W=/root/f9ca; B=$W/build-f9c2; P=$B/pkg; O=$W/out-f9c2   # f9c1 build/ and out/ stay untouched
[[ $(sha256sum < "$F9B/MANIFEST.sha256" | cut -c1-64) == 0fff1dea07f43aa1bb6c479d00219aa7ccb25bd66b690ae7b51fcc50d2194461 ]] \
  || { echo "F9C_BUILD_FAIL F9-B base MANIFEST"; exit 1; }
(cd "$F9B" && sha256sum --quiet -c MANIFEST.sha256) || { echo "F9C_BUILD_FAIL F9-B base tree"; exit 1; }
rm -rf "$B"; mkdir -p "$B"; cp -a "$F9B" "$P"
# Exactly the accepted F9-B content: later tests that ran the bundled interpreter left __pycache__ byproducts in the
# base tree that its MANIFEST never listed (sha256sum -c ignores extra files). Drop them, then their empty dirs.
(cd "$P" && comm -13 <(sed 's/^[0-9a-f]*  //' MANIFEST.sha256 | LC_ALL=C sort) \
   <(find . -type f ! -name MANIFEST.sha256 -printf '%P\n' | LC_ALL=C sort) | while read -r f; do
     [[ $f == *__pycache__/*.pyc ]] || { echo "F9C_BUILD_FAIL unlisted non-bytecode file in F9-B base: $f"; exit 1; }
     rm -f -- "$f"; done
 find . -depth -type d -name __pycache__ -empty -delete)
echo "base pruned to the F9-B MANIFEST ($(wc -l < "$P/MANIFEST.sha256") files)"
echo "$REL_ID" > "$P/RELEASE_ID"
over() {  # <package path> <expected base sha or NEW>
  if [[ $2 == NEW ]]; then [[ ! -e $P/$1 ]] || { echo "F9C_BUILD_FAIL unexpected base $1"; exit 1; }
  else [[ $(sha256sum < "$P/$1" | cut -c1-64) == "$2" ]] || { echo "F9C_BUILD_FAIL base $1"; exit 1; }; fi
  mkdir -p "$(dirname "$P/$1")"; cp "$OV/$1" "$P/$1"; echo "F9-C overlay $(sha256sum < "$P/$1" | cut -c1-16)  $1"; }
over bin/hermes_forget_executor.py NEW
over bin/hermes_restore_guard.py NEW
over bin/install_f9c.sh NEW
over bin/f9c_dev_drill.py NEW
over bin/preserve_f8r4.sh NEW
over bin/restore_f8r4.sh NEW
over bin/restore_f8r2.sh 654525bcea46535c17d93d291f88fe926bd67a89b15060109a511d3021f09e1a
over bin/rollback.sh ebdc8fc4ef5ce07676ceeff67a76d700b136bfe96d7b8ccdb3f0b87c2b6a1f85
for u in hermes-forget-executor.service hermes-forget-restart.service hermes-forget-reconcile.service \
         hermes-forget-reconcile.timer hermes-forget-hold.service hermes-forget.path hermes-forget-hold.path \
         hermes-forget.tmpfiles.conf hermes-gateway-dev.service.d/50-forget.conf; do over "systemd/$u" NEW; done
rm -rf "$P/bin/__pycache__"     # never the bundled stdlib byproducts: they are part of the F9-B base
chmod 0755 "$P"/bin/*.sh
for f in "$P"/bin/*.sh; do bash -n "$f"; done
for f in "$P"/bin/*.py; do "$P/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11" -I -B -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$f"; done
for f in "$P"/bin/*.sh "$P"/bin/*.py "$P"/systemd/hermes-forget* "$P"/systemd/hermes-gateway-dev.service.d/*; do
  if grep -q $'\r' "$f"; then echo "F9C_BUILD_FAIL CRLF $f"; exit 1; fi
done
(cd "$P" && find . -type f ! -name MANIFEST.sha256 -print | sed 's|^\./||' | LC_ALL=C sort | xargs -d '\n' sha256sum > MANIFEST.sha256)
mkdir -p "$O" && rm -f "$O"/*
tar --sort=name --mtime='2026-10-24 00:00:00Z' --owner=0 --group=0 --numeric-owner \
  --pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \
  -C "$B" --transform "s|^pkg|hermes-gateway-dev-$REL_ID|" -cf - pkg | gzip -9n > "$O/hermes-gateway-dev-$REL_ID.tar.gz"
(cd "$O" && sha256sum "hermes-gateway-dev-$REL_ID.tar.gz" > "hermes-gateway-dev-$REL_ID.tar.gz.sha256")
echo "manifest=$(wc -l < "$P/MANIFEST.sha256") manifest_sha=$(sha256sum < "$P/MANIFEST.sha256" | cut -c1-64)"
diff <(sed 's/^[0-9a-f]*  //' "$F9B/MANIFEST.sha256" | sort) <(sed 's/^[0-9a-f]*  //' "$P/MANIFEST.sha256" | sort) | sed 's/^/PATHSET /' || true
join -j 2 <(awk '{print $1, $2}' "$F9B/MANIFEST.sha256" | sort -k2) <(awk '{print $1, $2}' "$P/MANIFEST.sha256" | sort -k2) \
  | awk '$2 != $3 {print "CHANGED", $1}'
cat "$O/hermes-gateway-dev-$REL_ID.tar.gz.sha256"
