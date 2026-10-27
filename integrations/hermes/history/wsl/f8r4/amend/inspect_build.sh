#!/usr/bin/env bash
# READ-ONLY: show how the F8r4 package is built (stage scripts, package source tree, where F7 files come from).
set -u
cd /root/f8r4
echo "== build-stage2-r4.sh"; cat build-stage2-r4.sh
echo "== pkgfiles tree (depth 3)"; find pkgfiles -maxdepth 3 | sort | head -80
echo "== stage1 (f8hd)"; ls /root/f8hd; sed -n 1,80p /root/f8hd/build-stage1.sh
