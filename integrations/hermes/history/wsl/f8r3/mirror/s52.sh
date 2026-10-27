#!/usr/bin/env bash
L=/var/backups/hermes-gateway-dev/rollback-20261023T092210Z/hermes-dev/logs
ls $L
grep -n -E 'f8b-s1|f8b-s2|interrupt|queued|busy|duplicate' $L/gateway.log $L/agent.log | cut -c1-260 | head -40
