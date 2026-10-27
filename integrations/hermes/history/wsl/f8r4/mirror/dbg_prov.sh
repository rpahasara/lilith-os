#!/usr/bin/env bash
wc -l /root/f8r4/synth/requests.jsonl
python3 - <<'PY'
import json
bad = 0
for i, l in enumerate(open('/root/f8r4/synth/requests.jsonl')):
    try:
        json.loads(l)
    except Exception as e:
        bad += 1
        print("bad line", i, repr(l[:120]), e)
print("bad", bad)
PY
sed -n '/^f1=\$(fakecount)$/,/^PY$/p' /root/f8r4/mirror/run_suite_r4.sh | head -12
grep -n 'H-G7 smoke' /root/f8r4/suite.log | head -3
