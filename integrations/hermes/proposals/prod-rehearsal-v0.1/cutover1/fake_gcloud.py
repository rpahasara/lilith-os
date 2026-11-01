"""Scripted stand-in for gcloud and the IAP policy endpoint. TEST_ONLY: it reaches nothing. Every call is logged to C_STATE."""
import json
import os
import sys
from pathlib import Path

a = " ".join(sys.argv[1:])
f = os.environ.get("C_FAKE", "")
state = Path(os.environ["C_STATE"])
tunnel = state.with_suffix(".tunnel")
with state.open("a") as h:
    h.write(a + "\n")
if sys.argv[1] in ("getIamPolicy", "setIamPolicy"):
    if sys.argv[1] == "setIamPolicy":
        if f == "tunnel_fails":
            print(json.dumps({"etag": "x"}))
            sys.exit(0)
        tunnel.write_text(json.dumps(json.loads(sys.argv[2])["policy"]["bindings"]))
    print(json.dumps({"etag": "e1", "bindings": json.loads(tunnel.read_text()) if tunnel.exists() else []}))
    sys.exit(0)
if "firewall-rules describe" in a:
    print(json.dumps({"targetTags": ["x"] if f == "fw_tagged" else None, "sourceRanges": ["35.235.240.0/20"], "allowed": [{"ports": ["8765"]}]}))
elif "instances list" in a:
    rows = [{"name": "lilith-01", "tags": {"items": ["lilith-vm"]}}, {"name": "lilith-dev-01", "tags": {"items": ["lilith-vm"]}}]
    print(json.dumps(rows + ([{"name": "other", "tags": {}}] if f == "extra_vm" else [])))
elif "get-iam-policy" in a:
    roles = ["roles/compute.viewer"] + (["roles/compute.osAdminLogin"] if f == "deployer_wide" else [])
    print(json.dumps({"bindings": [{"role": r, "members": ["serviceAccount:github-lilith-deployer@lilith-agent-260823-27389.iam.gserviceaccount.com"]} for r in roles]}))
elif "disks describe" in a:
    print(json.dumps({"name": "lilith-01", "resourcePolicies": ["p"] if f == "has_schedule" else None}))
elif "firewall-rules update" in a and f == "fw_update_fails":
    sys.exit(1)
elif "add-iam-policy-binding" in a and f == "login_fails":
    sys.exit(1)
elif "resource-policies create" in a and f == "schedule_fails":
    sys.exit(1)
elif "add-resource-policies" in a and f == "attach_fails":
    sys.exit(1)
elif "compute scp" in a and f == "scp_fails":
    sys.exit(1)
elif "compute ssh" in a:
    if "cat /etc/lilith-os-api/auth.env" in a:
        if f != "no_tokens":
            print("LILITH_OS_READ_TOKEN=" + "a" * 64)
            print("LILITH_OS_WRITE_TOKEN=" + "b" * 64)
    elif f != "stage_fails":
        print("STAGED")
elif "snapshots describe" in a:
    print(json.dumps({"status": "CREATING" if f == "snap_not_ready" else "READY", "sourceDisk": "x/" + ("lilith-dev-01" if f == "snap_other_disk" else "lilith-01")}))
elif "instances stop" in a and f == "stop_fails":
    sys.exit(1)
elif "attach-disk" in a and "detach" not in a and f == "attach_boot_fails":
    sys.exit(1)
