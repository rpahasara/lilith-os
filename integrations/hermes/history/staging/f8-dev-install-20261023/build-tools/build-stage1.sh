#!/usr/bin/env bash
# F8 package build, stage 1 (local WSL Ubuntu 24.04 only). Assembles + verifies source, fetches pinned uv and
# CPython 3.11.16, exports the locked requirement set and downloads a hash-verified Linux wheelhouse.
set -Eeuo pipefail
W=/root/f8hd; IN=$W/in; B=$W/build; rm -rf "$B"; mkdir -p "$B"/{pkg,tmp}
P=$B/pkg; UPSTREAM=f293e7206b4ddd66042329442c6afebc19a8808d; UV_VER=0.12.5; PY_VER=3.11.16
export UV_CACHE_DIR=$B/tmp/uv-cache UV_PYTHON_INSTALL_DIR=$B/tmp/uv-python UV_NO_CONFIG=1 UV_PYTHON_DOWNLOADS=manual
echo "== source"; mkdir -p $B/tmp/s && tar -xf $IN/upstream-src.tar -C $B/tmp/s
# Every upstream file must equal its git blob at $UPSTREAM.
python3 - "$B/tmp/s/src" "$IN/upstream-ls-tree.txt" <<'PY'
import hashlib, sys, os
root, lst = sys.argv[1], sys.argv[2]; bad = n = crlf = 0
for line in open(lst, encoding="utf-8"):
    meta, path = line.rstrip("\n").split("\t", 1); mode, typ, oid = meta.split()
    if typ != "blob": continue
    p = os.path.join(root, path)
    data = os.readlink(p).encode() if mode == "120000" else open(p, "rb").read()
    n += 1
    blob = lambda d: hashlib.sha1(b"blob %d\0" % len(d) + d).hexdigest()
    if blob(data) == oid: continue
    # upstream .gitattributes `*.ps1 text eol=crlf`: checkout converts LF->CRLF; the stored blob is LF.
    if path.endswith(".ps1") and blob(data.replace(b"\r\n", b"\n")) == oid: crlf += 1; continue
    bad += 1; print("MISMATCH", path)
print(f"upstream blobs verified: {n}, ps1 eol=crlf checkouts: {crlf}, mismatches: {bad}"); sys.exit(1 if bad else 0)
PY
tar -xf $IN/overlay.tar -C $B/tmp/s
(cd $B/tmp/s/src && sha256sum -c --quiet <(grep -v personality $IN/hermes-patched.sha256 | sed 's/ \*/  /')) && echo "overlay = F7/PROD hashes OK"
echo "== uv $UV_VER"
cd $B/tmp && curl -fsSLO https://github.com/astral-sh/uv/releases/download/$UV_VER/uv-x86_64-unknown-linux-gnu.tar.gz \
  && curl -fsSLO https://github.com/astral-sh/uv/releases/download/$UV_VER/uv-x86_64-unknown-linux-gnu.tar.gz.sha256
sha256sum -c uv-x86_64-unknown-linux-gnu.tar.gz.sha256
mkdir -p $P/uv && tar -xzf uv-x86_64-unknown-linux-gnu.tar.gz -C $P/uv --strip-components=1
UV=$P/uv/uv; $UV --version
echo "== CPython $PY_VER"
$UV python list $PY_VER --all-platforms --output-format json 2>/dev/null | python3 -c 'import json,sys; [print("PBS", d.get("key"), d.get("url")) for d in json.load(sys.stdin) if "linux-x86_64-gnu" in d.get("key","") and d.get("variant","default") in ("default",None)]' || true
$UV python install $PY_VER
PYDIR=$(dirname "$(dirname "$($UV python find $PY_VER)")"); echo "python dir: $PYDIR"
mkdir -p $P/python && cp -a "$PYDIR" $P/python/cpython-$PY_VER-linux-x86_64-gnu
PY=$P/python/cpython-$PY_VER-linux-x86_64-gnu/bin/python3.11; $PY -VV
echo "== locked requirement set"
cd $B/tmp/s/src && $UV export --frozen --no-dev --no-emit-project --format requirements-txt -o $B/tmp/requirements.locked.txt >/dev/null
grep -c '^[a-z]' $B/tmp/requirements.locked.txt
echo "== wheelhouse"
mkdir -p $P/wheelhouse
$PY -m pip --version
$PY -m pip download --disable-pip-version-check --no-deps --require-hashes --only-binary=:all: \
  -r $B/tmp/requirements.locked.txt -d $P/wheelhouse 2>&1 | tail -5
# Build backend for the offline editable install of the project (pyproject: setuptools==83.0.0; not in uv.lock).
mkdir -p $P/buildbackend && $PY -m pip download --disable-pip-version-check --no-deps --only-binary=:all: \
  setuptools==83.0.0 -d $P/buildbackend 2>&1 | tail -1
cp -a $B/tmp/requirements.locked.txt $P/requirements.locked.txt
mv $B/tmp/s/src $P/src
ls $P/wheelhouse | wc -l
echo STAGE1_DONE
