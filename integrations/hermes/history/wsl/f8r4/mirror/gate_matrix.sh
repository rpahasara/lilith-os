#!/usr/bin/env bash
# F8r4 adversarial provider-gate matrix (WSL mirror ONLY; synthetic provider). Pre-condition: f8r4 installed, synthetic
# key provisioned, gate running. Every case asserts: HTTP status, provider-side request delta, ledger (R line) delta.
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || exit 1
W=/root/f8r4; SY=$W/synth; L=/var/lib/private/hermes-provider-gate-dev/ledger.log; P=${P:?}
OUT=${1:?outfile}; : > "$OUT"; T=__LILITH_GATE_CLIENT_TOKEN__; URL=http://127.0.0.1:9911/openai/v1/chat/completions
fc() { local c; c=$(grep -c . $SY/requests.jsonl 2>/dev/null); echo "${c:-0}"; }
lc() { local c; c=$(grep -c '^R ' $L 2>/dev/null); echo "${c:-0}"; }
mode() { echo "$1" > $SY/mode; }
reset_budget() { bash $P/bin/gate_budget.sh reset --owner-approved "matrix-$1" >/dev/null; }
up() { for i in $(seq 1 30); do ss -Hltn 'sport = :9911' | grep -q . && return 0; sleep 1; done; return 1; }
post() { curl -s -m 100 -o /tmp/f8m.body -w '%{http_code}' -H "Authorization: Bearer $T" -H 'Content-Type: application/json' "$@" $URL; }
B='{"model":"openai/gpt-oss-120b","messages":[{"role":"user","content":"F8-SYNTHETIC matrix"}]'
case_() {  # name expected_code expected_dfake expected_dledger -- command...
  local name=$1 ec=$2 ef=$3 el=$4; shift 5
  local f0 l0 code f1 l1; f0=$(fc); l0=$(lc); code=$("$@"); sleep 0.3; f1=$(fc); l1=$(lc)
  local df=$((f1 - f0)) dl=$((l1 - l0)) ok=PASS
  [[ $code == "$ec" && $df == "$ef" && $dl == "$el" ]] || ok=FAIL
  printf '%s\t%s\tcode=%s(exp %s) provider+%s(exp %s) ledger+%s(exp %s) %s\n' "$ok" "$name" "$code" "$ec" "$df" "$ef" "$dl" "$el" \
    "$(head -c 90 /tmp/f8m.body 2>/dev/null | tr -d '\n')" | tee -a "$OUT"
}
last_req() { tail -1 $SY/requests.jsonl; }
mode ok; reset_budget start
echo "== policy, streaming and non-streaming"
case_ M01-nonstream-ok 200 1 1 -- post -d "$B}"
python3 -c 'import json,sys;r=json.loads(sys.argv[1]);assert r["auth_ok"] and r["max_completion_tokens"]==1024 and r["reasoning_effort"]=="low" and not r["tools"] and not r["stream"]' "$(last_req)" \
  && echo -e "PASS\tM01b provider saw: key injected, cap 1024, effort low, no tools" | tee -a "$OUT" || echo -e "FAIL\tM01b $(last_req)" | tee -a "$OUT"
case_ M02-stream-max_tokens-99999 200 1 1 -- post -d "$B,\"stream\":true,\"max_tokens\":99999}"
python3 -c 'import json,sys;r=json.loads(sys.argv[1]);assert r["stream"] is True and r["max_completion_tokens"]==1024 and r["max_tokens"] is None' "$(last_req)" \
  && echo -e "PASS\tM02b stream clamped to max_completion_tokens 1024" | tee -a "$OUT" || echo -e "FAIL\tM02b $(last_req)" | tee -a "$OUT"
case_ M03-stream-tools 400 0 0 -- post -d "$B,\"stream\":true,\"tools\":[{\"type\":\"browser_search\"}]}"
case_ M04-stream-tool_choice 400 0 0 -- post -d "$B,\"stream\":true,\"tool_choice\":\"auto\"}"
case_ M05-stream-other-model 400 0 0 -- post -d '{"model":"compound-beta","stream":true,"messages":[{"role":"user","content":"x"}]}'
case_ M06-role-tool 400 0 0 -- post -d '{"model":"openai/gpt-oss-120b","messages":[{"role":"tool","content":"x","tool_call_id":"1"}]}'
case_ M07-assistant-tool_calls 400 0 0 -- post -d '{"model":"openai/gpt-oss-120b","messages":[{"role":"assistant","content":"","tool_calls":[{"id":"1"}]},{"role":"user","content":"x"}]}'
case_ M08-n-2 400 0 0 -- post -d "$B,\"n\":2}"
case_ M09-response_format 400 0 0 -- post -d "$B,\"response_format\":{\"type\":\"json_object\"}}"
case_ M10-stream-non-bool 400 0 0 -- post -d "$B,\"stream\":\"yes\"}"
echo "== smuggling / open proxy"
case_ M11-absolute-form 404 0 0 -- curl -s -m 10 -o /tmp/f8m.body -w '%{http_code}' -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
  --request-target 'http://evil.example/openai/v1/chat/completions' -d "$B}" http://127.0.0.1:9911/
case_ M12-host-header-spoof 200 1 1 -- post -H 'Host: evil.example' -d "$B}"
case_ M13-chunked-body 411 0 0 -- curl -s -m 10 -o /tmp/f8m.body -w '%{http_code}' -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -H 'Transfer-Encoding: chunked' -d "$B}" $URL
case_ M14-CONNECT 405 0 0 -- python3 -c 'import socket;s=socket.create_connection(("127.0.0.1",9911),5);s.sendall(b"CONNECT 169.254.169.254:80 HTTP/1.1\r\nHost: 169.254.169.254:80\r\n\r\n");print(s.recv(64).split()[1].decode())'
case_ M15-other-path 404 0 0 -- curl -s -m 10 -o /tmp/f8m.body -w '%{http_code}' -H "Authorization: Bearer $T" -d '{}' http://127.0.0.1:9911/openai/v1/responses
case_ M16-no-client-token 401 0 0 -- curl -s -m 10 -o /tmp/f8m.body -w '%{http_code}' -H 'Content-Type: application/json' -d "$B}" $URL
case_ M17-HEAD 405 0 0 -- curl -s -m 10 -o /tmp/f8m.body -w '%{http_code}' -I $URL
echo "== upstream failures (no retry; every attempt after TLS is spent exactly once)"
reset_budget failures
mode fail500;   case_ M20-upstream-500 500 1 1 -- post -d "$B}"
mode ratelimit; case_ M21-upstream-429 429 1 1 -- post -d "$B}"
mode redirect;  case_ M22-upstream-302-not-followed 302 1 1 -- post -d "$B}"
mode reset;     case_ M23-midstream-reset 200 1 1 -- post -d "$B,\"stream\":true}"
mode bigtokens; case_ M24-token-report-over-cap 200 1 1 -- post -d "$B}"
journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager | tail -3 | grep -q '"token_cap_anomaly": true' \
  && echo -e "PASS\tM24b over-cap usage flagged token_cap_anomaly=true (acceptance stop condition)" | tee -a "$OUT" || echo -e "FAIL\tM24b anomaly not flagged" | tee -a "$OUT"
reset_budget timeout
mode slow;      case_ M25-upstream-timeout 502 1 1 -- post -d "$B}"
mode ok
echo "== destinations: DNS rebinding, metadata, private, untrusted certificate (nothing sent, nothing spent)"
reset_budget destinations
for tgt in 169.254.169.254 10.20.0.2 127.0.0.2 100.64.1.1 192.168.1.10; do
  sed -i "s/^[0-9.]* api.groq.com # f8r3-synthetic-provider/$tgt api.groq.com # f8r3-synthetic-provider/" /etc/hosts
  case_ "M3x-rebind-$tgt" 502 0 0 -- post -d "$B}"
done
sed -i "s/^[0-9.]* api.groq.com # f8r3-synthetic-provider/1.2.3.4 api.groq.com # f8r3-synthetic-provider/" /etc/hosts
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=api.groq.com" -addext "subjectAltName=DNS:api.groq.com" -keyout $SY/rogue.key -out $SY/rogue.pem 2>/dev/null
systemctl stop f8r3-fake-groq; systemctl reset-failed f8r3-fake-groq 2>/dev/null
systemd-run --unit=f8r3-fake-groq --quiet /usr/bin/python3 -I -B $W/mirror/fake_groq.py 1.2.3.4 $SY/rogue.pem $SY/rogue.key $SY/synthetic-key $SY; sleep 1
case_ M40-untrusted-cert-for-api.groq.com 502 0 0 -- post -d "$B}"
systemctl stop f8r3-fake-groq; systemctl reset-failed f8r3-fake-groq 2>/dev/null
systemd-run --unit=f8r3-fake-groq --quiet /usr/bin/python3 -I -B $W/mirror/fake_groq.py 1.2.3.4 $SY/srv.pem $SY/srv.key $SY/synthetic-key $SY; sleep 1
grep -h '"reason": "UPSTREAM' <(journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager | tail -8) | cut -c1-150 | sed 's/^/INFO\t/' | tee -a "$OUT"
echo "== budget: exhaustion, persistence across SIGKILL / restart / in-flight crash, corrupt ledger"
reset_budget persistence
for i in 1 2 3; do case_ "M50-spend-$i" 200 1 1 -- post -d "$B}"; done
systemctl reset-failed hermes-provider-gate-dev; systemctl kill -s KILL hermes-provider-gate-dev; sleep 12; up
b=$(curl -s http://127.0.0.1:9911/healthz | python3 -c 'import json,sys;print(json.load(sys.stdin)["budget_used"])')
[[ $b == 3 ]] && echo -e "PASS\tM51 budget_used=3 after SIGKILL + automatic restart" | tee -a "$OUT" || echo -e "FAIL\tM51 budget_used=$b" | tee -a "$OUT"
systemctl reset-failed hermes-provider-gate-dev; systemctl restart hermes-provider-gate-dev; up
b=$(curl -s http://127.0.0.1:9911/healthz | python3 -c 'import json,sys;print(json.load(sys.stdin)["budget_used"])')
[[ $b == 3 ]] && echo -e "PASS\tM52 budget_used=3 after service restart" | tee -a "$OUT" || echo -e "FAIL\tM52 budget_used=$b" | tee -a "$OUT"
mode slow; f0=$(fc); l0=$(lc)
systemctl reset-failed hermes-provider-gate-dev; ( post -d "$B}" >/dev/null ) & sleep 4; systemctl kill -s KILL hermes-provider-gate-dev; wait; sleep 12; up; mode ok
f1=$(fc); l1=$(lc); b=$(curl -s http://127.0.0.1:9911/healthz | python3 -c 'import json,sys;print(json.load(sys.stdin)["budget_used"])')
[[ $((l1 - l0)) == 1 && $((f1 - f0)) == 1 && $b == 4 ]] && echo -e "PASS\tM53 crash during an in-flight request: reservation persisted (4), provider saw 1, no refund, no retry" | tee -a "$OUT" \
  || echo -e "FAIL\tM53 ledger+$((l1 - l0)) provider+$((f1 - f0)) budget=$b" | tee -a "$OUT"
case_ M54-spend-5th 200 1 1 -- post -d "$B}"
case_ M55-6th-refused-exhausted 429 0 0 -- post -d "$B}"
systemctl reset-failed hermes-provider-gate-dev; systemctl restart hermes-provider-gate-dev; up
case_ M56-still-exhausted-after-restart 429 0 0 -- post -d "$B}"
cp -p $L /root/f8r4/ledger.bak; echo 'garbage-line' >> $L
case_ M57-corrupt-ledger-fails-closed 503 0 0 -- post -d "$B}"
cp -p /root/f8r4/ledger.bak $L
case_ M58-ledger-restored-still-exhausted 429 0 0 -- post -d "$B}"
h=$(curl -s http://127.0.0.1:9911/healthz); grep -q gsk_ <<< "$h" && echo -e "FAIL\tM59 healthz leaks key material" | tee -a "$OUT" || echo -e "PASS\tM59 healthz carries no key material: $h" | tee -a "$OUT"
grep -qF -- "$(cat $SY/synthetic-key)" <(journalctl --namespace=hermes-gateway-dev -o cat --no-pager; cat $L) \
  && echo -e "FAIL\tM60 key found in gate journal/ledger" | tee -a "$OUT" || echo -e "PASS\tM60 key absent from gate journal and ledger" | tee -a "$OUT"
reset_budget matrix-end
echo "MATRIX: $(grep -c '^PASS' "$OUT") PASS / $(grep -c '^FAIL' "$OUT") FAIL"
