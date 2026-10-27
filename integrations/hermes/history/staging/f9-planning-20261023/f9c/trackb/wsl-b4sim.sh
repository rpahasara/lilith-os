set -u
export PYTHONDONTWRITEBYTECODE=1
B=/root/trackb-base2; rm -rf $B; mkdir -p $B; tar -xf /root/base2.tar -C $B
S=/root/trackb-b4sim; rm -rf $S; cp -a /root/trackb-tb $S
python3 - $S <<'PY'
import sys; from pathlib import Path
s = Path(sys.argv[1])
p = s / "services/authority-dev/ceremony/install_authority_dev.py"; t = p.read_text()
old = '"__init__.py", "profile.py", "credential.py", "storage.py", "writer.py", "protocol.py", "core.py", "server.py")),'
assert t.count(old) == 1; t = t.replace(old, old[:-3] + ', "privacy_anchor.py")),')
old = '"lilith_memory/__init__.py", "lilith_memory/canonical_contracts.py", "lilith_memory/owner_proof.py",'
assert t.count(old) == 1; t = t.replace(old, old + ' "lilith_memory/privacy_anchor_contracts.py",')
p.write_text(t)
p = s / "services/authority-dev/release_file_set.py"; t = p.read_text()
old = 'SHARED_HASHES = {\n'
assert t.count(old) == 1
t = t.replace(old, old + '    "services/core-api/lilith_memory/privacy_anchor_contracts.py": "58e954af7988115740fee8097d8d3248f47861a7b4046fc63bf9b0f3903fd768",\n')
p.write_text(t)
print("B4 simulation applied (WSL copy only)")
PY
for tree in base2 b4sim tb; do
  out=/root/trackb-$tree-ad.log
  (cd /root/trackb-$tree/services/authority-dev && PYTHONPATH=/root/l1deps timeout 1800 python3 -B -m unittest discover -s tests -p "test_*.py" > $out 2>&1)
  grep -E '^(FAIL|ERROR): ' $out | sed 's/ (\(.*\))$/ \1/' | sort > /root/trackb-$tree-ad.failset
  echo "$tree authority-dev: $(grep -E '^Ran ' $out) | $(grep -E '^(OK|FAILED)' $out) | failures=$(wc -l < /root/trackb-$tree-ad.failset)"
done
cmp -s /root/trackb-base2-ad.failset /root/trackb-b4sim-ad.failset && echo "b4sim vs main: failure set IDENTICAL" || { echo "b4sim vs main DIFFERS:"; diff /root/trackb-base2-ad.failset /root/trackb-b4sim-ad.failset | head; }
echo "tb (no B4) extra vs main: $(comm -13 /root/trackb-base2-ad.failset /root/trackb-tb-ad.failset | wc -l); reasons: $(grep -hoE 'InstallError: [A-Z_]+|AssertionError: Items in the (first|second) set' /root/trackb-tb-ad.log | sort | uniq -c | tr -s ' ' | paste -sd';')"
for tree in base2 b4sim; do
  out=/root/trackb-$tree-omc.log
  (cd /root/trackb-$tree/services/owner-memory-control && PYTHONPATH=/root/l1deps timeout 1800 python3 -B -m unittest discover -s tests -p "test_*.py" > $out 2>&1)
  grep -E '^(FAIL|ERROR): ' $out | sed 's/ (\(.*\))$/ \1/' | sort > /root/trackb-$tree-omc.failset
  echo "$tree OMC: $(grep -E '^Ran ' $out) | $(grep -E '^(OK|FAILED)' $out) | failures=$(wc -l < /root/trackb-$tree-omc.failset)"
done
cmp -s /root/trackb-base2-omc.failset /root/trackb-b4sim-omc.failset && echo "OMC b4sim vs main: failure set IDENTICAL" || { echo "OMC DIFFERS"; diff /root/trackb-base2-omc.failset /root/trackb-b4sim-omc.failset | head; }
(cd $B/services/recovery-witness && PYTHONPATH=/root/l1deps python3 -B -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -1 | sed 's/^/main witness: /')
