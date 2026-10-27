#!/usr/bin/env bash
# F9-C Track A mutation check (WSL, root). Each mutant breaks one hold-first safety rule; the named tests must fail.
# Sources are restored from a pristine copy after every mutant (and verified by hash at the end).
set -u
export PYTHONDONTWRITEBYTECODE=1
W=/root/f9ca; EXE=$W/tracka/pkgfiles/bin/hermes_forget_executor.py; CORE=$W/repo/services/core-api
PG=$CORE/lilith_memory/privacy_governance.py; FI=$CORE/lilith_memory/privacy_forget_intent.py; APP=$CORE/app.py
PY311=/root/f9b/build/pkg/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11
SAVE=$(mktemp -d); cp -p $EXE $PG $FI $APP $SAVE/; before=$(sha256sum $EXE $PG $FI $APP)
core() { (cd $CORE/tests && PYTHONPATH=/root/coreapi-deps:/root/l1deps timeout 900 $PY311 -B -m unittest "$@" 2>&1 | tail -1); }
matrix() { bash $W/matrix.sh "$@" | tail -1; }
mut() {  # <name> <file> <python replacement old> <new> <runner> <selector...>
  local name=$1 f=$2 old=$3 new=$4 runner=$5; shift 5
  python3 - "$f" "$old" "$new" <<'PY' || { echo "MUTANT $name NOT_APPLIED"; return; }
import sys
p, old, new = sys.argv[1:4]; s = open(p).read()
assert s.count(old) == 1, "pattern"
open(p, "w").write(s.replace(old, new))
PY
  r=$($runner "$@"); cp -p $SAVE/$(basename $f) $f
  [[ $r == OK ]] && echo "MUTANT $name SURVIVED" || echo "MUTANT $name DETECTED ($r)"
}
mut reconcile-releases-without-proof $EXE "and self._identity_completed():" "and True:" matrix \
  test_f9c_executor_matrix.HoldFirstMatrixTests
mut hold-never-takes-ownership $EXE "        os.fchown(fd, 0, cfg.receipt_gid)" "        pass" matrix \
  test_f9c_executor_matrix.HoldFirstMatrixTests
mut cancel-ignores-in-flight $EXE "if in_flight is not None or _journals_in_progress(self.cfg.state_dir):" "if False:" matrix \
  test_f9c_executor_matrix.HoldFirstMatrixTests.test_H5_H7_reconcile_never_releases_while_privacy_is_in_flight
mut runner-skips-the-hold $FI "            if self.intents.state() == HELD and self.gateway.stopped():" "            if True:" core \
  test_privacy_forget_intent
mut runner-releases-on-stall $FI "            if not str(exc).startswith(\"ACTOR_\"):" "            if True:" core \
  test_privacy_forget_intent
mut completion-ignores-required-owner $PG "and any(str(r[0]) == required_owner and str(r[1]) == \"COMPLETE\" for r in results):" "and bool(results):" core \
  test_privacy_forget_intent
mut completion-ignores-active-hold $PG "                return False
            suppression = conn.execute(" "                pass
            suppression = conn.execute(" matrix test_f9c_executor_matrix.HoldFirstMatrixTests.test_H5_H7_reconcile_never_releases_while_privacy_is_in_flight
mut relay-no-intent-check $APP "    raise HTTPException(status_code=503, detail=\"FORGET_HOLD_ACTIVE\")" "    return" core \
  test_privacy_forget_intent.RelayRefusalTests
mut relay-ignores-unreadable-state $APP "    except OSError:
        raise unavailable
    raise HTTPException(status_code=503, detail=\"FORGET_HOLD_ACTIVE\")" "    except OSError:
        return
    raise HTTPException(status_code=503, detail=\"FORGET_HOLD_ACTIVE\")" core test_privacy_forget_intent.RelayRefusalTests
mut delivery-ledger-not-purged $EXE '"delivery_obligations", "sessions"' '"sessions"' matrix   test_f9c_executor_matrix.HappyPathTests
after=$(sha256sum $EXE $PG $FI $APP); [[ $before == "$after" ]] && echo "SOURCES RESTORED" || echo "SOURCES DIFFER"
rm -rf $SAVE
