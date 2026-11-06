#!/bin/bash
# Tests for lilith-deploy against a fake host root (run as a normal user on Linux: bash deploy/prod/test_lilith_deploy.sh)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
D=$HERE/lilith-deploy
pass=0; fail=0
ok() { pass=$((pass+1)); echo "ok   $1"; }
bad() { fail=$((fail+1)); echo "FAIL $1"; }

setup() {
  T=$(mktemp -d); R=$T/root
  mkdir -p $R/home/lilith/.hermes/lilith-os/api $R/home/lilith/.hermes/lilith_router $R/var/log \
           $R/home/lilith/.hermes/lilith-os/api-venv/bin $R/home/lilith/.hermes/hermes-agent/venv/bin
  ln -s "$(command -v python3)" $R/home/lilith/.hermes/lilith-os/api-venv/bin/python
  ln -s "$(command -v python3)" $R/home/lilith/.hermes/hermes-agent/venv/bin/python
  echo 'print("old app")' > $R/home/lilith/.hermes/lilith-os/api/app.py; chmod 700 $R/home/lilith/.hermes/lilith-os/api/app.py
  echo 'X = 1' > $R/home/lilith/.hermes/lilith_router/policy.py; chmod 600 $R/home/lilith/.hermes/lilith_router/policy.py
  printf 'enabled: true\n' > $R/home/lilith/.hermes/lilith_router/router.yaml
  echo '{"keep": true}' > $R/home/lilith/.hermes/lilith_router/canonical_memory.json
  cat > $T/systemctl <<'EOF'
#!/bin/bash
echo "$*" >> "$(dirname "$0")/calls"
case "$1" in
  restart) [ -f "$(dirname "$0")/fail_restart" ] && exit 1; exit 0 ;;
  is-active) cat "$(dirname "$0")/state" 2>/dev/null || echo active ;;
  show) n=$(grep -c restart "$(dirname "$0")/calls"); [ -f "$(dirname "$0")/flap" ] && n=$((n + RANDOM)); echo "$n" ;;
esac
EOF
  cat > $T/curl <<'EOF'
#!/bin/bash
[ -f "$(dirname "$0")/unhealthy" ] && exit 22; echo '{"ok":true}'
EOF
  cat > $T/journalctl <<'EOF'
#!/bin/bash
cat "$(dirname "$0")/journal" 2>/dev/null; true
EOF
  chmod +x $T/systemctl $T/curl $T/journalctl
  export LILITH_DEPLOY_TEST_ROOT=$R TEST_SYSTEMCTL=$T/systemctl TEST_CURL=$T/curl TEST_JOURNALCTL=$T/journalctl
  unset SUDO_USER
}
SHA=0123456789abcdef0123456789abcdef01234567
bundle() { local d=$T/b; rm -rf $d; mkdir $d; while [ $# -gt 0 ]; do printf '%s' "$2" > "$d/$1"; shift 2; done
           (cd $d && tar -cf $T/bundle.tar *); }
run() { bash "$D" "$@" > $T/out 2>&1; echo $? > $T/rc; }
rc() { cat $T/rc; }

# 1 core-api deploy installs, keeps mode, restarts, logs
setup; bundle app.py 'print("new app")'; run core-api $T/bundle.tar $SHA
[ "$(rc)" = 0 ] && grep -q 'new app' $R/home/lilith/.hermes/lilith-os/api/app.py && \
  [ "$(stat -c %a $R/home/lilith/.hermes/lilith-os/api/app.py)" = 700 ] && grep -q "core-api $SHA DEPLOYED" $R/var/log/lilith-deploy.log \
  && ok "core-api deploy" || { bad "core-api deploy"; cat $T/out; }
# 2 same content again -> NOCHANGE, no restart
n=$(grep -c restart $T/calls); run core-api $T/bundle.tar $SHA
[ "$(rc)" = 0 ] && grep -q NOCHANGE $T/out && [ "$(grep -c restart $T/calls)" = "$n" ] && ok "nochange" || bad "nochange"
# 3 health failure -> rollback to the old file
setup; touch $T/unhealthy; bundle app.py 'print("broken")'; run core-api $T/bundle.tar $SHA
[ "$(rc)" = 1 ] && grep -q 'old app' $R/home/lilith/.hermes/lilith-os/api/app.py && grep -q ROLLED_BACK $R/var/log/lilith-deploy.log \
  && ok "health rollback" || { bad "health rollback"; cat $T/out; }
# 4 compile failure -> refused before any change
setup; bundle app.py 'def (:'; run core-api $T/bundle.tar $SHA
[ "$(rc)" = 2 ] && grep -q 'old app' $R/home/lilith/.hermes/lilith-os/api/app.py && [ ! -f $T/calls ] && ok "compile refusal" || bad "compile refusal"
# 5 names outside the component are refused
setup; bundle app.py 'x=1' other.py 'y=2'; run core-api $T/bundle.tar $SHA
[ "$(rc)" = 2 ] && grep -q 'not allowed: other.py' $T/out && ok "name allow-list" || bad "name allow-list"
setup; bundle canonical_memory.json '{}'; run router $T/bundle.tar $SHA
[ "$(rc)" = 2 ] && grep -q '{"keep": true}' $R/home/lilith/.hermes/lilith_router/canonical_memory.json && ok "router json refused" || bad "router json refused"
# 6 path traversal and symlinks are refused
setup; mkdir -p $T/b2/sub; echo x > $T/b2/sub/app.py; (cd $T/b2 && tar -cf $T/bundle.tar sub/app.py); run core-api $T/bundle.tar $SHA
[ "$(rc)" = 2 ] && ok "subdir refused" || bad "subdir refused"
setup; mkdir -p $T/b3; ln -s /etc/passwd $T/b3/app.py; (cd $T/b3 && tar -cf $T/bundle.tar app.py); run core-api $T/bundle.tar $SHA
[ "$(rc)" = 2 ] && grep -q non-regular $T/out && ok "symlink refused" || bad "symlink refused"
# 7 router deploy: only changed files, new file gets 600, other files untouched
setup; bundle policy.py 'X = 2' router.yaml $'enabled: true\n' social_lean.py 'Y = 1'; run router $T/bundle.tar $SHA
[ "$(rc)" = 0 ] && grep -q 'X = 2' $R/home/lilith/.hermes/lilith_router/policy.py && \
  [ "$(stat -c %a $R/home/lilith/.hermes/lilith_router/social_lean.py)" = 600 ] && \
  grep -q '{"keep": true}' $R/home/lilith/.hermes/lilith_router/canonical_memory.json && \
  grep -q 'DEPLOYED \[policy.py social_lean.py\]' $R/var/log/lilith-deploy.log && ok "router deploy" || { bad "router deploy"; cat $T/out; cat $R/var/log/lilith-deploy.log; }
# 8 router: traceback after restart -> rollback restores policy and removes the added file
setup; printf 'Traceback (most recent call last):\n' > $T/journal; bundle policy.py 'X = 3' new_mod.py 'Z = 1'; run router $T/bundle.tar $SHA
[ "$(rc)" = 1 ] && grep -q 'X = 1' $R/home/lilith/.hermes/lilith_router/policy.py && [ ! -e $R/home/lilith/.hermes/lilith_router/new_mod.py ] \
  && ok "router traceback rollback" || { bad "router traceback rollback"; cat $T/out; }
# 9 router: bad yaml refused
setup; bundle router.yaml $'a: [\n'; run router $T/bundle.tar $SHA
[ "$(rc)" = 2 ] && grep -q 'enabled: true' $R/home/lilith/.hermes/lilith_router/router.yaml && ok "yaml refusal" || bad "yaml refusal"
# 10 bad args
setup; bundle app.py 'x=1'; run core-api $T/bundle.tar notasha; [ "$(rc)" = 2 ] && ok "sha refused" || bad "sha refused"
run hermes $T/bundle.tar $SHA; [ "$(rc)" = 2 ] && ok "component refused" || bad "component refused"
SUDO_USER=x run core-api $T/bundle.tar $SHA; [ "$(rc)" = 2 ] && grep -q 'test mode under sudo' $T/out && ok "test mode refused under sudo" || bad "test mode under sudo"
# 11 status
run status; [ "$(rc)" = 0 ] && ok "status" || bad "status"

echo "passed $pass failed $fail"; [ $fail = 0 ]
