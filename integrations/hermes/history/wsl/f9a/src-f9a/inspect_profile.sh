#!/usr/bin/env bash
# READ-ONLY: operate profile mechanics and gateway/gate unit coupling in the F9-A build.
set -u
P=/root/f9a/build/pkg
sed -n 1,70p $P/bin/apply_profile.sh
echo "==== 10-operate.conf"; cat $P/profiles/operate/10-operate.conf
echo "==== base vs operate config (non-comment)"; diff <(grep -v '^\s*#' $P/home/config.yaml) <(grep -v '^\s*#' $P/profiles/operate/config.yaml)
echo "==== unit coupling"; grep -nE '^(Requires|BindsTo|Wants|After|PartOf|Restart)=' $P/systemd/hermes-gateway-dev.service $P/systemd/hermes-provider-gate-dev.service
grep -n 'StandardOutput\|StandardError\|LogNamespace\|Environment=' $P/systemd/hermes-gateway-dev.service
