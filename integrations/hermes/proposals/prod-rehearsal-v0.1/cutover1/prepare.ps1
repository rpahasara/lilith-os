# Cutover 1 preparation (PREPARED, NOT APPROVED, NOT RUN). Needs its own owner approval: APPROVED_PREPARE and the phrase.
# Firewall target, the deployer's lilith-01-only access, the daily snapshot schedule, then the guest files for the read-only review. Changes no LILITH runtime file and no service.
# Stops at the first failure, with no retry. undo_prepare.ps1 reverses every step.
param([Parameter(Mandatory = $true)][string]$Confirm)
. "$PSScriptRoot\common.ps1"
if ($Confirm -ne 'PREPARE-CUTOVER1') { Write-Output 'PREPARE REFUSED confirmation'; exit 3 }
$digest = (Get-FileHash "$Here\MANIFEST.txt" -Algorithm SHA256).Hash.ToLower()
if (-not (Test-Path "$Here\APPROVED_PREPARE") -or (Get-Content "$Here\APPROVED_PREPARE" -Raw).Trim() -ne $digest) { Write-Output 'PREPARE REFUSED not approved'; exit 3 }
if (Test-Path "$Out\started") { Write-Output 'PREPARE STOPPED already started'; exit 2 }
New-Item -ItemType Directory -Force $Out | Out-Null

# Read first: anything other than the recorded state stops with nothing changed.
$r = Invoke-G @('compute', 'firewall-rules', 'describe', $Rule, "--project=$Project", '--format=json')
if ($r.Code -ne 0) { Stop-Here 'STOPPED firewall read' }
$fw = $r.Text | ConvertFrom-Json
if ($fw.targetTags -or ($fw.sourceRanges -join ',') -ne '35.235.240.0/20' -or ($fw.allowed.ports -join ',') -ne '8765') { Stop-Here 'STOPPED firewall rule is not as recorded' }
$r = Invoke-G @('compute', 'instances', 'list', "--project=$Project", '--format=json')
if ($r.Code -ne 0) { Stop-Here 'STOPPED instance read' }
$all = @($r.Text | ConvertFrom-Json)
$tagged = @($all | Where-Object { $_.tags.items -contains $Tag } | ForEach-Object { $_.name } | Sort-Object)
if (($tagged -join ',') -ne 'lilith-01,lilith-dev-01' -or $all.Count -ne 2) { Stop-Here 'STOPPED instances are not as recorded' }
if ((@(Get-DeployerRoles) -join ',') -ne 'roles/compute.viewer') { Stop-Here 'STOPPED deployer is not as recorded' }
$policy = Get-TunnelPolicy
if (@($policy.bindings | Where-Object { $_ }).Count) { Stop-Here 'STOPPED instance tunnel policy is not empty' }
$r = Invoke-G @('compute', 'disks', 'describe', $Disk, "--zone=$Zone", "--project=$Project", '--format=json')
if ($r.Code -ne 0 -or ($r.Text | ConvertFrom-Json).resourcePolicies) { Stop-Here 'STOPPED disk already has a schedule, or could not be read' }
$r.Text | Out-File -Encoding utf8 "$Out\disk-before.json"
$fw | ConvertTo-Json -Depth 8 | Out-File -Encoding utf8 "$Out\firewall-before.json"
New-Item -ItemType File "$Out\started" | Out-Null

# 1. Firewall: the API rule covers tagged Lilith hosts, not every VM in the network. Both hosts already carry the tag, so neither loses its route.
$r = Invoke-G @('compute', 'firewall-rules', 'update', $Rule, "--target-tags=$Tag", "--project=$Project", '--format=none')
if ($r.Code -ne 0) { Stop-Here "STOPPED firewall update rc $($r.Code)" }
# 2. Deployer: admin login on lilith-01 only, and the tunnel on lilith-01 port 22 only.
$r = Invoke-G @('compute', 'instances', 'add-iam-policy-binding', $Vm, "--zone=$Zone", "--project=$Project", "--member=$Deployer", '--role=roles/compute.osAdminLogin', '--format=none')
if ($r.Code -ne 0) { Stop-Here "STOPPED instance login grant rc $($r.Code)" }
$binding = @{ role = 'roles/iap.tunnelResourceAccessor'; members = @($Deployer); condition = @{ title = 'lilith-01-ssh-only'; expression = 'destination.port == 22' } }
$set = @{ policy = @{ version = 3; etag = $policy.etag; bindings = @($binding) } }
Invoke-Iap 'setIamPolicy' $set | Out-Null
$back = Get-TunnelPolicy
$b = @(@($back.bindings) | Where-Object { $_.role -eq 'roles/iap.tunnelResourceAccessor' -and $_.members -contains $Deployer -and $_.condition.expression -eq 'destination.port == 22' })
if ($b.Count -ne 1 -or @($back.bindings | Where-Object { $_ }).Count -ne 1) { Stop-Here 'STOPPED tunnel binding not confirmed' }
# 3. Backups: daily, 30 days, stored multi-regionally, kept if the disk is ever deleted.
$r = Invoke-G @('compute', 'resource-policies', 'create', 'snapshot-schedule', $Schedule, "--region=$Region", "--project=$Project", '--max-retention-days=30', '--on-source-disk-delete=keep-auto-snapshots', '--daily-schedule', '--start-time=18:00', '--storage-location=asia', '--format=none')
if ($r.Code -ne 0) { Stop-Here "STOPPED schedule create rc $($r.Code)" }
$r = Invoke-G @('compute', 'disks', 'add-resource-policies', $Disk, "--zone=$Zone", "--project=$Project", "--resource-policies=$Schedule", '--format=none')
if ($r.Code -ne 0) { Stop-Here "STOPPED schedule attach rc $($r.Code)" }
# 4. Guest files for the read-only review, root-owned, checked by digest. Nothing runs here.
$files = 'guest_c1.sh', 'live_compare.py', 'rehearsal_compare.py'
Push-Location $Here   # a relative path: gcloud scp can read C:\ as a remote host
foreach ($f in @($files) + 'stage_c1.sh') {
    $r = Invoke-G @('compute', 'scp', '--quiet', "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', $f, "${Vm}:/tmp/c1-$f")
    if ($r.Code -ne 0) { Pop-Location; Stop-Here "STOPPED upload $f rc $($r.Code)" }
}
Pop-Location
$sums = ($files | ForEach-Object { (Get-FileHash (Join-Path $Here $_) -Algorithm SHA256).Hash.ToLower() }) -join ' '
$r = Invoke-G @('compute', 'ssh', $Vm, "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet', "--command=sudo -n bash /tmp/c1-stage_c1.sh $sums")
if ($r.Text -notmatch '(?m)^STAGED') { Stop-Here 'STOPPED guest files not confirmed' }
Stop-Here 'PASS' 0
