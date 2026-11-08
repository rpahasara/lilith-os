#!/usr/bin/env bash
# PREPARED, NOT RUN. Needs its own owner approval. Read-only cloud describes of PROD's network posture, from the owner's gcloud.
# No SSH, no IAP tunnel, no connection to port 8765, and no create, update or delete call. Prints names and rules, no secrets.
set -u
P=lilith-agent-260823-27389
Z=asia-southeast1-b
VM=lilith-01
echo "== interfaces"
gcloud compute instances describe "$VM" --project="$P" --zone="$Z" --format='json(networkInterfaces[].network,networkInterfaces[].networkIP,networkInterfaces[].accessConfigs,networkInterfaces[].ipv6AccessConfigs,tags.items)'
echo "== firewall rules"
gcloud compute firewall-rules list --project="$P" --format='table(name,network.basename(),direction,sourceRanges.list(),allowed[].map().firewall_rule().list(),targetTags.list(),disabled)'
echo "== forwarding"
gcloud compute forwarding-rules list --project="$P" --format='table(name,IPAddress,target.basename())'
gcloud compute target-tcp-proxies list --project="$P" --format='value(name)'
gcloud compute target-http-proxies list --project="$P" --format='value(name)'
echo "== network firewall policies"
gcloud compute network-firewall-policies list --project="$P" --format='value(name)'
echo "== who can tunnel: project"
gcloud projects get-iam-policy "$P" --flatten='bindings[].members' --filter='bindings.role:(roles/owner OR roles/editor OR roles/iap.tunnelResourceAccessor OR roles/compute.osAdminLogin OR roles/compute.osLogin)' --format='table(bindings.role,bindings.members,bindings.condition.title)'
echo "== who can tunnel: instance"
gcloud iap tcp iam get-iam-policy --project="$P" --zone="$Z" --resource-type=compute --service="$VM" 2>&1 | head -40
echo "PROD_EXPOSURE_PREFLIGHT_DONE"
