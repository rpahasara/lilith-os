# `dev-cognition-private-intent` overlay

`world_context.py`: the `dev-planning-hardening` adapter with the application number private on **every** lane, not only Planning.

**Why:** m1 records carried the application number in `intent.app_id` on the Cognitive, Goal and Reasoning records. The Planning candidate fixed only its own record, and the Ethics analysis found the same thing (E-5).

## The change

| Where | Before | After |
|---|---|---|
| The five `detect_*` entries | `app_id` in the intent the gateway logs | `app_id` null; the number sits under a private key that no log reads |
| Entries that read by application | used `app_id` | restore it from the private key, for that call only |

The gateway only logs `app_id`, so the record loses the number and the reads keep it. `gateway_integration.py` and the PROD module are unchanged. Reads still name the application in their path, so the Core API access log still carries it.

**The rest of the adapter** is the merged Planning candidate: hardened Planning detection, and one read per route within 1.5 seconds. FORGET stops the gateway, so the memo can't outlive an erasure.

**Evidence:** `release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1/tests/test_p1_planning.py`, on the real gateway, adapter and Core API.
