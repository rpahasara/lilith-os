import subprocess, sys, os
from pathlib import Path
root = Path(sys.argv[1]); W = root / "services/recovery-witness"
P = W / "lilith_recovery_witness/privacy_anchor.py"; C = W / "lilith_recovery_witness/credential.py"; S = W / "lilith_recovery_witness/server.py"
M = [
 ("W1 anchor served on any socket", S, "        if role == W.OWNER and anchor is not None and PAN.is_anchor_frame(frame):", "        if anchor is not None and PAN.is_anchor_frame(frame):"),
 ("W2 stale previous digest accepted", P, "            if payload[\"previousAnchorDigest\"] != chain.digest:", "            if False:"),
 ("W3 owner pin ignored", P, "        if body[\"setHead\"] != payload[\"expectedSetHead\"]:", "        if False:"),
 ("W4 signer skips extension re-verify", C, "            PA.verify_anchor_chain(previous + [signed], self.verifying_key(), environment=self.environment,\n                                   key_id=self.anchor_key_id)", "            pass"),
 ("W5 stored chain not verified", P, "        if not docs:\n            return None\n        try:", "        if True:\n            return None\n        try:"),
 ("W6 K-PAN may equal K-WIT", C, "    if witness_key is not None and anchor_key.public_key() == witness_key.public_key():", "    if False:"),
 ("W7 chain gap tolerated", P, "                if match is None or int(match.group(1)) != expected:", "                if match is None:"),
 ("W8 genesis twice", P, "        if message.operation == GENESIS_PRIVACY_ANCHOR and chain is not None:", "        if False:"),
]
env = dict(os.environ, PYTHONPATH="/root/l1deps", PYTHONDONTWRITEBYTECODE="1")
def run():
    return subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], cwd=W, env=env, capture_output=True, text=True).returncode == 0
caught = 0
for name, path, old, new in M:
    src = path.read_text()
    assert src.count(old) == 1, name
    try:
        path.write_text(src.replace(old, new)); ok = run()
    finally:
        path.write_text(src)
    caught += not ok; print(("CAUGHT  " if not ok else "SURVIVED"), name)
print(f"B2 mutations caught {caught}/{len(M)}; clean ok={run()}")
