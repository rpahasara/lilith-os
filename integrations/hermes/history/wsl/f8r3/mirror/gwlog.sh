#!/usr/bin/env bash
q=/var/backups/hermes-gateway-dev/rollback-20261023T100543Z/hermes-dev/logs
tail -n 30 $q/gateway.log | cut -c1-230
echo ==err; tail -n 10 $q/errors.log | cut -c1-230
